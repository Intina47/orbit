from __future__ import annotations

from typing import Protocol

import numpy as np
from numpy.typing import NDArray

from decision_engine.models import EncodedEvent, MemoryRecord, StorageDecision


class StorageManagerProtocol(Protocol):
    """Shared storage interface for SQLite and SQLAlchemy backends."""

    def store(
        self,
        encoded_event: EncodedEvent,
        decision: StorageDecision,
        account_key: str = "default",
    ) -> MemoryRecord:
        """Persist an encoded event and return the stored memory record."""

    def count_memories(self, account_key: str | None = None) -> int:
        """Return total persisted memories."""

    def list_memories(
        self,
        limit: int | None = None,
        account_key: str | None = None,
    ) -> list[MemoryRecord]:
        """Return all memories, optionally capped by limit."""

    def list_recent_memories(
        self,
        limit: int | None = None,
        account_key: str | None = None,
    ) -> list[MemoryRecord]:
        """Return the most recently created memories, capped by `limit`."""

    def fetch_by_ids(
        self,
        memory_ids: list[str],
        account_key: str | None = None,
    ) -> list[MemoryRecord]:
        """Return memories matching a set of IDs."""

    def fetch_by_entity_and_intent(
        self,
        entity_id: str,
        intent: str,
        since_iso: str | None = None,
        account_key: str | None = None,
    ) -> list[MemoryRecord]:
        """Return memories matching entity + intent with optional time filter."""

    def search_candidates(
        self,
        query_embedding: NDArray[np.float32],
        top_k: int,
        account_key: str | None = None,
    ) -> list[MemoryRecord]:
        """Return top-k semantic candidates."""

    def update_retrieval(self, memory_id: str, account_key: str | None = None) -> None:
        """Increment retrieval counters for a memory."""

    def update_outcome(
        self,
        memory_id: str,
        outcome_signal: float,
        account_key: str | None = None,
    ) -> None:
        """Update aggregated outcome signal for a memory."""

    def delete_memories(
        self,
        memory_ids: list[str],
        account_key: str | None = None,
    ) -> None:
        """Delete memories by ID."""

    def close(self) -> None:
        """Release storage resources."""
