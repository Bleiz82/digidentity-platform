import os

import pytest
from httpx import AsyncClient, ASGITransport

from digidentity_api.main import app


@pytest.fixture
async def client() -> AsyncClient:
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as ac:
        yield ac


# Marker for tests that require a live PostgreSQL instance.
# In CI: backend-test job provides DATABASE_URL_SYNC via service container.
# Locally without Docker: skip automatically.
requires_db = pytest.mark.skipif(
    not os.getenv("DATABASE_URL_SYNC"),
    reason="DATABASE_URL_SYNC not set — requires a running PostgreSQL instance",
)
