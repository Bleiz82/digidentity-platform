# ADR-003: Tenant Isolation Discipline

- **Status**: proposed
- **Date**: 2026-05-14
- **Authors**: Stefano Corda
- **BIBLE refs**: §5 (fat core / lean packs), §6.1 (Knowledge Graph Engine — RLS discipline), §10.3 (testing strategy)
- **Supersedes**: n/a
- **Superseded by**: n/a

---

## Contesto

DigIdentity Living Site è un sistema multi-tenant in cui ogni tenant possiede un `tenant.yaml` e un sottoinsieme di dati isolati nel database. Il core condivide la stessa istanza PostgreSQL 16 per tutti i tenant (architettura shared-schema). L'isolamento è garantito a livello di database tramite Row-Level Security (RLS), integrato con SQLAlchemy 2.0 async + asyncpg.

Il rischio primario è il **cross-tenant data leak**: una request del tenant A che restituisce, scrive o cancella dati del tenant B. Questo è un bug di sicurezza critico, non gestibile a posteriori.

Questo ADR stabilisce le regole tecniche non-negoziabili per: il meccanismo RLS scelto e la sua semantica transazionale; il pattern di session/transaction in SQLAlchemy; la scelta del connection pool e le sue implicazioni su RLS; la difesa applicativa a più livelli; la struttura dei test di isolamento in CI.

---

## Opzioni considerate

### Area A — Meccanismo RLS primario

#### A1 — `SET LOCAL app.tenant_id = :id` *(scelta adottata)*

Imposta la variabile di configurazione PostgreSQL a livello di transazione. `SET LOCAL` ha effetto solo per la durata della transazione corrente: al `COMMIT` o `ROLLBACK` il valore viene eliminato automaticamente (documentazione PostgreSQL 16: "The effects of SET LOCAL last only till the end of the current transaction"). La connessione ritorna al pool nello stato pulito, senza residui. Overhead stimato: **~1–5 μs per transazione** (ordine di grandezza da benchmark asyncpg — trascurabile rispetto a I/O query).

Le policy RLS si appoggiano su `current_setting('app.tenant_id', true)` con flag `missing_ok = true` per evitare eccezioni su connessioni senza contesto impostato.

#### A2 — Session-level `SET app.tenant_id = :id`

Imposta la variabile per tutta la durata della connessione. In un pool, se la connessione viene riutilizzata da un altro tenant prima del reset, il leak è silenzioso e difficile da rilevare in produzione.

**Perché scartato:** violazione del principio fail-fast; il pool non può garantire che il reset avvenga prima della restituzione della connessione, specialmente in caso di eccezione non gestita.

#### A3 — Nessun RLS, isolamento applicativo puro

Ogni query include `WHERE tenant_id = :id` gestito a livello applicativo. Flessibile, ma fragile: basta omettere un `WHERE` per esporre dati cross-tenant. Non offre garanzie enforcement a livello database.

**Perché scartato:** non soddisfa il requisito BIBLE §6.1 che esige RLS come meccanismo primario. Un bug applicativo bypassa l'intera protezione.

#### A4 — `current_setting()` con fallback a tenant di default nelle policy RLS

Le policy usano `COALESCE(current_setting('app.tenant_id', true), 'default')`. Query fuori contesto non falliscono — ritornano i dati del tenant placeholder.

**Perché scartato:** viola il principio fail-fast and loud. Un errore di programmazione diventa invisibile: nessuna eccezione, dati sbagliati restituiti silenziosamente.

---

### Area B — Pattern session/transaction in SQLAlchemy

#### B1 — Context manager `with_tenant(tenant_id)` esplicito *(scelta adottata)*

```python
async with with_tenant(tenant_id) as session:
    result = await session.execute(select(Entity))
```

Il context manager: (1) acquisisce una connessione dal pool, (2) apre una transazione esplicita, (3) esegue `SET LOCAL app.tenant_id = :id`, (4) al termine fa `COMMIT` — o `ROLLBACK` su eccezione.

**Isolation level:** `READ COMMITTED` (default PostgreSQL). Motivazione: RLS valuta le policy al momento della lettura di ogni riga; `READ COMMITTED` è sufficiente perché la variabile `app.tenant_id` è impostata per tutta la transazione corrente. `REPEATABLE READ` o `SERIALIZABLE` aggiungerebbero serialization overhead e rischio di retry su serialization failure senza benefici aggiuntivi per l'isolamento tenant.

**Comportamento nesting:** se `with_tenant(B)` viene chiamato mentre è già attivo un contesto `with_tenant(A)`, viene sollevato immediatamente `TenantContextError: nested tenant context is not allowed (active: A, requested: B)`. Il nesting silenzioso è proibito: maschererebbe bug di architettura rendendo invisibile quale tenant sta operando.

**Comportamento fuori contesto:** qualsiasi query su tabelle tenant-protette senza contesto attivo solleva `TenantContextError: no active tenant context` nel layer `TenantAwareRepository`, prima di toccare il database. Non un errore DB — un errore applicativo esplicito e immediato.

#### B2 — Middleware FastAPI automatico che wrappa ogni request

