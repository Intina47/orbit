from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import httpx

from orbit import Config, MemoryEngine


def test_memory_engine_core_methods_with_mock_transport() -> None:
    now = datetime.now(UTC).isoformat()

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/v1/ingest":
            return httpx.Response(
                status_code=201,
                json={
                    "memory_id": "mem_1",
                    "stored": True,
                    "importance_score": 0.9,
                    "decision_reason": "high relevance",
                    "encoded_at": now,
                    "latency_ms": 12.0,
                },
            )
        if request.url.path == "/v1/retrieve":
            return httpx.Response(
                status_code=200,
                json={
                    "memories": [
                        {
                            "memory_id": "mem_1",
                            "content": "hello",
                            "rank_position": 1,
                            "rank_score": 0.88,
                            "importance_score": 0.9,
                            "timestamp": now,
                            "metadata": {"event_type": "user_question"},
                            "relevance_explanation": "test",
                        }
                    ],
                    "total_candidates": 1,
                    "query_execution_time_ms": 5.0,
                    "applied_filters": {},
                },
            )
        if request.url.path == "/v1/feedback":
            return httpx.Response(
                status_code=200,
                json={
                    "recorded": True,
                    "memory_id": "mem_1",
                    "learning_impact": "positive",
                    "updated_at": now,
                },
            )
        if request.url.path == "/v1/status":
            return httpx.Response(
                status_code=200,
                json={
                    "connected": True,
                    "api_version": "1.0.0",
                    "account_usage": {
                        "events_ingested_this_month": 1,
                        "queries_this_month": 1,
                        "storage_usage_mb": 0.1,
                        "quota": {"events_per_day": 100, "queries_per_day": 500},
                    },
                    "latest_ingestion": now,
                    "uptime_percent": 99.9,
                },
            )
        if request.url.path == "/v1/ingest/batch":
            return httpx.Response(
                status_code=200,
                json={
                    "items": [
                        {
                            "memory_id": "mem_batch",
                            "stored": True,
                            "importance_score": 0.8,
                            "decision_reason": "batch",
                            "encoded_at": now,
                            "latency_ms": 7.0,
                        }
                    ]
                },
            )
        if request.url.path == "/v1/feedback/batch":
            return httpx.Response(
                status_code=200,
                json={
                    "items": [
                        {
                            "recorded": True,
                            "memory_id": "mem_batch",
                            "learning_impact": "batch",
                            "updated_at": now,
                        }
                    ]
                },
            )
        return httpx.Response(status_code=404, json={"detail": "not found"})

    engine = MemoryEngine(
        config=Config(api_key="orbit_pk_aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"),
        transport=httpx.MockTransport(handler),
    )
    try:
        ingest_response = engine.ingest(
            "What is a for loop?", event_type="user_question"
        )
        assert ingest_response.memory_id == "mem_1"
        retrieve_response = engine.retrieve("for loop")
        assert len(retrieve_response.memories) == 1
        feedback_response = engine.feedback(
            memory_id="mem_1", helpful=True, outcome_value=1.0
        )
        assert feedback_response.recorded
        status_response = engine.status()
        assert status_response.connected
        ingest_batch = engine.ingest_batch([{"content": "Event 1"}])
        assert ingest_batch[0].memory_id == "mem_batch"
        feedback_batch = engine.feedback_batch(
            [{"memory_id": "mem_batch", "helpful": True}]
        )
        assert feedback_batch[0].recorded
    finally:
        engine.close()


def test_memory_engine_accepts_overrides() -> None:
    captured: dict[str, Any] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["auth"] = request.headers.get("authorization")
        return httpx.Response(
            status_code=200,
            json={
                "connected": True,
                "api_version": "1.0.0",
                "account_usage": {
                    "events_ingested_this_month": 0,
                    "queries_this_month": 0,
                    "storage_usage_mb": 0.0,
                    "quota": {"events_per_day": 100, "queries_per_day": 500},
                },
                "latest_ingestion": None,
                "uptime_percent": 99.9,
            },
        )

    engine = MemoryEngine(
        api_key="orbit_pk_bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb",
        base_url="https://api.local",
        timeout_seconds=10.0,
        max_retries=2,
        transport=httpx.MockTransport(handler),
    )
    try:
        status_response = engine.status()
        assert status_response.connected
        assert captured["auth"] == "Bearer orbit_pk_bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb"
    finally:
        engine.close()
