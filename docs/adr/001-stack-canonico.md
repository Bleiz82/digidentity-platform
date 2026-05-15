# ADR-001: stack-canonico-digidentity-living-site

- **Status**: proposed
- **Date**: 2026-05-14
- **Authors**: Stefano Corda
- **BIBLE refs**: §9, §6.1, §6.2
- **Supersedes**: n/a
- **Superseded by**: n/a

---

## Contesto

DigIdentity Living Site è un sistema multi-tenant che espone una "digital identity" interattiva e adattiva per brand e aziende. Il prodotto combina:

- un **knowledge graph vettoriale** per ogni tenant (prodotti, brand values, tono di voce)
- un **rendering adattivo** (Morph) che trasforma contenuti in componenti React in tempo reale
- un **layer edge** (Sense) che classifica il visitatore anonimo prima del rendering
- esperienze **spatial** (3D, 360°) opzionali per tenant premium
- un canale **voice** per conversazioni vocali in-page

Questo ADR ratifica le scelte tecnologiche documentate nella BIBLE v3 §9. Non è una decisione da prendere: è documentazione delle ragioni per cui le scelte già fatte sono state fatte, in modo che chiunque lavori al progetto tra 12-24 mesi possa capire il ragionamento senza dover interrogare nessuno.

Le scelte sono state prese nel periodo dicembre 2025 – maggio 2026, in fase di progettazione iniziale, prima del primo commit di produzione.

---

## Opzioni considerate

### Area 1 — Linguaggio e runtime backend

#### Opzione A — Python 3.13 + FastAPI *(scelta adottata)*

Python è il linguaggio dominante nell'ecosistema AI/ML. I SDK ufficiali di Anthropic e OpenAI sono scritti e mantenuti in Python come prima classe. La disponibilità di librerie per embeddings, vector math, chunking, audio processing (per voice) è impareggiabile. FastAPI è la scelta naturale per API async in Python: type hints nativi, integrazione con Pydantic v2, performance paragonabili a framework Node.js per I/O-bound workload, documentazione OpenAPI generata automaticamente. Python 3.13 introduce miglioramenti al GIL e ottimizzazioni al bytecode rilevanti per chunking e processing vettoriale.

#### Opzione B — Go (Gin / Fiber)

Go avrebbe offerto: binari statici, latenza bassissima, consumo memoria ridotto, semplicità di deploy.

**Perché non scelto:** L'ecosistema AI in Go è di seconda mano. I SDK OpenAI/Anthropic ufficiali non esistono in Go: si usano wrapper community che inseguono le API ufficiali con settimane di ritardo. Ogni nuova funzionalità LLM (tool use, streaming con partial JSON, reasoning tokens) richiederebbe implementazione manuale. Il costo di adozione supera il beneficio di performance per un sistema il cui collo di bottiglia è il tempo di risposta dell'LLM (200-2000ms), non il runtime del server.

**Rimpianto parziale:** Go sarebbe ottimo per un eventuale sidecar ad alta frequenza (es. event collector analytics). Se in futuro si dovesse scrivere un microservizio con requisiti sub-10ms e processing ad alto volume, Go tornerebbe in considerazione come componente specializzato, non come sostituto del backend principale.

#### Opzione C — Node.js TypeScript full-stack

Avrebbe eliminato il context switch frontend/backend e permesso condivisione di tipi end-to-end senza schema intermediario.

**Perché non scelto:** L'ecosistema AI in Node.js è meno maturo. Le operazioni CPU-bound (chunking, embedding preprocessing, scoring) soffrono del single-thread di Node. Celery non ha equivalente Node con la stessa maturità per task queue distribuita con retry, dead letter, scheduling cron. Il vantaggio della condivisione dei tipi si ottiene con OpenAPI codegen senza sacrificare il runtime migliore per ogni layer.

---

### Area 2 — Database e vector store

#### Opzione A — PostgreSQL 16 + pgvector 0.8.2 *(scelta adottata)*

Un singolo database relazionale con estensione vettoriale elimina la complessità operativa di gestire due sistemi separati. RLS di PostgreSQL opera a livello kernel del database, non applicativo: anche un bug nel codice Python non può far leakare dati tra tenant se la row policy è corretta. La multi-embedding strategy (content_emb, lifestyle_emb, features_emb) è espressa come colonne normali su tabelle normali — backup, transazioni, foreign key funzionano senza adapter. Per il volume previsto (decine di migliaia di vettori per tenant, centinaia di tenant in 3 anni) le performance HNSW sono ampiamente sufficienti.

