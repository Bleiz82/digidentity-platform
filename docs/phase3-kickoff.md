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

## 7. Raccomandazione

**Scenario B — "Foundation Cliente"** con P3-03 (real embeddings) condizionato al budget.

**Motivazione**:

1. **Profilo utente**: Stefano è solo dev con competenza governance ma non senior engineering. Scenario A introduce il più rischioso dei candidati (P3-07 — Spatial, 🔴) come dipendenza critica per la demo. Un blocco su librerie 3D può costare 2 settimane. Scenario B non dipende da tecnologie nuove.

2. **Stato attuale**: nessun cliente reale menzionato, nessuna deadline. In questa condizione, investire 24h in Spatial prima di avere CI e prompts reali è una scelta sequenziale sbagliata: potresti fare una demo con un agente che risponde male, senza accorgerti delle regressioni.

3. **Lezione Phase 2**: il pattern /goal full-auto con stop solo al push funziona bene su STEP ben definiti (8-12h). P3-07 (Spatial, 24h) è troppo lungo per un singolo /goal senza checkpoint intermedi — rischio di loop >5 senza progresso.

4. **Ordine logico**: CI → prompts → ontologia → persistence è una catena dove ogni STEP migliora il successivo. La golden dataset (P3-02) è prerequisito de facto di P3-12 (Learning) e P3-08 (Static Manifestation). Costruirla subito sblocca Phase 4 senza costo aggiuntivo.

5. **Pivoting**: Scenario B non chiude la porta a Scenario A. Dopo B, aggiungere P3-07 (Spatial) è il naturale STEP 16 — ma a quel punto avrai CI che garantisce la stabilità durante l'implementazione.

**Contro**: se la risposta alla domanda §5.3 è "presentazione tra 4 settimane", Scenario A diventa la scelta corretta nonostante il rischio.

---

## 8. Definition of Done Phase 3

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

*Documento generato in automatico da Claude Code — non modificare manualmente. Per aggiornamenti, aprire una nuova sessione con REGOLA #0.*
