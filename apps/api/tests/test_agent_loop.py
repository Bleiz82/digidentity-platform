"""Tests for Agent Orchestrator — BIBLE §6.4.

All tests use mock Anthropic provider. No real API calls.
"""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from digidentity_api.engines.agent.loop import AgentLoop
from digidentity_api.engines.agent.providers.anthropic_provider import MockAnthropicProvider
from digidentity_api.engines.agent.tools.registry import ToolRegistry
from digidentity_api.engines.agent.tools.schemas import ALL_TOOLS

TENANT_ID = "00000000-0000-0000-0000-000000000001"
CONV_ID = "00000000-0000-0000-0000-000000000002"


# ── 1. Registry registers 3 tools with valid Anthropic schema ─────────────────

def test_registry_has_three_tools() -> None:
    registry = ToolRegistry(tenant_id=TENANT_ID)
    schemas = registry.schemas
    names = {s["name"] for s in schemas}
    assert names == {"kg_search", "render_highlight", "lead_update_score"}


def test_tool_schemas_are_anthropic_compatible() -> None:
    for schema in ALL_TOOLS:
        assert "name" in schema
        assert "description" in schema
        assert "input_schema" in schema
        assert schema["input_schema"]["type"] == "object"
        assert "properties" in schema["input_schema"]


# ── 2. kg_search returns simulated results ───────────────────────────────────

def test_kg_search_returns_results() -> None:
    registry = ToolRegistry(tenant_id=TENANT_ID)
    result = registry.kg_search(query="villa fronte mare", top_k=3)
    assert "results" in result
    assert len(result["results"]) == 3
    assert result["query"] == "villa fronte mare"
    assert result["tenant_id"] == TENANT_ID
    for r in result["results"]:
        assert "entity_id" in r
        assert "score" in r


# ── 3. render_highlight emits valid directive ────────────────────────────────

def test_render_highlight_directive() -> None:
    registry = ToolRegistry(tenant_id=TENANT_ID)
    result = registry.render_highlight(entity_id="ent-0001", reason="Prezzo ottimale")
    assert result["emitted"] is True
    directive = result["directive"]
    assert directive["type"] == "highlight"
    assert directive["target"] == "ent-0001"
    assert directive["params"]["reason"] == "Prezzo ottimale"


# ── 4. lead_update_score updates state ──────────────────────────────────────

def test_lead_update_score_accumulates() -> None:
    registry = ToolRegistry(tenant_id=TENANT_ID)
    r1 = registry.lead_update_score(signal="asked_price", weight=0.2)
    r2 = registry.lead_update_score(signal="requested_visit", weight=0.3)
    assert r1["total"] == pytest.approx(0.2)
    assert r2["total"] == pytest.approx(0.5)
    assert registry.lead_score == pytest.approx(0.5)
    assert r2["signal_count"] == 2


# ── 5. AgentLoop single-turn, no tool call ────────────────────────────────────

@pytest.mark.asyncio
async def test_agent_loop_single_turn_no_tool() -> None:
    provider = MockAnthropicProvider(responses=[
        {"type": "text_delta", "text": "Benvenuto!"},
        {"type": "message_stop"},
    ])
    loop = AgentLoop(provider=provider)
    events = []
    async for event in loop.run(
        conversation_id=CONV_ID,
        user_message="ciao",
        tenant_id=TENANT_ID,
    ):
        events.append(event)

    types = [e["type"] for e in events]
    assert "text" in types
    assert "done" in types
    done_event = next(e for e in events if e["type"] == "done")
    assert done_event["data"]["iterations"] == 1


# ── 6. AgentLoop: 1 tool_call → tool_result → final response ─────────────────

