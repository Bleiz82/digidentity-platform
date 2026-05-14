# DigIdentity Living Site — BIBLE v3

**Documento canonico del progetto.**
Versione: 3.0
Data: 14 maggio 2026
Autore: Stefano Corda
Stato: Source of truth. Ogni decisione tecnica, strategica e operativa nei prossimi 12 mesi deriva da questo documento. Le sole modifiche autorizzate sono quelle che passano per ADR.

---

## 0. Come leggere questo documento

Questo è il successore di BIBLE v2 (11 maggio 2026). Tre cose sono cambiate radicalmente rispetto a v2 e vanno digerite prima di proseguire.

**Prima**: il prodotto non è "una piattaforma con sei engine tecnici". Il prodotto è **un sito web che attraversa otto stati di interazione con il visitatore** (Sense, Morph, Converse, Inhabit, Qualify, Hand-off, Remember, Learn). Gli engine tecnici esistono solo per servire questi stati. Se un componente non serve uno stato, non esiste.

**Seconda**: è stato aggiunto il settimo engine — **Adaptive Renderer** — che era implicito in v2 ma non esplicito. È l'engine più importante del sistema. Senza di lui, DigIdentity è un chatbot. Con lui, è un sito che vive.

**Terza**: la roadmap è riordinata per priorità di valore percepito dal cliente, non per ordine logico-tecnico. Il primo Morph visibile e il primo Inhabit base entrano in Phase 1, perché senza di loro la demo è indistinguibile da Sierra/Lofty/Roof.

Il documento è strutturato in modo che Claude Code, configurato con i subagents e gli skills descritti in §15, possa eseguire l'implementazione da solo a partire da prompt brevi che fanno riferimento alle sezioni numerate. Esempio: "implementa §6.3 con i vincoli di §10". Ogni sezione è progettata per essere autoconsistente sotto questo profilo.

---

## 1. Visione

**Un solo principio fondante.** Un sito web non è un documento da leggere. È uno spazio da abitare in conversazione. Il sito non mostra: dialoga. Non naviga: accompagna. Non raccoglie lead: nutre prospect fino al momento della consegna.

**Posizionamento di mercato.** Il primo sito web abitabile per micro, piccole e medie imprese italiane ad alto valore percepito. Prima i settori dove il prezzo del singolo cliente giustifica il costo della tecnologia (immobiliare luxury, cliniche dentali e estetiche premium, hospitality di nicchia, atelier di lusso, studi professionali specialistici). Poi, quando il sistema-madre raggiunge maturità, scalabilità verso settori più ampi a margine compresso.

**Promessa al cliente.** Tre frasi, in quest'ordine, senza eccezioni:

1. Il tuo sito riconosce chi arriva prima che parli.
2. Il tuo sito si trasforma per ciascun visitatore.
3. Il tuo sito qualifica i prospect e ti consegna solo quelli pronti, già conosciuti.

**Promessa al mercato (lessico per stampa, pitch, manuali).** "Il primo sito web abitabile. Non un chatbot incollato a una landing. Un luogo digitale che riconosce, si trasforma, conversa, accompagna, qualifica, consegna, ricorda."

---

## 2. Otto stati dell'esperienza visitatore

Il sistema è definito da una macchina a stati. Ogni stato ha un input, una elaborazione, un output, una metrica di successo, e un set di engine tecnici che lo serve. Gli stati sono attraversabili in ordine non strettamente sequenziale: il visitatore può saltare, tornare indietro, abbandonare e rientrare.

### 2.1 Sense — il sito riconosce

Input: segnali grezzi della request HTTP. UTM parameters, referrer, user-agent, accept-language, IP geolocation (city-level, mai più preciso senza consenso), ora del giorno locale al visitatore, device class, eventuale cookie/session anonima da visita precedente, eventuale fingerprint stabile (browser fingerprint hashato, niente PII).

Elaborazione: regole deterministiche prima, modello ML statistico poi (quando ci sarà dataset sufficiente, mese 6+). Output: un `visitor_prior` strutturato, con probabilità su un insieme di personas configurate dal tenant.

Output: `VisitorPrior` (vedi §7 per schema), persistito in `visitor_sessions`.

Metrica di successo: precisione della classificazione personas misurata contro outcome reale (conversione, abbandono, qualifica). Target a 6 mesi: F1 ≥ 0.65 su top-3 personas.

Engine coinvolti: Adaptive Renderer (consuma), Knowledge Graph (legge tenant config), Learning Engine (feedback loop).

Latency budget: 50 ms al massimo, eseguito su edge (Cloudflare Workers).

### 2.2 Morph — il sito si trasforma

Input: `VisitorPrior` da Sense.

Elaborazione: applicazione delle morph rules del Pack attivo al component tree iniziale. Le morph rules sono espresse in un DSL dichiarativo (vedi §8). Il Decision Engine valuta le regole, produce una `RenderingDirectives` (lista di trasformazioni da applicare ai componenti).

Output: HTML iniziale (RSC + edge SSR) personalizzato per la persona inferita. Stesso URL, stesso underlying content, layout/ordine/copy/CTA diversi.

Metrica di successo: differenza misurabile (heatmap, scroll depth, time-to-first-interaction) tra varianti morph servite a personas diverse. Target: almeno il 30% delle pagine viste presenta una variante morph non-default.

Engine coinvolti: Adaptive Renderer (esegue), Knowledge Graph (fornisce dati), Static Manifestation (cache di varianti pre-renderizzate dove possibile).

Latency budget: 200 ms (TTFB) sul percorso edge → client.

### 2.3 Converse — il sito dialoga

Input: messaggio del visitatore (testo, voce, oppure micro-interazione come "espandi questa sezione").

Elaborazione: agent loop multi-turno (Claude Sonnet 4.6/4.7 primario, fallback GPT-5 via router) con tool calling verso il KG e verso il sito stesso. L'agente può modificare il sito durante la conversazione (vedi §3 punto chiave).

Output: stream di risposta (testo + eventuali rendering directives che modificano il DOM in tempo reale).

Metrica di successo: turn quality score (rolling 7d), media ≥ 4.0 su 5. Tool call success rate ≥ 90%. Abbandono conversazionale (turno utente senza follow-up entro 60 s) < 35%.

