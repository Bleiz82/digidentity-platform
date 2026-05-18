"""
Unit tests STEP 8c: DSL morph rule linter — JSON Schema draft 2020-12.
Nessun DB, nessun container. Test puri di validazione schema.
"""

import json
from pathlib import Path

import pytest
import yaml
import jsonschema

# ── paths ─────────────────────────────────────────────────────────────────────

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent.parent
_SCHEMA_PATH = _REPO_ROOT / "core" / "dsl" / "morph_rule.schema.json"
_HOMEPAGE_YAML = _REPO_ROOT / "packs" / "real-estate-luxury" / "morph_rules" / "homepage.yaml"


@pytest.fixture(scope="module")
def schema() -> dict:
    with _SCHEMA_PATH.open(encoding="utf-8") as f:
        return json.load(f)


@pytest.fixture(scope="module")
def validator(schema: dict) -> jsonschema.Draft202012Validator:
    return jsonschema.Draft202012Validator(schema)


def _errors(validator: jsonschema.Draft202012Validator, data: dict) -> list[str]:
    return [e.message for e in validator.iter_errors(data)]


# ── test 1: homepage.yaml passes without modification ─────────────────────────


def test_homepage_yaml_valid(validator):
    with _HOMEPAGE_YAML.open(encoding="utf-8") as f:
        data = yaml.safe_load(f)
    errors = _errors(validator, data)
    assert errors == [], f"homepage.yaml schema errors: {errors}"


# ── test 2: minimal valid file passes ─────────────────────────────────────────


def test_minimal_valid_file(validator):
    data = {
        "version": 1,
        "target_page": "homepage",
        "rules": [
            {
                "id": "minimal-rule",
                "priority": 10,
                "when": {"signal": "persona_score.buyer", "gte": 0.5},
                "do": [{"directive": "show", "target": "hero_section"}],
            }
        ],
    }
    assert _errors(validator, data) == []


# ── test 3: unknown directive type fails ──────────────────────────────────────


def test_unknown_directive_type_fails(validator):
    data = {
        "version": 1,
        "target_page": "homepage",
        "rules": [
            {
                "id": "bad-directive",
                "priority": 10,
                "when": {"signal": "persona_score.buyer", "gte": 0.5},
                "do": [{"directive": "flash_banner", "target": "hero"}],
            }
        ],
    }
    errors = _errors(validator, data)
    assert errors, "expected validation error for unknown directive type"


# ── test 4: missing required top-level field fails ────────────────────────────


def test_missing_required_field_fails(validator):
    data = {
        "version": 1,
        # target_page missing
        "rules": [
            {
                "id": "some-rule",
                "priority": 5,
                "when": {"signal": "persona_score.x", "gte": 0.3},
                "do": [{"directive": "hide", "target": "widget"}],
            }
        ],
    }
    errors = _errors(validator, data)
    assert errors, "expected validation error for missing target_page"


# ── test 5: priority out of range fails ───────────────────────────────────────


def test_priority_out_of_range_fails(validator):
    data = {
        "version": 1,
        "target_page": "homepage",
        "rules": [
            {
                "id": "bad-priority",
                "priority": 9999,
                "when": {"signal": "persona_score.buyer", "gte": 0.5},
                "do": [{"directive": "show", "target": "hero"}],
            }
        ],
    }
    errors = _errors(validator, data)
    assert errors, "expected validation error for priority > 1000"


# ── test 6: match_all condition with valid sub-conditions passes ───────────────


def test_match_all_condition_valid(validator):
    data = {
        "version": 1,
        "target_page": "homepage",
        "rules": [
            {
                "id": "match-all-rule",
                "priority": 50,
                "when": {
                    "match_all": [
                        {"signal": "utm.campaign", "equals_any": ["luxury", "premium"]},
                        {"signal": "persona_score.investor", "gte": 0.6},
                    ]
                },
                "do": [
                    {"directive": "morph_section", "target": "hero_section",
                     "params": {"template": "investor_hero_v1"}},
                    {"directive": "track", "target": "_self",
                     "params": {"event_name": "morph_investor"}},
                ],
            }
        ],
        "fallback": [{"directive": "render_default"}],
    }
    assert _errors(validator, data) == []
