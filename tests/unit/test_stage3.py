from __future__ import annotations

from memory_engine.models.event import Event


def test_record_outcome_updates_learning_path(engine) -> None:
    event = Event(
        entity_id="user_abc",
        event_type="interaction",
        description="User asked about deployment",
        metadata={"intent": "interaction"},
    )
    processed = engine.process_input(event)
    decision = engine.make_storage_decision(processed)
    stored = engine.store_memory(processed, decision)
    assert stored is not None

    result = engine.record_outcome(stored.memory_id, outcome="success")
    assert result["importance_loss"] is not None
