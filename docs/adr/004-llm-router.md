# ADR-004: LLM Router — Strategia di routing, circuit breaker e cost tracking

- **Status**: proposed
- **Date**: 2026-05-14
- **Authors**: Stefano Corda
- **BIBLE refs**: §6.4, §9, §2.3
- **Supersedes**: n/a
- **Superseded by**: n/a

---

## Contesto

Il sistema DigIdentity Living Site espone un Agent Orchestrator Engine (§6.4) che esegue conversazioni multi-turn con tool calling iterativo. Il routing LLM deve bilanciare tre vincoli in tensione:

1. **Qualità**: conversazioni complesse richiedono Claude Opus 4.7, ma l'upgrade ha un costo di latenza e denaro non trascurabile.
2. **Latenza**: il budget TTFC è ≤ 800ms (≤ 500ms per voice) secondo §2.3. Ogni retry o fallback erode questo budget.
3. **Resilienza**: Anthropic può avere outage parziali o totali; GPT-5 è il fallback cross-provider.

Un vincolo trasversale è il **prompt caching di Anthropic**: se una sessione è cached su Claude Sonnet 4.6, un upgrade a Opus 4.7 invalida il cache hit. Il costo di un cache miss su un context di 6.000 token è dell'ordine di ~0,018 USD in token aggiuntivi e ~200–400ms di latenza extra. L'upgrade a Opus deve quindi essere riservato a conversazioni genuinamente complesse, non usato preventivamente.

---

## Opzioni considerate

### Area A — Trigger upgrade Sonnet → Opus

La BIBLE §6.4 usa il termine "complex" senza definirlo operativamente. Questo ADR lo rende misurabile.

**Segnali con soglie proposte:**

| Segnale | Soglia | Motivazione |
|---|---|---|
| Context attivo (prompt tokens) | > 6.000 token | Conversazioni lunghe superano il sweet spot Sonnet; Opus regge meglio la coerenza multi-turn |
| Tool calls previsti nel turno | ≥ 3 tool distinti | Multi-tool reasoning richiede planning più robusto |
| Istruzione esplicita multi-step | Keyword `step-by-step`, `confronta`, `ragiona` nel prompt | Segnale debole ma a costo zero |
| Bassa qualità turno precedente | Score eval < 0.65 nel judge automatico (§11) | Segnale reattivo: Opus come recovery |

Promozione se **≥2 segnali** superano soglia (regola ≥2 per evitare upgrade spurie da segnale singolo debole).

#### A1 — Classificazione rule-based pre-call *(scelta adottata)*

Prima della chiamata LLM, `LLMRouter` valuta i segnali sopra in modo deterministico: conta i token del context corrente via SDK, ispeziona il tool manifest richiesto, controlla keyword. Zero latenza aggiuntiva, deterministica, debuggabile.

**Perché preferita:** la penalità di latenza di A2 è incompatibile con il budget §2.3. Il segnale reattivo (score basso turno precedente) integra il gap semantico senza latenza aggiuntiva.

#### A2 — Classificazione LLM-based

Un micro-prompt inviato a Sonnet 4.6 (o Haiku) stima la complessità prima di routare. Output: `{"complex": true, "confidence": 0.87}`.

**Perché scartata:** aggiunge ~150–300ms al TTFC; introduce una chiamata LLM che può fallire; costo extra per ogni turno; circolarità parziale (il modello che valuta è lo stesso che eseguirà se `false`).

---

### Area B — Granularità circuit breaker

La BIBLE §6.4 specifica: "3 errori 5xx in 30s → fallback per 5 minuti, poi half-open retry". Granularità non specificata.

#### B1 — Circuit breaker per provider (Anthropic tutto)

Un singolo breaker per tutto il provider Anthropic. Se Sonnet 4.6 restituisce 3 errori 5xx in 30s, sia Sonnet che Opus vengono bypassati per 5 minuti.

**Perché scartato:** un outage di Sonnet 4.6 non implica necessariamente un outage di Opus 4.7 — Anthropic espone endpoint separati per i modelli. Si perde disponibilità di Opus ingiustamente.

