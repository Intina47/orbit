from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class MemorySnapshot(BaseModel):
    """Current memory state for decision-time feature context."""

    total_memories: int = 0
    entity_reference_count: int = 0
    similar_recent_count: int = 0
    generated_at: datetime
    metadata: dict[str, str] = Field(default_factory=dict)
