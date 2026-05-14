# Phase 1 Kickoff — Core Engine Skeleton

**Status**: ready to start
**Predecessor**: Phase 0 completed (5 ADR + 2 amendments)
**Estimated duration**: 2-3 settimane di lavoro (calendar time)

---

## Obiettivo Phase 1

Validare le scelte architetturali degli ADR 001-005 con la prima implementazione verticale end-to-end:

1. **Pack pilota**: `real-estate-luxury` — dominio scelto per ricchezza di feature strutturate + componente lifestyle forte, ideale per testare la multi-embedding strategy di ADR-005.

2. **Engine minimi richiesti**:
   - Knowledge Graph Engine (ingestion, embedding, HNSW search) — ADR-005
   - Conversational Renderer (SSE streaming) — ADR-002
   - Agent Orchestrator (LLM Router base, no fallback ancora) — ADR-004
   - Tenant Isolation infra (with_tenant, RLS policies) — ADR-003
   - Stack base (FastAPI + PostgreSQL+pgvector + Next.js scaffold) — ADR-001

3. **Definition of Done Phase 1**:
   - Test CI tenant isolation: 50 req concorrenti su 5 tenant, zero leak. (ADR-003)
   - Ingestion di 100 entità immobiliari di test con 3 embedding ciascuna, recall@10 > 0.85 su query set etichettato manualmente.
   - Una conversazione end-to-end via SSE da Next.js a FastAPI con risposta LLM streaming (no voice ancora).
   - Hook RLS AST scan passa in CI.
   - Almeno 3 ADR promossi da "proposed" ad "accepted" (quelli validati dall'implementazione).

---

## Prompt di apertura per Claude Code

Da incollare in nuova sessione Claude Code dopo `claude code .`:

> Riprendiamo dal kickoff Phase 1. Leggi docs/phase1-kickoff.md integralmente, poi BIBLE-v3.md (in particolare la roadmap Phase 1 se documentata), poi i 5 ADR in docs/adr/.
>
> Riassumi in 10 righe: cosa costruiamo in Phase 1, in quale ordine di dipendenza tra gli engine, quale è il primo concreto deliverable tecnico (scaffold? schema DB? endpoint health?).
>
> Fermati. Aspetta mia approvazione del piano prima di scrivere qualsiasi codice.

---

## Sequenza di lavoro suggerita

1. **Setup ambiente dev** (1-2 giorni)
   - docker-compose con PostgreSQL 16 + pgvector + Redis
   - poetry/uv setup per FastAPI
   - pnpm setup per Next.js 15
   - .env.example e Doppler config

2. **DB foundation** (2-3 giorni)
   - Prima migration Alembic: schema tenant, sessioni, usage_logs
   - RLS policies su tabelle tenant-owned
   - Implementazione `with_tenant()` context manager
   - Test isolamento concorrente (ADR-003)

3. **Knowledge Graph Engine v0** (3-4 giorni)
   - Schema entità con 3 colonne vettoriali (3072 dim)
   - Ingestion script via OpenAI Batch API
   - Indici HNSW per-tenant (ADR-005 amendment)
   - HybridSearchRepository (somma pesata B1)

4. **Pack real-estate-luxury** (2-3 giorni)
   - pack.yaml con weights override
   - Template Jinja per features_emb
   - Dataset seed: 100 immobili di test

5. **Conversational Renderer** (3-4 giorni)
   - Endpoint SSE FastAPI con header Cloudflare-safe (ADR-002)
   - LLMRouter v0 (solo Sonnet, no fallback)
   - Client Next.js con fetch streaming

6. **Eval set + validazione** (2 giorni)
   - 50 query etichettate per recall test
   - Test CI gate

---

## Subagent da usare

- **engine-implementer** (sonnet) — la maggior parte del lavoro
- **pack-builder** (sonnet) — solo per il Pack real-estate-luxury
- **architect** (opus) — solo se emergono decisioni architetturali non coperte dagli ADR
- **eval-runner** (haiku) — per la validazione recall finale

---

## Quando fermarsi e tornare in chat con Claude (non Claude Code)

Consultami nuovamente quando:
- Una decisione di design richiede un nuovo ADR
- Un test CI fallisce in modo non ovvio
- Vuoi un sanity check pre-merge su un PR significativo
- Hai dubbi sulla promozione ADR proposed → accepted

Niente check-in ad ogni step — engine-implementer è abbastanza autonomo per il lavoro implementativo standard.

---

## Tensioni note da ADR Phase 0 (da monitorare durante Phase 1)

- **ADR-003 OQ#1**: scalabilità connessioni asyncpg oltre 300-500 concorrenti. Da strumentare con metriche pool saturation in Prometheus fin dal Sprint 1.
- **ADR-005 OQ#3 (era OQ#3 dopo rinumerazione)**: frequenza ricalibrazione pesi C2 con cross-encoder offline. Affrontabile solo dopo aver raccolto dati reali di ranking, quindi non bloccante per Phase 1.
