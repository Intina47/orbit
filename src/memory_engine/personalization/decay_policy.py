from __future__ import annotations

import math
from dataclasses import dataclass

from memory_engine.personalization import InferredMemoryCandidate


@dataclass(frozen=True)
class InferredDecayPlan:
    half_life_days: float
    decay_rate: float
    label: str


_CONFLICT_GUARD_HALF_LIFE = 10.0
_CONTESTED_HALF_LIFE = 14.0
_SUPERSEDING_HALF_LIFE = 30.0
_ACTIVE_HALF_LIFE = 180.0
_CRITICAL_MULTIPLIER = 2.0


def compute_inferred_decay_plan(candidate: InferredMemoryCandidate) -> InferredDecayPlan:
    metadata = candidate.metadata
    intent = str(metadata.get("intent", "")).strip().lower()
    clarification = bool(metadata.get("clarification_required"))
    fact_status = str(metadata.get("fact_status", "")).strip().lower()
    critical = bool(metadata.get("critical_fact"))

    if intent == "inferred_user_fact_conflict":
        half_life = _CONFLICT_GUARD_HALF_LIFE
        label = "conflict_guard"
    elif clarification or fact_status == "contested":
        half_life = _CONTESTED_HALF_LIFE
        label = "contested"
    elif fact_status == "superseding":
        half_life = _SUPERSEDING_HALF_LIFE
        label = "superseding"
    else:
        half_life = _ACTIVE_HALF_LIFE
        label = "confirmed"
        if critical:
            half_life *= _CRITICAL_MULTIPLIER

    half_life = max(1.0, half_life)
    decay_rate = math.log(2) / half_life
    return InferredDecayPlan(
        half_life_days=half_life,
        decay_rate=decay_rate,
        label=label,
    )
