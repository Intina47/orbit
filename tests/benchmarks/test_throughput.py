from __future__ import annotations

import time

from memory_engine.config import EngineConfig
from memory_engine.engine import DecisionEngine
from memory_engine.models.event import Event


def test_process_1000_events_under_threshold(tmp_path) -> None:
    engine = DecisionEngine(
        config=EngineConfig(
            sqlite_path=str(tmp_path / "bench-throughput.db"),
            metrics_path=str(tmp_path / "bench-throughput-metrics.json"),
            embedding_dim=32,
            persistent_confidence_prior=0.0,
            ephemeral_confidence_prior=0.0,
            compression_min_count=10_000,
        )
    )
    events = [
        Event(
            timestamp=1_700_000_000 + idx,
            entity_id=f"user_{idx % 100}",
            event_type="interaction",
            description=f"Event {idx}",
            metadata={"intent": "interaction"},
        )
        for idx in range(1000)
    ]
    start = time.perf_counter()
    try:
        for event in events:
            processed = engine.process_input(event)
            decision = engine.make_storage_decision(processed)
            if decision.store:
                engine.store_memory(processed, decision)
        elapsed = time.perf_counter() - start
        assert elapsed < 10.0
    finally:
        engine.close()
