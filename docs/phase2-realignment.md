> **✅ COMPLETED 2026-05-18 — see [docs/phase2-complete.md](phase2-complete.md)**

# Phase 2 — Riallineamento alla BIBLE-v3

**Data**: 2026-05-15
**Trigger**: revisione post-STEP 7b.4 (commit c1909db)
**Metodo**: rilettura source-of-truth (BIBLE-v3 §1-6) e mapping vs codice attuale.

---

## 1. Cosa dice la BIBLE per Phase 2

La BIBLE §0 (ultimo capoverso) chiarisce il principio ordinatore: *"la roadmap è riordinata
per priorità di valore percepito dal cliente, non per ordine logico-tecnico"*. Le Phase non
sono fasi di maturità tecnica — sono milestone commerciali.

### Engine nel sistema: ordine di priorità (BIBLE §4)

| # | Engine | Priorità strategica | Perché |
|---|---|---|---|
| 2 | **Adaptive Renderer** | **Massima — core IP** | *"È l'engine più importante del sistema. Senza di lui, DigIdentity è un chatbot."* (§4) |
| 4 | Agent Orchestrator | Alta | Esegue il loop, emette tool calls e scoring signals |
| 1 | Knowledge Graph | Alta | Fondamento dati — parzialmente fatto |
| 3 | Conversational Renderer | Media | SSE transport — parzialmente fatto |
| 5 | Spatial Experience | Media-bassa | Phase 1 per Inhabit, ma non urgente per commerciale Phase 2 |
| 6 | Static Manifestation | Media-bassa | SEO/GEO — Phase 3 BIBLE |
| 7 | Learning Engine | Bassa | Phase 4 BIBLE, richiede dataset |

### Cosa prevede la BIBLE per ciascuna Phase (§12)

**BIBLE Phase 1** ("Primo Morph visibile + Inhabit base", settimane 2-5):
- Adaptive Renderer v1: Edge Sense + Decision Engine + RSC morph + 3 morph rules concrete (§6.2)
- Pack `real-estate-luxury` v0.1: 3 personas, 3 morph rules homepage, 1 morph rule property detail (§5)
- **Frontend Next.js 15 con chat SSE consumer** ← classificato Phase 1, non Phase 2
- Spatial v1: Marzipano viewer + 1 property con tour 360° reale (§6.5)
- LLMRouter con fallback OpenAI (§6.4, ADR-004)
- Tenant isolation stress test in CI (ADR-003)
- Eval framework attivo con 20 conversation golden (§11)

**BIBLE Phase 2** ("Qualify + Hand-off", settimane 6-9):
- Lead scoring engine rule-based v1 (§2.5, §7.3 LeadScore)
- Tool catalog completo del core (§6.4: kg.search, kg.fetch, render.morph_section, lead.update_score, lead.trigger_handoff, ecc.)
- Briefing generator: PDF + Markdown + JSON via tenant integrations (§2.6)
- Integrazioni: email SMTP/SES, Slack, Telegram, generic webhook (§2.6)
- Pack `real-estate-luxury` v0.2 con scoring scorecard luxury-italiano (§5)
- Compliance baseline: GDPR, DSAR endpoint, retention policies, cookie banner (§10.6)

**BIBLE Phase 3** ("Remember + voice + GEO", settimane 10-15):
- Visitor sessions persistence + return visitor recognition (§2.7)
- LiveKit Agents integration (ADR-002 §B1)
- Static Manifestation Engine v1: Astro + JSON-LD + /llm.txt (§6.6, §13)
- Cloudflare Pages + Workers in production

**BIBLE Phase 4+**: Learning Engine, secondo verticale, ML personalization.

### Nota critica di riallineamento

