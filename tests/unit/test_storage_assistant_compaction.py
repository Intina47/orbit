from __future__ import annotations

from datetime import UTC, datetime

from decision_engine.models import (
    EncodedEvent,
    RawEvent,
    SemanticUnderstanding,
    StorageDecision,
    StorageTier,
)
from decision_engine.storage_manager import SQLiteStorageManager
from decision_engine.storage_sqlalchemy import SQLAlchemyStorageManager


def _encoded_event(content: str, *, intent: str = "assistant_response") -> EncodedEvent:
    return EncodedEvent(
        event=RawEvent(
            event_id="event-1",
            timestamp=datetime.now(UTC),
            content=content,
            context={"intent": intent},
        ),
        raw_embedding=[0.1, 0.2, 0.3],
        semantic_embedding=[0.1, 0.2, 0.3],
        understanding=SemanticUnderstanding(
            summary="assistant summary",
            entities=["alice"],
            relationships=[],
            intent=intent,
        ),
        semantic_key="semantic-key-1",
    )


def _decision() -> StorageDecision:
    return StorageDecision(
        should_store=True,
        tier=StorageTier.PERSISTENT,
        confidence=0.9,
        rationale="test",
        trace={},
    )


def test_sqlite_storage_compacts_repetitive_assistant_content(tmp_path) -> None:
    manager = SQLiteStorageManager(
        str(tmp_path / "assistant_compact.db"),
        assistant_max_content_chars=350,
    )
    try:
        long_repetitive = (
            "This answer is intentionally repetitive. " * 80
            + "Use a for loop for predictable repetition."
        )
        stored = manager.store(_encoded_event(long_repetitive), _decision())
        assert len(stored.content) < len(long_repetitive)
        assert "assistant content compacted" in stored.content
        assert len(stored.content) <= 350
    finally:
        manager.close()


def test_sqlalchemy_storage_compacts_repetitive_assistant_content(tmp_path) -> None:
    manager = SQLAlchemyStorageManager(
        f"sqlite:///{tmp_path / 'assistant_compact_sa.db'}",
        assistant_max_content_chars=350,
    )
    try:
        long_repetitive = (
            "Generic assistant wording that repeats heavily. " * 70
            + "Add one concrete fix at the end."
        )
        stored = manager.store(_encoded_event(long_repetitive), _decision())
        assert len(stored.content) < len(long_repetitive)
        assert "assistant content compacted" in stored.content
        assert len(stored.content) <= 350
    finally:
        manager.close()
