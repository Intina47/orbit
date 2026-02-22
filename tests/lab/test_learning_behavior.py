from __future__ import annotations

from memory_engine.models.event import Event


def test_learning_loop_updates_rank_and_importance(engine) -> None:
    for idx in range(6):
        event = Event(
            timestamp=1_700_000_000 + idx,
            entity_id="lab_user",
            event_type="incident_resolution",
            description=f"Resolved production issue #{idx}",
            metadata={"intent": "incident_resolution"},
        )
        processed = engine.process_input(event)
        decision = engine.make_storage_decision(processed)
        if decision.store:
            engine.store_memory(processed, decision)

    retrieved = engine.retrieve("production issue", top_k=3)
    assert retrieved
    top_memory_id = retrieved[0].memory.memory_id
    result = engine.record_feedback(
        query="production issue",
        ranked_memory_ids=[item.memory.memory_id for item in retrieved],
        helpful_memory_ids=[top_memory_id],
        outcome_signal=1.0,
    )
    assert result["importance_loss"] is not None
