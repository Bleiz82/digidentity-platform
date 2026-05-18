"""Lead scoring API — BIBLE §6.5, §7.3.

GET  /api/v1/leads/{visitor_session_id}       → current LeadScore
POST /api/v1/leads/{visitor_session_id}/score → recompute + persist
"""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

import structlog
from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel

from digidentity_api.db.tenant_context import with_tenant
from digidentity_api.engines.qualify.loader import get_pack_path, load_scorecard
from digidentity_api.engines.qualify.persistence import get_lead, upsert_lead
from digidentity_api.engines.qualify.scorer import LeadScorer
from digidentity_api.schemas.lead import LeadScore, ScoringSignal

log = structlog.get_logger()

router = APIRouter()
_scorer = LeadScorer()


# ── Request / Response schemas ────────────────────────────────────────────────


class ScoreRequest(BaseModel):
    signals: list[ScoringSignal]
    top_persona_id: str | None = None
    pack_id: str = "real-estate-luxury"


# ── Helpers ───────────────────────────────────────────────────────────────────


def _lead_to_score(lead: object, visitor_session_id: UUID) -> LeadScore:
    from digidentity_api.db.models import Lead  # noqa: PLC0415

    assert isinstance(lead, Lead)
    raw_signals: list[dict] = lead.signals or []
    signals = []
    for s in raw_signals:
        try:
            signals.append(
                ScoringSignal(
                    signal_name=s.get("signal_name", "unknown"),
                    weight=float(s.get("weight", 0.0)),
                    emitted_at=datetime.fromisoformat(s["emitted_at"])
                    if "emitted_at" in s
                    else datetime.now(UTC),
                    source=s.get("source"),
                )
            )
        except Exception:
            pass

    return LeadScore(
        session_id=visitor_session_id,
        score=float(lead.score),
        bucket=lead.bucket,  # type: ignore[arg-type]
        signals=signals,
        last_updated=lead.updated_at if hasattr(lead, "updated_at") and lead.updated_at else datetime.now(UTC),
    )


# ── GET /leads/{visitor_session_id} ──────────────────────────────────────────


@router.get("/leads/{visitor_session_id}", response_model=LeadScore)
async def get_lead_score(
    visitor_session_id: UUID,
    x_tenant_id: UUID = Header(..., alias="X-Tenant-Id"),
) -> LeadScore:
    try:
        async with with_tenant(x_tenant_id) as session:
            lead = await get_lead(session, visitor_session_id)
            if lead is None:
                raise HTTPException(
                    status_code=404,
                    detail=f"Lead not found for visitor_session_id={visitor_session_id}",
                )
            return _lead_to_score(lead, visitor_session_id)
    except HTTPException:
        raise
    except Exception as exc:
        log.error("leads.get.error", error=str(exc))
        raise HTTPException(status_code=503, detail="Database unavailable") from exc


# ── POST /leads/{visitor_session_id}/score ────────────────────────────────────


@router.post("/leads/{visitor_session_id}/score", response_model=LeadScore)
async def compute_lead_score(
    visitor_session_id: UUID,
    body: ScoreRequest,
    x_tenant_id: UUID = Header(..., alias="X-Tenant-Id"),
) -> LeadScore:
    try:
        pack_path = get_pack_path(body.pack_id)
        scorecard = load_scorecard(pack_path)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    lead_score = _scorer.compute(
        session_id=visitor_session_id,
        signals=body.signals,
        top_persona_id=body.top_persona_id,
        scorecard=scorecard,
    )

    try:
        async with with_tenant(x_tenant_id) as session:
            await upsert_lead(session, x_tenant_id, visitor_session_id, lead_score)
    except Exception as exc:
        log.error("leads.post.persist_error", error=str(exc))
        raise HTTPException(status_code=503, detail="Database unavailable") from exc

    return lead_score
