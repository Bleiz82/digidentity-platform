"""Test usage_logs DB writes via Celery task.

Uses testcontainers for a real PostgreSQL instance.
CELERY_TASK_ALWAYS_EAGER=True (default) so log_usage runs synchronously.
"""

import os
import re
import uuid
from pathlib import Path

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine


def _apply_migrations(sync_url: str) -> None:
    from alembic.config import Config

    from alembic import command

    alembic_cfg_path = Path(__file__).parent.parent / "alembic.ini"
    cfg = Config(str(alembic_cfg_path))
    cfg.set_main_option("sqlalchemy.url", sync_url)
    command.upgrade(cfg, "head")

    # Create a non-superuser role so RLS is enforced
    sync_engine = create_engine(sync_url, isolation_level="AUTOCOMMIT")
    with sync_engine.connect() as conn:
        # Drop role if it exists (idempotent)
        try:
            conn.execute(text("DROP USER IF EXISTS app_user_usage"))
        except Exception:
            pass
        conn.execute(text("CREATE USER app_user_usage WITH PASSWORD 'app_password_usage'"))
        conn.execute(text("GRANT CONNECT ON DATABASE test TO app_user_usage"))
        conn.execute(text("GRANT USAGE ON SCHEMA public TO app_user_usage"))
        conn.execute(
            text(
                "GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public "
                "TO app_user_usage"
            )
        )
        conn.execute(
            text("GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO app_user_usage")
        )
    sync_engine.dispose()


def _make_app_user_url(raw_url: str) -> str:
    """Replace superuser credentials with app_user_usage in the URL."""
    return re.sub(
        r"(postgresql(?:\+psycopg2)?://)([^:@]+):([^@]+)(@)",
        r"\1app_user_usage:app_password_usage\4",
        raw_url,
    )


def _make_async_url(url: str) -> str:
    return url.replace("postgresql+psycopg2://", "postgresql+asyncpg://").replace(
        "postgresql://", "postgresql+asyncpg://"
    )


@pytest.fixture(scope="module")
def pg_container_usage():
    from testcontainers.postgres import PostgresContainer

    with PostgresContainer("pgvector/pgvector:pg16") as container:
        _apply_migrations(container.get_connection_url())
        yield container


@pytest.fixture(scope="module")
def async_db_url(pg_container_usage):
    raw_url = pg_container_usage.get_connection_url()
    app_url = _make_app_user_url(raw_url)
    return _make_async_url(app_url)


@pytest.fixture(scope="module")
def async_session_factory_usage(async_db_url):
    from sqlalchemy.pool import NullPool

    engine = create_async_engine(async_db_url, echo=False, poolclass=NullPool)
    return async_sessionmaker(engine, expire_on_commit=False)


@pytest.fixture(scope="module")
def tenant_id_usage(pg_container_usage):
    """Insert a tenant and return its UUID."""
    import uuid as _uuid_module

    tid = _uuid_module.uuid4()
    raw_url = pg_container_usage.get_connection_url()
    sync_engine = create_engine(raw_url)
    with sync_engine.begin() as conn:
        # Use superuser to bypass RLS for tenant insertion
        conn.execute(text(f"SET LOCAL app.tenant_id = '{tid}'"))
        conn.execute(
            text("INSERT INTO tenants (id, slug, name) VALUES (:id, :slug, :name)"),
            {"id": str(tid), "slug": f"test-usage-{tid}", "name": "Test Usage Tenant"},
        )
    sync_engine.dispose()
    return tid


# ── Tests ─────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio(loop_scope="module")
async def test_usage_logs_written(async_db_url, async_session_factory_usage, tenant_id_usage):
    """log_usage task writes a row to usage_logs."""
    os.environ["DATABASE_URL_ASYNC"] = async_db_url
    os.environ["CELERY_TASK_ALWAYS_EAGER"] = "true"

    request_id = str(uuid.uuid4())
    conversation_id = str(uuid.uuid4())

    # Import and call the task directly (ALWAYS_EAGER runs sync in-process)
    from digidentity_api.tasks.usage import log_usage

    log_usage(
        tenant_id=str(tenant_id_usage),
        conversation_id=conversation_id,
        request_id=request_id,
        provider="anthropic",
        model="claude-sonnet-4-6",
        prompt_tokens=10,
        completion_tokens=20,
        cached_tokens=0,
        cost_usd=0.0001,
        latency_ms=150,
        fallback_used=False,
    )

    # Verify the row was inserted
    async with async_session_factory_usage() as session:
        async with session.begin():
            await session.execute(text(f"SET LOCAL app.tenant_id = '{tenant_id_usage}'"))
            result = await session.execute(
                text(
                    "SELECT request_id, provider, model, fallback_used "
                    "FROM usage_logs WHERE request_id = :request_id"
                ),
                {"request_id": uuid.UUID(request_id)},
            )
            rows = result.fetchall()

    assert len(rows) == 1, f"Expected 1 row, got {len(rows)}"
    assert str(rows[0].request_id) == request_id
    assert rows[0].provider == "anthropic"
    assert rows[0].model == "claude-sonnet-4-6"
    assert rows[0].fallback_used is False


@pytest.mark.asyncio(loop_scope="module")
async def test_usage_logs_idempotent(async_db_url, async_session_factory_usage, tenant_id_usage):
    """Calling log_usage twice with same request_id inserts only 1 row."""
    os.environ["DATABASE_URL_ASYNC"] = async_db_url

    request_id = str(uuid.uuid4())
    conversation_id = str(uuid.uuid4())

    from digidentity_api.tasks.usage import log_usage

    kwargs = {
        "tenant_id": str(tenant_id_usage),
        "conversation_id": conversation_id,
        "request_id": request_id,
        "provider": "openai",
        "model": "gpt-5",
        "prompt_tokens": 5,
        "completion_tokens": 10,
        "cached_tokens": 0,
        "cost_usd": 0.00005,
        "latency_ms": 200,
        "fallback_used": True,
    }

    # Call twice with same request_id
    log_usage(**kwargs)
    log_usage(**kwargs)

    # Should be exactly 1 row (ON CONFLICT DO NOTHING)
    async with async_session_factory_usage() as session:
        async with session.begin():
            await session.execute(text(f"SET LOCAL app.tenant_id = '{tenant_id_usage}'"))
            result = await session.execute(
                text("SELECT COUNT(*) as cnt FROM usage_logs WHERE request_id = :request_id"),
                {"request_id": uuid.UUID(request_id)},
            )
            count = result.scalar()

    assert count == 1, f"Expected 1 row (idempotent), got {count}"
