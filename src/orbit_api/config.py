"""Configuration model for Orbit FastAPI service."""

from __future__ import annotations

import os

from pydantic import BaseModel, field_validator


class ApiConfig(BaseModel):
    """Runtime settings for Orbit API server."""

    api_version: str = "1.0.0"
    database_url: str = "postgresql+psycopg://orbit:orbit@postgres:5432/orbit"
    sqlite_fallback_path: str = "memory.db"
    default_entity_id: str = "global"
    default_event_type: str = "generic_event"
    free_events_per_day: int = 100
    free_queries_per_day: int = 500
    per_minute_limit: str = "1000/minute"
    uptime_percent: float = 99.9

    jwt_secret: str = "orbit-dev-secret-change-me"
    jwt_algorithm: str = "HS256"
    jwt_issuer: str = "orbit"
    jwt_audience: str = "orbit-api"
    jwt_required_scope: str | None = None

    otel_service_name: str = "orbit-api"
    otel_exporter_endpoint: str | None = None

    @field_validator("database_url")
    @classmethod
    def validate_database_url(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            msg = "database_url cannot be empty"
            raise ValueError(msg)
        return stripped

    @field_validator("jwt_secret")
    @classmethod
    def validate_jwt_secret(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            msg = "jwt_secret cannot be empty"
            raise ValueError(msg)
        return stripped

    @field_validator("per_minute_limit")
    @classmethod
    def validate_per_minute_limit(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            msg = "per_minute_limit cannot be empty"
            raise ValueError(msg)
        return stripped

    @classmethod
    def from_env(cls) -> ApiConfig:
        fallback_path = os.getenv("MDE_SQLITE_PATH", "memory.db")
        database_url = os.getenv(
            "MDE_DATABASE_URL",
            "postgresql+psycopg://orbit:orbit@postgres:5432/orbit",
        )
        return cls(
            api_version=os.getenv("ORBIT_API_VERSION", "1.0.0"),
            database_url=database_url,
            sqlite_fallback_path=fallback_path,
            default_entity_id=os.getenv("ORBIT_DEFAULT_ENTITY_ID", "global"),
            default_event_type=os.getenv("ORBIT_DEFAULT_EVENT_TYPE", "generic_event"),
            free_events_per_day=_env_int("ORBIT_RATE_LIMIT_EVENTS_PER_DAY", 100),
            free_queries_per_day=_env_int("ORBIT_RATE_LIMIT_QUERIES_PER_DAY", 500),
            per_minute_limit=os.getenv("ORBIT_RATE_LIMIT_PER_MINUTE", "1000/minute"),
            uptime_percent=_env_float("ORBIT_UPTIME_PERCENT", 99.9),
            jwt_secret=os.getenv("ORBIT_JWT_SECRET", "orbit-dev-secret-change-me"),
            jwt_algorithm=os.getenv("ORBIT_JWT_ALGORITHM", "HS256"),
            jwt_issuer=os.getenv("ORBIT_JWT_ISSUER", "orbit"),
            jwt_audience=os.getenv("ORBIT_JWT_AUDIENCE", "orbit-api"),
            jwt_required_scope=_env_optional("ORBIT_JWT_REQUIRED_SCOPE"),
            otel_service_name=os.getenv("ORBIT_OTEL_SERVICE_NAME", "orbit-api"),
            otel_exporter_endpoint=_env_optional("ORBIT_OTEL_EXPORTER_ENDPOINT"),
        )


def _env_optional(name: str) -> str | None:
    raw = os.getenv(name)
    if raw is None:
        return None
    stripped = raw.strip()
    return stripped if stripped else None


def _env_int(name: str, default: int) -> int:
    raw = os.getenv(name)
    if raw is None:
        return default
    try:
        return int(raw)
    except ValueError:
        return default


def _env_float(name: str, default: float) -> float:
    raw = os.getenv(name)
    if raw is None:
        return default
    try:
        return float(raw)
    except ValueError:
        return default
