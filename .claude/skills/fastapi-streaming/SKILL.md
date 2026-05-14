---
name: fastapi-streaming
description: Patterns for streaming responses from FastAPI — SSE for text agent output, WebSocket for bidirectional flows (voice via LiveKit, viewport_state sync). Covers heartbeat, disconnect handling, backpressure, error propagation in stream.
---

# FastAPI Streaming Patterns

DigIdentity uses streaming heavily: agent responses arrive token-by-token, morph directives interleave with text, viewport state syncs continuously during Inhabit. Streaming done wrong looks broken to users (stalls, hangs, timeouts). Done right it feels alive.

## Three transports

1. **SSE (Server-Sent Events)** — text agent stream, morph directives, lightweight unidirectional server→client.
2. **WebSocket** — bidirectional flows: client emits `viewport_state` while server emits agent commentary. Also the future-proof transport for richer multimodal.
3. **WebRTC via LiveKit Agents** — voice. We do NOT implement WebRTC ourselves; LiveKit Agents handles media, we plug in the agent loop.

This skill covers SSE and WebSocket in FastAPI. LiveKit Agents is a separate concern.

## SSE: canonical implementation

Use `sse-starlette`:

```python
# pyproject dependency: sse-starlette
from sse_starlette import EventSourceResponse
from fastapi import APIRouter, Request
from uuid import UUID

router = APIRouter()

@router.post("/tenants/{slug}/conversations/{conv_id}/stream")
async def stream_conversation(
    slug: str,
    conv_id: UUID,
    request: Request,
):
    tenant_id = request.state.tenant_id

    async def event_generator():
        try:
            async for chunk in agent.run_stream(conv_id, tenant_id):
                if await request.is_disconnected():
                    logger.info("client_disconnected", conv_id=str(conv_id))
                    break

                if chunk.kind == "text":
                    yield {"event": "text", "data": chunk.content}
                elif chunk.kind == "directive":
                    yield {"event": "directive", "data": chunk.json()}
                elif chunk.kind == "tool_call":
                    yield {"event": "tool_call", "data": chunk.json()}
                elif chunk.kind == "done":
                    yield {"event": "done", "data": ""}
                    return
        except asyncio.CancelledError:
            logger.info("stream_cancelled", conv_id=str(conv_id))
            raise
        except Exception as e:
            logger.exception("stream_error", conv_id=str(conv_id))
            yield {"event": "error", "data": "{\"code\":\"internal\"}"}
            return

    return EventSourceResponse(
        event_generator(),
        ping=15,                       # heartbeat every 15s
        send_timeout=10,
    )
```

Critical points:

- **Heartbeat (`ping=15`)** keeps mobile clients alive. Without it, connections die at ~30s on cellular.
- **Disconnect detection** via `request.is_disconnected()`. Check it before yielding each chunk.
- **`CancelledError` re-raise**: don't swallow it. Let it propagate so the framework cleans up.
- **Final `done` event**: clients should explicitly close on this. Don't rely on connection close alone.
- **Error events**: structured JSON. Clients differentiate based on event type.

## SSE client expectations

Document for frontend implementers:

```typescript
const evt = new EventSource(`/tenants/${slug}/conversations/${convId}/stream`);

evt.addEventListener("text", (e) => appendText(e.data));
evt.addEventListener("directive", (e) => applyDirective(JSON.parse(e.data)));
evt.addEventListener("tool_call", (e) => showToolBadge(JSON.parse(e.data)));
evt.addEventListener("done", () => evt.close());
evt.addEventListener("error", (e) => handleErr(e));

// Browser auto-reconnects on transport failure; pair with idempotency key on the POST.
```

## Backpressure

If the client is slow consuming directives, the generator buffers. Use a bounded queue with drop policy for non-essential events:

```python
async def event_generator():
    queue: asyncio.Queue = asyncio.Queue(maxsize=64)
    producer_task = asyncio.create_task(produce_to_queue(queue))

    try:
        while True:
            try:
                chunk = await asyncio.wait_for(queue.get(), timeout=30.0)
            except asyncio.TimeoutError:
                yield {"event": "timeout", "data": ""}
                break
            if chunk is _SENTINEL_DONE:
                yield {"event": "done", "data": ""}
                break
            yield chunk_to_event(chunk)
    finally:
        producer_task.cancel()
```

For DigIdentity specifically:

- **Text chunks**: never drop. Text is canonical.
- **Directives**: never drop. They drive UI state. If queue full, log warning and slow the producer.
- **`viewport_state` echo from server**: droppable.
- **Telemetry events**: droppable.

## Initiating a conversation: POST + idempotency

The `/conversations/{conv_id}/stream` is a GET-like in concept but POST in practice (it accepts the user message in body). For retry safety:

```python
@router.post("/tenants/{slug}/conversations")
async def create_conversation_turn(
    slug: str,
    body: CreateTurnRequest,
    request: Request,
):
    tenant_id = request.state.tenant_id
    idem_key = body.idempotency_key or request.headers.get("Idempotency-Key")
    if not idem_key:
        raise HTTPException(400, "idempotency_key required")

    async with with_tenant(tenant_id) as session:
        # Atomic: lookup-or-create conversation + insert user turn
        conv, turn = await conversation_service.upsert_turn(
            session, body.conversation_id, body.user_message, idem_key
        )
        # session commits on context exit

    # Now stream the agent response
    return await stream_conversation_helper(conv.id, tenant_id, request)
```