Il middleware intercetta ogni request, estrae `tenant_id` dal JWT, apre `with_tenant`, chiude alla fine della request.

**Perché scartato come meccanismo primario:** (a) nasconde la dipendenza dal contesto DB rendendola implicita — i test devono simulare request HTTP per attivare il contesto; (b) non protegge background tasks e Celery workers che non passano dal middleware HTTP; (c) un task che bypassa il middleware ha il DB aperto senza tenant context. Rimane come strato di verifica aggiuntivo (Area D).

#### B3 — Decorator `@require_tenant` per endpoint

Sintatticamente esplicito ma verboso e soggetto a dimenticanze. Protegge solo il punto di entrata HTTP, non i layer repository/service interni.

**Perché scartato:** non garantisce isolamento a livello DB se i repository vengono chiamati da altri contesti (script, Celery, test utility).

---

### Area C — Connection pooling e interazione con RLS

#### C1 — asyncpg pool nativo *(scelta adottata)*

asyncpg garantisce che ogni `async with session.begin()` mantenga una singola connessione fisica per tutta la transazione. `SET LOCAL` è valido per tutta la durata della transazione su quella connessione. Al `COMMIT` la variabile scompare: la connessione ritorna al pool pulita. Overhead acquisizione connessione da pool già warm: **~0.1–0.5 ms**.

#### C2 — PgBouncer in transaction mode

In transaction mode, PgBouncer può assegnare statement diversi della stessa sessione logica a connessioni fisiche diverse. `SET LOCAL` è legato alla connessione fisica: se PgBouncer ruota la connessione tra `SET LOCAL` e la query successiva, il contesto tenant è perso e RLS non si applica. Il leak è silenzioso.

**Perché scartato:** incompatibile strutturalmente con `SET LOCAL`. Non esistono workaround affidabili senza abbandonare transaction mode, che è la ragione d'essere di PgBouncer.

#### C3 — PgBouncer in session mode

In session mode la connessione fisica è mantenuta per tutta la sessione logica: `SET LOCAL` funziona correttamente. Ma elimina i vantaggi di multiplexing di PgBouncer. Overhead aggiuntivo rispetto ad asyncpg nativo senza benefici reali alle dimensioni attuali.

**Perché scartato:** aggiunge un hop di rete (asyncpg → PgBouncer → PostgreSQL) senza vantaggio rispetto ad asyncpg diretto nel caso d'uso corrente.

---

### Area D — Defense in depth applicativo

**Strato 1 — FastAPI middleware di verifica (non sostituto di `with_tenant`):** intercetta ogni request HTTP, verifica che `tenant_id` sia presente e valido nel JWT prima di raggiungere qualsiasi handler. Se mancante: `401`. Se non autorizzato: `403`. Non apre transazioni.

**Strato 2 — `TenantAwareRepository` base class:** ogni repository eredita da questa classe. Il metodo `_assert_tenant_context()` viene chiamato all'inizio di ogni operazione DB e solleva `TenantContextError` se `current_tenant_id()` è `None`. Protegge anche background tasks, CLI scripts, seeders.

**Comportamento in development e test:** `with_tenant` è usato direttamente nei test senza simulare request HTTP. I seeders usano `with_tenant(SEED_TENANT_ID)` esplicito. Non esiste modalità "bypass per development" — production e test percorrono lo stesso path.

---

### Area E — Test strategy CI

**Struttura del test di isolamento:**

```python
# pytest-asyncio + testcontainers (PostgreSQL 16 reale, no mock)
@pytest.mark.asyncio
async def test_tenant_isolation_concurrent():
    # Setup: 5 tenant, 10 record ciascuno con owner_marker univoco
    # tenant_i, record_j → owner_marker = f"t{i}_r{j}"

    async def fetch_for_tenant(tenant_id, expected_i):
        async with with_tenant(tenant_id) as session:
            rows = await session.execute(select(Node))
            results = rows.scalars().all()
            assert len(results) == 10
            for r in results:
                assert r.tenant_id == tenant_id, f"LEAK: got {r.tenant_id}"
                assert r.owner_marker.startswith(f"t{expected_i}_"), \
                    f"LEAK: got {r.owner_marker}"

    # 50 task concorrenti (10 per tenant)
    tasks = [fetch_for_tenant(tid, i) for i, tid in enumerate(tenant_ids)
             for _ in range(10)]
    await asyncio.gather(*tasks)
```

**Cosa asserisce:** non solo "nessun errore", ma verifica esplicita che ogni riga nella response abbia `tenant_id == expected` e `owner_marker` con prefisso corretto. Un record intruso viene identificato con il tenant di provenienza.

**Soglia:** **zero leak tollerati** su 50 request concorrenti.

**Pipeline CI:** la suite `ci-tenant-isolation` gira ad ogni PR che tocca `db/`, `middleware/`, `repositories/`, o `migrations/`. Avvio testcontainer: ~15–30 s aggiuntivi per pipeline.

---

## Decisione

