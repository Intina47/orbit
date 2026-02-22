from __future__ import annotations

import asyncio
from datetime import UTC, datetime

import httpx

from orbit import AsyncMemoryEngine, Config


def test_async_memory_engine_core_methods() -> None:
    now = datetime.now(UTC).isoformat()

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/v1/ingest":
            return httpx.Response(
                status_code=201,
                json={
                    "memory_id": "mem_async",
                    "stored": True,
                    "importance_score": 0.91,
                    "decision_reason": "high relevance",
                    "encoded_at": now,
                    "latency_ms": 11.2,
                },
            )
        if request.url.path == "/v1/retrieve":
            return httpx.Response(
                status_code=200,
                json={
                    "memories": [],
                    "total_candidates": 0,
                    "query_execution_time_ms": 2.1,
                    "applied_filters": {},
                },
            )
        if request.url.path == "/v1/feedback":
            return httpx.Response(
                status_code=200,
                json={
                    "recorded": True,
                    "memory_id": "mem_async",
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
                        "storage_usage_mb": 0.0,
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
                            "memory_id": "mem_2",
                            "stored": True,
                            "importance_score": 0.7,
                            "decision_reason": "batch",
                            "encoded_at": now,
                            "latency_ms": 4.0,
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
                            "memory_id": "mem_2",
                            "learning_impact": "batch",
                            "updated_at": now,
                        }
                    ]
                },
            )
        return httpx.Response(status_code=404, json={"detail": "missing"})

    async def _run() -> None:
        engine = AsyncMemoryEngine(
            config=Config(api_key="orbit_pk_cccccccccccccccccccccccccccccccc"),
            transport=httpx.MockTransport(handler),
        )
        try:
            ingest_response = await engine.ingest("event")
            assert ingest_response.memory_id == "mem_async"
            retrieve_response = await engine.retrieve("query")
            assert retrieve_response.total_candidates == 0
            feedback_response = await engine.feedback("mem_async", helpful=True)
            assert feedback_response.recorded
            status_response = await engine.status()
            assert status_response.connected
            ingest_batch = await engine.ingest_batch([{"content": "Event"}])
            assert ingest_batch[0].memory_id == "mem_2"
            feedback_batch = await engine.feedback_batch(
                [{"memory_id": "mem_2", "helpful": True}]
            )
            assert feedback_batch[0].recorded
        finally:
            await engine.aclose()

    asyncio.run(_run())