Ciò che il progetto chiama "Phase 1 completata" copre solo una parte della BIBLE Phase 1:
backend KG + SSE + LLMRouter + tenant isolation. La BIBLE Phase 1 include anche **Adaptive
Renderer v1**, **frontend con SSE consumer**, e **Spatial v1** — nessuno dei quali era presente
nel tag `phase-1-complete`. Di conseguenza i commit STEP 7a/7b completano lavoro di BIBLE Phase 1
anziché aprire BIBLE Phase 2.

---

## 2. Stato attuale del codice (mappato sui 7 engine)

| Engine | Stato | Evidenze nel codice (file/path) | Commit di riferimento |
|---|---|---|---|
| **Knowledge Graph Engine** | 🟡 partial | `db/models.py` (entities con halfvec 3072), `db/repositories.py`, `db/search.py` (HybridSearchRepository), `packs/real-estate-luxury/` (pack.yaml, personas.yaml, templates), migration `002_entities_hnsw.py` | Phase 1 — `469532a`, `2caab8d` |
| **Adaptive Renderer** | ❌ missing | Nessun Decision Engine. Nessun DSL evaluator. Nessun Edge Sense (nessun file in `infra/workers/` o equivalente). `morph_rules/homepage.yaml` esiste nel pack ma non c'è codice che lo valuta. | — |
| **Conversational Renderer** | 🟡 partial | `api/conversations.py` (SSE endpoint), `engines/llm_router.py` (circuit breaker per-model), `engines/mock_provider.py`. Frontend: `lib/sse-client.ts`, `lib/use-conversation-stream.ts`, `components/ConversationUI.tsx`. Mancano: WebSocket patches endpoint, type discriminator `"directive"/"directive_batch"` (ADR-002 §A), long-polling fallback (ADR-002 §A3). | Phase 1 backend + Phase 2 frontend |
| **Agent Orchestrator** | ❌ missing | `llm_router.py` implementa il routing/circuit breaker ma usa `mock_provider.py` — zero tool calling, zero scoring signals, zero rendering directives emesse. Nessun agent loop. | — |
| **Spatial Experience Engine** | ❌ missing | Nessun file Three.js/Marzipano/R3F. `ADR-001` cita React Three Fiber come stack canonico ma nessun codice presente. | — |
| **Static Manifestation Engine** | ❌ missing | Nessun build pipeline Astro. Nessun JSON-LD generator. Nessun `/llm.txt`. | — |
| **Learning Engine** | ❌ missing | Nessun job Celery notturno. Nessuna tabella `learning_metrics_daily`. `tasks/usage.py` (Celery log_usage) è il solo task presente — è cost tracking, non Learning Engine. | — |

**Modelli dati v3 (§7):**
- `VisitorPrior` → ❌ nessuna tabella `visitor_sessions`, nessun schema Pydantic
- `RenderingDirectives` → ❌ non presente
- `LeadScore` → ❌ nessuna tabella `leads`, nessun schema
- `conversations` table → ❌ `conversation_id` è UUID opaco non persistito (aperto in `phase1-followups.md`)
- `conversation_turns` con `user_intent`, `quality_score`, `tool_calls_json` → ❌ non presente

**Pack `real-estate-luxury` (§5):**
- `pack.yaml`, `personas.yaml` → ✅ presente
- `morph_rules/homepage.yaml` → 🟡 file YAML presente, ma: nessun validatore JSON Schema, nessun evaluator che lo legge
- `ontology/`, `prompts/`, `components/`, `tools/`, `scoring/`, `golden_dataset/` → ❌ tutti assenti (struttura canonica BIBLE §5 non rispettata)

---

## 3. Commit Phase 2 — classificazione

Lista commit da `phase-1-complete` a HEAD:

