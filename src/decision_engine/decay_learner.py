from __future__ import annotations

import math
from collections import defaultdict
from dataclasses import dataclass


@dataclass(frozen=True)
class DecayObservation:
    semantic_key: str
    age_days: float
    was_helpful: bool


class DecayLearner:
    """Learns decay rates from outcome signals across semantic categories."""

    def __init__(
        self, learning_rate: float = 1e-2, prior_decay_rate: float = 1e-2
    ) -> None:
        self._learning_rate = learning_rate
        self._prior_decay_rate = prior_decay_rate
        self._decay_rates: dict[str, float] = {}
        self._observations: dict[str, list[DecayObservation]] = defaultdict(list)

    def predict_decay_rate(self, semantic_key: str) -> float:
        return self._decay_rates.get(semantic_key, self._prior_decay_rate)

    def predict_relevance(
        self, semantic_key: str, age_days: float, initial_importance: float
    ) -> float:
        rate = self.predict_decay_rate(semantic_key)
        return float(initial_importance * math.exp(-rate * max(age_days, 0.0)))

    def record_outcome(
        self, semantic_key: str, age_days: float, was_helpful: bool
    ) -> None:
        observation = DecayObservation(
            semantic_key=semantic_key,
            age_days=max(age_days, 0.0),
            was_helpful=was_helpful,
        )
        self._observations[semantic_key].append(observation)

    def learn(self) -> None:
        for semantic_key, observations in self._observations.items():
            if not observations:
                continue
            rate = self.predict_decay_rate(semantic_key)
            for obs in observations:
                target = 1.0 if obs.was_helpful else 0.0
                predicted = math.exp(-rate * obs.age_days)
                # Gradient for MSE: d/d(rate) (predicted - target)^2
                gradient = 2.0 * (predicted - target) * (-obs.age_days * predicted)
                rate -= self._learning_rate * gradient
                rate = min(max(rate, 1e-4), 2.0)
            self._decay_rates[semantic_key] = rate
