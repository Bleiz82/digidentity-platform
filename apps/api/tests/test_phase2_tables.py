"""
Test STEP 8a: schema DB v3 — conversations, conversation_turns, visitor_sessions, leads.

Verifica:
  1. idempotency_key unique per (tenant_id, key) — duplicato stesso tenant fallisce,
     stesso key su tenant diverso passa.
  2. (conversation_id, turn_index) unique — duplicato fallisce.
  3. RLS isolation visitor_sessions — tenant B non vede sessioni di tenant A.
  4. Un solo lead per visitor_session — duplicato visitor_session_id fallisce.
  5. Bucket enum constraint — valore non valido fallisce.
  6. FORCE RLS attivo su tutte e 4 le tabelle — SELECT senza app.tenant_id → 0 righe.

Usa testcontainers PostgreSQL 16+pgvector, app_user non-superuser (FORCE RLS effettivo).
Pattern identico a test_tenant_isolation.py.
"""

import re
from pathlib import Path
from uuid import UUID

import pytest
import sqlalchemy as sa
import uuid_utils
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from testcontainers.postgres import PostgresContainer

from digidentity_api.db.models import Conversation, ConversationTurn, Lead, VisitorSession
from digidentity_api.db.models import Tenant
from digidentity_api.db.tenant_context import with_tenant

# ── helpers ───────────────────────────────────────────────────────────────────


def _uuid7() -> UUID:
    return UUID(str(uuid_utils.uuid7()))


def _apply_migrations(sync_url: str) -> None:
    from alembic import command
    from alembic.config import Config
    from sqlalchemy import create_engine
    from sqlalchemy import text as sa_text

    alembic_cfg_path = Path(__file__).parent.parent / "alembic.ini"
    cfg = Config(str(alembic_cfg_path))
    cfg.set_main_option("sqlalchemy.url", sync_url)
    command.upgrade(cfg, "head")

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


# ── fixtures ──────────────────────────────────────────────────────────────────


@pytest.fixture(scope="session")
def pg_container():
    with PostgresContainer("pgvector/pgvector:pg16") as container:
        _apply_migrations(container.get_connection_url())
        yield container


@pytest.fixture(scope="session")
def async_session_factory(pg_container):
    from sqlalchemy.pool import NullPool

    raw_url = pg_container.get_connection_url()
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
def tenant_ids(pg_container, async_session_factory) -> list[UUID]:
    """Due tenant UUID v7 — inseriti in DB come prerequisito."""
    import asyncio

    tids = [_uuid7(), _uuid7()]

    async def _seed() -> None:
        for i, tid in enumerate(tids):
            async with with_tenant(tid, session_factory=async_session_factory) as s:
                s.add(Tenant(id=tid, slug=f"p2-tenant-{i}", name=f"Phase2 Tenant {i}"))

    asyncio.run(_seed())
    return tids


# ── test 1: idempotency_key unique per tenant ─────────────────────────────────


@pytest.mark.asyncio(loop_scope="session")
async def test_conversations_idempotency_key_unique_per_tenant(
    async_session_factory, tenant_ids
):
    tenant_a, tenant_b = tenant_ids

    # primo insert — deve riuscire
    async with with_tenant(tenant_a, session_factory=async_session_factory) as s:
        s.add(Conversation(tenant_id=tenant_a, idempotency_key="idem-key-001"))

    # duplicato stesso tenant — deve fallire
    with pytest.raises(Exception):
        async with with_tenant(tenant_a, session_factory=async_session_factory) as s:
            s.add(Conversation(tenant_id=tenant_a, idempotency_key="idem-key-001"))
            await s.flush()

    # stesso key su tenant diverso — deve riuscire
    async with with_tenant(tenant_b, session_factory=async_session_factory) as s:
        s.add(Conversation(tenant_id=tenant_b, idempotency_key="idem-key-001"))


# ── test 2: (conversation_id, turn_index) unique ─────────────────────────────


@pytest.mark.asyncio(loop_scope="session")
async def test_conversation_turns_sequence_unique(async_session_factory, tenant_ids):
    tenant_a = tenant_ids[0]

    # crea conversation di supporto
    conv_id = _uuid7()
    async with with_tenant(tenant_a, session_factory=async_session_factory) as s:
        s.add(Conversation(id=conv_id, tenant_id=tenant_a))

    # primo turno (turn_index=0) — deve riuscire
    async with with_tenant(tenant_a, session_factory=async_session_factory) as s:
        s.add(
            ConversationTurn(
                tenant_id=tenant_a,
                conversation_id=conv_id,
                turn_index=0,
                role="user",
                content="Ciao",
            )
        )

    # secondo turno stesso turn_index — deve fallire
    with pytest.raises(Exception):
        async with with_tenant(tenant_a, session_factory=async_session_factory) as s:
            s.add(
                ConversationTurn(
                    tenant_id=tenant_a,
                    conversation_id=conv_id,
                    turn_index=0,
                    role="assistant",
                    content="Duplicato",
                )
            )
            await s.flush()


# ── test 3: RLS isolation visitor_sessions ────────────────────────────────────


