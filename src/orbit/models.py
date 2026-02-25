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
    events_per_month: int | None = None
    queries_per_month: int | None = None
    api_keys: int | None = None
    retention_days: int | None = None
    plan: str | None = None
    reset_at: datetime | None = None
    warning_threshold_percent: int | None = None
    critical_threshold_percent: int | None = None


class AccountUsage(OrbitModel):
    events_ingested_this_month: int
    queries_this_month: int
    storage_usage_mb: float
    active_api_keys: int | None = None
    quota: AccountQuota


class PilotProRequest(OrbitModel):
    requested: bool
    status: str
    requested_at: datetime | None = None
    requested_by_email: str | None = None
    requested_by_name: str | None = None
    email_sent_at: datetime | None = None


class StatusResponse(OrbitModel):
    connected: bool
    api_version: str
    account_usage: AccountUsage
    pilot_pro_request: PilotProRequest | None = None
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


class ApiKeyCreateRequest(OrbitModel):
    name: str
    scopes: list[str] = Field(default_factory=list)

    @field_validator("name")
    @classmethod
    def validate_name(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            msg = "name cannot be empty"
            raise ValueError(msg)
        if len(normalized) > 128:
            msg = "name cannot exceed 128 characters"
            raise ValueError(msg)
        return normalized

    @field_validator("scopes")
    @classmethod
    def validate_scopes(cls, value: list[str]) -> list[str]:
        normalized = [item.strip() for item in value if item.strip()]
        return list(dict.fromkeys(normalized))


class ApiKeySummary(OrbitModel):
    key_id: str
    name: str
    key_prefix: str
    scopes: list[str] = Field(default_factory=list)
    status: str
    created_at: datetime
    last_used_at: datetime | None = None
    last_used_source: str | None = None
    revoked_at: datetime | None = None


class ApiKeyIssueResponse(ApiKeySummary):
    key: str


class ApiKeyListResponse(OrbitModel):
    data: list[ApiKeySummary]
    cursor: str | None = None
    has_more: bool = False


class ApiKeyRevokeResponse(OrbitModel):
    key_id: str
    revoked: bool
    revoked_at: datetime | None = None


class ApiKeyRotateRequest(OrbitModel):
    name: str | None = None
    scopes: list[str] | None = None

    @field_validator("name")
    @classmethod
    def validate_optional_name(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        if not normalized:
            msg = "name cannot be empty when provided"
            raise ValueError(msg)
        if len(normalized) > 128:
            msg = "name cannot exceed 128 characters"
            raise ValueError(msg)
        return normalized

    @field_validator("scopes")
    @classmethod
    def validate_optional_scopes(cls, value: list[str] | None) -> list[str] | None:
        if value is None:
            return None
        normalized = [item.strip() for item in value if item.strip()]
        return list(dict.fromkeys(normalized))


class ApiKeyRotateResponse(OrbitModel):
    revoked_key_id: str
    new_key: ApiKeyIssueResponse


class PilotProRequestResponse(OrbitModel):
    request: PilotProRequest
    created: bool
    email_sent: bool


class PaginatedMemoriesResponse(OrbitModel):
    data: list[Memory]
    cursor: str | None = None
    has_more: bool
