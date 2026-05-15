# ADR-006: pgvector halfvec(3072) Amendment to ADR-005

- **Status**: accepted
- **Date**: 2026-05-15
- **Authors**: Stefano Corda
- **BIBLE refs**: §6.1, §9
- **Supersedes**: n/a
- **Superseded by**: n/a
- **Amends**: ADR-005 (Multi-Embedding Strategy per Knowledge Graph Engine)

---

## Context

ADR-005 specified three HNSW indexes per entity using `vector(3072)` (float32) with a
per-tenant isolated index strategy and a RAM working set of ~25–35 GB/tenant at 100K
entities. During Phase 1 implementation, three constraints surfaced that required
deviating from those decisions before any code shipped to `main`.

**Constraint 1 — pgvector 0.8.2 HNSW dimension cap.**
pgvector 0.8.2 enforces a hard limit of 2000 dimensions on HNSW and ivfflat indexes for
the `vector` (float32) type. `text-embedding-3-large` produces 3072-dimensional vectors,
making it impossible to build any HNSW index on a `vector(3072)` column. The two
available escape hatches are: (a) reduce the embedding dimension to ≤2000 via the
model's matryoshka truncation, losing semantic coverage; or (b) switch to `halfvec`
(float16), which pgvector supports up to 16000 dimensions for HNSW. Option (b) was
chosen as it preserves full dimensionality.

**Constraint 2 — RAM implications of halfvec.**
Switching to float16 halves the per-vector storage from 12 KB to 6 KB (3072 dim × 4
bytes → 3072 dim × 2 bytes). This directly revises the RAM working set estimate in
ADR-005 §D downward from ~25–35 GB/tenant to ~13–18 GB/tenant, with corresponding
impact on multi-tenant capacity planning.

**Constraint 3 — HNSW index strategy: shared vs per-tenant.**
ADR-005 §Decisione table specified per-tenant isolated HNSW indexes for alignment with
ADR-003 tenant isolation guarantees. During implementation it became clear that
per-tenant HNSW is operationally expensive at scale: each new tenant requires index
creation, separate `pg_prewarm`, and independent `ef_search` tuning. pgvector 0.8.2
supports `halfvec_cosine_ops` on shared indexes with RLS post-filtering (using
`SET LOCAL row_security = on` via `with_tenant()`). The isolation guarantee is provided
by Postgres RLS, not by physical index separation. This approach was validated by the
test `test_vector_search_rls_isolation` (commit `469532a`).

All three changes were implemented in commit `469532a` and migration
`alembic/versions/002_entities_hnsw.py` before the Phase 1 DoD merge. This ADR
formalizes them retroactively per the convention that accepted decisions require an ADR
even when discovered during implementation.

---

## Decision

### Amendment 1 — Vector type: `vector(3072)` → `halfvec(3072)`

The `content_emb`, `lifestyle_emb`, and `features_emb` columns use `halfvec(3072)`
instead of `vector(3072)`. The HNSW index operator class is `halfvec_cosine_ops`.

**Trade-off:** float16 has lower numeric precision than float32. Empirical recall impact
across standard ANN benchmarks for cosine similarity at high dimensionality is 0.1–0.5%
(negligible for the query quality targets in §6.1). The constraint imposed by pgvector
0.8.2's 2000-dim cap on `vector`-type HNSW is non-negotiable at 3072 dims — `halfvec`
is the only path to HNSW at this dimensionality without truncating the embedding.

ADR-005 §D row "dim = 3072 / vector type" is superseded by this amendment.

### Amendment 2 — RAM working set: ~25–35 GB/tenant → ~13–18 GB/tenant

The revised RAM estimate for a single tenant at 100K entities is:

| Component | ADR-005 estimate | Revised estimate (halfvec) |
|---|---|---|
| 3 indexes × 3072 dim × bytes × 100K | ~3.7 GB (float32) | ~1.85 GB (float16) |
| HNSW graph overhead (m=16, ~2–3× raw) | ~7–10 GB | ~4–6 GB |
| Postgres shared buffers + WAL headroom | ~1–2 GB | ~1–2 GB |
| **Working set per tenant** | **~25–35 GB** | **~13–18 GB** |

Worst-case multi-tenant (10 tenants active in RAM): ~130–180 GB (down from ~250–350 GB).
Revised provisioning minimum for the DB host: **192 GB RAM** (down from 384 GB),
with swap on NVMe for idle tenants (cold page-in remains ~200–400ms).

