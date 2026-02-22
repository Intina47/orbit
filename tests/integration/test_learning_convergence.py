from __future__ import annotations

from memory_engine.models.event import Event


def test_frequently_used_memories_persist_longer(engine) -> None:
    for idx in range(20):
        event = Event(
            timestamp=1_700_000_000 + idx * 60,
            entity_id="user_pref",
            event_type="preference_stated",
            description="User stated preference",
            metadata={"intent": "preference_stated"},
        )
        processed = engine.process_input(event)
        decision = engine.make_storage_decision(processed)
        stored = engine.store_memory(processed, decision)
        if stored is not None:
            engine.record_outcome(stored.memory_id, outcome="success")

    memory = engine.get_memory(entity_id="user_pref")[0]
    assert memory.decay_half_life_days is not None
    assert memory.decay_half_life_days > 1.0


def test_noise_events_can_be_discarded() -> None:
    # Dedicated engine instance with strict thresholds to validate filtering behavior.
    from memory_engine.config import EngineConfig
    from memory_engine.engine import DecisionEngine

    cfg = EngineConfig(
        sqlite_path=":memory:",
        persistent_confidence_prior=0.9,
        ephemeral_confidence_prior=0.8,
        embedding_dim=32,
    )
    engine = DecisionEngine(config=cfg)
    try:
        low_event = Event(
            timestamp=1,
            entity_id="rare_user",
            event_type="random_event",
            description="Random one-off thing",
            metadata={"intent": "random_event"},
        )
        decision = engine.make_storage_decision(engine.process_input(low_event))
        assert decision.store is False or decision.confidence < 0.8
    finally:
        engine.close()
