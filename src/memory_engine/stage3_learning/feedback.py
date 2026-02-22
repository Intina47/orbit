from __future__ import annotations

from datetime import UTC, datetime

from pydantic import BaseModel, Field


class FeedbackSignal(BaseModel):
    memory_id: str
    semantic_key: str
    memory_age_days: float
    outcome: str
    outcome_signal: float
    observed_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
