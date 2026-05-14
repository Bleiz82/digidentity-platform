"""Unit tests for LLMRouter — ADR-004.

No DB, no Celery (log_usage.delay is mocked).
Uses injected mock providers for deterministic behavior.
"""

import time
from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta
from unittest.mock import MagicMock, patch

import pytest

from digidentity_api.engines.errors import CircuitOpenError, ProviderError
from digidentity_api.engines.llm_router import LLMRouter
from digidentity_api.engines.mock_provider import (
    BaseMockProvider,
    Chunk,
    TokenUsage,
)

# ── Helpers ───────────────────────────────────────────────────────────────────

_USAGE = TokenUsage(prompt_tokens=10, completion_tokens=20, cached_tokens=0)

_FINISH_CHUNK = Chunk(text=None, finish_reason="stop", usage=_USAGE)


def _make_success_provider(n_text_chunks: int = 2) -> BaseMockProvider:
    """Provider that emits n_text_chunks then stop."""

    class _SuccessProvider(BaseMockProvider):
        provider = "mock"
        model = "mock-success"
        call_count = 0

        async def stream(self, prompt: str, **kwargs: object) -> AsyncIterator[Chunk]:
            _SuccessProvider.call_count += 1
            for i in range(n_text_chunks):
                yield Chunk(text=f"chunk {i} ")
            yield _FINISH_CHUNK

    return _SuccessProvider()


def _make_fail_provider(status: int, fail_always: bool = True) -> BaseMockProvider:
    """Provider that always raises ProviderError with given status."""

    class _FailProvider(BaseMockProvider):
        provider = "mock"
        model = "mock-fail"
        call_count = 0

        async def stream(self, prompt: str, **kwargs: object) -> AsyncIterator[Chunk]:
            _FailProvider.call_count += 1
            raise ProviderError(status=status, provider="mock")
            # Make it a generator
            yield  # type: ignore[misc]

    return _FailProvider()


def _make_fail_once_provider(status: int) -> BaseMockProvider:
    """Provider that fails on first call, succeeds on second."""

    class _FailOnceProvider(BaseMockProvider):
        provider = "mock"
        model = "mock-fail-once"
        call_count = 0

        async def stream(self, prompt: str, **kwargs: object) -> AsyncIterator[Chunk]:
            _FailOnceProvider.call_count += 1
            if _FailOnceProvider.call_count == 1:
                raise ProviderError(status=status, provider="mock")
            for i in range(2):
                yield Chunk(text=f"retry chunk {i} ")
            yield _FINISH_CHUNK

    return _FailOnceProvider()


async def _collect_events(router: LLMRouter, **kwargs: object) -> list[dict]:
    events = []
    with patch("digidentity_api.tasks.usage.log_usage") as mock_task:
        mock_task.delay = MagicMock()
        async for event in router.route(**kwargs):
            events.append(event)
    return events


# ── Classification tests ──────────────────────────────────────────────────────


def test_classify_complex_keyword_and_low_score() -> None:
    """2 signals: keyword + low prev_score → complex."""
    router = LLMRouter()
    result = router.classify(
        context_tokens=100,
        tool_calls_prev=0,
        prompt="analizza questo testo",
        prev_score=0.5,
    )
    assert result is True


def test_classify_simple_query() -> None:
    """0 signals → not complex."""
    router = LLMRouter()
    result = router.classify(
        context_tokens=100,
        tool_calls_prev=0,
        prompt="ciao",
        prev_score=None,
    )
    assert result is False


def test_classify_context_tokens_and_tool_calls() -> None:
    """2 signals: context_tokens > 6000 + tool_calls >= 3 → complex."""
    router = LLMRouter()
    result = router.classify(
        context_tokens=7000,
        tool_calls_prev=3,
        prompt="semplice",
        prev_score=None,
    )
    assert result is True


