from __future__ import annotations

from memory_engine.models.event import Event


def test_compression_triggers_on_repetitive_cluster(engine) -> None:
    for idx in range(5):
        event = Event(
            timestamp=1_700_000_000 + idx * 60,
            entity_id="user_123",
            event_type="purchase",
            description=f"User bought item_{idx}",
            metadata={"intent": "purchase"},
        )
        processed = engine.process_input(event)
        decision = engine.make_storage_decision(processed)
        if decision.store:
            engine.store_memory(processed, decision)

    memories = engine.get_memory(entity_id="user_123")
    assert len(memories) == 1
    assert memories[0].is_compressed is True
    assert memories[0].original_count >= 5
