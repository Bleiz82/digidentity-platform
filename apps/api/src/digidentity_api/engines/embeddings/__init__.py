"""Embeddings engine — ADR-007.

Provides EmbeddingRouter with OpenAI (text-embedding-3-large) and Mock providers.
Back-compat: mock provider is active when OPENAI_API_KEY is absent or EMBEDDING_PROVIDER=mock.
"""

from digidentity_api.engines.embeddings.router import EmbeddingRouter, get_router

__all__ = ["EmbeddingRouter", "get_router"]