# ── Model selection tests ─────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_complex_query_routes_to_opus() -> None:
    """Complex query → preferred model is opus."""
    success = _make_success_provider()
    router = LLMRouter(providers={"sonnet": success, "opus": success, "gpt5": success})

    # Patch log_usage.delay
    with patch("digidentity_api.engines.llm_router.LLMRouter._attempt_stream") as mock_attempt:
        mock_attempt.return_value = ([Chunk(text="ok "), _FINISH_CHUNK], False)

        # "analizza" + prev_score=0.5 → 2 signals → complex → opus
        preferred = router._select_model(
            prompt="analizza bene",
            context_tokens=100,
            tool_calls_prev=0,
            prev_score=0.5,
        )
        assert preferred == "opus"


@pytest.mark.asyncio
async def test_simple_query_routes_to_sonnet() -> None:
    """Simple query → preferred model is sonnet."""
    router = LLMRouter()
    preferred = router._select_model(
        prompt="ciao come stai",
        context_tokens=100,
        tool_calls_prev=0,
        prev_score=None,
    )
    assert preferred == "sonnet"


# ── Circuit breaker tests ─────────────────────────────────────────────────────


def test_circuit_breaker_opens_after_3_failures() -> None:
    """3 failures on sonnet within window → circuit opens."""
    router = LLMRouter()
    for _ in range(3):
        router._record_failure("sonnet", 503)
    assert router._is_open("sonnet") is True


def test_circuit_breaker_per_model_isolation() -> None:
    """Opening sonnet circuit does not affect opus."""
    router = LLMRouter()
    for _ in range(3):
        router._record_failure("sonnet", 503)
    assert router._is_open("sonnet") is True
    assert router._is_open("opus") is False


def test_circuit_breaker_half_open_after_cooldown() -> None:
    """After cooldown period, circuit returns to half-open (allows probe)."""
    router = LLMRouter()
    for _ in range(3):
        router._record_failure("sonnet", 503)
    assert router._is_open("sonnet") is True

    # Simulate cooldown elapsed by backdating opened_at
    state = router._state["sonnet"]
    state.opened_at = datetime.now(UTC) - timedelta(seconds=301)

    # _is_open should return False (half-open: probe allowed)
    assert router._is_open("sonnet") is False
    # State should be cleared (opened_at reset)
    assert state.opened_at is None


def test_circuit_breaker_success_resets_state() -> None:
    """After success, circuit closes (failures reset)."""
    router = LLMRouter()
    router._record_failure("sonnet", 503)
    router._record_failure("sonnet", 503)
    router._record_success("sonnet")
    assert router._is_open("sonnet") is False
    assert router._state["sonnet"].failures == 0


@pytest.mark.asyncio
async def test_circuit_breaker_fallback_to_gpt5_when_sonnet_opus_open() -> None:
    """When sonnet and opus are open, router uses gpt5."""
    success_gpt5 = _make_success_provider()
    fail_sonnet = _make_fail_provider(503)
    fail_opus = _make_fail_provider(503)

    router = LLMRouter(providers={"sonnet": fail_sonnet, "opus": fail_opus, "gpt5": success_gpt5})

    # Manually open sonnet and opus circuits
    for _ in range(3):
        router._record_failure("sonnet", 503)
        router._record_failure("opus", 503)

    assert router._is_open("sonnet") is True
    assert router._is_open("opus") is True

    with patch("digidentity_api.engines.llm_router.log_usage", create=True):
        with patch("digidentity_api.tasks.usage.log_usage") as mock_task:
            mock_task.delay = MagicMock()
            events = []
            async for event in router.route(
                prompt="semplice",
                conversation_id="conv-1",
                tenant_id="00000000-0000-0000-0000-000000000001",
                channel="web",
            ):
                events.append(event)

    text_events = [e for e in events if e.get("type") == "text"]
    assert len(text_events) > 0


