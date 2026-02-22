from __future__ import annotations

import time

from memory_engine.config import EngineConfig
from memory_engine.engine import DecisionEngine
from memory_engine.models.event import Event


def test_retrieval_latency_under_100ms(tmp_path) -> None:
    engine = DecisionEngine(
        config=EngineConfig(
            sqlite_path=str(tmp_path / "bench-latency.db"),
            metrics_path=str(tmp_path / "bench-latency-metrics.json"),
            embedding_dim=32,
            persistent_confidence_prior=0.0,
            ephemeral_confidence_prior=0.0,
            compression_min_count=10_000,
        )
    )
    for idx in range(1000):
        event = Event(
            timestamp=1_700_000_000 + idx,
            entity_id=f"user_{idx % 200}",
            event_type="interaction",
            description=f"Memory {idx}",
            metadata={"intent": "interaction"},
        )
        processed = engine.process_input(event)
        decision = engine.make_storage_decision(processed)
        if decision.store:
            engine.store_memory(processed, decision)

    try:
        start = time.perf_counter()
        _ = engine.retrieve(query="recent interaction", top_k=10)
        elapsed = time.perf_counter() - start
        assert elapsed < 0.1
    finally:
        engine.close()
