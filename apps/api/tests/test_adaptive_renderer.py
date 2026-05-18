"""
STEP 9: Adaptive Renderer Decision Engine — test suite.
Nessun DB, nessun container. Test puri in-process.
"""

import time
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from digidentity_api.engines.adaptive_renderer.evaluator import evaluate_condition
from digidentity_api.engines.adaptive_renderer.loader import clear_cache, load_pack_rules
from digidentity_api.engines.adaptive_renderer.decision_engine import DecisionEngine
from digidentity_api.schemas.visitor import PersonaScore, SenseSignals, VisitorPrior

_REPO_ROOT = Path(__file__).resolve().parents[3]
_REAL_ESTATE_PACK = _REPO_ROOT / "packs" / "real-estate-luxury"
_NOW = datetime.now(timezone.utc)


def _prior(
    *,
    personas: list[tuple[str, float]] | None = None,
    utm: dict[str, str] | None = None,
    device_class: str = "desktop",
    is_returning: bool = False,
    referrer: str | None = None,
    geo_city: str | None = None,
    language: str | None = None,
) -> VisitorPrior:
    return VisitorPrior(
        session_id=uuid4(),
        tenant_id=uuid4(),
        visitor_hash="abcdef1234567890",
        inferred_personas=[PersonaScore(persona_id=pid, score=s) for pid, s in (personas or [])],
        signals=SenseSignals(
            device_class=device_class,  # type: ignore[arg-type]
            utm=utm or {},
            is_returning=is_returning,
            referrer=referrer,
            geo_city=geo_city,
            language=language,
        ),
        confidence=0.8,
        created_at=_NOW,
        updated_at=_NOW,
    )


# ── loader tests ──────────────────────────────────────────────────────────────


def test_load_pack_rules_validates_homepage_yaml():
    clear_cache()
    rules = load_pack_rules(_REAL_ESTATE_PACK)
    assert len(rules) >= 1
    homepage = next(r for r in rules if r["target_page"] == "homepage")
    assert homepage["version"] == 1
    assert len(homepage["rules"]) == 3


def test_load_pack_rules_rejects_invalid_yaml(tmp_path: Path):
    clear_cache()
    pack = tmp_path / "bad-pack"
    morph_dir = pack / "morph_rules"
    morph_dir.mkdir(parents=True)
    (morph_dir / "bad.yaml").write_text(
        "version: 1\ntarget_page: x\nrules:\n  - id: r\n    priority: 9999\n    when: {signal: x}\n    do: []\n",
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="schema validation failed"):
        load_pack_rules(pack)
    clear_cache()


# ── evaluator tests (10 operators) ───────────────────────────────────────────


@pytest.mark.parametrize(
    "condition,prior_kwargs,expected",
    [
        # gte
        ({"signal": "persona_score.buyer", "gte": 0.5}, {"personas": [("buyer", 0.7)]}, True),
        # lte
        ({"signal": "persona_score.buyer", "lte": 0.3}, {"personas": [("buyer", 0.2)]}, True),
        # gt
        ({"signal": "persona_score.buyer", "gt": 0.5}, {"personas": [("buyer", 0.5)]}, False),
        # lt
        ({"signal": "persona_score.buyer", "lt": 0.5}, {"personas": [("buyer", 0.4)]}, True),
        # equals
        ({"signal": "device_class", "equals": "mobile"}, {"device_class": "mobile"}, True),
        # eq
        ({"signal": "device_class", "eq": "desktop"}, {"device_class": "desktop"}, True),
        # neq
        ({"signal": "device_class", "neq": "bot"}, {"device_class": "mobile"}, True),
        # equals_any
        ({"signal": "utm.source", "equals_any": ["google", "bing"]}, {"utm": {"source": "google"}}, True),
        # not_in
        ({"signal": "utm.source", "not_in": ["spam"]}, {"utm": {"source": "google"}}, True),
        # matches_any (substring)
        ({"signal": "referrer", "matches_any": ["luxury"]}, {"referrer": "https://luxury-homes.it"}, True),
    ],
    ids=["gte", "lte", "gt", "lt", "equals", "eq", "neq", "equals_any", "not_in", "matches_any"],
)
def test_evaluator_operators(condition, prior_kwargs, expected):
    prior = _prior(**prior_kwargs)
    assert evaluate_condition(condition, prior) is expected


# ── decision engine tests ─────────────────────────────────────────────────────


def test_decision_engine_priority_ordering():
    """Higher priority rule directives appear before lower priority ones."""
    engine = DecisionEngine(repo_root=_REPO_ROOT)
    # family_relocating (priority 30) > investor (priority 20) > retiree (priority 10)
    prior = _prior(personas=[
        ("family_relocating", 0.9),
        ("international_investor", 0.9),
        ("luxury_retiree", 0.9),
    ])
    directives, matched = engine.decide(prior, "homepage", "real-estate-luxury")
    assert "family-relocating-hero" in matched
    assert matched.index("family-relocating-hero") < matched.index("investor-roi-hero")