| Hash | Message | Classificazione | Note |
|---|---|---|---|
| `af30065` | docs: add context brief for new Claude chat sessions | **INFRASTRUTTURALE** | Utile per sessioni future, non avanza engine |
| `2caab8d` | chore: ignore local Claude settings and eval run artifacts | **INFRASTRUTTURALE** | `.gitignore` maintenance |
| `7319223` | docs(adr): add ADR-006 formalizing pgvector halfvec amendments | **ALLINEATO** | Formalizza BIBLE §6.1 KG Engine, è ADR necessario |
| `b990199` | feat(phase2): web scaffold + SSE client foundations [step-7a] | **FUORI SEQUENZA** | Avanza Conversational Renderer (BIBLE §6.3), ma è BIBLE Phase 1 scope, non Phase 2 |
| `1d799c9` | feat(phase2): conversational UI + streaming hook [step-7b] | **FUORI SEQUENZA** | Idem — BIBLE Phase 1, completamento step 5.5 deferito |
| `923b285` | feat(phase2): backend accepts tenant_id via query string [step-7b.1] | **INFRASTRUTTURALE** | Bridge fix necessario per EventSource browser API (BIBLE §6.3 vincolo tecnico) |
| `c5b90de` | fix(phase2): enable CORS + frontend direct backend calls [step-7b.2] | **INFRASTRUTTURALE** | Fix dev environment, non avanza engine |
| `2d61296` | fix(phase2): align frontend SSE schema to real backend contract [step-7b.3] | **INFRASTRUTTURALE** | Bug fix allineamento contratto SSE |
| `c1909db` | fix(phase2): make SSE timestamp field optional [step-7b.4] | **INFRASTRUTTURALE** | Bug fix schema Zod |

**Sintesi**: 1 commit ALLINEATO (ADR-006), 2 FUORI SEQUENZA (completano BIBLE Phase 1), 6 INFRASTRUTTURALI.
Nessun commit avanza gli engine core mancanti: Adaptive Renderer, Agent Orchestrator, LeadScore.

---

## 4. Gap analysis: cosa manca per essere allineati alla BIBLE Phase 2

Per poter lavorare su BIBLE Phase 2 (Qualify + Hand-off) occorre prima completare i prerequisiti
di BIBLE Phase 1 non ancora implementati, poi costruire i deliverable Phase 2 propri.

### Prerequisiti BIBLE Phase 1 ancora mancanti

- **Adaptive Renderer Decision Engine** (BIBLE §6.2): nessun rule engine, nessun evaluator DSL, nessun Edge Sense su Cloudflare Workers. Senza di lui "DigIdentity è un chatbot" (BIBLE §4).
- **DSL morph rules YAML parser** (BIBLE §8): `homepage.yaml` esiste ma nessun codice lo valuta. Serve il parser + validatore JSON Schema in `core/dsl/morph_rule.schema.json` + evaluator TypeScript/Python.
- **Visitor Sense rule-based v0** (BIBLE §2.1): classificazione visitatore deterministica da UTM/referrer/device. Cloudflare Workers non configurato. Nessun `VisitorPrior` prodotto.
- **Tabella `conversations` persistita** (BIBLE §6.1, §6.4, `phase1-followups.md`): `conversation_id` è oggi UUID opaco. La BIBLE §6.4 richiede persistenza con `idempotency_key` per retry sicuri.
- **Modelli dati `VisitorPrior` e `visitor_sessions`** (BIBLE §7.1): tabella DB + schema Pydantic v2. Prerequisito per Sense e per Morph.
- **Modello `RenderingDirectives`** (BIBLE §7.2): prerequisito per il Decision Engine e per il canale SSE con type `"directive"`.
- **Real LLM integration** (ADR-004, `phase1-followups.md`): mock provider attuale non supporta tool calling. L'Agent Orchestrator reale — e quindi tutto il Qualify — richiede Anthropic SDK con streaming + function calls.
- **Pack `real-estate-luxury` struttura canonica completa** (BIBLE §5): mancano `ontology/`, `prompts/`, `components/`, `tools/`, `scoring/`, `golden_dataset/` con almeno 20 conversation golden (§11, §12 Phase 1 target).
- **Eval framework conversazionale** (BIBLE §11): eval attivi misurano retrieval, latency, circuit breaker — non qualità conversazionale. Nessun golden dataset conversazionale.

