from __future__ import annotations

import asyncio

import httpx
import pytest

from orbit.config import Config
from orbit.exceptions import OrbitAuthError, OrbitRateLimitError
from orbit.http import AsyncOrbitHttpClient, OrbitHttpClient


def test_sync_http_maps_auth_error() -> None:
    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(status_code=401, json={"detail": "invalid key"})

    client = OrbitHttpClient(
        config=Config(api_key="orbit_pk_aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"),
        transport=httpx.MockTransport(handler),
    )
    try:
        with pytest.raises(OrbitAuthError):
            client.get("/v1/status")
    finally:
        client.close()


def test_sync_http_retries_server_errors() -> None:
    calls = {"count": 0}

    def handler(_request: httpx.Request) -> httpx.Response:
        calls["count"] += 1
        if calls["count"] == 1:
            return httpx.Response(status_code=503, json={"detail": "unavailable"})
        return httpx.Response(status_code=200, json={"connected": True})

    client = OrbitHttpClient(
        config=Config(
            api_key="orbit_pk_aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
            max_retries=1,
            retry_backoff_factor=0.001,
        ),
        transport=httpx.MockTransport(handler),
    )
    try:
        payload = client.get("/v1/status")
        assert payload == {"connected": True}
        assert calls["count"] == 2
    finally:
        client.close()


def test_async_http_maps_rate_limit_error() -> None:
    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            status_code=429,
            headers={"Retry-After": "3"},
            json={"detail": "too many requests"},
        )

    async def _run() -> None:
        client = AsyncOrbitHttpClient(
            config=Config(
                api_key="orbit_pk_aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
                max_retries=0,
                retry_backoff_factor=0.001,
            ),
            transport=httpx.MockTransport(handler),
        )
        try:
            with pytest.raises(OrbitRateLimitError) as exc_info:
                await client.get("/v1/status")
            assert exc_info.value.retry_after == 3.0
        finally:
            await client.aclose()

    asyncio.run(_run())
