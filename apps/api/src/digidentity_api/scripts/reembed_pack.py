"""CLI: re-embed all entities of a pack using the current EmbeddingRouter.

Usage:
    uv run python -m digidentity_api.scripts.reembed_pack --pack real-estate-luxury
    uv run python -m digidentity_api.scripts.reembed_pack --pack real-estate-luxury --dry-run
    uv run python -m digidentity_api.scripts.reembed_pack --pack real-estate-luxury --batch-size 50

What it does:
  1. Connects to DATABASE_URL.
  2. Loads all entities WHERE pack_id = <pack> and (content_emb IS NULL OR embedding_version != current).
  3. For each entity, generates content_emb / lifestyle_emb / features_emb via EmbeddingRouter.
  4. Updates the entity row with new vectors and sets embedding_version.
  5. Reports progress per batch.

Does NOT run automatically at startup. Manual invocation only (ADR-007).
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import sys

log = logging.getLogger(__name__)

EMBEDDING_VERSION = "text-embedding-3-large-halfvec-v1"


async def _reembed(pack_id: str, batch_size: int, dry_run: bool) -> int:
    """Return count of entities processed."""
    from sqlalchemy import select, update  # noqa: PLC0415
    from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession  # noqa: PLC0415
    from sqlalchemy.orm import sessionmaker  # noqa: PLC0415

    from digidentity_api.config import settings  # noqa: PLC0415
    from digidentity_api.db.models import Entity  # noqa: PLC0415
    from digidentity_api.engines.embeddings import get_router  # noqa: PLC0415

    router = get_router()
    engine = create_async_engine(settings.DATABASE_URL, echo=False)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    processed = 0
    offset = 0

    print(f"[reembed_pack] pack={pack_id} batch_size={batch_size} dry_run={dry_run}")
    print(f"[reembed_pack] embedding provider dims={router.dimensions}")

    async with async_session() as session:
        while True:
            result = await session.execute(
                select(Entity)
                .where(Entity.pack_id == pack_id)
                .order_by(Entity.created_at)
                .limit(batch_size)
                .offset(offset)
            )
            entities: list[Entity] = list(result.scalars().all())

            if not entities:
                break

            # Build texts for each embedding type
            content_texts = [
                f"{e.payload.get('title', '')} {e.payload.get('description', '')}".strip()
                for e in entities
            ]
            lifestyle_texts = [
                e.payload.get("lifestyle_narrative", e.payload.get("description", ""))
                for e in entities
            ]
            features_texts = [
                _build_features_text(e.payload)
                for e in entities
            ]

            if not dry_run:
                content_vecs = await router.embed(content_texts)
                lifestyle_vecs = await router.embed(lifestyle_texts)
                features_vecs = await router.embed(features_texts)

                for i, entity in enumerate(entities):
                    entity.content_emb = content_vecs[i]
                    entity.lifestyle_emb = lifestyle_vecs[i]
                    entity.features_emb = features_vecs[i]
                    entity.embedding_version = EMBEDDING_VERSION

                await session.commit()

            processed += len(entities)
            print(
                f"[reembed_pack] processed {processed} entities "
                f"(batch offset={offset})"
                + (" [DRY RUN]" if dry_run else "")
            )

            if len(entities) < batch_size:
                break
            offset += batch_size

    await engine.dispose()
    print(f"[reembed_pack] done. total={processed}")
    return processed


def _build_features_text(payload: dict) -> str:
    """Convert structured payload to natural-language features string."""
    parts = []
    if title := payload.get("title"):
        parts.append(title)
    if bedrooms := payload.get("bedrooms"):
        parts.append(f"{bedrooms} bedrooms")
    if sqm := payload.get("sqm"):
        parts.append(f"{sqm} sqm")
    if payload.get("pool"):
        parts.append("with pool")
    if location := payload.get("location"):
        parts.append(location)
    return ", ".join(parts) if parts else payload.get("description", "")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Re-embed all entities of a pack via EmbeddingRouter (ADR-007)."
    )
    parser.add_argument("--pack", required=True, help="Pack ID (e.g. real-estate-luxury)")
    parser.add_argument(
        "--batch-size", type=int, default=100, help="Entities per batch (default: 100)"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Compute embeddings but do not write to DB",
    )
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, stream=sys.stdout)

    count = asyncio.run(_reembed(args.pack, args.batch_size, args.dry_run))
    sys.exit(0 if count >= 0 else 1)


if __name__ == "__main__":
    main()
