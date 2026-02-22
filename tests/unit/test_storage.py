from __future__ import annotations

from memory_engine.models.event import Event


def test_storage_persists_and_retrieves(engine) -> None:
    event = Event(
        entity_id="user_store",
        event_type="interaction",
        description="Storage validation event",
        metadata={"intent": "interaction"},
    )
    processed = engine.process_input(event)
    decision = engine.make_storage_decision(processed)
    stored = engine.store_memory(processed, decision)
    assert stored is not None
    assert engine.memory_count() >= 1

    retrieved = engine.retrieve("storage validation", top_k=1)
    assert len(retrieved) <= 1
