"""CORS middleware tests — Phase 2 dev configuration."""

import pytest
from httpx import ASGITransport, AsyncClient

from digidentity_api.main import app

_STREAM_PATH = "/api/v1/conversations/00000000-0000-0000-0000-000000000099/stream"


@pytest.mark.asyncio
async def test_cors_preflight_allows_localhost_3000() -> None:
    """OPTIONS preflight from localhost:3000 must be permitted."""
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as ac:
        resp = await ac.options(
            _STREAM_PATH,
            headers={
                "Origin": "http://localhost:3000",
                "Access-Control-Request-Method": "GET",
                "Access-Control-Request-Headers": "X-Tenant-Id",
            },
        )
    assert resp.status_code == 200
    assert resp.headers.get("access-control-allow-origin") == "http://localhost:3000"


@pytest.mark.asyncio
async def test_cors_rejects_unknown_origin() -> None:
    """Origin not in allowlist must not receive CORS allow-origin header."""
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as ac:
        resp = await ac.options(
            _STREAM_PATH,
            headers={
                "Origin": "http://evil.example.com",
                "Access-Control-Request-Method": "GET",
            },
        )
    assert resp.headers.get("access-control-allow-origin") is None
