# ADR-005: Multi-Embedding Strategy per Knowledge Graph Engine

- **Status**: proposed
- **Date**: 2026-05-14
- **Authors**: Stefano Corda
- **BIBLE refs**: §6.1, §5, §9, §10.3
- **Supersedes**: n/a
- **Superseded by**: n/a

---

## Contesto

Il Knowledge Graph Engine (§6.1) gestisce entità eterogenee — immobili,
prodotti, luoghi, contenuti editoriali — che devono essere recuperabili
tramite query semantiche con profili diversi: una query lifestyle
("casa con atmosfera nordica vicino al mare") e una query tecnica
("villa 5 camere 850 mq piscina") richiedono pesi vettoriali diversi
sulla stessa entità.

BIBLE v3 §6.1 specifica esplicitamente una strategia multi-embedding:
tre vettori per entità (`content_emb`, `lifestyle_emb`, `features_emb`)
con ricerca ibrida a pesi configurabili. Questo ADR definisce come
costruire ciascun vettore, come combinarli a query time, i parametri
HNSW, la strategia di migrazione da `text-embedding-3-small` (1536 dim)
a `text-embedding-3-large` (3072 dim), e se aggiungere un reranker
cross-encoder sul path principale.

Un vincolo trasversale è il budget RAM: tre indici HNSW da 3072 dim
su larga scala hanno un footprint stimabile e devono essere pianificati
prima del provisioning hardware.

---

## Opzioni considerate

### Area A — Costruzione del testo sorgente per `features_emb`

`content_emb` e `lifestyle_emb` sono non controversi:
- `content_emb` = concatenazione `title + "\n" + description`
- `lifestyle_emb` = `lifestyle_narrative` del documento (campo generato
  da LLM al momento dell'ingestione, fallback su `description` se assente)

Il punto di disaccordo è `features_emb`.

#### A1 — Flat JSON dei campi strutturati

Serializzare `{"bedrooms": 5, "sqm": 850, "pool": true}` come stringa
e embeddarla direttamente.

**Perché scartata:** i modelli embedding trattano meglio il linguaggio
naturale che JSON serializzato. Un flat JSON non sfrutta la comprensione
sintattica del modello: "bedrooms" è una chiave arbitraria, non ha
relazione semantica con "camere da letto" in una query italiana. Score
di similarità sistematicamente più bassi nei benchmark interni.

#### A2 — Prosa strutturata da template Pack *(scelta adottata)*

Il Pack di ogni vertical definisce un template Jinja per generare una
frase descrittiva dalle feature strutturate:
`"Villa con {{ bedrooms }} camere da letto, {{ sqm }} mq, {% if pool %}con piscina{% endif %}, {{ location }}."`

Output: `"Villa con 5 camere da letto, 850 mq, con piscina, Costa Smeralda."`

**Perché preferita:** prosa naturale nella lingua del tenant → embedding
con distribuzione semantica corretta. Il template vive nel Pack (§5:
fat core / lean packs), non nel core engine. Ogni vertical può
ottimizzare la prosa senza toccare il motore.

---

### Area B — Funzione di scoring ibrido

#### B1 — Somma pesata *(scelta adottata)*

```
score = w_c · sim(content_emb, q) +
        w_l · sim(lifestyle_emb, q) +
        w_f · sim(features_emb, q)
```
con `w_c + w_l + w_f = 1.0`. I pesi sono configurabili per query-type
(Area C). La funzione è calcolata lato applicativo dopo aver recuperato
i top-K candidati da ciascun indice HNSW (K=50 per indice, merge e
re-score sui 150 candidati totali).

**Perché preferita:** deterministica, debuggabile, latency-safe.
Il merge su 150 candidati è O(150) in Python — trascurabile.

#### B2 — Reciprocal Rank Fusion (RRF)

```
score_RRF = Σ 1 / (k + rank_i)   con k=60
```
Combina le rank list dei tre indici senza normalizzare i punteggi raw.
Non richiede calibrazione dei pesi, è robusta a scale diverse tra
i tre spazi embedding.

**Perché scartata come default:** non espone un parametro per query-type
personalizzato — non si può dire "su questa query voglio lifestyle più
forte". RRF è documentata come fallback operativo in Questione Aperta #2,
da attivare se la calibrazione pesi B1 risulta instabile in produzione.

---

### Area C — Default pesi e override

#### C1 — Pesi fissi globali *(scartata)*

Un unico set di pesi per tutto il traffico. Semplice ma inadatto: una
query "quante camere" e "atmosfera boho chic" hanno profili opposti.

**Perché scartata:** non sfrutta la classificazione query-type già
eseguita dall'Agent Orchestrator (§6.4 — il router conosce il contesto
della conversazione).