#### Opzione B — Qdrant o Weaviate come vector DB dedicato

Qdrant e Weaviate sono vector DB nativi con performance migliori su dataset di miliardi di vettori, filtering avanzato, sharding automatico.

**Perché non scelto:** Aggiungono un terzo sistema da mantenere, monitorare, backuppare, scalare. Il vantaggio di performance si materializza a scale che DigIdentity non raggiungerà nei primi 2 anni. La perdita critica è la transazionalità: un aggiornamento di un nodo del knowledge graph che coinvolge dati relazionali + vettori non può essere wrapped in una singola transazione ACID se i sistemi sono separati. Avrebbe richiesto pattern di compensazione (saga) per operazioni oggi banali.

**Condizione di rivalutazione:** se un tenant supera i 10 milioni di vettori, o se il tempo di query vettoriale supera i 50ms in produzione con carichi reali.

#### Opzione C — Supabase managed

Avrebbe offerto dashboard pronta, Auth integrato, Storage, Realtime, riduzione del lavoro operativo iniziale.

**Perché non scelto:** Il layer di astrazione di Supabase diventa un ostacolo con RLS custom complessa, pgvector con parametri HNSW non standard, e Realtime su tabelle specifiche. I limiti del piano Pro rendono difficile prevedere i costi con la multi-tenancy. Si preferisce PostgreSQL self-hosted o managed (Neon/RDS) con pieno controllo.

**Rimpianto parziale:** Supabase Studio in locale (docker) è genuinamente utile per esplorare il database durante lo sviluppo — si può usare senza il servizio managed.

#### Opzione D — MongoDB Atlas Vector Search

**Perché non scelto:** Il knowledge graph ha relazioni forti (nodi, archi, proprietà, tenant) che si esprimono naturalmente con foreign key e JOIN — il contrario del modello documento di MongoDB. RLS non esiste in MongoDB: l'isolamento tenant richiederebbe enforcement applicativo, che è un rischio di sicurezza strutturale.

---

### Area 3 — Frontend runtime

#### Opzione A — Next.js 15 + React 19 *(scelta adottata)*

Next.js 15 con React Server Components permette il Morph server-side: il server genera componenti React dal knowledge graph e li invia come RSC payload, riducendo il JavaScript inviato al client e permettendo streaming incrementale. **Questo è un requisito funzionale del sistema, non una preferenza estetica.** L'ecosistema React (Three Fiber, LiveKit SDK) è il più ricco disponibile. Hosting su Cloudflare Pages con integrazione nativa per Workers elimina hop di rete tra edge e frontend.

#### Opzione B — Remix

Avrebbe offerto routing più esplicito, gestione degli errori migliore per route, filosofia "web platform first".

**Perché non scelto:** Il Morph server-side si basa su React Server Components — al momento della decisione (Q1 2026), il supporto RSC in Remix era sperimentale e l'allineamento con React 19 incompleto. Remix è una scelta eccellente per applicazioni form-heavy CRUD, non per un sistema di rendering adattivo real-time.

**Rimpianto:** Il modello di routing di Remix è più prevedibile per sviluppatori junior. Se il team cresce con persone meno familiari con Next.js, vale la pena rivalutare.

#### Opzione C — Astro

**Perché non scelto:** Astro è progettato per siti content-heavy con interattività limitata (islands architecture). DigIdentity ha interattività profonda (3D, voice, WebSocket per JSON Patch, rendering adattivo real-time). Wrappare quasi tutto in islands React annullerebbe i benefici di Astro. RSC in Astro non esiste.

---

### Area 4 — Edge computing

#### Opzione A — Cloudflare Workers *(scelta adottata)*

Workers gira in 200+ PoP globali con latenza < 5ms. Cloudflare KV con TTL 24h per i profili visitatore anonimi: lettura O(1) globale, scrittura eventually consistent (accettabile per il profilo visitatore). Workers e Pages condividono la stessa infrastruttura: zero hop aggiuntivi tra classificazione visitatore e rendering.