### Deliverable propri di BIBLE Phase 2

- **Lead scoring rule-based v1** (BIBLE §2.5): tabella `leads`, schema `LeadScore` (§7.3), scorecard YAML nel Pack, scoring incrementale asincrono.
- **Tool catalog completo del core** (BIBLE §6.4): `kg.search`, `kg.fetch`, `kg.fetch_memory`, `render.morph_section`, `render.highlight`, `render.inject_component`, `lead.update_score`, `lead.trigger_handoff`, `comm.schedule_callback`.
- **Briefing generator** (BIBLE §2.6): PDF + Markdown + JSON, triggered da `LeadScore ≥ soglia hot`.
- **Integration layer** (BIBLE §2.6): email SMTP/SES, Slack, Telegram, generic webhook — configurabili via `tenant.yaml`.
- **GDPR baseline** (BIBLE §10.6): DSAR endpoint, retention policies, cookie banner minimalista.
- **Modello `LeadScore`** (BIBLE §7.3): tabella `leads`, schema Pydantic, aggiornamento asincrono.
- **`conversation_turns` enhancements** (BIBLE §7.4): campi `user_intent`, `quality_score`, `tool_calls_json`, `tool_call_success_overall`, `rendering_directives_emitted`.

---

## 5. Open question architetturali da risolvere PRIMA di scrivere codice Phase 2

**Q1 — "DigIdentity Card" vs "Living Site": quale prodotto stiamo costruendo?**

Il `docs/claude-context-brief.md` descrive Stefano come "inventore della DigIdentity Card".
La BIBLE-v3 non menziona mai "DigIdentity Card" — il prodotto è il "Living Site", definito come
*"un sito web abitabile"* (§1). Non è chiaro se la Card sia un prodotto separato, un nome precedente
del Living Site, o un concept superato dalla v3. Se la Card ha un'architettura o un contratto di
prodotto diverso dal Living Site, potrebbe richiedere un ADR-007 dedicato. Se è solo un naming
alternativo, la BIBLE è sufficiente. BIBLE non specifica.

**Q2 — Il frontend attuale (STEP 7a/7b) è riusabile come scaffold per Adaptive Renderer client?**

BIBLE §6.2 definisce il Client Layer come: *"React 19 che riceve stream di patches (RFC 6902 JSON
Patch) per il DOM via WebSocket dall'agente durante Converse/Inhabit, applica trasformazioni
atomiche."* Il frontend attuale ha:
- ✅ Next.js 15 + React 19 + TypeScript strict (stack corretto)
- ✅ SSE client funzionante con Zod validation (base per Conversational Renderer)
- ❌ Nessun WebSocket consumer per JSON Patch (ADR-002 §C1) — il Client Layer BIBLE manca
- ❌ Nessun RSC morph (Server Layer BIBLE §6.2) — la pagina è client-only, nessun RSC personalizzato per VisitorPrior
- ❌ `ConversationUI` è hardcoded, non VisitorPrior-aware

Il giudizio: lo scaffold è **riusabile come punto di partenza** (stack corretto, SSE client pronto,
struttura App Router) ma richiede estensioni significative per diventare il Client Layer BIBLE.
Non va riscritto, va esteso. Decisione formale non richiede ADR.

**Q3 — Mock LLM provider vs Anthropic Sonnet 4.6 reale: quando si integra?**

ADR-004 specifica Claude Sonnet 4.6 come primary, GPT-5 come fallback. Il `context-brief.md`
dice "Anthropic API prevista in Phase 2". Attualmente `mock_provider.py` restituisce testo
deterministico senza tool calling. L'Agent Orchestrator reale (BIBLE §6.4) — e quindi tutto il
Qualify — dipende da tool calling funzionante. Domanda aperta: si integra il provider reale
come primo step di Phase 2 (prima del Decision Engine), o dopo aver completato l'Adaptive
Renderer v1? La sequenza impatta la demo: un Adaptive Renderer con mock LLM non fa Converse reale.
BIBLE non specifica la sub-sequenza interna a Phase 1/2.

