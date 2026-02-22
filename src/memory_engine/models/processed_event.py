from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class ProcessedEvent(BaseModel):
    """Stage 1 output: validated and semantically encoded event."""

    event_id: str
    timestamp: datetime
    entity_id: str
    event_type: str
    description: str
    entity_references: list[str] = Field(default_factory=list)
    embedding: list[float]
    semantic_embedding: list[float]
    intent: str
    semantic_key: str
    semantic_summary: str
    context: dict[str, Any] = Field(default_factory=dict)