1. **RLS via `SET LOCAL app.tenant_id = :id`** — semantica transazionale: il valore scompare al `COMMIT`/`ROLLBACK`.
2. **`with_tenant(tenant_id)` context manager obbligatorio** — isolation level `READ COMMITTED`, nesting proibito con errore esplicito, query fuori contesto falliscono fast and loud.
3. **asyncpg pool nativo** — nessun PgBouncer nell'architettura attuale.
4. **Defense in depth su due strati**: middleware FastAPI (verifica JWT) + `TenantAwareRepository` (rifiuta query senza contesto).
5. **Test CI**: 50 request concorrenti su 5 tenant, asserzione esplicita su `tenant_id` e `owner_marker`, zero leak tollerati, PostgreSQL reale via testcontainers.

---

## Conseguenze

### Positive

- Isolamento garantito a livello database: un bug applicativo non bypassa RLS.
- `SET LOCAL` pulisce automaticamente la connessione al `COMMIT`/`ROLLBACK`: nessun residuo nel pool.
- Fail fast and loud: codice che dimentica `with_tenant` fallisce immediatamente, non silenziosamente in produzione.
- Test CI su PostgreSQL reale: nessun falso positivo da mock DB.
- Comportamento uniforme tra production, test e seeders — nessuna modalità bypass che crea divergenze.

### Negative

- **Disciplina manuale per ogni sviluppatore**: ogni accesso DB deve essere wrappato in `with_tenant`. Non è automatico. La code review deve verificarlo ad ogni PR. Costo cognitivo non trascurabile.
- **Background tasks e Celery workers**: non passano dal middleware HTTP; richiedono `with_tenant` esplicito in ogni task. Errore facile da commettere, difficile da rilevare in staging se i test di isolamento non coprono i worker.
- **Debug notturno di un sospetto leak**: richiede (a) log strutturati con `tenant_id` per ogni query, (b) accesso a `pg_stat_activity` per vedere `app.tenant_id` per connessione attiva, (c) query su `pg_stat_statements`. MTTR stimato: 30–90 minuti per un developer esperto con accesso DB diretto.
- **Testcontainers in CI**: avvio PostgreSQL reale aggiunge ~15–30 s per pipeline. Su PR frequenti, costo cumulativo non trascurabile.
- **Nesting proibito richiede refactoring preventivo**: codice che chiama funzioni DB da dentro un contesto tenant esistente deve essere ristrutturato prima del merge. Costo di migrazione non trascurabile se il codebase cresce prima che la disciplina sia consolidata.
- **PgBouncer escluso limita la scalabilità a lungo termine**: oltre ~300–500 connessioni concorrenti, il pool asyncpg nativo può diventare un collo di bottiglia. Vedi Questioni Aperte.

### Neutre

- `READ COMMITTED` non introduce anomalie rilevanti per il caso d'uso attuale (lettura/scrittura di record tenant-owned senza dipendenze cross-tenant nello stesso statement).
- La scelta di testcontainers vs un'istanza PostgreSQL fissa in CI è reversibile senza modificare il codice di produzione.

---

## Piano di migrazione / rollout

- [ ] Implementare `with_tenant()` context manager e `TenantAwareRepository` base class.
- [ ] Scrivere le RLS policy su tutte le tabelle tenant-protette con `current_setting('app.tenant_id', true)`.
- [ ] Aggiungere middleware FastAPI di verifica JWT.
- [ ] Aggiungere controllo pre-query in `TenantAwareRepository`.
- [ ] Audit completo: grep `session.execute` senza `with_tenant` nel call stack — wrappare tutto.
- [ ] Scrivere e far passare il test di isolamento concorrente su staging.
- [ ] Attivare RLS in produzione su una tabella pilota, verificare, estendere a tutte le tabelle.
- [ ] Aggiungere `ci-tenant-isolation` alla pipeline CI come gate obbligatorio.

---

## Questioni aperte

1. **Scalabilità connessioni oltre ~300–500 concorrenti**: se i tenant attivi crescono, il pool asyncpg può diventare un collo di bottiglia. Alternativa da valutare: PgBouncer session mode + `RESET app.tenant_id` esplicito a fine transazione. Richiede ADR separato.
2. **Convenzione `with_tenant` nei Celery workers**: non definita in questo ADR. Proposta: `tenant_id` come argomento obbligatorio di ogni task con decorator `@tenant_task` che wrappa automaticamente in `with_tenant`. Da formalizzare.
3. **Operazioni amministrative cross-tenant**: report globali o operazioni di superuser che devono leggere dati di più tenant richiedono un meccanismo separato (superuser connection senza RLS o policy con ruolo admin). Fuori scope di questo ADR.

---

## Riferimenti

- PostgreSQL 16 docs — `SET LOCAL` semantics
- PostgreSQL 16 docs — Row Security Policies
- asyncpg pool documentation
- BIBLE v3 §5 — fat core / lean packs, principio multi-tenant isolation
- BIBLE v3 §6.1 — Knowledge Graph Engine, disciplina RLS
- BIBLE v3 §10.3 — Testing strategy, tenant isolation test
- ADR-001 — Stack canonico (PostgreSQL 16 + asyncpg)