@pytest.mark.asyncio(loop_scope="session")
async def test_visitor_sessions_rls_isolation(async_session_factory, tenant_ids):
    tenant_a, tenant_b = tenant_ids

    # inserisci visitor_session per tenant_a
    vs_id = _uuid7()
    async with with_tenant(tenant_a, session_factory=async_session_factory) as s:
        s.add(
            VisitorSession(
                id=vs_id,
                tenant_id=tenant_a,
                visitor_hash="rls-isolation-test-hash",
                inferred_personas=[],
                signals={},
                confidence=0.5,
            )
        )

    # tenant_b non deve vedere le sessioni di tenant_a
    async with with_tenant(tenant_b, session_factory=async_session_factory) as s:
        result = await s.execute(
            sa.select(VisitorSession).where(VisitorSession.id == vs_id)
        )
        row = result.scalar_one_or_none()
        assert row is None, f"RLS LEAK: tenant_b vede visitor_session di tenant_a (id={vs_id})"

    # tenant_a deve vedere la propria sessione
    async with with_tenant(tenant_a, session_factory=async_session_factory) as s:
        result = await s.execute(
            sa.select(VisitorSession).where(VisitorSession.id == vs_id)
        )
        row = result.scalar_one_or_none()
        assert row is not None, "tenant_a non vede la propria visitor_session"
        assert row.tenant_id == tenant_a


# ── test 4: un solo lead per visitor_session ──────────────────────────────────


@pytest.mark.asyncio(loop_scope="session")
async def test_leads_one_per_visitor_session(async_session_factory, tenant_ids):
    tenant_a = tenant_ids[0]

    # crea visitor_session di supporto
    vs_id = _uuid7()
    async with with_tenant(tenant_a, session_factory=async_session_factory) as s:
        s.add(
            VisitorSession(
                id=vs_id,
                tenant_id=tenant_a,
                visitor_hash="lead-uniqueness-test",
                inferred_personas=[],
                signals={},
                confidence=0.0,
            )
        )

    # primo lead — deve riuscire
    async with with_tenant(tenant_a, session_factory=async_session_factory) as s:
        s.add(Lead(tenant_id=tenant_a, visitor_session_id=vs_id, score=10.0, bucket="cold"))

    # secondo lead stessa visitor_session — deve fallire (UNIQUE constraint)
    with pytest.raises(Exception):
        async with with_tenant(tenant_a, session_factory=async_session_factory) as s:
            s.add(
                Lead(tenant_id=tenant_a, visitor_session_id=vs_id, score=50.0, bucket="warm")
            )
            await s.flush()


# ── test 5: bucket enum constraint ───────────────────────────────────────────


@pytest.mark.asyncio(loop_scope="session")
async def test_leads_bucket_enum_constraint(async_session_factory, tenant_ids):
    tenant_a = tenant_ids[0]

    # crea visitor_session dedicata (bucket non ancora usata)
    vs_id = _uuid7()
    async with with_tenant(tenant_a, session_factory=async_session_factory) as s:
        s.add(
            VisitorSession(
                id=vs_id,
                tenant_id=tenant_a,
                visitor_hash="bucket-enum-test",
                inferred_personas=[],
                signals={},
                confidence=0.0,
            )
        )

    # valore bucket non valido deve fallire a livello DB
    with pytest.raises(Exception):
        async with with_tenant(tenant_a, session_factory=async_session_factory) as s:
            await s.execute(
                sa.text(
                    "INSERT INTO leads (id, tenant_id, visitor_session_id, score, bucket, signals)"
                    " VALUES (:id, :tid, :vsid, 0.0, 'vip', '[]'::jsonb)"
                ),
                {"id": str(_uuid7()), "tid": str(tenant_a), "vsid": str(vs_id)},
            )


# ── test 6: FORCE RLS attivo su tutte e 4 le tabelle ─────────────────────────


@pytest.mark.asyncio(loop_scope="session")
async def test_rls_force_active_on_all_4_tables(async_session_factory, tenant_ids):
    """
    Inserisce 1 riga per tabella con tenant context, poi verifica che SELECT
    senza app.tenant_id (usando app_user non-superuser) restituisca 0 righe.
    FORCE ROW LEVEL SECURITY blocca anche i proprietari del ruolo se il
    current_setting('app.tenant_id', true) è NULL.
    """
    tenant_a = tenant_ids[0]

    # setup: crea dati in tutte e 4 le tabelle
    vs_id = _uuid7()
    conv_id = _uuid7()

    async with with_tenant(tenant_a, session_factory=async_session_factory) as s:
        s.add(
            VisitorSession(
                id=vs_id,
                tenant_id=tenant_a,
                visitor_hash="rls-force-test",
                inferred_personas=[],
                signals={},
                confidence=0.0,
            )
        )

    async with with_tenant(tenant_a, session_factory=async_session_factory) as s:
        s.add(Conversation(id=conv_id, tenant_id=tenant_a))

    async with with_tenant(tenant_a, session_factory=async_session_factory) as s:
        s.add(
            ConversationTurn(
                tenant_id=tenant_a,
                conversation_id=conv_id,
                turn_index=99,
                role="system",
                content="rls force test turn",
            )
        )

    async with with_tenant(tenant_a, session_factory=async_session_factory) as s:
        s.add(Lead(tenant_id=tenant_a, visitor_session_id=vs_id, score=0.0, bucket="cold"))

    # verifica: SELECT senza tenant context → 0 righe per tutte le tabelle
    # app_user è non-superuser: FORCE RLS è effettivo
    tables = ("visitor_sessions", "conversations", "conversation_turns", "leads")
    async with async_session_factory() as s:
        async with s.begin():
            for table in tables:
                count = (
                    await s.execute(sa.text(f"SELECT COUNT(*) FROM {table}"))
                ).scalar()
                assert count == 0, (
                    f"FORCE RLS non blocca '{table}': {count} righe visibili senza tenant context"
                )
