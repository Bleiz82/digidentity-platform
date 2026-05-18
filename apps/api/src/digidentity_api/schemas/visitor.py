"""VisitorPrior e strutture correlate — BIBLE-v3 §7.1."""

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class PersonaScore(BaseModel):
    """Probabilità assegnata a una persona inferita dal Sense."""

    persona_id: str = Field(..., min_length=1, max_length=64)
    score: float = Field(..., ge=0.0, le=1.0)


class SenseSignals(BaseModel):
    """Segnali grezzi raccolti dal Sense durante la request HTTP — BIBLE §2.1."""

    referrer: str | None = None
    utm: dict[str, str] = Field(default_factory=dict)
    geo_city: str | None = None
    device_class: Literal["desktop", "mobile", "tablet", "bot", "unknown"] = "unknown"
    language: str | None = None
    local_time_bucket: Literal["morning", "afternoon", "evening", "night"] | None = None
    is_returning: bool = False
    prior_session_id: UUID | None = None


class VisitorPrior(BaseModel):
    """Output del Sense, persistito in visitor_sessions — BIBLE §7.1.

    session_id corrisponde a visitor_sessions.id nel DB.
    from_attributes=True abilita mapping ORM via model_validate(orm_instance).
    """

    session_id: UUID
    tenant_id: UUID
    visitor_hash: str = Field(..., min_length=8, max_length=64)
    inferred_personas: list[PersonaScore] = Field(default_factory=list)
    signals: SenseSignals
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(frozen=False, from_attributes=True)
