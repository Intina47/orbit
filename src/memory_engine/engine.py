from __future__ import annotations

import json
import os
from datetime import UTC, datetime
from pathlib import Path

from decision_engine.decay_learner import DecayLearner
from decision_engine.importance_model import ImportanceModel
from decision_engine.models import (
    MemoryRecord,
    OutcomeFeedback,
    RetrievedMemory,
    StorageTier,
)
from decision_engine.models import (
    StorageDecision as CoreStorageDecision,
)
from decision_engine.retrieval_ranker import RetrievalRanker
from decision_engine.storage_manager import SQLiteStorageManager
from decision_engine.storage_protocol import StorageManagerProtocol
from decision_engine.storage_sqlalchemy import SQLAlchemyStorageManager
from memory_engine.config import EngineConfig
from memory_engine.logger import EngineLogger
from memory_engine.models.event import Event
from memory_engine.models.memory_state import MemorySnapshot
from memory_engine.models.processed_event import ProcessedEvent
from memory_engine.models.storage_decision import StorageDecision
from memory_engine.personalization import (
    AdaptivePersonalizationEngine,
    InferredMemoryCandidate,
)
from memory_engine.stage1_input.embedding import build_embedding_provider
from memory_engine.stage1_input.extractors import build_semantic_provider
from memory_engine.stage1_input.processor import InputProcessor
from memory_engine.stage2_decision.compression import CompressionPlanner
from memory_engine.stage2_decision.decay import DecayPolicyAssigner
from memory_engine.stage2_decision.logic import DecisionLogic
from memory_engine.stage2_decision.scoring import LearnedRelevanceScorer
from memory_engine.stage3_learning.loop import LearningLoop
from memory_engine.stage3_learning.weight_updater import WeightUpdater
from memory_engine.storage.retrieval import RetrievalService
from memory_engine.storage.vector_store import VectorStore


