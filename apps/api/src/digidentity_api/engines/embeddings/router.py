"""EmbeddingRouter — selects provider based on config, ADR-007.

Selection logic:
  1. If EMBEDDING_PROVIDER=mock OR OPENAI_API_KEY is empty → MockEmbeddingProvider
  2. If EMBEDDING_PROVIDER=openai AND OPENAI_API_KEY is set → OpenAIEmbeddingProvider

The router is instantiated once per process via get_router() (module-level singleton).
Tests instantiate providers directly to avoid env dependency.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from digidentity_api.config import settings
from digidentity_api.engines.embeddings.providers.mock_provider import MockEmbeddingProvider
from digidentity_api.engines.embeddings.providers.openai_provider import OpenAIEmbeddingProvider

if TYPE_CHECKING:
    pass


class EmbeddingRouter:
    """Routes embed() calls to the configured provider."""

    def __init__(
        self,
        provider: MockEmbeddingProvider | OpenAIEmbeddingProvider | None = None,
    ) -> None:
        if provider is not None:
            self._provider = provider
        else:
            self._provider = _build_provider()

    @property
    def dimensions(self) -> int:
        return self._provider.dimensions

    async def embed(
        self, texts: list[str], model: str | None = None
    ) -> list[list[float]]:
        """Embed texts. Returns one float vector per input."""
        if not texts:
            return []
        vectors = await self._provider.embed(texts, model=model)
        # Validate dimension on first result only (fail fast)
        if vectors and len(vectors[0]) != self._provider.dimensions:
            raise ValueError(
                f"Embedding dimension mismatch: expected {self._provider.dimensions}, "
                f"got {len(vectors[0])}"
            )
        return vectors


def _build_provider() -> MockEmbeddingProvider | OpenAIEmbeddingProvider:
    use_openai = (
        settings.EMBEDDING_PROVIDER == "openai"
        and bool(settings.OPENAI_API_KEY)
    )
    if use_openai:
        return OpenAIEmbeddingProvider(
            api_key=settings.OPENAI_API_KEY,
            model=settings.EMBEDDING_MODEL,
            dimensions=settings.EMBEDDING_DIMENSIONS,
        )
    return MockEmbeddingProvider(dimensions=settings.EMBEDDING_DIMENSIONS)


# Module-level singleton — initialised lazily on first call
_router: EmbeddingRouter | None = None


def get_router() -> EmbeddingRouter:
    """Return the process-level singleton EmbeddingRouter."""
    global _router  # noqa: PLW0603
    if _router is None:
        _router = EmbeddingRouter()
    return _router
