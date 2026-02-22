from __future__ import annotations

from memory_engine.models.event import Event


def test_event_flows_through_all_stages(engine) -> None:
    event = Event(
        timestamp=1_700_000_000,
        entity_id="user_123",
        event_type="purchase",
        description="User bought a coffee",
        metadata={"intent": "purchase"},
    )
    processed = engine.process_input(event)
    assert processed.entity_references[0] == "user_123"

    decision = engine.make_storage_decision(processed)
    assert hasattr(decision, "store")
    assert hasattr(decision, "decay_half_life")

    if decision.store:
        engine.store_memory(processed, decision)
        assert engine.memory_count() > 0
