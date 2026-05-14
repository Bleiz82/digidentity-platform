"""
Test STEP 4 — Pack real-estate-luxury.

Verifica:
1. PackRegistry carica correttamente pack.yaml da disco
2. I 3 Jinja template si renderizzano senza errori con una proprietà sample
3. Search con query lifestyle-heavy → top-3 con lifestyle stub embedding
4. Search con query feature-heavy → top-3 con features stub embedding
5. Seed idempotente (due run → stesso numero di righe)
"""
import re
import sys
from pathlib import Path
from uuid import UUID

import pytest
import uuid_utils
from sqlalchemy import create_engine
from sqlalchemy import text as sa_text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from digidentity_api.db.models import Entity, Tenant
from digidentity_api.db.search import HybridSearchRepository, SearchWeights
from digidentity_api.db.tenant_context import with_tenant
from digidentity_api.packs.registry import PackRegistry, init_registry
from digidentity_api.packs.stub_embeddings import make_query_embedding, make_stub_embedding
from digidentity_api.packs.templates import render_pack_templates

PACK_ROOT = Path(__file__).parent.parent.parent.parent / "packs" / "real-estate-luxury"
PACKS_ROOT = PACK_ROOT.parent


def apply_migrations_re(sync_url: str) -> None:
    from alembic import command
    from alembic.config import Config

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


@pytest.fixture(scope="module")
def pg_re():
    from testcontainers.postgres import PostgresContainer

    with PostgresContainer("pgvector/pgvector:pg16") as container:
        apply_migrations_re(container.get_connection_url())
        yield container


@pytest.fixture(scope="module")
def session_factory_re(pg_re):
    raw_url = pg_re.get_connection_url()
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
def pack_registry() -> PackRegistry:
    return init_registry(PACKS_ROOT)


# ── test 1: pack loads ────────────────────────────────────────────────────────


def test_pack_loads_from_disk(pack_registry: PackRegistry) -> None:
    assert "real-estate-luxury" in pack_registry.pack_ids
    pack = pack_registry.get("real-estate-luxury")
    assert pack is not None
    assert pack["version"] == "0.1.0"
    assert len(pack["personas"]) == 3


# ── test 2: templates render ──────────────────────────────────────────────────


def test_templates_render_correctly() -> None:
    sample = {
        "title": "Villa Test",
        "property_type": "villa",
        "location": "Capri",
        "description": "Villa panoramica.",
        "price": 3000000,
        "rooms": 5,
        "bathrooms": 4,
        "sqm": 400,
        "land_sqm": 2000,
        "pool": True,
        "pool_type": "infinity",
        "garage": 2,
        "elevator": False,
        "sea_distance": 100,
        "year_built": 2015,
        "energy_class": "A",
        "lifestyle_tags": ["mare", "lusso"],
        "lifestyle_narrative": "Mare, sole, dolce vita.",
        "location_lifestyle": "Capri: icona italiana.",
        "outdoor_spaces": ["terrazza", "piscina"],
        "wellness": ["sauna"],
        "features": ["vista mare", "piscina infinity"],
        "slug": "villa-test",
    }
    rendered = render_pack_templates(PACK_ROOT, sample)
    assert "content_template" in rendered
    assert "lifestyle_template" in rendered
    assert "features_template" in rendered
    assert "Villa Test" in rendered["content_template"]
    assert "mare" in rendered["lifestyle_template"].lower()
    assert "villa" in rendered["features_template"].lower()
    assert "5" in rendered["features_template"]


# ── test 3: lifestyle query ranks lifestyle higher ─────────────────────────────


@pytest.mark.asyncio(loop_scope="session")
async def test_search_lifestyle_query_ranks_lifestyle_higher(session_factory_re: async_sessionmaker) -> None:
    """
    10 entità: 5 lifestyle-heavy, 5 feature-heavy.
    Query con pesi lifestyle_search (0.15/0.70/0.15).
    Le top-3 devono essere lifestyle-heavy (verificato da marker nel payload).
    """
    tid = UUID(str(uuid_utils.uuid7()))

    # Setup tenant
    async with with_tenant(tid, session_factory=session_factory_re) as sess:
        sess.add(Tenant(id=tid, slug=f"lifestyle-test-{str(tid)[:8]}", name="Lifestyle Test"))

    # 5 lifestyle-heavy
    lifestyle_text = "piscina terrazza vista mare tramonto dolce vita relax wellness spa"
    for i in range(5):
        async with with_tenant(tid, session_factory=session_factory_re) as sess:
            sess.add(Entity(
                tenant_id=tid,
                pack_id="real-estate-luxury",
                entity_type="property",
                payload={"type": "lifestyle_heavy", "idx": i},
                content_emb=make_stub_embedding(f"content lifestyle {i}", "content"),
                lifestyle_emb=make_stub_embedding(f"{lifestyle_text} {i}", "lifestyle"),
                features_emb=make_stub_embedding(f"features lifestyle {i}", "features"),
                embedding_version="text-embedding-3-large-halfvec-v1",
            ))

    # 5 feature-heavy
    features_text = "5 camere 850 mq garage 3 posti ascensore classe A+ anno 2022"
    for i in range(5):
        async with with_tenant(tid, session_factory=session_factory_re) as sess:
            sess.add(Entity(
                tenant_id=tid,
                pack_id="real-estate-luxury",
                entity_type="property",
                payload={"type": "feature_heavy", "idx": i},
                content_emb=make_stub_embedding(f"content features {i}", "content"),
                lifestyle_emb=make_stub_embedding(f"lifestyle features {i}", "lifestyle"),
                features_emb=make_stub_embedding(f"{features_text} {i}", "features"),
                embedding_version="text-embedding-3-large-halfvec-v1",
            ))

    # Query lifestyle
    query_emb = make_query_embedding(lifestyle_text, query_type="lifestyle")
    weights = SearchWeights(content=0.15, lifestyle=0.70, features=0.15)

    async with with_tenant(tid, session_factory=session_factory_re) as sess:
        repo = HybridSearchRepository(sess)
        results = await repo.search(query_emb, weights=weights, limit=10)

    top3_types = [e.payload.get("type") for e, _ in results[:3]]
    lifestyle_count = top3_types.count("lifestyle_heavy")
    assert lifestyle_count >= 2, (
        f"Expected >=2 lifestyle_heavy in top-3, got {top3_types}"
    )


