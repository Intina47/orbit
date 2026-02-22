from __future__ import annotations

from pathlib import Path

import pytest

from memory_engine.config import EngineConfig
from orbit.models import FeedbackRequest, IngestRequest, RetrieveRequest
from orbit_api.config import ApiConfig
from orbit_api.service import OrbitApiService, RateLimitExceededError


def _service(tmp_path: Path) -> OrbitApiService:
    db_path = tmp_path / "service.db"
    api_config = ApiConfig(
        database_url=f"sqlite:///{db_path}",
        sqlite_fallback_path=str(db_path),
        free_events_per_day=2,
        free_queries_per_day=2,
    )
    engine_config = EngineConfig(
        sqlite_path=str(db_path),
        database_url=f"sqlite:///{db_path}",
        embedding_dim=16,
        persistent_confidence_prior=0.0,
        ephemeral_confidence_prior=0.0,
        ranker_min_training_samples=2,
        ranker_training_batch_size=2,
    )
    return OrbitApiService(api_config=api_config, engine_config=engine_config)


def test_service_quota_enforcement(tmp_path: Path) -> None:
    service = _service(tmp_path)
    try:
        snapshot = service.consume_event_quota("acct_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx")
        assert snapshot.limit == 2
        assert snapshot.remaining == 1
        service.consume_event_quota("acct_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx")
        with pytest.raises(RateLimitExceededError):
            service.consume_event_quota("acct_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx")
    finally:
        service.close()


def test_service_ingest_retrieve_feedback_and_status(tmp_path: Path) -> None:
    service = _service(tmp_path)
    api_key = "acct_yyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyy"
    try:
        ingest = service.ingest(
            IngestRequest(
                content="Alice prefers short explanations",
                event_type="user_question",
                entity_id="alice",
            )
        )
        assert ingest.stored is True

        retrieve = service.retrieve(
            RetrieveRequest(query="What should I know about Alice?", limit=5)
        )
        assert retrieve.total_candidates >= 1
        assert retrieve.memories

        feedback = service.feedback(
            FeedbackRequest(memory_id=ingest.memory_id, helpful=True, outcome_value=1.0)
        )
        assert feedback.recorded is True

        status = service.status(api_key)
        assert status.connected is True
        assert status.account_usage.storage_usage_mb >= 0.0

        paged = service.list_memories(limit=10, cursor=None)
        assert paged.data
        assert paged.has_more in {True, False}

        metrics = service.metrics_text()
        assert "orbit_ingest_requests_total" in metrics
    finally:
        service.close()


def test_service_feedback_missing_memory(tmp_path: Path) -> None:
    service = _service(tmp_path)
    try:
        with pytest.raises(KeyError):
            service.feedback(FeedbackRequest(memory_id="missing", helpful=False))
    finally:
        service.close()
