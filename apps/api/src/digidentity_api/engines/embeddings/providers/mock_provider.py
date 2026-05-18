"""Mock embedding provider — deterministic, no external calls.

Returns unit vectors (1/sqrt(dim) in all dimensions) to preserve cosine
similarity properties: any two mock embeddings for different inputs will have
cosine similarity = 1.0 (not ideal for retrieval, but consistent and testable).

For tests that need distinct vectors per input, pass a custom_fn.
"""

from __future__ import annotations

import math
from collections.abc import Callable


class MockEmbeddingProvider:
    """Deterministic embedding provider for tests and key-absent environments."""

    def __init__(
        self,
        dimensions: int = 3072,
        custom_fn: Callable[[str], list[float]] | None = None,
    ) -> None:
        self._dimensions = dimensions
        self._custom_fn = custom_fn
        # Pre-compute the unit vector value (same for every dimension)
        self._unit_val = 1.0 / math.sqrt(dimensions)

    @property
    def dimensions(self) -> int:
        return self._dimensions

    async def embed(self, texts: list[str], model: str | None = None) -> list[list[float]]:
        """Return one deterministic vector per input text.

        If custom_fn is set, delegates to it (useful for per-input variation in tests).
        Otherwise returns a constant unit vector regardless of input.
        """
        if self._custom_fn is not None:
            return [self._custom_fn(t) for t in texts]
        unit_vec = [self._unit_val] * self._dimensions
        return [unit_vec for _ in texts]