# ── test 4: feature query ranks features higher ────────────────────────────────


@pytest.mark.asyncio(loop_scope="session")
async def test_search_feature_query_ranks_features_higher(session_factory_re: async_sessionmaker) -> None:
    """Simmetrico: query feature-heavy con pesi feature_search → top-3 features."""
    tid = UUID(str(uuid_utils.uuid7()))

    async with with_tenant(tid, session_factory=session_factory_re) as sess:
        sess.add(Tenant(id=tid, slug=f"features-test-{str(tid)[:8]}", name="Features Test"))

    lifestyle_text_ls = "mare tramonto relax piscina vista colline"
    features_text = "villa 7 camere 950 mq piscina garage 4 posti ascensore classe energetica A+"
    for i in range(5):
        async with with_tenant(tid, session_factory=session_factory_re) as sess:
            sess.add(Entity(
                tenant_id=tid,
                pack_id="real-estate-luxury",
                entity_type="property",
                payload={"type": "lifestyle_heavy", "idx": i},
                content_emb=make_stub_embedding(f"lifestyle_group_content_alpha_{i}", "content"),
                lifestyle_emb=make_stub_embedding(f"{lifestyle_text_ls} {i}", "lifestyle"),
                features_emb=make_stub_embedding(f"lifestyle_group_features_alpha_{i}", "features"),
                embedding_version="text-embedding-3-large-halfvec-v1",
            ))

    for i in range(5):
        async with with_tenant(tid, session_factory=session_factory_re) as sess:
            sess.add(Entity(
                tenant_id=tid,
                pack_id="real-estate-luxury",
                entity_type="property",
                payload={"type": "feature_heavy", "idx": i},
                content_emb=make_stub_embedding(f"features_group_content_beta_{i}", "content"),
                lifestyle_emb=make_stub_embedding(f"features_group_lifestyle_beta_{i}", "lifestyle"),
                features_emb=make_stub_embedding(f"{features_text} {i}", "features"),
                embedding_version="text-embedding-3-large-halfvec-v1",
            ))

    query_emb = make_query_embedding(features_text, query_type="features")
    weights = SearchWeights(content=0.20, lifestyle=0.10, features=0.70)

    async with with_tenant(tid, session_factory=session_factory_re) as sess:
        repo = HybridSearchRepository(sess)
        results = await repo.search(query_emb, weights=weights, limit=10)

    top3_types = [e.payload.get("type") for e, _ in results[:3]]
    features_count = top3_types.count("feature_heavy")
    assert features_count >= 2, (
        f"Expected >=2 feature_heavy in top-3, got {top3_types}"
    )


# ── test 5: seed idempotent ────────────────────────────────────────────────────


@pytest.mark.asyncio(loop_scope="session")
async def test_seed_idempotent(session_factory_re: async_sessionmaker) -> None:
    """Lanciare seed 2 volte → stesso numero di righe (no duplicati)."""
    sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))
    from seed_real_estate import seed_database  # type: ignore[import]

    tid = UUID(str(uuid_utils.uuid7()))
    async with with_tenant(tid, session_factory=session_factory_re) as sess:
        sess.add(Tenant(id=tid, slug=f"idempotent-{str(tid)[:8]}", name="Idempotent Test"))

    # Prima run
    counts1 = await seed_database(session_factory_re, [tid])
    inserted1 = counts1[str(tid)]

    # Seconda run — deve inserire 0
    counts2 = await seed_database(session_factory_re, [tid])
    inserted2 = counts2[str(tid)]

    assert inserted1 == 100, f"Expected 100 inserted in run 1, got {inserted1}"
    assert inserted2 == 0, f"Expected 0 inserted in run 2 (idempotent), got {inserted2}"
