"""Lead persistence — upsert_lead (one-per-session). BIBLE §7.3."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from uuid import UUID

import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession

from digidentity_api.db.models import Lead
from digidentity_api.schemas.lead import LeadScore


async def upsert_lead(
    session: AsyncSession,
    tenant_id: UUID,
    visitor_session_id: UUID,
    lead_score: LeadScore,
) -> Lead:
    """Insert or update a Lead row for the given visitor_session_id.

    UniqueConstraint on visitor_session_id (one-per-session) means we SELECT first,
    then INSERT or UPDATE. Both branches happen within the caller's transaction.
    """
    result = await session.execute(
        sa.select(Lead).where(Lead.visitor_session_id == visitor_session_id)
    )
    existing = result.scalar_one_or_none()

    signals_json = [
        {
            "signal_name": s.signal_name,
            "weight": s.weight,
            "emitted_at": s.emitted_at.isoformat(),
            "source": s.source,
        }
        for s in lead_score.signals
    ]

    if existing is None:
        lead = Lead(
            tenant_id=tenant_id,
            visitor_session_id=visitor_session_id,
            score=lead_score.score,
            bucket=lead_score.bucket,
            signals=signals_json,
        )
        session.add(lead)
        await session.flush()
        return lead
    else:
        existing.score = lead_score.score
        existing.bucket = lead_score.bucket
        existing.signals = signals_json
        existing.updated_at = datetime.now(UTC)
        await session.flush()
        return existing


async def get_lead(
    session: AsyncSession,
    visitor_session_id: UUID,
) -> Lead | None:
    """Fetch a lead by visitor_session_id (within active tenant context)."""
    result = await session.execute(
        sa.select(Lead).where(Lead.visitor_session_id == visitor_session_id)
    )
    return result.scalar_one_or_none()
