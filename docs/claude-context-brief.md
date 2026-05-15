\# DigIdentity Platform — Context Brief per Claude



\## Chi sono

Stefano Corda, 42, titolare web agency DigIdentity Agency, inventore della 

DigIdentity Card, autore di manuali su digital marketing locale. Cantante 

dei Revolver Sardinia. Esperto digital marketing, NON sviluppatore senior 

ma con buona comprensione tecnica e governance progettuale rigorosa.



\## Il progetto

DigIdentity Platform: backend multi-tenant SaaS per knowledge graph + 

conversational AI verticali (primo pack: real-estate-luxury). 

Repo: github.com/Bleiz82/digidentity-platform (privato).



\## Stato attuale (al 2026-05-15)

\- \*\*Phase 1 COMPLETATA\*\* — commit `2caab8d` su `main`, tag `phase-1-complete`

\- 24 commit, 106 file, \~10.300 righe

\- 58 test verdi, 4 eval set PASS, 0 issue RLS



\## Stack tecnologico

\- \*\*Backend\*\*: FastAPI + Python 3.13 (uv), SQLAlchemy 2.x async (Mapped + mapped\_column)

\- \*\*DB\*\*: PostgreSQL 16 + pgvector 0.8.2 (halfvec(3072) + HNSW)

\- \*\*Frontend\*\* (scaffold only, no logic): Next.js 14 (App Router) + TypeScript + pnpm

\- \*\*Infra\*\*: Docker Compose locale, testcontainers per test, Celery + Redis (mock)

\- \*\*LLM\*\*: mock provider in Phase 1, Anthropic API prevista in Phase 2



\## ADR fondamentali (sempre da rispettare)

\- \*\*ADR-001\*\*: Stack canonico (FastAPI + Postgres + Next.js)

\- \*\*ADR-002\*\*: Trasporto multimodale (SSE per web, voice deferred)

\- \*\*ADR-003\*\*: Tenant isolation via RLS FORCE + `with\_tenant()` async context manager

\- \*\*ADR-004\*\*: LLM router con circuit breaker per-model, retry 1x su 503/529

\- \*\*ADR-005\*\*: Multi-embedding (content/lifestyle/features 3072-dim halfvec, pesi 0.45/0.35/0.20)



\## Amendment ADR-005 da formalizzare in ADR-006 (Phase 2)

1\. `vector(3072)` → `halfvec(3072)` (pgvector HNSW limit 2000 dim)

2\. RAM 25-35 GB/tenant → 13-18 GB/tenant (halfvec dimezza)

3\. Shared HNSW con RLS confermato (non per-tenant)



\## Decisioni architetturali consolidate

\- UUID v7 via `uuid-utils` (Python), non extension Postgres

\- SQLAlchemy: classic `mapped\_column`, NO `MappedAsDataclass`

\- Testcontainers (image `pgvector/pgvector:pg16`), session-scoped

\- Table naming: plurale (`tenants`, `sessions`, `entities`, `usage\_logs`)

\- Stub embeddings deterministici (hash + signal boost dim 0-49/50-99/100-149)

\- Pack registry caricato da disco al boot (no DB in Phase 1)

\- Embedding versioning via VARCHAR `embedding\_version` (no JSONB)



\## Pattern di lavoro che FUNZIONA (mantenere in Phase 2)

\- Atomic commits con tag `\[step-N]` nel messaggio

\- Sub-agent: `engine-implementer` (sonnet) per codice, MAI per decisioni

\- Pausa su ogni decisione architetturale non coperta da ADR

\- Pre-commit: pytest verde + eval PASS + RLS check

\- Strategia "calibration first": prima si misurano i numeri reali, poi si tarano le soglie a baseline × 0.85

\- Refuse del "fake baseline" (es. anchor embedding che inflaziona NDCG)



\## File chiave da leggere se servono dettagli

\- `BIBLE-v3.md` — vision di progetto

\- `docs/phase1-followups.md` — backlog Phase 2 prioritizzato

\- `docs/adr/00X-\*.md` — ADR specifici

\- `apps/api/src/digidentity\_api/` — codice backend



\## Cosa NON è in Phase 1 (rinviato a Phase 2+)

\- Frontend Next.js logico (solo scaffold)

\- Integrazione LLM reale (solo mock)

\- Conversations/messages table

\- Long-polling fallback per SSE

\- LiveKit voice channel

\- GitHub Actions attive (workflow scritto ma dormiente)

\- Natural-language retrieval eval (stub embeddings non supportano)



\## Stato Phase 2

\- Nessuno step ancora avviato

\- Primo candidato in discussione: frontend Next.js client + SSE (step 5.5)

\- Alternative: real LLM integration | natural-language eval con sentence-transformers



\## Come voglio interagire

\- Risposte concrete, no fluff. Tono italiano, rock-friendly. Emoji solo se le uso io.

\- Decisioni architetturali: sempre pausa + 3 opzioni + raccomandazione motivata

\- Pattern: lavoro autonomo dell'engine-implementer con checkpoint, NON micro-management

\- Se Claude Code propone qualcosa fuori scope, blocca e chiedi a me



