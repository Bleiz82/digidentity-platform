"""P3-06: visitor_sessions persistence + Remember state. BIBLE §7.1.

Tests:
  1.  hash_visitor deterministico (pure function, no DB)
  2.  hash_visitor tenant isolation (stesso visitor_id → hash diverso per tenant diverso)
  3.  upsert insert → is_new=True, riga creata nel DB
  4.  upsert update → is_new=False, JSONB aggiornato
  5.  get_latest_session dopo upsert → restituisce la sessione
  6.  get_latest_session visitor inesistente → None
  7.  tenant isolation: stesso visitor_id, tenant diverso → 2 righe separate
  8.  API POST /visitor-sessions/upsert → 200 (mock with_tenant)
  9.  API POST /visitor-sessions/upsert → 422 payload non valido
  10. API GET /visitor-sessions/{visitor_id} → 404 senza DB (o 503)
  11. integrazione: upsert poi GET → coerenza dati
  12. concurrency: 2 upsert paralleli stesso visitor → 1 sola riga finale
"""

from __future__ import annotations

import asyncio
import re
from contextlib import asynccontextmanager
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import UUID

import pytest
import sqlalchemy as sa
import uuid_utils
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from testcontainers.postgres import PostgresContainer

from digidentity_api.db.models import Tenant, VisitorSession
from digidentity_api.db.tenant_context import with_tenant
from digidentity_api.engines.sense.persistence import (
    get_latest_session,
    hash_visitor,
    upsert_visitor_session,
)
from digidentity_api.schemas.visitor import PersonaScore, SenseSignals

TENANT_A = UUID("00000000-0000-0000-0001-000000000001")
TENANT_B = UUID("00000000-0000-0000-0001-000000000002")
VISITOR_UUID = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"

_SAMPLE_SIGNALS = SenseSignals(
    referrer="google.com",
    utm={"utm_source": "google"},
    geo_city="Milano",
    device_class="desktop",
    language="it",
    is_returning=False,
)
_SAMPLE_PERSONAS = [
    PersonaScore(persona_id="international_investor", score=0.75),
    PersonaScore(persona_id="browsing", score=0.25),
]


def _uuid7() -> UUID:
    return UUID(str(uuid_utils.uuid7()))


def _apply_migrations(sync_url: str) -> None:
    from alembic.config import Config
    from sqlalchemy import create_engine
    from sqlalchemy import text as sa_text

    from alembic import command

    alembic_cfg_path = Path(__file__).parent.parent / "alembic.ini"
    cfg = Config(str(alembic_cfg_path))
    cfg.set_main_option("sqlalchemy.url", sync_url)
    command.upgrade(cfg, "head")

    sync_engine = create_engine(sync_url, isolation_level="AUTOCOMMIT")
    with sync_engine.connect() as conn:
        conn.execute(sa_text("CREATE USER app_user_vs WITH PASSWORD 'app_password_vs'"))
        conn.execute(sa_text("GRANT CONNECT ON DATABASE test TO app_user_vs"))
        conn.execute(sa_text("GRANT USAGE ON SCHEMA public TO app_user_vs"))
        conn.execute(
            sa_text(
                "GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public "
                "TO app_user_vs"
            )
        )
        conn.execute(
            sa_text(
                "GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO app_user_vs"
            )
        )
    sync_engine.dispose()


# ── DB fixtures (session-scoped) ──────────────────────────────────────────────


@pytest.fixture(scope="session")
def pg_vs():
    with PostgresContainer("pgvector/pgvector:pg16") as container:
        _apply_migrations(container.get_connection_url())
        yield container


@pytest.fixture(scope="session")
def async_factory_vs(pg_vs):
    from sqlalchemy.pool import NullPool

    raw_url = pg_vs.get_connection_url()
    app_url = re.sub(
        r"(postgresql(?:\+psycopg2)?://)([^:@]+):([^@]+)(@)",
        r"\1app_user_vs:app_password_vs\4",
        raw_url,
    )
    async_url = app_url.replace("postgresql+psycopg2://", "postgresql+asyncpg://").replace(
        "postgresql://", "postgresql+asyncpg://"
    )
    engine = create_async_engine(async_url, echo=False, poolclass=NullPool)
    return async_sessionmaker(engine, expire_on_commit=False)


@pytest.fixture(scope="session")
def seeded_tenants(pg_vs, async_factory_vs):
    import asyncio as _asyncio

    async def _seed():
        for tid in (TENANT_A, TENANT_B):
            async with with_tenant(tid, session_factory=async_factory_vs) as s:
                s.add(Tenant(id=tid, slug=f"vs-tenant-{tid}", name=f"VS Tenant {tid}"))

    _asyncio.run(_seed())
    return (TENANT_A, TENANT_B)


