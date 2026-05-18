# ADR-007: Multi-Provider LLM and Embeddings Strategy

- **Status**: Accepted
- **Date**: 2026-05-18
- **Authors**: Stefano Corda
- **BIBLE refs**: §6.1, §6.4, §9
- **Supersedes**: n/a
- **Superseded by**: n/a
- **Extends**: ADR-004 (LLM Router), ADR-005 (Multi-Embedding), ADR-006 (halfvec amendment)

---

## Context

Phase 3 Scenario A++ (kickoff §10, decisions D-02 and D-03) requires:

1. **Multi-provider LLM routing**: Anthropic is the primary LLM provider, but the system must support OpenAI (via direct SDK) and OpenRouter (as a cost/availability fallback). ADR-004 defined the circuit-breaker routing strategy; this ADR formalises the provider list and OpenRouter opt-in policy.

2. **Real embeddings via `text-embedding-3-large`**: Phase 1–2 shipped with embedding stubs (zero vectors or mock values). BIBLE §6.1 specifies `text-embedding-3-large` (3072 dim) as the canonical embedding model; ADR-005/006 specified halfvec(3072) in the DB schema, which is already live in migration 002. Phase 3 must wire a real embedding provider. Phase 2 `kg_search` in `ToolRegistry` returns simulated entities — it must be upgraded to use a real embedding lookup.

3. **Mock back-compat**: Tests and environments without API keys must continue to work via mock providers (deterministic, no external calls).

---

## Decisions

### D-01 — LLM Provider Chain

**Primary**: Anthropic (`claude-sonnet-4-6` / `claude-opus-4-7`)  
**Fallback**: OpenAI (`gpt-4o` / `gpt-5` as available)  
**Opt-in**: OpenRouter — activated only when `OPENROUTER_API_KEY` is set AND `LLM_PROVIDER=openrouter`

Rationale: ADR-004 circuit-breaker chain already covers Anthropic → OpenAI fallback. OpenRouter is held as an opt-in to avoid adding an unneeded dependency to the default boot path. The router treats OpenRouter as a third link in the chain (after OpenAI fallback), not a replacement.

No local models (Ollama, Qwen, etc.) are in scope for Phase 3 — deliberate decision per kickoff §10 D-01.

### D-02 — Embedding Provider and Model

**Model**: `text-embedding-3-large` (3072 dimensions, float32 output, stored as halfvec per ADR-006)  
**Provider SDK**: `openai` Python SDK (`AsyncOpenAI`)  
**Active when**: `OPENAI_API_KEY` is set AND `EMBEDDING_PROVIDER=openai` (default if key present)  
**Fallback**: `MockEmbeddingProvider` — returns deterministic unit vectors of dimension 3072, active when `OPENAI_API_KEY` is absent or `EMBEDDING_PROVIDER=mock`

**Batching**: max 100 inputs per API call (OpenAI rate-limit-safe default); larger lists are split automatically.

**Retry**: exponential backoff on 429 (rate limit): 1s → 2s → 4s, max 3 retries. On 5xx: 2 retries with 1s fixed wait. Implemented via `tenacity` if available, otherwise a minimal inline loop.

**Dimensions config**: `EMBEDDING_DIMENSIONS=3072` (can be set to smaller for test environments where the mock ignores it).

### D-03 — EmbeddingRouter interface

```python
class EmbeddingRouter:
    async def embed(self, texts: list[str], model: str | None = None) -> list[list[float]]:
        """Returns one embedding vector per input text."""
```

The router is stateless and thread-safe. It selects the provider at construction time based on config. Tests instantiate the mock provider directly, bypassing the router factory, so no env patching is required.

### D-04 — ToolRegistry kg_search upgrade

`ToolRegistry.kg_search()` is upgraded from a stub that returns synthetic entities to a call through `EmbeddingRouter`. In Phase 3, without a real DB in the test environment, the method calls `EmbeddingRouter.embed([query])` to obtain the query vector, then returns a simulated result set (same as before) — the embedding call is real or mocked depending on the provider. A real DB lookup via pgvector will be wired in a future STEP when persistent KG data is available.

This approach makes the embedding path testable (router selection, batch splitting, retry) without requiring a running Postgres with RLS in CI.

### D-05 — `reembed_pack` CLI

A standalone script (`scripts/reembed_pack.py`) re-embeds all entities of a pack from the DB using the current `EmbeddingRouter`. CLI flags: `--pack`, `--dry-run`, `--batch-size`. Does not run automatically; must be invoked manually or via a scheduled pipeline. Not imported by the application at startup.

---

## Alternatives Considered

### Embedding model: `text-embedding-ada-002`

