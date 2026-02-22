from __future__ import annotations

from memory_engine.models.event import Event


def test_decay_half_life_is_positive(engine) -> None:
    processed = engine.process_input(
        Event(
            entity_id="task_1",
            event_type="task_execution",
            description="Completed data pipeline task",
            metadata={"intent": "task_execution"},
        )
    )
    decision = engine.make_storage_decision(processed)
    assert decision.decay_rate > 0.0
    assert decision.decay_half_life > 0.0
