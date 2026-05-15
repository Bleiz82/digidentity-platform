# ADR-002: Transport Multi-Modale per Conversational Renderer

- **Status**: proposed
- **Date**: 2026-05-14
- **Authors**: Stefano Corda
- **BIBLE refs**: §6.3, §6.4, §6.2, §2.1, §2.3, §9
- **Supersedes**: n/a
- **Superseded by**: n/a

---

## Contesto

Il DigIdentity Living Site espone tre layer di trasporto distinti con requisiti di latenza e semantica diversi:

1. **Testo conversazionale** — stream di chunk LLM dal server al browser, input testuale dall'utente. Budget TTFC ≤ 800 ms (§2.3: *"TTFC (time-to-first-chunk) ≤ 800 ms"*). Il percorso critico passa per Cloudflare.
2. **Voce real-time** — round-trip audio browser ↔ agente Python. Budget TTFC voice ≤ 500 ms (§2.3: *"TTFC voice ≤ 500 ms"*).
3. **State sync UI** — patches del DOM React (RFC 6902 JSON Patch) emesse dall'agente durante Converse/Inhabit. Budget ≤ 100 ms dall'emit al DOM update (§6.2).

Le tre aree sono architetturalmente indipendenti. Questo è un **ADR di ratifica**: le scelte sono già consolidate nella BIBLE v3. Lo scopo è fissare il ragionamento storico che ha portato a scartare le alternative.

**Vincoli trasversali:**
- Cloudflare come proxy full (non solo DNS) con comportamenti specifici su SSE, WebSocket upgrade, timeout.
- Multi-tenancy: ogni tenant.yaml dichiara i canali attivi. Il transport deve essere selezionabile per tenant a runtime, non a compile time.
- Agent Orchestrator (§6.4) è **agnostico al canale**: il cervello non sa su quale transport stanno arrivando i token. Questo vincolo di disaccoppiamento è non negoziabile.
- Latency budget Sense (edge): *"50 ms al massimo, eseguito su edge (Cloudflare Workers)"* (§2.1) — rilevante per il path di autenticazione dei WebSocket.

---

## Opzioni considerate

---

### Area A — Transport testo conversazionale

#### A1 — Server-Sent Events (SSE) su HTTP/1.1 e HTTP/2 *(scelta adottata)*

SSE è un protocollo HTTP standard (WHATWG EventSource): il server mantiene una risposta chunked aperta e invia eventi `text/event-stream`. Il client usa fetch-based streaming (non `EventSource` nativo) per supportare headers `Authorization` e metodo POST.

**Latenza TTFC stimata:**
- HTTP/2: 40–80 ms overhead di connessione (TLS già negoziata). Con Claude Sonnet 4.6 cachato: TTFC ≈ 250–450 ms end-to-end (§6.4).
- Nessun overhead di framing aggiuntivo: SSE è testo puro su TCP, il primo byte parte con il primo token LLM.

**Overhead per connessione concorrente (lato server):**
- ~2–4 KB di stack per coroutine asyncio. 10.000 connessioni concorrenti ≈ 20–40 MB di overhead coroutine, più buffer TCP OS (~4–8 KB send buffer per socket). Ordine di grandezza: 100–200 MB per 10K conn su un server da 4 core.
- Nessun handshake di upgrade: risparmio rispetto a WebSocket di circa 1 RTT per nuova connessione.

**Comportamento dietro Cloudflare:**
- Cloudflare supporta SSE in modalità pass-through **a condizione** che la risposta includa `Cache-Control: no-cache` e `X-Accel-Buffering: no`. Senza questi header, Cloudflare bufferizza il corpo e lo rilascia solo alla chiusura — annullando lo streaming silenziosamente.
- Con gli header corretti, Cloudflare non bufferizza. Test empirici (2024-2025) confermano latenza aggiuntiva ≤ 100 ms su edge europei.
- Timeout Cloudflare su SSE idle: default 100 s. Il server deve inviare commenti SSE (`: ping`) ogni 15–20 s per mantenere la connessione viva attraverso proxy intermedi.
- Cloudflare fa HTTP/2 tra client e edge, HTTP/1.1 tra edge e origin per default. Il multiplexing HTTP/2 aiuta lato client ma non elimina la necessità degli header anti-buffering lato origin.

