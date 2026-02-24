"""Configuration model for Orbit FastAPI service."""

from __future__ import annotations

import os

from pydantic import BaseModel, field_validator, model_validator

from decision_engine.database_url import normalize_database_url


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
    dashboard_key_per_minute_limit: str = "60/minute"
    max_ingest_content_chars: int = 20_000
    max_query_chars: int = 2_000
    max_batch_items: int = 100
    uptime_percent: float = 99.9
    environment: str = "development"
    dashboard_auto_provision_accounts: bool = True

    jwt_secret: str = "orbit-dev-secret-change-me"
    jwt_algorithm: str = "HS256"
    jwt_issuer: str = "orbit"
    jwt_audience: str = "orbit-api"
    jwt_required_scope: str | None = None

    otel_service_name: str = "orbit-api"
    otel_exporter_endpoint: str | None = None
    cors_allow_origins: list[str] = []

    @field_validator("database_url")
    @classmethod
    def validate_database_url(cls, value: str) -> str:
        normalized = normalize_database_url(value)
        if normalized is None:
            msg = "database_url cannot be empty"
            raise ValueError(msg)
        return normalized

    @field_validator("jwt_secret")
    @classmethod
    def validate_jwt_secret(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            msg = "jwt_secret cannot be empty"
            raise ValueError(msg)
        return stripped

    @field_validator("jwt_algorithm")
    @classmethod
    def validate_jwt_algorithm(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            msg = "jwt_algorithm cannot be empty"
            raise ValueError(msg)
        if normalized.lower() == "none":
            msg = "jwt_algorithm=none is not allowed"
            raise ValueError(msg)
        return normalized

    @field_validator("per_minute_limit", "dashboard_key_per_minute_limit")
    @classmethod
    def validate_rate_limit(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            msg = "rate limit values cannot be empty"
            raise ValueError(msg)
        return stripped

    @field_validator(
        "free_events_per_day",
        "free_queries_per_day",
        "max_ingest_content_chars",
        "max_query_chars",
        "max_batch_items",
    )
    @classmethod
    def validate_positive_limits(cls, value: int) -> int:
        if value <= 0:
            msg = "limit values must be positive integers"
            raise ValueError(msg)
        return value

    @field_validator("environment")
    @classmethod
    def validate_environment(cls, value: str) -> str:
        normalized = value.strip().lower()
        if not normalized:
            msg = "environment cannot be empty"
            raise ValueError(msg)
        return normalized

    @field_validator("cors_allow_origins", mode="before")
    @classmethod
    def parse_cors_allow_origins(
        cls,
        value: str | list[str] | None,
    ) -> list[str]:
        if value is None:
            return []
        if isinstance(value, str):
            return [item.strip() for item in value.split(",") if item.strip()]
        if isinstance(value, list):
            return [str(item).strip() for item in value if str(item).strip()]
        msg = "cors_allow_origins must be a string or list of strings"
        raise ValueError(msg)

    @model_validator(mode="after")
    def validate_production_jwt_secret(self) -> ApiConfig:
        if self.environment in {"prod", "production"} and (
            self.jwt_secret == "orbit-dev-secret-change-me"
        ):
            msg = "ORBIT_JWT_SECRET must be set to a non-default value in production"
            raise ValueError(msg)
        return self

    @classmethod
    def from_env(cls) -> ApiConfig:
        fallback_path = os.getenv("MDE_SQLITE_PATH", "memory.db")
        database_url = normalize_database_url(
            os.getenv(
            "MDE_DATABASE_URL",
            "postgresql+psycopg://orbit:orbit@postgres:5432/orbit",
            )
        )
        if database_url is None:
            database_url = "postgresql+psycopg://orbit:orbit@postgres:5432/orbit"
        return cls(
            api_version=os.getenv("ORBIT_API_VERSION", "1.0.0"),
            database_url=database_url,
            sqlite_fallback_path=fallback_path,
            default_entity_id=os.getenv("ORBIT_DEFAULT_ENTITY_ID", "global"),
            default_event_type=os.getenv("ORBIT_DEFAULT_EVENT_TYPE", "generic_event"),
            free_events_per_day=_env_int("ORBIT_RATE_LIMIT_EVENTS_PER_DAY", 100),
            free_queries_per_day=_env_int("ORBIT_RATE_LIMIT_QUERIES_PER_DAY", 500),
            per_minute_limit=os.getenv("ORBIT_RATE_LIMIT_PER_MINUTE", "1000/minute"),
            dashboard_key_per_minute_limit=os.getenv(
                "ORBIT_DASHBOARD_KEY_RATE_LIMIT_PER_MINUTE",
                "60/minute",
            ),
            max_ingest_content_chars=_env_int(
                "ORBIT_MAX_INGEST_CONTENT_CHARS", 20_000
            ),
            max_query_chars=_env_int("ORBIT_MAX_QUERY_CHARS", 2_000),
            max_batch_items=_env_int("ORBIT_MAX_BATCH_ITEMS", 100),
            uptime_percent=_env_float("ORBIT_UPTIME_PERCENT", 99.9),
            environment=os.getenv("ORBIT_ENV", "development"),
            dashboard_auto_provision_accounts=_env_bool(
                "ORBIT_DASHBOARD_AUTO_PROVISION_ACCOUNTS",
                True,
            ),
            jwt_secret=os.getenv("ORBIT_JWT_SECRET", "orbit-dev-secret-change-me"),
            jwt_algorithm=os.getenv("ORBIT_JWT_ALGORITHM", "HS256"),
            jwt_issuer=os.getenv("ORBIT_JWT_ISSUER", "orbit"),
            jwt_audience=os.getenv("ORBIT_JWT_AUDIENCE", "orbit-api"),
            jwt_required_scope=_env_optional("ORBIT_JWT_REQUIRED_SCOPE"),
            otel_service_name=os.getenv("ORBIT_OTEL_SERVICE_NAME", "orbit-api"),
            otel_exporter_endpoint=_env_optional("ORBIT_OTEL_EXPORTER_ENDPOINT"),
            cors_allow_origins=_env_csv("ORBIT_CORS_ALLOW_ORIGINS"),
        )


def _env_optional(name: str) -> str | None:
    raw = os.getenv(name)
    if raw is None:
        return None
    stripped = raw.strip()
    return stripped if stripped else None


def _env_csv(name: str) -> list[str]:
    raw = _env_optional(name)
    if raw is None:
        return []
    return [item.strip() for item in raw.split(",") if item.strip()]


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


def _env_bool(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    normalized = raw.strip().lower()
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"0", "false", "no", "off"}:
        return False
    return default
