---
name: python-async-conventions
description: Async Python conventions for DigIdentity backend — FastAPI + SQLAlchemy 2.0 async + httpx + Anthropic SDK. Covers error handling, retries, circuit breakers, timeouts, structured logging, and forbidden sync patterns.
---

# Python Async Conventions

DigIdentity backend is async-first end-to-end. Sync calls in a request path are a bug. This skill documents the canonical patterns.

## Stack baseline

- Python 3.13
- FastAPI (latest stable)
- SQLAlchemy 2.0 async + asyncpg
- httpx[http2] for HTTP clients
- Anthropic SDK (async)
- OpenAI SDK (async)
- loguru for logging
- tenacity for retry policies
- pybreaker for circuit breakers
- Pydantic v2 for validation

## Forbidden patterns

These NEVER appear in code that runs in a request path:

```python
# FORBIDDEN: sync HTTP
import requests
requests.get(...)

# FORBIDDEN: sync DB
import psycopg2
conn = psycopg2.connect(...)

# FORBIDDEN: blocking sleep
import time
time.sleep(...)

# FORBIDDEN: synchronous file IO in path
with open(path) as f:
    data = f.read()

# FORBIDDEN: print
print("debug")
```

Replacements:

```python
# httpx async
async with httpx.AsyncClient() as client:
    r = await client.get(...)

# SQLAlchemy async + asyncpg
async with AsyncSession(engine) as session:
    result = await session.execute(stmt)

# asyncio sleep
await asyncio.sleep(1.0)

# async file IO
async with aiofiles.open(path) as f:
    data = await f.read()

# structured logging
from loguru import logger
logger.info("event", tenant_id=tenant_id, request_id=request_id)
```

## HTTP client pattern

Every external HTTP call goes through a shared, configured `httpx.AsyncClient`:

```python
# core/clients/http.py
import httpx
from contextlib import asynccontextmanager

_client: httpx.AsyncClient | None = None

async def get_http_client() -> httpx.AsyncClient:
    global _client
    if _client is None:
        _client = httpx.AsyncClient(
            http2=True,
            timeout=httpx.Timeout(connect=2.0, read=10.0, write=5.0, pool=2.0),
            limits=httpx.Limits(max_connections=200, max_keepalive_connections=50),
        )
    return _client

async def close_http_client():
    global _client
    if _client is not None:
        await _client.aclose()
        _client = None
```

Wire `get_http_client` / `close_http_client` to FastAPI lifespan startup/shutdown.

NEVER instantiate `httpx.AsyncClient()` inside a route handler — it leaks sockets.

## Timeout discipline

Every external call has an explicit timeout. No defaults. No silent infinite waits.

```python
# explicit per-call timeout overrides client default if needed
async with client.stream("POST", url, json=payload, timeout=30.0) as response:
    async for chunk in response.aiter_bytes():
        ...
```

Timeout budgets:

- DB query: 2s default, 10s for complex aggregations (annotated with comment).
- Embedding API: 8s.
- LLM call (non-streaming): 30s.
- LLM streaming first byte: 5s, total stream: 60s.
- Voice (LiveKit): handled by LiveKit Agents internally.
- Internal RPC: 3s.

## Retry pattern

Use `tenacity`. Retry only on transient errors (network, 5xx, rate-limit-with-retry-after). NEVER retry on:

- 4xx user errors
- Authentication failures
- Validation errors
- Anything where the operation may have succeeded but the response was lost without idempotency

```python
from tenacity import (
    retry, stop_after_attempt, wait_exponential_jitter,
    retry_if_exception_type, before_sleep_log
)
from loguru import logger
import httpx

@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential_jitter(initial=0.5, max=4.0),
    retry=retry_if_exception_type((httpx.TransportError, httpx.HTTPStatusError)),
    before_sleep=before_sleep_log(logger, "WARNING"),
    reraise=True,
)
async def call_embedding_api(text: str) -> list[float]:
    ...
```

For state-mutating operations, retries require an idempotency key:

```python
async def post_with_idempotency(client, url, payload, idem_key: str):
    headers = {"Idempotency-Key": idem_key}
    r = await client.post(url, json=payload, headers=headers, timeout=10.0)
    r.raise_for_status()
    return r.json()
```

## Circuit breaker pattern

Per-provider circuit breakers protect us when an upstream is having an outage:

```python
# core/llm/router.py
import pybreaker
from loguru import logger

anthropic_breaker = pybreaker.CircuitBreaker(
    fail_max=3,
    reset_timeout=300,   # 5 minutes
    name="anthropic",
)

openai_breaker = pybreaker.CircuitBreaker(
    fail_max=3,
    reset_timeout=300,
    name="openai",
)

@anthropic_breaker
async def _call_anthropic(messages, **kwargs):
    ...

async def call_with_fallback(messages, **kwargs):
    try:
        return await _call_anthropic(messages, **kwargs)
    except pybreaker.CircuitBreakerError:
        logger.warning("anthropic_breaker_open_falling_back_openai")
        return await _call_openai(messages, **kwargs)
```

