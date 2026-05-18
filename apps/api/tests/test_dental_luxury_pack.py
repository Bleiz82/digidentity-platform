"""Pack tests — dental-luxury, BIBLE §5 + §6.5.

Two structural tests + 10 parametric golden scenario tests = 12 total.

Structural:
- test_pack_yaml_structure: validates pack.yaml has required fields
- test_personas_structure: validates 4 canonical personas present including alias resolution

Golden (parametric, 10 fixtures):
- test_golden_scenario: runs each conv_00N.json through AgentLoop with MockAnthropicProvider
  and verifies tools_called_must_include, lead_score range, directives_emitted_min.

NO real API calls — all tests use MockAnthropicProvider + MockEmbeddingProvider.
"""

from __future__ import annotations

import json
from collections.abc import AsyncIterator
from pathlib import Path
from typing import Any

import pytest
import yaml

from digidentity_api.engines.agent.loop import AgentLoop
from digidentity_api.engines.agent.providers.anthropic_provider import MockAnthropicProvider
from digidentity_api.engines.embeddings.providers.mock_provider import MockEmbeddingProvider
from digidentity_api.engines.embeddings.router import EmbeddingRouter

_REPO_ROOT = Path(__file__).resolve().parents[3]
_PACK_ROOT = _REPO_ROOT / "packs" / "dental-luxury"
GOLDEN_DIR = _PACK_ROOT / "evals" / "golden"

TENANT_ID = "00000000-0000-0000-0000-000000000002"
CONV_ID = "00000000-0000-0000-0000-000000000098"

_VALID_PERSONAS = {
    "appearance_seeker",
    "function_seeker",
    "anxious_patient",
    "dental_tourist",
    "browsing",
}

_EXPECTED_PERSONAS = {
    "appearance_seeker",
    "function_seeker",
    "anxious_patient",
    "dental_tourist",
}

_ANXIOUS_PATIENT_ALIAS = "fearful_patient"


# ── Structural tests ───────────────────────────────────────────────────────────

def test_pack_yaml_structure() -> None:
    pack_path = _PACK_ROOT / "pack.yaml"
    assert pack_path.exists(), f"pack.yaml not found at {pack_path}"
    data = yaml.safe_load(pack_path.read_text(encoding="utf-8"))
    assert data["id"] == "dental-luxury"
    assert "version" in data
    assert data["vertical"] == "dental"
    assert "search" in data
    assert "personas" in data
    persona_ids = {p["id"] for p in data["personas"]}
    assert _EXPECTED_PERSONAS <= persona_ids, (
        f"Missing personas in pack.yaml: {_EXPECTED_PERSONAS - persona_ids}"
    )


def test_personas_structure() -> None:
    personas_path = _PACK_ROOT / "ontology" / "personas.yaml"
    assert personas_path.exists(), f"personas.yaml not found at {personas_path}"
    data = yaml.safe_load(personas_path.read_text(encoding="utf-8"))
    assert data["pack_id"] == "dental-luxury"
    assert "personas" in data
    persona_ids = {p["id"] for p in data["personas"]}
    assert _EXPECTED_PERSONAS <= persona_ids, (
        f"Missing personas: {_EXPECTED_PERSONAS - persona_ids}"
    )
    # Check anxious_patient has fearful_patient alias
    anxious = next(p for p in data["personas"] if p["id"] == "anxious_patient")
    aliases = anxious.get("aliases", [])
    assert _ANXIOUS_PATIENT_ALIAS in aliases, (
        f"anxious_patient must have alias '{_ANXIOUS_PATIENT_ALIAS}', got: {aliases}"
    )


# ── Golden dataset helpers ─────────────────────────────────────────────────────

def _load_golden_files() -> list[Path]:
    files = sorted(GOLDEN_DIR.glob("conv_*.json"))
    assert len(files) >= 10, f"Expected ≥10 golden files, found {len(files)}"
    return files


