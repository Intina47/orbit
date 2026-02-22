from __future__ import annotations

from datetime import UTC, datetime, timedelta

import numpy as np
import torch

from decision_engine.models import MemoryRecord, StorageTier
from decision_engine.retrieval_ranker import RetrievalRanker


def _memory(
    memory_id: str,
    semantic: list[float],
    outcome: float,
    *,
    content: str | None = None,
    summary: str | None = None,
    intent: str = "test",
    importance: float = 0.7,
) -> MemoryRecord:
    now = datetime.now(UTC)
    resolved_content = content or f"content-{memory_id}"
    resolved_summary = summary or f"summary-{memory_id}"
    return MemoryRecord(
        memory_id=memory_id,
        event_id=f"event-{memory_id}",
        content=resolved_content,
        summary=resolved_summary,
        intent=intent,
        entities=[],
        relationships=[],
        raw_embedding=semantic,
        semantic_embedding=semantic,
        semantic_key=f"key-{memory_id}",
        created_at=now - timedelta(days=1),
        updated_at=now,
        retrieval_count=1,
        avg_outcome_signal=outcome,
        storage_tier=StorageTier.PERSISTENT,
        latest_importance=importance,
    )


def test_ranker_trains_on_feedback_buffer() -> None:
    torch.manual_seed(0)
    query = np.array([1.0, 0.0, 0.0], dtype=np.float32)
    memories = [
        _memory("m1", [0.9, 0.1, 0.0], outcome=0.1),
        _memory("m2", [0.8, 0.2, 0.0], outcome=0.9),
    ]
    ranker = RetrievalRanker(
        learning_rate=1e-2, min_training_samples=2, training_batch_size=2
    )

    now = datetime.now(UTC)
    loss = ranker.learn_from_feedback(
        query_embedding=query,
        candidates=memories,
        helpful_memory_ids={"m2"},
        now=now,
    )

    assert loss is not None
    assert loss >= 0.0
    assert ranker.is_trained

    ranked = ranker.rank(query_embedding=query, candidates=memories, now=now)
    assert len(ranked) == 2


def test_ranker_downweights_long_assistant_responses_pre_warmup() -> None:
    query = np.array([1.0, 0.0, 0.0], dtype=np.float32)
    concise_profile = _memory(
        "profile",
        [0.84, 0.16, 0.0],
        outcome=0.6,
        summary="Alice is a beginner and prefers short examples.",
        intent="preference_stated",
        importance=0.92,
    )
    long_assistant = _memory(
        "assistant",
        [0.9, 0.1, 0.0],
        outcome=0.1,
        content="assistant response " * 900,
        summary="assistant response " * 120,
        intent="assistant_response",
        importance=0.5,
    )
    ranker = RetrievalRanker(min_training_samples=100, training_batch_size=64)
    ranked = ranker.rank(
        query_embedding=query,
        candidates=[long_assistant, concise_profile],
        now=datetime.now(UTC),
    )

    assert ranked[0].memory.memory_id == "profile"
