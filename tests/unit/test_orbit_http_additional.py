from __future__ import annotations

import asyncio

import httpx
import pytest

from orbit.config import Config
from orbit.exceptions import (
    OrbitAuthError,
    OrbitNotFoundError,
    OrbitServerError,
    OrbitTimeoutError,
    OrbitValidationError,
)
from orbit.http import AsyncOrbitHttpClient, OrbitHttpClient


def test_http_client_requires_api_key() -> None:
    with pytest.raises(OrbitAuthError):
        OrbitHttpClient(config=Config(api_key=None))


def test_http_client_maps_validation_error() -> None:
    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(status_code=400, json={"detail": "bad request"})

    client = OrbitHttpClient(
        config=Config(api_key="orbit_pk_aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"),
        transport=httpx.MockTransport(handler),
    )
    try:
        with pytest.raises(OrbitValidationError):
            client.post("/v1/ingest", json_body={"content": ""})
    finally:
        client.close()


def test_http_client_maps_not_found_error() -> None:
    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(status_code=404, json={"detail": "missing"})

    client = OrbitHttpClient(
        config=Config(api_key="orbit_pk_aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"),
        transport=httpx.MockTransport(handler),
    )
    try:
        with pytest.raises(OrbitNotFoundError):
            client.get("/v1/memories")
    finally:
        client.close()


def test_http_client_timeout_error() -> None:
    def handler(_request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("timeout")

    client = OrbitHttpClient(
        config=Config(
            api_key="orbit_pk_aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
            max_retries=0,
        ),
        transport=httpx.MockTransport(handler),
    )
    try:
        with pytest.raises(OrbitTimeoutError):
            client.get("/v1/status")
    finally:
        client.close()


def test_http_client_plain_text_payload() -> None:
    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(status_code=200, text="ok")

    client = OrbitHttpClient(
        config=Config(api_key="orbit_pk_aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"),
        transport=httpx.MockTransport(handler),
    )
    try:
        payload = client.get("/v1/health")
        assert payload == {"message": "ok"}
    finally:
        client.close()


def test_async_http_transport_error() -> None:
    def handler(_request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("connect error")

    async def _run() -> None:
        client = AsyncOrbitHttpClient(
            config=Config(
                api_key="orbit_pk_aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
                max_retries=0,
            ),
            transport=httpx.MockTransport(handler),
        )
        try:
            with pytest.raises(OrbitServerError):
                await client.get("/v1/status")
        finally:
            await client.aclose()

    asyncio.run(_run())
