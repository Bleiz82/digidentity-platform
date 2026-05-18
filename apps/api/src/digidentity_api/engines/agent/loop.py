"""AgentLoop — BIBLE §6.4.

Orchestrates the Anthropic tool-call loop:
  1. Build messages (system + user).
  2. Call provider → parse events.
  3. On tool_use: execute tool, append tool_result, loop.
  4. On message_stop with no pending tools: yield done.
  5. Hard caps: max 5 iterations, 30s total timeout.
  6. Persist every turn to conversation_turns via optional async_session.
"""

from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncIterator
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import UUID

import structlog

from digidentity_api.config import settings
from digidentity_api.engines.agent.providers.anthropic_provider import (
    BaseAnthropicProvider,
    get_provider,
)
from digidentity_api.engines.agent.tools.registry import ToolRegistry

log = structlog.get_logger()

_REPO_ROOT = Path(__file__).resolve().parents[7]
_FALLBACK_SYSTEM = (
    "Sei l'assistente del Living Site. Aiuta il visitatore a trovare la proprietà ideale."
)


def _load_system_prompt(pack_id: str) -> str:
    """Load system prompt from pack, falling back to built-in placeholder."""
    prompt_path = _REPO_ROOT / "packs" / pack_id / "prompts" / "system.md"
    try:
        return prompt_path.read_text(encoding="utf-8").strip()
    except FileNotFoundError:
        return _FALLBACK_SYSTEM


class AgentLoop:
    """Async generator-based agent loop for one conversation turn."""

    def __init__(
        self,
        provider: BaseAnthropicProvider | None = None,
        session: Any = None,
    ) -> None:
        self._provider = provider or get_provider()
        self._session = session  # optional SQLAlchemy AsyncSession

    async def run(
        self,
        conversation_id: str | UUID,
        user_message: str,
        tenant_id: str | UUID,
        pack_id: str = "real-estate-luxury",
    ) -> AsyncIterator[dict[str, Any]]:
        """Run the agent loop. Yields SSE-ready event dicts."""
        conv_id = str(conversation_id)
        t_id = str(tenant_id)
        system = _load_system_prompt(pack_id)
        registry = ToolRegistry(tenant_id=t_id)

        messages: list[dict[str, Any]] = [{"role": "user", "content": user_message}]
        collected_tool_calls: list[dict[str, Any]] = []
        collected_directives: list[dict[str, Any]] = []
        turn_index = 0

        async def _run_loop() -> AsyncIterator[dict[str, Any]]:
            nonlocal turn_index

            for iteration in range(settings.AGENT_MAX_ITERATIONS):
                pending_tool_uses: list[dict[str, Any]] = []
                assistant_text_parts: list[str] = []

                async for event in self._provider.stream_message(
                    system=system,
                    messages=messages,
                    tools=registry.schemas,
                    model=settings.ANTHROPIC_MODEL,
                ):
                    etype = event.get("type")

                    if etype == "text_delta":
                        assistant_text_parts.append(event["text"])
                        yield {"type": "text", "data": {"text": event["text"]}}

                    elif etype == "tool_use":
                        pending_tool_uses.append(event)
                        yield {"type": "tool_call", "data": {
                            "id": event["id"],
                            "name": event["name"],
                            "input": event["input"],
                        }}
                        collected_tool_calls.append(event)

                    elif etype == "message_stop":
                        pass

                if not pending_tool_uses:
                    # No tools called — conversation complete
                    assistant_text = "".join(assistant_text_parts)
                    await _persist_turn(
                        conv_id, t_id, turn_index, "user", user_message if iteration == 0 else None
                    )
                    turn_index += 1
                    await _persist_turn(
                        conv_id, t_id, turn_index, "assistant", assistant_text,
                        tool_calls=collected_tool_calls if collected_tool_calls else None,
                        directives=collected_directives if collected_directives else None,
                    )
                    yield {"type": "done", "data": {
                        "iterations": iteration + 1,
                        "lead_score": registry.lead_score,
                    }}
                    return

                # Execute tools and build tool_result messages
                tool_results: list[dict[str, Any]] = []
                for tu in pending_tool_uses:
                    try:
                        result = registry.execute(tu["name"], tu["input"])
                    except Exception as exc:
                        result = {"error": str(exc)}

                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": tu["id"],
                        "content": json.dumps(result),
                    })

                    yield {"type": "tool_result", "data": {
                        "tool_use_id": tu["id"],
                        "name": tu["name"],
                        "result": result,
                    }}

                    # If render_highlight emitted a directive, surface it
                    if tu["name"] == "render_highlight" and "directive" in result:
                        collected_directives.append(result["directive"])
                        yield {"type": "directive", "data": result["directive"]}

                # Append assistant + tool_result messages for next iteration
                assistant_content: list[dict[str, Any]] = []
                if "".join(assistant_text_parts):
                    assistant_content.append({"type": "text", "text": "".join(assistant_text_parts)})
                for tu in pending_tool_uses:
                    assistant_content.append({
                        "type": "tool_use",
                        "id": tu["id"],
                        "name": tu["name"],
                        "input": tu["input"],
                    })

                messages.append({"role": "assistant", "content": assistant_content})
                messages.append({"role": "user", "content": tool_results})

            # Max iterations reached
            yield {"type": "done", "data": {
                "iterations": settings.AGENT_MAX_ITERATIONS,
                "max_iterations_reached": True,
                "lead_score": registry.lead_score,
            }}

        async def _persist_turn(
            conv_id: str,
            t_id: str,
            idx: int,
            role: str,
            content: str | None,
            tool_calls: list[dict[str, Any]] | None = None,
            directives: list[dict[str, Any]] | None = None,
        ) -> None:
            if self._session is None:
                return
            from digidentity_api.db.models import ConversationTurn  # noqa: PLC0415

            turn = ConversationTurn(
                conversation_id=UUID(conv_id),
                tenant_id=UUID(t_id),
                turn_index=idx,
                role=role,
                content=content,
                tool_calls_json=tool_calls,
                rendering_directives_emitted=directives,
                created_at=datetime.now(UTC),
            )
            self._session.add(turn)
            try:
                await self._session.flush()
            except Exception as exc:
                log.error("agent_loop.persist_turn.error", error=str(exc))

        try:
            async with asyncio.timeout(settings.AGENT_TIMEOUT_SECS):
                async for event in _run_loop():
                    yield event
        except TimeoutError:
            yield {"type": "error", "data": {"code": "timeout", "secs": settings.AGENT_TIMEOUT_SECS}}
