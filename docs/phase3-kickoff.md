# Phase 3 — Kickoff & Strategic Plan

**Data**: 2026-05-18  
**Predecessor**: phase-2-complete (tag `fe4a63dc`)  
**Method**: prioritizzazione per valore commerciale × rischio tecnico  
**Baseline test**: 127 backend + 24 frontend = 151 totali

---

## 1. Inventario candidati Phase 3

| ID | Nome STEP | Origine | Tipo | Stima ore | Dipendenze |
|----|-----------|---------|------|-----------|------------|
| P3-01 | GitHub Actions CI + eval gate | phase1-followups (open), CLAUDE.md §10 | infra | 8h | nessuna |
| P3-02 | `prompts/system.md` reale + golden dataset 20 conv | phase2-complete (non fatto), BIBLE §6.4 | content | 12h | P3-01 raccomandato |
| P3-03 | Real OpenAI embeddings (`text-embedding-3-large`) | phase1-followups (retrieval eval), ADR-005 | engine (KG) | 10h | OpenAI API (a pagamento) |
| P3-04 | Ontologia persona condivisa | phase2-complete (known issue #1) | refactor | 4h | nessuna |
| P3-05 | Refactor `_REPO_ROOT` → `settings.REPO_ROOT` | phase2-complete (known issue #2) | refactor | 2h | nessuna |
| P3-06 | Persistence `visitor_sessions` automatica (backend middleware) | BIBLE §6.1, phase2-complete | engine (KG) | 6h | DB già presente |
| P3-07 | Spatial Experience Engine v1 (Inhabit) | BIBLE §6.6 | engine | 24h | asset 3D/360 (esterni) |
| P3-08 | Static Manifestation Engine v1 (SEO + `/llm.txt`) | BIBLE §6.7 | engine | 16h | P3-02 raccomandato |
| P3-09 | Long-polling fallback (`/conversations/{id}/poll`) | phase1-followups (ADR-002 §A3) | infra | 6h | Redis già presente |
| P3-10 | RLS AST scan hook (pre-commit + CI) | phase1-followups (open) | infra | 4h | P3-01 |
| P3-11 | Voice channel v1 (LiveKit + Deepgram + Cartesia) | BIBLE §6.3, ADR-002 §B1 | engine | 40h | 3 API a pagamento (LiveKit, Deepgram, Cartesia) |
| P3-12 | Learning Engine v1 (pipeline notturna) | BIBLE §6.8 | engine | 32h | P3-02, P3-03, dataset ≥500 conv |
| P3-13 | Pack dental-luxury (NUOVO) | BIBLE §5 dimostrazione fat-core/lean-packs | pack | 10h | P3-04 (ontologia persona) |
| P3-14 | Pack aesthetic-clinic (NUOVO) | BIBLE §5 dimostrazione fat-core/lean-packs | pack | 10h | P3-04, P3-13 |

---

## 2. Valutazione commerciale

Scala 1–5. Totale = (valore demo + valore produzione) − costo opportunità.

| ID | Valore demo | Valore produzione | Costo opportunità | **Totale** |
|----|-------------|-------------------|-------------------|------------|
| P3-01 | 1 | 5 | 1 | **+5** |
| P3-02 | 4 | 5 | 1 | **+8** |
| P3-03 | 2 | 5 | 2 | **+5** |
| P3-04 | 1 | 4 | 1 | **+4** |
| P3-05 | 1 | 2 | 1 | **+2** |
| P3-06 | 2 | 4 | 1 | **+5** |
| P3-07 | 5 | 3 | 3 | **+5** |
| P3-08 | 3 | 4 | 2 | **+5** |
| P3-09 | 1 | 3 | 2 | **+2** |
| P3-10 | 1 | 3 | 1 | **+3** |
| P3-11 | 5 | 2 | 4 | **+3** |
| P3-12 | 2 | 2 | 4 | **0** |

**P3-02** (prompts + golden dataset) è il candidato con il più alto valore commerciale totale: trasforma un agente che risponde in un agente che vende. Nessun cliente pagante è disponibile a comprare un agente generico.

---

## 3. Valutazione tecnica

Scala 1–5. Tag di rischio complessivo: 🟢 ≤6 punti / 🟡 7–9 / 🔴 ≥10.

| ID | Rischio impl. | Dipendenze esterne | Reversibilità (1=difficile, 5=facile) | **Rischio** |
|----|--------------|---------------------|---------------------------------------|-------------|
| P3-01 | 2 | 2 (GitHub Actions free) | 5 | 🟢 **4** |
| P3-02 | 2 | 1 (solo testo) | 5 | 🟢 **3** |
| P3-03 | 3 | 4 (OpenAI API paid) | 3 | 🟡 **8** |
| P3-04 | 1 | 1 | 5 | 🟢 **2** |
| P3-05 | 1 | 1 | 5 | 🟢 **2** |
| P3-06 | 2 | 1 | 4 | 🟢 **4** |
| P3-07 | 4 | 3 (asset 3D, librerie 360) | 2 | 🔴 **11** |
| P3-08 | 3 | 1 | 3 | 🟡 **8** |
| P3-09 | 3 | 2 (Redis già presente) | 3 | 🟡 **7** |
| P3-10 | 2 | 1 | 4 | 🟢 **4** |
| P3-11 | 5 | 5 (LiveKit + Deepgram + Cartesia) | 1 | 🔴 **14** |
| P3-12 | 4 | 2 | 2 | 🟡 **9** |

---

## 4. Matrice priorità

|  | **Rischio BASSO 🟢** | **Rischio MEDIO 🟡** | **Rischio ALTO 🔴** |
|--|---------------------|---------------------|---------------------|
| **Valore ALTO** ✨ | P3-01, **P3-02**, P3-04, P3-06 | P3-03, P3-08 | P3-07, P3-11 |
| **Valore MEDIO** | P3-05, P3-10 | P3-09 | — |
| **Valore BASSO** | — | P3-12 | — |

**Quadrante prioritario — Alto valore + Basso rischio:**  
`P3-02` (prompts reali + golden dataset), `P3-01` (CI), `P3-06` (visitor_sessions), `P3-04` (ontologia persona).  
Questi quattro, nell'ordine indicato, sono la sequenza naturale di apertura Phase 3 a prescindere dallo scenario scelto.

---

## 5. Domande aperte BLOCCANTI

Prima di iniziare qualsiasi STEP di Phase 3, rispondere a queste 7 domande. Cambiano materialmente la scelta di scenario.

1. **Cliente pilota reale?** C'è un'agenzia immobiliare, clinica, o hospitality che vuole essere il primo cliente pagante? In quale vertical? (Determina se serve un secondo pack o se real-estate-luxury è sufficiente.)

2. **Budget API esterne?** Quanti euro/mese sono disponibili per: OpenAI Embeddings (stimato ~$20-50/mese a regime), LiveKit (~$50/mese base), Deepgram (~$0.003/min), Cartesia (~$15/mese)? Senza budget esplicito, P3-03 e P3-11 vanno fermati.

3. **Deadline demo pubblica?** C'è una data entro cui mostrare qualcosa a un investitore, partner, o potenziale cliente? Una demo senza CI verde è un rischio: una regressione non detectata può emergere durante la presentazione.

4. **DigIdentity Card — separata o bridge?** Il contesto attuale la definisce progetto separato (nota in `claude-context-brief.md`). Questa separazione rimane valida per tutta Phase 3? Se Card e Living Site devono condividere identità visitatore, serve un bridge API non pianificato.

5. **Phase 3 target: "demo killer" o "produzione cliente"?** Sono obiettivi in tensione: una demo massimizza WOW-factor visivo (Spatial, Voice); la produzione cliente massimizza affidabilità (CI, embeddings reali, ontologia). Scegliere uno prima di iniziare.

6. **Tempo/settimana disponibile?** Con /goal full-auto ogni STEP richiede ~1-3h di review e decisione da Stefano. Stima realistica: 2-4 STEP al mese a 4h/settimana. Aiuta a calibrare lo scenario in base a una timeline reale.

7. **Secondo pack in Phase 3?** Un secondo vertical (es. `dental-premium` o `hospitality-nicchia`) multiplica la dimostrazione della scalabilità fat-core/lean-packs. Ma richiede 8-12h aggiuntive e un brief di dominio. È in scope Phase 3?

---

## 6. Tre scenari Phase 3

Mutuamente esclusivi come punto di partenza. Possono evolvere dopo la risposta alle domande §5.

---

### Scenario A — "Demo Killer" (~44h)

**Obiettivo**: costruire una demo live che impressioni in una presentazione a investitori o potenziali clienti.

| # | STEP | Ore |
|---|------|-----|
| 1 | P3-02 — prompts/system.md reale + golden dataset 20 conv | 12h |
| 2 | P3-01 — GitHub Actions CI | 8h |
| 3 | P3-04 — Ontologia persona condivisa | 4h |
| 4 | P3-07 — Spatial Experience Engine v1 (tour 360° sincronizzato) | 24h |

**Output finale**: URL demo live dove il visitatore può scegliere una villa, parlare con l'agente, vedere il layout morpharsi in real-time, e fare un mini-tour 360° sincronizzato con la conversazione. Tutti i testi dell'agente sono coerenti e verticale-specifici.

**Stima totale**: ~44h di implementazione + 6h di review/decisioni Stefano.

**Sceglierlo se**: esiste una presentazione entro 6-8 settimane, anche senza cliente pagante confermato. La Spatial Experience è il differenziatore visivo che nessun chatbot-su-sito può imitare.

**Rischio principale**: P3-07 è il più rischioso del gruppo (dipendenze asset 3D, scelte libreria). Se saltato, lo scenario degenera in Scenario B senza CI.

---

### Scenario B — "Foundation Cliente" (~38h)

**Obiettivo**: rendere il sistema consegnabile a un primo cliente pagante reale — CI verde, zero known inconsistencies, agente che parla bene.

| # | STEP | Ore |
|---|------|-----|
| 1 | P3-01 — GitHub Actions CI + eval gate | 8h |
| 2 | P3-02 — prompts/system.md reale + golden dataset 20 conv | 12h |
| 3 | P3-04 — Ontologia persona condivisa | 4h |
| 4 | P3-06 — Persistence visitor_sessions automatica | 6h |
| 5 | P3-03 — Real OpenAI embeddings (se budget disponibile) | 10h |

**Output finale**: sistema con CI che blocca le regressioni, agente che risponde in modo coerente e verticale-specifico, visitatori di ritorno riconosciuti, retrieval qualitativo (se P3-03 incluso). Nessun known issue aperto.

**Stima totale**: ~38h (o ~28h senza P3-03).

**Sceglierlo se**: c'è un cliente reale in vista nei prossimi 2-3 mesi, anche solo come "beta tester" non pagante. È lo scenario più sostenibile per un solo sviluppatore perché non introduce nuovi engine rischiosi.

**Nota**: P3-03 (real embeddings) richiede budget OpenAI e migrazione dati; può essere fatto dopo o rimandato a Phase 4 senza bloccare la consegna.

---

### Scenario C — "Foundation Cleanup" (~20h)

**Obiettivo**: azzerare il tech debt prima di investire in nuovi engine.

| # | STEP | Ore |
|---|------|-----|
| 1 | P3-01 — GitHub Actions CI | 8h |
| 2 | P3-05 — Refactor REPO_ROOT | 2h |
| 3 | P3-04 — Ontologia persona condivisa | 4h |
| 4 | P3-10 — RLS AST scan hook | 4h |
| 5 | P3-09 — Long-polling fallback | 6h |

**Output finale**: codebase senza known issues, CI verde, sicurezza RLS verificata staticamente, rete enterprise supportata. Nessun nuovo engine.

**Stima totale**: ~20h.

**Sceglierlo se**: hai identificato un bug o un rischio sicurezza che ti pesa, o vuoi avere una base solida prima di mostrare il codice a un partner tecnico. Scenario conservativo — non produce valore visibile all'esterno.

---

## 7. Scenario A++ — Multi-Vertical Living Site Prototype (SCELTO)

**Decisione presa 2026-05-18.** Obiettivo: prototipare la tesi fondante di BIBLE §5 (fat-core/lean-packs) su tre vertical, dimostrando che lo stesso engine core serve domini completamente diversi con solo il pack che cambia.

**Contesto decisionale**:
- Nessun cliente firmato, nessuna deadline esterna
- API cloud disponibili: Anthropic, OpenAI, OpenRouter
- Nessun modello locale (no Qwen, no Ollama) — scelta deliberata per semplicità operativa
- Vertical sanitarie gestite con DPA standard Anthropic+OpenAI; nessun dato clinico nel KG
- DigIdentity Card confermata fuori scope

**Sequenza STEP definitiva**:

| # | ID | Nome | Ore | Note |
|---|----|------|-----|------|
| 1 | P3-03 | Real OpenAI embeddings + router multi-provider | 8h | text-embedding-3-large; ADR-007 multi-provider |
| 2 | P3-02a | Prompts + golden dataset real-estate-luxury | 12h | 20 conv min; system.md verticale specifico |
| 3 | P3-04 | Ontologia persona condivisa Sense ↔ Qualify | 4h | risolve known issue Phase 2 #1 |
| 4 | P3-01 | GitHub Actions CI + eval gate cross-pack | 8h | blocca regressioni su tutti e 3 i pack |
| 5 | P3-13 | Pack dental-luxury (NUOVO) | 10h | ontology+prompts+scoring+morph, template demo |
| 6 | P3-14 | Pack aesthetic-clinic (NUOVO) | 10h | idem, secondo vertical sanitario |
| 7 | P3-06 | Persistence visitor_sessions (Remember cross-pack) | 6h | cookie+DB; riconosce visitatore di ritorno |
| 8 | P3-07 | Spatial Experience v1 (tour 360° sync, solo RE) | 24h | deliverable WOW finale; solo real-estate-luxury |

**Totale stimato**: ~82h implementazione + ~12h review/decisioni = ~94h calendario.  
**Timeline**: 5-10 settimane a ~10h/settimana.

**Output finale**:
- 3 URL demo navigabili: `/demo/real-estate-luxury`, `/demo/dental-luxury`, `/demo/aesthetic-clinic`
- Tour 360° sincronizzato con l'agente su real-estate-luxury
- CI verde su ogni push, eval gate attivo su tutti i pack
- Dimostrazione concreta che lo stesso core engine serve immobiliare, dentale, estetica senza modifiche al core

**Razionale sequenza**: P3-03 prima perché real embeddings migliorano la qualità di ogni golden dataset scritto dopo; P3-04 prima dei nuovi pack perché l'ontologia persona è prerequisito dei loro scorecard; CI (P3-01) prima dei pack nuovi perché altrimenti ogni pack aggiunte regressioni non detectate; P3-07 (Spatial) ultimo perché è il più rischioso e deve trovare CI verde già in piedi.

---

## 7-alt. Scenario B — "Foundation Cliente" (archiviato)

> Questa era la raccomandazione originale, archiviata per tracciabilità dopo la decisione del 2026-05-18 di procedere con Scenario A++.

**Scenario B — "Foundation Cliente"** (~38h) con P3-03 condizionato al budget.

Sequenza: P3-01 CI → P3-02 prompts → P3-04 ontologia → P3-06 persistence → P3-03 embeddings.

**Motivo archiviazione**: lo scenario B era ottimale per consegna a singolo cliente. La decisione di prototipare la tesi multi-vertical rende B insufficiente: non produce la dimostrazione fat-core/lean-packs né i due pack sanitari. Rimane valido come fallback se dovesse emergere un cliente pilota urgente che richiede consegna entro 4-6 settimane.

---

## 8. Definition of Done Phase 3 (originale — vedi §11 per versione aggiornata)

**Criteri binari** — tutti devono essere `true` prima di taggare `phase-3-complete`:

| Criterio | Verifica |
|----------|----------|
| CI GitHub Actions verde su `main` | `gh run list --limit 1 --json conclusion` = `success` |
| `pnpm test` ≥24 frontend, `pytest` ≥127 backend | Ultima riga di ogni suite |
| Eval gate non regredisce (baseline × 0.85) | `eval-runner` exit code 0 |
| `prompts/system.md` reale presente in pack | File esiste, >200 caratteri, non contiene "placeholder" |
| Golden dataset ≥20 conversazioni | `ls packs/real-estate-luxury/evals/golden/*.json | wc -l` ≥20 |
| Zero known issues aperti in `phase3-complete.md` (equivalente di phase2) | Sezione "Known issues" = vuota o "none" |
| `git tag phase-3-complete` pushato su origin | `git ls-remote --tags origin phase-3-complete` non vuoto |

**Tag `phase-3-complete` garantisce**: sistema dimostrabile a un cliente reale, CI che blocca le regressioni future, agente con prompt verticale-specifico, eval baseline aggiornata.

---

## 9. Pack verticali Phase 3

Descrizione dello scope minimo per ogni nuovo pack in Scenario A++. Ogni pack è strutturalmente identico a `real-estate-luxury` — solo il contenuto di dominio cambia.

### Pack: `dental-luxury`

**Dominio**: cliniche odontoiatriche premium / smile design / implantologia.

| Componente | Contenuto atteso |
|------------|-----------------|
| `ontology/entities.yaml` | Entità: `treatment`, `clinic`, `practitioner`, `before_after_case` |
| `ontology/personas.yaml` | Personas: `aesthetic_patient` (vuole smile design), `functional_patient` (dolore/urgenza), `implant_candidate` (età 45+, budget alto), `browsing` |
| `morph_rules/` | Regole: mostra `before_after_gallery` se `aesthetic_patient`; hero CTA = "Prenota consulenza gratuita" se `functional_patient` |
| `scoring/lead_scorecard.yaml` | Segnali: `consultation_requested` (25pt), `treatment_mentioned` (15pt), `budget_explicit` (15pt), `pain_mentioned` (10pt), `location_mentioned` (8pt) |
| `prompts/system.md` | System prompt per agente: ruolo "consulente clinic", NON diagnosi medica, raccolta segnali di lead silenziosamente |
| `evals/golden/` | ≥10 conversazioni golden (minimo per eval gate, target 20) |
| Demo page | `/demo/dental-luxury` — stessa struttura di `/demo/real-estate-luxury` |

**Vincoli GDPR/sanità**: nessun dato clinico nel KG. L'agente può raccogliere interesse per trattamenti ma non storicizza sintomi o diagnosi. DPA standard Anthropic + OpenAI è sufficiente.

---

### Pack: `aesthetic-clinic`

**Dominio**: cliniche di medicina estetica premium (filler, botox, corpo).

| Componente | Contenuto atteso |
|------------|-----------------|
| `ontology/entities.yaml` | Entità: `treatment`, `area_of_concern`, `practitioner`, `before_after_case` |
| `ontology/personas.yaml` | Personas: `anti_aging_seeker` (40+, botox/filler viso), `body_contouring_seeker` (dimagrimento non chirurgico), `bridal_candidate` (evento imminente), `browsing` |
| `morph_rules/` | Regole: mostra `before_after_gallery` se `anti_aging_seeker`; urgency banner se `bridal_candidate` con `timeline_urgent` |
| `scoring/lead_scorecard.yaml` | Segnali: `consultation_requested` (25pt), `treatment_mentioned` (15pt), `area_of_concern_specific` (12pt), `timeline_specific` (10pt), `budget_comfortable` (8pt) |
| `prompts/system.md` | System prompt: ruolo "patient coordinator", focus su comfort e riservatezza, raccolta lead silenziosamente |
| `evals/golden/` | ≥10 conversazioni golden |
| Demo page | `/demo/aesthetic-clinic` |

**Vincoli GDPR/sanità**: identici a dental-luxury. Zero diagnosi, zero anamnesi nel KG. Solo segnali di interesse commerciale.

---

**Struttura file comune a tutti i pack** (conforme BIBLE §5):

```
packs/<vertical>/
  ontology/
    entities.yaml
    personas.yaml
  morph_rules/
    default.yaml
  scoring/
    lead_scorecard.yaml
  prompts/
    system.md
  evals/
    golden/          # ≥10 JSON per eval gate
  components/        # React componenti pack-specifici (se necessari)
  pack.yaml          # manifest: id, version, display_name, engines_used
```

---

## 10. Decisioni architetturali Phase 3

Decisioni prese il 2026-05-18, recepite nel piano. Ogni decisione che introduce un nuovo pattern o dipendenza richiede un ADR formale prima dell'implementazione.

| # | Decisione | Rationale | ADR da produrre |
|---|-----------|-----------|-----------------|
| D-01 | **Cloud-only, nessun modello locale** | Semplifica ops, abbassa barriera di entry per nuovi pack; Ollama/Qwen aggiunti solo se emerge esigenza specifica di latenza o costo | — (conferma ADR-004 esistente) |
| D-02 | **Multi-provider LLM: Anthropic + OpenAI + OpenRouter** | LLMRouter già presente (BIBLE §6.4 circuit-breaker); OpenRouter come fallback economico; evita lock-in su singolo provider | ADR-007 (P3-03 prerequisito) |
| D-03 | **Embeddings: `text-embedding-3-large` (OpenAI)** | Qualità superiore a `ada-002`; costo ~$0.13/1M token; compatibile con pgvector già presente | ADR-007 (incluso in P3-03) |
| D-04 | **GDPR pack sanitari: DPA standard, nessun dato clinico nel KG** | Anthropic e OpenAI hanno DPA conformi GDPR per uso commerciale; i pack dental/aesthetic non storicizzano sintomi, diagnosi, anamnesi — solo segnali di interesse commerciale (treatment_mentioned, consultation_requested) | — (documentato in §9 e BIBLE §5.3) |
| D-05 | **DigIdentity Card: out of scope Phase 3** | Confermato: Card è progetto separato, nessun bridge API pianificato. Se emerge bisogno di condivisione identità visitatore, aprire ADR dedicato prima di implementare | — |
| D-06 | **Pack CI eval gate: cross-pack, un job per pack** | GitHub Actions: `eval-real-estate`, `eval-dental`, `eval-aesthetic` come job separati; un pack che fallisce blocca la merge ma non esegue gli altri job su regressione | ADR da produrre in P3-01 |
| D-07 | **Ontologia persona condivisa: `packs/shared/personas.yaml`** | Le personas con overlap cross-pack (es. `browsing`, tipi demografici) vivono in shared; le personas verticale-specifiche in `packs/<vertical>/ontology/personas.yaml` | — (risolve Phase 2 known issue #1) |

**ADR-007** è l'unico ADR bloccante prima di avviare P3-03 (real embeddings). Include: scelta provider, schema di costi, migration plan da embeddings mock/nulli.

---

## 11. Definition of Done Phase 3 (aggiornato — Scenario A++)

Sostituisce §8 per il Scenario A++ scelto. I criteri di §8 rimangono validi; questa sezione aggiunge i criteri multi-vertical.

**Criteri binari** — tutti devono essere `true` prima di taggare `phase-3-complete`:

| Criterio | Verifica |
|----------|----------|
| CI GitHub Actions verde su `main` (tutti i job) | `gh run list --limit 1 --json conclusion` = `success` |
| `pnpm test` ≥24 frontend, `pytest` ≥127 backend | Ultima riga di ogni suite (nessuna regressione) |
| Eval gate **real-estate-luxury**: baseline × 0.85 | `eval-runner` exit code 0, report in `eval-reports/` |
| Eval gate **dental-luxury**: baseline × 0.85 | Idem (golden ≥10 conv) |
| Eval gate **aesthetic-clinic**: baseline × 0.85 | Idem (golden ≥10 conv) |
| `prompts/system.md` reale in tutti e 3 i pack | File esiste, >200 char, no "placeholder" in nessuno dei 3 |
| Golden dataset ≥20 conv per real-estate-luxury | `ls packs/real-estate-luxury/evals/golden/*.json \| wc -l` ≥20 |
| Golden dataset ≥10 conv per dental-luxury | `ls packs/dental-luxury/evals/golden/*.json \| wc -l` ≥10 |
| Golden dataset ≥10 conv per aesthetic-clinic | `ls packs/aesthetic-clinic/evals/golden/*.json \| wc -l` ≥10 |
| ADR-007 (multi-provider + embeddings) prodotto e accettato | File `docs/adr/ADR-007-*.md` presente con status `Accepted` |
| Demo URL `/demo/dental-luxury` navigabile | HTTP 200 in staging o localhost |
| Demo URL `/demo/aesthetic-clinic` navigabile | HTTP 200 in staging o localhost |
| Spatial Experience v1 live su `/demo/real-estate-luxury` | Tour 360° sincronizzato con conversazione funzionante |
| Zero known issues aperti in `phase3-complete.md` | Sezione "Known issues" = vuota o "none" |
| `git tag phase-3-complete` pushato su origin | `git ls-remote --tags origin phase-3-complete` non vuoto |

**Tag `phase-3-complete` garantisce**: tre vertical dimostrabili, fat-core/lean-packs validato empiricamente, CI che blocca regressioni cross-pack, embeddings reali attivi, eval baseline aggiornata.

---

*Documento generato in automatico da Claude Code — non modificare manualmente. Per aggiornamenti, aprire una nuova sessione con REGOLA #0.*
