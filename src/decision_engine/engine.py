from __future__ import annotations

from datetime import UTC, datetime

from decision_engine.config import EngineConfig
from decision_engine.decay_learner import DecayLearner
from decision_engine.importance_model import ImportanceModel
from decision_engine.models import (
    MemoryRecord,
    OutcomeFeedback,
    RawEvent,
    RetrievedMemory,
    StorageDecision,
    StorageTier,
)
from decision_engine.observability import JsonLogger
from decision_engine.retrieval_ranker import RetrievalRanker
from decision_engine.semantic_encoding import (
    ContextSemanticProvider,
    DeterministicEmbeddingProvider,
    EmbeddingProvider,
    SemanticEncoder,
    SemanticProvider,
)
from decision_engine.storage_manager import SQLiteStorageManager


class DecisionEngine:
    """Main orchestrator for encoding, storing, retrieving, and learning."""

    def __init__(
        self,
        config: EngineConfig | None = None,
        embedding_provider: EmbeddingProvider | None = None,
        semantic_provider: SemanticProvider | None = None,
    ) -> None:
        self.config = config or EngineConfig()
        self._log = JsonLogger()

        resolved_embedding_provider = (
            embedding_provider
            or DeterministicEmbeddingProvider(self.config.embedding_dim)
        )
        resolved_semantic_provider = semantic_provider or ContextSemanticProvider()
        self.encoder = SemanticEncoder(
            resolved_embedding_provider, resolved_semantic_provider
        )

        self.importance_model = ImportanceModel(
            embedding_dim=self.config.embedding_dim,
            learning_rate=self.config.importance_learning_rate,
        )
        self.decay_learner = DecayLearner(learning_rate=self.config.decay_learning_rate)
        self.ranker = RetrievalRanker(
            learning_rate=self.config.ranker_learning_rate,
            min_training_samples=self.config.ranker_min_training_samples,
            training_batch_size=self.config.ranker_training_batch_size,
        )
        self.storage = SQLiteStorageManager(
            self.config.sqlite_path,
            max_content_chars=self.config.max_content_chars,
            assistant_max_content_chars=self.config.assistant_max_content_chars,
            store_raw_embedding=self.config.store_raw_embedding,
        )

    def process_event(
        self, event: RawEvent
    ) -> tuple[StorageDecision, MemoryRecord | None]:
        encoded = self.encoder.encode_event(event)
        confidence = self.importance_model.predict(encoded.semantic_embedding)
        tier = self._select_storage_tier(confidence)
        decision = StorageDecision(
            should_store=tier is not StorageTier.DISCARD,
            tier=tier,
            confidence=confidence,
            rationale="importance model prediction",
            trace={
                "semantic_key": encoded.semantic_key,
                "intent": encoded.understanding.intent,
                "entities": encoded.understanding.entities,
            },
        )

        stored_memory: MemoryRecord | None = None
        if decision.should_store:
            stored_memory = self.storage.store(encoded, decision)
            decision.memory_id = stored_memory.memory_id
            self._log.info(
                "memory_stored",
                memory_id=stored_memory.memory_id,
                confidence=confidence,
                tier=tier.value,
            )
        else:
            self._log.info(
                "memory_discarded", event_id=event.event_id, confidence=confidence
            )

        return decision, stored_memory

    def retrieve(
        self, query: str, top_k: int = 5, candidate_pool_size: int | None = None
    ) -> list[RetrievedMemory]:
        query_embedding = self.encoder.encode_query(query)
        pool_size = candidate_pool_size or max(top_k * 2, 20)
        candidates = self.storage.search_candidates(query_embedding, top_k=pool_size)
        now = datetime.now(UTC)
        ranked = self.ranker.rank(query_embedding, candidates, now=now)
        selected = ranked[:top_k]
        for item in selected:
            self.storage.update_retrieval(item.memory.memory_id)
        self._log.info("memory_retrieved", query=query, returned=len(selected))
        return selected

    def record_feedback(self, feedback: OutcomeFeedback) -> dict[str, float | None]:
        now = datetime.now(UTC)
        query_embedding = self.encoder.encode_query(feedback.query)
        ranked_memories = self.storage.fetch_by_ids(feedback.ranked_memory_ids)
        helpful_ids = set(feedback.helpful_memory_ids)

        rank_loss = self.ranker.learn_from_feedback(
            query_embedding=query_embedding,
            candidates=ranked_memories,
            helpful_memory_ids=helpful_ids,
            now=now,
        )

        importance_loss: float | None = None
        if ranked_memories:
            embeddings = [memory.semantic_embedding for memory in ranked_memories]
            outcomes = [
                (
                    feedback.outcome_signal
                    if memory.memory_id in helpful_ids
                    else -abs(feedback.outcome_signal)
                )
                for memory in ranked_memories
            ]
            importance_loss = self.importance_model.train_batch(embeddings, outcomes)

        for memory in ranked_memories:
            age_days = max((now - memory.created_at).total_seconds() / 86400.0, 0.0)
            was_helpful = memory.memory_id in helpful_ids
            self.decay_learner.record_outcome(
                memory.semantic_key, age_days, was_helpful
            )
            memory_signal = (
                feedback.outcome_signal
                if was_helpful
                else -abs(feedback.outcome_signal)
            )
            self.storage.update_outcome(memory.memory_id, memory_signal)
        self.decay_learner.learn()

        self._log.info(
            "feedback_recorded",
            ranked_count=len(ranked_memories),
            helpful_count=len(helpful_ids),
            rank_loss=rank_loss,
            importance_loss=importance_loss,
        )
        return {"rank_loss": rank_loss, "importance_loss": importance_loss}

    def estimate_memory_relevance(self, memory: MemoryRecord) -> float:
        age_days = max(
            (datetime.now(UTC) - memory.created_at).total_seconds() / 86400.0, 0.0
        )
        return self.decay_learner.predict_relevance(
            memory.semantic_key, age_days, memory.latest_importance
        )

    def memory_count(self) -> int:
        return self.storage.count_memories()

    def close(self) -> None:
        self.storage.close()

    def _select_storage_tier(self, confidence: float) -> StorageTier:
        persistent = self.config.persistent_confidence_prior
        ephemeral = self.config.ephemeral_confidence_prior
        if confidence >= persistent:
            return StorageTier.PERSISTENT
        if confidence >= ephemeral:
            return StorageTier.EPHEMERAL
        return StorageTier.DISCARD
