from datetime import UTC, datetime
from decimal import Decimal
from uuid import UUID

import uuid_utils
from pgvector.sqlalchemy import HALFVEC
from sqlalchemy import Boolean, DateTime, Enum, Float, Index, Integer, Numeric, SmallInteger, String, Text, UniqueConstraint, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from digidentity_api.db.base import Base


def _uuid7() -> UUID:
    # uuid_utils.uuid7() restituisce uuid_utils.UUID, non uuid.UUID standard.
    # Convertiamo esplicitamente per compatibilità con SQLAlchemy e confronti di tipo.
    return UUID(str(uuid_utils.uuid7()))


def _now() -> datetime:
    return datetime.now(UTC)


class Tenant(Base):
    __tablename__ = "tenants"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=_uuid7)
    slug: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_now
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_now, onupdate=_now
    )


class Session(Base):
    __tablename__ = "sessions"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=_uuid7)
    tenant_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False, index=True)
    visitor_id: Mapped[UUID | None] = mapped_column(PG_UUID(as_uuid=True), nullable=True)
    channel: Mapped[str] = mapped_column(String(32), nullable=False, server_default="web")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_now
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_now, onupdate=_now
    )


class UsageLog(Base):
    __tablename__ = "usage_logs"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=_uuid7)
    tenant_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False, index=True)
    conversation_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    request_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False, unique=True)
    provider: Mapped[str] = mapped_column(String(32), nullable=False)
    model: Mapped[str] = mapped_column(String(64), nullable=False)
    prompt_tokens: Mapped[int] = mapped_column(Integer, nullable=False)
    completion_tokens: Mapped[int] = mapped_column(Integer, nullable=False)
    cached_tokens: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    cost_usd: Mapped[Decimal] = mapped_column(Numeric(10, 6), nullable=False)
    latency_ms: Mapped[int] = mapped_column(Integer, nullable=False)
    ts: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=text("NOW()"),
    )
    fallback_used: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=text("false")
    )


class Entity(Base):
    __tablename__ = "entities"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=_uuid7)
    tenant_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False, index=True)
    pack_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    entity_type: Mapped[str] = mapped_column(String(64), nullable=False)
    payload: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    content_emb: Mapped[list[float] | None] = mapped_column(HALFVEC(3072), nullable=True)
    lifestyle_emb: Mapped[list[float] | None] = mapped_column(HALFVEC(3072), nullable=True)
    features_emb: Mapped[list[float] | None] = mapped_column(HALFVEC(3072), nullable=True)
    embedding_version: Mapped[str] = mapped_column(
        String(64), nullable=False, server_default="text-embedding-3-large-halfvec-v1"
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_now
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_now, onupdate=_now
    )


# ── BIBLE v3 Phase 2 models (migration 003) ───────────────────────────────────


class VisitorSession(Base):
    """Persistenza di VisitorPrior — BIBLE §7.1."""

    __tablename__ = "visitor_sessions"
    __table_args__ = (
        Index("ix_visitor_sessions_tenant_hash", "tenant_id", "visitor_hash"),
    )

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=_uuid7)
    tenant_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False, index=True)
    visitor_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    # list[PersonaScore] serializzata come JSONB
    inferred_personas: Mapped[dict] = mapped_column(JSONB, nullable=False, default=list)
    # SenseSignals: referrer, utm, geo_city, device_class, language, ...
    signals: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    confidence: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_now
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_now, onupdate=_now
    )


class Conversation(Base):
    """Conversazione persistita con idempotency_key — BIBLE §6.1, §6.4."""

    __tablename__ = "conversations"
    __table_args__ = (
        # partial unique index: NULL idempotency_key non partecipa al vincolo
        Index(
            "ix_conversations_tenant_idempotency",
            "tenant_id",
            "idempotency_key",
            unique=True,
            postgresql_where=text("idempotency_key IS NOT NULL"),
        ),
    )

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=_uuid7)
    tenant_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False, index=True)
    visitor_session_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), nullable=True
    )
    idempotency_key: Mapped[str | None] = mapped_column(String(64), nullable=True)
    # enum: 'active' | 'completed' | 'abandoned'
    status: Mapped[str] = mapped_column(
        Enum("active", "completed", "abandoned", name="conversation_status", create_type=False),
        nullable=False,
        default="active",
    )
    # enum: 'web' | 'voice'  (BIBLE §6.3)
    channel: Mapped[str] = mapped_column(
        Enum("web", "voice", name="conversation_channel", create_type=False),
        nullable=False,
        default="web",
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_now
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_now, onupdate=_now
    )


class ConversationTurn(Base):
    """Turno di conversazione con campi v3 — BIBLE §7.4."""

    __tablename__ = "conversation_turns"
    __table_args__ = (
        UniqueConstraint("conversation_id", "turn_index", name="uq_conversation_turns_idx"),
    )

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=_uuid7)
    conversation_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), nullable=False, index=True
    )
    # tenant_id denormalizzato per RLS — nessuna FK, enforced via conversation chain
    tenant_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False, index=True)
    turn_index: Mapped[int] = mapped_column(Integer, nullable=False)
    # enum: 'user' | 'assistant' | 'tool' | 'system'
    role: Mapped[str] = mapped_column(
        Enum("user", "assistant", "tool", "system", name="turn_role", create_type=False),
        nullable=False,
    )
    content: Mapped[str | None] = mapped_column(Text, nullable=True)
    user_intent: Mapped[str | None] = mapped_column(String(32), nullable=True)
    # 1-5, popolato da annotation umana settimanale (BIBLE §6.7)
    quality_score: Mapped[int | None] = mapped_column(SmallInteger, nullable=True)
    tool_calls_json: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    tool_call_success_overall: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    rendering_directives_emitted: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_now
    )


class Lead(Base):
    """Lead con LeadScore incrementale — BIBLE §7.3."""

    __tablename__ = "leads"
    __table_args__ = (
        UniqueConstraint("visitor_session_id", name="uq_leads_visitor_session"),
    )

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=_uuid7)
    tenant_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False, index=True)
    visitor_session_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    score: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    # enum: 'cold' | 'warm' | 'hot'  soglie: <30, 30-70, >=70
    bucket: Mapped[str] = mapped_column(
        Enum("cold", "warm", "hot", name="lead_bucket", create_type=False),
        nullable=False,
        default="cold",
    )
    # list[ScoringSignal] storico segnali emessi dall'agente
    signals: Mapped[dict] = mapped_column(JSONB, nullable=False, default=list)
    handoff_triggered_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    handoff_briefing_uri: Mapped[str | None] = mapped_column(String(500), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_now
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_now, onupdate=_now
    )
