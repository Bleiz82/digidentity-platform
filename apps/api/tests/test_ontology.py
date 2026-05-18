"""Tests for persona ontology loader — P3-04."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
import yaml

from digidentity_api.engines.ontology.loader import (
    PersonaDef,
    PersonaRegistry,
    load_personas,
    resolve_alias,
    validate_personas_file,
)
from digidentity_api.engines.ontology.loader import load_personas as _lp_fn

PACK = "real-estate-luxury"
REPO_ROOT = Path(__file__).resolve().parents[3]
SHARED_PATH = REPO_ROOT / "packs" / "shared" / "personas.yaml"
VERTICAL_PATH = REPO_ROOT / "packs" / PACK / "ontology" / "personas.yaml"
SCHEMA_PATH = REPO_ROOT / "core" / "dsl" / "personas.schema.json"
SCORECARD_PATH = REPO_ROOT / "packs" / PACK / "scoring" / "lead_scorecard.yaml"


def _fresh_registry(pack_id: str = PACK) -> PersonaRegistry:
    _lp_fn.cache_clear()
    return load_personas(pack_id)


# ── 1. shared + vertical merge ────────────────────────────────────────────────

def test_load_merges_shared_and_vertical():
    reg = _fresh_registry()
    ids = reg.canonical_ids
    # shared
    assert "browsing" in ids
    assert "returning_visitor" in ids
    assert "mobile_quick_visit" in ids
    assert "desktop_research_mode" in ids
    assert "social_referral" in ids
    # vertical
    assert "international_investor" in ids
    assert "luxury_retiree" in ids
    assert "family_relocating" in ids
    assert "holiday_seeker" in ids


# ── 2. alias resolution ───────────────────────────────────────────────────────

def test_resolve_alias_luxury_investor():
    reg = _fresh_registry()
    assert reg.resolve("luxury_investor") == "international_investor"


def test_resolve_alias_canonical_passthrough():
    reg = _fresh_registry()
    assert reg.resolve("international_investor") == "international_investor"


def test_resolve_alias_unknown_returns_none():
    reg = _fresh_registry()
    assert reg.resolve("business_traveler") is None


def test_resolve_alias_convenience_fn():
    _lp_fn.cache_clear()
    assert resolve_alias("luxury_investor", PACK) == "international_investor"


# ── 3. schema validation ──────────────────────────────────────────────────────

def test_schema_validates_shared_file():
    pytest.importorskip("jsonschema")
    errors = validate_personas_file(SHARED_PATH)
    assert errors == [], f"shared personas.yaml invalid: {errors}"


def test_schema_validates_vertical_file():
    pytest.importorskip("jsonschema")
    errors = validate_personas_file(VERTICAL_PATH)
    assert errors == [], f"vertical personas.yaml invalid: {errors}"


def test_schema_rejects_malformed(tmp_path: Path):
    pytest.importorskip("jsonschema")
    bad = tmp_path / "bad_personas.yaml"
    bad.write_text(
        yaml.dump(
            {
                "version": "1.0",
                "personas": [
                    {
                        "id": "INVALID ID",  # uppercase not allowed
                        "display_name_it": "x",
                        "display_name_en": "x",
                        "scope": "shared",
                        "description": "too short",
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    errors = validate_personas_file(bad)
    assert len(errors) > 0


# ── 4. unique ids ─────────────────────────────────────────────────────────────

def test_persona_ids_unique_in_pack():
    reg = _fresh_registry()
    ids = reg.canonical_ids
    assert len(ids) == len(set(ids)), f"Duplicate persona ids: {ids}"


# ── 5. scorecard modifiers resolvable ─────────────────────────────────────────

def test_scorecard_persona_modifiers_are_resolvable():
    _lp_fn.cache_clear()
    scorecard = yaml.safe_load(SCORECARD_PATH.read_text(encoding="utf-8"))
    modifiers = scorecard.get("persona_modifiers", {})
    reg = load_personas(PACK)
    for persona_id in modifiers:
        canonical = reg.resolve(persona_id)
        assert canonical is not None, (
            f"Scorecard modifier '{persona_id}' not resolvable in pack '{PACK}'"
        )


# ── 6. no ghost canonical ids ─────────────────────────────────────────────────

def test_no_ghost_canonical_ids_in_scorecard():
    scorecard = yaml.safe_load(SCORECARD_PATH.read_text(encoding="utf-8"))
    modifiers = scorecard.get("persona_modifiers", {})
    ghost_ids = {"luxury_investor", "business_traveler"}
    for ghost in ghost_ids:
        assert ghost not in modifiers, (
            f"Ghost canonical id '{ghost}' found in persona_modifiers — use alias instead"
        )


# ── 7. frontend canonical ids match backend ───────────────────────────────────

def test_frontend_inferPersona_uses_canonical_ids():
    frontend_sense_path = REPO_ROOT / "apps" / "web" / "src" / "lib" / "sense" / "rules.ts"
    content = frontend_sense_path.read_text(encoding="utf-8")
    _lp_fn.cache_clear()
    reg = load_personas(PACK)
    canonical_ids = set(reg.canonical_ids)
    for cid in ["international_investor", "family_relocating", "luxury_retiree", "holiday_seeker", "browsing"]:
        assert cid in content, f"Canonical persona id '{cid}' not found in rules.ts"
    assert "luxury_investor" not in content or "alias" in content.lower() or "ALIAS" in content, (
        "Legacy id 'luxury_investor' appears in rules.ts as a non-alias reference"
    )


# ── 8. regression: PersonaRegistry.get works ─────────────────────────────────

def test_persona_registry_get_returns_def():
    reg = _fresh_registry()
    p = reg.get("international_investor")
    assert p is not None
    assert isinstance(p, PersonaDef)
    assert p.display_name_en == "International Investor"
    assert "luxury_investor" in p.aliases


# ── 9. cache works correctly ──────────────────────────────────────────────────

def test_cache_returns_same_object():
    _lp_fn.cache_clear()
    r1 = load_personas(PACK)
    r2 = load_personas(PACK)
    assert r1 is r2