#### Opzione B — Vercel Edge Functions

**Perché non scelto:** Il frontend è su Cloudflare Pages, non Vercel. Avere edge su Vercel e frontend su Cloudflare avrebbe introdotto un hop di rete aggiuntivo per ogni request — il contrario dell'obiettivo. Il vantaggio DX di Vercel non compensa la degradazione architetturale.

**Condizione di rivalutazione:** se si decidesse di spostare il frontend su Vercel, il layer edge si sposterebbe di conseguenza.

#### Opzione C — Deno Deploy

**Perché non scelto:** L'ecosistema di Deno per Workers è meno maturo di Cloudflare su KV, Queues, Durable Objects. La documentazione e la community per pattern specifici (rate limiting, cookie handling, request fingerprinting) è più sottile. Cloudflare ha 5+ anni di vantaggio in produzione su questi pattern.

#### Opzione D — Nessun edge layer: Sense eseguito nel backend Python

L'alternativa più semplice: eliminare il layer edge e eseguire la classificazione visitatore direttamente nel backend FastAPI, come una normale chiamata HTTP.

**Perché non scelto:** Il Sense deve operare entro un budget di latenza di 50ms (BIBLE §2.1) perché avviene prima del primo byte inviato al browser. Un backend Python su un singolo datacenter europeo aggiunge 80-200ms per visitatori in Asia, America, Oceania — violando il budget già prima di qualsiasi elaborazione. Cloudflare Workers esegue il Sense nel PoP geograficamente più vicino al visitatore: per un visitatore in Giappone, il PoP di Tokyo risponde in 3-5ms invece di 150ms da Francoforte. Oltre alla latenza, perdere l'edge layer significa perdere la pre-classificazione prima del rendering: il backend Next.js riceverebbe una request senza VisitorPrior, dovrebbe fermarsi ad aspettarlo, e il Morph server-side non potrebbe essere eseguito in streaming concorrente alla classificazione. L'edge layer non è una complessità aggiuntiva: è il meccanismo che rende il Morph percettivamente istantaneo.

---

### Area 5 — Orchestrazione LLM

#### Opzione A — SDK multi-provider custom via `llm_provider.py` *(scelta adottata)*

Wrapping diretto di `anthropic` SDK e `openai` SDK senza framework intermediario. Controllo totale su: retry logic, streaming handling, token counting, cost tracking via `usage_logs`, prompt versioning. I bug sono nel codice del progetto, non in un layer di astrazione opaco.

#### Opzione B — LangChain

**Perché non scelto:** LangChain è sovraingegnerizzato per questo caso d'uso e opaco per il debugging. Le astrazioni (`Chain`, `Agent`, `Tool`) mappano male su un dominio dove il flusso conversazionale è strettamente controllato dal prodotto. Le versioni 0.1→0.2→0.3 hanno introdotto breaking change ripetuti. Il debugging di comportamento inatteso richiede leggere il codice di LangChain, non il proprio.

**Eccezione accettata:** `langchain-text-splitters` può essere usato come dipendenza puntuale per il document processing senza adottare il framework completo.

#### Opzione C — LlamaIndex

**Perché non scelto:** LlamaIndex è eccellente per RAG classico su documenti. Il knowledge graph di DigIdentity non è RAG su documenti: è un grafo strutturato con relazioni semantiche, multi-embedding per dimensione, e scoring composito. Adottarlo avrebbe significato combatterlo ogni volta che il comportamento desiderato deviava dal suo modello mentale di "document + embedding + retriever".

---

## Decisione

Si adotta lo stack canonico documentato in BIBLE v3 §9 nella sua interezza:

**Backend:** Python 3.13, FastAPI, PostgreSQL 16 + pgvector 0.8.2, SQLAlchemy 2.0 async + asyncpg, Redis 7, Celery 5, SDK Anthropic + OpenAI diretti via `llm_provider.py`, Pydantic v2.

**Frontend:** Next.js 15 + React 19 + TypeScript 5.x strict, Tailwind CSS 4, React Server Components per Morph, React Three Fiber + drei per Spatial, Marzipano per 360°, LiveKit React SDK per voice, Cloudflare Pages.

**Edge:** Cloudflare Workers per Sense, Cloudflare KV per VisitorPrior (TTL 24h).

