from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import UTC, datetime

from decision_engine.importance_model import ImportanceModel
from memory_engine.models.memory_state import MemorySnapshot
from memory_engine.models.processed_event import ProcessedEvent

ALPHA = 0.4
BETA = 0.3
GAMMA = 0.3
RECENCY_LAMBDA = 0.1
FREQUENCY_LAMBDA = 0.3


def bootstrap_relevance_score(
    recency_days: float,
    frequency_count: int,
    entity_ref_count: int,
) -> float:
    """Deterministic bootstrap prior from v1 formula set."""

    recency = math.exp(-RECENCY_LAMBDA * max(recency_days, 0.0))
    frequency = 1.0 - math.exp(-FREQUENCY_LAMBDA * max(frequency_count, 0))
    entity_importance = min(1.0, max(entity_ref_count, 0) / 10.0)
    return (ALPHA * recency) + (BETA * frequency) + (GAMMA * entity_importance)


@dataclass(frozen=True)
class ScoreResult:
    confidence: float
    trace: dict[str, float]


class LearnedRelevanceScorer:
    """Learned scorer with deterministic bootstrap prior for cold-start stability."""

    def __init__(self, importance_model: ImportanceModel) -> None:
        self._importance_model = importance_model

    def score(self, processed: ProcessedEvent, snapshot: MemorySnapshot) -> ScoreResult:
        model_confidence = self._importance_model.predict(processed.semantic_embedding)
        recency_days = max(
            (datetime.now(UTC) - processed.timestamp).total_seconds() / 86400.0,
            0.0,
        )
        prior_confidence = bootstrap_relevance_score(
            recency_days=recency_days,
            frequency_count=snapshot.similar_recent_count,
            entity_ref_count=snapshot.entity_reference_count,
        )
        confidence = min(
            max((0.85 * model_confidence) + (0.15 * prior_confidence), 0.0), 1.0
        )
        return ScoreResult(
            confidence=confidence,
            trace={
                "model_confidence": model_confidence,
                "prior_confidence": prior_confidence,
                "recency_days": recency_days,
                "similar_recent_count": float(snapshot.similar_recent_count),
                "entity_reference_count": float(snapshot.entity_reference_count),
            },
        )
