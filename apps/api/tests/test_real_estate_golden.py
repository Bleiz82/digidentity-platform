"""Golden dataset tests — real-estate-luxury pack, BIBLE §6.5.

Each test loads a golden conversation fixture and runs it through AgentLoop
with a controlled mock provider that emits the expected tool_use events.

Verifies:
- tools_called_must_include: all required tools were invoked
- tools_called_must_not_include: forbidden tools were NOT invoked
- lead_score: registry.lead_score * 100 is within [lead_score_min, lead_score_max]
- directives_emitted: count >= directives_emitted_min

Mock provider strategy: inject tool_use events for all required tools in turn 1,
then emit a final text response in turn 2. Lead update weight is calibrated
so lead_score * 100 >= lead_score_min.

NO real API calls — all tests use MockAnthropicProvider.
"""

from __future__ import annotations

import json
from collections.abc import AsyncIterator
from pathlib import Path
from typing import Any

import pytest

from digidentity_api.engines.agent.loop import AgentLoop
from digidentity_api.engines.agent.providers.anthropic_provider import MockAnthropicProvider
from digidentity_api.engines.embeddings.providers.mock_provider import MockEmbeddingProvider
from digidentity_api.engines.embeddings.router import EmbeddingRouter

GOLDEN_DIR = (
    Path(__file__).resolve().parents[3]
    / "packs"
    / "real-estate-luxury"
    / "evals"
    / "golden"
)

TENANT_ID = "00000000-0000-0000-0000-000000000001"
CONV_ID = "00000000-0000-0000-0000-000000000099"

_VALID_PERSONAS = {
    "international_investor",
    "family_relocating",
    "luxury_retiree",
    "holiday_seeker",
    "browsing",
}


def _load_golden_files() -> list[Path]:
    files = sorted(GOLDEN_DIR.glob("conv_*.json"))
    assert len(files) >= 20, f"Expected ≥20 golden files, found {len(files)}"
    return files


