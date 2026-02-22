from __future__ import annotations

from memory_engine.models.event import Event


def test_retrieval_ranking_returns_top_k(engine) -> None:
    for idx in range(10):
        event = Event(
            timestamp=1_700_000_000 + idx * 3600,
            entity_id=f"user_{idx}",
            event_type="interaction",
            description="User interacted with system",
            metadata={"intent": "interaction"},
        )
        processed = engine.process_input(event)
        decision = engine.make_storage_decision(processed)
        if decision.store:
            engine.store_memory(processed, decision)

    results = engine.retrieve("recent user interaction", top_k=3)
    assert len(results) <= 3
    if len(results) >= 2:
        assert results[0].rank_score >= results[1].rank_score
