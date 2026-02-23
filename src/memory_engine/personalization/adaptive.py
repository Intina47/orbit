from __future__ import annotations

import re
import threading
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Any

import numpy as np
from numpy.typing import NDArray

from decision_engine.math_utils import cosine_similarity
from decision_engine.models import MemoryRecord
from decision_engine.storage_protocol import StorageManagerProtocol


@dataclass(frozen=True)
class InferredMemoryCandidate:
    entity_id: str
    event_type: str
    content: str
    summary: str
    confidence: float
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class _PreferenceState:
    concise_score: float = 0.0
    detailed_score: float = 0.0
    updates: int = 0
    last_emitted: str | None = None


class AdaptivePersonalizationEngine:
    """Derive adaptive user-profile memories from repeated patterns and feedback."""

    _TOPIC_CLUSTER_SOURCE_INTENTS = {
        "user_question",
        "user_attempt",
        "assessment_result",
        "learning_progress",
    }
    _FAILURE_SOURCE_INTENTS = {
        "user_question",
        "user_attempt",
        "assessment_result",
    }
    _PROGRESS_SOURCE_INTENTS = {
        "user_attempt",
        "assessment_result",
        "learning_progress",
    }
    _FAILURE_TERMS = {
        "bug",
        "bugs",
        "confused",
        "confusing",
        "error",
        "errors",
        "exception",
        "exceptions",
        "failing",
        "fails",
        "failed",
        "failure",
        "incorrect",
        "mistake",
        "mistakes",
        "stuck",
        "struggle",
        "struggles",
        "wrong",
    }
    _PROGRESS_TERMS = {
        "advanced",
        "complete",
        "completed",
        "correct",
        "correctly",
        "improved",
        "improving",
        "learned",
        "mastered",
        "passed",
        "progress",
        "solved",
        "understands",
    }

    def __init__(
        self,
        storage: StorageManagerProtocol,
        *,
        enabled: bool = True,
        repeat_threshold: int = 3,
        similarity_threshold: float = 0.82,
        window_days: int = 30,
        min_feedback_events: int = 4,
        preference_margin: float = 2.0,
    ) -> None:
        self._storage = storage
        self._enabled = enabled
        self._repeat_threshold = max(repeat_threshold, 2)
        self._similarity_threshold = min(max(similarity_threshold, 0.0), 1.0)
        self._window_days = max(window_days, 1)
        self._min_feedback_events = max(min_feedback_events, 1)
        self._preference_margin = max(preference_margin, 0.1)
        self._emitted_signatures: set[str] = set()
        self._preference_state_by_entity: dict[str, _PreferenceState] = {}
        self._lock = threading.RLock()

    def observe_memory(self, memory: MemoryRecord) -> list[InferredMemoryCandidate]:
        if not self._enabled:
            return []
        intent = memory.intent.strip().lower()
        if intent.startswith("inferred_") or self._is_inferred_memory(memory):
            return []
        if intent not in (
            self._TOPIC_CLUSTER_SOURCE_INTENTS
            | self._FAILURE_SOURCE_INTENTS
            | self._PROGRESS_SOURCE_INTENTS
        ):
            return []

        entity_id = self._primary_entity(memory)
        if entity_id is None:
            return []

        candidates: list[InferredMemoryCandidate] = []
        if intent in self._TOPIC_CLUSTER_SOURCE_INTENTS:
            repeated_topic_candidate = self._infer_repeat_topic_cluster(
                memory=memory,
                entity_id=entity_id,
            )
            if repeated_topic_candidate is not None:
                candidates.append(repeated_topic_candidate)
        if intent in self._FAILURE_SOURCE_INTENTS:
            recurring_failure_candidate = self._infer_recurring_failure(
                memory=memory,
                entity_id=entity_id,
            )
            if recurring_failure_candidate is not None:
                candidates.append(recurring_failure_candidate)
        if intent in self._PROGRESS_SOURCE_INTENTS:
            progress_candidate = self._infer_progress_accumulation(
                memory=memory,
                entity_id=entity_id,
            )
            if progress_candidate is not None:
                candidates.append(progress_candidate)
        return candidates

    def _infer_repeat_topic_cluster(
        self,
        *,
        memory: MemoryRecord,
        entity_id: str,
    ) -> InferredMemoryCandidate | None:
        since_iso = (
            datetime.now(UTC) - timedelta(days=self._window_days)
        ).isoformat()
        history = self._storage.fetch_by_entity_and_intent(
            entity_id=entity_id,
            intent=memory.intent.strip().lower(),
            since_iso=since_iso,
        )
        history = [item for item in history if not self._is_inferred_memory(item)]
        if len(history) < self._repeat_threshold:
            return None

        cluster, average_similarity = self._topic_cluster(
            anchor=memory,
            candidates=history,
        )
        if len(cluster) < self._repeat_threshold:
            return None

        topic_summary = self._representative_summary(cluster)
        signature = self._reserve_signature(
            entity_id=entity_id,
            inference_type="repeat_question_cluster",
            topic_summary=topic_summary,
        )
        if signature is None:
            return None

        confidence = min(
            0.96,
            0.58
            + (0.08 * (len(cluster) - self._repeat_threshold))
            + (0.18 * average_similarity),
        )
        supporting_ids = [item.memory_id for item in cluster[:8]]
        summary = f"{entity_id} repeatedly asks about {topic_summary}"
        relationships = [
            f"{entity_id}->pattern:repeat_question_cluster",
            "inferred:true",
            "inference_type:repeat_question_cluster",
            f"signature:{signature}",
        ]
        relationships.extend(f"derived_from:{memory_id}" for memory_id in supporting_ids)
        content = (
            f"Inferred learning pattern: {entity_id} repeatedly asks about {topic_summary}. "
            "Prioritize concise, step-by-step reinforcement and verify understanding "
            "before moving to more advanced material."
        )
        return InferredMemoryCandidate(
            entity_id=entity_id,
            event_type="inferred_learning_pattern",
            content=content,
            summary=summary,
            confidence=confidence,
            metadata={
                "inferred": True,
                "intent": "inferred_learning_pattern",
                "summary": summary,
                "entities": [entity_id],
                "relationships": relationships,
                "inference_type": "repeat_question_cluster",
            },
        )

    def _infer_recurring_failure(
        self,
        *,
        memory: MemoryRecord,
        entity_id: str,
    ) -> InferredMemoryCandidate | None:
        if not self._is_failure_signal(memory):
            return None
        history = self._recent_entity_memories(
            entity_id=entity_id,
            intents=self._FAILURE_SOURCE_INTENTS,
        )
        history = [item for item in history if self._is_failure_signal(item)]
        if len(history) < self._repeat_threshold:
            return None

        cluster, average_similarity = self._topic_cluster(
            anchor=memory,
            candidates=history,
            min_similarity=self._relaxed_similarity_threshold(),
        )
        cluster = [item for item in cluster if self._is_failure_signal(item)]
        if len(cluster) < self._repeat_threshold:
            return None

        topic_summary = self._representative_summary(cluster)
        signature = self._reserve_signature(
            entity_id=entity_id,
            inference_type="recurring_failure_pattern",
            topic_summary=topic_summary,
        )
        if signature is None:
            return None

        confidence = min(
            0.97,
            0.6
            + (0.07 * (len(cluster) - self._repeat_threshold))
            + (0.16 * average_similarity),
        )
        supporting_ids = [item.memory_id for item in cluster[:8]]
        summary = f"{entity_id} repeatedly struggles with {topic_summary}"
        relationships = [
            f"{entity_id}->pattern:recurring_failure",
            "inferred:true",
            "inference_type:recurring_failure_pattern",
            f"signature:{signature}",
        ]
        relationships.extend(f"derived_from:{memory_id}" for memory_id in supporting_ids)
        content = (
            f"Inferred learning pattern: {entity_id} repeatedly struggles with {topic_summary}. "
            "Prioritize targeted remediation, isolate the failing concept, and verify mastery "
            "with progressively harder practice checks."
        )
        return InferredMemoryCandidate(
            entity_id=entity_id,
            event_type="inferred_learning_pattern",
            content=content,
            summary=summary,
            confidence=confidence,
            metadata={
                "inferred": True,
                "intent": "inferred_learning_pattern",
                "summary": summary,
                "entities": [entity_id],
                "relationships": relationships,
                "inference_type": "recurring_failure_pattern",
            },
        )

    def _infer_progress_accumulation(
        self,
        *,
        memory: MemoryRecord,
        entity_id: str,
    ) -> InferredMemoryCandidate | None:
        if not self._is_progress_signal(memory):
            return None
        history = self._recent_entity_memories(
            entity_id=entity_id,
            intents=self._PROGRESS_SOURCE_INTENTS,
        )
        history = [item for item in history if self._is_progress_signal(item)]
        if len(history) < self._repeat_threshold:
            return None

        cluster, average_similarity = self._topic_cluster(
            anchor=memory,
            candidates=history,
            min_similarity=self._relaxed_similarity_threshold(),
        )
        cluster = [item for item in cluster if self._is_progress_signal(item)]
        if len(cluster) < self._repeat_threshold:
            return None

        topic_summary = self._representative_summary(cluster)
        signature = self._reserve_signature(
            entity_id=entity_id,
            inference_type="progress_accumulation",
            topic_summary=topic_summary,
        )
        if signature is None:
            return None

        confidence = min(
            0.95,
            0.58
            + (0.06 * (len(cluster) - self._repeat_threshold))
            + (0.18 * average_similarity),
        )
        supporting_ids = [item.memory_id for item in cluster[:8]]
        summary = f"{entity_id} progressed in {topic_summary}"
        relationships = [
            f"{entity_id}->progress:accumulated_mastery",
            "inferred:true",
            "inference_type:progress_accumulation",
            f"signature:{signature}",
        ]
        relationships.extend(f"derived_from:{memory_id}" for memory_id in supporting_ids)
        content = (
            f"Inferred progress: {entity_id} has progressed in {topic_summary}. "
            "Adjust tutoring to the next challenge tier and reduce beginner-level repetition."
        )
        return InferredMemoryCandidate(
            entity_id=entity_id,
            event_type="learning_progress",
            content=content,
            summary=summary,
            confidence=confidence,
            metadata={
                "inferred": True,
                "intent": "learning_progress",
                "summary": summary,
                "entities": [entity_id],
                "relationships": relationships,
                "inference_type": "progress_accumulation",
            },
        )

    def observe_feedback(
        self,
        ranked_memories: list[MemoryRecord],
        helpful_memory_ids: set[str],
        outcome_signal: float,
    ) -> list[InferredMemoryCandidate]:
        if not self._enabled:
            return []
        candidates: list[InferredMemoryCandidate] = []
        emitted_for_entity: set[str] = set()

        for memory in ranked_memories:
            if not self._is_assistant_intent(memory.intent):
                continue
            if memory.memory_id not in helpful_memory_ids or outcome_signal <= 0.0:
                continue
            entity_id = self._primary_entity(memory)
            if entity_id is None or entity_id in emitted_for_entity:
                continue
            style = self._style_bucket(memory)
            candidate = self._update_preference_state(
                entity_id=entity_id,
                style=style,
                signal=abs(outcome_signal),
            )
            if candidate is not None:
                candidates.append(candidate)
                emitted_for_entity.add(entity_id)
        return candidates

    def _recent_entity_memories(
        self,
        *,
        entity_id: str,
        intents: set[str],
    ) -> list[MemoryRecord]:
        since = datetime.now(UTC) - timedelta(days=self._window_days)
        filtered: list[MemoryRecord] = []
        for memory in self._storage.list_memories():
            if entity_id not in memory.entities:
                continue
            if memory.created_at < since:
                continue
            if memory.intent.strip().lower() not in intents:
                continue
            if self._is_inferred_memory(memory):
                continue
            filtered.append(memory)
        return filtered

    def _reserve_signature(
        self,
        *,
        entity_id: str,
        inference_type: str,
        topic_summary: str,
    ) -> str | None:
        signature = self._signature(
            entity_id=entity_id,
            inference_type=inference_type,
            topic_summary=topic_summary,
        )
        with self._lock:
            if signature in self._emitted_signatures:
                return None
            if self._signature_exists_in_storage(entity_id=entity_id, signature=signature):
                self._emitted_signatures.add(signature)
                return None
            self._emitted_signatures.add(signature)
        return signature

    def _signature_exists_in_storage(self, *, entity_id: str, signature: str) -> bool:
        signature_marker = f"signature:{signature}"
        for memory in self._storage.list_memories():
            if entity_id not in memory.entities:
                continue
            if signature_marker in memory.relationships:
                return True
        return False

    def _update_preference_state(
        self,
        entity_id: str,
        style: str,
        signal: float,
    ) -> InferredMemoryCandidate | None:
        delta = max(signal, 0.1)
        with self._lock:
            state = self._preference_state_by_entity.setdefault(entity_id, _PreferenceState())
            if style == "concise":
                state.concise_score += delta
            else:
                state.detailed_score += delta
            state.updates += 1

            if state.updates < self._min_feedback_events:
                return None
            margin = state.concise_score - state.detailed_score
            if abs(margin) < self._preference_margin:
                return None
            preferred_style = "concise" if margin > 0 else "detailed"
            if state.last_emitted == preferred_style:
                return None
            state.last_emitted = preferred_style

        confidence = min(0.95, 0.62 + min(abs(margin) / 8.0, 0.3))
        if preferred_style == "concise":
            summary = f"{entity_id} prefers concise explanations"
            content = (
                f"Inferred preference: {entity_id} responds better to concise explanations. "
                "Keep responses short, concrete, and step-by-step."
            )
        else:
            summary = f"{entity_id} prefers detailed explanations"
            content = (
                f"Inferred preference: {entity_id} responds better to detailed explanations. "
                "Include fuller context, rationale, and worked examples."
            )
        return InferredMemoryCandidate(
            entity_id=entity_id,
            event_type="inferred_preference",
            content=content,
            summary=summary,
            confidence=confidence,
            metadata={
                "inferred": True,
                "intent": "inferred_preference",
                "summary": summary,
                "entities": [entity_id],
                "relationships": [
                    f"{entity_id}->preference:explanation_style={preferred_style}"
                ],
                "inference_type": "feedback_preference_shift",
            },
        )

    def _topic_cluster(
        self,
        anchor: MemoryRecord,
        candidates: list[MemoryRecord],
        min_similarity: float | None = None,
    ) -> tuple[list[MemoryRecord], float]:
        anchor_vector = np.asarray(anchor.semantic_embedding, dtype=np.float32)
        scored: list[tuple[MemoryRecord, float]] = []
        threshold = (
            self._similarity_threshold
            if min_similarity is None
            else min(max(min_similarity, 0.0), 1.0)
        )
        for candidate in candidates:
            similarity = self._semantic_similarity(anchor, candidate, anchor_vector)
            if similarity >= threshold:
                scored.append((candidate, similarity))
        if not scored:
            return [], 0.0
        scored.sort(key=lambda item: item[1], reverse=True)
        cluster = [item[0] for item in scored]
        average_similarity = float(sum(item[1] for item in scored) / len(scored))
        return cluster, average_similarity

    @staticmethod
    def _semantic_similarity(
        anchor: MemoryRecord,
        candidate: MemoryRecord,
        anchor_vector: NDArray[np.float32],
    ) -> float:
        lexical_similarity = AdaptivePersonalizationEngine._lexical_similarity(
            anchor,
            candidate,
        )
        candidate_vector = np.asarray(candidate.semantic_embedding, dtype=np.float32)
        if (
            anchor_vector.size > 0
            and candidate_vector.size > 0
            and anchor_vector.shape == candidate_vector.shape
        ):
            vector_similarity = float(cosine_similarity(anchor_vector, candidate_vector))
            return max(vector_similarity, lexical_similarity)
        if anchor.semantic_key == candidate.semantic_key:
            return 1.0
        return lexical_similarity

    @staticmethod
    def _lexical_similarity(anchor: MemoryRecord, candidate: MemoryRecord) -> float:
        anchor_tokens = AdaptivePersonalizationEngine._tokens(anchor)
        candidate_tokens = AdaptivePersonalizationEngine._tokens(candidate)
        if not anchor_tokens or not candidate_tokens:
            return 0.0
        union = anchor_tokens.union(candidate_tokens)
        if not union:
            return 0.0
        intersection = anchor_tokens.intersection(candidate_tokens)
        return float(len(intersection)) / float(len(union))

    @staticmethod
    def _representative_summary(cluster: list[MemoryRecord]) -> str:
        if not cluster:
            return "current learning topic"
        counts: dict[str, tuple[int, str]] = {}
        for memory in cluster:
            cleaned = " ".join(memory.summary.split()).strip()
            if not cleaned:
                continue
            key = cleaned.lower()
            current = counts.get(key)
            if current is None:
                counts[key] = (1, cleaned)
            else:
                counts[key] = (current[0] + 1, current[1])
        if not counts:
            return "current learning topic"
        selected = sorted(
            counts.values(),
            key=lambda item: (item[0], len(item[1])),
            reverse=True,
        )[0][1]
        if len(selected) <= 140:
            return selected
        return selected[:137].rstrip() + "..."

    @staticmethod
    def _primary_entity(memory: MemoryRecord) -> str | None:
        for entity in memory.entities:
            cleaned = entity.strip()
            if cleaned:
                return cleaned
        return None

    @staticmethod
    def _signature(entity_id: str, inference_type: str, topic_summary: str) -> str:
        normalized_topic = re.sub(r"\s+", " ", topic_summary.strip().lower())
        return f"{entity_id}|{inference_type}|{normalized_topic}"

    @classmethod
    def _is_failure_signal(cls, memory: MemoryRecord) -> bool:
        tokens = cls._tokens(memory)
        if not tokens:
            return False
        return bool(tokens.intersection(cls._FAILURE_TERMS))

    @classmethod
    def _is_progress_signal(cls, memory: MemoryRecord) -> bool:
        tokens = cls._tokens(memory)
        if not tokens:
            return False
        if bool(tokens.intersection(cls._FAILURE_TERMS)):
            return False
        return bool(tokens.intersection(cls._PROGRESS_TERMS))

    @staticmethod
    def _tokens(memory: MemoryRecord) -> set[str]:
        text = f"{memory.summary} {memory.content}".lower()
        return set(re.findall(r"[a-z0-9]+", text))

    @staticmethod
    def _is_inferred_memory(memory: MemoryRecord) -> bool:
        normalized_intent = memory.intent.strip().lower()
        if normalized_intent.startswith("inferred_"):
            return True
        for relation in memory.relationships:
            normalized_relation = relation.strip().lower()
            if normalized_relation == "inferred:true":
                return True
            if normalized_relation.startswith("inference_type:"):
                return True
            if normalized_relation.startswith("signature:"):
                return True
        return False

    def _relaxed_similarity_threshold(self) -> float:
        return max(0.1, self._similarity_threshold * 0.12)

    @staticmethod
    def _style_bucket(memory: MemoryRecord) -> str:
        size = len(memory.content.split())
        if size <= 160:
            return "concise"
        return "detailed"

    @staticmethod
    def _is_assistant_intent(intent: str) -> bool:
        normalized = intent.strip().lower()
        return normalized.startswith("assistant_") or normalized == "assistant_message"