Engine coinvolti: Agent Orchestrator (esegue), Knowledge Graph (legge), Adaptive Renderer (riceve directives dall'agente), Learning Engine (annota).

Latency budget: TTFC (time-to-first-chunk) ≤ 800 ms; TTFC voice ≤ 500 ms.

### 2.4 Inhabit — il visitatore abita

Input: visitatore entrato in una pagina di profondità (property, servizio, case study, atelier).

Elaborazione: presentazione spaziale del contenuto (tour 3D, galleria 360°, modello volumetrico) sincronizzata con l'agente in overlay. L'agente conosce lo spazio: riceve dal client la `viewport_state` (dove sta guardando, dove si è fermato, cosa ha ingrandito) come contesto.

Output: esperienza sincrona dove utente e agente "stanno nello stesso luogo digitale".

Metrica di successo: tempo medio in Inhabit ≥ 90 secondi su pagine di profondità. Dwell-by-region (heatmap 3D) come segnale per il Qualify.

Engine coinvolti: Spatial Experience (esegue), Agent Orchestrator (commenta), Knowledge Graph (annotazioni spaziali).

Latency budget: tour load p95 ≤ 3 s su 4G.

### 2.5 Qualify — il sito qualifica

Input: ogni interazione del visitatore (conversazione, scroll, click, dwell, micro-interazioni Inhabit).

Elaborazione: lead scoring incrementale eseguito server-side. Modello iniziale: rule-based scorecard (budget signal, urgency signal, decisional-authority signal, fit signal, friction signal). Modello mese 6+: gradient boosting su dataset annotato. Tre soglie: cold (<30), warm (30-70), hot (≥70).

Output: `LeadScore` aggiornato in continuo, persistito in `leads`.

Metrica di successo: precisione qualify-to-conversion. Target: ≥ 50% dei lead "hot" diventano opportunità reali entro 30 giorni dalla consegna al cliente.

Engine coinvolti: Agent Orchestrator (emette segnali di scoring durante conversazione), Learning Engine (calibra pesi).

Latency budget: aggiornamento score asincrono, non in path critico.

### 2.6 Hand-off — il sito consegna

Input: `LeadScore` ≥ soglia hot configurata dal tenant, oppure trigger esplicito (visitatore chiede di parlare con umano).

Elaborazione: generazione di un briefing completo (PDF + JSON + Markdown) per il sales del cliente. Contenuto: profilo persona inferita, transcript conversazione annotato per intenti, properties/servizi visti, dwell heatmap, lingua, fascia oraria preferita, eventuali obiezioni emerse e suggerimento di risposta.

Output: briefing recapitato via canali configurati (email, Slack, Telegram, webhook CRM). Conferma al visitatore: "abbiamo preparato Marco per la vostra chiamata: vi richiamerà entro le 18 di domani con tutto il contesto già letto".

Metrica di successo: time-to-first-sales-contact dal momento dell'handoff. Target: mediano ≤ 4 ore in giorni lavorativi.

Engine coinvolti: Agent Orchestrator (compone briefing), Knowledge Graph (legge tenant integrations), Integration Layer (consegna).

Latency budget: handoff completo entro 30 s dall'evento trigger.

### 2.7 Remember — il sito ricorda

Input: visitatore di ritorno (cookie, fingerprint, oppure account autenticato).

Elaborazione: caricamento dello stato precedente (`visitor_sessions`, conversazioni passate, properties viste, eventuale `LeadScore`). Continuation dell'agente con memoria piena del precedente.

Output: il sito non chiede "ciao, come ti chiami?". Dice "Marco, l'ultima volta avete visto la villa di Porto Cervo: nel frattempo è arrivata una proprietà simile a Punta Lada che potrebbe interessarvi". Tono e lessico configurabili per tenant.

Metrica di successo: tasso di ritorno qualificato. Visitatori che tornano una seconda volta convertono a tasso 2-4x rispetto a first-time.

Engine coinvolti: Knowledge Graph (memoria), Agent Orchestrator (consuma memoria), Adaptive Renderer (configura UI per return-visitor).

### 2.8 Learn — il sistema impara

Input: tutte le conversazioni, gli outcome del Qualify, le metriche di Morph e Inhabit, gli annotation manuali fatti dal team (settimanali).

Elaborazione: pipeline notturna che (a) calcola metriche aggregate per tenant, (b) identifica pattern di obiezioni nuove, (c) suggerisce modifiche ai prompt e alle morph rules, (d) raffina i pesi del lead scoring quando dataset è sufficiente, (e) prepara il batch annotation per la review umana settimanale.

Output: dashboard tenant (cosa funziona, cosa no, suggerimenti automatici). Per il team DigIdentity: report cross-tenant per migliorare il core e i Pack.

Metrica di successo: miglioramento mese-su-mese delle metriche di tutti gli altri stati. Composite metric da definire (vedi ADR-006).

Engine coinvolti: Learning Engine (esegue), tutti gli altri (forniscono dati).

---

## 3. Inversione concettuale fondante

Questa è la sezione più importante del documento. Va capita prima di leggere il resto.

**Il sito non è l'interfaccia dell'agente. Il sito è uno strumento che l'agente usa.**

Questa inversione cambia tutto. Nei sistemi tradizionali, l'agente è un widget aggiunto al sito: il sito è il prodotto principale, l'agente è un servizio ausiliario. In DigIdentity è esattamente il contrario. L'agente è il prodotto principale. Il sito è il suo strumento di rappresentazione e azione. L'agente, durante la conversazione, può chiamare funzioni che modificano il sito: cambiare layout, mostrare un componente, nascondere una sezione, evidenziare una property, riscrivere il copy di un titolo, attivare un tour 3D.

Tecnicamente: il sito espone all'agente un set di tool dichiarati come function calls. Tool come `morph_section`, `highlight_property`, `inject_component`, `change_persona`, `trigger_handoff`. L'agente, ragionando sulla conversazione, decide quali tool chiamare. Il client React riceve le directives via SSE/WebSocket e applica la trasformazione.

Implicazione architetturale: il `Decision Engine` (cuore dell'Adaptive Renderer) ha due input — le morph rules statiche (dal Pack) e le directive dinamiche emesse dall'agente. Le combina, produce il rendering finale.

Implicazione commerciale: vendere "un sito con AI" è il prodotto vecchio. Vendere "un agente AI che si manifesta come sito" è il prodotto nuovo. Quando spieghi al cliente "il vostro venditore digitale costruisce la vetrina giusta per ogni cliente, in tempo reale, mentre lo accompagna", capiscono in 10 secondi.

---

## 4. Architettura: i sette engine

Ogni engine ha responsabilità singola, contratti chiari di input/output, e una sezione tecnica dedicata in §6.

| # | Engine | Responsabilità singola | Stati serviti |
|---|---|---|---|
| 1 | Knowledge Graph Engine | Persistere e interrogare la conoscenza strutturata multi-tenant (entità, embeddings, relazioni, memoria visitatore) | tutti |
| 2 | **Adaptive Renderer** (nuovo in v3) | Decidere e applicare la rappresentazione del sito in funzione di `VisitorPrior` + `RenderingDirectives` dall'agente + morph rules del Pack | Sense, Morph, Converse, Inhabit, Remember |
| 3 | Conversational Renderer | Trasportare lo stream conversazionale tra agente e visitatore (testo via SSE, voce via WebRTC/LiveKit, futura modalità immersiva) | Converse, Inhabit |
| 4 | Agent Orchestrator | Eseguire il loop dell'agente: ragionamento, tool calling, gestione fallback modelli, scoring incrementale | Converse, Qualify, Hand-off |
| 5 | Spatial Experience Engine | Servire tour 3D, gallerie 360°, modelli volumetrici, sincronizzati con l'agente | Inhabit |
| 6 | Static Manifestation Engine | Pre-renderizzare varianti morph statiche per SEO classico + servire `/llm.txt` per GEO (Generative Engine Optimization) | Sense (cache), tutti (SEO) |
| 7 | Learning Engine | Annotare, aggregare, analizzare, suggerire miglioramenti | Learn, retro-feedback su tutti |

Nota su Adaptive Renderer: è l'engine che rende DigIdentity diverso da qualsiasi altra piattaforma. Va trattato come la "core IP" del progetto. Il suo Decision Engine deve essere modellato come una macchina di valutazione di regole (rule engine) con priorità, conflict resolution deterministico, e tracciabilità completa di ogni decisione (per debug e audit cliente).

---

## 5. Principio fat core / lean packs (riformulato)

Il principio di v2 — "fat core, lean packs" — è confermato ma va declinato con disciplina maggiore.

**Cos'è il core (sempre stesso, mai ramificato per cliente).**

- I sette engine in §4, nella loro implementazione generica.
- Il DSL delle morph rules (vedi §8).
- I tool generici dell'agente (search, fetch_entity, morph_section, ecc.).
- Lo schema KG base (tenants, entities, embeddings, conversations, conversation_turns, leads, visitor_sessions).
- Il sistema di multi-tenant isolation.
- Il sistema di plugin/integrazione per CRM, email, webhook, telefonia.
- Il deployment, l'observability, il sistema di auth.

**Cos'è un Pack (specifico per verticale).**

Un Pack è una cartella `packs/<vertical-name>/` con questa struttura canonica:

```
packs/real-estate-luxury/
├── pack.yaml                    # metadata: nome, versione, dependencies, owner
├── ontology/
│   ├── schema_extension.sql     # tabelle aggiuntive specifiche
│   └── entities.json            # dichiarazione entità del verticale
├── personas/
│   └── personas.yaml            # personas configurabili per i tenant del verticale
├── morph_rules/
│   ├── homepage.yaml            # regole morph per homepage
│   ├── property_detail.yaml
│   └── lead_form.yaml
├── prompts/
│   ├── system.md                # system prompt dell'agente per il verticale
│   ├── tool_descriptions.md     # descrizioni tool specializzate
│   └── few_shots/               # esempi few-shot per il verticale
├── components/                  # React components custom del verticale
│   ├── PropertyHero.tsx
│   ├── VineyardFocus.tsx
│   └── ...
├── tools/                       # tool Python aggiuntivi (function calling)
│   └── valuation_estimator.py
├── scoring/
│   └── lead_scorecard.yaml      # pesi e regole del Qualify per il verticale
├── golden_dataset/              # eval dataset specifico
│   └── conversations.jsonl
└── README.md
```

**Regola di disciplina (NON-NEGOZIABILE).** Se viene voglia di toccare il core per gestire un caso specifico di un cliente, STOP. Va nel Pack. Mai. Quando il Pack non basta, si crea un Pack derivato (`real-estate-luxury-italia`) che eredita dal Pack base. Mai modificare il core per un cliente.

**Configurazione cliente (Tenant config).**

Ogni tenant ha un `tenant.yaml` che dichiara: Pack utilizzato, personas attive, override puntuali (copy, colori, voci TTS, integrazioni, soglie scoring). Il tenant.yaml è il SOLO modo legittimo di personalizzare un cliente specifico. Nessun codice client-specific nel repository, mai.

**Promozione Core → Pack → Tenant.**

Una feature richiesta da un cliente segue questa pipeline mentale:

1. È utile a tutti i clienti di tutti i verticali? Va nel core.
2. È utile a tutti i clienti di QUESTO verticale? Va nel Pack.
3. È utile solo a questo cliente? Va nel tenant.yaml (configurazione) o si rifiuta cortesemente.

Questa pipeline è la differenza tra agency a margine 20% e SaaS a margine 75%.

---

## 6. Engine in dettaglio

### 6.1 Knowledge Graph Engine

**Stack tecnico.** PostgreSQL 16 + pgvector 0.8.2. Multi-tenant via Row-Level Security (RLS) con `app.tenant_id` impostato per request. Connection pool tenant-aware (vedi ADR-003 per la disciplina di session/transaction). Embeddings: OpenAI `text-embedding-3-large` (3072 dim) per il core, override per Pack se necessario.

**Cambiamento rispetto a v2.** v2 usava `text-embedding-3-small` (1536 dim). v3 usa `large` (3072 dim) e introduce **multi-embedding strategy**: ogni entità rilevante ha tre vettori — `content_emb` (descrizione generica), `lifestyle_emb` (narrativa, atmosfera, emotional appeal), `features_emb` (caratteristiche strutturate). Search hybrid con pesi configurabili per query type (lifestyle-query, technical-query, mixed-query). Costo storage triplicato è irrilevante a questi volumi (< 100k entità per anno 1).

**Tabelle base (core).**

`tenants`, `users` (per multi-tenant management), `entities` (super-tabella polimorfica con `entity_type`, le entità specifiche del verticale sono in tabelle dedicate del Pack), `embeddings` (con `entity_id`, `embedding_type`, `vector`, `model_version`), `conversations`, `conversation_turns` (con campi nuovi: `user_intent`, `quality_score`, `tool_calls_json`, `tool_call_success`), `leads`, `visitor_sessions` (nuova in v3: vedi §7), `events` (event log per Learn).

**Indici.** HNSW su tutti i vettori (3 indici per `embedding_type`), GIN sui campi JSONB di filtro, btree su `tenant_id` + colonne di lookup. RLS policy su tutte le tabelle che contengono dati di tenant.

**Disciplina RLS.** Vedi ADR-003. Il pattern `SET LOCAL app.tenant_id = :id` deve essere applicato all'interno di una transazione esplicita, e ogni request HTTP apre la sua transazione. Mai condividere connessioni con `SET LOCAL` tra request. Test di leak cross-tenant (50 request concorrenti su 5 tenant) come parte della CI.

### 6.2 Adaptive Renderer Engine (core IP)

**Cos'è.** Un sistema che, dato `VisitorPrior + RenderingDirectives + PackConfig + TenantConfig`, produce il rendering del sito.

**Composizione.**

- **Edge Layer (Cloudflare Workers).** Esegue Sense, calcola VisitorPrior, sceglie la variante morph cached o richiede al backend la generazione dinamica. Output: HTML iniziale.
- **Server Layer (Next.js 15 + React Server Components).** Esegue il Decision Engine, applica morph rules + agent directives, renderizza i componenti server-side dove possibile.
- **Client Layer (React 19).** Riceve stream di patches (RFC 6902 JSON Patch) per il DOM via WebSocket dall'agente durante Converse/Inhabit, applica trasformazioni atomiche.

**Decision Engine.**

Implementato come rule engine pure-functional in TypeScript (server) + Python (Agent Orchestrator side). Stessa logica nei due posti, condivisione del DSL via codegen. Ogni decisione di rendering è registrata in `events` con (regola applicata, input, output, latency). Audit completo per debug e per il cliente.

**Conflict resolution.** Se due regole conflict, vince quella con priorità più alta. Se priorità uguali, vince la più specifica (più condizioni `match`). Se ancora uguale, errore a deploy time (validazione del Pack).

**Performance budget.**

- Sense (edge): ≤ 50 ms p95.
- Decision Engine + RSC render: ≤ 200 ms p95 TTFB.
- Patch via WebSocket: ≤ 100 ms dall'emit dell'agente al DOM update client.

### 6.3 Conversational Renderer Engine

**Cos'è.** Lo strato di trasporto del dialogo tra agente e visitatore. Disaccoppiato dall'agent loop: il Conversational Renderer non sa cosa l'agente sta dicendo, sa solo come consegnarlo al client e come ricevere input dal client.

**Modalità di trasporto.**

- **Text via Server-Sent Events (SSE)** sulla rotta `/conversations/{id}/stream`. Modalità default, supportata da qualsiasi browser.
- **Voice via WebRTC (LiveKit Agents)** quando il tenant ha la modalità voce abilitata. Il transport è separato (LiveKit room), ma l'agent loop è lo stesso: l'agente Python parla con LiveKit Agents come orchestratore media, il media è agnostico al cervello.
- **Channel-extensible.** Architettura preparata per trasporto futuro via WhatsApp, Telegram, telefonia (LiveKit SIP). Il tenant.yaml dichiara i canali attivi.

**Decisione architetturale critica (ADR-002).** SSE per testo è confermato per v3. Per la voce si va su LiveKit Agents (Python SDK 1.5.x, native MCP, sub-500 ms latency). Non si reinventa il transport. Il cervello (Agent Orchestrator) è agnostico al canale.

**Patches Renderer-Adapter.** Quando l'agente emette una directive di rendering ("highlight property X"), il Conversational Renderer la incanala sullo stesso channel del messaggio testuale, con type discriminator (`type: "text" | "directive" | "directive_batch"`). Il client distingue e indirizza.

### 6.4 Agent Orchestrator Engine

**Cos'è.** Il cervello. Esegue il loop dell'agente: percepisce input, ragiona, chiama tool, emette output.

**Stack.** Python 3.13 + FastAPI + Anthropic SDK + OpenAI SDK + LiveKit Agents.

**Routing modelli.** `LLMRouter` con strategia primary/fallback. Primary: Claude Sonnet 4.6 per default (cost/quality sweet spot), upgrade automatico a Claude Opus 4.7 per le conversation classificate `complex` (multi-turn lungo, decisioni high-value, multi-tool reasoning). Fallback: GPT-5 di OpenAI quando circuit breaker scatta su Anthropic (3 errori 5xx in 30 s → fallback per 5 minuti, poi half-open retry).

**Tool catalog del core.**

- `kg.search(query, entity_type, filters, embedding_type)` — ricerca semantica multi-embedding.
- `kg.fetch(entity_id, depth)` — recupero entità con relazioni fino a profondità configurata.
- `kg.fetch_memory(visitor_session_id)` — recupero memoria visitatore (Remember).
- `render.morph_section(section_id, directive)` — chiede al Renderer di trasformare una sezione.
- `render.highlight(entity_id, mode)` — evidenzia un'entità (property, servizio, ecc.).
- `render.inject_component(component_name, props, position)` — inietta un componente.
- `render.set_persona(persona_id)` — cambia la persona di rendering attiva (raro, ma utile quando il visitatore rivela informazioni che invalidano la prior iniziale).
- `lead.update_score(signal, weight)` — emette un segnale di scoring.
- `lead.trigger_handoff(reason, urgency)` — innesca lo stato Hand-off.
- `comm.schedule_callback(when, contact, context)` — registra una callback al sales.

**Tool del Pack.** Aggiunti per verticale. Esempi per real-estate-luxury: `valuation.estimate(criteria)`, `availability.viewing(property_id, when)`, `compliance.aml_prescreen(buyer_indicators)`.

**Streaming + tool calling.** L'agent loop usa streaming con tool calling iterativo. Pattern: stream del ragionamento, parse di eventuali tool calls, esecuzione tool, re-prompt con risultato, continue streaming. Latency target TTFC ≤ 800 ms con strategie di pre-warming (system prompt cached, KG warm cache).

**Resilienza.** Conversazione + turno utente vengono salvati in un'unica transazione atomica con `idempotency_key` (fix del bug parcheggiato in v2). Retry sicuri lato client.

**Eval framework.** Vedi §11. Golden dataset per Pack, eval ogni notte su CI, regressione = blocker per deploy.

### 6.5 Spatial Experience Engine

**Cos'è.** Lo strato che serve esperienze immersive (tour 360°, modelli 3D, gallerie volumetriche) sincronizzate con l'agente.

**Stack.**

- **Acquisition pipeline.** Polycam (mobile scan) come default per i clienti, Matterport per i tenant Luxury/Bespoke che ne hanno già uno, Insta360/Ricoh THETA per i tenant che fanno 360° puri. Una funzione di ingestione converte tutti in formato unificato (glTF 2.0 + descriptor JSON con room graph).
- **Rendering.** Marzipano per 360° puri (lightweight, ottimo su mobile). Three.js per modelli 3D walkable. React Three Fiber come strato React.
- **Sincronia con agente.** Il client invia all'agente `viewport_state` ogni 2 secondi (room corrente, dwell time, eventuale "punto di interesse" che l'utente sta guardando). L'agente usa questo come contesto per commenti contestuali.

**Annotazioni spaziali.** Il Pack dichiara `spatial_annotations` per ogni entità (es. "in questa stanza la luce è perfetta tra le 16 e le 18", "questa terrazza ha 240° di vista mare"). L'agente le legge dal KG e le usa nel commento.

**Performance budget.** Tour load p95 ≤ 3 s su 4G. Modelli 3D > 10 MB pre-compressed in Draco. Lazy loading aggressivo.

**Roadmap interna engine.** v1 (Phase 1): 360° statici via Marzipano + overlay agente. v2 (Phase 3): 3D walkable Three.js + viewport_state agent sync. v3 (Phase 6+): video sferico interattivo, AR mobile, eventuale integrazione visori.

### 6.6 Static Manifestation Engine

**Cos'è.** Lo strato di SEO e GEO. Serve tre cose: HTML statico cacheable per SEO classico, varianti morph pre-renderizzate per ridurre carico Edge, e file `/llm.txt` per AI search engine.

**Stack.** Build pipeline che parte dal KG → Next.js SSG per varianti morph pre-renderizzabili + Astro per pagine prevalentemente statiche (blog, glossari, case study). Cloudflare Pages come hosting.

**Schema.org JSON-LD.** Ogni pagina pubblica include `<script type="application/ld+json">` generato dal KG. Per real-estate-luxury: `RealEstateListing` esteso con vocabolario `digidentity:LuxuryResidence` (estensione propria, vedi §13). Per altri verticali: estensioni analoghe.

**`/llm.txt` standard.** Per ogni entità importante, generazione di `/{slug}/llm.txt` con rappresentazione plain-text strutturata pensata per consumo LLM (formato proposto da llmstxt.org, adattato). Questo è il GEO che vendi al cliente: il sito si fa leggere meglio da ChatGPT, Perplexity, Claude e Google AI Overviews.

**Single source of truth.** Il KG. Mai modificare il build output a mano. La build è riproducibile.

### 6.7 Learning Engine

**Cos'è.** Il sistema che chiude il loop. Aggrega tutto, suggerisce migliorie, prepara la review umana.

**Stack.** Celery + Redis per job scheduling. Pipeline notturne (alle 04:00 ora server). Storage analytics in tabelle dedicate (`learning_metrics_daily`, `learning_observations`, `learning_suggestions`).

**Cosa fa.**

- Calcola metriche aggregate per tenant e cross-tenant.
- Identifica drift conversazionale (pattern di obiezioni nuove non ancora gestite dai prompt).
- Suggerisce modifiche ai prompt e alle morph rules (suggerimenti, non automatici).
- Quando dataset Pack-level raggiunge 1000+ turni annotati, raffina i pesi del lead scoring con un modello di gradient boosting (XGBoost).
- Prepara batch per annotation umana settimanale: top 50 turni di basso quality score, top 20 di alto, sample casuale di 50, totale 120/settimana/tenant attivo.

**Annotation umana.** Settimanale, fatta da te (Stefano) finché non c'è un team. Tag enum: `intent` (search/qualify/book/objection/info/other), `quality` (1-5), `tool_call_assessment` (correct/wrong/missing), `note_libero`. Tool: una piccola UI interna in `/admin/annotate`.

**Output verso il team.** Report settimanale Markdown auto-generato in `docs/learning/weekly/YYYY-WW.md` con highlights, regressions, suggested changes. Decisioni di accettazione/rifiuto registrate come ADR quando significative.

---

## 7. Modelli dati nuovi (cambiamenti rispetto a v2)

### 7.1 VisitorPrior

Struttura emessa dal Sense, persistita in `visitor_sessions`:

```python
class VisitorPrior(BaseModel):
    session_id: UUID
    tenant_id: UUID
    visitor_hash: str  # fingerprint hashato, no PII
    inferred_personas: list[PersonaScore]  # [{persona_id, score}, ...]
    signals: SenseSignals  # tutto quello che ha visto Sense
    confidence: float  # 0..1
    created_at: datetime
    updated_at: datetime
```

`PersonaScore` ha `persona_id` (riferito a personas dichiarate nel Pack) e `score` (probabilità).

`SenseSignals` contiene: `referrer`, `utm`, `geo_city`, `device_class`, `language`, `local_time_bucket`, `is_returning`, `prior_session_id`.

### 7.2 RenderingDirectives

Emesse dall'agente, applicate dal Renderer:

```python
class RenderingDirective(BaseModel):
    type: Literal["morph_section", "highlight", "inject", "set_persona", "show", "hide", "reorder", "rewrite_copy"]
    target: str  # selettore o entity_id
    params: dict
    priority: int = 100
    reason: str  # tracciabilità: perché l'agente ha deciso questo
```

### 7.3 LeadScore

Aggiornato in continuo dall'agent loop:

```python
class LeadScore(BaseModel):
    session_id: UUID
    score: float  # 0..100
    bucket: Literal["cold", "warm", "hot"]
    signals: list[ScoringSignal]  # storico dei segnali emessi
    last_updated: datetime
```

### 7.4 Conversation turn enhancements

Rispetto a v2, aggiunge: `user_intent` (enum), `quality_score` (nullable, popolato da annotation umana), `tool_calls_json` (lista dei tool chiamati con risultato), `tool_call_success_overall` (bool), `rendering_directives_emitted` (lista, per audit).

---

## 8. DSL delle morph rules

**Perché esiste.** Replicabilità verticale richiede che le regole di morphing siano dichiarative, leggibili da non-developer (te le scrive un domain expert luxury, te le scrive un consulente dentale), versionabili. Hardcoded in TypeScript significa rifare ogni cliente.

**Formato.** YAML. Posizione: `packs/<vertical>/morph_rules/*.yaml`.

**Esempio (real-estate-luxury, homepage.yaml):**

```yaml
version: 1
target_page: homepage
rules:
  - id: luxury-buyer-prior
    priority: 100
    when:
      match_all:
        - signal: utm.campaign
          equals_any: ["luxury-search", "lionard-paid"]
        - signal: persona_score.luxury_buyer
          gte: 0.6
    do:
      - directive: reorder
        target: hero_section
        params:
          order: ["above_5m_listings", "concierge_cta", "trust_badges"]
      - directive: rewrite_copy
        target: hero_headline
        params:
          variant: luxury_buyer_v2
      - directive: hide
        target: generic_search_form
      - directive: show
        target: concierge_chat_invite
        params:
          delay_ms: 4000

  - id: journalist-prior
    priority: 90
    when:
      match_all:
        - signal: persona_score.journalist
          gte: 0.5
    do:
      - directive: morph_section
        target: hero_section
        params:
          template: press_kit

  - id: competitor-prior
    priority: 80
    when:
      match_all:
        - signal: referrer.domain
          matches_any: ["competitor1.com", "competitor2.it"]
    do:
      - directive: hide
        target: pricing_section
      - directive: hide
        target: case_studies_advanced

fallback:
  - directive: render_default
```

**Validazione.** Schema JSON Schema in `core/dsl/morph_rule.schema.json`. Linter custom in `tools/lint-pack/`. Validazione obbligatoria in CI prima di merge.

**Primitive del DSL.** Stabili nel core: `morph_section`, `highlight`, `inject`, `show`, `hide`, `reorder`, `rewrite_copy`, `set_persona`, `trigger_agent`, `track`. Estensioni Pack-level possibili dichiarando custom primitive in `packs/<vertical>/dsl_extensions.yaml`.

**Test di morph rules.** Snapshot testing: dato (Page, VisitorPrior fixtures, PackConfig), il rendering risultante è confrontato a uno snapshot golden. Cambiamenti agli snapshot richiedono review.

---

## 9. Stack tecnologico canonico

Questa lista è la single source of truth della scelta tecnologica. Modifiche solo via ADR.

**Backend.**

- Linguaggio: Python 3.13.
- Web: FastAPI (ultima stabile 2026).
- DB: PostgreSQL 16 + pgvector 0.8.2.
- ORM: SQLAlchemy 2.0 async + asyncpg + pgvector-python adapter (fix del tech-debt v2).
- Cache/queue: Redis 7.
- Background jobs: Celery 5.
- LLM SDKs: `anthropic` ultima stabile, `openai` ultima stabile.
- Embeddings: OpenAI `text-embedding-3-large` (3072 dim).
- Voice agents: `livekit-agents` 1.5.x.
- Validation: Pydantic v2 + pydantic-settings.

**Frontend.**

- Next.js 15 + React 19 + TypeScript 5.x.
- Tailwind CSS 4.
- React Server Components per Morph server-side.
- React Three Fiber + drei + Three.js per Spatial.
- Marzipano per 360° puri.
- LiveKit React SDK per voice client.
- Hosting: Cloudflare Pages.

**Edge.**

- Cloudflare Workers per Sense.
- Cloudflare KV per cache di VisitorPrior anonimizzati (TTL 24h).

**Database e infrastruttura.**

- Local dev: Docker Compose (Postgres pgvector + Redis).
- Production: dipende dalla scelta cloud (vedi §14).

**Auth.**

- v1 (Phase 1-2): nessun auth visitatore. Anon session via cookie.
- v2 (Phase 3+): auth opzionale tramite Clerk o Auth.js per visitatori returning che si auto-identificano.
- Tenant admin: Clerk con SSO support per i clienti Luxury/Bespoke.

**Observability.**

- Logging: structured JSON con `loguru` + ship a Cloudflare Logpush o Axiom.
- Tracing: OpenTelemetry, backend ship a Honeycomb (free tier) o Grafana Tempo.
- Metrics: Prometheus-compatible, dashboard Grafana.
- Cost tracking: per-tenant per-model token usage in tabella `usage_logs`, dashboard interna.

**Sicurezza.**

- Secrets management: doppler.com o 1Password connect (mai .env in repo, mai key in chat).
- RLS PostgreSQL come isolamento primario tenant.
- Rate limiting: middleware FastAPI + Cloudflare WAF.
- DDoS: Cloudflare standard.
- Compliance: GDPR-first, DSAR-ready (data subject access request endpoint), data retention configurabile per tenant.

---

## 10. Standard operativi

### 10.1 Documentation as code

- Ogni decisione architetturale → ADR in `docs/adr/NNNN-titolo.md`. Numerazione progressiva, status `proposed/accepted/superseded`.
- Ogni feature significativa → ADR + PR collegato.
- Lista ADR aperti in §16.

### 10.2 Conventional commits + branch model

- Conventional commits per ogni commit (`feat`, `fix`, `chore`, `docs`, `refactor`, `test`, `perf`, `journal`).
- Scope: nome dell'engine o del Pack (`feat(adaptive-renderer): ...`, `feat(pack-real-estate-luxury): ...`).
- Branch model: trunk-based con feature branch a vita corta (< 3 giorni). PR sempre.

### 10.3 Testing strategy

- Unit test per ogni servizio del backend (pytest + pytest-asyncio).
- Integration test per le rotte FastAPI (httpx + testcontainers per Postgres pgvector reale).
- Tenant isolation test (50 request concorrenti su 5 tenant, verifica zero leak).
- Eval test per ogni Pack (golden dataset, regressione blocca merge).
- Snapshot test per morph rules.
- E2E test (Playwright) per i percorsi visitor critici, almeno 5 per Pack.

### 10.4 CI/CD

- GitHub Actions.
- Pipeline: lint → typecheck → unit test → integration test → eval Pack → build → deploy preview.
- Deploy preview per ogni PR (Cloudflare Pages + transient Postgres).
- Deploy production solo da `main`, manuale (no auto-deploy nei primi 6 mesi).

### 10.5 Code style

- Python: ruff + black + mypy strict.
- TypeScript: biome (linter + formatter unico).
- Markdown: prettier per coerenza.

### 10.6 Sicurezza e privacy operativa

- API keys e secrets: mai in chat, mai in repo, mai in screenshot, mai in journal.
- `.env` sempre gitignored, verificato in pre-commit hook.
- PII visitatore: hashato a livello applicativo (visitor_hash), mai persistito email/telefono in chiaro fino al consenso esplicito (handoff form).
- Cookie: solo first-party, no third-party tracking. CMP minimale per il consenso.

---

## 11. Eval framework

Questa sezione è critica. Senza eval, nei prossimi 12 mesi non si capisce più cosa funziona.

**Cosa si valuta.**

- Qualità conversazionale (judge automatico Claude Opus 4.7 + ground truth golden dataset).
- Tool call correctness (esatto match di tool + parametri attesi entro tolleranza definita).
- Lead scoring accuracy (su outcome reali, validation periodica).
- Morph rule correctness (snapshot test).
- Latency per ogni stato (regression test continuo).

**Golden dataset.**

- Per Pack: minimo 50 conversation di reference, target 200 entro mese 6.
- Formato JSONL: input visitor sequence + expected agent behavior (asserzioni semantiche, non match esatto del testo).
- Versionato in Pack: `packs/<vertical>/golden_dataset/conversations.jsonl`.

**Esecuzione.**

- CI ogni notte: run completo del golden dataset per ogni Pack.
- Su PR: run rapido (10% sample) + run completo se PR tocca core o Pack.
- Threshold di passaggio configurabile per Pack, default 90% pass.

**Tool.** `promptfoo` come runner (open-source, integration Anthropic + OpenAI). Custom Python wrapper per integrazione con KG fixtures.

**Reporting.** Eval results pushed a dashboard interna + commento auto sul PR.

---

## 12. Roadmap 12 mesi (riordinata per valore percepito)

Tutte le date sono indicative. Il principio di priorità è: **ogni Phase deve produrre una demo dimostrabile a un cliente reale**.

### Phase 0 — Fondazioni (Day 1 fatto, Day 2-7)

Stato: 70% completato.

- ✅ Repo, BIBLE v2, backend FastAPI base, KG base.
- 🔜 BIBLE v3 (questo documento) committed.
- 🔜 ADR-001 (stack), ADR-002 (transport multi-modal), ADR-003 (RLS discipline), ADR-004 (LLM router), ADR-005 (multi-embedding).
- 🔜 Setup Claude Code subagents + skills + plugins (§15).
- 🔜 Cleanup tech-debt parcheggiato v2 (atomicity chat, model validation, pgvector adapter).

Deliverable end of Phase: repo configurato per esecuzione assistita Claude Code, fondamenta v3 in piedi.

### Phase 1 — Primo Morph visibile + Inhabit base (settimane 2-5)

Obiettivo commerciale: demo `demo.digidentity.agency` che mostra (a) 3 morph variants della stessa homepage real-estate-luxury per 3 personas diverse, e (b) una property page con tour 360° + agente in overlay.

- Adaptive Renderer v1: Edge Sense + Decision Engine + RSC morph + 3 morph rules concrete.
- Pack `real-estate-luxury` v0.1 con 3 personas, 3 morph rules homepage, 1 morph rule property detail.
- Frontend Next.js 15 con chat SSE consumer.
- Spatial v1: Marzipano viewer + 1 property con tour 360° reale (Polycam scan di una villa demo).
- LLMRouter con fallback OpenAI.
- Tenant isolation stress test in CI.
- Eval framework attivo con 20 conversation golden.

Deliverable end of Phase: demo live + 3 pitch deck cliente (Real Estate luxury).

### Phase 2 — Qualify + Hand-off (settimane 6-9)

Obiettivo commerciale: primi 3 pilot clients firmati. Capacità di consegnare lead qualificati con briefing automatico.

- Lead scoring engine rule-based v1.
- Tool catalog completo del core.
- Briefing generator (PDF + Markdown + JSON via tenant integrations).
- Integrazioni: email (SMTP/SES), Slack, Telegram, generic webhook.
- Pack `real-estate-luxury` v0.2 con scoring scorecard luxury-italiano.
- Compliance baseline: GDPR, DSAR endpoint, retention policies, cookie banner.

Deliverable end of Phase: 1-2 pilot firmati a `prezzo pilota` (vedi §17), feedback loop attivo.

### Phase 3 — Remember + voice opzionale + GEO (settimane 10-15)

Obiettivo commerciale: secondo pilot firmato, GEO come argomento di vendita differenziante.

- Visitor sessions persistence + return visitor recognition.
- LiveKit Agents integration come secondo transport opzionale.
- Static Manifestation Engine v1: Astro + JSON-LD + /llm.txt per ogni entità.
- Ontology `digidentity:LuxuryResidence` v1.0 pubblicata.
- Cloudflare Pages + Workers in production.

Deliverable end of Phase: 3 pilot live, primo cliente paying mese 4, demo GEO documentata.

### Phase 4 — Learning Engine attivo + secondo verticale (mesi 4-6)

Obiettivo commerciale: 5-7 paying clients real-estate-luxury, prima validazione secondo verticale.

- Learning Engine pipeline notturne.
- Annotation UI interna.
- Dashboard tenant con metriche.
- Apertura secondo verticale: candidates da valutare (cliniche dentali premium / atelier moda / hospitality boutique). Decisione basata su (a) market size attuale, (b) tuoi network di vendita, (c) trasferibilità del Pack real-estate-luxury.

Deliverable end of Phase: Pack `dental-luxury` (o altro) v0.1 con 1 pilot.

### Phase 5 — Scaling Real Estate Luxury (mesi 7-9)

Obiettivo commerciale: 15+ paying clients real-estate-luxury, validazione Bible Rule per apertura altri verticali.

- Hardening, performance optimization.
- ML-based personalization (Sense modello statistico).
- Spatial v2: 3D walkable con Three.js + viewport_state sync.
- Internazionalizzazione (multi-language, multi-currency).
- Outreach Costa Smeralda → Côte d'Azur → Marbella.

### Phase 6 — Pre-seed/Seed fundraising + apertura terzo verticale (mesi 10-12)

Obiettivo commerciale: 25+ paying clients, ARR > €500k, condizioni per Bible Rule rispettate, raising opzionale.

- Pitch deck investor con metriche reali.
- Apertura terzo verticale.
- Decisione strategica: bootstrap o raise.

---

## 13. Ontologia luxury come standard aperto

**Strategia.** Pubblicare `LuxuryResidence Ontology v1.0` come spec aperta su GitHub (licenza CC-BY-SA), maintainerata da DigIdentity. Diventa lo standard de facto per descrivere proprietà luxury in Europa.

**Cosa contiene.** Estensione di `schema.org/SingleFamilyResidence` con 40-60 predicati luxury-specific:

- Geomorfologia e vista: `seaViewAngleDegrees`, `seaViewDistance`, `mountainView`, `panoramicView`, `solarExposureSummer`, `solarExposureWinter`.
- Discrezione e sicurezza: `privacyLevel`, `gatedCommunity`, `securityServices24h`, `helipadDistance`, `pressAccessRestrictions`.
- Produzione e attività: `vineyardArea`, `wineProductionAnnualBottles`, `oliveTreeCount`, `productionDOCStatus`.
- Compliance & disclosure: `amlPreScreeningRequired`, `nonDisclosureExpected`.
- Spazi e amenities tipici luxury: `wineCellar`, `cinemaRoom`, `spaPrivate`, `mooring`, `staffQuarters`.

**Perché lo fai.** Non per essere altruista. Per essere lo standard. Quando Lionard, Knight Frank, Sotheby's si svegliano a fare il loro AI site, il loro IT chiede: "che ontologia usiamo?". Risposta: "quella di DigIdentity, è lo standard". E quando devono implementarla, ti chiamano. Consulenza €30-80k/progetto, ticket alto, margine 90%, e ti porta dentro le loro data.

**Repo separato.** `digidentity-ontology` pubblico, distinto dal repo principale (privato).

---

## 14. Decisioni infrastrutturali da prendere

Queste sono le decisioni che vanno chiuse in Phase 0-1 con ADR dedicati.

**ADR-007: Cloud production.** Cloudflare Pages + Workers per frontend/edge. Per backend: Fly.io (semplicità) vs AWS (Activate credits) vs Hetzner (costo). Decisione preliminare: Fly.io per velocità di deploy primi 6 mesi, AWS per migrazione mese 6+ se i credits Activate arrivano.

**ADR-008: Postgres production.** Neon (serverless, branching) vs Supabase (full stack) vs RDS. Decisione preliminare: Neon per branching su PR (game-changer per CI).

**ADR-009: Voice provider production.** LiveKit Cloud vs self-hosted LiveKit. Decisione preliminare: LiveKit Cloud primi 6 mesi, valutazione self-host se costo > €500/mese.

**ADR-010: Annotation tool.** Build interno minimal vs Argilla/Label Studio. Preliminare: build interno minimal (1 settimana) per controllo totale.

---

## 15. Esecuzione assistita: setup Claude Code

Questa è la sezione che rende la BIBLE v3 implementabile a velocità massima. Configurazione pronta per Claude Code, con subagents, skills, plugins e hooks specifici per DigIdentity.

### 15.1 CLAUDE.md root del repo

File `CLAUDE.md` nella root del repo, sempre caricato come contesto persistente:

```markdown
# DigIdentity Living Site — Project Conventions for Claude Code

## Authority
- BIBLE-v3.md is the source of truth. Cite section numbers in commits/PRs.
- Stack and architectural decisions live in BIBLE §9 + docs/adr/.
- Never deviate from BIBLE without proposing an ADR first.

## Code style
- Python: 3.13, ruff + black, mypy strict, async-first, type hints everywhere.
- TypeScript: 5.x, biome, strict mode, no any.
- SQL: snake_case, explicit FK, RLS on every tenant-scoped table.

## Multi-tenant discipline
- Every DB query that touches tenant data MUST run inside a transaction with
  `SET LOCAL app.tenant_id = :id`. Use the `with_tenant(tenant_id)` context manager.
- Never assume connection state; always set tenant explicitly per request.

## Fat core / Lean packs
- Never add client-specific code to /core. Use packs/<vertical>/ or tenant.yaml.
- New cross-vertical pattern? Promote to /core only after 2+ packs need it.

## Workflow
- Trunk-based dev, feature branches < 3 days.
- Conventional commits scoped by engine or pack.
- ADR before non-trivial architectural changes.
- Eval pack regression blocks merge.

## Never do
- Commit secrets, .env, API keys.
- Bypass RLS with admin queries in production code paths.
- Add `if tenant_id == "specific"` anywhere. That's a Pack signal.
- Modify the morph DSL primitives without ADR.

## When unsure
- Check BIBLE §N first.
- Check docs/adr/.
- Ask for spec, don't guess on architecture.
```

### 15.2 Subagents in `.claude/agents/`

Quattro subagent specializzati che Claude Code può invocare automaticamente o esplicitamente.

**`.claude/agents/architect.md`** — coordina decisioni architetturali, scrive ADR draft, valuta promozione core/pack.

```yaml
---
name: architect
description: Use proactively when architectural decisions are needed, when promoting code from pack to core, when proposing ADRs, or when a change spans multiple engines. Specializes in BIBLE v3 and ADR workflow.
tools: Read, Glob, Grep, Write, Edit
model: opus
memory: project
---
You are the architecture guardian for DigIdentity Living Site.

Before any architectural decision:
1. Read the relevant BIBLE-v3.md sections.
2. Scan docs/adr/ for related decisions.
3. Identify whether the change is core-level or pack-level (BIBLE §5).
4. Draft an ADR using docs/adr/_template.md if the change is non-trivial.

When in doubt, prefer pack-level over core-level. The core stays small.

Output structure for any architectural recommendation:
- Context (what's the problem)
- Options considered (2-3 alternatives)
- Decision (chosen path + why)
- Consequences (positive + negative + neutral)
- Migration / rollout plan
```

**`.claude/agents/pack-builder.md`** — costruisce e mantiene Pack verticali.

```yaml
---
name: pack-builder
description: Use when creating or modifying a vertical Pack (packs/<vertical>/). Specializes in pack structure, morph DSL, personas, prompts, scoring scorecards, and golden datasets.
tools: Read, Write, Edit, Glob, Bash
model: sonnet
skills:
  - morph-dsl
  - pack-structure
  - prompt-conventions
---
You build and maintain DigIdentity Packs.

Mandatory pack structure (BIBLE §5):
packs/<name>/
  pack.yaml
  ontology/
  personas/
  morph_rules/
  prompts/
  components/
  tools/
  scoring/
  golden_dataset/
  README.md

Rules:
- Every morph rule passes the DSL JSON Schema validator.
- Every Pack ships ≥50 golden conversations in JSONL.
- Personas reference back to scoring scorecard signals.
- Pack version follows semver: breaking changes bump major.

Before shipping a Pack:
- Run `tools/lint-pack/main.py packs/<name>`.
- Run eval against the golden dataset (threshold ≥90% pass).
- Verify tenant.yaml example exists for at least one tenant of this vertical.
```

**`.claude/agents/engine-implementer.md`** — implementa codice negli engine core.

```yaml
---
name: engine-implementer
description: Use for implementing or modifying any of the 7 core engines (KG, Adaptive Renderer, Conversational Renderer, Agent Orchestrator, Spatial, Static Manifestation, Learning). Strict adherence to BIBLE §6.
tools: Read, Write, Edit, Glob, Grep, Bash
model: sonnet
skills:
  - python-async-conventions
  - sqlalchemy-rls
  - fastapi-streaming
  - typescript-rsc
---
You implement core engine code.

Hard rules:
1. Always read BIBLE-v3.md §6.X for the relevant engine before coding.
2. Multi-tenant: use the `with_tenant()` context manager. Period.
3. Async-first Python. No sync DB calls in request paths.
4. Streaming for any LLM call. No buffered responses to clients.
5. Every external API call has timeout, retry with exponential backoff, circuit breaker.
6. Tests in same PR. Unit + integration for the rotation touched.
7. Type-safe end-to-end. Pydantic for inputs, typed outputs everywhere.

Output structure for implementation tasks:
- Files to modify (with reason)
- Files to create (with role)
- Migration impact (DB schema, env vars)
- Test plan
- Then proceed.
```

**`.claude/agents/eval-runner.md`** — esegue eval pack, valuta regressioni.

```yaml
---
name: eval-runner
description: Use for evaluating prompt/agent changes against golden datasets, running pack regression tests, and producing eval reports. Specializes in promptfoo + custom DigIdentity eval harness.
tools: Read, Bash, Glob
model: haiku
---
You run evals.

Workflow:
1. Identify the changed pack(s) or core agent code.
2. Run `make eval PACK=<name>` (or full suite if core changed).
3. Parse results, identify regressions vs baseline.
4. For any regression, produce a delta report with:
   - Failing scenario(s)
   - Expected vs actual
   - Hypothesis on root cause
5. If pass rate ≥ threshold, output green report.
6. If regression, never auto-fix — escalate to engine-implementer or pack-builder.
```

### 15.3 Skills in `.claude/skills/`

Skills sono auto-invocate da Claude Code quando il contesto matcha. Sono caricate dal subagent appropriato.

Cartelle:

- `.claude/skills/morph-dsl/SKILL.md` — sintassi DSL, esempi, validatore.
- `.claude/skills/pack-structure/SKILL.md` — struttura canonica Pack, checklist creazione.
- `.claude/skills/prompt-conventions/SKILL.md` — convenzioni per system prompts e tool descriptions (XML-tagged structure, role definitions, few-shot patterns).
- `.claude/skills/python-async-conventions/SKILL.md` — async patterns, error handling, retry policies.
- `.claude/skills/sqlalchemy-rls/SKILL.md` — RLS context manager usage, transaction discipline.
- `.claude/skills/fastapi-streaming/SKILL.md` — SSE patterns, error in stream, backpressure.
- `.claude/skills/typescript-rsc/SKILL.md` — React Server Components patterns, RSC <-> client boundaries.
- `.claude/skills/eval-authoring/SKILL.md` — come scrivere golden dataset entries, asserzioni semantiche.

Ogni skill è ~50-150 righe di Markdown con esempi concreti dal repo. Trigger via descrizione frontmatter + auto-discovery di Claude Code.

### 15.4 Slash commands in `.claude/commands/`

Workflow ricorrenti come comandi rapidi.

- `/new-adr` — scaffold di nuovo ADR con template + numerazione progressiva.
- `/new-pack <name>` — scaffold completo di nuovo Pack vuoto.
- `/run-eval <pack>` — invoca `eval-runner` con il Pack target.
- `/promote-to-core` — invoca `architect` per valutare promozione di codice da Pack a core.
- `/dev-up` — bash che fa `docker-compose up -d`, migrazioni, seed, healthcheck.
- `/tenant-test` — esegue il test di leak cross-tenant.

### 15.5 Hooks in `.claude/hooks/`

Regole deterministiche enforce-side.

- `pre-commit-secrets` — blocca commit di pattern API key tipici (sk-, anthropic-, AKIA, ecc.).
- `pre-merge-eval` — non permette merge se eval del Pack toccato è in regressione.
- `pre-deploy-rls-check` — verifica che ogni route tenant-scoped usa `with_tenant`.
- `post-edit-sql-format` — formatta SQL con `sqlfluff`.

### 15.6 Plugin distribution

`digidentity-toolkit` come plugin interno, distribuibile via marketplace privato (GitHub repo privato), bundle di tutti i subagents + skills + commands sopra. Versionato. Permette di avere stesso setup su qualsiasi macchina dove gira Claude Code.

### 15.7 MCP servers configurati

MCP server da connettere a Claude Code per sviluppo:

- **Filesystem MCP** (built-in) — accesso al repo.
- **Postgres MCP** custom — query introspettive sul DB locale (schema, sample data, EXPLAIN su query in sviluppo).
- **GitHub MCP** — issues, PR review, CI status.
- **Linear MCP** o Notion MCP — per il backlog progetto, se userai uno dei due.

---

## 16. ADR pending (lista)

ADR da scrivere in Phase 0-1, in ordine di priorità:

- ADR-001: Stack canonico (Python 3.13, Next.js 15, Postgres 16+pgvector, Cloudflare).
- ADR-002: Transport multi-modale (SSE testo, WebRTC voce via LiveKit, channel-extensible).
- ADR-003: Tenant isolation discipline (RLS + context manager + test).
- ADR-004: LLM Router (Sonnet 4.6 default, Opus 4.7 upgrade, GPT-5 fallback, circuit breaker).
- ADR-005: Multi-embedding strategy (content/lifestyle/features, text-embedding-3-large).
- ADR-006: Composite metric per Learning Engine.
- ADR-007: Cloud production (Fly.io primi 6 mesi, valutazione AWS).
- ADR-008: Postgres production (Neon con branching).
- ADR-009: Voice provider production (LiveKit Cloud).
- ADR-010: Annotation tool (build interno minimal).
- ADR-011: Adaptive Renderer architecture (Decision Engine, DSL evaluator, audit).
- ADR-012: Atomic chat transaction + idempotency key (fix tech-debt v2).

---

## 17. Pricing & GTM (allineato alla visione, da affinare nel tempo)

Questa sezione è "preliminare" e va riconfermata dopo le prime 3 sales call. Comunque parte tecnica e parte commerciale stanno qui per coerenza.

**Posizionamento.** Il primo sito web abitabile per MPMI ad alto valore percepito.

**Tier preliminari (real-estate-luxury italia, Phase 2-3):**

- Pilot: €4.500 setup + €1.500/mese, 6 mesi minimo. Solo primi 5 clienti.
- Professional: €9.000 setup + €2.900/mese.
- Luxury: €15.000 setup + €5.900/mese.
- Bespoke: €25.000+ setup + €9.900+/mese, custom Pack derivati, integrazione CRM proprietario, voice premium.

Niente Starter sotto €1.500/mese. Esperienza dice che sotto si attirano clienti rompiscatole, non aspirazionali.

**Beachhead ICP rivisto (rispetto a v2).**

Agenzie boutique mono-fondatore con 1-3 agenti, fondatore decisore unico, 5-15M€ transato/anno. Ciclo di vendita 4-6 settimane. Lionard/Sotheby's restano target Phase 5+ con motion enterprise dedicato.

**Sales motion Phase 1-2.**

Outbound caldo: 20 agenzie luxury Italia/anno target. Demo live `demo.digidentity.agency` come asset principale. Articolo founder + manuale 18° (uscita 2026) come amplificatore credibilità.

---

## 18. Operational principles aggiornati

- 70%+ tempo su Living Site nei primi 18 mesi. Confermato da v2.
- No new projects per 90 giorni dall'inizio Phase 1. Idee → `docs/inbox/IDEAS-PARKING-LOT.md`.
- AI-assisted development discipline: Claude Code è il primary IDE companion. Subagents + skills + plugins come da §15.
- Journaling giornaliero in `docs/journal/YYYY-MM-DD.md` quando si avanza significativamente.
- ADR per ogni decisione architetturale.
- BIBLE v3 review trimestrale: prima il 14 agosto 2026, valutare se serve v3.1 o v4.

---

## 19. Cosa NON è DigIdentity Living Site

Per chiarezza, lista delle cose che non costruisci. Aiuta a dire di no.

- Non è un CRM. Si integra ai CRM esistenti del cliente.
- Non è un MLS / portale di annunci. Espone le proprietà del cliente, non aggrega listing terzi.
- Non è un chatbot widget. Il chat è un manifestazione di un sito che vive, non un widget bolted-on.
- Non è una piattaforma no-code per non-developer. È SaaS managed: il cliente compra un servizio, non un tool da configurare.
- Non è multi-canale unificato (omnichannel CX) tipo Sierra. Il primo prodotto vive nel sito web. WhatsApp/telefonia/email arrivano come canali aggiuntivi del sito, non viceversa.
- Non è generatore di contenuti AI. Il copy e i contenuti li scrive il cliente (eventualmente assistito).

---

## 20. Glossario veloce

- **Pack**: bundle verticale (ontologia + personas + morph rules + prompts + components + tools + scoring + golden dataset). Vedi §5.
- **Morph**: trasformazione del sito basata su VisitorPrior. Vedi §2.2 + §8.
- **VisitorPrior**: probabilità inferita su personas, prodotta da Sense. Vedi §7.1.
- **Rendering Directive**: istruzione emessa dall'agente per modificare il sito durante la conversazione. Vedi §7.2.
- **Decision Engine**: cuore dell'Adaptive Renderer, valuta morph rules + agent directives. Vedi §6.2.
- **Tenant config (tenant.yaml)**: unico luogo legittimo per configurazioni cliente-specifiche.
- **Bible Rule**: requisiti per aprire nuovo verticale (≥25 paying clients, ≥€500k ARR, mercato verticale >1000 prospects nel verticale attivo). Eredità da v2.
- **GEO**: Generative Engine Optimization. Ottimizzazione per essere letti correttamente da LLM e AI search engine, non solo Google classico.

---

**Fine BIBLE v3.**

Ogni dubbio, prima di chiedere: leggi §N. Se la risposta non c'è, proponi un ADR.
