"""LLM Router — ADR-004.

Responsibilities:
- Classify query complexity (simple vs complex) based on signals.
- Select starting model (Sonnet vs Opus) based on classification.
- Route through fallback chain with per-model circuit breakers.
- Retry policy: max 1 retry on 503/529 for web channel only (200ms wait).
- Mid-stream recovery: emit stream_interrupted, try next provider.
- Dispatch async Celery task for usage logging after successful stream.

Does NOT touch DB directly. No with_tenant() here.
"""

import asyncio
import time
import uuid
from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Literal

import structlog

from digidentity_api.engines.errors import CircuitOpenError, ProviderError
from digidentity_api.engines.mock_provider import (
    DEFAULT_PROVIDERS,
    BaseMockProvider,
    Chunk,
    TokenUsage,
)

log = structlog.get_logger()

# ── Model configuration ────────────────────────────────────────────────────────


@dataclass(frozen=True)
class ModelConfig:
    provider: str
    model: str


MODELS: dict[str, ModelConfig] = {
    "sonnet": ModelConfig("anthropic", "claude-sonnet-4-6"),
    "opus": ModelConfig("anthropic", "claude-opus-4-7"),
    "gpt5": ModelConfig("openai", "gpt-5"),
}

# Chain order for fallback
_CHAIN: list[str] = ["sonnet", "opus", "gpt5"]

# Complex query classification keywords
_COMPLEX_KEYWORDS = frozenset(
    ["step-by-step", "confronta", "ragiona", "analizza", "compara", "complex"]
)

# ── Circuit breaker state ─────────────────────────────────────────────────────

_FAILURE_THRESHOLD = 3
_WINDOW_SECS = 30
_COOLDOWN_SECS = 300  # 5 minutes


@dataclass
class CircuitBreakerState:
    failures: int = 0
    opened_at: datetime | None = None
    # Timestamps of recent failures (within the window)
    failure_times: list[datetime] = field(default_factory=list)


# ── Router ────────────────────────────────────────────────────────────────────


