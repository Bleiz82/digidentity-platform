"""SSE endpoint for conversational streaming — ADR-002.

GET /conversations/{conversation_id}/stream
  - Requires X-Tenant-Id header (UUID)
  - Streams LLM chunks as SSE events
  - Pings every 15s to keep connection alive
  - Negotiates Accept header: 406 if client only accepts application/json
"""

import asyncio
import json
from uuid import UUID

import structlog
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import Response, StreamingResponse

from digidentity_api.engines.errors import CircuitOpenError
from digidentity_api.engines.llm_router import LLMRouter

log = structlog.get_logger()

router = APIRouter()

# Shared router instance (singleton for Phase 1)
_llm_router = LLMRouter()


# ── Tenant dependency ─────────────────────────────────────────────────────────


async def get_tenant_id(request: Request) -> UUID:
    tid = request.headers.get("X-Tenant-Id")
    if not tid:
        raise HTTPException(status_code=401, detail="X-Tenant-Id header required")
    try:
        return UUID(tid)
    except ValueError:
        raise HTTPException(status_code=400, detail="X-Tenant-Id must be a valid UUID")


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

    async def event_generator() -> object:
        queue: asyncio.Queue[str | None] = asyncio.Queue()

        async def pinger() -> None:
            while True:
                await asyncio.sleep(15)
                await queue.put('data: {"type":"ping"}\n\n')

        async def streamer() -> None:
            try:
                async for event in _llm_router.route(
                    prompt=prompt,
                    conversation_id=str(conversation_id),
                    tenant_id=str(tenant_id),
                    fail_mode=fail_mode,
                ):
                    await queue.put(f"data: {json.dumps(event)}\n\n")
            except CircuitOpenError as exc:
                error_event = {"type": "error", "code": "circuit_open", "model": exc.model}
                await queue.put(f"data: {json.dumps(error_event)}\n\n")
            except Exception as exc:
                log.error("stream_conversation.error", error=str(exc))
                error_event = {"type": "error", "code": "internal_error"}
                await queue.put(f"data: {json.dumps(error_event)}\n\n")
            finally:
                await queue.put(None)  # sentinel

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
            # Wait for tasks to finish cancellation cleanly
            await asyncio.gather(ping_task, stream_task, return_exceptions=True)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        },
    )
