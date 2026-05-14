"""SSE endpoint tests — ADR-002.

No testcontainers. Celery log_usage.delay is mocked.
Uses httpx.AsyncClient with ASGITransport.
"""

import json
import time
from unittest.mock import MagicMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

# Patch log_usage.delay at module import time so it doesn't try to connect to DB
_MOCK_DELAY = MagicMock()

VALID_TENANT_ID = "550e8400-e29b-41d4-a716-446655440000"
VALID_CONV_ID = "a1b2c3d4-e5f6-7890-abcd-ef1234567890"


@pytest.fixture
async def client():
    with patch("digidentity_api.tasks.usage.log_usage") as mock_task:
        mock_task.delay = _MOCK_DELAY
        from digidentity_api.main import app

        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as ac:
            yield ac


# ── Path parameter validation ─────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_sse_invalid_conversation_id_rejected(client: AsyncClient) -> None:
    """Non-UUID conversation_id → 422 (FastAPI path param validation)."""
    response = await client.get(
        "/api/v1/conversations/pippo/stream",
        headers={"X-Tenant-Id": VALID_TENANT_ID},
    )
    assert response.status_code == 422


# ── Auth / header validation ──────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_sse_requires_tenant_header(client: AsyncClient) -> None:
    """Missing X-Tenant-Id → 401."""
    response = await client.get(f"/api/v1/conversations/{VALID_CONV_ID}/stream")
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_sse_wrong_tenant_uuid(client: AsyncClient) -> None:
    """Invalid UUID in X-Tenant-Id → 400."""
    response = await client.get(
        f"/api/v1/conversations/{VALID_CONV_ID}/stream",
        headers={"X-Tenant-Id": "not-a-uuid"},
    )
    assert response.status_code == 400


# ── Accept negotiation ────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_sse_accept_json_returns_406(client: AsyncClient) -> None:
    """Accept: application/json without text/event-stream → 406."""
    response = await client.get(
        f"/api/v1/conversations/{VALID_CONV_ID}/stream",
        headers={
            "X-Tenant-Id": VALID_TENANT_ID,
            "Accept": "application/json",
        },
    )
    assert response.status_code == 406
    assert response.headers.get("X-Suggested-Fallback") == "long-polling"


@pytest.mark.asyncio
async def test_sse_accept_both_allows_stream(client: AsyncClient) -> None:
    """Accept: text/event-stream,application/json → allowed."""
    with patch("digidentity_api.tasks.usage.log_usage") as mock_task:
        mock_task.delay = MagicMock()
        async with client.stream(
            "GET",
            f"/api/v1/conversations/{VALID_CONV_ID}/stream",
            params={"prompt": "ciao"},
            headers={
                "X-Tenant-Id": VALID_TENANT_ID,
                "Accept": "text/event-stream, application/json",
            },
        ) as response:
            assert response.status_code == 200


# ── SSE streaming content ─────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_sse_emits_text_events(client: AsyncClient) -> None:
    """Stream returns text events and correct headers."""
    with patch("digidentity_api.tasks.usage.log_usage") as mock_task:
        mock_task.delay = MagicMock()
        collected_events = []

        async with client.stream(
            "GET",
            f"/api/v1/conversations/{VALID_CONV_ID}/stream",
            params={"prompt": "ciao"},
            headers={"X-Tenant-Id": VALID_TENANT_ID},
        ) as response:
            assert response.status_code == 200
            assert "text/event-stream" in response.headers.get("content-type", "")
            assert response.headers.get("Cache-Control") == "no-cache"

            async for line in response.aiter_lines():
                line = line.strip()
                if line.startswith("data: "):
                    payload = line[6:]
                    try:
                        event = json.loads(payload)
                        collected_events.append(event)
                    except json.JSONDecodeError:
                        pass

    text_events = [e for e in collected_events if e.get("type") == "text"]
    assert len(text_events) >= 1, f"Expected ≥1 text events, got: {collected_events}"


@pytest.mark.asyncio
async def test_sse_cloudflare_headers_present(client: AsyncClient) -> None:
    """Required anti-buffering headers are present."""
    with patch("digidentity_api.tasks.usage.log_usage") as mock_task:
        mock_task.delay = MagicMock()
        async with client.stream(
            "GET",
            f"/api/v1/conversations/{VALID_CONV_ID}/stream",
            params={"prompt": "ciao"},
            headers={"X-Tenant-Id": VALID_TENANT_ID},
        ) as response:
            assert response.headers.get("Cache-Control") == "no-cache"
            assert response.headers.get("X-Accel-Buffering") == "no"


@pytest.mark.asyncio
async def test_sse_ttfc_under_800ms(client: AsyncClient) -> None:
    """Time-to-first-chunk must be < 800ms."""
    with patch("digidentity_api.tasks.usage.log_usage") as mock_task:
        mock_task.delay = MagicMock()
        first_chunk_time: float | None = None
        start = time.monotonic()

        async with client.stream(
            "GET",
            f"/api/v1/conversations/{VALID_CONV_ID}/stream",
            params={"prompt": "ciao"},
            headers={"X-Tenant-Id": VALID_TENANT_ID},
        ) as response:
            async for line in response.aiter_lines():
                line = line.strip()
                if line.startswith("data: "):
                    payload = line[6:]
                    try:
                        event = json.loads(payload)
                        if event.get("type") == "text" and first_chunk_time is None:
                            first_chunk_time = time.monotonic() - start
                            break
                    except json.JSONDecodeError:
                        pass

        assert first_chunk_time is not None, "No text event received"
        assert first_chunk_time < 0.8, f"TTFC was {first_chunk_time:.3f}s — expected < 800ms"


@pytest.mark.asyncio
async def test_sse_fail_mode_503(client: AsyncClient) -> None:
    """X-Mock-Fail-Mode: 503 on all providers → stream_interrupted events or error."""
    with patch("digidentity_api.tasks.usage.log_usage") as mock_task:
        mock_task.delay = MagicMock()
        events = []

        async with client.stream(
            "GET",
            f"/api/v1/conversations/{VALID_CONV_ID}/stream",
            params={"prompt": "ciao"},
            headers={
                "X-Tenant-Id": VALID_TENANT_ID,
                "X-Mock-Fail-Mode": "503",
            },
        ) as response:
            assert response.status_code == 200
            async for line in response.aiter_lines():
                line = line.strip()
                if line.startswith("data: "):
                    payload = line[6:]
                    try:
                        events.append(json.loads(payload))
                    except json.JSONDecodeError:
                        pass

    # Should have at least one stream_interrupted or error event
    types = {e.get("type") for e in events}
    assert "stream_interrupted" in types or "error" in types, (
        f"Expected interrupt/error events, got: {events}"
    )
