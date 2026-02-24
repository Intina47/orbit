from __future__ import annotations

import os

from pydantic import BaseModel, field_validator

from decision_engine.database_url import normalize_database_url


class EngineConfig(BaseModel):
    """Runtime configuration for the memory decision engine."""

    embedding_dim: int = 384
    sqlite_path: str = "memory.db"
    database_url: str | None = None
    max_content_chars: int = 4000
    assistant_max_content_chars: int = 900
    store_raw_embedding: bool = False
    assistant_response_max_share: float = 0.25
    enable_adaptive_personalization: bool = True
    personalization_repeat_threshold: int = 3
    personalization_similarity_threshold: float = 0.82
    personalization_window_days: int = 30
    personalization_min_feedback_events: int = 4
    personalization_preference_margin: float = 2.0
    personalization_inferred_ttl_days: int = 45
    personalization_inferred_refresh_days: int = 14
    personalization_lifecycle_check_interval_seconds: int = 30

    # Cold-start priors used before enough feedback is available.
    persistent_confidence_prior: float = 0.60
    ephemeral_confidence_prior: float = 0.30

    importance_learning_rate: float = 1e-3
    ranker_learning_rate: float = 1e-3
    decay_learning_rate: float = 1e-2

    ranker_min_training_samples: int = 100
    ranker_training_batch_size: int = 64

    @field_validator("embedding_dim")
    @classmethod
    def validate_embedding_dim(cls, value: int) -> int:
        if value <= 0:
            msg = "embedding_dim must be positive"
            raise ValueError(msg)
        return value

    @field_validator("persistent_confidence_prior", "ephemeral_confidence_prior")
    @classmethod
    def validate_confidence_thresholds(cls, value: float) -> float:
        if not 0.0 <= value <= 1.0:
            msg = "confidence priors must be in [0.0, 1.0]"
            raise ValueError(msg)
        return value

    @field_validator("database_url")
    @classmethod
    def validate_database_url(cls, value: str | None) -> str | None:
        return normalize_database_url(value)

    @field_validator("max_content_chars", "assistant_max_content_chars")
    @classmethod
    def validate_content_limits(cls, value: int) -> int:
        if value <= 0:
            msg = "content limits must be positive"
            raise ValueError(msg)
        return value

    @field_validator("assistant_response_max_share")
    @classmethod
    def validate_assistant_share(cls, value: float) -> float:
        if not 0.0 < value <= 1.0:
            msg = "assistant_response_max_share must be in (0.0, 1.0]"
            raise ValueError(msg)
        return value

    @field_validator("personalization_repeat_threshold")
    @classmethod
    def validate_personalization_repeat_threshold(cls, value: int) -> int:
        if value < 2:
            msg = "personalization_repeat_threshold must be >= 2"
            raise ValueError(msg)
        return value

    @field_validator("personalization_similarity_threshold")
    @classmethod
    def validate_personalization_similarity_threshold(cls, value: float) -> float:
        if not 0.0 <= value <= 1.0:
            msg = "personalization_similarity_threshold must be in [0.0, 1.0]"
            raise ValueError(msg)
        return value

    @field_validator(
        "personalization_window_days",
        "personalization_min_feedback_events",
        "personalization_inferred_ttl_days",
    )
    @classmethod
    def validate_positive_integer_tunables(cls, value: int) -> int:
        if value <= 0:
            msg = "personalization tunables must be positive"
            raise ValueError(msg)
        return value

    @field_validator("personalization_inferred_refresh_days")
    @classmethod
    def validate_non_negative_refresh_days(cls, value: int) -> int:
        if value < 0:
            msg = "personalization_inferred_refresh_days must be >= 0"
            raise ValueError(msg)
        return value

    @field_validator("personalization_lifecycle_check_interval_seconds")
    @classmethod
    def validate_non_negative_lifecycle_interval(cls, value: int) -> int:
        if value < 0:
            msg = "personalization_lifecycle_check_interval_seconds must be >= 0"
            raise ValueError(msg)
        return value

    @field_validator("personalization_preference_margin")
    @classmethod
    def validate_personalization_preference_margin(cls, value: float) -> float:
        if value <= 0.0:
            msg = "personalization_preference_margin must be > 0"
            raise ValueError(msg)
        return value

    @classmethod
    def from_env(cls) -> EngineConfig:
        database_url = normalize_database_url(os.getenv("MDE_DATABASE_URL"))
        return cls(
            embedding_dim=int(os.getenv("MDE_EMBEDDING_DIM", "384")),
            sqlite_path=os.getenv("MDE_SQLITE_PATH", "memory.db"),
            database_url=database_url if database_url else None,
            max_content_chars=int(os.getenv("MDE_MAX_CONTENT_CHARS", "4000")),
            assistant_max_content_chars=int(
                os.getenv("MDE_ASSISTANT_MAX_CONTENT_CHARS", "900")
            ),
            store_raw_embedding=_env_bool("MDE_STORE_RAW_EMBEDDING", False),
            assistant_response_max_share=float(
                os.getenv("MDE_ASSISTANT_RESPONSE_MAX_SHARE", "0.25")
            ),
            enable_adaptive_personalization=_env_bool(
                "MDE_ENABLE_ADAPTIVE_PERSONALIZATION", True
            ),
            personalization_repeat_threshold=int(
                os.getenv("MDE_PERSONALIZATION_REPEAT_THRESHOLD", "3")
            ),
            personalization_similarity_threshold=float(
                os.getenv("MDE_PERSONALIZATION_SIMILARITY_THRESHOLD", "0.82")
            ),
            personalization_window_days=int(
                os.getenv("MDE_PERSONALIZATION_WINDOW_DAYS", "30")
            ),
            personalization_min_feedback_events=int(
                os.getenv("MDE_PERSONALIZATION_MIN_FEEDBACK_EVENTS", "4")
            ),
            personalization_preference_margin=float(
                os.getenv("MDE_PERSONALIZATION_PREFERENCE_MARGIN", "2.0")
            ),
            personalization_inferred_ttl_days=int(
                os.getenv("MDE_PERSONALIZATION_INFERRED_TTL_DAYS", "45")
            ),
            personalization_inferred_refresh_days=int(
                os.getenv("MDE_PERSONALIZATION_INFERRED_REFRESH_DAYS", "14")
            ),
            personalization_lifecycle_check_interval_seconds=int(
                os.getenv(
                    "MDE_PERSONALIZATION_LIFECYCLE_CHECK_INTERVAL_SECONDS",
                    "30",
                )
            ),
            persistent_confidence_prior=float(
                os.getenv("MDE_PERSISTENT_CONFIDENCE_PRIOR", "0.60")
            ),
            ephemeral_confidence_prior=float(
                os.getenv("MDE_EPHEMERAL_CONFIDENCE_PRIOR", "0.30")
            ),
            importance_learning_rate=float(
                os.getenv("MDE_IMPORTANCE_LEARNING_RATE", "0.001")
            ),
            ranker_learning_rate=float(os.getenv("MDE_RANKER_LEARNING_RATE", "0.001")),
            decay_learning_rate=float(os.getenv("MDE_DECAY_LEARNING_RATE", "0.01")),
            ranker_min_training_samples=int(
                os.getenv("MDE_RANKER_MIN_TRAINING_SAMPLES", "100")
            ),
            ranker_training_batch_size=int(
                os.getenv("MDE_RANKER_TRAINING_BATCH_SIZE", "64")
            ),
        )


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
