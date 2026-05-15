---
name: sqlalchemy-rls
description: Multi-tenant Row-Level Security discipline for SQLAlchemy 2.0 async + asyncpg + PostgreSQL 16. The single most important pattern in the backend. Mishandling causes cross-tenant data leakage.
---

# SQLAlchemy + RLS Discipline

Multi-tenant isolation in DigIdentity is enforced at the database layer via PostgreSQL Row-Level Security (RLS). Application code MUST set the `app.tenant_id` GUC for each request inside its own transaction. Mishandling this causes cross-tenant data leakage — the worst possible failure mode for a SaaS.

This skill is the canonical recipe. ADR-003 codifies the same discipline.

## The contract in one sentence

Every database operation that touches tenant-scoped data runs inside a transaction where `SET LOCAL app.tenant_id = '<uuid>'` was executed AS THE FIRST STATEMENT.

## RLS policy template

Every tenant-scoped table has RLS enabled and a policy referencing `app.tenant_id`:

```sql
-- schema/policies.sql
ALTER TABLE properties ENABLE ROW LEVEL SECURITY;

CREATE POLICY tenant_isolation ON properties
    USING (tenant_id = current_setting('app.tenant_id', true)::uuid);

CREATE POLICY tenant_isolation_insert ON properties
    FOR INSERT WITH CHECK (tenant_id = current_setting('app.tenant_id', true)::uuid);
```

`current_setting('app.tenant_id', true)` — the `true` means "return NULL if unset" instead of raising. If NULL, no row matches: this is the safe default. If you ever see queries returning zero rows where they shouldn't, the GUC is unset → bug in your context management.

Tables WITHOUT `tenant_id` (e.g., `tenants` itself, `users`, system tables) do NOT have RLS. They are accessed only via admin paths with a separate connection.

## The `with_tenant` context manager (canonical)

```python
# core/db/tenant_context.py
from contextlib import asynccontextmanager
from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from loguru import logger

from core.db.engine import async_session_maker

@asynccontextmanager
async def with_tenant(tenant_id: UUID):
    """
    Open a session, begin transaction, SET LOCAL app.tenant_id, yield session.
    Commits on success, rolls back on exception. Closes session always.
    """
    if not isinstance(tenant_id, UUID):
        raise ValueError(f"tenant_id must be UUID, got {type(tenant_id).__name__}")

    async with async_session_maker() as session:
        async with session.begin():
            # CRITICAL: this must be the first statement of the transaction
            await session.execute(
                text("SET LOCAL app.tenant_id = :tid"),
                {"tid": str(tenant_id)},
            )
            try:
                yield session
            except Exception:
                logger.exception("error_in_tenant_context", tenant_id=str(tenant_id))
                raise
            # context manager from session.begin() commits on success
```

Usage in service code:

```python
from core.db.tenant_context import with_tenant

async def list_properties(tenant_id: UUID, filters: dict) -> list[Property]:
    async with with_tenant(tenant_id) as session:
        stmt = select(Property).where(...)
        result = await session.execute(stmt)
        return list(result.scalars().all())
```

In a FastAPI route:

```python
@router.get("/tenants/{slug}/properties")
async def list_props(slug: str, ...):
    tenant = await resolve_tenant(slug)        # admin connection, no RLS
    return await list_properties(tenant.id, ...)
```

## Why `SET LOCAL` and not session-level GUC

`SET LOCAL` scopes the value to the current transaction. When the transaction ends, the value is gone. This means even if asyncpg's connection pool reuses the connection for another request, the previous tenant's GUC is no longer set.

`SET` (without LOCAL) persists for the connection lifetime. With a pooled connection, this leaks tenant context between requests. NEVER use `SET app.tenant_id`. Always `SET LOCAL`.

## Connection pool configuration

```python
# core/db/engine.py
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker

engine = create_async_engine(
    settings.database_url,
    pool_size=20,
    max_overflow=10,
    pool_pre_ping=True,
    pool_recycle=1800,
    # asyncpg is the driver
    connect_args={
        "server_settings": {
            "application_name": "digidentity",
            "jit": "off",      # pgvector + JIT can cause unexpected regressions
        }
    },
)

async_session_maker = async_sessionmaker(
    engine,
    expire_on_commit=False,
    class_=AsyncSession,
)
```

## Multi-tenant request middleware

A FastAPI middleware extracts the tenant from the URL or token, then passes the UUID into service functions. The middleware does NOT set the GUC — the service does, inside `with_tenant`. Why: services are testable in isolation, middleware is HTTP-specific.

```python
@app.middleware("http")
async def tenant_resolution_middleware(request, call_next):
    # Extract tenant slug from URL, e.g., /tenants/lionard-demo/...
    parts = request.url.path.strip("/").split("/")
    if len(parts) >= 2 and parts[0] == "tenants":
        slug = parts[1]
        # Resolve via admin connection (no RLS)
        tenant = await tenant_resolver_admin.by_slug(slug)
        if tenant is None:
            return JSONResponse({"error": "tenant_not_found"}, status_code=404)
        request.state.tenant_id = tenant.id
    return await call_next(request)
```

