from __future__ import annotations

from datetime import UTC, datetime
from typing import cast

from decision_engine.models import MemoryRecord, RetrievedMemory, StorageTier
from decision_engine.retrieval_ranker import RetrievalRanker
from decision_engine.semantic_encoding import SemanticEncoder
from decision_engine.storage_protocol import StorageManagerProtocol
from memory_engine.storage.retrieval import RetrievalService


def _retrieved(memory_id: str, intent: str, score: float) -> RetrievedMemory:
    now = datetime.now(UTC)
    record = MemoryRecord(
        memory_id=memory_id,
        event_id=f"event-{memory_id}",
        content=f"content-{memory_id}",
        summary=f"summary-{memory_id}",
        intent=intent,
        entities=["alice"],
        relationships=[],
        raw_embedding=[0.1, 0.2],
        semantic_embedding=[0.1, 0.2],
        semantic_key=f"key-{memory_id}",
        created_at=now,
        updated_at=now,
        retrieval_count=0,
        avg_outcome_signal=0.0,
        storage_tier=StorageTier.PERSISTENT,
        latest_importance=0.8,
    )
    return RetrievedMemory(memory=record, rank_score=score)


def _service(assistant_share: float) -> RetrievalService:
    return RetrievalService(
        storage=cast(StorageManagerProtocol, object()),
        ranker=RetrievalRanker(min_training_samples=1000),
        encoder=cast(SemanticEncoder, object()),
        assistant_response_max_share=assistant_share,
    )


def test_intent_cap_limits_assistant_share_with_mixed_candidates() -> None:
    service = _service(assistant_share=0.25)
    ranked = [
        _retrieved("assistant-1", "assistant_response", 0.99),
        _retrieved("assistant-2", "assistant_response", 0.98),
        _retrieved("assistant-3", "assistant_response", 0.97),
        _retrieved("profile-1", "preference_stated", 0.96),
        _retrieved("profile-2", "learning_progress", 0.95),
        _retrieved("profile-3", "user_question", 0.94),
        _retrieved("profile-4", "user_fact", 0.93),
    ]

    selected = service._select_with_intent_caps(ranked, top_k=5)
    assistant_count = sum(
        1 for item in selected if item.memory.intent.startswith("assistant_")
    )
    assert len(selected) == 5
    assert assistant_count <= 1


def test_intent_cap_falls_back_when_only_assistant_candidates_exist() -> None:
    service = _service(assistant_share=0.25)
    ranked = [
        _retrieved("assistant-1", "assistant_response", 0.99),
        _retrieved("assistant-2", "assistant_response", 0.98),
        _retrieved("assistant-3", "assistant_response", 0.97),
        _retrieved("assistant-4", "assistant_response", 0.96),
    ]

    selected = service._select_with_intent_caps(ranked, top_k=3)
    assert len(selected) == 3
    assert all(item.memory.intent.startswith("assistant_") for item in selected)
