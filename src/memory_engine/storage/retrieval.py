from __future__ import annotations

from datetime import UTC, datetime

import numpy as np

from decision_engine.models import MemoryRecord, RetrievedMemory
from decision_engine.retrieval_ranker import RetrievalRanker
from decision_engine.semantic_encoding import SemanticEncoder
from decision_engine.storage_protocol import StorageManagerProtocol
from memory_engine.storage.vector_store import VectorStore


class RetrievalService:
    """Retrieval service that combines vector preselection and learned ranking."""

    def __init__(
        self,
        storage: StorageManagerProtocol,
        ranker: RetrievalRanker,
        encoder: SemanticEncoder,
        vector_store: VectorStore | None = None,
        assistant_response_max_share: float = 0.25,
    ) -> None:
        self._storage = storage
        self._ranker = ranker
        self._encoder = encoder
        self._vector_store = vector_store
        self._assistant_response_max_share = max(
            0.0, min(assistant_response_max_share, 1.0)
        )

    def retrieve(
        self, query: str, top_k: int = 5, candidate_pool_size: int | None = None
    ) -> list[RetrievedMemory]:
        query_embedding = self._encoder.encode_query(query)
        pool_size = candidate_pool_size or max(80, top_k * 12)

        if self._vector_store is not None:
            hits = self._vector_store.search(query_embedding, top_k=pool_size)
            candidates = self._storage.fetch_by_ids([hit.memory_id for hit in hits])
            if not candidates:
                candidates = self._storage.search_candidates(
                    np.asarray(query_embedding, dtype=np.float32), top_k=pool_size
                )
        else:
            candidates = self._storage.search_candidates(
                np.asarray(query_embedding, dtype=np.float32), top_k=pool_size
            )
        candidates = self._ensure_non_assistant_candidates(
            candidates,
            top_k=top_k,
            pool_size=pool_size,
        )

        ranked = self._ranker.rank(
            np.asarray(query_embedding, dtype=np.float32),
            candidates,
            now=datetime.now(UTC),
        )
        selected = self._select_with_intent_caps(ranked, top_k=top_k)
        for item in selected:
            self._storage.update_retrieval(item.memory.memory_id)
        return selected

    def _select_with_intent_caps(
        self,
        ranked: list[RetrievedMemory],
        top_k: int,
    ) -> list[RetrievedMemory]:
        if top_k <= 0:
            return []
        assistant_cap = self._assistant_cap(top_k)
        selected: list[RetrievedMemory] = []
        assistant_count = 0
        deferred: list[RetrievedMemory] = []
        for item in ranked:
            is_assistant = self._is_assistant_intent(item.memory.intent)
            if is_assistant and assistant_count >= assistant_cap:
                deferred.append(item)
                continue
            selected.append(item)
            if is_assistant:
                assistant_count += 1
            if len(selected) >= top_k:
                return selected
        for item in deferred:
            if len(selected) >= top_k:
                break
            selected.append(item)
        return selected

    def _ensure_non_assistant_candidates(
        self,
        candidates: list[MemoryRecord],
        *,
        top_k: int,
        pool_size: int,
    ) -> list[MemoryRecord]:
        if top_k <= 0:
            return candidates
        required_non_assistant = max(top_k - self._assistant_cap(top_k), 0)
        current_non_assistant = sum(
            1 for item in candidates if not self._is_assistant_intent(item.intent)
        )
        if current_non_assistant >= required_non_assistant:
            return candidates

        fallback_pool = self._storage.list_memories(limit=max(pool_size, top_k * 8))
        seen_ids = {item.memory_id for item in candidates}
        enriched = list(candidates)
        for memory in fallback_pool:
            if memory.memory_id in seen_ids:
                continue
            if self._is_assistant_intent(memory.intent):
                continue
            enriched.append(memory)
            seen_ids.add(memory.memory_id)
            current_non_assistant += 1
            if current_non_assistant >= required_non_assistant:
                break
        return enriched

    def _assistant_cap(self, top_k: int) -> int:
        return min(top_k, max(0, int(top_k * self._assistant_response_max_share)))

    @staticmethod
    def _is_assistant_intent(intent: str) -> bool:
        return intent.strip().lower().startswith("assistant_")
