"""Persona ontology loader — merges shared + vertical persona YAML files.

Resolves alias → canonical id. Per-pack cache avoids repeated disk reads.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path

import yaml

# ── Repo root resolution (same pattern as loader.py in other engines) ─────────
_REPO_ROOT = Path(__file__).resolve().parents[6]
_SHARED_PERSONAS_PATH = _REPO_ROOT / "packs" / "shared" / "personas.yaml"
_SCHEMA_PATH = _REPO_ROOT / "core" / "dsl" / "personas.schema.json"


@dataclass(frozen=True)
class PersonaDef:
    id: str
    display_name_it: str
    display_name_en: str
    scope: str
    description: str
    aliases: tuple[str, ...] = field(default_factory=tuple)
    inference_hints: tuple[str, ...] = field(default_factory=tuple)


@dataclass
class PersonaRegistry:
    personas: list[PersonaDef]
    _alias_map: dict[str, str] = field(default_factory=dict)

    def __post_init__(self) -> None:
        for p in self.personas:
            self._alias_map[p.id] = p.id
            for alias in p.aliases:
                self._alias_map[alias] = p.id

    def resolve(self, name: str) -> str | None:
        """Return canonical id for name or alias, or None if unknown."""
        return self._alias_map.get(name)

    def get(self, canonical_id: str) -> PersonaDef | None:
        for p in self.personas:
            if p.id == canonical_id:
                return p
        return None

    @property
    def canonical_ids(self) -> list[str]:
        return [p.id for p in self.personas]


def _parse_personas(raw: dict) -> list[PersonaDef]:
    result: list[PersonaDef] = []
    for item in raw.get("personas", []):
        result.append(
            PersonaDef(
                id=item["id"],
                display_name_it=item["display_name_it"],
                display_name_en=item["display_name_en"],
                scope=item["scope"],
                description=item["description"],
                aliases=tuple(item.get("aliases") or []),
                inference_hints=tuple(item.get("inference_hints") or []),
            )
        )
    return result


def _load_yaml(path: Path) -> dict:
    with path.open(encoding="utf-8") as fh:
        return yaml.safe_load(fh) or {}


@lru_cache(maxsize=16)
def load_personas(pack_id: str) -> PersonaRegistry:
    """Merge shared + vertical personas. Result cached per pack_id.

    shared personas appear first; vertical personas follow. Duplicate ids
    (vertical overriding shared) raise ValueError to fail fast at load time.
    """
    shared_raw = _load_yaml(_SHARED_PERSONAS_PATH)
    shared_personas = _parse_personas(shared_raw)

    vertical_path = _REPO_ROOT / "packs" / pack_id / "ontology" / "personas.yaml"
    vertical_personas: list[PersonaDef] = []
    if vertical_path.exists():
        vertical_raw = _load_yaml(vertical_path)
        vertical_personas = _parse_personas(vertical_raw)

    shared_ids = {p.id for p in shared_personas}
    for vp in vertical_personas:
        if vp.id in shared_ids:
            raise ValueError(
                f"Vertical persona '{vp.id}' in pack '{pack_id}' conflicts with a shared persona id."
            )

    all_personas = shared_personas + vertical_personas

    ids = [p.id for p in all_personas]
    if len(ids) != len(set(ids)):
        dupes = [i for i in ids if ids.count(i) > 1]
        raise ValueError(f"Duplicate persona ids in pack '{pack_id}': {dupes}")

    return PersonaRegistry(personas=all_personas)


def resolve_alias(name: str, pack_id: str) -> str | None:
    """Convenience wrapper: resolve alias → canonical id for a given pack."""
    return load_personas(pack_id).resolve(name)


def validate_personas_file(path: Path) -> list[str]:
    """Validate a personas.yaml against personas.schema.json.

    Returns list of error strings (empty = valid). Does NOT raise.
    Requires jsonschema (already in dev deps via pytest ecosystem).
    """
    try:
        import jsonschema  # optional: not a hard dep
    except ImportError:
        return ["jsonschema not installed — cannot validate"]

    schema = json.loads(_SCHEMA_PATH.read_text(encoding="utf-8"))
    raw = _load_yaml(path)
    errors: list[str] = []
    validator = jsonschema.Draft202012Validator(schema)
    for error in validator.iter_errors(raw):
        errors.append(f"{'.'.join(str(p) for p in error.absolute_path)}: {error.message}")
    return errors