Ada-002 is 1536 dimensions (half of 3072). The DB schema already targets 3072 (ADR-006). Switching to ada-002 would require either truncating the halfvec columns (breaking ADR-006) or padding to 3072 (nonsensical). Ada-002 is also deprecated by OpenAI in favour of text-embedding-3-*. **Rejected**.

### Embedding provider: Voyage AI (`voyage-3-large`)

Voyage AI offers strong embedding quality for domain-specific text. However:
- Adds a third external dependency (OpenAI SDK is already in scope for LLM fallback)
- Introduces provider lock-in with a smaller ecosystem
- `voyage-3-large` is 1024 dimensions — incompatible with the halfvec(3072) schema without migration

**Rejected** for Phase 3. May be revisited in Phase 4 if recall quality evidence emerges.

### OpenRouter as default (not opt-in)

OpenRouter aggregates multiple providers and could replace both Anthropic and OpenAI SDKs via a single OpenAI-compatible API. Rejected as default because:
- Introduces a single-point-of-failure for all LLM calls
- OpenRouter markup (~10%) is acceptable for cost optimisation, not for primary routing
- The existing Anthropic SDK integration (streaming, tool_use parsing) would need to be replaced or wrapped

**Retained as opt-in** via `OPENROUTER_API_KEY` + `LLM_PROVIDER=openrouter`.

---

## Consequences

### Positive

- Real embedding quality from Phase 3 onwards: KG retrieval uses semantic vectors, not zero-vectors
- Mock back-compat guarantees all existing tests continue to pass without API keys
- EmbeddingRouter is provider-agnostic; switching embedding models in future requires only a new provider class
- `reembed_pack` CLI enables zero-downtime re-embedding of a pack (run offline, cutover atomically)

### Negative

- **OpenAI API key required for real embeddings**: environments without it fall back to mock silently. If misconfigured (key present but wrong), the OpenAI SDK raises `AuthenticationError` — must be surfaced at startup, not silently degraded.
- **Cost at scale**: 1M tokens/embedding call ≈ $0.130; 100K entities × 3 vectors × ~350 tokens ≈ $13.65/tenant (Batch API: ~$6.83). Not a blocker for Phase 3 prototype; matters at multi-tenant scale.
- **Batch API not used in Phase 3**: `reembed_pack` uses the synchronous embedding API (rate-limited). For large tenants, the Batch API (ADR-005 §E1) must be implemented in a future step to reduce cost and time.
- **kg_search still returns synthetic results**: the embedding vector is computed but not used for a real vector search (no live DB in test env). Full KG retrieval is deferred to the Spatial Engine STEP (P3-07).

### Neutral

- `tenacity` is not added as a new dependency in this STEP; retry is implemented inline. If retry logic grows complex, `tenacity` will be added via ADR.
- The `openai` SDK is already implicitly expected by ADR-001 (stack canonico mentions OpenAI); this ADR makes it explicit and adds it to `pyproject.toml`.

---

## Cost Estimates

| Operation | Unit cost | Phase 3 estimate |
|-----------|-----------|-----------------|
| text-embedding-3-large (synchronous API) | $0.130 / 1M tokens | ~$1-3 during prototype (few hundred entities) |
| text-embedding-3-large (Batch API, 50% discount) | $0.065 / 1M tokens | N/A in Phase 3 |
| GPT-4o (LLM fallback, input) | $2.50 / 1M tokens | Marginal (circuit breaker rarely fires) |
| claude-sonnet-4-6 (primary LLM) | $3.00 / 1M tokens | Main cost driver |

---

## Migration: mock → real embeddings

1. Set `OPENAI_API_KEY` in `.env` (never committed).
2. Set `EMBEDDING_PROVIDER=openai` (default when key is present).
3. Run `uv run python -m digidentity_api.scripts.reembed_pack --pack real-estate-luxury` for existing entities.
4. Verify HNSW index is populated: `SELECT COUNT(*) FROM entities WHERE content_emb IS NOT NULL`.
5. Smoke-test `kg_search` via the demo UI.

Rollback: set `EMBEDDING_PROVIDER=mock` — the router falls back silently, existing vectors in DB remain untouched.

---

## References

- BIBLE v3 §6.1 — Knowledge Graph Engine: multi-embedding, HNSW, hybrid search
- BIBLE v3 §6.4 — Agent Orchestrator: LLM routing, tool calling
- BIBLE v3 §9 — Canonical stack: OpenAI SDK, Anthropic SDK, pgvector
- ADR-004 — LLM Router circuit-breaker strategy
- ADR-005 — Multi-Embedding Strategy (features_emb, hybrid scoring)
- ADR-006 — pgvector halfvec(3072) amendment
- Phase 3 kickoff §10 — Architectural decisions D-02 (multi-provider), D-03 (text-embedding-3-large)
- OpenAI Embeddings documentation — text-embedding-3-large, pricing, rate limits