def test_decision_engine_conflict_resolution_same_target():
    """When two rules target the same section, highest priority rule wins."""
    engine = DecisionEngine(repo_root=_REPO_ROOT)
    # Both family_relocating (prio 30) and investor (prio 20) morph hero_section
    prior = _prior(personas=[
        ("family_relocating", 0.9),
        ("international_investor", 0.9),
    ])
    directives, matched = engine.decide(prior, "homepage", "real-estate-luxury")

    # Find directives targeting hero_section
    hero_directives = [d for d in directives if d.target == "hero_section"]
    # Only one should survive (conflict resolution)
    assert len(hero_directives) == 1
    # It must come from the higher-priority rule (family-relocating, template=family_hero_v1)
    assert hero_directives[0].params.get("template") == "family_hero_v1"


def test_decision_engine_fallback_no_match():
    """When no rule matches, directives list is empty (render default)."""
    engine = DecisionEngine(repo_root=_REPO_ROOT)
    prior = _prior(personas=[("unknown_persona", 0.1)])
    directives, matched = engine.decide(prior, "homepage", "real-estate-luxury")
    assert matched == []
    assert directives == []


def test_decision_engine_pack_not_found():
    engine = DecisionEngine(repo_root=_REPO_ROOT)
    prior = _prior()
    with pytest.raises(FileNotFoundError, match="Pack 'nonexistent'"):
        engine.decide(prior, "homepage", "nonexistent")


# ── API endpoint tests ────────────────────────────────────────────────────────


@pytest.fixture(scope="module")
def client():
    from digidentity_api.main import app
    return TestClient(app)


def _decide_payload(
    tenant_id: str | None = None,
    personas: list[tuple[str, float]] | None = None,
    pack_id: str = "real-estate-luxury",
    target_page: str = "homepage",
) -> tuple[dict, dict]:
    tid = tenant_id or str(uuid4())
    sid = str(uuid4())
    payload = {
        "prior": {
            "session_id": sid,
            "tenant_id": tid,
            "visitor_hash": "abcdef1234567890",
            "inferred_personas": [
                {"persona_id": pid, "score": s} for pid, s in (personas or [])
            ],
            "signals": {
                "device_class": "desktop",
                "utm": {},
                "is_returning": False,
            },
            "confidence": 0.8,
            "created_at": _NOW.isoformat(),
            "updated_at": _NOW.isoformat(),
        },
        "target_page": target_page,
        "pack_id": pack_id,
    }
    headers = {"X-Tenant-Id": tid}
    return payload, headers


def test_api_decide_200_with_directives(client):
    payload, headers = _decide_payload(personas=[("family_relocating", 0.9)])
    resp = client.post("/api/v1/rendering/decide", json=payload, headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["directives"]) >= 1
    assert "family-relocating-hero" in data["matched_rules"]
    assert data["latency_ms"] >= 0


def test_api_decide_422_malformed_prior(client):
    payload = {"prior": {"session_id": "not-a-uuid"}, "target_page": "homepage", "pack_id": "real-estate-luxury"}
    resp = client.post("/api/v1/rendering/decide", json=payload, headers={"X-Tenant-Id": str(uuid4())})
    assert resp.status_code == 422


def test_api_decide_404_pack_not_found(client):
    payload, headers = _decide_payload(pack_id="nonexistent-pack")
    resp = client.post("/api/v1/rendering/decide", json=payload, headers=headers)
    assert resp.status_code == 404


# ── latency test ──────────────────────────────────────────────────────────────


def test_p95_latency_under_50ms():
    """P95 decision latency must be < 50ms over 100 iterations (BIBLE §6.2)."""
    engine = DecisionEngine(repo_root=_REPO_ROOT)
    prior = _prior(personas=[("family_relocating", 0.9)])
    latencies: list[float] = []

    for _ in range(100):
        t0 = time.perf_counter()
        engine.decide(prior, "homepage", "real-estate-luxury")
        latencies.append((time.perf_counter() - t0) * 1000)

    latencies.sort()
    p95 = latencies[94]  # index 94 of 100-element sorted list = 95th percentile
    assert p95 < 50.0, f"P95 latency {p95:.2f}ms exceeds 50ms budget"


# ── tenant isolation test ─────────────────────────────────────────────────────


def test_tenant_isolation_same_pack(client):
    """Two different tenants using the same pack get identical directives (pack-scoped rules)."""
    personas = [("family_relocating", 0.9)]
    payload_a, headers_a = _decide_payload(personas=personas)
    payload_b, headers_b = _decide_payload(personas=personas)

    resp_a = client.post("/api/v1/rendering/decide", json=payload_a, headers=headers_a)
    resp_b = client.post("/api/v1/rendering/decide", json=payload_b, headers=headers_b)

    assert resp_a.status_code == 200
    assert resp_b.status_code == 200

    # Same pack rules → same matched_rules regardless of tenant
    data_a, data_b = resp_a.json(), resp_b.json()
    assert data_a["matched_rules"] == data_b["matched_rules"]
    assert len(data_a["directives"]) == len(data_b["directives"])
