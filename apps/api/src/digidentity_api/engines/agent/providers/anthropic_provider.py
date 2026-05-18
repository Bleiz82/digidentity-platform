"""Anthropic SDK wrapper — BIBLE §6.4.

Wraps the real anthropic.AsyncAnthropic client for streaming + tool_use.
Falls back to MockAnthropicProvider if ANTHROPIC_API_KEY is empty.
"""

from __future__ import annotations

import json
from abc import ABC, abstractmethod
from collections.abc import AsyncIterator
from typing import Any

import structlog

from digidentity_api.config import settings

log = structlog.get_logger()


# ── Abstract interface ────────────────────────────────────────────────────────


class BaseAnthropicProvider(ABC):
    @abstractmethod
    async def stream_message(
        self,
        *,
        system: str,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]],
        model: str,
        max_tokens: int = 1024,
    ) -> AsyncIterator[dict[str, Any]]:
        """Yield parsed events: text_delta, tool_use, message_stop."""
        ...


# ── Mock provider (no API key required) ───────────────────────────────────────


class MockAnthropicProvider(BaseAnthropicProvider):
    """Deterministic mock — used when ANTHROPIC_API_KEY is absent or in tests."""

    def __init__(self, responses: list[dict[str, Any]] | None = None) -> None:
        self._responses = responses or [
            {"type": "text_delta", "text": "Ciao! Sono l'assistente del Living Site."},
            {"type": "message_stop"},
        ]

    async def stream_message(
        self,
        *,
        system: str,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]],
        model: str,
        max_tokens: int = 1024,
    ) -> AsyncIterator[dict[str, Any]]:
        for event in self._responses:
            yield event


# ── Real Anthropic provider ───────────────────────────────────────────────────


class AnthropicProvider(BaseAnthropicProvider):
    """Real Anthropic SDK streaming provider."""

    def __init__(self, api_key: str | None = None) -> None:
        import anthropic  # noqa: PLC0415

        self._client = anthropic.AsyncAnthropic(api_key=api_key or settings.ANTHROPIC_API_KEY)

    async def stream_message(
        self,
        *,
        system: str,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]],
        model: str,
        max_tokens: int = 1024,
    ) -> AsyncIterator[dict[str, Any]]:
        async with self._client.messages.stream(
            model=model,
            max_tokens=max_tokens,
            system=system,
            messages=messages,
            tools=tools,  # type: ignore[arg-type]
        ) as stream:
            current_tool_id: str | None = None
            current_tool_name: str | None = None
            current_tool_input_chunks: list[str] = []

            async for event in stream:
                etype = event.type

                if etype == "content_block_start":
                    block = event.content_block
                    if block.type == "tool_use":
                        current_tool_id = block.id
                        current_tool_name = block.name
                        current_tool_input_chunks = []
                    elif block.type == "text":
                        pass

                elif etype == "content_block_delta":
                    delta = event.delta
                    if delta.type == "text_delta":
                        yield {"type": "text_delta", "text": delta.text}
                    elif delta.type == "input_json_delta":
                        current_tool_input_chunks.append(delta.partial_json)

                elif etype == "content_block_stop":
                    if current_tool_id is not None:
                        try:
                            tool_input = json.loads("".join(current_tool_input_chunks))
                        except json.JSONDecodeError:
                            tool_input = {}
                        yield {
                            "type": "tool_use",
                            "id": current_tool_id,
                            "name": current_tool_name,
                            "input": tool_input,
                        }
                        current_tool_id = None
                        current_tool_name = None
                        current_tool_input_chunks = []

                elif etype == "message_stop":
                    yield {"type": "message_stop"}

                elif etype == "message_start":
                    pass


# ── Factory ───────────────────────────────────────────────────────────────────


def get_provider() -> BaseAnthropicProvider:
    """Return real provider if API key is set, otherwise mock."""
    if settings.ANTHROPIC_API_KEY:
        return AnthropicProvider()
    log.info("agent.provider.mock", reason="ANTHROPIC_API_KEY not set")
    return MockAnthropicProvider()
