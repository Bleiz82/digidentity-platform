"""
Test ADR-003: tenant isolation discipline.
Usa testcontainers per un PostgreSQL 16+pgvector fresh.
Applica la migration 001 via alembic (programmatico).
Verifica:
  1. 50 request concorrenti × 5 tenant → zero cross-tenant leak
  2. Query senza with_tenant → TenantContextError da TenantAwareRepository
  3. Nesting with_tenant → TenantContextError
"""

import asyncio
import uuid as _uuid
from pathlib import Path
from uuid import UUID

import pytest
import uuid_utils
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from testcontainers.postgres import PostgresContainer

from digidentity_api.db.errors import TenantContextError
from digidentity_api.db.models import Session as DBSession
from digidentity_api.db.models import Tenant
from digidentity_api.db.repositories import TenantAwareRepository
from digidentity_api.db.tenant_context import with_tenant

# ── helpers ──────────────────────────────────────────────────────────────────


def _apply_migrations(sync_url: str) -> None:
    """Applica migration Alembic usando connessione sincrona, poi crea ruolo app."""

    from alembic.config import Config

    from alembic import command

    # 1. Applica migration come superuser
    alembic_cfg_path = Path(__file__).parent.parent / "alembic.ini"
    cfg = Config(str(alembic_cfg_path))
    cfg.set_main_option("sqlalchemy.url", sync_url)
    command.upgrade(cfg, "head")

    # 2. Crea ruolo app_user non-superuser e concedi permessi
    #    I superuser aggirano sempre RLS (FORCE non basta):
    #    i test devono usare un ruolo normale per rispettare le policy.
    from sqlalchemy import create_engine
    from sqlalchemy import text as sa_text

    sync_engine = create_engine(sync_url, isolation_level="AUTOCOMMIT")
    with sync_engine.connect() as conn:
        conn.execute(sa_text("CREATE USER app_user WITH PASSWORD 'app_password'"))
        conn.execute(sa_text("GRANT CONNECT ON DATABASE test TO app_user"))
        conn.execute(sa_text("GRANT USAGE ON SCHEMA public TO app_user"))
        conn.execute(
            sa_text(
                "GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO app_user"
            )
        )
        conn.execute(sa_text("GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO app_user"))
    sync_engine.dispose()


# ── fixtures ─────────────────────────────────────────────────────────────────


@pytest.fixture(scope="session")
def pg_container():
    """Spinna un container PostgreSQL 16+pgvector per tutta la session di test."""
    with PostgresContainer("pgvector/pgvector:pg16") as container:
        _apply_migrations(container.get_connection_url())
        yield container


@pytest.fixture(scope="session")
def async_session_factory(pg_container):
    """Session factory asincrona puntata al container.

    Usa app_user (non-superuser) in modo che FORCE ROW LEVEL SECURITY funzioni.
    I superuser PostgreSQL aggirano sempre RLS indipendentemente da FORCE.
    """
    from sqlalchemy.pool import NullPool

    raw_url = pg_container.get_connection_url()
    # Sostituisce le credenziali superuser con app_user nella URL
    # URL formato: postgresql+psycopg2://user:password@host:port/db
    import re

    app_url = re.sub(
        r"(postgresql(?:\+psycopg2)?://)([^:@]+):([^@]+)(@)",
        r"\1app_user:app_password\4",
        raw_url,
    )
    async_url = app_url.replace("postgresql+psycopg2://", "postgresql+asyncpg://").replace(
        "postgresql://", "postgresql+asyncpg://"
    )
    engine = create_async_engine(async_url, echo=False, poolclass=NullPool)
    return async_sessionmaker(engine, expire_on_commit=False)


@pytest.fixture(scope="session")
def tenant_ids() -> list[UUID]:
    """5 tenant UUID v7 fissi per la session (come uuid.UUID standard)."""
    return [UUID(str(uuid_utils.uuid7())) for _ in range(5)]


# ── test 1: 50 concurrent requests, zero leak ────────────────────────────────


@pytest.mark.asyncio(loop_scope="session")
async def test_tenant_isolation_concurrent(async_session_factory, tenant_ids, pg_container):
    """
    Setup: 5 tenant × 10 sessioni ciascuno con marker univoco t{i}_s{j}.
    Esecuzione: 50 task concorrenti via asyncio.gather.
    Asserzione: ogni task vede SOLO le proprie 10 sessioni con marker corretto.
    Zero leak tollerati.
    """
    # ── setup: inserisci tenant ───────────────────────────────────────────────
    for i, tid in enumerate(tenant_ids):
        async with with_tenant(tid, session_factory=async_session_factory) as session:
            tenant = Tenant(id=tid, slug=f"tenant-{i}", name=f"Tenant {i}")
            session.add(tenant)

    # ── setup: inserisci 10 sessioni per tenant con visitor_id come marker ────
    ns = _uuid.UUID("12345678-1234-5678-1234-567812345678")

    session_markers: dict[UUID, list[UUID]] = {}
    for i, tid in enumerate(tenant_ids):
        markers = []
        async with with_tenant(tid, session_factory=async_session_factory) as sess:
            for j in range(10):
                marker = _uuid.uuid5(ns, f"t{i}_s{j}")
                db_session = DBSession(tenant_id=tid, visitor_id=marker, channel="web")
                sess.add(db_session)
                markers.append(marker)
        session_markers[tid] = markers

    # ── concurrent reads ─────────────────────────────────────────────────────
    async def fetch_for_tenant(tenant_id: UUID, expected_markers: list[UUID]) -> None:
        async with with_tenant(tenant_id, session_factory=async_session_factory) as sess:
            result = await sess.execute(select(DBSession))
            rows = result.scalars().all()
            assert len(rows) == 10, f"LEAK: tenant {tenant_id} got {len(rows)} rows instead of 10"
            got_markers = {r.visitor_id for r in rows}
            for row in rows:
                assert row.tenant_id == tenant_id, (
                    f"LEAK: tenant {tenant_id} got row with tenant_id={row.tenant_id}"
                )
            assert got_markers == set(expected_markers), (
                f"LEAK: unexpected markers for tenant {tenant_id}"
            )

    tasks = [fetch_for_tenant(tid, session_markers[tid]) for tid in tenant_ids for _ in range(10)]
    await asyncio.gather(*tasks)


# ── test 2: query senza with_tenant → TenantContextError ─────────────────────


@pytest.mark.asyncio(loop_scope="session")
async def test_query_without_tenant_context_raises(async_session_factory):
    """TenantAwareRepository._assert_tenant_context() deve alzare senza contesto attivo."""
    async with async_session_factory() as session:
        repo = TenantAwareRepository(session)
        with pytest.raises(TenantContextError, match="no active tenant context"):
            repo._assert_tenant_context()


# ── test 3: nesting → TenantContextError ─────────────────────────────────────


@pytest.mark.asyncio(loop_scope="session")
async def test_nested_tenant_context_raises(async_session_factory, tenant_ids):
    """Annidare with_tenant deve alzare TenantContextError immediato."""
    tenant_a, tenant_b = tenant_ids[0], tenant_ids[1]
    with pytest.raises(TenantContextError, match="nested"):
        async with with_tenant(tenant_a, session_factory=async_session_factory):
            async with with_tenant(tenant_b, session_factory=async_session_factory):
                pass  # non deve mai arrivare qui
