from __future__ import annotations

from memory_engine.models.memory_state import MemorySnapshot
from memory_engine.models.processed_event import ProcessedEvent
from memory_engine.models.storage_decision import StorageDecision
from memory_engine.stage2_decision.compression import CompressionPlanner
from memory_engine.stage2_decision.decay import DecayPolicyAssigner
from memory_engine.stage2_decision.scoring import LearnedRelevanceScorer


class DecisionLogic:
    """Stage 2 decision logic with learned scoring and decay assignment."""

    def __init__(
        self,
        scorer: LearnedRelevanceScorer,
        decay_assigner: DecayPolicyAssigner,
        compression_planner: CompressionPlanner,
        persistent_threshold: float,
        ephemeral_threshold: float,
    ) -> None:
        self._scorer = scorer
        self._decay_assigner = decay_assigner
        self._compression_planner = compression_planner
        self._persistent_threshold = persistent_threshold
        self._ephemeral_threshold = ephemeral_threshold

    def decide(
        self, processed: ProcessedEvent, snapshot: MemorySnapshot
    ) -> StorageDecision:
        score = self._scorer.score(processed, snapshot)
        decay_rate, half_life = self._decay_assigner.assign(processed)
        if score.confidence >= self._persistent_threshold:
            tier = "persistent"
            store = True
        elif score.confidence >= self._ephemeral_threshold:
            tier = "ephemeral"
            store = True
        else:
            tier = "discard"
            store = False
        return StorageDecision(
            store=store,
            storage_tier=tier,
            confidence=score.confidence,
            decay_rate=decay_rate,
            decay_half_life=half_life,
            should_compress=(snapshot.similar_recent_count + 1)
            >= self._compression_planner.min_count,
            trace=score.trace,
        )
