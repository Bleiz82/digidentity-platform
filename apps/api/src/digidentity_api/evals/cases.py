"""Eval case data classes and YAML loader.

Defines EvalCase, EvalSet, and load_eval_set() for the eval framework.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal

import yaml

EvalType = Literal["retrieval", "routing", "circuit_breaker", "latency"]


@dataclass
class EvalCase:
    id: str
    type: EvalType
    input: dict[str, Any]
    expected: dict[str, Any]
    tags: list[str] = field(default_factory=list)


@dataclass
class EvalSet:
    name: str
    description: str
    cases: list[EvalCase]
    thresholds: dict[str, float]
    calibration_mode: bool = True


def load_eval_set(path: Path) -> EvalSet:
    """Carica un file YAML e restituisce un EvalSet."""
    with path.open("r", encoding="utf-8") as f:
        data = yaml.safe_load(f)

    meta = data.get("meta", {})
    name = meta.get("name", path.stem)
    description = meta.get("description", "")
    calibration_mode = bool(meta.get("calibration_mode", True))
    thresholds: dict[str, float] = {k: float(v) for k, v in meta.get("thresholds", {}).items()}

    cases: list[EvalCase] = []
    for raw in data.get("cases", []):
        case = EvalCase(
            id=raw["id"],
            type=raw["type"],
            input=raw.get("input", {}),
            expected=raw.get("expected", {}),
            tags=raw.get("tags", []),
        )
        cases.append(case)

    return EvalSet(
        name=name,
        description=description,
        cases=cases,
        thresholds=thresholds,
        calibration_mode=calibration_mode,
    )
