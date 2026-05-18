"""Adaptive Renderer API — POST /api/v1/rendering/decide — BIBLE-v3 §6.2.

Budget: P95 < 50ms (Sense layer, BIBLE §6.2 performance budget).
Input:  VisitorPrior + target_page + pack_id, X-Tenant-Id header.
Output: { directives, matched_rules, latency_ms }
"""

import time
from uuid import UUID

import structlog
from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel

from digidentity_api.engines.adaptive_renderer import DecisionEngine
from digidentity_api.schemas import RenderingDirective, VisitorPrior

log = structlog.get_logger()

router = APIRouter(tags=["adaptive-renderer"])

_engine = DecisionEngine()


class DecideRequest(BaseModel):
    prior: VisitorPrior
    target_page: str
    pack_id: str


class DecideResponse(BaseModel):
    directives: list[RenderingDirective]
    matched_rules: list[str]
    latency_ms: float


@router.post("/rendering/decide", response_model=DecideResponse)
async def decide(
    body: DecideRequest,
    x_tenant_id: UUID = Header(..., alias="X-Tenant-Id"),
) -> DecideResponse:
    """Evaluate morph rules for the given VisitorPrior and return RenderingDirectives."""
    t0 = time.perf_counter()
    try:
        directives, matched_rules = _engine.decide(
            prior=body.prior,
            target_page=body.target_page,
            pack_id=body.pack_id,
        )
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    latency_ms = (time.perf_counter() - t0) * 1000
    log.info(
        "rendering.decide",
        tenant_id=str(x_tenant_id),
        pack_id=body.pack_id,
        target_page=body.target_page,
        matched=len(matched_rules),
        directives=len(directives),
        latency_ms=round(latency_ms, 2),
    )
    return DecideResponse(
        directives=directives,
        matched_rules=matched_rules,
        latency_ms=round(latency_ms, 3),
    )