#### C2 — Pesi per query-type con override a cascata *(scelta adottata)*

Default globali: `content=0.45 / lifestyle=0.35 / features=0.20`

Mapping per query-type:

| Query type | content | lifestyle | features |
|---|---|---|---|
| `lifestyle-query` | 0.25 | 0.60 | 0.15 |
| `technical-query` | 0.35 | 0.10 | 0.55 |
| `mixed` (default) | 0.40 | 0.35 | 0.25 |

Override a cascata (priorità decrescente):
1. **Pack-level**: il Pack vertical sovrascrive i default nel proprio
   `pack.yaml → search.weights`
2. **Tenant-level**: `tenant.yaml → search.weights` sovrascrive il Pack
3. **Query-time**: il caller può passare `weights_override` esplicito
   per A/B test o personalizzazione contestuale

---

### Area D — Parametri indice HNSW e stima costi

Parametri scelti (per tutti e tre gli indici):

| Parametro | Valore | Motivazione |
|---|---|---|
| `m` | 16 | Sweet spot qualità/RAM per recall ≥ 0.95 |
| `ef_construction` | 128 | Build quality; usato solo offline |
| `ef_search` | 80 | Latenza ~8–15ms per indice su NVMe |
| `dim` | 3072 | `text-embedding-3-large` |

**Stima RAM working set per tenant a regime (100K entità):**

| Componente | Dimensione |
|---|---|
| 3 indici HNSW × 3072 dim × 4 bytes × 100K | ~3.7 GB vettori raw |
| Overhead HNSW graph (m=16) | ~7–10 GB (2–3× raw) |
| **Totale working set per tenant** | **~25–35 GB** |

Scenario worst-case multi-tenant (10 tenant attivi in RAM):
~250–350 GB. Provisioning minimo consigliato per il DB host: 384 GB RAM
con swap su NVMe per tenant idle (cold page-in: ~200–400ms).

**Costo embedding iniziale per tenant (100K entità, 3 vettori):**

`text-embedding-3-large` → $0.130/1M token (pricing OpenAI 2025).
300K chiamate × media ~350 token/entità = ~105M token → **~$13.65/tenant**.
Con Batch API (sconto 50%): **~$6.83/tenant**.
Tempo stimato Batch API (rate limit 1M token/min): **~105 min/tenant**.

---

### Area E — Strategia di migrazione da 1536 a 3072 dim

#### E1 — Big bang: re-embedding completo offline *(scelta adottata)*

Tutti i tenant vengono re-embeddati in staging con
`text-embedding-3-large` prima del cutover. Gli indici HNSW
vengono ricostruiti offline. Il cutover è atomico: si sposta
il puntatore dell'indice attivo in produzione.

E1 si appoggia su OpenAI Batch API (non API sincrona) per il
re-embedding di massa: rate limit Batch ~1M token/min permette
~105 min/tenant come stimato. API sincrona avrebbe richiesto
quote dedicate enterprise OpenAI e tempi ~10× maggiori. La Batch
API è quindi parte costitutiva di E1, non solo ottimizzazione
di costo.

**Perché preferita:** nessuna ambiguità di dimensione a runtime.
Il codebase non deve gestire due formati paralleli. La finestra
di migrazione stimata per 10 tenant è ~18 ore (si parallelizza:
10 tenant × 105 min / N workers).

#### E2 — Dual-write: nuovi embedding in parallelo, migrazione lazy

Nuove entità vengono scritte con 3072 dim; le entità esistenti
rimangono a 1536 dim fino all'aggiornamento. La ricerca usa
l'indice disponibile per ciascuna entità.