**Osservabilità:** loguru + Cloudflare Logpush/Axiom, OpenTelemetry → Honeycomb/Grafana Tempo, Prometheus-compatible → Grafana, `usage_logs` per cost tracking.

**Sicurezza:** Doppler o 1Password Connect per secrets, RLS PostgreSQL come isolamento tenant primario, FastAPI middleware + Cloudflare WAF.

**Auth:** Phase 1-2 sessione anonima via cookie; Phase 3+ provider auth da decidere con ADR dedicato.

---

## Conseguenze

### Positive

- Ecosistema AI di prima classe: SDK Anthropic e OpenAI in Python ricevono nuove funzionalità prima di qualsiasi altro linguaggio.
- Isolamento tenant solido: RLS PostgreSQL opera a livello database — un bug applicativo non può causare data leak tra tenant se la row policy è corretta.
- Single source of truth per i dati: backup è `pg_dump`, restore è `pg_restore`, complessità operativa lineare.
- RSC abilita il Morph server-side: nessun'altra scelta frontend avrebbe permesso questo con la stessa semplicità.
- Cloudflare come unica rete per edge + frontend: zero hop aggiuntivi tra Sense e rendering, VisitorPrior disponibile prima che la request raggiunga Next.js.
- Stack coerente con CLAUDE.md: le convenzioni di sviluppo già documentate si applicano senza eccezioni su tutto il sistema.

### Negative

- **Profilo di competenze raro.** Lo stack richiede contemporaneamente: Python async avanzato, PostgreSQL internals (RLS, HNSW tuning, vacuum strategy), TypeScript strict con RSC, Cloudflare Workers (runtime V8 Isolates, non Node.js). Un singolo sviluppatore full-stack su tutti questi livelli è difficile da trovare. Il team minimo funzionante è 2 persone: backend Python/PostgreSQL solido e frontend Next.js/edge solido.
- **Nessun database managed "semplice".** PostgreSQL richiede attenzione continuativa a: vacuum, connection pooling, backup verification, replica lag, HNSW index rebuild dopo bulk import. Non sono problemi complessi, ma richiedono attenzione. Un weekend senza monitoraggio può diventare un problema il lunedì mattina.
- **pgvector non scala a dimensioni enterprise.** A > 10M vettori per tenant o > 100 QPS concorrenti su query vettoriali, pgvector mostra overhead rispetto a Qdrant/Weaviate. L'HNSW index è in-memory: RAM insufficiente sul database server causa degradazione di query time. Stima: con text-embedding-3-large (3072 dim), 3 embedding types, 100K entità per tenant e 20 tenant stimati, l'indice HNSW richiede circa 32-40GB RAM disponibili sul server database. Dimensionamento iniziale critico.
- **Celery è robusto ma verboso.** Richiede: broker Redis configurato, worker deployment separato, beat scheduler per cron, Flower o equivalente per monitoring. Per task semplici è molto boilerplate. Costo di bootstrapping reale: 2-3 giorni per setup corretto con monitoring.
- **Cloudflare Workers ha limitazioni runtime.** Non gira su Node.js: `fs`, `crypto` nativo Node e molte librerie npm non funzionano. Il codice Sense deve essere scritto pensando alle limitazioni V8 Isolates. Debugging in produzione richiede Logpush configurato preventivamente.
- **React Three Fiber aggiunge ~500KB al bundle gzipped.** Per tenant che non usano Spatial, questo bundle non serve. Code splitting aggressivo è obbligatorio — se fallisce, tutta la pagina paga il costo per tutti i tenant.
- **Costi operativi non trascurabili.** Stima conservativa per 10 tenant attivi: PostgreSQL managed ~$100-200/mese, Redis ~$30-50/mese, Celery workers ~$50-100/mese, Cloudflare Workers ~$5/mese, LLM inference ~$50-500/mese (molto variabile per volume). **Totale infrastruttura: ~$300-900/mese escluso LLM.** Il cost tracking via `usage_logs` è obbligatorio, non opzionale.
- **Debug alle 3 di notte richiede 4 sistemi simultanei.** Scenario tipico (tenant segnala risposte "strane"): Grafana per spike latenza LLM, Honeycomb per trace della request specifica, Axiom per log del Worker Sense, psql diretto per verificare embedding della query. Se gli accessi non sono configurati e documentati prima del problema, il MTTR raddoppia. Va pianificato prima del primo tenant in produzione.
- **Sessioni anonime fragili in Phase 1-2.** Cookie clearing, incognito mode, device switching spezzano la continuità del VisitorPrior. I test di personalizzazione nelle prime fasi saranno statisticamente rumorosi.

