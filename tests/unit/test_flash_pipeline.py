from __future__ import annotations

import time
from datetime import UTC, datetime

from memory_engine.config import EngineConfig
from memory_engine.engine import DecisionEngine
from memory_engine.models.event import Event


def _ingest(engine: DecisionEngine, *, content: str, entity_id: str = "alice") -> None:
    event = Event(
        timestamp=datetime.now(UTC),
        entity_id=entity_id,
        event_type="user_question",
        description=content,
        metadata={},
    )
    processed = engine.process_input(event)
    decision = engine.make_storage_decision(processed)
    stored = engine.store_memory(processed, decision)
    assert stored is not None


def test_async_flash_pipeline_enqueues_and_runs(tmp_path) -> None:
    config = EngineConfig(
        sqlite_path=str(tmp_path / "flash.db"),
        metrics_path=str(tmp_path / "metrics.json"),
        embedding_dim=32,
        persistent_confidence_prior=0.0,
        ephemeral_confidence_prior=0.0,
        ranker_min_training_samples=2,
        ranker_training_batch_size=2,
        flash_pipeline_mode="async",
        flash_pipeline_workers=1,
        flash_pipeline_queue_size=32,
        flash_pipeline_maintenance_interval=1,
        personalization_repeat_threshold=2,
    )
    engine = DecisionEngine(config=config)
    try:
        _ingest(engine, content="hello loop help", entity_id="alice")
        _ingest(engine, content="hello loop help", entity_id="alice")
        deadline = time.monotonic() + 2.0
        inferred_found = False
        while time.monotonic() < deadline:
            inferred_found = any(
                item.intent == "inferred_learning_pattern"
                for item in engine.get_memory(entity_id="alice")
            )
            if inferred_found:
                break
            time.sleep(0.05)
        assert inferred_found is True
        assert engine._metrics.get("flash_pipeline_enqueued", 0.0) >= 2.0
        assert engine._metrics.get("flash_pipeline_runs", 0.0) >= 1.0
        assert engine._metrics.get("flash_maintenance_runs", 0.0) >= 1.0
    finally:
        engine.close()
