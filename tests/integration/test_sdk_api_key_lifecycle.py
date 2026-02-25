from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta
from pathlib import Path

import httpx
import jwt
import pytest

from memory_engine.config import EngineConfig
from orbit import AsyncMemoryEngine, Config
from orbit.exceptions import OrbitAuthError
from orbit_api.app import create_app
from orbit_api.config import ApiConfig

JWT_SECRET = "sdk-lifecycle-secret"
JWT_ISSUER = "orbit-sdk-tests"
JWT_AUDIENCE = "orbit-sdk-tests-api"


def _build_app(tmp_path: Path):
    db_path = tmp_path / "sdk_lifecycle.db"
    api_config = ApiConfig(
        database_url=f"sqlite:///{db_path}",
        sqlite_fallback_path=str(db_path),
        free_events_per_day=100,
        free_queries_per_day=500,
        free_events_per_month=100,
        free_queries_per_month=500,
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


def _jwt_token(subject: str = "sdk-admin") -> str:
    now = datetime.now(UTC)
    payload = {
        "sub": subject,
        "iss": JWT_ISSUER,
        "aud": JWT_AUDIENCE,
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(hours=1)).timestamp()),
        "scopes": ["read", "write", "feedback", "keys:read", "keys:write"],
    }
    return str(jwt.encode(payload, JWT_SECRET, algorithm="HS256"))


def _sdk_config(api_key: str) -> Config:
    return Config(
        api_key=api_key,
        base_url="http://testserver",
        timeout_seconds=10.0,
        max_retries=0,
        enable_telemetry=False,
    )


def test_async_sdk_api_key_lifecycle_enforced(tmp_path: Path) -> None:
    async def _run() -> None:
        app = _build_app(tmp_path)
        transport = httpx.ASGITransport(app=app)
        dashboard_headers = {"Authorization": f"Bearer {_jwt_token()}"}

        async with httpx.AsyncClient(
            transport=transport,
            base_url="http://testserver",
        ) as admin_client:
            issue = await admin_client.post(
                "/v1/dashboard/keys",
                headers=dashboard_headers,
                json={"name": "sdk-e2e", "scopes": ["read", "write", "feedback"]},
            )
            assert issue.status_code == 201
            issue_body = issue.json()
            key_id = str(issue_body["key_id"])
            plaintext_key = str(issue_body["key"])

            sdk = AsyncMemoryEngine(
                config=_sdk_config(plaintext_key),
                transport=transport,
            )
            try:
                ingest = await sdk.ingest(
                    content="SDK lifecycle test memory",
                    event_type="sdk_test_event",
                    entity_id="sdk-user",
                )
                assert ingest.stored is True

                retrieve = await sdk.retrieve(
                    query="What did sdk-user ask?",
                    entity_id="sdk-user",
                    limit=5,
                )
                assert retrieve.total_candidates >= 1
                assert retrieve.memories

                status = await sdk.status()
                assert status.connected is True
            finally:
                await sdk.aclose()

            revoke = await admin_client.post(
                f"/v1/dashboard/keys/{key_id}/revoke",
                headers=dashboard_headers,
            )
            assert revoke.status_code == 200

            revoked_sdk = AsyncMemoryEngine(
                config=_sdk_config(plaintext_key),
                transport=transport,
            )
            try:
                with pytest.raises(OrbitAuthError):
                    await revoked_sdk.status()
            finally:
                await revoked_sdk.aclose()

            invalid_sdk = AsyncMemoryEngine(
                config=_sdk_config("orbit_pk_invalidprefix_badsecret"),
                transport=transport,
            )
            try:
                with pytest.raises(OrbitAuthError):
                    await invalid_sdk.status()
            finally:
                await invalid_sdk.aclose()

    asyncio.run(_run())


def test_async_sdk_rotation_invalidates_old_key_and_accepts_new_key(
    tmp_path: Path,
) -> None:
    async def _run() -> None:
        app = _build_app(tmp_path)
        transport = httpx.ASGITransport(app=app)
        dashboard_headers = {"Authorization": f"Bearer {_jwt_token()}"}

        async with httpx.AsyncClient(
            transport=transport,
            base_url="http://testserver",
        ) as admin_client:
            issue = await admin_client.post(
                "/v1/dashboard/keys",
                headers=dashboard_headers,
                json={"name": "sdk-rotate", "scopes": ["read", "write", "feedback"]},
            )
            assert issue.status_code == 201
            issue_body = issue.json()
            key_id = str(issue_body["key_id"])
            old_key = str(issue_body["key"])

            rotate = await admin_client.post(
                f"/v1/dashboard/keys/{key_id}/rotate",
                headers=dashboard_headers,
                json={"name": "sdk-rotate-v2", "scopes": ["read", "write", "feedback"]},
            )
            assert rotate.status_code == 201
            rotate_body = rotate.json()
            new_key = str(rotate_body["new_key"]["key"])

            old_sdk = AsyncMemoryEngine(
                config=_sdk_config(old_key),
                transport=transport,
            )
            try:
                with pytest.raises(OrbitAuthError):
                    await old_sdk.status()
            finally:
                await old_sdk.aclose()

            new_sdk = AsyncMemoryEngine(
                config=_sdk_config(new_key),
                transport=transport,
            )
            try:
                new_status = await new_sdk.status()
                assert new_status.connected is True
            finally:
                await new_sdk.aclose()

    asyncio.run(_run())