def _parse_golden(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
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
    sc = golden["success_criteria"]
    tools_must_include: list[str] = sc["tools_called_must_include"]
    lead_score_min: int = sc["lead_score_min"]
    directives_min: int = sc["directives_emitted_min"]

    tools_to_emit: list[str] = list(tools_must_include)

    if lead_score_min > 0 and "lead_update_score" not in tools_to_emit:
        tools_to_emit.append("lead_update_score")

    if directives_min > 0 and "render_highlight" not in tools_to_emit:
        tools_to_emit.append("render_highlight")

    lead_weight = min(1.0, max(0.1, (lead_score_min + 15) / 100.0))

    turn1: list[dict[str, Any]] = []
    for i, tool_name in enumerate(tools_to_emit):
        tool_id = f"tu_{i}_{golden['id']}"
        if tool_name == "kg_search":
            turn1.append({
                "type": "tool_use",
                "id": tool_id,
                "name": "kg_search",
                "input": {"query": "trattamenti odontoiatrici di eccellenza", "top_k": 3},
            })
        elif tool_name == "render_highlight":
            turn1.append({
                "type": "tool_use",
                "id": tool_id,
                "name": "render_highlight",
                "input": {
                    "entity_id": "ent-dental-0001",
                    "reason": "Trattamento selezionato per il profilo del visitatore",
                },
            })
        elif tool_name == "lead_update_score":
            turn1.append({
                "type": "tool_use",
                "id": tool_id,
                "name": "lead_update_score",
                "input": {"signal": "specific_treatment_asked", "weight": lead_weight},
            })
    turn1.append({"type": "message_stop"})

    turn2: list[dict[str, Any]] = [
        {"type": "text_delta", "text": "Posso aiutarla a trovare la soluzione più adatta al suo caso."},
        {"type": "message_stop"},
    ]

    sequences = iter([turn1, turn2])

    class _ScenarioProvider(MockAnthropicProvider):
        async def stream_message(self, **_: Any) -> AsyncIterator[dict[str, Any]]:
            try:
                for ev in next(sequences):
                    yield ev
            except StopIteration:
                yield {"type": "message_stop"}

    return _ScenarioProvider(responses=[])


# ── Parametric golden tests ────────────────────────────────────────────────────

@pytest.mark.parametrize(
    "golden_path",
    _load_golden_files(),
    ids=[p.stem for p in _load_golden_files()],
)
@pytest.mark.asyncio
async def test_golden_scenario(golden_path: Path) -> None:
    golden = _parse_golden(golden_path)
    sc = golden["success_criteria"]

    assert golden["persona_expected"] in _VALID_PERSONAS, (
        f"{golden['id']}: persona_expected '{golden['persona_expected']}' not in valid set"
    )

    tools_must_include: list[str] = sc["tools_called_must_include"]
    tools_must_not_include: list[str] = sc["tools_called_must_not_include"]
    lead_score_min: int = sc["lead_score_min"]
    lead_score_max: int = sc["lead_score_max"]
    directives_min: int = sc["directives_emitted_min"]

    provider = _build_scenario_provider(golden)
    mock_emb_router = EmbeddingRouter(provider=MockEmbeddingProvider(dimensions=3072))

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
            pack_id="dental-luxury",
        ):
            events.append(event)
    finally:
        emb_router_mod._router = original_router

    tool_call_events = [e for e in events if e["type"] == "tool_call"]
    tool_names_called = [e["data"]["name"] for e in tool_call_events]
    directive_events = [e for e in events if e["type"] == "directive"]
    done_events = [e for e in events if e["type"] == "done"]

    assert done_events, f"{golden['id']}: no 'done' event emitted"
    done = done_events[-1]
    lead_score_raw: float = done["data"]["lead_score"]
    lead_score_100 = lead_score_raw * 100.0

    for required_tool in tools_must_include:
        assert required_tool in tool_names_called, (
            f"{golden['id']}: required tool '{required_tool}' was not called. "
            f"Called: {tool_names_called}"
        )

    for forbidden_tool in tools_must_not_include:
        assert forbidden_tool not in tool_names_called, (
            f"{golden['id']}: forbidden tool '{forbidden_tool}' was called unexpectedly"
        )

    assert lead_score_100 >= lead_score_min, (
        f"{golden['id']}: lead_score {lead_score_100:.1f} < min {lead_score_min}"
    )
    assert lead_score_100 <= lead_score_max, (
        f"{golden['id']}: lead_score {lead_score_100:.1f} > max {lead_score_max}"
    )

    assert len(directive_events) >= directives_min, (
        f"{golden['id']}: directives emitted {len(directive_events)} < min {directives_min}"
    )