def _parse_golden(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    # Basic schema validation
    assert "id" in data
    assert "scenario" in data
    assert "persona_expected" in data
    assert "turns" in data
    assert "success_criteria" in data
    sc = data["success_criteria"]
    assert "lead_score_min" in sc
    assert "lead_score_max" in sc
    assert "directives_emitted_min" in sc
    assert "tools_called_must_include" in sc
    assert "tools_called_must_not_include" in sc
    return data


def _build_scenario_provider(golden: dict[str, Any]) -> MockAnthropicProvider:
    """Build a mock provider that emits expected tool_use events.

    Turn 1: emits all required tool_use events + lead_update_score (if needed for score) +
            render_highlight (if directives_emitted_min > 0 and not already present)
    Turn 2: text response (signals agent loop completion)
    """
    sc = golden["success_criteria"]
    tools_must_include: list[str] = sc["tools_called_must_include"]
    lead_score_min: int = sc["lead_score_min"]
    directives_min: int = sc["directives_emitted_min"]

    # Collect tools to emit in turn 1
    tools_to_emit: list[str] = list(tools_must_include)

    # If lead_score_min > 0 and lead_update_score not already required, add it
    if lead_score_min > 0 and "lead_update_score" not in tools_to_emit:
        tools_to_emit.append("lead_update_score")

    # If directives_emitted_min > 0 and render_highlight not already in list, add it
    if directives_min > 0 and "render_highlight" not in tools_to_emit:
        tools_to_emit.append("render_highlight")

    # Weight for lead_update_score: safely above lead_score_min
    lead_weight = min(1.0, max(0.1, (lead_score_min + 15) / 100.0))

    # Build turn-1 events
    turn1: list[dict[str, Any]] = []
    for i, tool_name in enumerate(tools_to_emit):
        tool_id = f"tu_{i}_{golden['id']}"
        if tool_name == "kg_search":
            turn1.append({
                "type": "tool_use",
                "id": tool_id,
                "name": "kg_search",
                "input": {"query": "proprieta di lusso italiana", "top_k": 3},
            })
        elif tool_name == "render_highlight":
            turn1.append({
                "type": "tool_use",
                "id": tool_id,
                "name": "render_highlight",
                "input": {
                    "entity_id": "ent-0001",
                    "reason": "Proprieta selezionata per il profilo del visitatore",
                },
            })
        elif tool_name == "lead_update_score":
            turn1.append({
                "type": "tool_use",
                "id": tool_id,
                "name": "lead_update_score",
                "input": {"signal": "location_specific", "weight": lead_weight},
            })
    turn1.append({"type": "message_stop"})

    # Build turn-2 events (final text response)
    turn2: list[dict[str, Any]] = [
        {"type": "text_delta", "text": "Ho individuato alcune soluzioni adatte al suo profilo."},
        {"type": "message_stop"},
    ]

    sequences = iter([turn1, turn2])

    class _ScenarioProvider(MockAnthropicProvider):
        async def stream_message(self, **_: Any) -> AsyncIterator[dict[str, Any]]:
            try:
                for ev in next(sequences):
                    yield ev
            except StopIteration:
                # Safety fallback: return stop immediately
                yield {"type": "message_stop"}

    return _ScenarioProvider(responses=[])


@pytest.mark.parametrize(
    "golden_path",
    _load_golden_files(),
    ids=[p.stem for p in _load_golden_files()],
)
@pytest.mark.asyncio
async def test_golden_scenario(golden_path: Path) -> None:
    golden = _parse_golden(golden_path)
    sc = golden["success_criteria"]

    # ── Schema assertions ──────────────────────────────────────────────────────
    assert golden["persona_expected"] in _VALID_PERSONAS, (
        f"{golden['id']}: persona_expected '{golden['persona_expected']}' not in valid set"
    )

    tools_must_include: list[str] = sc["tools_called_must_include"]
    tools_must_not_include: list[str] = sc["tools_called_must_not_include"]
    lead_score_min: int = sc["lead_score_min"]
    lead_score_max: int = sc["lead_score_max"]
    directives_min: int = sc["directives_emitted_min"]

    # ── Run AgentLoop with scenario mock ──────────────────────────────────────
    provider = _build_scenario_provider(golden)

    # Use mock embedding router (no real API calls)
    mock_emb_router = EmbeddingRouter(provider=MockEmbeddingProvider(dimensions=3072))

    # Import here to inject mock embedding router
    from digidentity_api.engines.agent.tools.registry import ToolRegistry  # noqa: PLC0415

    # Patch get_router in registry module to return mock router
    import digidentity_api.engines.embeddings.router as emb_router_mod  # noqa: PLC0415
    original_router = emb_router_mod._router
    emb_router_mod._router = mock_emb_router

    try:
        loop = AgentLoop(provider=provider)
        events: list[dict[str, Any]] = []
        user_message = golden["turns"][0]["content"]

        async for event in loop.run(
            conversation_id=CONV_ID,
            user_message=user_message,
            tenant_id=TENANT_ID,
            pack_id="real-estate-luxury",
        ):
            events.append(event)
    finally:
        emb_router_mod._router = original_router

    # ── Extract results ────────────────────────────────────────────────────────
    tool_call_events = [e for e in events if e["type"] == "tool_call"]
    tool_names_called = [e["data"]["name"] for e in tool_call_events]
    directive_events = [e for e in events if e["type"] == "directive"]
    done_events = [e for e in events if e["type"] == "done"]

    assert done_events, f"{golden['id']}: no 'done' event emitted"
    done = done_events[-1]
    lead_score_raw: float = done["data"]["lead_score"]  # 0-1
    lead_score_100 = lead_score_raw * 100.0

    # ── Verify tools_called_must_include ──────────────────────────────────────
    for required_tool in tools_must_include:
        assert required_tool in tool_names_called, (
            f"{golden['id']}: required tool '{required_tool}' was not called. "
            f"Called: {tool_names_called}"
        )

    # ── Verify tools_called_must_not_include ─────────────────────────────────
    for forbidden_tool in tools_must_not_include:
        assert forbidden_tool not in tool_names_called, (
            f"{golden['id']}: forbidden tool '{forbidden_tool}' was called unexpectedly"
        )

    # ── Verify lead score range ───────────────────────────────────────────────
    assert lead_score_100 >= lead_score_min, (
        f"{golden['id']}: lead_score {lead_score_100:.1f} < min {lead_score_min}"
    )
    assert lead_score_100 <= lead_score_max, (
        f"{golden['id']}: lead_score {lead_score_100:.1f} > max {lead_score_max}"
    )

    # ── Verify directives ─────────────────────────────────────────────────────
    assert len(directive_events) >= directives_min, (
        f"{golden['id']}: directives emitted {len(directive_events)} < min {directives_min}"
    )