**Costo di reconnect:**
- `EventSource` nativo riconnette automaticamente con backoff inviando `Last-Event-ID`. Il server deve mantenere gli ultimi N eventi in Redis per permettere la ripresa. Senza questa gestione esplicita, ogni reconnect ricomincia da capo.
- Con gestione corretta: interruzione ≤ 1–2 s per l'utente.

**Supporto browser/mobile 2026:**
- Fetch streaming API: supportata al ~99% dei browser moderni. Nessun problema su iOS Safari, Chrome Android.
- `EventSource` nativo (alternativa): 98,7% copertura ma non supporta headers custom né POST.

**Fallback se SSE fallisce dietro proxy corporate aggressivo:**
Proxy come Zscaler, BlueCoat, Cisco WSA possono: (a) disabilitare `Transfer-Encoding: chunked`, (b) terminare connessioni idle dopo 30–60 s, (c) bloccare connessioni HTTP con body "aperto". La strategia adottata è **long-polling degradato (A3)**, attivato automaticamente se il client non riceve chunk entro 5 s. L'alternativa di accettare il fallimento è stata scartata perché tenant enterprise in contesti corporate sono un caso d'uso primario.

---

#### A2 — WebSocket bidirezionale

WebSocket fornisce un canale full-duplex persistent con overhead di framing di 2–14 byte per frame.

**Latenza TTFC stimata:**
- Aggiunge 1 RTT di handshake HTTP Upgrade rispetto a SSE su connessione nuova. Su connessioni riutilizzate, SSE su HTTP/2 è più efficiente (multiplexing).

**Overhead per connessione concorrente:**
- Simile a SSE. Ma: WebSocket richiede **sticky session / session affinity** in cluster (il socket è pinned a un processo). Con SSE su HTTP/2, ogni request può andare su qualsiasi instance — lo stato conversazionale è su Redis, il server è stateless.

**Comportamento dietro Cloudflare:**
- WebSocket supportato da Cloudflare Pro+, ma: l'upgrade richiede piano Pro per sessioni > 100 s; Cloudflare non supporta HTTP/2 WebSocket (RFC 8441) — downgrade a HTTP/1.1, nessun multiplexing; in caso di errore backend Cloudflare invia frame `1001 Going Away` senza propagare il codice errore origin (debugging opaco).

**Perché scartato per il testo:**
Il trasporto testo è intrinsecamente **monodirezionale** durante lo streaming (server → client). L'input utente è discreto e non richiede bidirezionalità continua. WebSocket aggiunge complessità (session affinity, reconnect custom, gestione stato socket) senza vantaggio di latenza misurabile. La bidirezionalità WebSocket è la scelta corretta per Area C. Usare WebSocket anche per il testo avrebbe creato o due WebSocket per conversazione, o un multiplexing applicativo sopra WebSocket — reinventare HTTP/2.

---

#### A3 — Long-polling (modalità fallback)

Il client invia `GET /conversations/{id}/poll?after={seq}`, il server trattiene la risposta finché non ci sono nuovi chunk, risponde con tutti i chunk accumulati dall'ultimo `seq`.

**Latenza TTFC:**
- Aggiunge 1 RTT per ogni batch di chunk. Con token LLM a ~30–50 token/s, una risposta accumulata ogni 200 ms introduce latenza percepibile: il testo arriva a blocchi, non a token. Non accettabile come modalità primaria.

**Perché incluso:**
Fallback di degradazione per ambienti proxy aggressivi. In questa modalità la UX è degradata (testo a blocchi) ma la conversazione funziona. Il `last_seq` viene persistito in localStorage per sopravvivere a page refresh.

---

### Area B — Transport voce real-time

#### B1 — LiveKit Agents Python SDK 1.5.x *(scelta adottata)*

