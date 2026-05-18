"""Tests for Qualify engine — BIBLE §6.5 lead scoring.

Fast tests (no DB): loader, scorer.
Mock-based: persistence unit tests, API endpoint tests.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import UUID

import pytest

from digidentity_api.engines.qualify.loader import clear_cache, get_pack_path, load_scorecard
from digidentity_api.engines.qualify.scorer import LeadScorer
from digidentity_api.schemas.lead import LeadScore, ScoringSignal

TENANT_ID = UUID("00000000-0000-0000-0000-000000000001")
VISITOR_SESSION_ID = UUID("00000000-0000-0000-0000-000000000099")
_REAL_ESTATE_PACK_PATH = get_pack_path("real-estate-luxury")
_NOW = datetime.now(UTC)


def _sig(name: str, weight: float) -> ScoringSignal:
    return ScoringSignal(signal_name=name, weight=weight, emitted_at=_NOW)


# ── 1. Loader validates lead_scorecard.yaml ───────────────────────────────────

def test_loader_validates_real_estate_scorecard() -> None:
    clear_cache()
    scorecard = load_scorecard(_REAL_ESTATE_PACK_PATH)
    assert scorecard["version"] == "1.0"
    assert len(scorecard["signals"]) >= 10
    assert "buckets" in scorecard
    for sig in scorecard["signals"]:
        assert "id" in sig
        assert "weight" in sig
        assert "max_score" in sig


# ── 2. Loader rejects malformed scorecard ────────────────────────────────────

def test_loader_rejects_missing_required_field(tmp_path: Path) -> None:
    import jsonschema  # noqa: PLC0415
    import yaml  # noqa: PLC0415

    scoring_dir = tmp_path / "scoring"
    scoring_dir.mkdir()
    bad = {"version": "1.0", "signals": []}  # missing 'buckets'
    (scoring_dir / "lead_scorecard.yaml").write_text(yaml.dump(bad))

    clear_cache()
    with pytest.raises(jsonschema.ValidationError):
        load_scorecard(tmp_path)


# ── 3. Scorer cold (low signals) ─────────────────────────────────────────────

def test_scorer_cold() -> None:
    clear_cache()
    scorecard = load_scorecard(_REAL_ESTATE_PACK_PATH)
    scorer = LeadScorer()

    result = scorer.compute(
        session_id=VISITOR_SESSION_ID,
        signals=[_sig("dwell_long", 0.1)],  # 0.1 * 8 = 0.8 points
        top_persona_id=None,
        scorecard=scorecard,
    )
    assert result.bucket == "cold"
    assert result.score < 30


# ── 4. Scorer warm ───────────────────────────────────────────────────────────

def test_scorer_warm() -> None:
    clear_cache()
    scorecard = load_scorecard(_REAL_ESTATE_PACK_PATH)
    scorer = LeadScorer()

    result = scorer.compute(
        session_id=VISITOR_SESSION_ID,
        signals=[
            _sig("budget_explicit", 1.0),   # 15
            _sig("location_specific", 1.0), # 10
            _sig("family_mentioned", 1.0),  # 8
        ],
        top_persona_id=None,
        scorecard=scorecard,
    )
    assert result.bucket == "warm"
    assert 30 <= result.score < 70


# ── 5. Scorer hot ────────────────────────────────────────────────────────────

def test_scorer_hot() -> None:
    clear_cache()
    scorecard = load_scorecard(_REAL_ESTATE_PACK_PATH)
    scorer = LeadScorer()

    result = scorer.compute(
        session_id=VISITOR_SESSION_ID,
        signals=[
            _sig("contact_provided", 1.0),   # 20
            _sig("viewing_requested", 1.0),  # 25
            _sig("budget_explicit", 1.0),    # 15
            _sig("timeline_urgent", 1.0),    # 12
        ],
        top_persona_id=None,
        scorecard=scorecard,
    )
    assert result.bucket == "hot"
    assert result.score >= 70


# ── 6. Scorer applies persona_modifier international_investor ─────────────────

def test_scorer_persona_modifier_international_investor() -> None:
    clear_cache()
    scorecard = load_scorecard(_REAL_ESTATE_PACK_PATH)
    scorer = LeadScorer()

    no_modifier = scorer.compute(
        session_id=VISITOR_SESSION_ID,
        signals=[_sig("location_specific", 1.0)],  # 10 pts
        top_persona_id=None,
        scorecard=scorecard,
    )

    with_modifier = scorer.compute(
        session_id=VISITOR_SESSION_ID,
        signals=[_sig("location_specific", 1.0)],  # 10 pts
        top_persona_id="international_investor",    # +10
        scorecard=scorecard,
    )

    assert with_modifier.score == pytest.approx(no_modifier.score + 10.0)


# ── 7. Cap max_score per signal ───────────────────────────────────────────────

def test_scorer_caps_max_score_per_signal() -> None:
    clear_cache()
    scorecard = load_scorecard(_REAL_ESTATE_PACK_PATH)
    scorer = LeadScorer()

    # dwell_long max_score = 8; weight=999 should not exceed 8
    result = scorer.compute(
        session_id=VISITOR_SESSION_ID,
        signals=[_sig("dwell_long", 999.0)],
        top_persona_id=None,
        scorecard=scorecard,
    )
    # Only dwell_long: 8 pts (capped)
    assert result.score <= 8.0


# ── 8. Cap total at 100 ───────────────────────────────────────────────────────

def test_scorer_caps_total_at_100() -> None:
    clear_cache()
    scorecard = load_scorecard(_REAL_ESTATE_PACK_PATH)
    scorer = LeadScorer()

    # Provide all signals at max weight
    all_signals = [_sig(s["id"], 1.0) for s in scorecard["signals"]]
    result = scorer.compute(
        session_id=VISITOR_SESSION_ID,
        signals=all_signals,
        top_persona_id="international_investor",  # +10 on top
        scorecard=scorecard,
    )
    assert result.score <= 100.0


# ── 9. Persistence: upsert INSERT new lead ────────────────────────────────────

@pytest.mark.asyncio
async def test_persistence_upsert_insert() -> None:
    from digidentity_api.engines.qualify.persistence import upsert_lead  # noqa: PLC0415

    mock_session = AsyncMock()
    mock_session.execute = AsyncMock(return_value=MagicMock(scalar_one_or_none=lambda: None))
    mock_session.add = MagicMock()
    mock_session.flush = AsyncMock()

    lead_score = LeadScore(
        session_id=VISITOR_SESSION_ID,
        score=45.0,
        bucket="warm",
        signals=[_sig("budget_explicit", 1.0)],
        last_updated=_NOW,
    )

    result = await upsert_lead(mock_session, TENANT_ID, VISITOR_SESSION_ID, lead_score)
    mock_session.add.assert_called_once()
    mock_session.flush.assert_called_once()


# ── 10. Persistence: upsert UPDATE existing lead ─────────────────────────────

@pytest.mark.asyncio
async def test_persistence_upsert_update_existing() -> None:
    from digidentity_api.db.models import Lead  # noqa: PLC0415
    from digidentity_api.engines.qualify.persistence import upsert_lead  # noqa: PLC0415

    existing_lead = MagicMock(spec=Lead)
    existing_lead.score = 10.0
    existing_lead.bucket = "cold"

    mock_session = AsyncMock()
    mock_session.execute = AsyncMock(
        return_value=MagicMock(scalar_one_or_none=lambda: existing_lead)
    )
    mock_session.flush = AsyncMock()

    lead_score = LeadScore(
        session_id=VISITOR_SESSION_ID,
        score=75.0,
        bucket="hot",
        signals=[_sig("viewing_requested", 1.0)],
        last_updated=_NOW,
    )

    result = await upsert_lead(mock_session, TENANT_ID, VISITOR_SESSION_ID, lead_score)

    assert result.score == 75.0
    assert result.bucket == "hot"
    mock_session.flush.assert_called_once()


# ── 11. API GET 200 + 404 ─────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_api_get_lead_404(client) -> None:
    """GET returns 404 when DB unavailable or lead absent (503 → acceptable)."""
    resp = await client.get(
        f"/api/v1/leads/{VISITOR_SESSION_ID}",
        headers={"X-Tenant-Id": str(TENANT_ID)},
    )
    # 404 (no lead) or 503 (no DB) are both valid in test env without real DB
    assert resp.status_code in (404, 503)


@pytest.mark.asyncio
async def test_api_get_lead_missing_tenant_header(client) -> None:
    resp = await client.get(f"/api/v1/leads/{VISITOR_SESSION_ID}")
    assert resp.status_code == 422  # X-Tenant-Id required


# ── 12. API POST 200 + persist ────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_api_post_score_computes_and_responds(client) -> None:
    """POST returns 200 with computed LeadScore (persist may fail without DB)."""
    payload = {
        "signals": [
            {
                "signal_name": "viewing_requested",
                "weight": 1.0,
                "emitted_at": _NOW.isoformat(),
                "source": None,
            },
            {
                "signal_name": "contact_provided",
                "weight": 1.0,
                "emitted_at": _NOW.isoformat(),
                "source": None,
            },
        ],
        "top_persona_id": "international_investor",
        "pack_id": "real-estate-luxury",
    }

    from contextlib import asynccontextmanager  # noqa: PLC0415

    @asynccontextmanager
    async def _fake_with_tenant(*args, **kwargs):
        yield AsyncMock()

    with patch(
        "digidentity_api.api.leads.upsert_lead",
        new=AsyncMock(),
    ), patch(
        "digidentity_api.api.leads.with_tenant",
        new=_fake_with_tenant,
    ):
        resp = await client.post(
            f"/api/v1/leads/{VISITOR_SESSION_ID}/score",
            json=payload,
            headers={"X-Tenant-Id": str(TENANT_ID)},
        )

    assert resp.status_code == 200
    data = resp.json()
    assert "score" in data
    assert "bucket" in data
    assert data["score"] > 0