ADR-005 §D "Stima RAM working set" table and §Negative consequences RAM bullet are
superseded by this amendment.

### Amendment 3 — HNSW strategy: per-tenant isolated → SHARED with RLS

A single shared HNSW index covers all tenants per embedding type. Tenant isolation is
enforced by Postgres RLS (`SET LOCAL row_security = on` inside `with_tenant()`), not by
physical index boundaries.

**Rationale:** Shared HNSW + RLS FORCE is the correct implementation of ADR-003's
isolation contract at the pgvector layer. Per-tenant indexes duplicate identical graph
structure for each tenant, increase DBA overhead (index creation on tenant onboarding,
separate vacuum and reindex schedules), and provide no additional isolation beyond RLS.
The isolation test `test_vector_search_rls_isolation` verifies that a query executed
inside `with_tenant(tenant_A)` cannot retrieve entities belonging to `tenant_B` even
when both share the same physical index.

**Threshold for revisiting:** if query latency p95 exceeds 50 ms on a single large
tenant (≥500K entities), the over-fetch factor inherent in shared HNSW post-filtering
warrants moving that tenant to a dedicated index partition. This is a monitoring
trigger, not a current action item.

ADR-005 §Decisione table row "Indice HNSW" is superseded by this amendment.

---

## Consequences

### Positive

- HNSW indexes on `halfvec(3072)` are buildable without any dimension truncation or
  model downgrade.
- RAM provisioning cost is halved: 192 GB host (not 384 GB) for 10 concurrent tenants.
  Reduces cloud infrastructure spend before the first multi-tenant go-live.
- Shared HNSW simplifies operations: single index creation per embedding type, no
  per-tenant index lifecycle management, no need to pre-warm N separate indexes on
  restart.
- Isolation guarantee is unchanged: RLS FORCE on the `with_tenant()` context manager
  prevents cross-tenant data access regardless of index sharing.

### Negative

- **float16 precision loss:** 0.1–0.5% recall degradation vs float32 at cosine similarity.
  Acceptable for production, but must be re-evaluated if a future embedding model has
  poor float16 stability at 3072 dims.
- **Shared index over-fetch at scale:** a query inside `with_tenant(X)` scans the full
  shared graph and discards non-X rows via RLS. At large tenant sizes (≥500K entities),
  the effective K retrieved before RLS filtering grows, increasing latency. The 50 ms
  p95 threshold (Amendment 3) is the operational guard.
- **halfvec is pgvector-specific:** if the vector store is ever migrated away from
  pgvector (requires an ADR), the half-precision storage format does not have a direct
  equivalent in all alternative backends (e.g., Weaviate, Qdrant). Migration would
  require re-embedding or upcast to float32.

### Neutral

- The `halfvec_cosine_ops` operator class requires pgvector ≥ 0.7.0. The project
  already pins pgvector 0.8.2; this is not an additional constraint.
- `ef_search=80` and `m=16` HNSW parameters from ADR-005 §D are unchanged.
- Embedding cost estimates ($6.83/tenant via Batch API) from ADR-005 §D are unchanged;
  they depend on token count, not vector storage type.

---

## Implementation Notes

- Migration file: `alembic/versions/002_entities_hnsw.py`
  — defines `halfvec(3072)` column type and creates HNSW index with
  `halfvec_cosine_ops`, `m=16`, `ef_construction=128`.
- Isolation test: `tests/test_vector_search_rls_isolation.py`
  — verifies shared index + RLS prevents cross-tenant retrieval.
- Commit reference: `469532a` — first implementation of halfvec + shared HNSW.
- All three amendments are co-deployed; there is no intermediate state where only one
  or two are active.

---

## References

- ADR-005 — Multi-Embedding Strategy per Knowledge Graph Engine (amended by this ADR)
- ADR-003 — Tenant isolation (RLS contract that shared HNSW relies on)
- BIBLE v3 §6.1 — Knowledge Graph Engine: multi-embedding, HNSW, hybrid search
- BIBLE v3 §9 — Canonical stack: pgvector, OpenAI embedding SDK
- pgvector 0.8.2 release notes — `halfvec` type, HNSW operator classes, dimension limits
- `alembic/versions/002_entities_hnsw.py` — migration implementing these amendments
- `tests/test_vector_search_rls_isolation.py` — RLS isolation test for shared index
