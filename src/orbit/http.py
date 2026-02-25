"""HTTP client wrappers with retry and Orbit-specific error mapping."""

from __future__ import annotations

import asyncio
import time
from typing import Any

import httpx

from orbit.config import Config
from orbit.exceptions import (
    OrbitAuthError,
    OrbitError,
    OrbitNotFoundError,
    OrbitRateLimitError,
    OrbitServerError,
    OrbitTimeoutError,
    OrbitValidationError,
)

_RETRYABLE_STATUS_CODES = {408, 425, 429, 500, 502, 503, 504}


class OrbitHttpClient:
    """Synchronous HTTP client for Orbit API."""

    def __init__(
        self, config: Config, transport: httpx.BaseTransport | None = None
    ) -> None:
        self._config = config
        if not self._config.api_key:
            msg = "Missing API key. Set ORBIT_API_KEY or pass api_key to MemoryEngine."
            raise OrbitAuthError(msg)
        self._client = httpx.Client(
            base_url=self._config.base_url,
            timeout=self._config.timeout_seconds,
            headers={
                "Authorization": f"Bearer {self._config.api_key}",
                "User-Agent": self._config.user_agent,
            },
            transport=transport,
        )

    def get(
        self, path: str, params: dict[str, Any] | None = None
    ) -> dict[str, Any] | list[Any]:
        return self.request("GET", path, params=params)

    def post(
        self, path: str, json_body: dict[str, Any] | None = None
    ) -> dict[str, Any] | list[Any]:
        return self.request("POST", path, json_body=json_body)

    def request(
        self,
        method: str,
        path: str,
        params: dict[str, Any] | None = None,
        json_body: dict[str, Any] | None = None,
    ) -> dict[str, Any] | list[Any]:
        for attempt in range(self._config.max_retries + 1):
            try:
                response = self._client.request(
                    method,
                    path,
                    params=params,
                    json=json_body,
                )
            except httpx.TimeoutException as exc:
                if attempt >= self._config.max_retries:
                    msg = "Orbit request timed out"
                    raise OrbitTimeoutError(msg) from exc
                self._sleep(attempt)
                continue
            except httpx.HTTPError as exc:
                if attempt >= self._config.max_retries:
                    msg = f"HTTP transport error: {exc!s}"
                    raise OrbitServerError(msg) from exc
                self._sleep(attempt)
                continue

            if (
                response.status_code in _RETRYABLE_STATUS_CODES
                and attempt < self._config.max_retries
            ):
                self._sleep(attempt, retry_after=_retry_after_seconds(response))
                continue

            _raise_for_status(response)
            return _parse_payload(response)

        msg = "Orbit request failed after retries"
        raise OrbitServerError(msg)

    def close(self) -> None:
        self._client.close()

    def _sleep(self, attempt: int, retry_after: float | None = None) -> None:
        delay = _compute_backoff(
            attempt=attempt,
            backoff_factor=self._config.retry_backoff_factor,
            retry_after=retry_after,
        )
        time.sleep(delay)


class AsyncOrbitHttpClient:
    """Asynchronous HTTP client for Orbit API."""

    def __init__(
        self, config: Config, transport: httpx.AsyncBaseTransport | None = None
    ) -> None:
        self._config = config
        if not self._config.api_key:
            msg = "Missing API key. Set ORBIT_API_KEY or pass api_key to AsyncMemoryEngine."
            raise OrbitAuthError(msg)
        self._client = httpx.AsyncClient(
            base_url=self._config.base_url,
            timeout=self._config.timeout_seconds,
            headers={
                "Authorization": f"Bearer {self._config.api_key}",
                "User-Agent": self._config.user_agent,
            },
            transport=transport,
        )

    async def get(
        self, path: str, params: dict[str, Any] | None = None
    ) -> dict[str, Any] | list[Any]:
        return await self.request("GET", path, params=params)

    async def post(
        self, path: str, json_body: dict[str, Any] | None = None
    ) -> dict[str, Any] | list[Any]:
        return await self.request("POST", path, json_body=json_body)

    async def request(
        self,
        method: str,
        path: str,
        params: dict[str, Any] | None = None,
        json_body: dict[str, Any] | None = None,
    ) -> dict[str, Any] | list[Any]:
        for attempt in range(self._config.max_retries + 1):
            try:
                response = await self._client.request(
                    method,
                    path,
                    params=params,
                    json=json_body,
                )
            except httpx.TimeoutException as exc:
                if attempt >= self._config.max_retries:
                    msg = "Orbit request timed out"
                    raise OrbitTimeoutError(msg) from exc
                await self._sleep(attempt)
                continue
            except httpx.HTTPError as exc:
                if attempt >= self._config.max_retries:
                    msg = f"HTTP transport error: {exc!s}"
                    raise OrbitServerError(msg) from exc
                await self._sleep(attempt)
                continue

            if (
                response.status_code in _RETRYABLE_STATUS_CODES
                and attempt < self._config.max_retries
            ):
                await self._sleep(attempt, retry_after=_retry_after_seconds(response))
                continue

            _raise_for_status(response)
            return _parse_payload(response)

        msg = "Orbit request failed after retries"
        raise OrbitServerError(msg)

    async def aclose(self) -> None:
        await self._client.aclose()

    async def _sleep(self, attempt: int, retry_after: float | None = None) -> None:
        delay = _compute_backoff(
            attempt=attempt,
            backoff_factor=self._config.retry_backoff_factor,
            retry_after=retry_after,
        )
        await asyncio.sleep(delay)


def _compute_backoff(
    attempt: int, backoff_factor: float, retry_after: float | None
) -> float:
    if retry_after is not None and retry_after >= 0:
        return retry_after
    return backoff_factor * float(2**attempt)


def _retry_after_seconds(response: httpx.Response) -> float | None:
    raw = response.headers.get("Retry-After")
    if raw is None:
        return None
    try:
        return float(raw)
    except ValueError:
        return None


def _raise_for_status(response: httpx.Response) -> None:
    if response.status_code < 400:
        return
    message = _error_message(response)
    code = response.status_code
    if code in {401, 403}:
        raise OrbitAuthError(message)
    if code == 400:
        raise OrbitValidationError(message)
    if code == 404:
        raise OrbitNotFoundError(message)
    if code == 429:
        raise OrbitRateLimitError(message, retry_after=_retry_after_seconds(response))
    if code >= 500:
        raise OrbitServerError(message)
    raise OrbitError(message)


def _error_message(response: httpx.Response) -> str:
    payload = _parse_payload(response)
    if isinstance(payload, dict):
        detail_payload = payload.get("detail")
        if isinstance(detail_payload, dict):
            for key in ("message", "detail", "error"):
                value = detail_payload.get(key)
                if isinstance(value, str) and value:
                    return value
        for key in ("detail", "message", "error"):
            value = payload.get(key)
            if isinstance(value, str) and value:
                return value
    text = response.text.strip()
    return text if text else f"Orbit API error ({response.status_code})"


def _parse_payload(response: httpx.Response) -> dict[str, Any] | list[Any]:
    if not response.content:
        return {}
    try:
        payload = response.json()
    except ValueError:
        return {"message": response.text}
    if isinstance(payload, (dict, list)):
        return payload
    return {"value": payload}
