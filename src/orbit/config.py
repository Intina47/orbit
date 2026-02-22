"""Configuration models for Orbit SDK clients."""

from __future__ import annotations

import os

from pydantic import BaseModel, Field, field_validator

from orbit.version import __version__


class Config(BaseModel):
    """Runtime configuration for sync and async SDK clients."""

    api_key: str | None = None
    base_url: str = "https://api.orbit.dev"
    timeout_seconds: float = 30.0
    max_retries: int = 3
    retry_backoff_factor: float = 2.0
    log_level: str = "info"
    user_agent: str = Field(default_factory=lambda: f"orbit-python/{__version__}")
    enable_telemetry: bool = True

    @field_validator("base_url")
    @classmethod
    def validate_base_url(cls, value: str) -> str:
        stripped = value.strip().rstrip("/")
        if not stripped:
            msg = "base_url cannot be empty"
            raise ValueError(msg)
        return stripped

    @field_validator("timeout_seconds")
    @classmethod
    def validate_timeout_seconds(cls, value: float) -> float:
        if value <= 0:
            msg = "timeout_seconds must be > 0"
            raise ValueError(msg)
        return value

    @field_validator("max_retries")
    @classmethod
    def validate_max_retries(cls, value: int) -> int:
        if value < 0:
            msg = "max_retries must be >= 0"
            raise ValueError(msg)
        return value

    @field_validator("retry_backoff_factor")
    @classmethod
    def validate_retry_backoff_factor(cls, value: float) -> float:
        if value <= 0:
            msg = "retry_backoff_factor must be > 0"
            raise ValueError(msg)
        return value

    @classmethod
    def from_env(cls) -> Config:
        return cls(
            api_key=os.getenv("ORBIT_API_KEY"),
            base_url=os.getenv("ORBIT_BASE_URL", "https://api.orbit.dev"),
            timeout_seconds=_env_float("ORBIT_TIMEOUT", 30.0),
            max_retries=_env_int("ORBIT_MAX_RETRIES", 3),
            retry_backoff_factor=_env_float("ORBIT_RETRY_BACKOFF_FACTOR", 2.0),
            log_level=os.getenv("ORBIT_LOG_LEVEL", "info"),
            user_agent=os.getenv("ORBIT_USER_AGENT", f"orbit-python/{__version__}"),
            enable_telemetry=_env_bool("ORBIT_ENABLE_TELEMETRY", True),
        )


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
    return raw.strip().lower() in {"1", "true", "yes", "on"}