# ── 1. hash_visitor deterministico ───────────────────────────────────────────


def test_hash_visitor_deterministic():
    h1 = hash_visitor(VISITOR_UUID, str(TENANT_A))
    h2 = hash_visitor(VISITOR_UUID, str(TENANT_A))
    assert h1 == h2
    assert len(h1) == 32
    assert h1.isalnum()


# ── 2. hash_visitor tenant isolation ─────────────────────────────────────────


def test_hash_visitor_tenant_isolation():
    h_a = hash_visitor(VISITOR_UUID, str(TENANT_A))
    h_b = hash_visitor(VISITOR_UUID, str(TENANT_B))
    assert h_a != h_b


# ── 3. upsert insert → is_new=True ───────────────────────────────────────────


@pytest.mark.asyncio(loop_scope="session")
async def test_upsert_insert_new_visitor(async_factory_vs, seeded_tenants):
    visitor_id = str(_uuid7())

    async with with_tenant(TENANT_A, session_factory=async_factory_vs) as s:
        vs, is_new = await upsert_visitor_session(
            s, TENANT_A, visitor_id, _SAMPLE_SIGNALS, _SAMPLE_PERSONAS, 0.75
        )

    assert is_new is True
    assert vs.id is not None
    assert vs.tenant_id == TENANT_A
    assert vs.confidence == pytest.approx(0.75)
    assert len(vs.inferred_personas) == 2


# ── 4. upsert update → is_new=False, JSONB aggiornato ────────────────────────


@pytest.mark.asyncio(loop_scope="session")
async def test_upsert_update_existing_visitor(async_factory_vs, seeded_tenants):
    visitor_id = str(_uuid7())

    async with with_tenant(TENANT_A, session_factory=async_factory_vs) as s:
        _, is_new_first = await upsert_visitor_session(
            s, TENANT_A, visitor_id, _SAMPLE_SIGNALS, _SAMPLE_PERSONAS, 0.5
        )

    updated_personas = [PersonaScore(persona_id="luxury_retiree", score=0.9)]
    async with with_tenant(TENANT_A, session_factory=async_factory_vs) as s:
        vs, is_new_second = await upsert_visitor_session(
            s, TENANT_A, visitor_id, _SAMPLE_SIGNALS, updated_personas, 0.9
        )

    assert is_new_first is True
    assert is_new_second is False
    assert vs.confidence == pytest.approx(0.9)
    assert len(vs.inferred_personas) == 1
    assert vs.inferred_personas[0]["persona_id"] == "luxury_retiree"


# ── 5. get_latest_session dopo upsert ────────────────────────────────────────


@pytest.mark.asyncio(loop_scope="session")
async def test_get_latest_session_after_upsert(async_factory_vs, seeded_tenants):
    visitor_id = str(_uuid7())

    async with with_tenant(TENANT_A, session_factory=async_factory_vs) as s:
        inserted, _ = await upsert_visitor_session(
            s, TENANT_A, visitor_id, _SAMPLE_SIGNALS, _SAMPLE_PERSONAS, 0.6
        )

    async with with_tenant(TENANT_A, session_factory=async_factory_vs) as s:
        found = await get_latest_session(s, TENANT_A, visitor_id)

    assert found is not None
    assert found.id == inserted.id
    assert found.visitor_hash == inserted.visitor_hash


# ── 6. get_latest_session visitor inesistente → None ─────────────────────────


@pytest.mark.asyncio(loop_scope="session")
async def test_get_latest_session_not_found(async_factory_vs, seeded_tenants):
    unknown_id = str(_uuid7())
    async with with_tenant(TENANT_A, session_factory=async_factory_vs) as s:
        result = await get_latest_session(s, TENANT_A, unknown_id)
    assert result is None


# ── 7. tenant isolation: stesso visitor_id → 2 righe separate ────────────────


@pytest.mark.asyncio(loop_scope="session")
async def test_tenant_isolation_separate_rows(async_factory_vs, seeded_tenants):
    visitor_id = str(_uuid7())

    async with with_tenant(TENANT_A, session_factory=async_factory_vs) as s:
        vs_a, _ = await upsert_visitor_session(
            s, TENANT_A, visitor_id, _SAMPLE_SIGNALS, _SAMPLE_PERSONAS, 0.5
        )

    async with with_tenant(TENANT_B, session_factory=async_factory_vs) as s:
        vs_b, _ = await upsert_visitor_session(
            s, TENANT_B, visitor_id, _SAMPLE_SIGNALS, _SAMPLE_PERSONAS, 0.5
        )

    assert vs_a.id != vs_b.id
    assert vs_a.tenant_id == TENANT_A
    assert vs_b.tenant_id == TENANT_B
    # Different hashes because tenant_id is part of the hash
    assert vs_a.visitor_hash != vs_b.visitor_hash


