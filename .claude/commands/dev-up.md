---
name: dev-up
description: Boot the local development environment — Postgres + pgvector + Redis via Docker Compose, run migrations, seed demo tenant, healthcheck.
---

Run the following in sequence. Stop at the first failure and report.

```bash
# 1. Boot containers
docker compose up -d

# 2. Wait for Postgres to be ready
until docker exec digidentity-pg pg_isready -U digidentity; do sleep 1; done

# 3. Apply migrations
cd backend
uv run alembic upgrade head    # or `python -m core.db.migrate` depending on current setup

# 4. Seed demo tenant
uv run python scripts/seed_demo.py

# 5. Healthcheck
curl -fsS http://localhost:8000/health | jq .

# 6. Display useful URLs
echo ""
echo "Backend:      http://localhost:8000"
echo "Health:       http://localhost:8000/health"
echo "Demo tenant:  http://localhost:8000/tenants/lionard-demo/properties"
echo "OpenAPI:      http://localhost:8000/docs"
```

On Windows PowerShell, use `curl.exe` instead of `curl` (the PowerShell alias points to `Invoke-WebRequest`).

If any step fails, surface the error verbatim and suggest the fix from the project troubleshooting notes (typically: container not running, port conflict, missing env vars).
