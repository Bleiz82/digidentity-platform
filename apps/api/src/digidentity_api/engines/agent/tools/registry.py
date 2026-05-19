"""ToolRegistry — executes the 3 built-in agent tools.

All execution is pure in-memory for Phase 2; no shell, no filesystem writes.
If session + visitor_session_id are provided, lead_update_score also persists
the accumulated score via qualify.persistence.upsert_lead (back-compat: in-memory
only when session is not available).

kg_search now calls EmbeddingRouter to embed the query (ADR-007 P3-03).
Results remain simulated until a live pgvector DB is available (P3-07).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any
from uuid import UUID

from digidentity_api.engines.agent.tools.schemas import ALL_TOOLS
from digidentity_api.engines.embeddings import EmbeddingRouter, get_router


@dataclass
class LeadScoreState:
    """Mutable per-conversation lead score accumulator."""

    total: float = 0.0
    signals: list[dict[str, Any]] = field(default_factory=list)


class ToolRegistry:
    """Executes tool calls by name, maintaining per-conversation lead state."""

    def __init__(
        self,
        tenant_id: str | UUID,
        session: Any = None,
        visitor_session_id: UUID | None = None,
        embedding_router: EmbeddingRouter | None = None,
    ) -> None:
        self.tenant_id = str(tenant_id)
        self._session = session
        self._visitor_session_id = visitor_session_id
        self._lead_state: LeadScoreState = LeadScoreState()
        self._embedding_router: EmbeddingRouter = embedding_router or get_router()

    # ── Schema accessor ───────────────────────────────────────────────────────

    @property
    def schemas(self) -> list[dict[str, Any]]:
        return ALL_TOOLS

    # ── Tool implementations ──────────────────────────────────────────────────

    async def kg_search(self, query: str, top_k: int = 5) -> dict[str, Any]:
        """Embed query via EmbeddingRouter then return simulated entity results.

        The embedding call is real (OpenAI) or mocked depending on config (ADR-007).
        Full pgvector retrieval will be wired in P3-07 when a live KG is available.
        """
        query_vectors = await self._embedding_router.embed([query])
        query_vector = query_vectors[0]  # keep for future pgvector lookup
        _ = query_vector  # not yet used for retrieval
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
        return {
            "query": query,
            "results": results,
            "tenant_id": self.tenant_id,
            "embedding_dims": len(query_vector),
        }

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

    def spatial_navigate(self, scene_id: str, reason: str) -> dict[str, Any]:
        """Emit a spatial_navigate RenderingDirective to transition the 360° viewer."""
        directive = {
            "type": "spatial_navigate",
            "target": scene_id,
            "params": {"target_scene_id": scene_id, "transition": "fade"},
            "priority": 200,
            "reason": reason,
        }
        return {"directive": directive, "emitted": True, "scene_id": scene_id}

    def lead_update_score(self, signal: str, weight: float) -> dict[str, Any]:
        """Record scoring signal and return updated total (in-memory accumulator).

        If session + visitor_session_id are configured, the caller should invoke
        `persist_lead_score()` after this to flush to DB.
        """
        self._lead_state.signals.append({"signal": signal, "weight": weight})
        self._lead_state.total = min(1.0, self._lead_state.total + weight)
        return {
            "signal": signal,
            "weight": weight,
            "total": round(self._lead_state.total, 4),
            "signal_count": len(self._lead_state.signals),
        }

    async def persist_lead_score(self) -> None:
        """Flush accumulated lead score to DB (no-op if session not configured)."""
        if self._session is None or self._visitor_session_id is None:
            return

        from datetime import UTC, datetime  # noqa: PLC0415

        from digidentity_api.engines.qualify.persistence import upsert_lead  # noqa: PLC0415
        from digidentity_api.schemas.lead import LeadScore, ScoringSignal  # noqa: PLC0415

        signals = [
            ScoringSignal(
                signal_name=s["signal"],
                weight=s["weight"],
                emitted_at=datetime.now(UTC),
            )
            for s in self._lead_state.signals
        ]

        # Convert in-memory [0,1] total to 0-100 scale
        score_100 = min(100.0, self._lead_state.total * 100.0)
        bucket = "hot" if score_100 >= 70 else "warm" if score_100 >= 30 else "cold"

        lead_score = LeadScore(
            session_id=self._visitor_session_id,
            score=score_100,
            bucket=bucket,  # type: ignore[arg-type]
            signals=signals,
            last_updated=datetime.now(UTC),
        )

        await upsert_lead(
            session=self._session,
            tenant_id=UUID(self.tenant_id),
            visitor_session_id=self._visitor_session_id,
            lead_score=lead_score,
        )

    @property
    def lead_score(self) -> float:
        return self._lead_state.total

    # ── Dispatch ──────────────────────────────────────────────────────────────

    async def execute(self, tool_name: str, tool_input: dict[str, Any]) -> dict[str, Any]:
        """Dispatch tool_name with tool_input dict. Raises ValueError if unknown."""
        match tool_name:
            case "kg_search":
                return await self.kg_search(
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
            case "spatial_navigate":
                return self.spatial_navigate(
                    scene_id=tool_input["scene_id"],
                    reason=tool_input["reason"],
                )
            case _:
                raise ValueError(f"Unknown tool: {tool_name!r}")
