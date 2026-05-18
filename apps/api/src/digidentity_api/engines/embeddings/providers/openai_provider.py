"""OpenAI embedding provider — text-embedding-3-large, ADR-007.

Batches up to 100 inputs per API call.
Retry policy on rate limits: exponential backoff 1s → 2s → 4s (max 3 retries).
Retry policy on 5xx: 2 retries with 1s fixed wait.
"""

from __future__ import annotations

import asyncio
import logging

from openai import AsyncOpenAI, RateLimitError

log = logging.getLogger(__name__)

_BATCH_SIZE = 100
_MAX_RETRIES_RATE = 3
_MAX_RETRIES_5XX = 2


class OpenAIEmbeddingProvider:
    """Wraps AsyncOpenAI for embedding calls with batching and retry."""

    def __init__(
        self,
        api_key: str,
        model: str = "text-embedding-3-large",
        dimensions: int = 3072,
    ) -> None:
        self._client = AsyncOpenAI(api_key=api_key)
        self._model = model
        self._dimensions = dimensions

    @property
    def dimensions(self) -> int:
        return self._dimensions

    async def embed(self, texts: list[str], model: str | None = None) -> list[list[float]]:
        """Embed texts in batches of up to 100. Returns one vector per input."""
        effective_model = model or self._model
        results: list[list[float]] = []

        for i in range(0, len(texts), _BATCH_SIZE):
            batch = texts[i : i + _BATCH_SIZE]
            vectors = await self._embed_batch_with_retry(batch, effective_model)
            results.extend(vectors)

        return results

    async def _embed_batch_with_retry(
        self, batch: list[str], model: str
    ) -> list[list[float]]:
        rate_retries = 0
        server_retries = 0

        while True:
            try:
                response = await self._client.embeddings.create(
                    input=batch,
                    model=model,
                    dimensions=self._dimensions,
                )
                # Sort by index in case OpenAI returns out-of-order
                items = sorted(response.data, key=lambda x: x.index)
                return [item.embedding for item in items]

            except RateLimitError:
                if rate_retries >= _MAX_RETRIES_RATE:
                    raise
                wait = 2**rate_retries  # 1s, 2s, 4s
                log.warning(
                    "openai_embedding.rate_limit",
                    extra={"retry": rate_retries + 1, "wait_s": wait},
                )
                await asyncio.sleep(wait)
                rate_retries += 1

            except Exception as exc:  # noqa: BLE001
                # Treat any non-rate-limit exception as a transient 5xx
                if server_retries >= _MAX_RETRIES_5XX:
                    raise
                log.warning(
                    "openai_embedding.server_error",
                    extra={"retry": server_retries + 1, "error": str(exc)},
                )
                await asyncio.sleep(1.0)
                server_retries += 1
