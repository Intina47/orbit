from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta
from pathlib import Path

import httpx
import jwt

from memory_engine.config import EngineConfig
from orbit_api.app import create_app
from orbit_api.config import ApiConfig

JWT_SECRET = "error-secret"
JWT_ISSUER = "orbit-tests"
JWT_AUDIENCE = "orbit-tests-api"


def _build_app(tmp_path: Path):
    db_path = tmp_path / "errors.db"
    api_config = ApiConfig(
        database_url=f"sqlite:///{db_path}",
        sqlite_fallback_path=str(db_path),
        free_events_per_day=1,
        free_queries_per_day=1,
        jwt_secret=JWT_SECRET,
        jwt_issuer=JWT_ISSUER,
        jwt_audience=JWT_AUDIENCE,
    )
    engine_config = EngineConfig(
        sqlite_path=str(db_path),
        database_url=f"sqlite:///{db_path}",
        embedding_dim=16,
        persistent_confidence_prior=0.0,
        ephemeral_confidence_prior=0.0,
    )
    return create_app(api_config=api_config, engine_config=engine_config)


def _jwt_token(subject: str = "error-user") -> str:
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


def test_api_auth_and_rate_limit_errors(tmp_path: Path) -> None:
    async def _run() -> None:
        app = _build_app(tmp_path)
        transport = httpx.ASGITransport(app=app)

        async with httpx.AsyncClient(
            transport=transport,
            base_url="http://testserver",
        ) as client:
            missing_auth = await client.post(
                "/v1/ingest", json={"content": "hello", "event_type": "user_question"}
            )
            assert missing_auth.status_code == 401

            invalid_auth = await client.post(
                "/v1/ingest",
                headers={"Authorization": "Bearer invalid"},
                json={"content": "hello", "event_type": "user_question"},
            )
            assert invalid_auth.status_code == 401

            first = await client.post(
                "/v1/ingest",
                headers={"Authorization": f"Bearer {_jwt_token()}"},
                json={"content": "hello", "event_type": "user_question"},
            )
            assert first.status_code == 201

            second = await client.post(
                "/v1/ingest",
                headers={"Authorization": f"Bearer {_jwt_token()}"},
                json={"content": "hello again", "event_type": "user_question"},
            )
            assert second.status_code == 429
            assert "Retry-After" in second.headers
            assert "1" in second.headers["X-RateLimit-Limit"]

            auth_validate = await client.post(
                "/v1/auth/validate",
                headers={"Authorization": f"Bearer {_jwt_token()}"},
            )
            assert auth_validate.status_code == 200
            assert auth_validate.json()["valid"] is True

    asyncio.run(_run())