### Neutre

- TypeScript e Python coesistono in layer separati con interfaccia HTTP/JSON. Richiede disciplina per mantenere i tipi sincronizzati: OpenAPI codegen da FastAPI → TypeScript client va integrato nella pipeline CI.
- Marzipano è in stato di maintenance-only upstream. Funziona, ma bug su browser moderni potrebbero richiedere un fork. Accettabile per Phase 1; da rivalutare se il feature set 360° cresce.
- La scelta tra Doppler e 1Password Connect è operativa (costo, UX del team, integrazioni CI) e non impatta l'architettura.

---

## Piano di migrazione / rollout

Progetto in fase di avvio — nessun sistema legacy da migrare.

- [ ] Settimana 1-2: `docker-compose.yml` con PostgreSQL 16 + pgvector, Redis, Celery worker. Configurazione Doppler per development.
- [ ] Settimana 2-3: Scaffold FastAPI con `llm_provider.py`, Pydantic settings, health endpoint. Scaffold Next.js 15 con TypeScript strict, Tailwind 4, struttura App Router.
- [ ] Settimana 3-4: Prima migrazione PostgreSQL con schema base (tenant, sessioni, usage_logs). RLS enablement e prima policy. Test che simulano tenant diversi.
- [ ] Settimana 4-6: Scaffolding Cloudflare Workers per Sense (passthrough + logging). KV configurato con TTL 24h.
- [ ] Settimana 6-8: OpenTelemetry integrato in FastAPI e Next.js. Primo dashboard Grafana/Honeycomb funzionante. Alert su latenza LLM e error rate.
- [ ] Phase 3 (TBD): Integrazione provider auth per return visitor (decisione con ADR dedicato). Migration script per associare sessioni anonime a utenti autenticati.

---

## Questioni aperte

1. **PostgreSQL hosting provider** — Neon vs RDS vs self-hosted su VPS. Neon offre branching (utile per staging), RDS offre stabilità enterprise, self-hosted dà controllo totale ma costo operativo. Decisione necessaria prima del primo deploy in staging. Sarà oggetto di un ADR dedicato all'hosting infrastruttura, numerazione TBD.

2. **Dimensionamento RAM database** — Con text-embedding-3-large (3072 dim), 3 embedding per entità, stima 100K entità per tenant e 20 tenant, il server database necessita di almeno 32GB RAM per mantenere l'HNSW index in memoria. Verificare se il budget permette questo sizing dall'avvio o se si parte con text-embedding-3-small (1536 dim) e si migra. Da risolvere prima del primo tenant in produzione.

3. **Provider auth per Phase 3** — Clerk (DX migliore, SSO, user management dashboard, costo variabile) vs Auth.js (open source, zero vendor lock-in, più configurazione). La scelta impatta sia il dashboard tenant admin sia il future return visitor auth. Deadline: inizio Phase 3.

4. **Strategia di connection pooling** — PgBouncer in transaction mode vs pool nativo asyncpg vs Neon serverless pooling. Da scegliere prima di andare in produzione con più di 1 tenant attivo contemporaneamente.

5. **Code splitting React Three Fiber** — Strategia concreta (dynamic import con `next/dynamic`, route-level splitting, feature flag per tenant) da definire prima di implementare il componente Spatial. Un bundle non splittato è una regressione di performance per tutti i tenant non-Spatial.

---

## Riferimenti

- BIBLE v3 §9 — Stack tecnologico canonico
- BIBLE v3 §6.1 — Knowledge Graph (PostgreSQL + pgvector, RLS multi-tenant)
- BIBLE v3 §6.2 — Adaptive Renderer (edge layer, RSC, JSON Patch WebSocket)
- BIBLE v3 §2.1 — Sense: latency budget ≤ 50ms, edge execution
- BIBLE v3 §5 — Fat core / lean packs (motivazione per non usare Supabase full-stack)
- `docs/adr/_template.md` — template strutturale
