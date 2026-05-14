"""
Test ADR-005: Knowledge Graph Engine v0 — HybridSearchRepository.

Verifica:
1. RLS su vector search: entità di tenant A invisibili a tenant B
   (il caso più sneaky: HNSW index è shared, ma RLS deve filtrare)
2. Pesi diversi → ordinamenti diversi (verifica somma pesata B1)
3. Search senza with_tenant → TenantContextError
"""

import re
from pathlib import Path
from uuid import UUID

import numpy as np
import pytest
import uuid_utils
from sqlalchemy import create_engine
from sqlalchemy import text as sa_text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool
from testcontainers.postgres import PostgresContainer

from digidentity_api.db.errors import TenantContextError
from digidentity_api.db.models import Entity, Tenant
from digidentity_api.db.search import HybridSearchRepository, SearchWeights, normalize_embedding
from digidentity_api.db.tenant_context import with_tenant


# ── helpers ──────────────────────────────────────────────────────────────────


def make_stub_embedding(seed: int, dim: int = 3072) -> list[float]:
    """Genera embedding deterministico normalizzato come float16."""
    rng = np.random.default_rng(seed)
    v = rng.random(dim).astype(np.float32)
    v = v / np.linalg.norm(v)
    return v.astype(np.float16).tolist()


def apply_migrations_kg(sync_url: str) -> None:
    from alembic import command
    from alembic.config import Config

    # 1. Applica migration come superuser
    alembic_cfg_path = Path(__file__).parent.parent / "alembic.ini"
    cfg = Config(str(alembic_cfg_path))
    cfg.set_main_option("sqlalchemy.url", sync_url)
    command.upgrade(cfg, "head")

    # 2. Crea app_user non-superuser — necessario perché FORCE ROW LEVEL SECURITY
    #    non si applica ai superuser PostgreSQL.
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


@pytest.fixture(scope="module")
def pg_container_kg():
    with PostgresContainer("pgvector/pgvector:pg16") as container:
        apply_migrations_kg(container.get_connection_url())
        yield container


@pytest.fixture(scope="module")
def session_factory_kg(pg_container_kg):
    raw_url = pg_container_kg.get_connection_url()
    # Sostituisce le credenziali superuser con app_user — necessario per RLS FORCE
    app_url = re.sub(
        r"(postgresql(?:\+psycopg2)?://)([^:@]+):([^@]+)(@)",
        r"\1app_user:app_password\4",
        raw_url,
    )
    async_url = (
        app_url.replace("postgresql+psycopg2://", "postgresql+asyncpg://").replace(
            "postgresql://", "postgresql+asyncpg://"
        )
    )
    engine = create_async_engine(async_url, echo=False, poolclass=NullPool)
    return async_sessionmaker(engine, expire_on_commit=False)


@pytest.fixture(scope="module")
def tenant_ids_kg() -> list[UUID]:
    return [UUID(str(uuid_utils.uuid7())) for _ in range(3)]


# ── test 1: RLS su vector search — cross-tenant leak ─────────────────────────


@pytest.mark.asyncio(loop_scope="session")
async def test_vector_search_rls_isolation(session_factory_kg, tenant_ids_kg):
    """
    Inserisce 10 entità per ciascuno dei 3 tenant.
    La query di tenant A non deve mai restituire entità di B o C.
    Questo verifica che RLS funzioni su ANN search con HNSW shared.
    """
    # Setup: inserisci 3 tenants
    for i, tid in enumerate(tenant_ids_kg):
        async with with_tenant(tid, session_factory=session_factory_kg) as sess:
            tenant = Tenant(id=tid, slug=f"kg-tenant-{i}", name=f"KG Tenant {i}")
            sess.add(tenant)

    # Setup: 10 entities per tenant
    seed_offset = 1000
    for i, tid in enumerate(tenant_ids_kg):
        async with with_tenant(tid, session_factory=session_factory_kg) as sess:
            for j in range(10):
                seed = seed_offset + i * 100 + j
                entity = Entity(
                    tenant_id=tid,
                    pack_id="real-estate-luxury",
                    entity_type="property",
                    payload={"title": f"Property t{i} e{j}"},
                    content_emb=make_stub_embedding(seed),
                    lifestyle_emb=make_stub_embedding(seed + 1),
                    features_emb=make_stub_embedding(seed + 2),
                )
                sess.add(entity)

    # Search: ogni tenant vede solo le proprie entità
    query_emb = make_stub_embedding(42)
    for tid in tenant_ids_kg:
        async with with_tenant(tid, session_factory=session_factory_kg) as sess:
            repo = HybridSearchRepository(sess)
            results = await repo.search(query_emb, limit=20)
            assert len(results) <= 10, f"Expected max 10 results, got {len(results)}"
            for entity, score in results:
                assert entity.tenant_id == tid, (
                    f"VECTOR SEARCH LEAK: tenant {tid} got entity with tenant_id={entity.tenant_id}"
                )


# ── test 2: pesi diversi → ordinamenti diversi ───────────────────────────────


@pytest.mark.asyncio(loop_scope="session")
async def test_different_weights_give_different_rankings(session_factory_kg, tenant_ids_kg):
    """
    Con pesi content-heavy vs lifestyle-heavy, le entità devono essere
    ordinate diversamente (almeno per qualche coppia di entità).
    """
    tid = tenant_ids_kg[0]
    # Query embedding: simile al seed 1000 (content_emb della prima entity)
    query_emb = make_stub_embedding(1000)

    weights_content_heavy = SearchWeights(content=0.80, lifestyle=0.10, features=0.10)
    weights_lifestyle_heavy = SearchWeights(content=0.10, lifestyle=0.80, features=0.10)

    async with with_tenant(tid, session_factory=session_factory_kg) as sess:
        repo = HybridSearchRepository(sess)
        results_content = await repo.search(query_emb, weights=weights_content_heavy, limit=10)

    async with with_tenant(tid, session_factory=session_factory_kg) as sess:
        repo = HybridSearchRepository(sess)
        results_lifestyle = await repo.search(query_emb, weights=weights_lifestyle_heavy, limit=10)

    ids_content = [e.id for e, _ in results_content]
    ids_lifestyle = [e.id for e, _ in results_lifestyle]

    # I ranking devono differire in almeno una posizione
    assert ids_content != ids_lifestyle, (
        "Expected different rankings with different weights"
    )


# ── test 3: search senza with_tenant → TenantContextError ────────────────────


@pytest.mark.asyncio(loop_scope="session")
async def test_search_without_tenant_context_raises(session_factory_kg):
    """HybridSearchRepository deve alzare TenantContextError senza contesto attivo."""
    async with session_factory_kg() as sess:
        repo = HybridSearchRepository(sess)
        with pytest.raises(TenantContextError, match="no active tenant context"):
            await repo.search(make_stub_embedding(0), limit=5)
