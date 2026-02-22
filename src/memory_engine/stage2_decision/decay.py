from __future__ import annotations

import math

from decision_engine.decay_learner import DecayLearner
from memory_engine.models.processed_event import ProcessedEvent


class DecayPolicyAssigner:
    """Assign decay from learned rates and expose half-life metadata."""

    def __init__(self, decay_learner: DecayLearner) -> None:
        self._decay_learner = decay_learner

    def assign(self, processed: ProcessedEvent) -> tuple[float, float]:
        rate = self._decay_learner.predict_decay_rate(processed.semantic_key)
        half_life = math.log(2) / rate if rate > 0 else float("inf")
        return rate, half_life
