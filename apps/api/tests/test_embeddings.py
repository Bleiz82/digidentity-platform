"""Tests for Embeddings engine — ADR-007 P3-03.

All tests use mock providers or patched OpenAI. NO real API calls.
"""

from __future__ import annotations

import math
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from digidentity_api.engines.embeddings.providers.mock_provider import MockEmbeddingProvider
from digidentity_api.engines.embeddings.providers.openai_provider import OpenAIEmbeddingProvider
from digidentity_api.engines.embeddings.router import EmbeddingRouter
from digidentity_api.engines.agent.tools.registry import ToolRegistry

TENANT_ID = "00000000-0000-0000-0000-000000000001"


# ── 1. MockEmbeddingProvider: deterministic unit vectors ─────────────────────

@pytest.mark.asyncio
async def test_mock_provider_deterministic() -> None:
    provider = MockEmbeddingProvider(dimensions=3072)
    vecs = await provider.embed(["hello", "world"])
    assert len(vecs) == 2
    # Both vectors are identical (constant unit vector)
    assert vecs[0] == vecs[1]
    # All components equal 1/sqrt(3072)
    expected = 1.0 / math.sqrt(3072)
    assert abs(vecs[0][0] - expected) < 1e-9
    assert len(vecs[0]) == 3072


# ── 2. MockEmbeddingProvider: custom_fn produces per-input vectors ───────────

@pytest.mark.asyncio
async def test_mock_provider_custom_fn() -> None:
    def custom(text: str) -> list[float]:
        return [float(ord(text[0]) if text else 0)] + [0.0] * 3071

    provider = MockEmbeddingProvider(dimensions=3072, custom_fn=custom)
    vecs = await provider.embed(["a", "b"])
    assert vecs[0][0] == float(ord("a"))
    assert vecs[1][0] == float(ord("b"))
    assert len(vecs[0]) == 3072


# ── 3. OpenAIEmbeddingProvider (mocked): returns 3072-dim vectors ────────────

@pytest.mark.asyncio
async def test_openai_provider_mocked_returns_3072_dims() -> None:
    fake_embedding = [0.1] * 3072

    fake_data_item = MagicMock()
    fake_data_item.index = 0
    fake_data_item.embedding = fake_embedding

    fake_response = MagicMock()
    fake_response.data = [fake_data_item]

    mock_client = MagicMock()
    mock_client.embeddings = MagicMock()
    mock_client.embeddings.create = AsyncMock(return_value=fake_response)

    provider = OpenAIEmbeddingProvider(
        api_key="sk-test", model="text-embedding-3-large", dimensions=3072
    )
    # Replace internal client to avoid real API calls
    provider._client = mock_client

    vecs = await provider.embed(["test query"])

    assert len(vecs) == 1
    assert len(vecs[0]) == 3072
    assert vecs[0][0] == pytest.approx(0.1)


# ── 4. EmbeddingRouter selects mock when EMBEDDING_PROVIDER=mock ─────────────

@pytest.mark.asyncio
async def test_router_selects_mock_when_provider_mock() -> None:
    mock_provider = MockEmbeddingProvider(dimensions=3072)
    router = EmbeddingRouter(provider=mock_provider)
    vecs = await router.embed(["test"])
    assert len(vecs) == 1
    assert len(vecs[0]) == 3072


# ── 5. EmbeddingRouter falls back to mock when OPENAI_API_KEY absent ─────────

def test_router_fallback_to_mock_when_no_key() -> None:
    with patch(
        "digidentity_api.engines.embeddings.router.settings"
    ) as mock_settings:
        mock_settings.EMBEDDING_PROVIDER = "openai"
        mock_settings.OPENAI_API_KEY = ""  # no key
        mock_settings.EMBEDDING_MODEL = "text-embedding-3-large"
        mock_settings.EMBEDDING_DIMENSIONS = 3072

        from digidentity_api.engines.embeddings.router import _build_provider  # noqa: PLC0415
        provider = _build_provider()
        assert isinstance(provider, MockEmbeddingProvider)


# ── 6. EmbeddingRouter selects OpenAI when key + EMBEDDING_PROVIDER=openai ───

def test_router_selects_openai_when_key_set() -> None:
    with patch(
        "digidentity_api.engines.embeddings.router.settings"
    ) as mock_settings, patch(
        "digidentity_api.engines.embeddings.providers.openai_provider.AsyncOpenAI",
        return_value=MagicMock(),
    ):
        mock_settings.EMBEDDING_PROVIDER = "openai"
        mock_settings.OPENAI_API_KEY = "sk-test-key"
        mock_settings.EMBEDDING_MODEL = "text-embedding-3-large"
        mock_settings.EMBEDDING_DIMENSIONS = 3072

        from digidentity_api.engines.embeddings.router import _build_provider  # noqa: PLC0415
        provider = _build_provider()
        assert isinstance(provider, OpenAIEmbeddingProvider)