class DecisionEngine:
    """v1-compatible orchestrator over the intelligent-first core modules."""

    def __init__(
        self, db_path: str | None = None, config: EngineConfig | None = None
    ) -> None:
        loaded = config or EngineConfig.from_env()
        if db_path is not None:
            loaded.sqlite_path = db_path
        self.config = loaded

        self._log = EngineLogger()
        self._metrics: dict[str, float] = {
            "events_received": 0.0,
            "events_stored": 0.0,
            "events_discarded": 0.0,
            "compression_events": 0.0,
            "feedback_events": 0.0,
        }
        self._ops_since_metrics_flush = 0

        embedding_provider = build_embedding_provider(
            self.config.embedding_dim,
            provider_name=os.getenv("MDE_EMBEDDING_PROVIDER"),
        )
        semantic_provider = build_semantic_provider(
            use_openai=os.getenv("USE_LLM_SEMANTICS", "false").lower()
            in {"true", "1", "yes"},
            provider_name=os.getenv("MDE_SEMANTIC_PROVIDER"),
        )
        self.input_processor = InputProcessor(embedding_provider, semantic_provider)

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
        self.storage: StorageManagerProtocol
        if self.config.database_url:
            self.storage = SQLAlchemyStorageManager(
                self.config.database_url,
                max_content_chars=self.config.max_content_chars,
                assistant_max_content_chars=self.config.assistant_max_content_chars,
                store_raw_embedding=self.config.store_raw_embedding,
            )
        else:
            self.storage = SQLiteStorageManager(
                self.config.sqlite_path,
                max_content_chars=self.config.max_content_chars,
                assistant_max_content_chars=self.config.assistant_max_content_chars,
                store_raw_embedding=self.config.store_raw_embedding,
            )
        self._persist_vector_index = (
            self.config.database_url is not None
            or self.config.sqlite_path != ":memory:"
        )
        vector_index_path = (
            str(Path(self.config.sqlite_path).with_suffix(".idx"))
            if self._persist_vector_index
            else "runtime_vector_index.idx"
        )
        self.vector_store = VectorStore(
            embedding_dim=self.config.embedding_dim,
            index_path=vector_index_path,
        )

        self.compression_planner = CompressionPlanner(
            min_count=self.config.compression_min_count,
            window_days=self.config.compression_window_days,
            max_summary_items=self.config.compression_max_items_in_summary,
        )
        self.decision_logic = DecisionLogic(
            scorer=LearnedRelevanceScorer(self.importance_model),
            decay_assigner=DecayPolicyAssigner(self.decay_learner),
            compression_planner=self.compression_planner,
            persistent_threshold=self.config.persistent_confidence_prior,
            ephemeral_threshold=self.config.ephemeral_confidence_prior,
        )
        self.retrieval_service = RetrievalService(
            storage=self.storage,
            ranker=self.ranker,
            encoder=self.input_processor.encoder,
            vector_store=self.vector_store,
            assistant_response_max_share=self.config.assistant_response_max_share,
        )
        self.learning_loop = LearningLoop(
            storage=self.storage,
            ranker=self.ranker,
            weight_updater=WeightUpdater(self.importance_model, self.decay_learner),
        )
        self.personalization = AdaptivePersonalizationEngine(
            storage=self.storage,
            enabled=self.config.enable_adaptive_personalization,
            repeat_threshold=self.config.personalization_repeat_threshold,
            similarity_threshold=self.config.personalization_similarity_threshold,
            window_days=self.config.personalization_window_days,
            min_feedback_events=self.config.personalization_min_feedback_events,
            preference_margin=self.config.personalization_preference_margin,
            inferred_ttl_days=self.config.personalization_inferred_ttl_days,
            inferred_refresh_days=self.config.personalization_inferred_refresh_days,
        )
        self._lifecycle_scan_interval_seconds = max(
            0,
            int(self.config.personalization_lifecycle_check_interval_seconds),
        )
        self._last_lifecycle_scan_at: datetime | None = None
        self._total_memories = 0
        self._entity_reference_counts: dict[tuple[str, str], int] = {}
        self._entity_memory_ids: dict[tuple[str, str], set[str]] = {}
        self._recent_key_timestamps: dict[tuple[str, str, str], list[datetime]] = {}
        self._warm_cache_from_storage()

    def process_input(self, event: Event) -> ProcessedEvent:
        self._metrics["events_received"] += 1
        return self.input_processor.process(event)

    def make_storage_decision(
        self,
        processed: ProcessedEvent,
        account_key: str | None = None,
    ) -> StorageDecision:
        snapshot = self._memory_snapshot(processed, account_key=account_key)
        return self.decision_logic.decide(processed, snapshot)

    def store_memory(
        self,
        processed: ProcessedEvent,
        decision: StorageDecision,
        account_key: str | None = None,
    ) -> MemoryRecord | None:
        self._run_personalization_lifecycle(account_key=account_key)
        if not decision.store:
            self._metrics["events_discarded"] += 1
            return None

        stored = self._store_core_memory(
            processed=processed,
            decision=decision,
            compressed=False,
            original_count=1,
            account_key=account_key,
        )
        self._register_stored_memory(stored)
        self._metrics["events_stored"] += 1
        self._store_inferred_candidates(
            self.personalization.observe_memory(stored, account_key=account_key),
            account_key=account_key,
        )

        if decision.should_compress:
            self._maybe_compress_cluster(processed, account_key=account_key)
        self._schedule_metrics_flush()
        return stored

    def retrieve(
        self,
        query: str,
        top_k: int = 5,
        account_key: str | None = None,
    ) -> list[RetrievedMemory]:
        return self.retrieval_service.retrieve(
            query,
            top_k=top_k,
            account_key=account_key,
        )

    def record_outcome(self, memory_id: str, outcome: str) -> dict[str, float | None]:
        signal = 1.0 if outcome.lower() == "success" else -1.0
        feedback = OutcomeFeedback(
            query=f"memory:{memory_id}",
            ranked_memory_ids=[memory_id],
            helpful_memory_ids=[memory_id] if signal > 0 else [],
            outcome_signal=signal,
        )
        result = self.record_feedback(
            query=feedback.query,
            ranked_memory_ids=feedback.ranked_memory_ids,
            helpful_memory_ids=feedback.helpful_memory_ids,
            outcome_signal=feedback.outcome_signal,
        )
        return result

    def record_feedback(
        self,
        query: str,
        ranked_memory_ids: list[str],
        helpful_memory_ids: list[str],
        outcome_signal: float = 1.0,
        account_key: str | None = None,
    ) -> dict[str, float | None]:
        self._run_personalization_lifecycle(account_key=account_key)
        feedback = OutcomeFeedback(
            query=query,
            ranked_memory_ids=ranked_memory_ids,
            helpful_memory_ids=helpful_memory_ids,
            outcome_signal=outcome_signal,
        )
        query_embedding = self.input_processor.encoder.encode_query(query).tolist()
        self._metrics["feedback_events"] += 1
        result = self.learning_loop.record_feedback(
            feedback,
            query_embedding=query_embedding,
            account_key=account_key,
        )
        ranked_memories = self.storage.fetch_by_ids(
            ranked_memory_ids,
            account_key=account_key,
        )
        self._store_inferred_candidates(
            self.personalization.observe_feedback(
                ranked_memories=ranked_memories,
                helpful_memory_ids=set(helpful_memory_ids),
                outcome_signal=outcome_signal,
                account_key=account_key,
            ),
            account_key=account_key,
        )
        self._schedule_metrics_flush()
        return result

    def get_memory(
        self,
        entity_id: str | None = None,
        account_key: str | None = None,
    ) -> list[MemoryRecord]:
        records = self.storage.list_memories(account_key=account_key)
        if entity_id is not None:
            records = [record for record in records if entity_id in record.entities]
        output = []
        for record in records:
            half_life = self._half_life_for_key(record.semantic_key)
            output.append(record.model_copy(update={"decay_half_life_days": half_life}))
        return output

    def memory_count(self, account_key: str | None = None) -> int:
        return self.storage.count_memories(account_key=account_key)

    def memory_ids_for_entity(
        self,
        entity_id: str,
        account_key: str | None = None,
    ) -> list[str]:
        scope_key = self._entity_scope_key(account_key=account_key, entity_id=entity_id)
        return sorted(self._entity_memory_ids.get(scope_key, set()))

    def close(self) -> None:
        self._write_metrics()
        if self._persist_vector_index:
            self.vector_store.save()
        self.storage.close()

    def _store_core_memory(
        self,
        processed: ProcessedEvent,
        decision: StorageDecision,
        compressed: bool,
        original_count: int,
        account_key: str | None = None,
    ) -> MemoryRecord:
        encoded = self.input_processor.to_encoded_event(processed)
        tier = self._tier_from_string(decision.storage_tier)
        core_decision = CoreStorageDecision(
            should_store=decision.store,
            tier=tier,
            confidence=decision.confidence,
            rationale=decision.rationale,
            trace={
                **decision.trace,
                "is_compressed": compressed,
                "original_count": original_count,
            },
        )
        normalized_account_key = self._normalize_account_key(account_key)
        stored = self.storage.store(
            encoded,
            core_decision,
            account_key=normalized_account_key,
        )
        self.vector_store.add(stored.memory_id, stored.semantic_embedding)
        return stored

    def _maybe_compress_cluster(
        self,
        processed: ProcessedEvent,
        account_key: str | None = None,
    ) -> None:
        since_iso = self.compression_planner.since_iso()
        candidates = self.storage.fetch_by_entity_and_intent(
            entity_id=processed.entity_id,
            intent=processed.event_type,
            since_iso=since_iso,
            account_key=account_key,
        )
        candidates = [memory for memory in candidates if not memory.is_compressed]
        plan = self.compression_planner.plan(processed, candidates)
        if not plan.should_compress:
            return

        self._delete_memories(plan.memory_ids_to_replace, account_key=account_key)
        compressed_event = Event(
            timestamp=processed.timestamp,
            entity_id=processed.entity_id,
            event_type=processed.event_type,
            description=plan.summary_text,
            metadata={
                "summary": plan.summary_text,
                "intent": processed.event_type,
                "entities": [processed.entity_id],
                "compressed": True,
                "compressed_original_count": plan.original_count,
            },
        )
        compressed_processed = self.input_processor.process(compressed_event)
        try:
            confidence_seed = float(processed.context.get("importance", 0.8))
        except (TypeError, ValueError):
            confidence_seed = 0.8
        compressed_decision = StorageDecision(
            store=True,
            storage_tier="persistent",
            confidence=max(0.8, confidence_seed),
            decay_rate=1.0 / max(plan.original_count, 1),
            decay_half_life=float(plan.original_count),
            should_compress=False,
            rationale="compression-replacement",
            trace={"compression": "cluster"},
        )
        compressed_record = self._store_core_memory(
            # The compressed record replaces the cluster and re-enters indexes.
            processed=compressed_processed,
            decision=compressed_decision,
            compressed=True,
            original_count=plan.original_count,
            account_key=account_key,
        )
        self._register_stored_memory(compressed_record)
        self._metrics["compression_events"] += 1
        self._log.warning(
            "compression_triggered",
            entity_id=processed.entity_id,
            event_type=processed.event_type,
            original_count=plan.original_count,
        )

    def _memory_snapshot(
        self,
        processed: ProcessedEvent,
        account_key: str | None = None,
    ) -> MemorySnapshot:
        scope_key = self._entity_scope_key(
            account_key=account_key,
            entity_id=processed.entity_id,
        )
        entity_reference_count = self._entity_reference_counts.get(scope_key, 0)
        similar_recent_count = self._similar_recent_count(
            entity_id=processed.entity_id,
            intent=processed.event_type,
            reference_time=processed.timestamp,
            account_key=account_key,
        )
        return MemorySnapshot(
            total_memories=self._total_memories,
            entity_reference_count=entity_reference_count,
            similar_recent_count=similar_recent_count,
            generated_at=datetime.now(UTC),
            metadata={"event_type": processed.event_type},
        )

    def _store_inferred_candidates(
        self,
        candidates: list[InferredMemoryCandidate],
        account_key: str | None = None,
    ) -> None:
        if not candidates:
            return
        for candidate in candidates:
            self._store_inferred_candidate(candidate, account_key=account_key)

    def _store_inferred_candidate(
        self,
        candidate: InferredMemoryCandidate,
        account_key: str | None = None,
    ) -> None:
        if candidate.supersedes_memory_ids:
            removed = self._delete_memories(
                list(candidate.supersedes_memory_ids),
                account_key=account_key,
            )
            if removed:
                self._metrics["inferred_memories_superseded"] = (
                    self._metrics.get("inferred_memories_superseded", 0.0)
                    + float(len(removed))
                )
                self._log.info(
                    "adaptive_inferred_memories_superseded",
                    entity_id=candidate.entity_id,
                    event_type=candidate.event_type,
                    removed_count=len(removed),
                )
        metadata = dict(candidate.metadata)
        relationships = [str(item) for item in metadata.get("relationships", [])]
        if candidate.supersedes_memory_ids:
            relationships.extend(
                f"supersedes:{memory_id}" for memory_id in candidate.supersedes_memory_ids
            )
        metadata["relationships"] = _unique_preserving_order(relationships)
        metadata.setdefault("summary", candidate.summary)
        metadata.setdefault("intent", candidate.event_type)
        metadata.setdefault("entities", [candidate.entity_id])
        metadata.setdefault("inferred", True)
        event = Event(
            timestamp=datetime.now(UTC),
            entity_id=candidate.entity_id,
            event_type=candidate.event_type,
            description=candidate.content,
            metadata=metadata,
        )
        processed = self.input_processor.process(event)
        inferred_decision = StorageDecision(
            store=True,
            storage_tier="persistent",
            confidence=max(min(candidate.confidence, 0.99), 0.5),
            decay_rate=1.0 / 90.0,
            decay_half_life=90.0,
            should_compress=False,
            rationale="adaptive_personalization_inference",
            trace={"inferred": True},
        )
        stored = self._store_core_memory(
            processed=processed,
            decision=inferred_decision,
            compressed=False,
            original_count=1,
            account_key=account_key,
        )
        self._register_stored_memory(stored)
        self._metrics["events_stored"] += 1
        self._metrics["inferred_memories_created"] = (
            self._metrics.get("inferred_memories_created", 0.0) + 1.0
        )
        self._log.info(
            "adaptive_inferred_memory_stored",
            entity_id=candidate.entity_id,
            event_type=candidate.event_type,
            confidence=round(candidate.confidence, 3),
            memory_id=stored.memory_id,
        )

    def _delete_memories(
        self,
        memory_ids: list[str],
        account_key: str | None = None,
    ) -> list[MemoryRecord]:
        unique_ids = sorted({memory_id for memory_id in memory_ids if memory_id})
        if not unique_ids:
            return []
        existing = self.storage.fetch_by_ids(unique_ids, account_key=account_key)
        if not existing:
            return []
        existing_ids = [memory.memory_id for memory in existing]
        self.storage.delete_memories(existing_ids, account_key=account_key)
        self.vector_store.remove_many(existing_ids)
        for memory in existing:
            self._unregister_stored_memory(memory)
        self.personalization.notify_memories_deleted(existing)
        return existing

    def _run_personalization_lifecycle(self, account_key: str | None = None) -> None:
        now = datetime.now(UTC)
        if (
            self._lifecycle_scan_interval_seconds > 0
            and self._last_lifecycle_scan_at is not None
            and (now - self._last_lifecycle_scan_at).total_seconds()
            < self._lifecycle_scan_interval_seconds
        ):
            return
        self._last_lifecycle_scan_at = now
        expired_ids = self.personalization.expired_inferred_memory_ids(
            account_key=account_key,
        )
        if not expired_ids:
            return
        removed = self._delete_memories(expired_ids, account_key=account_key)
        if not removed:
            return
        self._metrics["inferred_memories_expired"] = (
            self._metrics.get("inferred_memories_expired", 0.0)
            + float(len(removed))
        )
        self._log.info(
            "adaptive_inferred_memories_expired",
            removed_count=len(removed),
        )

    def _write_metrics(self) -> None:
        payload = {
            "generated_at": datetime.now(UTC).isoformat(),
            "metrics": self._metrics,
            "storage_ratio": self._safe_ratio(
                self._metrics["events_stored"], self._metrics["events_received"]
            ),
        }
        path = Path(self.config.metrics_path)
        path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    def _schedule_metrics_flush(self) -> None:
        self._ops_since_metrics_flush += 1
        if self._ops_since_metrics_flush >= self.config.metrics_flush_interval:
            self._write_metrics()
            self._ops_since_metrics_flush = 0

    @staticmethod
    def _safe_ratio(numerator: float, denominator: float) -> float:
        if denominator <= 0:
            return 0.0
        return numerator / denominator

    def _half_life_for_key(self, semantic_key: str) -> float:
        rate = self.decay_learner.predict_decay_rate(semantic_key)
        if rate <= 0:
            return float("inf")
        return 0.6931471805599453 / rate

    @staticmethod
    def _tier_from_string(value: str) -> StorageTier:
        normalized = value.strip().lower()
        if normalized == "persistent":
            return StorageTier.PERSISTENT
        if normalized == "ephemeral":
            return StorageTier.EPHEMERAL
        return StorageTier.DISCARD

    def _warm_cache_from_storage(self) -> None:
        for record in self.storage.list_memories():
            self.vector_store.add(record.memory_id, record.semantic_embedding)
            self._register_stored_memory(record)

    def _register_stored_memory(self, memory: MemoryRecord) -> None:
        self._total_memories += 1
        account_key = self._normalize_account_key(memory.account_key)
        for entity in set(memory.entities):
            scope_key = self._entity_scope_key(account_key=account_key, entity_id=entity)
            self._entity_reference_counts[scope_key] = (
                self._entity_reference_counts.get(scope_key, 0) + 1
            )
            self._entity_memory_ids.setdefault(scope_key, set()).add(memory.memory_id)
        key = self._memory_key(
            account_key=account_key,
            primary_entity=memory.entities[0] if memory.entities else "",
            intent=memory.intent,
        )
        self._recent_key_timestamps.setdefault(key, []).append(memory.created_at)

    def _unregister_stored_memory(self, memory: MemoryRecord) -> None:
        self._total_memories = max(0, self._total_memories - 1)
        account_key = self._normalize_account_key(memory.account_key)
        for entity in set(memory.entities):
            scope_key = self._entity_scope_key(account_key=account_key, entity_id=entity)
            current = self._entity_reference_counts.get(scope_key, 0)
            self._entity_reference_counts[scope_key] = max(0, current - 1)
            ids = self._entity_memory_ids.get(scope_key)
            if ids is not None:
                ids.discard(memory.memory_id)
                if not ids:
                    self._entity_memory_ids.pop(scope_key, None)
        key = self._memory_key(
            account_key=account_key,
            primary_entity=memory.entities[0] if memory.entities else "",
            intent=memory.intent,
        )
        timestamps = self._recent_key_timestamps.get(key, [])
        if timestamps:
            self._recent_key_timestamps[key] = timestamps[1:]

    @staticmethod
    def _memory_key(
        account_key: str,
        primary_entity: str,
        intent: str,
    ) -> tuple[str, str, str]:
        return (account_key, primary_entity, intent)

    def _similar_recent_count(
        self,
        entity_id: str,
        intent: str,
        reference_time: datetime,
        account_key: str | None = None,
    ) -> int:
        key = self._memory_key(
            account_key=self._normalize_account_key(account_key),
            primary_entity=entity_id,
            intent=intent,
        )
        timestamps = self._recent_key_timestamps.get(key, [])
        window_start = reference_time.timestamp() - (
            self.config.compression_window_days * 86400
        )
        filtered = [ts for ts in timestamps if ts.timestamp() >= window_start]
        self._recent_key_timestamps[key] = filtered
        return len(filtered)

    @staticmethod
    def _normalize_account_key(account_key: str | None) -> str:
        if account_key is None:
            return "default"
        normalized = account_key.strip()
        return normalized or "default"

    def _entity_scope_key(
        self,
        *,
        account_key: str | None,
        entity_id: str,
    ) -> tuple[str, str]:
        return (self._normalize_account_key(account_key), entity_id)


def _unique_preserving_order(values: list[str]) -> list[str]:
    output: list[str] = []
    seen: set[str] = set()
    for value in values:
        normalized = value.strip()
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        output.append(normalized)
    return output
