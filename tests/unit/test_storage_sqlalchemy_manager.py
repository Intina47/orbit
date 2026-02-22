from __future__ import annotations

from pathlib import Path

import numpy as np

from decision_engine.models import (
    EncodedEvent,
    RawEvent,
    SemanticUnderstanding,
    StorageDecision,
    StorageTier,
)
from decision_engine.storage_sqlalchemy import SQLAlchemyStorageManager


def test_sqlalchemy_storage_manager_with_sqlite_url(tmp_path: Path) -> None:
    manager = SQLAlchemyStorageManager(f"sqlite:///{tmp_path / 'sa-manager.db'}")
    try:
        encoded = EncodedEvent(
            event=RawEvent(content="Event content", context={"intent": "interaction"}),
            raw_embedding=[1.0, 0.0],
            semantic_embedding=[1.0, 0.0],
            understanding=SemanticUnderstanding(
                summary="Event summary",
                intent="interaction",
                entities=["user_1"],
                relationships=["user_1->topic_python"],
            ),
            semantic_key="semantic-key-1",
        )
        decision = StorageDecision(
            should_store=True,
            tier=StorageTier.PERSISTENT,
            confidence=0.9,
            rationale="test store",
            trace={},
        )
        stored = manager.store(encoded, decision)
        assert stored.memory_id
        assert manager.count_memories() == 1

        fetched = manager.fetch_by_ids([stored.memory_id])
        assert len(fetched) == 1

        candidates = manager.search_candidates(
            np.asarray([1.0, 0.0], dtype=np.float32), 5
        )
        assert candidates

        manager.update_retrieval(stored.memory_id)
        manager.update_outcome(stored.memory_id, 1.0)
        entity_intent = manager.fetch_by_entity_and_intent("user_1", "interaction")
        assert entity_intent

        size_mb = manager.storage_usage_mb()
        assert size_mb >= 0.0

        manager.delete_memories([stored.memory_id])
        assert manager.count_memories() == 0
    finally:
        manager.close()
