from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class StorageDecision(BaseModel):
    """Stage 2 output: learned storage decision and metadata."""

    store: bool
    storage_tier: str
    confidence: float
    decay_rate: float
    decay_half_life: float
    should_compress: bool = False
    rationale: str = "learned importance prediction"
    trace: dict[str, Any] = Field(default_factory=dict)