@pytest.mark.asyncio
async def test_agent_loop_single_tool_call() -> None:
    responses_iter = iter([
        # First call: tool_use
        [
            {"type": "tool_use", "id": "tu_1", "name": "kg_search", "input": {"query": "villa"}},
            {"type": "message_stop"},
        ],
        # Second call (after tool_result): text response
        [
            {"type": "text_delta", "text": "Ho trovato 5 ville per te."},
            {"type": "message_stop"},
        ],
    ])

    class _SequentialMock(MockAnthropicProvider):
        async def stream_message(self, **_: Any) -> AsyncIterator[dict[str, Any]]:
            for ev in next(responses_iter):
                yield ev

    provider = _SequentialMock(responses=[])
    loop = AgentLoop(provider=provider)
    events = []
    async for event in loop.run(
        conversation_id=CONV_ID,
        user_message="mostrami ville",
        tenant_id=TENANT_ID,
    ):
        events.append(event)

    types = [e["type"] for e in events]
    assert "tool_call" in types
    assert "tool_result" in types
    assert "text" in types
    assert "done" in types

    tool_call_ev = next(e for e in events if e["type"] == "tool_call")
    assert tool_call_ev["data"]["name"] == "kg_search"


# ── 7. AgentLoop respects max_iterations ────────────────────────────────────

@pytest.mark.asyncio
async def test_agent_loop_max_iterations() -> None:
    """Provider always returns a tool call → should stop after 5 iterations."""

    class _InfiniteToolProvider(MockAnthropicProvider):
        async def stream_message(self, **_: Any) -> AsyncIterator[dict[str, Any]]:
            yield {"type": "tool_use", "id": "tu_x", "name": "kg_search", "input": {"query": "x"}}
            yield {"type": "message_stop"}

    provider = _InfiniteToolProvider(responses=[])
    loop = AgentLoop(provider=provider)
    events = []
    async for event in loop.run(
        conversation_id=CONV_ID,
        user_message="loop me",
        tenant_id=TENANT_ID,
    ):
        events.append(event)

    done_event = next((e for e in events if e["type"] == "done"), None)
    assert done_event is not None
    assert done_event["data"].get("max_iterations_reached") is True
    assert done_event["data"]["iterations"] == 5


# ── 8. AgentLoop timeout ─────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_agent_loop_timeout() -> None:
    """Provider hangs forever → timeout fires."""

    class _HangingProvider(MockAnthropicProvider):
        async def stream_message(self, **_: Any) -> AsyncIterator[dict[str, Any]]:
            await asyncio.sleep(9999)
            yield {"type": "message_stop"}

    provider = _HangingProvider(responses=[])
    with patch("digidentity_api.engines.agent.loop.settings") as mock_settings:
        mock_settings.AGENT_TIMEOUT_SECS = 0.05  # 50ms
        mock_settings.AGENT_MAX_ITERATIONS = 5
        mock_settings.ANTHROPIC_MODEL = "claude-sonnet-4-6"
        loop = AgentLoop(provider=provider)
        events = []
        async for event in loop.run(
            conversation_id=CONV_ID,
            user_message="hang",
            tenant_id=TENANT_ID,
        ):
            events.append(event)

    error_event = next((e for e in events if e["type"] == "error"), None)
    assert error_event is not None
    assert error_event["data"]["code"] == "timeout"


# ── 9. AgentLoop persists turns in DB ────────────────────────────────────────

@pytest.mark.asyncio
async def test_agent_loop_persists_turns() -> None:
    """Turn persistence calls session.add and session.flush."""
    provider = MockAnthropicProvider(responses=[
        {"type": "text_delta", "text": "Certo!"},
        {"type": "message_stop"},
    ])

    mock_session = AsyncMock()
    mock_session.add = MagicMock()
    mock_session.flush = AsyncMock()

    loop = AgentLoop(provider=provider, session=mock_session)
    async for _ in loop.run(
        conversation_id=CONV_ID,
        user_message="salve",
        tenant_id=TENANT_ID,
    ):
        pass

    assert mock_session.add.called
    assert mock_session.flush.called


# ── 10. Fallback mock when ANTHROPIC_API_KEY absent ──────────────────────────

def test_get_provider_returns_mock_without_api_key() -> None:
    with patch("digidentity_api.engines.agent.providers.anthropic_provider.settings") as ms:
        ms.ANTHROPIC_API_KEY = ""
        from digidentity_api.engines.agent.providers.anthropic_provider import (
            MockAnthropicProvider,
            get_provider,
        )
        provider = get_provider()
        assert isinstance(provider, MockAnthropicProvider)
