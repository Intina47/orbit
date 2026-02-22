from __future__ import annotations

from memory_engine.config import EngineConfig
from memory_engine.engine import DecisionEngine
from memory_engine.models.event import Event


def test_compression_ratio_on_repetitive_data(tmp_path) -> None:
    engine = DecisionEngine(
        config=EngineConfig(
            sqlite_path=str(tmp_path / "bench-efficiency.db"),
            metrics_path=str(tmp_path / "bench-efficiency-metrics.json"),
            embedding_dim=32,
            persistent_confidence_prior=0.0,
            ephemeral_confidence_prior=0.0,
            compression_min_count=5,
        )
    )
    input_events = 50
    try:
        for idx in range(input_events):
            event = Event(
                timestamp=1_700_000_000 + idx * 30,
                entity_id="user_repeat",
                event_type="purchase",
                description=f"User purchased item_{idx % 5}",
                metadata={"intent": "purchase"},
            )
            processed = engine.process_input(event)
            decision = engine.make_storage_decision(processed)
            if decision.store:
                engine.store_memory(processed, decision)

        stored = engine.memory_count()
        compression_ratio = 1.0 - (stored / input_events)
        assert compression_ratio >= 0.60
    finally:
        engine.close()