**Perché scartata:** incompatibilità di score durante la migrazione —
i punteggi di similarità tra spazi 1536 e 3072 non sono comparabili;
un merge su query produrrebbe ranking inconsistenti. Complessità
operativa alta per un beneficio marginale rispetto al big bang.

---

### Area F — Reranker cross-encoder sul path principale

#### F1 — Nessun reranker sul path principale *(scelta adottata)*

Il top-K restituito dalla somma pesata (B1) è il risultato finale.
La latenza aggiuntiva di un reranker cross-encoder (~80–120ms su CPU,
~20–30ms su GPU) non è compatibile con il budget TTFC ≤ 800ms (§2.3)
considerando che la ricerca è un passo in un agent loop multi-turn.

#### F2 — Cross-encoder per use case offline

Un reranker `cross-encoder/ms-marco-MiniLM-L-6-v2` (o equivalente)
può essere usato in pipeline offline: generazione di training data per
calibrazione pesi, valutazione periodica della qualità del ranking,
produzione di dataset etichettati per §10.3 (eval framework).
Non è nel path di produzione real-time.

**F2 non è scartata in assoluto** — è documentata come strumento
operativo per la calibrazione dei pesi C2, da attivare in batch
notturni. Vedi Questione Aperta #3.

---

## Decisione