LiveKit è open-source (Apache 2.0). LiveKit Agents 1.5.x orchestra VAD, STT, LLM, TTS in un loop event-driven con native MCP support.

**Latenza end-to-end (mouth-to-ear) stimata:**
- WebRTC capture → LiveKit ingest: 20–40 ms
- VAD (Silero, turn detection): 100–200 ms
- STT (Deepgram Nova-3, streaming): 100–200 ms
- LLM (Claude Sonnet 4.6, cached): 250–400 ms TTFC
- TTS (Cartesia Sonic, streaming): 100–200 ms primo chunk audio
- WebRTC playout: 20–40 ms
- **Totale stimato: 590–1.080 ms** in fast-path ottimizzato. Il budget ≤ 500 ms TTFC è raggiungibile solo sul primo chunk audio con LLM cached nella parte bassa (~250 ms) e TTS a 100 ms; mouth-to-ear completo supera i 500 ms sul caso medio.

**Costo per minuto (giugno 2026, stime da pricing pubblico 2024-2025 — verificare al procurement nel 2026):**
- LiveKit Cloud: ~$0,006–0,008/min/partecipante. A 1.000 min/mese: ~$6–8. A 100.000 min/mese: ~$600–800. *(Pricing non è listino fisso — verificare con LiveKit sales.)*
- Self-hosted su Hetzner CCX23 (8 vCPU, 16 GB, ~$440/mese): ~500–1.000 rooms concorrenti leggere. A 100K min/mese indicativamente < $0,005/min.
- STT Deepgram Nova-3: $0,0043/min. TTS Cartesia Sonic: ~$0,006/min. LLM: $3/$15 per M token (Sonnet input/output).

**Vendor lock-in:**
- LiveKit Server è **open-source (Apache 2.0)**. Il media stream appartiene al tenant: nessun audio transita per server LiveKit Inc. in modalità self-hosted.
- Pipeline STT/TTS/LLM è modulare: ogni componente è sostituibile con un plugin.
- Migrazione da LiveKit Cloud a self-hosted: solo cambio di `url` e `api_key` nel config. Nessun lock-in architetturale.

**Maturità SDK Python 1.5.x:**
- Versione 1.5.x rilasciata Q1 2025, produzione-ready. Documentazione completa, changelog attivo. Integrazione nativa Claude: `livekit.plugins.anthropic`.

---

#### B2 — Twilio Voice / ConversationRelay

**Latenza end-to-end:**
- Twilio introduce un hop PSTN/media server fisso: latenza aggiuntiva 200–400 ms rispetto a WebRTC puro. Mouth-to-ear tipico: 800–1.200 ms. **Non rispetta il budget ≤ 500 ms.**

**Costo per minuto (pricing 2024-2025 — verificare al procurement nel 2026):**
- Twilio Voice + ConversationRelay (STT+TTS Twilio inclusi): stima $0,02–0,03/min. A 1.000 min/mese: ~$20–30. A 100K min/mese: $2.000–3.000. Significativamente più caro di LiveKit self-hosted.

**Vendor lock-in:**
- Fortissimo. Il media transita per i server Twilio. Nessuna opzione self-host. Audio processato da infrastruttura Twilio (US-based per default). GDPR: certificazioni disponibili ma dati audio su infrastruttura US su piani standard.

**Perché scartato:** Latenza fuori budget, costo 3–5x rispetto a self-hosted LiveKit, vendor lock-in sul media stream incompatibile con i requisiti di privacy tenant EU.

---

#### B3 — Vapi / Retell AI (categoria: managed voice AI)

**Latenza:**
- Vapi dichiara < 800 ms mouth-to-ear. Retell dichiara < 600 ms. **Non garantiscono il budget ≤ 500 ms.**

**Costo per minuto (pricing 2024-2025 — verificare al procurement nel 2026):**
- Vapi: ~$0,05/min all-inclusive. A 1.000 min/mese: ~$50. A 100K min/mese: $5.000.
- Retell: ~$0,034/min. A 1.000 min/mese: ~$34. A 100K min/mese: $3.400.
- Confronto: 5–10x rispetto a LiveKit self-hosted.

