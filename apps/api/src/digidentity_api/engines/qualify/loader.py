"""Scorecard loader with JSON Schema validation and per-pack cache."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import jsonschema
import yaml

_REPO_ROOT = Path(__file__).resolve().parents[6]
_SCHEMA_PATH = _REPO_ROOT / "core" / "dsl" / "scorecard.schema.json"

_CACHE: dict[str, dict[str, Any]] = {}


def _load_schema() -> dict[str, Any]:
    import json  # noqa: PLC0415

    return json.loads(_SCHEMA_PATH.read_text(encoding="utf-8"))


def load_scorecard(pack_path: Path) -> dict[str, Any]:
    """Load and validate the scoring/lead_scorecard.yaml for a pack.

    Caches by resolved path. Raises FileNotFoundError if missing,
    jsonschema.ValidationError if schema invalid.
    """
    scorecard_path = pack_path / "scoring" / "lead_scorecard.yaml"
    cache_key = str(scorecard_path.resolve())

    if cache_key in _CACHE:
        return _CACHE[cache_key]

    if not scorecard_path.exists():
        raise FileNotFoundError(f"Scorecard not found: {scorecard_path}")

    raw = yaml.safe_load(scorecard_path.read_text(encoding="utf-8"))
    schema = _load_schema()

    validator = jsonschema.Draft202012Validator(schema)
    validator.validate(raw)

    _CACHE[cache_key] = raw
    return raw


def get_pack_path(pack_id: str) -> Path:
    return _REPO_ROOT / "packs" / pack_id


def clear_cache() -> None:
    _CACHE.clear()
