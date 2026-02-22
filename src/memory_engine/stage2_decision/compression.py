from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from decision_engine.models import MemoryRecord
from memory_engine.models.processed_event import ProcessedEvent


@dataclass(frozen=True)
class CompressionPlan:
    should_compress: bool
    memory_ids_to_replace: list[str]
    summary_text: str = ""
    original_count: int = 0


class CompressionPlanner:
    """Plans event compression for repetitive memory clusters."""

    def __init__(
        self, min_count: int = 5, window_days: int = 7, max_summary_items: int = 20
    ) -> None:
        self._min_count = min_count
        self._window_days = window_days
        self._max_summary_items = max_summary_items

    @property
    def min_count(self) -> int:
        return self._min_count

    def plan(
        self, processed: ProcessedEvent, similar_recent_memories: list[MemoryRecord]
    ) -> CompressionPlan:
        if len(similar_recent_memories) < self._min_count:
            return CompressionPlan(should_compress=False, memory_ids_to_replace=[])

        selected = similar_recent_memories[: self._max_summary_items]
        snippets = [memory.summary for memory in selected]
        summary_text = (
            f"Compressed memory for entity={processed.entity_id}, event_type={processed.event_type}. "
            f"Observed {len(similar_recent_memories)} events in {self._window_days} days: "
            + " | ".join(snippets)
        )
        return CompressionPlan(
            should_compress=True,
            memory_ids_to_replace=[
                memory.memory_id for memory in similar_recent_memories
            ],
            summary_text=summary_text,
            original_count=len(similar_recent_memories),
        )

    def since_iso(self, now: datetime | None = None) -> str:
        reference = now or datetime.now(UTC)
        return (reference - timedelta(days=self._window_days)).isoformat()
