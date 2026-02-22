from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from pydantic import BaseModel, Field, field_validator


class Event(BaseModel):
    """External event shape accepted by the stage-based API."""

    timestamp: int | datetime = Field(default_factory=lambda: datetime.now(UTC))
    entity_id: str
    event_type: str
    description: str
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator("description")
    @classmethod
    def validate_description(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            msg = "description cannot be empty"
            raise ValueError(msg)
        return stripped

    def as_datetime(self) -> datetime:
        if isinstance(self.timestamp, datetime):
            if self.timestamp.tzinfo is None:
                return self.timestamp.replace(tzinfo=UTC)
            return self.timestamp
        return datetime.fromtimestamp(self.timestamp, tz=UTC)