#### B2 — Circuit breaker per modello *(scelta adottata)*

Due breaker indipendenti: uno per `claude-sonnet-4-6`, uno per `claude-opus-4-7`. Se Sonnet scatta, il router tenta Opus prima di passare a GPT-5. Solo se anche Opus scatta si passa al cross-provider.

La sequenza di routing diventa: `Sonnet → (se scatta) Opus → (se scatta) GPT-5`.

**Perché preferito:** endpoint Anthropic separati per i modelli; un outage parziale è lo scenario più comune. Il costo implementativo è giustificato dalla resilienza guadagnata.

---

### Area C — Retry intra-provider

Prima di contare un errore verso il circuit breaker, quanti retry esegue il router?

#### C1 — Retry con backoff *(scelta adottata, versione modificata)*

Max **1 retry**, attesa fissa **200ms**, solo per errori transient (HTTP 503, 529, connection reset). Gli errori 429 e 500 contano direttamente per il circuit breaker senza retry.

Motivazione del limite: 1 retry × 200ms = 200ms di attesa massima, lascia ~600ms di budget per TTFC. Un secondo retry porterebbe il worst-case a ~400ms di attesa, con tensione reale sul budget §2.3.

Eccezione canale voice: sul canale voce (LiveKit Agents, ADR-002)
il retry intra-provider è disabilitato. Il budget TTFC voice di
500ms (§2.3) non è compatibile con un retry da 200ms + chiamata
LLM (~400ms). Su voice, il router salta direttamente al fallback
cross-provider via circuit breaker. Il LLMRouter riceve il
parametro `channel='voice'|'web'` dal caller e ne adatta la policy.

#### C2 — Nessun retry, ogni errore conta

Ogni errore 5xx incrementa immediatamente il counter. Fallback senza attesa.

**Perché scartato come policy primaria:** instabilità transitoria — un singolo picco di 503 che dura <100ms scatterebbe il breaker dopo 3 errori consecutivi che si sarebbero auto-risolti. Aumenta inutilmente il traffico cross-provider per errori non gravi.

---

### Area D — Mid-stream failure

Scenario: il provider restituisce un errore (500, connection reset) dopo aver già inviato N token in streaming.

#### D1 — Abort e retry completo su provider alternativo *(scelta adottata)*

Il router interrompe lo stream corrente, salva l'`idempotency_key` della richiesta (§6.4), e riemette la stessa richiesta completa al provider successivo. Il client riceve `{"type": "stream_interrupted", "retry": true}` seguito da un nuovo stream completo. Il context non viene perso grazie alla transazione atomica del turno (§6.4).

**Contro:** il client vede un'interruzione visibile; i token già generati sono sprecati; la latenza totale per la seconda risposta può superare il TTFC budget.

#### D2 — Continuazione dal token parziale su provider alternativo

Il router invia al provider alternativo il testo già generato + "continua da qui".

**Perché D2 è impraticabile:** i due provider hanno tokenizzatori diversi (Claude tokenizer vs tiktoken/BPE). Il "token #150" di Anthropic non è trasparente al prompt di OpenAI. Ricostruire il testo parziale come context fittizio introduce artefatti: il modello alternativo non sa che sta "continuando" — produrrà una risposta coerente col context ma non con lo stile/struttura iniziata. Rischio di incoerenza semantica alta; complessità implementativa molto elevata per un caso marginale.

---

### Area E — Cost tracking via usage_logs

**Schema `usage_logs` — campi minimi obbligatori:**