**Vendor lock-in:**
- Massimo. Media transita per server vendor. Nessuna opzione self-host. Accesso ai raw audio: limitato o assente. Impossibile GDPR-compliant deletion granulare.

**Perché scartato:** Costo proibitivo a scala, vendor lock-in sul media stream, impossibilità di self-host per tenant con requisiti GDPR stringenti.

---

### Area C — Transport state sync UI

#### C1 — WebSocket con JSON Patch RFC 6902 *(scelta adottata)*

**Latenza:**
- Una patch JSON di 200 byte arriva in ≤ 5 ms su rete locale, ≤ 30–50 ms over internet. Budget di 100 ms dall'emit al DOM update abbondantemente rispettato per patches di dimensione ragionevole.
- Bidirezionale: il client può confermare l'applicazione della patch (ACK), permettendo al server di rilevare drift di stato.

**Perché WebSocket e non SSE per le patches:**
- Le patches UI sono intrinsecamente bidirezionali: il server deve sapere se il client ha applicato la patch correttamente. SSE è monodirezionale.
- Mescolare patches e testo sullo stesso canale SSE (con `type` discriminator) è possibile, ma combina semantiche diverse e fa diventare il Conversational Renderer responsabile di routing applicativo — violando il principio di responsabilità singola.
- Il canale separato mantiene il disaccoppiamento: Conversational Renderer non conosce le patches, il Patch Engine non conosce il testo.

**Comportamento dietro Cloudflare:**
- WebSocket su Cloudflare Pro+: supportato. Session affinity richiesta.

**Alternative scartate:**
- *HTTP PATCH polling*: latenza ≥ polling interval (100–500 ms), non rispetta il budget di 100 ms.
- *gRPC streaming bidirezionale*: overhead di setup (proxy Envoy/grpc-gateway) sproporzionato; gRPC-Web non supporta bidirezionale completo in browser.

---

## Decisione

**Area A — Testo:** SSE fetch-based su `GET /conversations/{id}/stream`. Headers obbligatori: `Cache-Control: no-cache`, `X-Accel-Buffering: no`. Ping SSE ogni 15 s. Fallback automatico a long-polling se assenza di chunk entro 5 s. Type discriminator `"text" | "directive" | "directive_batch"` su ogni evento (§6.3).

**Area B — Voce:** LiveKit Agents Python SDK 1.5.x. Deploy iniziale su LiveKit Cloud; migrazione a self-hosted su VPS EU alla soglia di 50.000 min/mese. Pipeline: WebRTC → LiveKit → Deepgram Nova-3 STT → Claude Sonnet 4.6 → Cartesia Sonic TTS. Feature flag per voce nel tenant.yaml.

**Area C — State sync UI:** WebSocket separato su `/conversations/{id}/patches`. JSON Patch RFC 6902. Autenticato con stesso JWT della sessione. Reconnect con full-state request.

---

## Conseguenze

### Positive

- Disaccoppiamento canale-cervello rispettato: il cambio futuro di transport non tocca l'Agent Orchestrator.
- SSE riduce la complessità di session affinity: ogni request è HTTP stateless fino al primo chunk; load balancing senza sticky sessions.
- LiveKit self-hostable: nessun audio tenant EU su server di terze parti in modalità self-hosted.
- Long-polling fallback automatico: supporto per ambienti enterprise con proxy aggressivi senza configurazioni lato cliente.
- JSON Patch RFC 6902 è standard: librerie disponibili in ogni linguaggio, debuggabile senza tooling speciale.

### Negative

- **Header SSE critici silenziosi**: `Cache-Control: no-cache` e `X-Accel-Buffering: no` devono essere presenti su ogni risposta SSE. Un deploy che dimentica questi header causa buffering silenzioso (il client vede la risposta solo a fine stream, senza errore esplicito). Il bug è difficile da rilevare in staging dove spesso non c'è Cloudflare. Richiede test di integrazione con proxy locale che simuli il buffering Cloudflare.

