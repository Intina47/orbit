"""Pydantic request/response models for Orbit SDK and API contracts."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator


class OrbitModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class TimeRange(OrbitModel):
    start: datetime
    end: datetime

    @field_validator("end")
    @classmethod
    def validate_range(cls, value: datetime, info: Any) -> datetime:
        start = info.data.get("start")
        if isinstance(start, datetime) and value < start:
            msg = "time range end must be >= start"
            raise ValueError(msg)
        return value


class IngestRequest(OrbitModel):
    content: str
    event_type: str | None = None
    metadata: dict[str, Any] | None = None
    entity_id: str | None = None

    @field_validator("content")
    @classmethod
    def validate_content(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            msg = "content cannot be empty"
            raise ValueError(msg)
        return stripped


class IngestResponse(OrbitModel):
    memory_id: str
    stored: bool
    importance_score: float
    decision_reason: str
    encoded_at: datetime
    latency_ms: float


class Memory(OrbitModel):
    memory_id: str
    content: str
    rank_position: int
    rank_score: float
    importance_score: float
    timestamp: datetime
    metadata: dict[str, Any] = Field(default_factory=dict)
    relevance_explanation: str


class RetrieveResponse(OrbitModel):
    memories: list[Memory]
    total_candidates: int
    query_execution_time_ms: float
    applied_filters: dict[str, Any] = Field(default_factory=dict)


class FeedbackRequest(OrbitModel):
    memory_id: str
    helpful: bool
    outcome_value: float | None = None

    @field_validator("memory_id")
    @classmethod
    def validate_memory_id(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            msg = "memory_id cannot be empty"
            raise ValueError(msg)
        return stripped

    @field_validator("outcome_value")
    @classmethod
    def validate_outcome_value(cls, value: float | None) -> float | None:
        if value is None:
            return None
        if not -1.0 <= value <= 1.0:
            msg = "outcome_value must be between -1.0 and 1.0"
            raise ValueError(msg)
        return value


class FeedbackResponse(OrbitModel):
    recorded: bool
    memory_id: str
    learning_impact: str
    updated_at: datetime


class AccountQuota(OrbitModel):
    events_per_day: int
    queries_per_day: int


class AccountUsage(OrbitModel):
    events_ingested_this_month: int
    queries_this_month: int
    storage_usage_mb: float
    quota: AccountQuota


class StatusResponse(OrbitModel):
    connected: bool
    api_version: str
    account_usage: AccountUsage
    latest_ingestion: datetime | None = None
    uptime_percent: float


class RetrieveRequest(OrbitModel):
    query: str
    limit: int = 10
    entity_id: str | None = None
    event_type: str | None = None
    time_range: TimeRange | None = None

    @field_validator("query")
    @classmethod
    def validate_query(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            msg = "query cannot be empty"
            raise ValueError(msg)
        return stripped

    @field_validator("limit")
    @classmethod
    def validate_limit(cls, value: int) -> int:
        if not 1 <= value <= 100:
            msg = "limit must be between 1 and 100"
            raise ValueError(msg)
        return value


class IngestBatchRequest(OrbitModel):
    events: list[IngestRequest] = Field(min_length=1, max_length=100)


class IngestBatchResponse(OrbitModel):
    items: list[IngestResponse]


class FeedbackBatchRequest(OrbitModel):
    feedback: list[FeedbackRequest] = Field(min_length=1, max_length=100)


class FeedbackBatchResponse(OrbitModel):
    items: list[FeedbackResponse]


class AuthValidationResponse(OrbitModel):
    valid: bool
    scopes: list[str] = Field(default_factory=list)


class PaginatedMemoriesResponse(OrbitModel):
    data: list[Memory]
    cursor: str | None = None
    has_more: bool
