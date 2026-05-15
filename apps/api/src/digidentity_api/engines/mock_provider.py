"""Mock LLM providers for Phase 1 / testing.

No real Anthropic/OpenAI calls. Deterministic streaming output.
Failure injection via DIGIDENTITY_MOCK_FAIL_RATE env var or fail_mode kwarg.
"""

import asyncio
import os
import random
from collections.abc import AsyncIterator
from dataclasses import dataclass

from digidentity_api.engines.errors import ProviderError

# ── Data classes ──────────────────────────────────────────────────────────────


@dataclass
class TokenUsage:
    prompt_tokens: int
    completion_tokens: int
    cached_tokens: int = 0


@dataclass
class Chunk:
    text: str | None = None
    finish_reason: str | None = None
    usage: TokenUsage | None = None


# ── Complex query keywords ────────────────────────────────────────────────────

_COMPLEX_KEYWORDS = frozenset(["complex", "analizza", "compara", "confronta", "ragiona"])

_SHORT_WORDS = [
    "Certo",
    "ecco",
    "la",
    "risposta",
    "che",
    "stai",
    "cercando",
    ".",
]

_LONG_WORDS = [
    "Analizzando",
    "attentamente",
    "la",
    "tua",
    "richiesta",
    "posso",
    "fornire",
    "una",
    "risposta",
    "dettagliata",
    "e",
    "approfondita",
    "su",
    "questo",
    "argomento",
    ".",
]


def _is_complex(prompt: str) -> bool:
    lower = prompt.lower()
    return any(kw in lower for kw in _COMPLEX_KEYWORDS)


def _build_chunks(prompt: str, provider: str, model: str) -> list[Chunk]:
    """Build deterministic chunk list based on prompt complexity."""
    complex_query = _is_complex(prompt)
    n_chunks = 8 if complex_query else 4
    words_per_chunk = _LONG_WORDS if complex_query else _SHORT_WORDS
    total_words = len(words_per_chunk)

    chunks: list[Chunk] = []
    completion_tokens = 0
    for i in range(n_chunks):
        # Cycle through words to fill each chunk
        start = (i * 3) % total_words
        text_words = (words_per_chunk * 3)[start : start + (5 if complex_query else 3)]
        text = " ".join(text_words) + " "
        completion_tokens += len(text_words)
        chunks.append(Chunk(text=text))

    prompt_tokens = max(10, len(prompt.split()))
    chunks.append(
        Chunk(
            text=None,
            finish_reason="stop",
            usage=TokenUsage(
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                cached_tokens=0,
            ),
        )
    )
    return chunks


# ── Base protocol / ABC ───────────────────────────────────────────────────────


class BaseMockProvider:
    provider: str = ""
    model: str = ""

    async def stream(self, prompt: str, **kwargs: object) -> AsyncIterator[Chunk]:
        raise NotImplementedError

    async def _check_failure_injection(self, fail_mode: str | None) -> None:
        """Raise ProviderError according to injection settings."""
        # Explicit override via kwarg (from test / header)
        if fail_mode is not None:
            mode = fail_mode.strip().lower()
            if mode == "500":
                raise ProviderError(status=500, provider=self.provider)
            elif mode == "503":
                raise ProviderError(status=503, provider=self.provider)
            elif mode == "529":
                raise ProviderError(status=529, provider=self.provider)
            elif mode == "timeout":
                await asyncio.sleep(5)
                raise ProviderError(status=503, provider=self.provider)
            # Unknown mode: fall through (no injection)

        # Random failure rate from env
        fail_rate_str = os.getenv("DIGIDENTITY_MOCK_FAIL_RATE", "0")
        try:
            fail_rate = float(fail_rate_str)
        except ValueError:
            fail_rate = 0.0

        if fail_rate > 0.0 and random.random() < fail_rate:
            raise ProviderError(status=503, provider=self.provider)


# ── Concrete mock providers ───────────────────────────────────────────────────


class MockAnthropicSonnet(BaseMockProvider):
    provider = "anthropic"
    model = "claude-sonnet-4-6"

    async def stream(self, prompt: str, **kwargs: object) -> AsyncIterator[Chunk]:
        fail_mode = kwargs.get("fail_mode")
        assert fail_mode is None or isinstance(fail_mode, str)
        await self._check_failure_injection(fail_mode)
        for chunk in _build_chunks(prompt, self.provider, self.model):
            await asyncio.sleep(0.01)
            yield chunk


class MockAnthropicOpus(BaseMockProvider):
    provider = "anthropic"
    model = "claude-opus-4-7"

    async def stream(self, prompt: str, **kwargs: object) -> AsyncIterator[Chunk]:
        fail_mode = kwargs.get("fail_mode")
        assert fail_mode is None or isinstance(fail_mode, str)
        await self._check_failure_injection(fail_mode)
        for chunk in _build_chunks(prompt, self.provider, self.model):
            await asyncio.sleep(0.01)
            yield chunk


class MockOpenAIGPT5(BaseMockProvider):
    provider = "openai"
    model = "gpt-5"

    async def stream(self, prompt: str, **kwargs: object) -> AsyncIterator[Chunk]:
        fail_mode = kwargs.get("fail_mode")
        assert fail_mode is None or isinstance(fail_mode, str)
        await self._check_failure_injection(fail_mode)
        for chunk in _build_chunks(prompt, self.provider, self.model):
            await asyncio.sleep(0.01)
            yield chunk


# ── Default provider registry ─────────────────────────────────────────────────

DEFAULT_PROVIDERS: dict[str, BaseMockProvider] = {
    "sonnet": MockAnthropicSonnet(),
    "opus": MockAnthropicOpus(),
    "gpt5": MockOpenAIGPT5(),
}
