"""Visitor Sessions API — POST upsert / GET by visitor_id. BIBLE §7.1 (Remember).

POST /api/v1/visitor-sessions/upsert    → upsert, return {session_id, is_new, last_seen_at}
GET  /api/v1/visitor-sessions/{visitor_id} → VisitorPrior consolidato o 404
"""

from __future__ import annotations

from uuid import UUID

import structlog
from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel

from digidentity_api.db.tenant_context import with_tenant
from digidentity_api.engines.sense.persistence import get_latest_session, upsert_visitor_session
from digidentity_api.schemas.visitor import PersonaScore, SenseSignals, VisitorPrior

log = structlog.get_logger()

router = APIRouter(tags=["visitor-sessions"])


# ── Request / Response ────────────────────────────────────────────────────────


class UpsertRequest(BaseModel):
    visitor_id: UUID
    signals: SenseSignals
    inferred_personas: list[PersonaScore]
    confidence: float


class UpsertResponse(BaseModel):
    session_id: UUID
    is_new: bool
    last_seen_at: str  # ISO-8601


# ── POST /visitor-sessions/upsert ─────────────────────────────────────────────


@router.post("/visitor-sessions/upsert", response_model=UpsertResponse)
async def upsert_session(
    body: UpsertRequest,
    x_tenant_id: UUID = Header(..., alias="X-Tenant-Id"),
) -> UpsertResponse:
    try:
        async with with_tenant(x_tenant_id) as session:
            vs, is_new = await upsert_visitor_session(
                session,
                tenant_id=x_tenant_id,
                visitor_id=str(body.visitor_id),
                signals=body.signals,
                personas=body.inferred_personas,
                confidence=body.confidence,
            )
        log.info(
            "visitor_sessions.upsert",
            tenant_id=str(x_tenant_id),
            session_id=str(vs.id),
            is_new=is_new,
        )
        return UpsertResponse(
            session_id=vs.id,
            is_new=is_new,
            last_seen_at=vs.updated_at.isoformat(),
        )
    except Exception as exc:
        log.error("visitor_sessions.upsert.error", error=str(exc))
        raise HTTPException(status_code=503, detail="Database unavailable") from exc


# ── GET /visitor-sessions/{visitor_id} ────────────────────────────────────────


@router.get("/visitor-sessions/{visitor_id}", response_model=VisitorPrior)
async def get_session(
    visitor_id: UUID,
    x_tenant_id: UUID = Header(..., alias="X-Tenant-Id"),
) -> VisitorPrior:
    try:
        async with with_tenant(x_tenant_id) as session:
            vs = await get_latest_session(session, x_tenant_id, str(visitor_id))
    except Exception as exc:
        log.error("visitor_sessions.get.error", error=str(exc))
        raise HTTPException(status_code=503, detail="Database unavailable") from exc

    if vs is None:
        raise HTTPException(
            status_code=404,
            detail=f"No session found for visitor_id={visitor_id} tenant={x_tenant_id}",
        )

    # VisitorPrior.session_id maps to VisitorSession.id (different field name).
    # Construct manually; Pydantic v2 coerces signals dict → SenseSignals and
    # inferred_personas list[dict] → list[PersonaScore].
    from digidentity_api.schemas.visitor import SenseSignals  # noqa: PLC0415

    return VisitorPrior(
        session_id=vs.id,
        tenant_id=vs.tenant_id,
        visitor_hash=vs.visitor_hash,
        inferred_personas=vs.inferred_personas or [],
        signals=SenseSignals.model_validate(vs.signals),
        confidence=vs.confidence,
        created_at=vs.created_at,
        updated_at=vs.updated_at,
    )
