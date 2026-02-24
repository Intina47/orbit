from __future__ import annotations

from datetime import UTC, datetime

import numpy as np

from decision_engine.models import OutcomeFeedback
from decision_engine.retrieval_ranker import RetrievalRanker
from decision_engine.storage_protocol import StorageManagerProtocol
from memory_engine.logger import EngineLogger
from memory_engine.stage3_learning.weight_updater import WeightUpdater


class LearningLoop:
    """Continuous learning loop fed by retrieval outcomes."""

    def __init__(
        self,
        storage: StorageManagerProtocol,
        ranker: RetrievalRanker,
        weight_updater: WeightUpdater,
    ) -> None:
        self._storage = storage
        self._ranker = ranker
        self._weight_updater = weight_updater
        self._log = EngineLogger()

    def record_feedback(
        self,
        feedback: OutcomeFeedback,
        query_embedding: list[float],
        account_key: str | None = None,
    ) -> dict[str, float | None]:
        now = datetime.now(UTC)
        memories = self._storage.fetch_by_ids(
            feedback.ranked_memory_ids,
            account_key=account_key,
        )
        helpful_ids = set(feedback.helpful_memory_ids)
        losses: list[float] = []
        for memory in memories:
            age_days = max((now - memory.created_at).total_seconds() / 86400.0, 0.0)
            signal = (
                feedback.outcome_signal
                if memory.memory_id in helpful_ids
                else -abs(feedback.outcome_signal)
            )
            loss = self._weight_updater.apply(memory, signal, age_days)
            losses.append(loss)
            self._storage.update_outcome(
                memory.memory_id,
                signal,
                account_key=account_key,
            )

        rank_loss = self._ranker.learn_from_feedback(
            query_embedding=np.asarray(query_embedding, dtype=np.float32),
            candidates=memories,
            helpful_memory_ids=helpful_ids,
            now=now,
        )
        avg_importance_loss = sum(losses) / len(losses) if losses else None
        self._log.info(
            "learning_feedback_applied",
            ranked_count=len(memories),
            helpful_count=len(helpful_ids),
            rank_loss=rank_loss,
            importance_loss=avg_importance_loss,
        )
        return {"rank_loss": rank_loss, "importance_loss": avg_importance_loss}
