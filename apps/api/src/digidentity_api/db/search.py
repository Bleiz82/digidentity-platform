from dataclasses import dataclass
from uuid import UUID

import numpy as np
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from digidentity_api.db.models import Entity
from digidentity_api.db.repositories import TenantAwareRepository


@dataclass(frozen=True)
class SearchWeights:
    content: float = 0.45
    lifestyle: float = 0.35
    features: float = 0.20

    def __post_init__(self) -> None:
        total = self.content + self.lifestyle + self.features
        if abs(total - 1.0) > 1e-6:
            raise ValueError(f"weights must sum to 1.0, got {total}")


def normalize_embedding(v: list[float] | np.ndarray) -> list[float]:
    """Normalizza a unit vector e converte a float16 per halfvec."""
    arr = np.array(v, dtype=np.float32)
    norm = np.linalg.norm(arr)
    if norm > 0:
        arr = arr / norm
    return arr.astype(np.float16).tolist()


class HybridSearchRepository(TenantAwareRepository):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session)

    async def search(
        self,
        query_embedding: list[float] | np.ndarray,
        weights: SearchWeights | None = None,
        limit: int = 10,
        ef_search: int = 80,
    ) -> list[tuple[Entity, float]]:
        """
        Ricerca ibrida multi-embedding con somma pesata (ADR-005 B1).

        Strategia:
        1. CTE: top-50 candidati per ciascun indice HNSW (usa hnsw.ef_search)
        2. Re-score: somma pesata delle 3 similarità coseno sui candidati merged
        3. Ritorna top-N ordinati per score desc

        Deve girare dentro with_tenant().
        """
        self._assert_tenant_context()

        w = weights or SearchWeights()
        q_normalized = normalize_embedding(query_embedding)

        # ef_search per questa transazione.
        # asyncpg non supporta parametri bind per SET LOCAL: interpolazione
        # diretta sicura perché ef_search è validato come intero.
        ef_int = int(ef_search)
        await self._session.execute(text(f"SET LOCAL hnsw.ef_search = {ef_int}"))

        # Cast dell'embedding a stringa '[x,y,z]' per pgvector ::halfvec
        q_str = "[" + ",".join(str(x) for x in q_normalized) + "]"

        result = await self._session.execute(
            text("""
                WITH candidates AS (
                    (
                        SELECT id FROM entities
                        WHERE content_emb IS NOT NULL
                        ORDER BY content_emb <=> (:q)::halfvec
                        LIMIT 50
                    )
                    UNION
                    (
                        SELECT id FROM entities
                        WHERE lifestyle_emb IS NOT NULL
                        ORDER BY lifestyle_emb <=> (:q)::halfvec
                        LIMIT 50
                    )
                    UNION
                    (
                        SELECT id FROM entities
                        WHERE features_emb IS NOT NULL
                        ORDER BY features_emb <=> (:q)::halfvec
                        LIMIT 50
                    )
                )
                SELECT
                    e.id,
                    e.tenant_id,
                    e.pack_id,
                    e.entity_type,
                    e.payload,
                    e.embedding_version,
                    e.created_at,
                    e.updated_at,
                    :w_c * (1 - (e.content_emb <=> (:q)::halfvec)) +
                    :w_l * (1 - (e.lifestyle_emb <=> (:q)::halfvec)) +
                    :w_f * (1 - (e.features_emb <=> (:q)::halfvec)) AS score
                FROM entities e
                WHERE e.id IN (SELECT id FROM candidates)
                ORDER BY score DESC
                LIMIT :limit
            """),
            {
                "q": q_str,
                "w_c": w.content,
                "w_l": w.lifestyle,
                "w_f": w.features,
                "limit": limit,
            },
        )
        rows = result.fetchall()

        entities_with_scores: list[tuple[Entity, float]] = []
        for row in rows:
            entity = Entity(
                id=row.id,
                tenant_id=row.tenant_id,
                pack_id=row.pack_id,
                entity_type=row.entity_type,
                payload=row.payload,
                embedding_version=row.embedding_version,
                created_at=row.created_at,
                updated_at=row.updated_at,
            )
            entities_with_scores.append((entity, float(row.score)))

        return entities_with_scores
