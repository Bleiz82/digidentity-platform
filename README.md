# DigIdentity Platform

[![CI](https://github.com/Bleiz82/digidentity-platform/actions/workflows/ci.yml/badge.svg)](https://github.com/Bleiz82/digidentity-platform/actions/workflows/ci.yml)

Living Site platform: digital identity multi-tenant per brand, con knowledge graph vettoriale, rendering adattivo (Morph), edge classification (Sense) e canale voice conversazionale.

## Stato

- **Phase 0**: completata (5 ADR + 2 amendments)
- **Phase 1**: completata — vedi sotto
- **Phase 2**: kickoff in attesa — vedi `docs/phase1-followups.md`

## Phase 1 — completed (2026-05-15)

Backend MVP multi-tenant. Tag: `phase-1-complete`.

### Contenuto

- **Multi-tenant DB foundation** — RLS + `with_tenant()` context manager, asyncpg, SQLAlchemy 2.0 async. Tenant isolation verificata con stress test concorrente.
- **Knowledge Graph Engine v0** — `halfvec(3072)` HNSW (pgvector 0.8.2), HybridSearchRepository con weighted multi-vector search, RLS-isolated. ADR-005.
- **Pack system** — architettura fat-core/lean-pack, Pack `real-estate-luxury` pilot con template Jinja, stub embeddings, seed 100 entità.
- **SSE conversational backend** — endpoint `GET /conversations/{id}/stream`, LLMRouter con circuit breaker per-model (3 failure threshold, 5min cooldown), retry policy web vs voice, fallback chain Sonnet→Opus→GPT-5, Celery usage logging. ADR-004.
- **Eval framework** — 4 eval set con gate CI attivo, 58 test unit/integration verdi, runner con direction-aware threshold (lower-is-better per latency).

### Baseline metrics (calibration run `6ae91f8`)

| Eval | Metrica | Valore | Soglia gate |
|------|---------|--------|-------------|
| retrieval_real_estate | NDCG@10 | 0.532 | ≥ 0.45 |
| retrieval_real_estate | MRR | 0.525 | ≥ 0.44 |
| retrieval_real_estate | recall@10 | 0.550 | ≥ 0.46 |
| circuit_breaker | success_rate | 1.000 | ≥ 0.95 |
| router_correctness | accuracy | 1.000 | ≥ 0.95 |
| latency_sse | P50 | 84.4ms | ≤ 120ms |
| latency_sse | P95 | 185.3ms | ≤ 280ms |

### Non incluso in Phase 1

Frontend Next.js, embedding OpenAI reali, LiveKit voice, GitHub Actions attivazione.
16 item open tracciati in `docs/phase1-followups.md`.

## Documentazione

- `docs/BIBLE-v3.md` — source of truth architetturale
- `CLAUDE.md` — convenzioni progetto, auto-caricato da Claude Code
- `docs/adr/` — Architecture Decision Records (ADR-001 .. ADR-005 + 2 amendments)
- `docs/phase1-followups.md` — item aperti per Phase 2
- `docs/phase1-kickoff.md` — documento di kickoff Phase 1

## CI/CD

Pipeline GitHub Actions con 5 job paralleli (ADR-008). Ogni push a `main` esegue:

| Job | Cosa fa | Gate |
|-----|---------|------|
| `backend-test` | pytest 172+ test, Postgres 16 + pgvector service container, Alembic migrations | bloccante |
| `frontend-test` | vitest 25+ test + `next build` | bloccante |
| `lint-packs` | validazione YAML morph rules + schema DSL | bloccante |
| `eval-real-estate-luxury` | 20 golden conversation eval (mock provider) | bloccante |
| `adr-coverage` | verifica status ADR valido (no Rejected, no assente) | bloccante |

Le PR verso `main` eseguono i primi 3 job. Le ultime due gate (`eval-*` e `adr-coverage`) girano solo su push a `main`.
Configurare branch protection rules in GitHub Settings → Branches dopo il primo CI run verde.

## Stack

Python 3.13 + FastAPI · PostgreSQL 16 + pgvector · Next.js 15 + React 19 · Cloudflare Workers · LiveKit Agents

Stack canonico: `docs/adr/001-stack-canonico.md`.
