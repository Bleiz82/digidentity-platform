"""Decision Engine — pure-functional rule evaluation — BIBLE-v3 §6.2.

DecisionEngine.decide(prior, target_page, pack_id) → (directives, matched_rule_ids)

Algorithm:
1. Load morph rule files for pack_id (cached).
2. Filter by target_page.
3. Evaluate each rule's condition against prior.
4. Sort matching rules by priority desc.
5. Conflict resolution: per (directive, target) pair, highest-priority rule wins.
6. Convert matching DSL directives to RenderingDirective (filtering non-rendering types).
7. Cap at _MAX_DIRECTIVES.
"""

from pathlib import Path
from typing import Any

from digidentity_api.engines.adaptive_renderer.evaluator import evaluate_condition
from digidentity_api.engines.adaptive_renderer.loader import load_pack_rules
from digidentity_api.schemas.rendering import RenderingDirective
from digidentity_api.schemas.visitor import VisitorPrior

_MAX_DIRECTIVES = 10
_REPO_ROOT = Path(__file__).resolve().parents[6]

# DSL directive types that map to RenderingDirective (BIBLE §7.2)
# track, trigger_agent, render_default are DSL-internal; excluded from API output
_RENDERING_TYPES: frozenset[str] = frozenset({
    "morph_section",
    "highlight",
    "inject",
    "set_persona",
    "show",
    "hide",
    "reorder",
    "rewrite_copy",
})


def _to_rendering_directive(d: dict[str, Any], rule_id: str) -> RenderingDirective | None:
    dtype = d.get("directive", "")
    target = d.get("target", "")
    if dtype not in _RENDERING_TYPES or not target:
        return None
    return RenderingDirective(
        type=dtype,  # type: ignore[arg-type]
        target=target,
        params=d.get("params", {}),
        priority=100,
        reason=f"rule:{rule_id}",
    )


class DecisionEngine:
    """Pure-functional Decision Engine for the Adaptive Renderer.

    repo_root is injected for testability; defaults to the monorepo root.
    """

    def __init__(self, repo_root: Path | None = None) -> None:
        self._repo_root = repo_root or _REPO_ROOT

    def decide(
        self,
        prior: VisitorPrior,
        target_page: str,
        pack_id: str,
    ) -> tuple[list[RenderingDirective], list[str]]:
        """Evaluate morph rules and return (rendering_directives, matched_rule_ids).

        Raises FileNotFoundError if pack_id does not exist.
        Returns ([], []) when no rules match (client renders default layout).
        """
        pack_path = self._repo_root / "packs" / pack_id
        if not pack_path.is_dir():
            raise FileNotFoundError(f"Pack '{pack_id}' not found")

        rule_files = load_pack_rules(pack_path)

        # Collect (priority, rule_id, do_list) for rules matching target_page + condition
        candidates: list[tuple[int, str, list[dict[str, Any]]]] = []

        for rule_file in rule_files:
            if rule_file.get("target_page") != target_page:
                continue
            for rule in rule_file.get("rules", []):
                if evaluate_condition(rule.get("when", {}), prior):
                    candidates.append((
                        rule.get("priority", 0),
                        rule.get("id", ""),
                        rule.get("do", []),
                    ))

        # Sort by priority descending (highest first)
        candidates.sort(key=lambda x: x[0], reverse=True)

        # Conflict resolution: first seen (highest priority) wins per (directive, target)
        seen: set[tuple[str, str]] = set()
        result: list[RenderingDirective] = []
        matched_ids: list[str] = []

        for _priority, rule_id, do_list in candidates:
            matched_ids.append(rule_id)
            for d in do_list:
                key = (d.get("directive", ""), d.get("target", ""))
                if key in seen:
                    continue
                seen.add(key)
                rd = _to_rendering_directive(d, rule_id)
                if rd is not None and len(result) < _MAX_DIRECTIVES:
                    result.append(rd)

        return result, matched_ids