**Q4 — ADR-007/008/009/010: infrastructure decisions ancora aperte**

BIBLE §14 lista quattro decisioni da chiudere in Phase 0-1 con ADR:
- ADR-007: Cloud production (Fly.io vs AWS vs Hetzner)
- ADR-008: Postgres production (Neon vs Supabase vs RDS)
- ADR-009: Voice provider production (LiveKit Cloud vs self-hosted)
- ADR-010: Annotation tool

Nessuno di questi è stato scritto. Il progetto sta sviluppando su Docker Compose locale.
Prima di qualsiasi deploy in staging (necessario per la demo BIBLE Phase 1), queste
decisioni bloccano. BIBLE §14: *"Decisioni da prendere in Phase 0-1"*. Sono in ritardo.

**Q5 — Morph DSL: il `homepage.yaml` attuale è conforme allo schema BIBLE §8?**

BIBLE §8 specifica: *"Schema JSON Schema in `core/dsl/morph_rule.schema.json`"* e validazione
obbligatoria in CI. Il file `packs/real-estate-luxury/morph_rules/homepage.yaml` esiste ma:
nessun `core/dsl/` esiste nel repo, nessun JSON Schema, nessun lint-pack tool. Non è chiaro se il
YAML attuale rispetti lo schema BIBLE §8 (struttura `version`, `target_page`, `rules[]`, `fallback`).
Questa ambiguità blocca il Decision Engine perché non c'è contratto formale da implementare.

**Q6 — `conversations` table e `idempotency_key`: schema minimo necessario per Phase 2**

BIBLE §6.4 dice: *"Conversazione + turno utente vengono salvati in un'unica transazione atomica
con `idempotency_key`"*. BIBLE §6.1 lista le tabelle base: `conversations`, `conversation_turns`
con i nuovi campi v3 (§7.4). La tabella non esiste. Qualsiasi lavoro sul Qualify o sul Handoff
richiede queste tabelle. Questo è un prerequisito di migrazione DB che richiede Alembic
migration n. 003. BIBLE non specifica il timing esatto — va definito.

---

## 6. Proposta di riordino STEP Phase 2 (allineata BIBLE)

I seguenti STEP sono derivati direttamente da BIBLE §2, §6, §7, §8, §12. Niente inventato.
Ogni STEP produce un deliverable verificabile che avanza un engine della BIBLE.

**STEP 8 — Completamento prerequisiti BIBLE Phase 1 (2-3 settimane)**

Prerequisiti non negoziabili per qualsiasi Phase 2 BIBLE work. Da completare prima di tutto.

- **STEP 8a**: Schema DB v3 completo — migration Alembic 003 con `conversations`,
  `conversation_turns` (con campi §7.4), `visitor_sessions` (VisitorPrior), `leads` (LeadScore).
  Refs: BIBLE §6.1, §7.1, §7.3, §7.4. Dipendenze: nessuna.

- **STEP 8b**: Pydantic models v3 — `VisitorPrior`, `RenderingDirective`, `LeadScore` da BIBLE §7.
  Refs: BIBLE §7.1-7.3. Dipendenze: STEP 8a.

- **STEP 8c**: DSL morph rules — JSON Schema in `core/dsl/morph_rule.schema.json`, validatore,
  lint-pack tool. Valida il `homepage.yaml` esistente contro lo schema. Refs: BIBLE §8.
  Dipendenze: nessuna (parallelo a 8a).

- **STEP 8d**: Pack `real-estate-luxury` struttura canonica completa — cartelle mancanti
  (`ontology/`, `prompts/`, `tools/`, `scoring/`, `golden_dataset/`), almeno 20 conversation
  golden in JSONL, scoring scorecard YAML. Refs: BIBLE §5, §11, §12 Phase 1.
  Dipendenze: STEP 8c.

