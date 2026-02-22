from __future__ import annotations

from decision_engine.decay_learner import DecayLearner
from decision_engine.importance_model import ImportanceModel
from decision_engine.models import MemoryRecord


class WeightUpdater:
    """Applies outcome signals to learned importance and decay components."""

    def __init__(
        self, importance_model: ImportanceModel, decay_learner: DecayLearner
    ) -> None:
        self._importance_model = importance_model
        self._decay_learner = decay_learner

    def apply(
        self, memory: MemoryRecord, outcome_signal: float, age_days: float
    ) -> float:
        loss = self._importance_model.train_batch(
            embeddings=[memory.semantic_embedding],
            outcomes=[outcome_signal],
        )
        self._decay_learner.record_outcome(
            semantic_key=memory.semantic_key,
            age_days=age_days,
            was_helpful=outcome_signal > 0.0,
        )
        self._decay_learner.learn()
        return loss