# ── 7. Batch split >100 inputs ───────────────────────────────────────────────

@pytest.mark.asyncio
async def test_openai_provider_splits_batch_above_100() -> None:
    call_count = 0

    async def fake_create(**kwargs: Any) -> MagicMock:
        nonlocal call_count
        call_count += 1
        input_texts = kwargs["input"]
        items = []
        for i, _ in enumerate(input_texts):
            item = MagicMock()
            item.index = i
            item.embedding = [0.0] * 3072
            items.append(item)
        resp = MagicMock()
        resp.data = items
        return resp

    mock_client = MagicMock()
    mock_client.embeddings = MagicMock()
    mock_client.embeddings.create = fake_create

    provider = OpenAIEmbeddingProvider(
        api_key="sk-test", model="text-embedding-3-large", dimensions=3072
    )
    provider._client = mock_client

    texts = [f"text {i}" for i in range(150)]
    vecs = await provider.embed(texts)

    assert len(vecs) == 150
    assert call_count == 2  # 100 + 50


# ── 8. Retry on rate limit ───────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_openai_provider_retries_on_rate_limit() -> None:
    from openai import RateLimitError  # noqa: PLC0415

    call_count = 0

    async def fake_create(**_: Any) -> MagicMock:
        nonlocal call_count
        call_count += 1
        if call_count < 2:
            raise RateLimitError(
                message="rate limit",
                response=MagicMock(status_code=429, headers={}),
                body=None,
            )
        item = MagicMock()
        item.index = 0
        item.embedding = [0.5] * 3072
        resp = MagicMock()
        resp.data = [item]
        return resp

    provider = OpenAIEmbeddingProvider(
        api_key="sk-test", model="text-embedding-3-large", dimensions=3072
    )
    mock_client = MagicMock()
    mock_client.embeddings = MagicMock()
    mock_client.embeddings.create = fake_create
    provider._client = mock_client

    with patch(
        "digidentity_api.engines.embeddings.providers.openai_provider.asyncio.sleep",
        new=AsyncMock(),
    ):
        vecs = await provider.embed(["test"])

    assert call_count == 2
    assert len(vecs[0]) == 3072


# ── 9. EmbeddingRouter raises on dimension mismatch ─────────────────────────

@pytest.mark.asyncio
async def test_router_raises_on_dimension_mismatch() -> None:
    class WrongDimProvider(MockEmbeddingProvider):
        async def embed(self, texts: list[str], model: str | None = None) -> list[list[float]]:
            return [[1.0, 2.0]]  # only 2 dims, not 3072

    wrong_provider = WrongDimProvider(dimensions=3072)
    router = EmbeddingRouter(provider=wrong_provider)
    with pytest.raises(ValueError, match="dimension mismatch"):
        await router.embed(["test"])


# ── 10. kg_search uses EmbeddingRouter and returns embedding_dims ────────────

@pytest.mark.asyncio
async def test_kg_search_uses_embedding_router() -> None:
    mock_provider = MockEmbeddingProvider(dimensions=3072)
    router = EmbeddingRouter(provider=mock_provider)
    registry = ToolRegistry(tenant_id=TENANT_ID, embedding_router=router)

    result = await registry.kg_search(query="luxury villa", top_k=3)

    assert "results" in result
    assert len(result["results"]) == 3
    # Confirm embedding was called: result includes embedding_dims key
    assert "embedding_dims" in result
    assert result["embedding_dims"] == 3072


# ── BONUS 11. Regression: existing KG search + lead_update_score still work ──

@pytest.mark.asyncio
async def test_registry_regression_lead_and_kg_search() -> None:
    """Existing functionality not broken by embedding integration."""
    mock_provider = MockEmbeddingProvider(dimensions=3072)
    router = EmbeddingRouter(provider=mock_provider)
    registry = ToolRegistry(tenant_id=TENANT_ID, embedding_router=router)

    kg = await registry.kg_search(query="appartamento", top_k=2)
    assert kg["tenant_id"] == TENANT_ID
    assert len(kg["results"]) == 2

    lead = registry.lead_update_score(signal="budget_explicit", weight=0.5)
    assert lead["total"] == pytest.approx(0.5)