**STEP 9 — Adaptive Renderer v1 — Decision Engine (3-4 settimane)**

Core IP del progetto. Senza questo, DigIdentity è un chatbot (BIBLE §4).

- **STEP 9a**: Decision Engine backend (Python) — rule engine pure-functional che valuta
  `morph_rules/*.yaml` su input `VisitorPrior + PackConfig + TenantConfig`, produce lista
  `RenderingDirective`. Ogni decisione loggata in `events`. Refs: BIBLE §6.2, §8.
  Dipendenze: STEP 8b, 8c.

- **STEP 9b**: RSC morph server-side (Next.js) — Server Components che consumano `VisitorPrior`
  (via cookie/edge header) e applicano `RenderingDirective` al component tree. Almeno 1 morph
  rule funzionante su homepage real-estate-luxury. Refs: BIBLE §6.2 (Server Layer), §2.2.
  Dipendenze: STEP 9a.

- **STEP 9c**: Visitor Sense v0 rule-based — classificazione deterministica da UTM/referrer/
  device in Next.js middleware (edge-compatible, prima di un vero Worker). Produce `VisitorPrior`
  minimal. Refs: BIBLE §2.1, §6.2 (Edge Layer). Nota: Cloudflare Workers deployment è deferred
  (ADR-007 non ancora deciso). Dipendenze: STEP 8b.

- **STEP 9d**: Client Layer JSON Patch WebSocket — consumer WebSocket in React 19 che applica
  RFC 6902 JSON Patch al DOM. Endpoint `/conversations/{id}/patches` sul backend.
  Refs: BIBLE §6.2 (Client Layer), ADR-002 §C1. Dipendenze: STEP 9b.

- **STEP 9e**: Snapshot test morph rules — dato (Page, VisitorPrior fixtures, PackConfig),
  rendering risultante confrontato a golden snapshot. Refs: BIBLE §10.3. Dipendenze: STEP 9a-9b.

**STEP 10 — Real LLM + Agent Orchestrator v1 (2-3 settimane)**

Prerequisito per Converse reale, per tool calling, per Qualify.

- **STEP 10a**: Anthropic SDK integration — sostituisce `mock_provider.py` con chiamata reale
  a `claude-sonnet-4-6`. Streaming + tool calling. Refs: BIBLE §6.4, ADR-004.
  Dipendenze: STEP 8a (conversations table per persistenza turni atomica).

- **STEP 10b**: Tool catalog core v1 — implementa `kg.search`, `kg.fetch`, `render.morph_section`,
  `render.highlight`. Refs: BIBLE §6.4 (Tool catalog del core). Dipendenze: STEP 10a, 9a.

- **STEP 10c**: Agent loop multi-turn con tool calling — stream del ragionamento, parse tool calls,
  esecuzione tool, re-prompt. Latenza target TTFC ≤ 800ms. Refs: BIBLE §6.4.
  Dipendenze: STEP 10a-10b.

**STEP 11 — Qualify Engine (Lead Scoring) — BIBLE Phase 2 vero (2 settimane)**

Primo step genuinamente di BIBLE Phase 2.

- **STEP 11a**: Lead scoring rule-based v1 — scorecard YAML nel Pack, scoring incrementale
  da segnali agente. Tabella `leads` con `LeadScore` (§7.3). Refs: BIBLE §2.5, §7.3, §12 Phase 2.
  Dipendenze: STEP 10c.

- **STEP 11b**: Tool `lead.update_score` e `lead.trigger_handoff` — agente emette segnali
  durante conversazione. Refs: BIBLE §6.4 (Tool catalog), §2.5. Dipendenze: STEP 11a, 10b.

**STEP 12 — Hand-off Engine — BIBLE Phase 2 (2 settimane)**

