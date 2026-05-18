"""Condition evaluator for morph DSL — BIBLE-v3 §8.

evaluate_condition(condition, prior) → bool

Supported operators (simple condition on a signal):
  gte, lte, gt, lt, equals / eq, neq, equals_any / in, not_in, matches_any

Compound conditions:
  match_all  — all sub-conditions must be true (AND)
  match_any  — at least one sub-condition must be true (OR)
  and / or / not — alternative compound keys

Signal paths resolved from VisitorPrior:
  persona_score.<id>    → inferred_personas score (0.0 if absent)
  utm.<key>             → signals.utm dict
  referrer              → signals.referrer
  referrer.domain       → parsed netloc of referrer
  device_class          → signals.device_class
  is_returning          → signals.is_returning
  geo_city              → signals.geo_city
  language              → signals.language
  dwell_time            → 0 (not tracked in VisitorPrior v1)
"""

from typing import Any
from urllib.parse import urlparse

from digidentity_api.schemas.visitor import VisitorPrior


def _resolve_signal(signal: str, prior: VisitorPrior) -> Any:
    if signal.startswith("persona_score."):
        persona_id = signal[len("persona_score."):]
        for ps in prior.inferred_personas:
            if ps.persona_id == persona_id:
                return ps.score
        return 0.0

    if signal.startswith("utm."):
        key = signal[len("utm."):]
        return prior.signals.utm.get(key, "")

    if signal.startswith("referrer."):
        attr = signal[len("referrer."):]
        referrer = prior.signals.referrer or ""
        if attr == "domain":
            try:
                return urlparse(referrer).netloc
            except Exception:
                return ""
        return referrer

    _direct: dict[str, Any] = {
        "device_class": prior.signals.device_class,
        "is_returning": prior.signals.is_returning,
        "referrer": prior.signals.referrer or "",
        "geo_city": prior.signals.geo_city or "",
        "language": prior.signals.language or "",
        "dwell_time": 0,
    }
    return _direct.get(signal)


def _apply_operator(value: Any, cond: dict[str, Any]) -> bool:
    if "gte" in cond:
        return float(value or 0) >= float(cond["gte"])
    if "lte" in cond:
        return float(value or 0) <= float(cond["lte"])
    if "gt" in cond:
        return float(value or 0) > float(cond["gt"])
    if "lt" in cond:
        return float(value or 0) < float(cond["lt"])
    if "equals" in cond:
        return value == cond["equals"]
    if "eq" in cond:
        return value == cond["eq"]
    if "neq" in cond:
        return value != cond["neq"]
    if "equals_any" in cond:
        return value in cond["equals_any"]
    if "in" in cond:
        return value in cond["in"]
    if "not_in" in cond:
        return value not in cond["not_in"]
    if "matches_any" in cond:
        val_str = str(value or "")
        return any(m in val_str for m in cond["matches_any"])
    # No operator key → truthy check on signal presence
    return bool(value)


def evaluate_condition(condition: dict[str, Any], prior: VisitorPrior) -> bool:
    """Evaluate a morph DSL condition against a VisitorPrior."""
    if "match_all" in condition:
        return all(evaluate_condition(c, prior) for c in condition["match_all"])
    if "match_any" in condition:
        return any(evaluate_condition(c, prior) for c in condition["match_any"])
    if "and" in condition:
        return all(evaluate_condition(c, prior) for c in condition["and"])
    if "or" in condition:
        return any(evaluate_condition(c, prior) for c in condition["or"])
    if "not" in condition:
        return not evaluate_condition(condition["not"], prior)

    signal = condition.get("signal")
    if signal is None:
        return False
    value = _resolve_signal(signal, prior)
    return _apply_operator(value, condition)