| Campo | Tipo | Nullable | Motivazione |
|---|---|---|---|
| `tenant_id` | `uuid` | NOT NULL | Multi-tenancy obbligatoria (§6.4) |
| `conversation_id` | `uuid` | NOT NULL | Aggregazione per sessione |
| `request_id` | `uuid` | NOT NULL | Corrisponde all'`idempotency_key`; deduplicazione retry |
| `provider` | `varchar(32)` | NOT NULL | `anthropic` / `openai` |
| `model` | `varchar(64)` | NOT NULL | Nome completo modello (es. `claude-sonnet-4-6`) |
| `prompt_tokens` | `integer` | NOT NULL | Costo input |
| `completion_tokens` | `integer` | NOT NULL | Costo output |
| `cached_tokens` | `integer` | NOT NULL DEFAULT 0 | Token serviti da prompt cache Anthropic (costo ridotto) |
| `cost_usd` | `numeric(10,6)` | NOT NULL | Costo calcolato lato app da pricing table |
| `latency_ms` | `integer` | NOT NULL | TTFC o latency totale; fonte per regression test §11 |
| `ts` | `timestamptz` | NOT NULL DEFAULT now() | Timestamp evento |
| `fallback_used` | `boolean` | NOT NULL DEFAULT false | Flag: risposta da provider/modello di fallback |

#### E1 — Log sincrono nella stessa transazione

Il log viene scritto nella stessa transazione atomica che persiste la risposta.

**Perché scartato come default:** se `usage_logs` è lento o in lock, blocca la delivery della risposta al client. Un problema di DB cost tracking diventa un outage dell'agente.

#### E2 — Log asincrono via Celery task *(scelta adottata)*

Il router risponde al client e poi emette `log_usage.delay(...)`. Deduplicazione via `INSERT ... ON CONFLICT (request_id) DO NOTHING`. Il task Celery ha max 3 retry con backoff 5s.

**Rischio accettato:** in caso di crash totale del broker Redis, i log non ancora persistiti vanno persi. Documentato come limitazione nota.

---

## Decisione

| Area | Scelta | Rationale sintetico |
|---|---|---|
| A — Trigger upgrade | **A1** rule-based: ≥2 segnali tra: context > 6.000 token, ≥3 tool nel turno, keyword multi-step nel prompt, score prev < 0.65 (regola ≥2 segnali per evitare upgrade spurie) | Latency-safe, deterministica |
| B — CB granularità | **B2** per-model: breaker separato per Sonnet e Opus | Endpoint Anthropic separati; resilienza fine-grained |
| C — Retry | **C1 mod.**: max 1 retry, 200ms fissa, solo 503/529 | Budget TTFC §2.3; 429/500 → CB diretto; retry disabilitato su channel=voice |
| D — Mid-stream | **D1**: abort + retry completo su provider alternativo via `idempotency_key` | Consistenza garantita; D2 impraticabile |
| E — Cost tracking | **E2**: log asincrono Celery, `ON CONFLICT (request_id) DO NOTHING` | Latency isolata; perdita accettabile vs impatto response path |

**Routing pipeline:**
```
Request → A1 classify (≥2 segnali?) → select model (Sonnet/Opus)
        → CB check (per-model) → if open → next in chain
        → Call provider (+ C1: 1 retry 200ms se 503/529)
        → Stream → if mid-stream error → D1: abort + retry su chain
        → On success: response to client + E2 Celery log task
        → CB update (success/failure counter)
```

---

## Conseguenze

### Positive

- Routing deterministico e debuggabile: ogni decisione di upgrade o fallback è loggata con il segnale che l'ha triggerata.
- Resilienza granulare: un outage parziale Anthropic (solo Sonnet) non forza immediatamente il cross-provider.
- Cost tracking deduplicato: l'`idempotency_key` previene double-counting su retry.
- Compatibilità con prompt caching: il routing rule-based con soglia ≥2 segnali scoraggia upgrade frequenti a Opus, preservando i cache hit su Sonnet.

### Negative