- **STEP 12a**: Briefing generator — PDF + Markdown + JSON dal transcript annotato.
  Refs: BIBLE §2.6, §12 Phase 2. Dipendenze: STEP 11b.

- **STEP 12b**: Integration layer — email SMTP, Slack webhook, generic webhook.
  Feature flag via `tenant.yaml`. Refs: BIBLE §2.6, §6.1 (tenant integrations).
  Dipendenze: STEP 12a.

**STEP 13 — Compliance e infrastruttura Phase 2 (1 settimana)**

- GDPR baseline: DSAR endpoint, retention config per tenant, cookie banner minimal.
  Refs: BIBLE §10.6, §12 Phase 2.

---

## 7. Cosa fare del lavoro STEP 7a-7b.4 già committato

### Opzione A — Mantieni in main, riusalo come scaffold per Adaptive Renderer client

**Pro:**
- Il frontend SSE consumer è esplicitamente citato in BIBLE Phase 1: *"Frontend Next.js 15
  con chat SSE consumer"* (§12). Il lavoro fatto completa un item BIBLE Phase 1 autentico.
- Next.js 15 + React 19 è lo stack canonico BIBLE §9. La struttura App Router è la base corretta
  per i futuri RSC morph (STEP 9b).
- Il Zod schema SSE (`types/api.ts`) è allineato al contratto backend reale — va esteso
  con il type discriminator `"directive"/"directive_batch"` (ADR-002 §A) senza riscrivere.
- `sse-client.ts` e `use-conversation-stream.ts` sono test-coperti (5 test vitest verdi).

**Contro:**
- `ConversationUI.tsx` è una chat generica non VisitorPrior-aware — va estesa, non riusata as-is.
- Nessuna struttura RSC — la pagina `app/page.tsx` è un Server Component vuoto che rende
  un Client Component. Il refactor verso RSC morph richiede ristrutturazione del routing.

### Opzione B — Sposta su branch `archive/phase2-step7-frontend-scaffold`, riparti pulito

**Pro:** La historia di main resta "solo BIBLE-aligned". Nessun codice legacy a contaminare il
punto di partenza dell'Adaptive Renderer.

**Contro:** Il branch archivio è un cimitero. Il codice funzionante (SSE client, hook, test)
va comunque recuperato per STEP 9 e 10. Spreco di rework. BIBLE Phase 1 richiede il SSE consumer
— ripartire pulito significa rifare qualcosa che funziona già.

### Opzione C — Revert dei commit e rifare in ordine BIBLE

**Pro:** Massima pulizia della timeline git.

**Contro:** Distrugge 7 commit di cui 5 sono fix di bug reali (CORS, schema, timestamp). Il codice
funzionante viene eliminato per motivi estetici. Non c'è nessun beneficio architetturale: il
problema non era che il frontend esiste, ma che mancano gli engine core.

### Raccomandazione: Opzione A

Basata esclusivamente sulla BIBLE:

1. La BIBLE Phase 1 include esplicitamente *"Frontend Next.js 15 con chat SSE consumer"* (§12).
   Il lavoro è BIBLE-legittimo, solo fuori sequenza nella nomenclatura del progetto.

2. Il Next.js 15 scaffold è il Client Layer BIBLE (§6.2) — va esteso verso RSC morph e
   WebSocket patches, non sostituito.

3. Il problema reale non è che il frontend esiste: è che l'Adaptive Renderer (Decision Engine,
   DSL evaluator, RSC morph) non esiste. La priorità è costruire quello — sopra il scaffold attuale.

4. Rimuovere il lavoro funzionante rallenta senza migliorare l'allineamento architetturale.

**Azione suggerita:** aggiornare `README.md` e i documenti di tracking per riclassificare
STEP 7a/7b come "completamento BIBLE Phase 1 step 5.5" anziché "primo deliverable Phase 2",
mantenendo i commit in main. Poi procedere con STEP 8 (prerequisiti) → STEP 9 (Adaptive
Renderer) come da §6 di questo documento.
