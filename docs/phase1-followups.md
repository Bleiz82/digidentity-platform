# Phase 1 — Follow-up Tracker

Items accumulated during Phase 1 implementation that are deferred or need formal resolution.
Not blockers for Phase 1 DoD unless noted.

---

## Phase 1 Baseline Metrics

Official baseline from Calibration Run #3 (commit `6ae91f8`, 2026-05-15):

| Eval | Metric | Value |
|------|--------|-------|
| retrieval_real_estate | NDCG@10 | 0.532 |
| retrieval_real_estate | MRR | 0.525 |
| retrieval_real_estate | recall@10 | 0.550 |
| retrieval_real_estate | min_results_rate | 1.000 |
| circuit_breaker | success_rate | 1.000 |
| router_correctness | accuracy | 1.000 |
| latency_sse | P50 | 84.4ms |
| latency_sse | P95 | 185.3ms |

Gates active from step-6.3 (commit post-`6ae91f8`). Thresholds = baseline × 0.85 for
non-deterministic metrics, baseline × 0.95 for deterministic. Latency margin 40–50%
for CI runner noise.

---

## Resolved in Phase 1

- **conversation_id path validation** (STEP 5.1): `GET /conversations/{id}/stream` now
  typed as `UUID` — FastAPI returns 422 on non-UUID path values.

- **Eval framework + calibration** (STEP 6.1–6.3): 4 eval sets implemented and gated.
  Runner fixed (alembic path, CB NoneType, router context signals). Retrieval YAML
  rewritten with exact-template queries (stub embedding constraint documented).
  cb-004 corrected (voice no-retry test, circuit stays closed with 1 failure < threshold 3).
  All gates active, exit-code 1 on threshold miss verified.

---

## Open for Phase 2

### Retrieval eval con query naturali

- **Reason**: stub embedding SHA256-based non supporta similarità semantica da overlap di keyword.
  Query naturali producono NDCG≈0 indipendentemente dalla somiglianza semantica con le entità.
- **Current workaround**: query = exact rendered template text (pipeline test, not quality test).
  Archive: `apps/api/evals/_archive/retrieval_natural_queries_phase1.yaml`
- **Action**: integrazione `text-embedding-3-large` reale (ADR-005 dim 3072 halfvec),
  ripristinare query naturali dall'archivio e rigenerare le aspettative NDCG.

### Tabella `conversations`

`conversation_id` is currently an opaque UUID string not persisted. The SSE endpoint
accepts it but does not create/validate against a DB record.
Phase 2: add `conversations` table with `tenant_id`, `session_id`, `created_at`, history refs.
The `log_usage` task silently fails if `conversation_id` is not a valid UUID format — acceptable
for Phase 1, must be validated server-side when the table is introduced.

### Long-polling fallback implementation

ADR-002 §A3 defines a long-polling degraded mode for aggressive corporate proxies.
Phase 1 only implements the `406 + X-Suggested-Fallback: long-polling` header negotiation.
Phase 2: implement `GET /conversations/{id}/poll?after={seq}` with Redis chunk buffer
and `last_seq` tracking. Reconnect behavior and localStorage persistence to be defined.

### Voice channel implementation

`channel='voice'` flag exists in `LLMRouter` (no retry, direct fallback per ADR-004 §C).
The LiveKit Agents pipeline (ADR-002 §B1), VAD, STT (Deepgram Nova-3), TTS (Cartesia Sonic)
are not implemented. Feature-flagged in `tenant.yaml`. Phase 2 / Phase 3.

### Celery worker isolation (real broker)

`log_usage` is tested only with `CELERY_TASK_ALWAYS_EAGER=True` (in-process execution).
Phase 2 / CI infra: add `docker-compose.test.yml` with Redis service; test worker
round-trip with `@pytest.fixture` that starts a Celery worker subprocess.

### Frontend Next.js client

STEP 5.5 deferred. Adaptive Renderer client integration, RSC streaming, Tailwind 4
components, persona-aware morph rules UI. Full scope in BIBLE §7.

### Adaptive Renderer completo

Morph rules engine, decision tree, viewport_state WebSocket sync. Phase 2.

### GitHub Actions attivazione

CI pipeline defined but not activated. Activate after Phase 1 DoD merge to `main`.

### RLS AST scan hook

Static analysis to ensure all queries on tenant-scoped tables are inside `with_tenant()`.
Pre-commit hook + CI step. Blocks Phase 1 DoD merge to `main`.

---

## ADR formal amendments pending

These decisions were made during Phase 1 implementation and documented only in commit messages.
Formal ADR updates required before Phase 1 DoD sign-off:

### ADR-005 — halfvec(3072) instead of vector(3072) for HNSW

pgvector 0.8.2 caps `vector` type HNSW at 2000 dimensions. `halfvec(3072)` supports HNSW
up to 16000 dims. RAM working set halved to ~13–18 GB/tenant (vs ~25–35 GB in ADR-005).
Impacts: §Decisione row D, §Negative consequences (RAM estimate), §Conseguenze neutre.

### ADR-005 — Shared HNSW with RLS (not per-tenant isolated index)

ADR-005 originally specified per-tenant isolated HNSW indexes. Phase 1 uses a shared index
with RLS post-filtering (per the amendment in commit `0e9ac18`).
Formal amendment must update §Decisione table and §Conseguenze to reflect the shared index
tradeoff (simpler ops, candidate over-fetch at scale).

### ADR-005 — RAM working set revised

With halfvec + shared index, the RAM estimate per tenant is significantly lower than the
original §D table. The "worst-case multi-tenant" scenario should be recalculated.

---

## Notes

- The `alembic.ini` warning `No path_separator found in configuration` is cosmetic.
  Fix: add `path_separator = os` to `[alembic]` section. Low priority.