# ── Retry policy tests ────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_voice_channel_no_retry() -> None:
    """Voice channel: no retry on 503. Fails over immediately to next provider."""
    fail_once = _make_fail_once_provider(503)
    # Reset call count
    type(fail_once).call_count = 0

    success = _make_success_provider()
    router = LLMRouter(providers={"sonnet": fail_once, "opus": success, "gpt5": success})

    start = time.monotonic()
    with patch("digidentity_api.tasks.usage.log_usage") as mock_task:
        mock_task.delay = MagicMock()
        events = []
        async for event in router.route(
            prompt="ciao",
            conversation_id="conv-voice",
            tenant_id="00000000-0000-0000-0000-000000000001",
            channel="voice",
        ):
            events.append(event)
    elapsed = time.monotonic() - start

    # No retry sleep (200ms) — should complete well under 500ms
    assert elapsed < 0.5, f"Voice channel took {elapsed:.2f}s — unexpected retry delay"
    # Should have gotten text events (from opus fallback)
    text_events = [e for e in events if e.get("type") == "text"]
    assert len(text_events) > 0


@pytest.mark.asyncio
async def test_web_channel_retries_once_on_503() -> None:
    """Web channel: exactly 1 retry on 503 then success on same provider."""
    # We need a provider that fails first call, succeeds second

    class _FailOnceSonnet(BaseMockProvider):
        provider = "anthropic"
        model = "claude-sonnet-4-6"
        calls: list[int] = []

        async def stream(self, prompt: str, **kwargs: object) -> AsyncIterator[Chunk]:
            _FailOnceSonnet.calls.append(1)
            if len(_FailOnceSonnet.calls) == 1:
                raise ProviderError(status=503, provider="anthropic")
            yield Chunk(text="retry success ")
            yield _FINISH_CHUNK

    fail_once = _FailOnceSonnet()
    _FailOnceSonnet.calls = []

    success = _make_success_provider()
    router = LLMRouter(providers={"sonnet": fail_once, "opus": success, "gpt5": success})

    with patch("digidentity_api.tasks.usage.log_usage") as mock_task:
        mock_task.delay = MagicMock()
        events = []
        async for event in router.route(
            prompt="ciao",
            conversation_id="conv-web",
            tenant_id="00000000-0000-0000-0000-000000000001",
            channel="web",
        ):
            events.append(event)

    # Sonnet should have been called exactly 2 times (1 fail + 1 retry)
    assert len(_FailOnceSonnet.calls) == 2
    text_events = [e for e in events if e.get("type") == "text"]
    assert len(text_events) > 0


@pytest.mark.asyncio
async def test_no_retry_on_500() -> None:
    """500 errors do not trigger retry even on web channel."""

    class _Fail500Sonnet(BaseMockProvider):
        provider = "anthropic"
        model = "claude-sonnet-4-6"
        calls: list[int] = []

        async def stream(self, prompt: str, **kwargs: object) -> AsyncIterator[Chunk]:
            _Fail500Sonnet.calls.append(1)
            raise ProviderError(status=500, provider="anthropic")
            yield  # type: ignore[misc]

    fail_500 = _Fail500Sonnet()
    _Fail500Sonnet.calls = []

    success = _make_success_provider()
    router = LLMRouter(providers={"sonnet": fail_500, "opus": success, "gpt5": success})

    with patch("digidentity_api.tasks.usage.log_usage") as mock_task:
        mock_task.delay = MagicMock()
        events = []
        async for event in router.route(
            prompt="ciao",
            conversation_id="conv-web2",
            tenant_id="00000000-0000-0000-0000-000000000001",
            channel="web",
        ):
            events.append(event)

    # Sonnet called exactly once — no retry on 500
    assert len(_Fail500Sonnet.calls) == 1
    text_events = [e for e in events if e.get("type") == "text"]
    assert len(text_events) > 0  # opus fallback succeeded


@pytest.mark.asyncio
async def test_all_circuits_open_raises() -> None:
    """If all circuits are open, CircuitOpenError is raised."""
    router = LLMRouter()
    for model_key in ["sonnet", "opus", "gpt5"]:
        for _ in range(3):
            router._record_failure(model_key, 503)

    with pytest.raises(CircuitOpenError):
        async for _ in router.route(
            prompt="test",
            conversation_id="conv-all-open",
            tenant_id="00000000-0000-0000-0000-000000000001",
        ):
            pass
