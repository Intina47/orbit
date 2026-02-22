from __future__ import annotations

from datetime import UTC, datetime
from enum import Enum
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field, field_validator


class StorageTier(str, Enum):
    PERSISTENT = "persistent"
    EPHEMERAL = "ephemeral"
    DISCARD = "discard"


class RawEvent(BaseModel):
    event_id: str = Field(default_factory=lambda: str(uuid4()))
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))
    content: str
    context: dict[str, Any] = Field(default_factory=dict)

    @field_validator("content")
    @classmethod
    def validate_content(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            msg = "event content cannot be empty"
            raise ValueError(msg)
        return stripped


class SemanticUnderstanding(BaseModel):
    summary: str
    entities: list[str] = Field(default_factory=list)
    relationships: list[str] = Field(default_factory=list)
    intent: str = "unknown"


class EncodedEvent(BaseModel):
    event: RawEvent
    raw_embedding: list[float]
    semantic_embedding: list[float]
    understanding: SemanticUnderstanding
    semantic_key: str


class StorageDecision(BaseModel):
    should_store: bool
    tier: StorageTier
    confidence: float
    rationale: str
    trace: dict[str, Any] = Field(default_factory=dict)
    memory_id: str | None = None


class MemoryRecord(BaseModel):
    memory_id: str
    event_id: str
    content: str
    summary: str
    intent: str
    entities: list[str]
    relationships: list[str]
    raw_embedding: list[float]
    semantic_embedding: list[float]
    semantic_key: str
    created_at: datetime
    updated_at: datetime
    retrieval_count: int = 0
    avg_outcome_signal: float = 0.0
    storage_tier: StorageTier
    latest_importance: float
    is_compressed: bool = False
    original_count: int = 1
    decay_half_life_days: float | None = None


class RetrievedMemory(BaseModel):
    memory: MemoryRecord
    rank_score: float


class OutcomeFeedback(BaseModel):
    query: str
    ranked_memory_ids: list[str]
    helpful_memory_ids: list[str]
    outcome_signal: float = 1.0

    @field_validator("outcome_signal")
    @classmethod
    def validate_outcome_signal(cls, value: float) -> float:
        if not -1.0 <= value <= 1.0:
            msg = "outcome_signal must be between -1.0 and 1.0"
            raise ValueError(msg)
        return value