## Error handling boundaries

Three boundary types, each with its own error policy:

**Route handler (top of stack).** Catches all unhandled, logs with full context, returns clean error to client:

```python
@app.exception_handler(Exception)
async def unhandled(request: Request, exc: Exception):
    logger.exception("unhandled_error", path=request.url.path, request_id=request.state.request_id)
    return JSONResponse({"error": "internal_error", "request_id": request.state.request_id}, status_code=500)
```

**Service layer.** Catches expected business errors, translates to typed exceptions:

```python
from core.errors import ValidationError, NotFoundError, ExternalServiceError

class PropertyService:
    async def get(self, property_id: UUID, tenant_id: UUID):
        async with with_tenant(tenant_id) as session:
            row = await session.get(Property, property_id)
            if row is None:
                raise NotFoundError(f"property {property_id}")
            return row
```

**Adapter layer (external service clients).** Translates SDK exceptions into our typed exceptions:

```python
try:
    response = await anthropic_client.messages.create(...)
except anthropic.APIStatusError as e:
    if e.status_code >= 500:
        raise ExternalServiceError("anthropic", retriable=True) from e
    raise ExternalServiceError("anthropic", retriable=False) from e
```

## Streaming patterns

For SSE/LLM streaming, the standard wrapper:

```python
from sse_starlette import EventSourceResponse

async def stream_chat(session_id: UUID, tenant_id: UUID):
    async def event_generator():
        async with with_tenant(tenant_id) as db_session:
            async for chunk in agent.run_stream(session_id):
                if chunk.type == "text":
                    yield {"event": "text", "data": chunk.content}
                elif chunk.type == "directive":
                    yield {"event": "directive", "data": chunk.json()}
                elif chunk.type == "done":
                    yield {"event": "done", "data": ""}
                    return

    return EventSourceResponse(event_generator(), ping=15)
```

Three rules for streaming:

1. **Heartbeat every 15s.** SSE clients (especially mobile) timeout otherwise.
2. **Handle client disconnect.** When `event_generator` raises GeneratorExit, persist partial state and stop cleanly.
3. **Bound the stream.** Hard timeout at 60s. If the LLM is still going, send a `{"event": "timeout"}` and close.

## Background tasks

Don't use FastAPI `BackgroundTasks` for anything non-trivial. Use Celery:

```python
# core/jobs/embeddings.py
from celery import shared_task

@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def embed_entity(self, entity_id: str, tenant_id: str):
    try:
        ...
    except ExternalServiceError as e:
        if e.retriable:
            raise self.retry(exc=e)
        raise
```

Jobs that touch the DB pop into their own async context:

```python
from asgiref.sync import async_to_sync

@shared_task
def reembed_pack_entities(pack_name: str, tenant_id: str):
    async_to_sync(_reembed_pack_entities)(pack_name, tenant_id)
```

## Logging discipline

Always structured. Always with `tenant_id` and `request_id` when in request context. Use `loguru.contextualize`:

```python
from loguru import logger

@app.middleware("http")
async def context_middleware(request, call_next):
    request_id = request.headers.get("X-Request-Id") or str(uuid.uuid4())
    request.state.request_id = request_id
    with logger.contextualize(request_id=request_id, path=request.url.path):
        return await call_next(request)
```

Levels:
- `debug`: dev only, removed in prod by config.
- `info`: routine state changes.
- `warning`: retriable failures, fallbacks activated.
- `error`: unhandled or critical business errors.
- `exception`: only inside `except` with exception info.

Never log secrets, never log full visitor PII, never log full conversation transcripts (only IDs).

## Testing async code

```python
import pytest

@pytest.mark.asyncio
async def test_search_returns_relevant():
    async with TestClient(app) as client:
        r = await client.post("/tenants/demo/search", json={"q": "villa vista mare"})
        assert r.status_code == 200
        ...
```

Use `pytest-asyncio` with `asyncio_mode = auto` in `pytest.ini`. Use `testcontainers-postgres` for real DB in integration tests (sqlite fakes don't have pgvector).

## Common mistakes

- Forgetting `await`. Mypy strict catches most. Run `mypy --strict` in CI.
- Sharing `AsyncSession` across requests. Each request opens its own.
- Forgetting to close streams on client disconnect. Use try/finally.
- Logging conversation content. Reference by ID only.
- Not setting timeouts on `await asyncio.wait_for(...)`. Always bound waits.
