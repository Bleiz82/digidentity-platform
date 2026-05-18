# DigIdentity Living Site — Context Brief per Claude

## REGOLA #0 — LETTURA SOURCE-OF-TRUTH OBBLIGATORIA

All'inizio di ogni nuova sessione Claude Code o Claude chat importante, PRIMA di
proporre qualsiasi azione, leggere nell'ordine:

1. `BIBLE-v3.md` (integralmente o sezioni rilevanti)
2. `docs/phase2-realignment.md`
3. `docs/phase1-followups.md`
4. Ultimo commit con `git log --oneline -5`

Poi riassumere in 5 righe cosa si è capito e ATTENDERE conferma umana prima di
agire. Mai ricostruire il contesto a memoria.

---

## Chi sono

Stefano Corda, 42, titolare web agency DigIdentity Agency, autore di manuali su
digital marketing locale. Cantante dei Revolver Sardinia. Esperto digital
marketing, NON sviluppatore senior ma con buona comprensione tecnica e governance
progettuale rigorosa.

**Nota di scope:** "DigIdentity Card" è un progetto SEPARATO di Stefano, NON
parte di questo repository. Questo repository implementa esclusivamente il
prodotto Living Site (BIBLE-v3). Non confondere i due progetti.

---

## Il progetto

**DigIdentity Living Site** — piattaforma SaaS multi-tenant per la creazione di
"siti web abitabili". Il prodotto NON è un sito con chatbot aggiunto: è un
agente AI che si manifesta come sito, riconosce il visitatore (Sense), trasforma
il layout per ciascuno (Morph), dialoga (Converse), accompagna in spazi immersivi
(Inhabit), qualifica i prospect (Qualify) e li consegna al sales (Hand-off).

Target verticali: immobiliare luxury, cliniche dentali e estetiche premium,
hospitality di nicchia, atelier di lusso, studi professionali specialistici.
Pack pilota: `real-estate-luxury`.

Repo: github.com/Bleiz82/digidentity-platform (privato).

---

## Otto stati dell'esperienza visitatore (BIBLE-v3 §2)

| Stato | Cosa fa |
|-------|---------|
| **Sense** | Il sito riconosce il visitatore prima che parli (UTM, device, geo, fingerprint) |
| **Morph** | Il sito si trasforma in base alla persona inferita (stesso URL, layout diverso) |
| **Converse** | Il sito dialoga — agente multi-turno con tool calling verso il KG e verso il DOM |
| **Inhabit** | Il visitatore abita uno spazio immersivo (tour 3D, 360°) sincronizzato con l'agente |
| **Qualify** | Il sito qualifica il prospect (lead scoring incrementale, soglie cold/warm/hot) |
| **Hand-off** | Il sito consegna il lead hot al sales con briefing completo |
| **Remember** | Il sito ricorda il visitatore di ritorno e riprende da dove si era fermato |
| **Learn** | Il sistema impara da ogni interazione e migliora le regole morph e i prompt |

---

## Architettura: i sette engine (BIBLE-v3 §4)

| # | Engine | Ruolo |
|---|--------|-------|
| 1 | Knowledge Graph Engine | Persistenza e retrieval multi-tenant (entità, embeddings, relazioni, memoria) |
| 2 | **Adaptive Renderer** ← core IP | Decision Engine: morph rules statiche + directives dinamiche dall'agente |
| 3 | Conversational Renderer | Trasporto stream: SSE per testo, WebRTC/LiveKit per voce |
| 4 | Agent Orchestrator | Loop agente: ragionamento, tool calling, scoring incrementale, fallback modelli |
| 5 | Spatial Experience Engine | Tour 3D, gallerie 360°, modelli volumetrici sincronizzati con l'agente |
| 6 | Static Manifestation Engine | Pre-render varianti morph per SEO + `/llm.txt` per GEO |
| 7 | Learning Engine | Pipeline notturna: metriche, pattern, suggerimenti prompt e morph rules |

