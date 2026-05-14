---
name: tenant-test
description: Run the cross-tenant isolation stress test. 50 concurrent requests across 5 tenants verifying zero data leak. Critical P0 test.
---

Run the tenant isolation test:

```bash
cd backend
uv run pytest tests/test_tenant_isolation.py -v --tb=short
```

This test:

1. Creates 5 isolated tenants in a clean test database.
2. Seeds each with marker properties tagged by tenant.
3. Spawns 50 concurrent requests (10 per tenant in parallel).
4. Asserts that every response contains only properties belonging to the calling tenant.

Result interpretation:

- **PASS** → tenant isolation holds under concurrency. Safe to ship.
- **FAIL** → P0 incident. STOP all feature work. The leak is in `core/db/tenant_context.py` or somewhere a session bypasses `with_tenant`. Investigate immediately.

If FAIL:

1. Capture the failure output.
2. Identify the request that returned cross-tenant data.
3. Trace from the route handler down to the DB query.
4. Look for: missing `with_tenant` wrapper, sync session reuse, `SET` without `LOCAL`, admin session leaking into a public route.
5. File the incident as P0 in the journal under `docs/journal/YYYY-MM-DD.md`.
6. Do not deploy anything until fixed.

This test runs in CI on every PR. It must remain green for the project to ship.
