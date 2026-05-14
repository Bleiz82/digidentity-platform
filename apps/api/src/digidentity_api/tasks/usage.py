"""Celery task: async usage log writer.

Writes a row to usage_logs with ON CONFLICT (request_id) DO NOTHING
for idempotency (ADR-004 §E).

usage_logs has RLS enabled (001_initial_schema.py), so we must SET LOCAL
app.tenant_id before the INSERT even in the Celery context.
"""

import asyncio
import os
from decimal import Decimal
from uuid import UUID

import structlog

from digidentity_api.tasks import celery_app

log = structlog.get_logger()


@celery_app.task(name="log_usage", max_retries=3, default_retry_delay=5)
def log_usage(
    tenant_id: str,
    conversation_id: str,
    request_id: str,
    provider: str,
    model: str,
    prompt_tokens: int,
    completion_tokens: int,
    cached_tokens: int,
    cost_usd: float,
    latency_ms: int,
    fallback_used: bool,
) -> None:
    """Log LLM usage to DB. Idempotent via ON CONFLICT DO NOTHING."""
    # asyncio.run() is acceptable in production Celery workers (no running loop).
    # In tests (pytest-asyncio), a loop is already active so we must run in a
    # dedicated thread to avoid "cannot call asyncio.run() from a running event loop".
    import concurrent.futures

    coro = _write_log(
        tenant_id=tenant_id,
        conversation_id=conversation_id,
        request_id=request_id,
        provider=provider,
        model=model,
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
        cached_tokens=cached_tokens,
        cost_usd=cost_usd,
        latency_ms=latency_ms,
        fallback_used=fallback_used,
    )

    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = None

    if loop is not None and loop.is_running():
        # Running inside an existing event loop (e.g., pytest-asyncio).
        # Spawn a thread with its own fresh event loop.
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
            future = executor.submit(asyncio.run, coro)
            future.result()
    else:
        asyncio.run(coro)


async def _write_log(
    *,
    tenant_id: str,
    conversation_id: str,
    request_id: str,
    provider: str,
    model: str,
    prompt_tokens: int,
    completion_tokens: int,
    cached_tokens: int,
    cost_usd: float,
    latency_ms: int,
    fallback_used: bool,
) -> None:
    """Execute the INSERT asynchronously using a fresh SQLAlchemy engine."""
    from sqlalchemy import text
    from sqlalchemy.ext.asyncio import create_async_engine

    database_url = os.getenv("DATABASE_URL_ASYNC") or os.getenv("DATABASE_URL_ASYNC_TEST")
    if not database_url:
        log.warning("log_usage.no_database_url_configured")
        return

    engine = create_async_engine(database_url, echo=False)
    try:
        async with engine.begin() as conn:
            # RLS requires app.tenant_id to be set within the transaction
            tid_str = str(UUID(tenant_id))
            await conn.execute(text(f"SET LOCAL app.tenant_id = '{tid_str}'"))

            # Note: asyncpg cannot mix named bind params with PG cast syntax (::uuid).
            # Pass UUID objects directly — SQLAlchemy asyncpg dialect handles the type.
            await conn.execute(
                text("""
                    INSERT INTO usage_logs (
                        id, tenant_id, conversation_id, request_id,
                        provider, model,
                        prompt_tokens, completion_tokens, cached_tokens,
                        cost_usd, latency_ms, fallback_used
                    ) VALUES (
                        gen_random_uuid(),
                        :tenant_id,
                        :conversation_id,
                        :request_id,
                        :provider,
                        :model,
                        :prompt_tokens,
                        :completion_tokens,
                        :cached_tokens,
                        :cost_usd,
                        :latency_ms,
                        :fallback_used
                    )
                    ON CONFLICT (request_id) DO NOTHING
                """),
                {
                    "tenant_id": UUID(tenant_id),
                    "conversation_id": UUID(conversation_id),
                    "request_id": UUID(request_id),
                    "provider": provider,
                    "model": model,
                    "prompt_tokens": prompt_tokens,
                    "completion_tokens": completion_tokens,
                    "cached_tokens": cached_tokens,
                    "cost_usd": Decimal(str(cost_usd)),
                    "latency_ms": latency_ms,
                    "fallback_used": fallback_used,
                },
            )
        log.info(
            "log_usage.written",
            tenant_id=tenant_id,
            request_id=request_id,
            model=model,
        )
    except Exception as exc:
        log.error("log_usage.db_error", error=str(exc), request_id=request_id)
        raise
    finally:
        await engine.dispose()