- **Proxy corporate non è gestibile completamente**: anche con fallback a long-polling, alcuni proxy bloccano connessioni HTTP "aperte" tramite DPI. La UX in fallback long-polling è degradata (testo a blocchi). Non c'è soluzione tecnica: è un limite del deployment environment del cliente.

- **LiveKit Cloud è un single point of failure esterno**: outage LiveKit Cloud interrompe la voce su tutti i tenant non ancora su self-hosted. Vedi Questione Aperta #6 per la strategia di fallback voce → testo.

- **Latenza mouth-to-ear ≤ 500 ms è condizionale**: raggiungibile solo con LLM cached nella parte bassa (~250 ms) e TTS a ~100 ms. Con LLM in fallback su GPT-5 (TTFC 400–600 ms) o rete congestionata, il budget si sfora. La UI deve comunicare esplicitamente quando la risposta è lenta.

- **WebSocket per patches richiede session affinity**: a differenza di SSE, il WebSocket è pinned a una singola istanza server. In caso di crash del server, la sessione è persa. Il client deve essere progettato per riconnessione con full-state request, altrimenti il DOM può divergere dallo stato server in modo silenzioso.

- **Due connessioni persistenti per sessione attiva (SSE + WebSocket)**: su mobile e reti instabili la gestione di due connessioni indipendenti aumenta la probabilità di stati parzialmente disconnessi. Il server deve gestire gracefully la chiusura indipendente di entrambe le connessioni.

- **Costo operativo della pipeline voce richiede monitoring su tre vendor**: Deepgram (STT), Cartesia (TTS), LiveKit (media). Un degrado su uno dei tre si manifesta come degrado dell'esperienza complessiva senza errore esplicito. Chi debugga alle 3 di notte deve avere accesso alle dashboard di tutti e tre i vendor simultaneamente, oltre al monitoring FastAPI standard.

- **Sicurezza canale voce (GDPR)**: nella fase iniziale (LiveKit Cloud), il media audio dei tenant europei transita per server LiveKit Inc. (US-based). Azioni richieste prima del go-live con tenant EU: (a) firma DPA con LiveKit Inc., che deve dichiarare esplicitamente che LiveKit Cloud è un media relay puro senza registrazione audio; (b) completare migrazione a self-hosted su VPS EU in alternativa. Anche su self-hosted: Deepgram Cloud per STT invia l'audio a Deepgram (US) — valutare Deepgram EU endpoint o Whisper.cpp self-hosted per tenant con requisiti stringenti, accettando latenza STT maggiore. Analoga valutazione per TTS (vedi Questione Aperta #7).

### Neutre

- Il discriminator `type: "text" | "directive" | "directive_batch"` sul canale SSE introduce un parser minimo lato client (~30 righe), conforme alla struttura SSE standard, senza dipendenze esterne.
- La scelta di fetch-based streaming invece di `EventSource` nativo segue il pattern già usato da Anthropic e OpenAI nei loro SDK: la utility wrapper è boilerplate standard.

---

## Piano di migrazione / rollout

**Fase 1 — Testo SSE (v3.0, sprint attuale)**
- [ ] Implementare rotta `GET /conversations/{id}/stream` con header Cloudflare-safe.
- [ ] Implementare ping SSE ogni 15 s lato server.
- [ ] Implementare rilevamento fallback lato client (timeout 5 s → long-polling).
- [ ] Test di integrazione con proxy locale che simula buffering Cloudflare (nginx con `proxy_buffering on`).
- [ ] Monitoring: latenza TTFC p50/p95/p99, percentuale sessioni in fallback long-polling per tenant.

**Fase 2 — Voce LiveKit Cloud (v3.1, post-alpha)**
- [ ] Setup LiveKit Cloud account, firma DPA, configurazione room per tenant con voce abilitata.
- [ ] Implementare pipeline Python: Deepgram STT + Claude Sonnet + Cartesia TTS.
- [ ] Feature flag voce nel tenant.yaml.
- [ ] Test latenza mouth-to-ear in condizioni normali e con LLM in fallback.
- [ ] Alerting: latenza STT > 300 ms, latenza TTS > 300 ms, LLM TTFC > 600 ms.

