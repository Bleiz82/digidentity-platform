"""
Unit test STEP 8b: Pydantic schemas v3 — VisitorPrior, RenderingDirective, LeadScore.
Nessun DB, nessun container. Test puri di validazione.
"""

from datetime import datetime, timezone
from uuid import UUID, uuid4

import pytest
from pydantic import ValidationError

from digidentity_api.schemas import (
    LeadScore,
    PersonaScore,
    RenderingDirective,
    ScoringSignal,
    SenseSignals,
    VisitorPrior,
)

_NOW = datetime.now(timezone.utc)
_UUID = uuid4()


# ── test 1: PersonaScore.score range ─────────────────────────────────────────


def test_persona_score_validates_score_range():
    assert PersonaScore(persona_id="buyer", score=0.0).score == 0.0
    assert PersonaScore(persona_id="buyer", score=0.5).score == 0.5
    assert PersonaScore(persona_id="buyer", score=1.0).score == 1.0

    with pytest.raises(ValidationError):
        PersonaScore(persona_id="buyer", score=-0.1)

    with pytest.raises(ValidationError):
        PersonaScore(persona_id="buyer", score=1.1)


# ── test 2: SenseSignals defaults ────────────────────────────────────────────


def test_sense_signals_defaults():
    s = SenseSignals()
    assert s.device_class == "unknown"
    assert s.utm == {}
    assert s.is_returning is False
    assert s.referrer is None
    assert s.geo_city is None
    assert s.language is None
    assert s.local_time_bucket is None
    assert s.prior_session_id is None


# ── test 3: VisitorPrior round-trip ──────────────────────────────────────────


def test_visitor_prior_construction():
    vp = VisitorPrior(
        session_id=_UUID,
        tenant_id=_UUID,
        visitor_hash="abcdef1234567890",
        inferred_personas=[PersonaScore(persona_id="luxury-buyer", score=0.8)],
        signals=SenseSignals(
            device_class="desktop",
            utm={"source": "google", "medium": "cpc"},
            is_returning=True,
        ),
        confidence=0.75,
        created_at=_NOW,
        updated_at=_NOW,
    )

    dumped = vp.model_dump()
    restored = VisitorPrior.model_validate(dumped)

    assert restored.session_id == vp.session_id
    assert restored.confidence == vp.confidence
    assert restored.inferred_personas[0].persona_id == "luxury-buyer"
    assert restored.signals.utm["source"] == "google"


# ── test 4: VisitorPrior from_attributes (ORM-like dict) ─────────────────────


def test_visitor_prior_from_orm_attributes():
    orm_like = {
        "session_id": _UUID,
        "tenant_id": _UUID,
        "visitor_hash": "hashvalue12345678",
        "inferred_personas": [{"persona_id": "first-time", "score": 0.6}],
        "signals": {"device_class": "mobile", "utm": {}, "is_returning": False},
        "confidence": 0.6,
        "created_at": _NOW,
        "updated_at": _NOW,
    }
    vp = VisitorPrior.model_validate(orm_like)
    assert vp.visitor_hash == "hashvalue12345678"
    assert vp.signals.device_class == "mobile"
    assert vp.inferred_personas[0].score == 0.6


# ── test 5: RenderingDirective type literal ───────────────────────────────────


def test_rendering_directive_type_literal():
    rd = RenderingDirective(
        type="morph_section",
        target="#hero",
        reason="luxury buyer prior detected",
    )
    assert rd.type == "morph_section"

    with pytest.raises(ValidationError):
        RenderingDirective(
            type="invalid_type",  # type: ignore[arg-type]
            target="#hero",
            reason="test",
        )


# ── test 6: RenderingDirective priority bounds ───────────────────────────────


def test_rendering_directive_priority_bounds():
    rd = RenderingDirective(
        type="highlight", target="entity-123", priority=500, reason="test"
    )
    assert rd.priority == 500

    with pytest.raises(ValidationError):
        RenderingDirective(type="show", target="x", priority=-1, reason="test")

    with pytest.raises(ValidationError):
        RenderingDirective(type="show", target="x", priority=1001, reason="test")


# ── test 7: LeadScore bucket enum ────────────────────────────────────────────


def test_lead_score_bucket_enum():
    ls = LeadScore(session_id=_UUID, bucket="hot", last_updated=_NOW)
    assert ls.bucket == "hot"

    with pytest.raises(ValidationError):
        LeadScore(
            session_id=_UUID,
            bucket="HOT",  # type: ignore[arg-type]
            last_updated=_NOW,
        )

    with pytest.raises(ValidationError):
        LeadScore(
            session_id=_UUID,
            bucket="legendary",  # type: ignore[arg-type]
            last_updated=_NOW,
        )


# ── test 8: LeadScore score range ────────────────────────────────────────────


def test_lead_score_range():
    ls = LeadScore(session_id=_UUID, score=50.0, last_updated=_NOW)
    assert ls.score == 50.0

    with pytest.raises(ValidationError):
        LeadScore(session_id=_UUID, score=-1.0, last_updated=_NOW)

    with pytest.raises(ValidationError):
        LeadScore(session_id=_UUID, score=101.0, last_updated=_NOW)