## Admin / cross-tenant queries

Some operations legitimately need to read across tenants: scheduled jobs aggregating stats, the resolution of `tenants` table itself, super-admin dashboards.

These use a SEPARATE engine with no tenant_id and explicit admin role:

```python
# core/db/admin.py
admin_engine = create_async_engine(
    settings.admin_database_url,    # different role: digidentity_admin
    pool_size=5,
)

@asynccontextmanager
async def admin_session():
    """Cross-tenant operations. Use sparingly. Logged."""
    async with async_sessionmaker(admin_engine)() as session:
        logger.warning("admin_session_opened", caller=...)
        yield session
```

The `digidentity_admin` role has `BYPASSRLS` privilege. The `digidentity` role used by request handling does NOT. This is enforced at DB grant level.

## Testing tenant isolation

Mandatory test that must pass in CI:

```python
# tests/test_tenant_isolation.py
import asyncio
import pytest
from uuid import uuid4

@pytest.mark.asyncio
async def test_concurrent_cross_tenant_no_leak():
    """50 concurrent requests across 5 tenants — verify no leak."""
    tenant_ids = [uuid4() for _ in range(5)]
    # Pre-seed each tenant with a known marker property
    await seed_tenants(tenant_ids)

    async def query_tenant(tid):
        async with with_tenant(tid) as session:
            rows = await session.execute(select(Property))
            properties = rows.scalars().all()
            # All returned properties must belong to this tenant
            assert all(p.tenant_id == tid for p in properties), \
                f"LEAK: tenant {tid} saw rows from another tenant"

    tasks = []
    for _ in range(10):
        for tid in tenant_ids:
            tasks.append(asyncio.create_task(query_tenant(tid)))

    await asyncio.gather(*tasks)
```

This test runs on every PR. If it fails, halt all feature work.

## Common bugs and how to spot them

**Symptom**: queries return zero rows on a freshly seeded tenant.
**Cause**: GUC not set, RLS policy returning false for NULL.
**Fix**: ensure `with_tenant()` wrapper is used.

**Symptom**: cross-tenant data appears in responses.
**Cause**: query was executed on a connection from the pool that had a previous `SET` (without LOCAL).
**Fix**: audit for any `SET` without LOCAL. Replace.

**Symptom**: insert fails with "row violates row-level security policy".
**Cause**: INSERT path didn't set GUC, or row has wrong tenant_id.
**Fix**: ensure object's `tenant_id` matches the context's tenant_id.

**Symptom**: background job sees no data.
**Cause**: Celery task didn't enter `with_tenant`.
**Fix**: every Celery task that touches tenant data wraps its work in `async_to_sync(with_tenant(...))`.

## Forbidden patterns

```python
# FORBIDDEN: passing session into a function that doesn't know about tenant context
async def some_helper(session: AsyncSession): ...

# CORRECT: pass tenant_id, helper opens its own context
async def some_helper(tenant_id: UUID): ...

# FORBIDDEN: long-lived session shared across requests
app.state.session = ...

# FORBIDDEN: setting tenant_id outside transaction
await session.execute(text("SET app.tenant_id = ..."))

# FORBIDDEN: trusting tenant_id from request body
@router.post(...)
async def create(req: CreateReq):
    async with with_tenant(req.tenant_id) as session: ...  # NO

# CORRECT: tenant_id comes from authenticated context (URL slug, JWT claim, etc.)
@router.post(...)
async def create(req: CreateReq, request: Request):
    tenant_id = request.state.tenant_id
    async with with_tenant(tenant_id) as session: ...
```

## Migration safety

When writing migrations:

- New tenant-scoped tables: enable RLS in the same migration, create policy in the same migration. Never deploy a table without RLS then add it later.
- Backfills: use `admin_session()` explicitly, log every step, narrow scope.
- DROP / ALTER on tenant-scoped tables: take a backup, test on staging with realistic tenant count.

Migration template snippet:

```sql
-- 003_add_visitor_sessions.sql
CREATE TABLE visitor_sessions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    visitor_hash TEXT NOT NULL,
    inferred_personas JSONB,
    signals JSONB,
    confidence REAL,
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX idx_visitor_sessions_tenant_hash ON visitor_sessions (tenant_id, visitor_hash);

ALTER TABLE visitor_sessions ENABLE ROW LEVEL SECURITY;

CREATE POLICY tenant_isolation ON visitor_sessions
    USING (tenant_id = current_setting('app.tenant_id', true)::uuid);

CREATE POLICY tenant_isolation_insert ON visitor_sessions
    FOR INSERT WITH CHECK (tenant_id = current_setting('app.tenant_id', true)::uuid);
```