# ── 8. API POST /visitor-sessions/upsert → 200 (mock) ────────────────────────


@pytest.mark.asyncio
async def test_api_upsert_200(client):
    mock_vs = MagicMock(spec=VisitorSession)
    mock_vs.id = _uuid7()
    mock_vs.updated_at = __import__("datetime").datetime.now(__import__("datetime").timezone.utc)

    @asynccontextmanager
    async def _fake_with_tenant(*args, **kwargs):
        yield AsyncMock()

    with patch(
        "digidentity_api.api.visitor_sessions.with_tenant",
        new=_fake_with_tenant,
    ), patch(
        "digidentity_api.api.visitor_sessions.upsert_visitor_session",
        new=AsyncMock(return_value=(mock_vs, True)),
    ):
        resp = await client.post(
            "/api/v1/visitor-sessions/upsert",
            json={
                "visitor_id": VISITOR_UUID,
                "signals": {
                    "device_class": "desktop",
                    "utm": {},
                    "is_returning": False,
                },
                "inferred_personas": [
                    {"persona_id": "browsing", "score": 0.5},
                ],
                "confidence": 0.5,
            },
            headers={"X-Tenant-Id": str(TENANT_A)},
        )

    assert resp.status_code == 200
    data = resp.json()
    assert "session_id" in data
    assert data["is_new"] is True


# ── 9. API POST → 422 payload non valido ─────────────────────────────────────


@pytest.mark.asyncio
async def test_api_upsert_422_invalid_payload(client):
    resp = await client.post(
        "/api/v1/visitor-sessions/upsert",
        json={"visitor_id": "not-a-uuid"},  # missing required fields
        headers={"X-Tenant-Id": str(TENANT_A)},
    )
    assert resp.status_code == 422


# ── 10. API GET 404 senza DB ──────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_api_get_visitor_session_no_db(client):
    resp = await client.get(
        f"/api/v1/visitor-sessions/{VISITOR_UUID}",
        headers={"X-Tenant-Id": str(TENANT_A)},
    )
    # 404 (no session) or 503 (no real DB configured) are both valid without a DB
    assert resp.status_code in (404, 503)


# ── 11. Integrazione: upsert poi GET → coerenza dati ─────────────────────────


@pytest.mark.asyncio(loop_scope="session")
async def test_integration_upsert_then_get(async_factory_vs, seeded_tenants):
    visitor_id = str(_uuid7())

    async with with_tenant(TENANT_A, session_factory=async_factory_vs) as s:
        inserted, _ = await upsert_visitor_session(
            s, TENANT_A, visitor_id, _SAMPLE_SIGNALS, _SAMPLE_PERSONAS, 0.77
        )

    async with with_tenant(TENANT_A, session_factory=async_factory_vs) as s:
        found = await get_latest_session(s, TENANT_A, visitor_id)

    assert found is not None
    assert found.id == inserted.id
    assert found.confidence == pytest.approx(0.77)
    assert found.signals.get("referrer") == "google.com"
    assert found.inferred_personas[0]["persona_id"] == "international_investor"


# ── 12. Concurrency: 2 upsert paralleli → 1 riga ─────────────────────────────


@pytest.mark.asyncio(loop_scope="session")
async def test_concurrency_parallel_upserts_single_row(async_factory_vs, seeded_tenants):
    visitor_id = str(_uuid7())
    visitor_hash = hash_visitor(visitor_id, str(TENANT_A))

    async def _do_upsert(confidence: float):
        async with with_tenant(TENANT_A, session_factory=async_factory_vs) as s:
            return await upsert_visitor_session(
                s, TENANT_A, visitor_id, _SAMPLE_SIGNALS, _SAMPLE_PERSONAS, confidence
            )

    await asyncio.gather(_do_upsert(0.6), _do_upsert(0.8))

    # Verify only 1 row exists via tenant-context count
    async with async_factory_vs() as s:
        async with s.begin():
            from sqlalchemy import text  # noqa: PLC0415

            await s.execute(text(f"SET LOCAL app.tenant_id = '{TENANT_A}'"))
            result = await s.execute(
                sa.text(
                    "SELECT COUNT(*) FROM visitor_sessions "
                    "WHERE tenant_id = :tid AND visitor_hash = :vh"
                ),
                {"tid": str(TENANT_A), "vh": visitor_hash},
            )
            count = result.scalar()

    assert count == 1, f"Expected 1 row after concurrent upserts, got {count}"
