"""Synchronous Orbit SDK client."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

import httpx

from orbit.config import Config
from orbit.http import OrbitHttpClient
from orbit.logger import configure_logging, get_logger
from orbit.models import (
    FeedbackBatchRequest,
    FeedbackBatchResponse,
    FeedbackRequest,
    FeedbackResponse,
    IngestBatchRequest,
    IngestBatchResponse,
    IngestRequest,
    IngestResponse,
    RetrieveRequest,
    RetrieveResponse,
    StatusResponse,
    TimeRange,
)
from orbit.telemetry import TelemetryClient


class MemoryEngine:
    """Main synchronous interface for Orbit SDK users."""

    def __init__(
        self,
        api_key: str | None = None,
        config: Config | None = None,
        *,
        base_url: str | None = None,
        timeout_seconds: float | None = None,
        max_retries: int | None = None,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        resolved = _resolve_config(
            api_key=api_key,
            config=config,
            base_url=base_url,
            timeout_seconds=timeout_seconds,
            max_retries=max_retries,
        )
        configure_logging(resolved.log_level)
        self.config = resolved
        self._log = get_logger("orbit.client")
        self._telemetry = TelemetryClient(enabled=self.config.enable_telemetry)
        self._http = OrbitHttpClient(config=resolved, transport=transport)

    def ingest(
        self,
        content: str,
        event_type: str | None = None,
        metadata: dict[str, Any] | None = None,
        entity_id: str | None = None,
    ) -> IngestResponse:
        request = IngestRequest(
            content=content,
            event_type=event_type,
            metadata=metadata,
            entity_id=entity_id,
        )
        payload = self._http.post(
            "/v1/ingest", json_body=request.model_dump(exclude_none=True)
        )
        response = IngestResponse.model_validate(payload)
        self._telemetry.track("ingest")
        self._log.debug(
            "ingest_completed", memory_id=response.memory_id, stored=response.stored
        )
        return response

    def retrieve(
        self,
        query: str,
        limit: int = 10,
        entity_id: str | None = None,
        event_type: str | None = None,
        time_range: TimeRange | None = None,
    ) -> RetrieveResponse:
        request = RetrieveRequest(
            query=query,
            limit=limit,
            entity_id=entity_id,
            event_type=event_type,
            time_range=time_range,
        )
        params: dict[str, Any] = {
            "query": request.query,
            "limit": request.limit,
        }
        if request.entity_id:
            params["entity_id"] = request.entity_id
        if request.event_type:
            params["event_type"] = request.event_type
        if request.time_range:
            params["start_time"] = request.time_range.start.isoformat()
            params["end_time"] = request.time_range.end.isoformat()
        payload = self._http.get("/v1/retrieve", params=params)
        response = RetrieveResponse.model_validate(payload)
        self._telemetry.track("retrieve", {"result_count": len(response.memories)})
        return response

    def feedback(
        self,
        memory_id: str,
        helpful: bool,
        outcome_value: float | None = None,
    ) -> FeedbackResponse:
        request = FeedbackRequest(
            memory_id=memory_id,
            helpful=helpful,
            outcome_value=outcome_value,
        )
        payload = self._http.post(
            "/v1/feedback", json_body=request.model_dump(exclude_none=True)
        )
        response = FeedbackResponse.model_validate(payload)
        self._telemetry.track("feedback", {"helpful": helpful})
        return response

    def status(self) -> StatusResponse:
        payload = self._http.get("/v1/status")
        response = StatusResponse.model_validate(payload)
        self._telemetry.track("status")
        return response

    def ingest_batch(
        self, events: Sequence[IngestRequest | dict[str, Any]]
    ) -> list[IngestResponse]:
        request = IngestBatchRequest(
            events=[IngestRequest.model_validate(item) for item in events]
        )
        payload = self._http.post(
            "/v1/ingest/batch",
            json_body=request.model_dump(mode="json"),
        )
        response = IngestBatchResponse.model_validate(payload)
        self._telemetry.track("ingest_batch", {"count": len(response.items)})
        return response.items

    def feedback_batch(
        self, feedback: Sequence[FeedbackRequest | dict[str, Any]]
    ) -> list[FeedbackResponse]:
        request = FeedbackBatchRequest(
            feedback=[FeedbackRequest.model_validate(item) for item in feedback]
        )
        payload = self._http.post(
            "/v1/feedback/batch",
            json_body=request.model_dump(mode="json"),
        )
        response = FeedbackBatchResponse.model_validate(payload)
        self._telemetry.track("feedback_batch", {"count": len(response.items)})
        return response.items

    def close(self) -> None:
        self._http.close()

    def __enter__(self) -> MemoryEngine:
        return self

    def __exit__(self, exc_type: object, exc: object, tb: object) -> None:
        self.close()


def _resolve_config(
    api_key: str | None,
    config: Config | None,
    base_url: str | None,
    timeout_seconds: float | None,
    max_retries: int | None,
) -> Config:
    resolved = config.model_copy() if config else Config.from_env()
    if api_key is not None:
        resolved.api_key = api_key
    if base_url is not None:
        resolved.base_url = base_url
    if timeout_seconds is not None:
        resolved.timeout_seconds = timeout_seconds
    if max_retries is not None:
        resolved.max_retries = max_retries
    return resolved
