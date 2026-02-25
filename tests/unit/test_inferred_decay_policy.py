from __future__ import annotations

import math

from memory_engine.personalization import InferredMemoryCandidate
from memory_engine.personalization.decay_policy import compute_inferred_decay_plan


def _candidate(metadata: dict[str, object]) -> InferredMemoryCandidate:
    return InferredMemoryCandidate(
        entity_id="alice",
        event_type=str(metadata.get("intent", "inferred_user_fact")),
        content="Fact content",
        summary="Fact summary",
        confidence=0.85,
        metadata=metadata,
    )


def test_conflict_guard_uses_short_half_life() -> None:
    candidate = _candidate({"intent": "inferred_user_fact_conflict"})
    plan = compute_inferred_decay_plan(candidate)
    assert plan.label == "conflict_guard"
    assert math.isclose(plan.half_life_days, 10.0)
    assert math.isclose(plan.decay_rate, math.log(2) / 10.0)


def test_contested_fact_decays_faster() -> None:
    candidate = _candidate(
        {"intent": "inferred_user_fact", "clarification_required": True, "fact_status": "contested"}
    )
    plan = compute_inferred_decay_plan(candidate)
    assert plan.label == "contested"
    assert math.isclose(plan.half_life_days, 14.0)


def test_confirmed_critical_fact_boosts_half_life() -> None:
    candidate = _candidate({"critical_fact": True})
    plan = compute_inferred_decay_plan(candidate)
    assert plan.label == "confirmed"
    assert math.isclose(plan.half_life_days, 360.0)


def test_superseding_fact_uses_medium_halflife() -> None:
    candidate = _candidate({"fact_status": "superseding"})
    plan = compute_inferred_decay_plan(candidate)
    assert plan.label == "superseding"
    assert math.isclose(plan.half_life_days, 30.0)