**Inversione fondante (BIBLE-v3 §3):** il sito non è l'interfaccia dell'agente —
il sito è uno strumento che l'agente usa. L'agente chiama tool (`morph_section`,
`highlight_property`, `inject_component`, `trigger_handoff`) che modificano il
DOM in tempo reale via SSE.

---

## Stack tecnologico

- **Backend**: FastAPI + Python 3.13 (uv), SQLAlchemy 2.x async (Mapped + mapped_column)
- **DB**: PostgreSQL 16 + pgvector 0.8.2 (halfvec(3072) + HNSW)
- **Frontend**: Next.js 15 (App Router) + React 19 RSC + TypeScript + pnpm
- **Infra**: Docker Compose locale, testcontainers per test, Celery + Redis
- **LLM**: Anthropic Claude Sonnet 4.6/4.7 primario, fallback GPT-5 via router

---

## ADR fondamentali

- **ADR-001**: Stack canonico (FastAPI + Postgres + Next.js)
- **ADR-002**: Trasporto multimodale (SSE per web, voice deferred)
- **ADR-003**: Tenant isolation via RLS FORCE + `with_tenant()` async context manager
- **ADR-004**: LLM router con circuit breaker per-model, retry 1x su 503/529
- **ADR-005**: Multi-embedding (content/lifestyle/features 3072-dim halfvec, pesi 0.45/0.35/0.20)

---

## Stato attuale (al 2026-05-18)

- **Phase 1 COMPLETATA** — commit `2caab8d`, tag `phase-1-complete`
- **Phase 2 in corso** — 9 commit dopo phase-1-complete
- **Ultimo commit**: `6017824` — docs realignment (phase2-realignment.md)
- **Prossimo step**: STEP 8 — prerequisiti BIBLE Phase 1 ancora mancanti
  (dettaglio in `docs/phase2-realignment.md §6`)

---

## Decisioni architetturali consolidate

- UUID v7 via `uuid-utils` (Python), non extension Postgres
- SQLAlchemy: classic `mapped_column`, NO `MappedAsDataclass`
- Testcontainers (image `pgvector/pgvector:pg16`), session-scoped
- Table naming: plurale (`tenants`, `sessions`, `entities`, `usage_logs`)
- Stub embeddings deterministici (hash + signal boost dim 0-49/50-99/100-149)
- Pack registry caricato da disco al boot (no DB in Phase 1)
- Embedding versioning via VARCHAR `embedding_version` (no JSONB)
- `vector(3072)` → `halfvec(3072)` (pgvector HNSW limit 2000 dim, RAM dimezzata)

---

## Pattern di lavoro che FUNZIONA

- Atomic commits con tag `[step-N]` nel messaggio
- Sub-agent: `engine-implementer` (sonnet) per codice, MAI per decisioni architetturali
- Pausa su ogni decisione architetturale non coperta da ADR
- Pre-commit: pytest verde + eval PASS + RLS check
- Strategia "calibration first": si misurano i numeri reali, poi si tarano le
  soglie a baseline × 0.85
- Refuse del "fake baseline" (es. anchor embedding che inflaziona NDCG)

---

## Come voglio interagire

- Risposte concrete, no fluff. Tono italiano, rock-friendly. Emoji solo se le uso io.
- Decisioni architetturali: sempre pausa + 3 opzioni + raccomandazione motivata
- Pattern: lavoro autonomo dell'engine-implementer con checkpoint, NON micro-management
- Se Claude Code propone qualcosa fuori scope, blocca e chiedi a me

---

## File chiave da leggere se servono dettagli

- `BIBLE-v3.md` — source of truth assoluta
- `docs/phase2-realignment.md` — open questions + prossimi step
- `docs/phase1-followups.md` — backlog Phase 2 prioritizzato
- `docs/adr/00X-*.md` — ADR specifici
- `apps/api/src/digidentity_api/` — codice backend