class LLMRouter:
    def __init__(
        self,
        providers: dict[str, BaseMockProvider] | None = None,
    ) -> None:
        self._providers: dict[str, BaseMockProvider] = providers or dict(DEFAULT_PROVIDERS)
        self._state: dict[str, CircuitBreakerState] = {key: CircuitBreakerState() for key in MODELS}

    # ── Classification ────────────────────────────────────────────────────────

    def classify(
        self,
        context_tokens: int,
        tool_calls_prev: int,
        prompt: str,
        prev_score: float | None,
    ) -> bool:
        """Return True if the query is complex (≥2 signals)."""
        signals = 0
        if context_tokens > 6000:
            signals += 1
        if tool_calls_prev >= 3:
            signals += 1
        lower = prompt.lower()
        if any(kw in lower for kw in _COMPLEX_KEYWORDS):
            signals += 1
        if prev_score is not None and prev_score < 0.65:
            signals += 1
        return signals >= 2

    # ── Circuit breaker ───────────────────────────────────────────────────────

    def _is_open(self, model_key: str) -> bool:
        """Return True if circuit is open (should skip this model).

        Half-open: if cooldown has elapsed, allow one probe through (return False).
        """
        state = self._state[model_key]
        if state.opened_at is None:
            return False

        now = datetime.now(UTC)
        elapsed = (now - state.opened_at).total_seconds()

        if elapsed >= _COOLDOWN_SECS:
            # Transition to half-open: allow one probe through
            # We clear opened_at so next call also gets through until failure/success recorded
            state.opened_at = None
            log.info("circuit_breaker.half_open", model=model_key)
            return False

        return True

    def _record_failure(self, model_key: str, status: int) -> None:
        state = self._state[model_key]
        now = datetime.now(UTC)

        # Prune failures outside the window
        state.failure_times = [
            t for t in state.failure_times if (now - t).total_seconds() <= _WINDOW_SECS
        ]
        state.failure_times.append(now)
        state.failures = len(state.failure_times)

        if state.failures >= _FAILURE_THRESHOLD and state.opened_at is None:
            state.opened_at = now
            log.warning(
                "circuit_breaker.opened",
                model=model_key,
                failures=state.failures,
                status=status,
            )

    def _record_success(self, model_key: str) -> None:
        state = self._state[model_key]
        state.failures = 0
        state.failure_times = []
        state.opened_at = None

    # ── Model selection ───────────────────────────────────────────────────────

    def _select_model(
        self,
        prompt: str,
        context_tokens: int,
        tool_calls_prev: int,
        prev_score: float | None,
    ) -> str:
        """Return the preferred model key based on classification."""
        is_complex = self.classify(context_tokens, tool_calls_prev, prompt, prev_score)
        return "opus" if is_complex else "sonnet"

    def _get_chain(self, preferred_model: str) -> list[str]:
        """Return ordered chain starting from preferred_model, excluding open circuits."""
        # Build chain: preferred first, then remaining in _CHAIN order
        remaining = [m for m in _CHAIN if m != preferred_model]
        full_chain = [preferred_model] + remaining
        return full_chain

    # ── Single attempt with retry ─────────────────────────────────────────────

    async def _attempt_stream(
        self,
        model_key: str,
        prompt: str,
        channel: Literal["web", "voice"],
        fail_mode: str | None,
    ) -> tuple[list[Chunk], bool]:
        """Try to stream from a provider. Returns (chunks, fallback_used).

        Retry policy C1:
        - Only on 503/529, only for channel='web'
        - Max 1 retry, 200ms wait
        - 429/500 → no retry, record failure immediately
        """
        provider = self._providers[model_key]
        retries_left = 1 if channel == "web" else 0

        attempt = 0
        while True:
            attempt += 1
            try:
                chunks: list[Chunk] = []
                async for chunk in provider.stream(prompt, fail_mode=fail_mode):
                    chunks.append(chunk)
                self._record_success(model_key)
                return chunks, False
            except ProviderError as exc:
                retryable = exc.status in (503, 529)

                if retryable and retries_left > 0:
                    retries_left -= 1
                    log.info(
                        "llm_router.retry",
                        model=model_key,
                        status=exc.status,
                        attempt=attempt,
                    )
                    await asyncio.sleep(0.2)
                    continue

                # No retry: record failure and re-raise
                self._record_failure(model_key, exc.status)
                raise

    # ── Main route method ─────────────────────────────────────────────────────

    async def route(
        self,
        prompt: str,
        conversation_id: str,
        tenant_id: str,
        channel: Literal["web", "voice"] = "web",
        context_tokens: int = 0,
        tool_calls_prev: int = 0,
        prev_score: float | None = None,
        fail_mode: str | None = None,
    ) -> AsyncIterator[dict[str, object]]:
        preferred = self._select_model(prompt, context_tokens, tool_calls_prev, prev_score)
        chain = self._get_chain(preferred)

        start_time = time.monotonic()
        request_id = str(uuid.uuid4())

        last_exc: ProviderError | None = None
        used_model_key: str | None = None
        final_chunks: list[Chunk] = []
        fallback_used = False

        for i, model_key in enumerate(chain):
            if self._is_open(model_key):
                log.info("circuit_breaker.skip", model=model_key)
                continue

            try:
                chunks, _ = await self._attempt_stream(model_key, prompt, channel, fail_mode)
                used_model_key = model_key
                final_chunks = chunks
                fallback_used = i > 0
                last_exc = None
                break
            except ProviderError as exc:
                last_exc = exc
                log.warning(
                    "llm_router.provider_failed",
                    model=model_key,
                    status=exc.status,
                    chain_pos=i,
                )
                # If there's a next provider, emit mid-stream interrupted signal
                remaining_chain = [m for m in chain[i + 1 :] if not self._is_open(m)]
                if remaining_chain:
                    yield {"type": "stream_interrupted", "retry": True}
                continue

        if used_model_key is None:
            # All providers exhausted
            all_open = all(self._is_open(m) for m in chain)
            if all_open:
                raise CircuitOpenError("all")
            if last_exc is not None:
                raise last_exc
            raise CircuitOpenError("all")

        # Emit chunks as SSE events
        model_cfg = MODELS[used_model_key]
        final_usage: TokenUsage | None = None

        for chunk in final_chunks:
            if chunk.finish_reason == "stop":
                final_usage = chunk.usage
            elif chunk.text is not None:
                yield {"type": "text", "text": chunk.text}

        # Async usage logging via Celery
        if final_usage is not None:
            latency_ms = int((time.monotonic() - start_time) * 1000)
            cost_usd = _estimate_cost(
                model_cfg.model,
                final_usage.prompt_tokens,
                final_usage.completion_tokens,
            )
            try:
                from digidentity_api.tasks.usage import log_usage  # noqa: PLC0415

                log_usage.delay(
                    tenant_id=tenant_id,
                    conversation_id=conversation_id,
                    request_id=request_id,
                    provider=model_cfg.provider,
                    model=model_cfg.model,
                    prompt_tokens=final_usage.prompt_tokens,
                    completion_tokens=final_usage.completion_tokens,
                    cached_tokens=final_usage.cached_tokens,
                    cost_usd=cost_usd,
                    latency_ms=latency_ms,
                    fallback_used=fallback_used,
                )
            except Exception as exc:
                log.error("llm_router.usage_log_failed", error=str(exc))


def _estimate_cost(model: str, prompt_tokens: int, completion_tokens: int) -> float:
    """Very rough cost estimate per token. Phase 1 placeholder."""
    # Prices per 1M tokens (USD) — approximate
    _prices: dict[str, tuple[float, float]] = {
        "claude-sonnet-4-6": (3.0, 15.0),
        "claude-opus-4-7": (15.0, 75.0),
        "gpt-5": (10.0, 30.0),
    }
    input_price, output_price = _prices.get(model, (5.0, 15.0))
    return (prompt_tokens * input_price + completion_tokens * output_price) / 1_000_000
