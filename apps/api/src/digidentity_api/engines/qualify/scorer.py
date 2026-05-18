"""LeadScorer — computes LeadScore from signals + persona + scorecard.

Pure function: no I/O, no DB. BIBLE §6.5.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from digidentity_api.schemas.lead import LeadBucket, LeadScore, ScoringSignal


def _assign_bucket(score: float) -> LeadBucket:
    if score >= 70:
        return "hot"
    if score >= 30:
        return "warm"
    return "cold"


class LeadScorer:
    def compute(
        self,
        session_id: UUID,
        signals: list[ScoringSignal],
        top_persona_id: str | None,
        scorecard: dict[str, Any],
    ) -> LeadScore:
        """Compute a LeadScore from signals + scorecard.

        Algorithm:
          1. For each ScoringSignal, look up matching scorecard entry by id == signal_name.
             Contribution = signal.weight * scorecard_signal.max_score, capped at max_score.
             Unknown signals (not in scorecard) contribute signal.weight directly, uncapped.
          2. Sum contributions, cap total at 100.
          3. Apply persona modifier (flat points), clamp [0, 100].
          4. Assign bucket.
        """
        # Index scorecard signals by id
        sig_index: dict[str, dict[str, Any]] = {
            s["id"]: s for s in scorecard.get("signals", [])
        }

        total = 0.0
        for sig in signals:
            sc_sig = sig_index.get(sig.signal_name)
            if sc_sig is not None:
                # weight acts as a multiplier [0,1] → scale by max_score
                contribution = sig.weight * sc_sig["max_score"]
                contribution = min(contribution, sc_sig["max_score"])
            else:
                # Unknown signal: use raw weight as points
                contribution = sig.weight
            total += contribution

        # Cap total before persona modifier
        total = min(total, 100.0)

        # Persona modifier
        modifiers: dict[str, float] = scorecard.get("persona_modifiers", {})
        if top_persona_id and top_persona_id in modifiers:
            total += modifiers[top_persona_id]

        # Clamp final score
        total = max(0.0, min(100.0, total))
        total = round(total, 2)

        bucket = _assign_bucket(total)

        return LeadScore(
            session_id=session_id,
            score=total,
            bucket=bucket,
            signals=signals,
            last_updated=datetime.now(UTC),
        )