**Fase 3 — Migrazione LiveKit self-hosted (soglia: 50K min/mese)**
- [ ] Deploy LiveKit Server su VPS EU (Hetzner Falkenstein o Hostinger EU datacenter).
- [ ] Configurare TURN server per reti restrittive.
- [ ] Aggiornare `LIVEKIT_URL` e `LIVEKIT_API_KEY` in env per tenant.
- [ ] Test failover: LiveKit Cloud come backup se self-hosted è down.

**Fase 4 — WebSocket patches UI (v3.x, Converse/Inhabit)**
- [ ] Implementare WebSocket endpoint `/conversations/{id}/patches`.
- [ ] Configurare session affinity su Cloudflare.
- [ ] Implementare reconnect con full-state request sul client.
- [ ] Test: il DOM deve convergere allo stato corretto dopo disconnessione e riconnessione.

---

## Questioni aperte

1. **DPA LiveKit per tenant EU**: da finalizzare prima del lancio voce. Self-hosted Hetzner EU come piano B immediato se i tempi DPA si allungano.

2. **Deepgram EU endpoint**: da verificare la disponibilità di datacenter EU a condizioni accettabili. Se non disponibile, valutare Whisper.cpp self-hosted per tenant con requisiti GDPR stringenti (benchmark latenza STT richiesto).

3. **Soglia esatta di migrazione a LiveKit self-hosted**: 50K min/mese è stima. Da rivedere al primo billing LiveKit Cloud reale.

4. **Gestione disconnessione WebSocket mid-patch**: se il WebSocket si disconnette mentre una patch è in transito, il DOM client può divergere. Il protocollo di reconnect con full-state request richiede che il server mantenga il full-state della UI in sessione (Redis o in-memory). La struttura di questo store non è ancora definita.

5. **Long-polling fallback: persistenza del `last_seq`**: il client deve persistere il `last_seq` in localStorage per sopravvivere a page refresh. Comportamento da definire se il server ha già purgato i chunk precedenti al `seq` salvato (full-restart della conversazione vs errore esplicito).

6. **Circuit breaker voce**: in caso di errore prolungato del canale voce, il sistema deve fare graceful fallback al canale testo con messaggio UI esplicito all'utente ("la voce non è disponibile, continua in chat"). Parametri da definire: soglia per attivazione fallback (N errori consecutivi o timeout), tempo di cooldown prima del retry automatico, azione utente per forzare il retry. Il fallback deve essere reversibile senza page reload.

7. **Alternative TTS EU-compliant per tenant con requisiti GDPR stringenti**: Cartesia Sonic è US-based. Per tenant europei con obblighi di localizzazione del dato audio, valutare: Piper TTS self-hosted (open-source, qualità inferiore ma latenza locale), XTTS-v2 self-hosted (qualità alta, GPU raccomandata), ElevenLabs EU endpoint (da verificare disponibilità). Benchmark di latenza e qualità voce richiesto prima del lancio della funzione voce per tenant EU.

---

## Riferimenti

- BIBLE v3 §6.3 — Conversational Renderer Engine
- BIBLE v3 §6.4 — Agent Orchestrator Engine (latenza LLM)
- BIBLE v3 §6.2 — Adaptive Renderer (budget JSON Patch)
- BIBLE v3 §2.1 — Sense: *"Latency budget: 50 ms al massimo, eseguito su edge (Cloudflare Workers)"*
- BIBLE v3 §2.3 — Converse: *"Latency budget: TTFC (time-to-first-chunk) ≤ 800 ms; TTFC voice ≤ 500 ms"*
- BIBLE v3 §9 — Stack tecnologico (voce)
- WHATWG EventSource specification
- Cloudflare SSE documentation — buffering behavior
- LiveKit Agents Python SDK 1.5.x — changelog e documentazione
- RFC 6902 — JSON Patch
- Deepgram Nova-3 — latency benchmarks
- ADR-001 — Stack canonico (contesto stack generale)
