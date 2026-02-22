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

    _REPETITION_SOURCE_INTENTS = {
        "user_question",
        "user_attempt",
        "assessment_result",
        "learning_progress",
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
        if intent.startswith("inferred_"):
            return []
        if intent not in self._REPETITION_SOURCE_INTENTS:
            return []

        entity_id = self._primary_entity(memory)
        if entity_id is None:
            return []

        since_iso = (
            datetime.now(UTC) - timedelta(days=self._window_days)
        ).isoformat()
        history = self._storage.fetch_by_entity_and_intent(
            entity_id=entity_id,
            intent=intent,
            since_iso=since_iso,
        )
        if len(history) < self._repeat_threshold:
            return []

        cluster, average_similarity = self._topic_cluster(anchor=memory, candidates=history)
        if len(cluster) < self._repeat_threshold:
            return []

        topic_summary = self._representative_summary(cluster)
        signature = self._signature(
            entity_id=entity_id,
            inference_type="repeat_question_cluster",
            topic_summary=topic_summary,
        )
        with self._lock:
            if signature in self._emitted_signatures:
                return []
            self._emitted_signatures.add(signature)

        confidence = min(
            0.96,
            0.58
            + (0.08 * (len(cluster) - self._repeat_threshold))
            + (0.18 * average_similarity),
        )
        supporting_ids = [item.memory_id for item in cluster[:8]]
        summary = f"{entity_id} repeatedly asks about {topic_summary}"
        relationships = [f"{entity_id}->pattern:repeat_question_cluster"]
        relationships.extend(f"derived_from:{memory_id}" for memory_id in supporting_ids)
        content = (
            f"Inferred learning pattern: {entity_id} repeatedly asks about {topic_summary}. "
            "Prioritize concise, step-by-step reinforcement and verify understanding "
            "before moving to more advanced material."
        )
        return [
            InferredMemoryCandidate(
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
        ]

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
    ) -> tuple[list[MemoryRecord], float]:
        anchor_vector = np.asarray(anchor.semantic_embedding, dtype=np.float32)
        scored: list[tuple[MemoryRecord, float]] = []
        for candidate in candidates:
            similarity = self._semantic_similarity(anchor, candidate, anchor_vector)
            if similarity >= self._similarity_threshold:
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
        candidate_vector = np.asarray(candidate.semantic_embedding, dtype=np.float32)
        if (
            anchor_vector.size > 0
            and candidate_vector.size > 0
            and anchor_vector.shape == candidate_vector.shape
        ):
            return float(cosine_similarity(anchor_vector, candidate_vector))
        if anchor.semantic_key == candidate.semantic_key:
            return 1.0
        return 0.0

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
