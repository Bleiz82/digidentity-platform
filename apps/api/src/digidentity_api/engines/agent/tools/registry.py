"""ToolRegistry — executes the 3 built-in agent tools.

All execution is pure in-memory for Phase 2; no shell, no filesystem writes.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any
from uuid import UUID

from digidentity_api.engines.agent.tools.schemas import ALL_TOOLS


@dataclass
class LeadScoreState:
    """Mutable per-conversation lead score accumulator."""

    total: float = 0.0
    signals: list[dict[str, Any]] = field(default_factory=list)


class ToolRegistry:
    """Executes tool calls by name, maintaining per-conversation lead state."""

    def __init__(self, tenant_id: str | UUID) -> None:
        self.tenant_id = str(tenant_id)
        self._lead_state: LeadScoreState = LeadScoreState()

    # ── Schema accessor ───────────────────────────────────────────────────────

    @property
    def schemas(self) -> list[dict[str, Any]]:
        return ALL_TOOLS

    # ── Tool implementations ──────────────────────────────────────────────────

    def kg_search(self, query: str, top_k: int = 5) -> dict[str, Any]:
        """Stub KG search — returns simulated entities for Phase 2."""
        results = [
            {
                "entity_id": f"ent-{i:04d}",
                "entity_type": "property",
                "score": round(0.95 - i * 0.08, 2),
                "payload": {
                    "name": f"Villa {chr(65 + i)} — {query[:20]}",
                    "price_eur": 450_000 + i * 50_000,
                },
            }
            for i in range(min(top_k, 5))
        ]
        return {"query": query, "results": results, "tenant_id": self.tenant_id}

    def render_highlight(self, entity_id: str, reason: str) -> dict[str, Any]:
        """Emit a highlight RenderingDirective (returned as tool result)."""
        directive = {
            "type": "highlight",
            "target": entity_id,
            "params": {"reason": reason},
            "priority": 100,
            "reason": reason,
        }
        return {"directive": directive, "emitted": True}

    def lead_update_score(self, signal: str, weight: float) -> dict[str, Any]:
        """Record scoring signal and return updated total."""
        self._lead_state.signals.append({"signal": signal, "weight": weight})
        self._lead_state.total = min(1.0, self._lead_state.total + weight)
        return {
            "signal": signal,
            "weight": weight,
            "total": round(self._lead_state.total, 4),
            "signal_count": len(self._lead_state.signals),
        }

    @property
    def lead_score(self) -> float:
        return self._lead_state.total

    # ── Dispatch ──────────────────────────────────────────────────────────────

    def execute(self, tool_name: str, tool_input: dict[str, Any]) -> dict[str, Any]:
        """Dispatch tool_name with tool_input dict. Raises ValueError if unknown."""
        match tool_name:
            case "kg_search":
                return self.kg_search(
                    query=tool_input["query"],
                    top_k=tool_input.get("top_k", 5),
                )
            case "render_highlight":
                return self.render_highlight(
                    entity_id=tool_input["entity_id"],
                    reason=tool_input["reason"],
                )
            case "lead_update_score":
                return self.lead_update_score(
                    signal=tool_input["signal"],
                    weight=float(tool_input["weight"]),
                )
            case _:
                raise ValueError(f"Unknown tool: {tool_name!r}")
