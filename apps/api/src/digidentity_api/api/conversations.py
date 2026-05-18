"""SSE endpoint for conversational streaming — ADR-002.

GET /conversations/{conversation_id}/stream
  - Tenant resolved from X-Tenant-Id header (priority) or ?tenant_id query param
    (fallback required for EventSource browser API, which cannot set custom headers)
  - Streams LLM chunks as SSE events
  - Pings every 15s to keep connection alive
  - Negotiates Accept header: 406 if client only accepts application/json
  - If ANTHROPIC_API_KEY is set → routes through AgentLoop (real tool-calling loop)
  - Otherwise → falls back to LLMRouter mock (back-compat)
"""

import asyncio
import json
from uuid import UUID

import structlog
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import Response, StreamingResponse

from digidentity_api.config import settings
from digidentity_api.engines.errors import CircuitOpenError
from digidentity_api.engines.llm_router import LLMRouter

log = structlog.get_logger()

router = APIRouter()

# Shared router instance (singleton for Phase 1 back-compat)
_llm_router = LLMRouter()


# ── Tenant dependency ─────────────────────────────────────────────────────────


async def get_tenant_id(
    request: Request,
    tenant_id_query: UUID | None = Query(None, alias="tenant_id"),
) -> UUID:
    """Resolve tenant from X-Tenant-Id header (priority) or ?tenant_id query param.

    Header takes priority when both are present. Invalid header UUID → 400 (backward
    compat). Invalid query UUID → 422 (FastAPI auto-validation). Missing both → 401.
    """
    tid_header = request.headers.get("X-Tenant-Id")
    if tid_header is not None:
        try:
            return UUID(tid_header)
        except ValueError:
            raise HTTPException(status_code=400, detail="X-Tenant-Id must be a valid UUID")
    if tenant_id_query is not None:
        return tenant_id_query
    raise HTTPException(
        status_code=401,
        detail="tenant_id required via X-Tenant-Id header or ?tenant_id query parameter",
    )


# ── SSE helpers ───────────────────────────────────────────────────────────────


def _sse(payload: dict) -> str:
    return f"data: {json.dumps(payload)}\n\n"


# ── SSE endpoint ──────────────────────────────────────────────────────────────


@router.get("/conversations/{conversation_id}/stream")
async def stream_conversation(
    conversation_id: UUID,
    request: Request,
    tenant_id: UUID = Depends(get_tenant_id),
) -> Response:
    # Accept negotiation (ADR-002)
    accept = request.headers.get("Accept", "")
    if "application/json" in accept and "text/event-stream" not in accept:
        return Response(
            status_code=406,
            headers={"X-Suggested-Fallback": "long-polling"},
        )

    prompt = request.query_params.get("prompt", "ciao")
    fail_mode = request.headers.get("X-Mock-Fail-Mode")

    if settings.ANTHROPIC_API_KEY:
        generator = _agent_event_generator(conversation_id, prompt, tenant_id)
    else:
        generator = _mock_event_generator(prompt, conversation_id, tenant_id, fail_mode)

    return StreamingResponse(
        generator,
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        },
    )


# ── Agent loop generator (real Anthropic) ─────────────────────────────────────


async def _agent_event_generator(
    conversation_id: UUID,
    user_message: str,
    tenant_id: UUID,
) -> object:
    from digidentity_api.engines.agent.loop import AgentLoop  # noqa: PLC0415

    queue: asyncio.Queue[str | None] = asyncio.Queue()

    async def pinger() -> None:
        while True:
            await asyncio.sleep(15)
            await queue.put(_sse({"type": "ping"}))

    async def streamer() -> None:
        try:
            loop = AgentLoop()
            async for event in loop.run(
                conversation_id=conversation_id,
                user_message=user_message,
                tenant_id=tenant_id,
            ):
                await queue.put(_sse(event))
        except Exception as exc:
            log.error("agent_stream.error", error=str(exc))
            await queue.put(_sse({"type": "error", "code": "internal_error"}))
        finally:
            await queue.put(None)

    ping_task = asyncio.create_task(pinger())
    stream_task = asyncio.create_task(streamer())
    try:
        while True:
            item = await queue.get()
            if item is None:
                break
            yield item
    finally:
        ping_task.cancel()
        stream_task.cancel()
        await asyncio.gather(ping_task, stream_task, return_exceptions=True)


# ── Mock/LLMRouter generator (back-compat, no API key) ───────────────────────


async def _mock_event_generator(
    prompt: str,
    conversation_id: UUID,
    tenant_id: UUID,
    fail_mode: str | None,
) -> object:
    queue: asyncio.Queue[str | None] = asyncio.Queue()

    async def pinger() -> None:
        while True:
            await asyncio.sleep(15)
            await queue.put(_sse({"type": "ping"}))

    async def streamer() -> None:
        try:
            async for event in _llm_router.route(
                prompt=prompt,
                conversation_id=str(conversation_id),
                tenant_id=str(tenant_id),
                fail_mode=fail_mode,
            ):
                await queue.put(_sse(event))
        except CircuitOpenError as exc:
            await queue.put(_sse({"type": "error", "code": "circuit_open", "model": exc.model}))
        except Exception as exc:
            log.error("stream_conversation.error", error=str(exc))
            await queue.put(_sse({"type": "error", "code": "internal_error"}))
        finally:
            await queue.put(None)

    ping_task = asyncio.create_task(pinger())
    stream_task = asyncio.create_task(streamer())
    try:
        while True:
            item = await queue.get()
            if item is None:
                break
            yield item
    finally:
        ping_task.cancel()
        stream_task.cancel()
        await asyncio.gather(ping_task, stream_task, return_exceptions=True)