- **Complessità del grafo di stati**: con circuit breaker per-modello (B2) e retry (C1), il `LLMRouter` gestisce 6+ stati distinti (Sonnet-closed/half-open/open, Opus-closed/half-open/open, cross-provider-active). Testing exhaustivo richiesto.
- **Degradation silenziosa**: quando il fallback è attivo (GPT-5), la qualità delle risposte può essere diversa da Anthropic. Il flag `fallback_used` è l'unico strumento di rilevamento retroattivo — manca un alert real-time. Serve un monitor Celery che controlla `fallback_used = true` supera il 5% dei turni negli ultimi 10 minuti.
- **Cache miss su upgrade a Opus**: ogni promozione Sonnet→Opus invalida il cache hit del context corrente. Con context da 6.000 token, costo aggiuntivo ~0,018 USD e ~200–400ms di latenza extra. Se la soglia A1 è calibrata male (troppo bassa), il costo aggregato per tenant può essere significativo.
- **Perdita log costi in crash Celery**: in caso di crash del broker Redis, i task non ancora persistiti sono persi. Nessuna reconciliazione automatica prevista — gap nei report di costo per tenant.
- **Soglie A1 non auto-adattive**: le soglie (6.000 token, 3 tool, score < 0.65) sono fisse. Revisione manuale periodica richiesta se il comportamento degli utenti cambia.
- **Interruzione visibile al client su D1**: il segnale `stream_interrupted` deve essere gestito nel client con UX appropriata. Un'interruzione senza feedback visivo è percepita come bug.

### Neutre

- Lo schema `usage_logs` è estensibile: campi aggiuntivi (es. `temperature`, `stop_reason`) possono essere aggiunti senza breaking change.
- Il limite di 1 retry (C1) è conservativo; se il TTFC budget venisse allargato, si può passare a 2 retry senza impatto architetturale.

---

## Piano di migrazione / rollout

- [ ] Sprint 1: implementare `LLMRouter` v1 con routing Sonnet/Opus, trigger A1, senza circuit breaker. Deploy in staging.
- [ ] Sprint 1: raccogliere 200 conversazioni reali, verificare manualmente che le promozioni Opus corrispondano a conversazioni effettivamente complesse. Tarare le soglie se necessario.
- [ ] Sprint 2: aggiungere circuit breaker B2 (per-model). Test chaos: iniettare 503 su Sonnet, verificare che Opus rimanga up.
- [ ] Sprint 2: integrare fallback cross-provider GPT-5 (OpenAI SDK già in stack §9). Testare `idempotency_key` anti-double-processing.
- [ ] Sprint 2: migration SQL `usage_logs`, Celery task `log_usage`, deduplicazione ON CONFLICT.
- [ ] Sprint 3: monitor alert `fallback_used > 5%` negli ultimi 10 minuti.
- [ ] Sprint 3: feature flag per abilitare il router progressivamente (10% → 50% → 100% traffico).

---

## Questioni aperte

1. **Pricing table**: dove vive la tabella `(provider, model) → cost_usd_per_token`? Hardcodata nel codice, in config file, o in DB? Se i prezzi cambiano, serve un deploy o una modifica config?
2. **GPT-5 streaming compatibility**: il pattern streaming con tool calling di OpenAI SDK è compatibile con quello Anthropic nell'agent loop? Verificare che D1 abort + retry su GPT-5 non richieda adattatori specifici.
3. **Judge automatico Opus 4.7 (§11)**: il judge che valuta la qualità (segnale A1 reattivo) usa `LLMRouter`? Se sì, rischio di loop. Il judge deve usare Opus 4.7 direttamente, bypassando il router.

---

## Riferimenti

- BIBLE v3 §6.4 — Agent Orchestrator Engine: stack, routing modelli, streaming, resilienza, `idempotency_key`
- BIBLE v3 §9 — Stack tecnologico: `anthropic` SDK, `openai` SDK
- BIBLE v3 §2.3 — Converse latency budget: TTFC ≤ 800ms (web), ≤ 500ms (voice)
- BIBLE v3 §11 — Eval framework: judge automatico Opus 4.7, latency regression test
- Anthropic Prompt Caching documentation — cache invalidation su cambio modello
- `tenacity` library (Python) — retry e circuit breaker patterns
- ADR-001 — Stack canonico (`anthropic` SDK + `openai` SDK)
- ADR-003 — Tenant isolation (`tenant_id` in `usage_logs`)
