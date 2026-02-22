from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta
from pathlib import Path

import httpx
import jwt

from memory_engine.config import EngineConfig
from orbit import AsyncMemoryEngine, Config
from orbit_api.app import create_app
from orbit_api.config import ApiConfig

JWT_SECRET = "integration-secret"
JWT_ISSUER = "orbit-tests"
JWT_AUDIENCE = "orbit-tests-api"


def _build_app(tmp_path: Path):
    db_path = tmp_path / "orbit_api.db"
    api_config = ApiConfig(
        database_url=f"sqlite:///{db_path}",
        sqlite_fallback_path=str(db_path),
        free_events_per_day=100,
        free_queries_per_day=500,
        jwt_secret=JWT_SECRET,
        jwt_issuer=JWT_ISSUER,
        jwt_audience=JWT_AUDIENCE,
    )
    engine_config = EngineConfig(
        sqlite_path=str(db_path),
        database_url=f"sqlite:///{db_path}",
        embedding_dim=32,
        persistent_confidence_prior=0.0,
        ephemeral_confidence_prior=0.0,
        ranker_min_training_samples=2,
        ranker_training_batch_size=2,
    )
    return create_app(api_config=api_config, engine_config=engine_config)


def _jwt_token(subject: str = "integration-user") -> str:
    now = datetime.now(UTC)
    payload = {
        "sub": subject,
        "iss": JWT_ISSUER,
        "aud": JWT_AUDIENCE,
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(hours=1)).timestamp()),
        "scopes": ["read", "write", "feedback"],
    }
    return str(jwt.encode(payload, JWT_SECRET, algorithm="HS256"))


def test_api_end_to_end_flow(tmp_path: Path) -> None:
    async def _run() -> None:
        app = _build_app(tmp_path)
        transport = httpx.ASGITransport(app=app)
        headers = {"Authorization": f"Bearer {_jwt_token()}"}

        async with httpx.AsyncClient(
            transport=transport,
            base_url="http://testserver",
        ) as client:
            ingest = await client.post(
                "/v1/ingest",
                headers=headers,
                json={
                    "content": "Alice is learning loops and likes short explanations",
                    "event_type": "user_question",
                    "entity_id": "alice",
                    "metadata": {"topic": "loops"},
                },
            )
            assert ingest.status_code == 201
            assert ingest.json()["stored"] is True
            memory_id = ingest.json()["memory_id"]
            assert "100" in ingest.headers["X-RateLimit-Limit"]

            retrieve = await client.get(
                "/v1/retrieve",
                headers=headers,
                params={
                    "query": "What does Alice need help with?",
                    "entity_id": "alice",
                    "limit": 5,
                },
            )
            assert retrieve.status_code == 200
            body = retrieve.json()
            assert body["total_candidates"] >= 1
            assert len(body["memories"]) >= 1
            assert "500" in retrieve.headers["X-RateLimit-Limit"]

            feedback = await client.post(
                "/v1/feedback",
                headers=headers,
                json={"memory_id": memory_id, "helpful": True, "outcome_value": 1.0},
            )
            assert feedback.status_code == 200
            assert feedback.json()["recorded"] is True

            status = await client.get("/v1/status", headers=headers)
            assert status.status_code == 200
            assert status.json()["connected"] is True

            health = await client.get("/v1/health")
            assert health.status_code == 200
            assert health.json()["status"] == "ok"

            metrics = await client.get("/v1/metrics")
            assert metrics.status_code == 200
            assert "orbit_ingest_requests_total" in metrics.text

    asyncio.run(_run())


def test_async_sdk_against_fastapi_app(tmp_path: Path) -> None:
    async def _run() -> None:
        app = _build_app(tmp_path)
        transport = httpx.ASGITransport(app=app)

        engine = AsyncMemoryEngine(
            config=Config(
                api_key=_jwt_token(),
                base_url="http://testserver",
                timeout_seconds=10.0,
                max_retries=0,
            ),
            transport=transport,
        )
        try:
            ingest_response = await engine.ingest(
                content="Alice completed lesson 10 and now asks architecture questions",
                event_type="learning_progress",
                entity_id="alice",
            )
            assert ingest_response.stored is True

            retrieve_response = await engine.retrieve(
                query="What should I know about alice?",
                entity_id="alice",
                limit=5,
            )
            assert retrieve_response.total_candidates >= 1
            assert retrieve_response.memories
        finally:
            await engine.aclose()

    asyncio.run(_run())
