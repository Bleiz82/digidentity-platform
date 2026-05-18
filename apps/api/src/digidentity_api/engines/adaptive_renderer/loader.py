"""Morph rule YAML loader and validator — BIBLE-v3 §8.

load_pack_rules(pack_path) reads all morph_rules/*.yaml, validates each
against core/dsl/morph_rule.schema.json, and caches by pack path.
"""

import json
from functools import lru_cache
from pathlib import Path
from typing import Any

import jsonschema
import yaml

_REPO_ROOT = Path(__file__).resolve().parents[6]
_SCHEMA_PATH = _REPO_ROOT / "core" / "dsl" / "morph_rule.schema.json"

# In-memory cache: resolved pack path str → list of rule-file dicts
_RULES_CACHE: dict[str, list[dict[str, Any]]] = {}


@lru_cache(maxsize=1)
def _get_schema() -> dict[str, Any]:
    with _SCHEMA_PATH.open(encoding="utf-8") as f:
        return json.load(f)


def load_pack_rules(pack_path: Path) -> list[dict[str, Any]]:
    """Return validated rule-file dicts for all morph_rules/*.yaml in pack_path.

    Each dict has the top-level YAML structure: {version, target_page, rules, fallback?}.
    Raises FileNotFoundError if morph_rules/ dir missing.
    Raises ValueError if any YAML fails schema validation.
    Results are cached by resolved path.
    """
    key = str(pack_path.resolve())
    if key in _RULES_CACHE:
        return _RULES_CACHE[key]

    morph_dir = pack_path / "morph_rules"
    if not morph_dir.is_dir():
        raise FileNotFoundError(f"morph_rules/ not found in {pack_path}")

    schema = _get_schema()
    validator = jsonschema.Draft202012Validator(schema)

    rule_files: list[dict[str, Any]] = []
    for yaml_path in sorted(morph_dir.glob("*.yaml")):
        with yaml_path.open(encoding="utf-8") as f:
            data = yaml.safe_load(f)
        errors = list(validator.iter_errors(data))
        if errors:
            msgs = "; ".join(e.message for e in errors[:5])
            raise ValueError(f"{yaml_path.name} schema validation failed: {msgs}")
        rule_files.append(data)

    _RULES_CACHE[key] = rule_files
    return rule_files


def clear_cache() -> None:
    """Clear the in-memory rules cache (for tests and hot-reload)."""
    _RULES_CACHE.clear()
