"""LeadScore e strutture correlate — BIBLE-v3 §7.3."""

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

LeadBucket = Literal["cold", "warm", "hot"]


class ScoringSignal(BaseModel):
    """Singolo segnale di scoring emesso dall'agent loop durante la conversazione."""

    signal_name: str = Field(..., min_length=1, max_length=64)
    weight: float
    emitted_at: datetime
    source: str | None = None


class LeadScore(BaseModel):
    """Lead score incrementale — BIBLE §7.3.

    session_id corrisponde a leads.visitor_session_id nel DB.
    Soglie: cold < 30, warm 30-70, hot >= 70 (BIBLE §2.5).
    from_attributes=True abilita mapping ORM via model_validate(orm_instance).
    """

    session_id: UUID
    score: float = Field(default=0.0, ge=0.0, le=100.0)
    bucket: LeadBucket = "cold"
    signals: list[ScoringSignal] = Field(default_factory=list)
    last_updated: datetime

    model_config = ConfigDict(frozen=False, from_attributes=True)
