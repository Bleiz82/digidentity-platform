"""Sense engine — VisitorSession persistence. BIBLE §7.1 (Remember state)."""

from __future__ import annotations

import hashlib
from datetime import UTC, datetime
from uuid import UUID

import sqlalchemy as sa
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from digidentity_api.db.models import VisitorSession
from digidentity_api.schemas.visitor import PersonaScore, SenseSignals


def hash_visitor(visitor_id: str, tenant_id: str) -> str:
    """SHA-256 of visitor_id+tenant_id, first 32 hex chars."""
    raw = f"{visitor_id}:{tenant_id}".encode()
    return hashlib.sha256(raw).hexdigest()[:32]


def _advisory_lock_key(tenant_id: str, visitor_hash: str) -> int:
    """Deterministic positive int64 for pg_advisory_xact_lock."""
    raw = f"{tenant_id}:{visitor_hash}".encode()
    digest = hashlib.sha256(raw).hexdigest()[:16]
    return int(digest, 16) % (2**63)


async def upsert_visitor_session(
    session: AsyncSession,
    tenant_id: UUID,
    visitor_id: str,
    signals: SenseSignals,
    personas: list[PersonaScore],
    confidence: float,
) -> tuple[VisitorSession, bool]:
    """Upsert a VisitorSession row for the given visitor.

    Uses a transaction-scoped advisory lock to serialize concurrent upserts
    for the same (tenant_id, visitor_hash) without requiring a UNIQUE constraint.

    Returns (session, is_new).
    """
    visitor_hash = hash_visitor(visitor_id, str(tenant_id))
    lock_key = _advisory_lock_key(str(tenant_id), visitor_hash)
    await session.execute(text(f"SELECT pg_advisory_xact_lock({lock_key})"))

    result = await session.execute(
        sa.select(VisitorSession).where(
            VisitorSession.tenant_id == tenant_id,
            VisitorSession.visitor_hash == visitor_hash,
        )
    )
    existing = result.scalar_one_or_none()

    personas_data = [p.model_dump() for p in personas]
    signals_data = signals.model_dump()

    if existing is None:
        vs = VisitorSession(
            tenant_id=tenant_id,
            visitor_hash=visitor_hash,
            inferred_personas=personas_data,
            signals=signals_data,
            confidence=confidence,
        )
        session.add(vs)
        await session.flush()
        return vs, True
    else:
        existing.inferred_personas = personas_data
        existing.signals = signals_data
        existing.confidence = confidence
        existing.updated_at = datetime.now(UTC)
        await session.flush()
        return existing, False


async def get_latest_session(
    session: AsyncSession,
    tenant_id: UUID,
    visitor_id: str,
) -> VisitorSession | None:
    """Fetch the VisitorSession for the given visitor_id within the active tenant context."""
    visitor_hash = hash_visitor(visitor_id, str(tenant_id))
    result = await session.execute(
        sa.select(VisitorSession).where(
            VisitorSession.tenant_id == tenant_id,
            VisitorSession.visitor_hash == visitor_hash,
        )
    )
    return result.scalar_one_or_none()