`upsert_turn` is implemented with `INSERT ... ON CONFLICT DO NOTHING RETURNING` on the idempotency key, ensuring exactly-once turn creation even with client retries.

## WebSocket: bidirectional pattern (Inhabit + viewport state)

```python
from fastapi import WebSocket, WebSocketDisconnect

@router.websocket("/tenants/{slug}/inhabit/{property_id}/ws")
async def inhabit_ws(websocket: WebSocket, slug: str, property_id: UUID):
    await websocket.accept()
    tenant_id = await resolve_tenant_id(slug)
    if tenant_id is None:
        await websocket.close(code=4004, reason="tenant_not_found")
        return

    receiver_task = asyncio.create_task(receive_loop(websocket, property_id, tenant_id))
    sender_task = asyncio.create_task(send_loop(websocket, property_id, tenant_id))

    try:
        # Wait for either side to terminate
        done, pending = await asyncio.wait(
            [receiver_task, sender_task],
            return_when=asyncio.FIRST_COMPLETED,
        )
        for task in pending:
            task.cancel()
    except WebSocketDisconnect:
        pass
    finally:
        receiver_task.cancel()
        sender_task.cancel()
        with contextlib.suppress(Exception):
            await websocket.close()


async def receive_loop(ws: WebSocket, property_id, tenant_id):
    """Receive viewport_state from client and feed it to agent context."""
    while True:
        msg = await ws.receive_json()
        if msg["type"] == "viewport_state":
            await viewport_state_bus.publish(property_id, msg["payload"])
        elif msg["type"] == "chat":
            await chat_bus.publish(property_id, msg["payload"])


async def send_loop(ws: WebSocket, property_id, tenant_id):
    """Send agent commentary + directives to client."""
    async for chunk in agent.run_inhabit_stream(property_id, tenant_id):
        await ws.send_json(chunk.to_dict())
```

WebSocket close codes:

- 1000: normal close.
- 1011: server error.
- 4004: not found (tenant or resource).
- 4001: unauthorized.
- 4029: rate limited.

## Error propagation in streams

Once headers are sent, you cannot return a 500 status. The stream MUST emit an `error` event and close cleanly:

```python
yield {"event": "error", "data": json.dumps({"code": "external_service_unavailable", "retry": True})}
```

Clients differentiate based on `code`. Common codes:

- `internal`: generic 500.
- `external_service_unavailable`: upstream LLM/embedding down. Retry with backoff.
- `rate_limited`: client should slow down.
- `validation`: bad input, don't retry.
- `forbidden`: auth or permission issue.

## Timeouts and stream lifecycle

Three timeouts to enforce per stream:

1. **TTFC (time to first chunk)**: 5 seconds. If LLM hasn't produced anything after 5s, yield `slow` event so client can show a "thinking" indicator.
2. **Idle**: 30 seconds without any chunk. Close with `timeout` event.
3. **Total**: 60 seconds. Hard ceiling.

Implementation:

```python
async def event_generator():
    start = time.monotonic()
    last_chunk = start
    first_chunk_seen = False

    async for chunk in agent.run_stream(...):
        now = time.monotonic()
        if not first_chunk_seen:
            ttfc = now - start
            metrics.record_ttfc(ttfc)
            first_chunk_seen = True
        if now - start > 60.0:
            yield {"event": "timeout", "data": ""}
            break
        last_chunk = now
        yield chunk_to_event(chunk)
```

## Testing streams

Use `httpx.AsyncClient` for SSE:

```python
@pytest.mark.asyncio
async def test_stream_yields_text_then_done():
    async with httpx.AsyncClient(base_url=...) as client:
        async with client.stream("POST", "/tenants/demo/conversations/x/stream", json={...}) as r:
            assert r.status_code == 200
            events = []
            async for line in r.aiter_lines():
                if line.startswith("event:"):
                    events.append(line)
            assert any("event: text" in e for e in events)
            assert events[-1].startswith("event: done")
```

For WebSocket, use FastAPI's `TestClient` (sync) or `websockets` lib for full async:

```python
def test_inhabit_ws_echo():
    client = TestClient(app)
    with client.websocket_connect("/tenants/demo/inhabit/abc/ws") as ws:
        ws.send_json({"type": "viewport_state", "payload": {"room": "salone"}})
        msg = ws.receive_json()
        assert msg["type"] in ("agent_commentary", "directive", "ack")
```

## CORS for streams

SSE requires special CORS handling on the response side. The middleware should preserve streaming behavior:

```python
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Content-Type", "Idempotency-Key", "Authorization"],
    expose_headers=["X-Request-Id"],
)
```

## Anti-patterns

- **Returning `StreamingResponse` with `JSONResponse` headers**: causes Chrome to buffer until close. Use `EventSourceResponse` for SSE.
- **No heartbeat**: connection dies on mobile/firewall. Always `ping=15` or shorter.
- **Yielding stringified JSON without `event:` prefix**: clients can't dispatch by type.
- **Catching `CancelledError` silently**: leaks tasks. Re-raise after cleanup.
- **Long-running sync work inside the generator**: blocks the event loop, blocks other streams. Offload via `asyncio.to_thread` or Celery.
- **Streaming with `expire_on_commit=True`**: SQLAlchemy expires objects between yields, attribute access lazy-loads → crashes. Use `expire_on_commit=False` for streaming sessions.