| Area | Scelta | Rationale sintetico |
|---|---|---|
| A — features_emb sorgente | **A2** prosa da template Pack | Linguaggio naturale → distribuzione embedding corretta; template nel Pack, non nel core |
| B — Scoring ibrido | **B1** somma pesata | Deterministica, parametrizzabile per query-type; RRF come fallback operativo (OQ#2) |
| C — Pesi e override | **C2** per query-type, cascata Pack > tenant > query-time | Flessibilità senza accoppiamento core |
| D — HNSW params | **m=16, ef_c=128, ef_s=80, dim=3072** | Recall ≥ 0.95; ~$6.83/tenant via Batch API; ~105 min re-embedding |
| E — Migrazione dim | **E1** big bang offline via Batch API | Nessuna ambiguità score; finestra ~18h per 10 tenant; Batch API parte costitutiva di E1 |
| F — Reranker | **F1** no reranker su path principale; **F2** solo offline | TTFC budget §2.3 non compatibile con cross-encoder real-time |

---

## Conseguenze

### Positive

- Ricerca lifestyle e tecnica usano pesi diversi: nessun compromesso
  di qualità su query-type distanti.
- I template Pack (A2) sono modificabili dal team vertical senza
  toccare il core engine — rispetta §5 fat core / lean packs.
- Somma pesata (B1) è debuggabile: ogni decisione di ranking è
  riproducibile deterministicamente dato query + pesi.
- Batch API riduce il costo di re-embedding del 50% rispetto
  all'API sincrona.

### Negative

- **RAM working set elevato**: ~25–35 GB per tenant a regime. Con
  10 tenant attivi → 250–350 GB. Il DB host richiede provisioning
  hardware significativo prima del go-live multi-tenant. Costo
  operativo hardware non trascurabile.
- **Calibrazione pesi C2 è manuale e a rischio deriva**: le soglie
  (0.45/0.35/0.20) sono stime; senza feedback loop automatizzato,
  la qualità del ranking può degradare silenziosamente se il
  comportamento degli utenti cambia. Richiede revisione periodica
  con cross-encoder offline (F2).
- **Costo re-embedding non ammortizzato su tenant piccoli**: per un
  tenant con 1K entità il costo Batch API è irrisorio (~$0.07), ma il
  costo operativo di setup (template Pack, trigger pipeline, monitoring)
  è fisso. Soglia di break-even stimata: ≥500 entità/tenant.
- **Template A2 accoppiati alla lingua del tenant**: un template italiano
  produce embedding italiani. Query in inglese su un tenant italiano
  degradano il recall di `features_emb`. Soluzione: generare prosa
  nella lingua del documento, non dell'interfaccia. Richiede disciplina
  operativa in onboarding nuovo tenant.
- **Big bang E1 richiede finestra di manutenzione**: ~18h per 10 tenant
  se parallelizzato su N workers. In produzione live, gli indici vecchi
  devono rimanere attivi durante la migrazione — doppio footprint RAM
  temporaneo (~2×). Rischio: se il cutover fallisce a metà, rollback
  richiede ripristino degli indici 1536 dim (snapshot obbligatorio
  pre-migrazione).

### Neutre

- `ef_search=80` può essere abbassato a 40–60 se la latenza
  risultasse critica, con degradazione recall stimata <3%.
- Lo schema `pgvector` è estensibile: un quarto vettore
  (es. `temporal_emb` per contenuti con forte componente temporale)
  può essere aggiunto senza breaking change all'indice esistente.

---

## Piano di migrazione / rollout

- [ ] Sprint 1: implementare template A2 per il Pack `immobiliare`
  (vertical pilota). Generare `features_emb` per 1K entità di test.
- [ ] Sprint 1: creare i tre indici HNSW (m=16, ef_c=128) in staging
  con `text-embedding-3-large`. Misurare recall@10 vs baseline
  `text-embedding-3-small`.
- [ ] Sprint 1: implementare `HybridSearchRepository` con somma pesata
  B1 e mapping C2. Test A/B su query set etichettato manualmente.
- [ ] Sprint 2: pipeline Batch API per re-embedding completo del
  tenant pilota. Misurare tempo effettivo vs stima 105 min.
- [ ] Sprint 2: snapshot pre-cutover, switch atomico indice attivo,
  smoke test ranking.
- [ ] Sprint 2: implementare cross-encoder F2 in pipeline offline
  notturna per calibrazione pesi. Loggare delta score vs pesi correnti.
- [ ] Sprint 3: estendere a tutti i tenant in produzione (big bang E1).
  Monitor RAM working set per tenant post-cutover.

---

## Questioni aperte

1. **Lingua dei template A2 in tenant multilingua**: se un tenant serve
   utenti in IT e EN, deve mantenere due versioni del template (e quindi
   due embedding `features_emb`)? Oppure un unico embedding nella lingua
   principale del documento? Da definire con il team content prima
   dell'onboarding del primo tenant multilingua.

2. **RRF come fallback operativo**: se la calibrazione pesi B1 risulta
   instabile in produzione (alta varianza nei feedback impliciti),
   attivare RRF come sostituto senza ricalibrazione. Definire la soglia
   di instabilità (es. NDCG@10 < 0.70 su eval set) che triggera il
   switch. Da formalizzare nel runbook operativo.

3. **Frequenza ricalibrazione pesi C2 con cross-encoder offline**:
   il reranker F2 produce un dataset di ranking "ground truth" notturno.
   Con quale cadenza i pesi C2 vengono aggiornati? Proposta: revisione
   mensile manuale con alert automatico se il delta score medio supera
   0.05. Richiede accordo con il team ML.

4. **Indice HNSW per tenant isolato o shared**: ogni tenant ha il proprio
   indice HNSW (isolamento totale, overhead RAM per tenant) oppure
   un indice shared con filtro `tenant_id` (minor RAM, ma i vettori
   di tenant diversi competono per i cluster HNSW)? La BIBLE §6.1
   non specifica. Isolamento per-tenant è coerente con ADR-003 (RLS),
   ma impatta il provisioning RAM. Da decidere prima del deploy
   multi-tenant.

---

## Riferimenti

- BIBLE v3 §6.1 — Knowledge Graph Engine: multi-embedding, HNSW,
  ricerca ibrida
- BIBLE v3 §5 — Fat core / lean packs: template Pack per features_emb
- BIBLE v3 §9 — Stack canonico: OpenAI embedding SDK, pgvector
- BIBLE v3 §10.3 — Eval framework: dataset etichettato per calibrazione
- BIBLE v3 §2.3 — Latency budget TTFC: vincolo su reranker real-time
- ADR-001 — Stack canonico (pgvector, text-embedding-3-large)
- ADR-003 — Tenant isolation (isolamento per-tenant degli indici HNSW)
- ADR-004 — LLM Router (query-type classification per pesi C2)
- OpenAI Embeddings documentation — text-embedding-3-large pricing,
  Batch API
- pgvector HNSW documentation — parametri m, ef_construction, ef_search
