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
    supersedes_memory_ids: tuple[str, ...] = ()


@dataclass
class _PreferenceState:
    concise_score: float = 0.0
    detailed_score: float = 0.0
    updates: int = 0
    last_emitted: str | None = None
    concise_supporting_ids: list[str] = field(default_factory=list)
    detailed_supporting_ids: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class _SignatureReservation:
    signature: str
    supersedes_memory_ids: tuple[str, ...] = ()


@dataclass(frozen=True)
class _FactSignal:
    subject: str
    fact_key: str
    fact_type: str
    polarity: str
    value: str
    critical: bool


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
    _FACT_SOURCE_INTENTS = {
        "user_question",
        "user_attempt",
        "preference_stated",
        "user_fact",
        "learning_progress",
    }
    _CRITICAL_FACT_TYPES = {"constraint", "medical_constraint"}
    _SUBJECT_ALIASES = {
        "i": "user",
        "i'm": "user",
        "im": "user",
        "me": "user",
        "myself": "user",
        "my father": "father",
        "my dad": "father",
        "my mother": "mother",
        "my mom": "mother",
        "my brother": "brother",
        "my sister": "sister",
        "my wife": "wife",
        "my husband": "husband",
        "my son": "son",
        "my daughter": "daughter",
        "my partner": "partner",
        "my family": "family",
    }
    _ALLERGY_PATTERN = re.compile(
        r"\b(?P<subject>i(?:'m)?|im|me|myself|my father|my dad|my mother|my mom|"
        r"my brother|my sister|my wife|my husband|my son|my daughter|my partner|"
        r"my family)\s+(?:am|are|is)?\s*(?P<neg>not\s+|no longer\s+)?allergic\s+to\s+"
        r"(?P<item>[^.,;!?]+)",
        flags=re.IGNORECASE,
    )
    _LIKES_PATTERN = re.compile(
        r"\b(?P<subject>i(?:'m)?|im|me|myself|my father|my dad|my mother|my mom|"
        r"my brother|my sister|my wife|my husband|my son|my daughter|my partner|"
        r"my family)\s+(?:really\s+)?(?:like|likes|love|loves|enjoy|enjoys)\s+"
        r"(?P<item>[^.,;!?]+)",
        flags=re.IGNORECASE,
    )
    _FAN_OF_PATTERN = re.compile(
        r"\b(?P<subject>my father|my dad|my mother|my mom|my brother|my sister|"
        r"my wife|my husband|my son|my daughter|my partner|my family)\s+"
        r"(?:is|are)\s+(?:a\s+)?(?:big\s+)?fan\s+of\s+(?P<item>[^.,;!?]+)",
        flags=re.IGNORECASE,
    )
    _WEIGHT_CURRENT_PATTERN = re.compile(
        r"\b(?:i(?:'m)?|im|currently|current(?:ly)?\s+at)\s+"
        r"(?:am\s+|at\s+|weigh(?:ing)?\s+)?"
        r"(?P<weight>\d{2,3})(?:\s*(?:kg|kgs|kilograms?|lb|lbs|pounds?))?\b",
        flags=re.IGNORECASE,
    )
    _WEIGHT_TARGET_PATTERN = re.compile(
        r"\b(?:need|aim|target|goal|want|trying|plan)\b[^.!?]{0,40}"
        r"(?:to be(?:\s+at)?|to reach|reach|get to|hit)\s*"
        r"(?P<weight>\d{2,3})(?:\s*(?:kg|kgs|kilograms?|lb|lbs|pounds?))?\b",
        flags=re.IGNORECASE,
    )
    _WEIGHT_REASON_PATTERN = re.compile(
        r"\b(?:need|aim|target|goal|want|trying|plan)\b[^.!?]{0,70}"
        r"(?:to be(?:\s+at)?|to reach|reach|get to|hit)\s*\d{2,3}[^.!?]{0,80}\bfor\b\s+"
        r"(?P<reason>[^.!?]+)",
        flags=re.IGNORECASE,
    )
    _CONFIRMATION_TERMS = (
        "doctor",
        "confirmed",
        "test result",
        "tested",
        "medical report",
        "cleared",
        "clinically",
        "diagnosed",
    )
    _FACT_TRAILING_TERMS = {
        "again",
        "anymore",
        "currently",
        "now",
        "still",
        "today",
        "yet",
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
        inferred_ttl_days: int = 45,
        inferred_refresh_days: int = 14,
    ) -> None:
        self._storage = storage
        self._enabled = enabled
        self._repeat_threshold = max(repeat_threshold, 2)
        self._similarity_threshold = min(max(similarity_threshold, 0.0), 1.0)
        self._window_days = max(window_days, 1)
        self._min_feedback_events = max(min_feedback_events, 1)
        self._preference_margin = max(preference_margin, 0.1)
        self._inferred_ttl_days = max(inferred_ttl_days, 1)
        self._inferred_refresh_days = max(inferred_refresh_days, 0)
        self._emitted_signatures: dict[str, datetime] = {}
        self._preference_state_by_entity: dict[str, _PreferenceState] = {}
        self._lock = threading.RLock()

    def observe_memory(
        self,
        memory: MemoryRecord,
        account_key: str | None = None,
        source_text: str | None = None,
    ) -> list[InferredMemoryCandidate]:
        if not self._enabled:
            return []
        intent = memory.intent.strip().lower()
        if intent.startswith("inferred_") or self._is_inferred_memory(memory):
            return []
        if intent not in (
            self._TOPIC_CLUSTER_SOURCE_INTENTS
            | self._FAILURE_SOURCE_INTENTS
            | self._PROGRESS_SOURCE_INTENTS
            | self._FACT_SOURCE_INTENTS
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
                account_key=account_key,
            )
            if repeated_topic_candidate is not None:
                candidates.append(repeated_topic_candidate)
        if intent in self._FAILURE_SOURCE_INTENTS:
            recurring_failure_candidate = self._infer_recurring_failure(
                memory=memory,
                entity_id=entity_id,
                account_key=account_key,
            )
            if recurring_failure_candidate is not None:
                candidates.append(recurring_failure_candidate)
        if intent in self._PROGRESS_SOURCE_INTENTS:
            progress_candidate = self._infer_progress_accumulation(
                memory=memory,
                entity_id=entity_id,
                account_key=account_key,
            )
            if progress_candidate is not None:
                candidates.append(progress_candidate)
        if intent in self._FACT_SOURCE_INTENTS:
            candidates.extend(
                self._infer_fact_candidates(
                    memory=memory,
                    entity_id=entity_id,
                    account_key=account_key,
                    source_text=source_text,
                )
            )
        return candidates

    def _infer_repeat_topic_cluster(
        self,
        *,
        memory: MemoryRecord,
        entity_id: str,
        account_key: str | None = None,
    ) -> InferredMemoryCandidate | None:
        since_iso = (
            datetime.now(UTC) - timedelta(days=self._window_days)
        ).isoformat()
        history = self._storage.fetch_by_entity_and_intent(
            entity_id=entity_id,
            intent=memory.intent.strip().lower(),
            since_iso=since_iso,
            account_key=account_key,
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
        reservation = self._reserve_signature(
            entity_id=entity_id,
            inference_type="repeat_question_cluster",
            topic_summary=topic_summary,
            account_key=account_key,
        )
        if reservation is None:
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
            f"signature:{reservation.signature}",
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
            supersedes_memory_ids=reservation.supersedes_memory_ids,
        )

    def _infer_recurring_failure(
        self,
        *,
        memory: MemoryRecord,
        entity_id: str,
        account_key: str | None = None,
    ) -> InferredMemoryCandidate | None:
        if not self._is_failure_signal(memory):
            return None
        history = self._recent_entity_memories(
            entity_id=entity_id,
            intents=self._FAILURE_SOURCE_INTENTS,
            account_key=account_key,
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
        reservation = self._reserve_signature(
            entity_id=entity_id,
            inference_type="recurring_failure_pattern",
            topic_summary=topic_summary,
            account_key=account_key,
        )
        if reservation is None:
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
            f"signature:{reservation.signature}",
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
            supersedes_memory_ids=reservation.supersedes_memory_ids,
        )

    def _infer_progress_accumulation(
        self,
        *,
        memory: MemoryRecord,
        entity_id: str,
        account_key: str | None = None,
    ) -> InferredMemoryCandidate | None:
        if not self._is_progress_signal(memory):
            return None
        history = self._recent_entity_memories(
            entity_id=entity_id,
            intents=self._PROGRESS_SOURCE_INTENTS,
            account_key=account_key,
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
        reservation = self._reserve_signature(
            entity_id=entity_id,
            inference_type="progress_accumulation",
            topic_summary=topic_summary,
            account_key=account_key,
        )
        if reservation is None:
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
            f"signature:{reservation.signature}",
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
            supersedes_memory_ids=reservation.supersedes_memory_ids,
        )

    def observe_feedback(
        self,
        ranked_memories: list[MemoryRecord],
        helpful_memory_ids: set[str],
        outcome_signal: float,
        account_key: str | None = None,
    ) -> list[InferredMemoryCandidate]:
        if not self._enabled:
            return []
        candidates: list[InferredMemoryCandidate] = []
        emitted_for_entity: set[str] = set()

        for memory in ranked_memories:
            if not self._is_assistant_intent(memory.intent):
                continue
            signal_strength = abs(outcome_signal)
            if signal_strength <= 0.0:
                continue
            entity_id = self._primary_entity(memory)
            if entity_id is None or entity_id in emitted_for_entity:
                continue
            style = self._style_bucket(memory)
            if memory.memory_id in helpful_memory_ids and outcome_signal > 0.0:
                inferred_style = style
            elif memory.memory_id not in helpful_memory_ids and outcome_signal < 0.0:
                inferred_style = "detailed" if style == "concise" else "concise"
            else:
                continue
            candidate = self._update_preference_state(
                entity_id=entity_id,
                style=inferred_style,
                signal=signal_strength,
                source_memory_id=memory.memory_id,
                account_key=account_key,
            )
            if candidate is not None:
                candidates.append(candidate)
                emitted_for_entity.add(entity_id)
        return candidates

    def _infer_fact_candidates(
        self,
        *,
        memory: MemoryRecord,
        entity_id: str,
        account_key: str | None = None,
        source_text: str | None = None,
    ) -> list[InferredMemoryCandidate]:
        text = (
            source_text.strip()
            if isinstance(source_text, str) and source_text.strip()
            else f"{memory.summary} {memory.content}".strip()
        )
        signals = self._extract_fact_signals(text=text)
        if not signals:
            return []

        output: list[InferredMemoryCandidate] = []
        for signal in signals:
            signature_topic = f"{signal.subject}|{signal.fact_key}|{signal.polarity}"
            reservation = self._reserve_signature(
                entity_id=entity_id,
                inference_type="fact_extraction_v1",
                topic_summary=signature_topic,
                account_key=account_key,
            )
            if reservation is None:
                continue

            existing = self._existing_fact_memories(
                entity_id=entity_id,
                subject=signal.subject,
                fact_key=signal.fact_key,
                account_key=account_key,
            )
            conflicting = [
                item
                for item in existing
                if self._fact_polarity(item) not in {None, signal.polarity}
            ]
            conflict_ids = [item.memory_id for item in conflicting]
            mutable_supersedes = self._mutable_numeric_supersedes(
                entity_id=entity_id,
                subject=signal.subject,
                fact_key=signal.fact_key,
                account_key=account_key,
            )

            confirmed_change = bool(conflicting) and self._has_confirmation_signal(text)
            supersedes_ids: list[str] = []
            if confirmed_change:
                supersedes_ids.extend(conflict_ids)
            supersedes_ids.extend(mutable_supersedes)
            supersedes = tuple(dict.fromkeys(memory_id for memory_id in supersedes_ids if memory_id))
            clarification_required = bool(
                conflicting and signal.critical and not confirmed_change
            )
            if supersedes:
                fact_status = "superseding"
            elif clarification_required:
                fact_status = "contested"
            else:
                fact_status = "active"

            summary = self._fact_summary(entity_id=entity_id, signal=signal)
            content = self._fact_content(
                entity_id=entity_id,
                signal=signal,
                clarification_required=clarification_required,
            )
            relationships = [
                f"{entity_id}->fact:{signal.fact_key}",
                "inferred:true",
                "inference_type:fact_extraction_v1",
                f"signature:{reservation.signature}",
                f"fact_subject:{signal.subject}",
                f"fact_key:{signal.fact_key}",
                f"fact_type:{signal.fact_type}",
                f"fact_polarity:{signal.polarity}",
                f"fact_status:{fact_status}",
                f"clarification_required:{str(clarification_required).lower()}",
                f"critical_fact:{str(signal.critical).lower()}",
                f"derived_from:{memory.memory_id}",
            ]
            relationships.extend(f"conflicts_with:{memory_id}" for memory_id in conflict_ids)

            confidence = 0.9 if signal.critical else 0.82
            if clarification_required:
                confidence = min(0.95, confidence + 0.03)
            candidate = InferredMemoryCandidate(
                entity_id=entity_id,
                event_type="inferred_user_fact",
                content=content,
                summary=summary,
                confidence=confidence,
                metadata={
                    "inferred": True,
                    "intent": "inferred_user_fact",
                    "summary": summary,
                    "entities": [entity_id],
                    "relationships": relationships,
                    "inference_type": "fact_extraction_v1",
                    "fact_subject": signal.subject,
                    "fact_key": signal.fact_key,
                    "fact_type": signal.fact_type,
                    "fact_polarity": signal.polarity,
                    "fact_status": fact_status,
                    "clarification_required": clarification_required,
                    "critical_fact": signal.critical,
                    "conflicts_with_memory_ids": conflict_ids,
                },
                supersedes_memory_ids=supersedes,
            )
            output.append(candidate)

            if clarification_required:
                guard = self._build_fact_conflict_guard(
                    entity_id=entity_id,
                    signal=signal,
                    conflict_ids=conflict_ids,
                    source_memory_id=memory.memory_id,
                    account_key=account_key,
                )
                if guard is not None:
                    output.append(guard)

        return output

    def _mutable_numeric_supersedes(
        self,
        *,
        entity_id: str,
        subject: str,
        fact_key: str,
        account_key: str | None = None,
    ) -> list[str]:
        family = self._fact_family(fact_key)
        if family not in {"weight_current", "weight_target"}:
            return []
        matches: list[str] = []
        prefix = f"{family}:"
        for memory in self._storage.list_memories(account_key=account_key):
            if entity_id not in memory.entities:
                continue
            if memory.intent.strip().lower() != "inferred_user_fact":
                continue
            memory_subject = self._relationship_value(
                memory.relationships,
                prefix="fact_subject:",
            )
            if memory_subject != subject:
                continue
            memory_key = self._relationship_value(
                memory.relationships,
                prefix="fact_key:",
            )
            if memory_key is None or not memory_key.startswith(prefix):
                continue
            if memory_key == fact_key:
                continue
            matches.append(memory.memory_id)
        return matches

    @staticmethod
    def _fact_family(fact_key: str) -> str:
        normalized = fact_key.strip().lower()
        if ":" not in normalized:
            return normalized
        return normalized.split(":", 1)[0]

    def _build_fact_conflict_guard(
        self,
        *,
        entity_id: str,
        signal: _FactSignal,
        conflict_ids: list[str],
        source_memory_id: str,
        account_key: str | None = None,
    ) -> InferredMemoryCandidate | None:
        reservation = self._reserve_signature(
            entity_id=entity_id,
            inference_type="fact_conflict_guard_v1",
            topic_summary=f"{signal.subject}|{signal.fact_key}",
            account_key=account_key,
        )
        if reservation is None:
            return None
        summary = (
            f"Clarify conflicting {signal.fact_type.replace('_', ' ')} facts for "
            f"{self._subject_label(entity_id=entity_id, subject=signal.subject)}"
        )
        content = (
            f"Inferred conflict guard: conflicting statements detected for "
            f"{self._subject_label(entity_id=entity_id, subject=signal.subject)} "
            f"on {signal.value}. Ask a clarification question before relying on this "
            "fact in safety-sensitive responses."
        )
        relationships = [
            f"{entity_id}->fact_conflict:{signal.fact_key}",
            "inferred:true",
            "inference_type:fact_conflict_guard_v1",
            f"signature:{reservation.signature}",
            f"fact_subject:{signal.subject}",
            f"fact_key:{signal.fact_key}",
            f"fact_type:{signal.fact_type}",
            "fact_status:contested",
            "clarification_required:true",
            f"critical_fact:{str(signal.critical).lower()}",
            f"derived_from:{source_memory_id}",
        ]
        relationships.extend(f"conflicts_with:{memory_id}" for memory_id in conflict_ids)
        return InferredMemoryCandidate(
            entity_id=entity_id,
            event_type="inferred_user_fact_conflict",
            content=content,
            summary=summary,
            confidence=0.94,
            metadata={
                "inferred": True,
                "intent": "inferred_user_fact_conflict",
                "summary": summary,
                "entities": [entity_id],
                "relationships": relationships,
                "inference_type": "fact_conflict_guard_v1",
                "fact_subject": signal.subject,
                "fact_key": signal.fact_key,
                "fact_type": signal.fact_type,
                "fact_status": "contested",
                "clarification_required": True,
                "critical_fact": signal.critical,
                "conflicts_with_memory_ids": conflict_ids,
            },
            supersedes_memory_ids=reservation.supersedes_memory_ids,
        )

    def _recent_entity_memories(
        self,
        *,
        entity_id: str,
        intents: set[str],
        account_key: str | None = None,
    ) -> list[MemoryRecord]:
        since = datetime.now(UTC) - timedelta(days=self._window_days)
        filtered: list[MemoryRecord] = []
        for memory in self._storage.list_memories(account_key=account_key):
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
        account_key: str | None = None,
    ) -> _SignatureReservation | None:
        now = datetime.now(UTC)
        refresh_window = timedelta(days=self._inferred_refresh_days)
        signature = self._signature(
            entity_id=entity_id,
            inference_type=inference_type,
            topic_summary=topic_summary,
        )
        with self._lock:
            last_emitted_at = self._emitted_signatures.get(signature)
            if (
                last_emitted_at is not None
                and now - last_emitted_at < refresh_window
            ):
                return None

        existing = self._signature_memories_in_storage(
            entity_id=entity_id,
            signature=signature,
            account_key=account_key,
        )
        if existing:
            freshest = max(existing, key=lambda memory: memory.created_at)
            if now - freshest.created_at < refresh_window:
                with self._lock:
                    self._emitted_signatures[signature] = now
                return None
            supersedes = tuple(memory.memory_id for memory in existing)
        else:
            supersedes = ()

        with self._lock:
            self._emitted_signatures[signature] = now
        return _SignatureReservation(
            signature=signature,
            supersedes_memory_ids=supersedes,
        )

    def _signature_memories_in_storage(
        self,
        *,
        entity_id: str,
        signature: str,
        account_key: str | None = None,
    ) -> list[MemoryRecord]:
        signature_marker = f"signature:{signature}"
        matches: list[MemoryRecord] = []
        for memory in self._storage.list_memories(account_key=account_key):
            if entity_id not in memory.entities:
                continue
            if signature_marker in memory.relationships:
                matches.append(memory)
        return matches

    def expired_inferred_memory_ids(
        self,
        account_key: str | None = None,
    ) -> list[str]:
        if not self._enabled:
            return []
        cutoff = datetime.now(UTC) - timedelta(days=self._inferred_ttl_days)
        expired: list[str] = []
        for memory in self._storage.list_memories(account_key=account_key):
            if not self._is_inferred_memory(memory):
                continue
            if memory.created_at < cutoff:
                expired.append(memory.memory_id)
        return expired

    def notify_memories_deleted(self, memories: list[MemoryRecord]) -> None:
        if not memories:
            return
        signatures: set[str] = set()
        for memory in memories:
            signatures.update(self._signatures_for_memory(memory))
        if not signatures:
            return
        with self._lock:
            for signature in signatures:
                self._emitted_signatures.pop(signature, None)

    def _update_preference_state(
        self,
        entity_id: str,
        style: str,
        signal: float,
        source_memory_id: str,
        account_key: str | None = None,
    ) -> InferredMemoryCandidate | None:
        delta = max(signal, 0.1)
        with self._lock:
            state = self._preference_state_by_entity.setdefault(entity_id, _PreferenceState())
            if style == "concise":
                state.concise_score += delta
                self._append_unique_limited(
                    state.concise_supporting_ids,
                    source_memory_id,
                )
            else:
                state.detailed_score += delta
                self._append_unique_limited(
                    state.detailed_supporting_ids,
                    source_memory_id,
                )
            state.updates += 1

            if state.updates < self._min_feedback_events:
                return None
            margin = state.concise_score - state.detailed_score
            if abs(margin) < self._preference_margin:
                return None
            preferred_style = "concise" if margin > 0 else "detailed"
            explicit_style = self._explicit_style_preference(
                entity_id,
                account_key=account_key,
            )
            if (
                explicit_style is not None
                and explicit_style != preferred_style
                and abs(margin) < (self._preference_margin * 4.0)
            ):
                preferred_style = explicit_style
            if state.last_emitted == preferred_style:
                return None
            state.last_emitted = preferred_style
            supporting_ids = (
                list(state.concise_supporting_ids)
                if preferred_style == "concise"
                else list(state.detailed_supporting_ids)
            )
        derived_from_ids = [memory_id for memory_id in supporting_ids[-8:] if memory_id]
        if not derived_from_ids and source_memory_id:
            derived_from_ids = [source_memory_id]

        confidence = min(0.95, 0.62 + min(abs(margin) / 8.0, 0.3))
        signature = self._signature(
            entity_id=entity_id,
            inference_type="feedback_preference_shift",
            topic_summary=preferred_style,
        )
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
        relationships = [
            f"{entity_id}->preference:explanation_style={preferred_style}",
            "inferred:true",
            "inference_type:feedback_preference_shift",
            f"signature:{signature}",
        ]
        relationships.extend(
            f"derived_from:{memory_id}" for memory_id in derived_from_ids
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
                "relationships": relationships,
                "inference_type": "feedback_preference_shift",
            },
        )

    @staticmethod
    def _append_unique_limited(
        values: list[str],
        value: str,
        *,
        limit: int = 16,
    ) -> None:
        normalized = value.strip()
        if not normalized:
            return
        if normalized in values:
            values.remove(normalized)
        values.append(normalized)
        if len(values) > limit:
            del values[: len(values) - limit]

    def _explicit_style_preference(
        self,
        entity_id: str,
        account_key: str | None = None,
    ) -> str | None:
        candidates = sorted(
            self._storage.list_memories(account_key=account_key),
            key=lambda memory: memory.created_at,
            reverse=True,
        )
        for memory in candidates:
            if entity_id not in memory.entities:
                continue
            intent = memory.intent.strip().lower()
            if intent not in {"preference_stated", "user_profile", "user_fact"}:
                continue
            style = self._style_preference_from_text(
                f"{memory.summary} {memory.content}".lower()
            )
            if style is not None:
                return style
        return None

    @staticmethod
    def _style_preference_from_text(text: str) -> str | None:
        concise_markers = (
            "concise",
            "short",
            "brief",
            "compact",
        )
        detailed_markers = (
            "detailed",
            "fuller context",
            "step-by-step",
            "in-depth",
        )
        has_concise = any(marker in text for marker in concise_markers)
        has_detailed = any(marker in text for marker in detailed_markers)
        if has_detailed and not has_concise:
            return "detailed"
        if has_concise and not has_detailed:
            return "concise"
        return None

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
    def _extract_fact_signals(cls, *, text: str) -> list[_FactSignal]:
        normalized = text.strip()
        if not normalized:
            return []

        extracted: list[_FactSignal] = []
        seen: set[tuple[str, str, str]] = set()

        for match in cls._ALLERGY_PATTERN.finditer(normalized):
            subject = cls._normalize_subject(match.group("subject"))
            item = cls._normalize_fact_value(match.group("item"))
            if item is None:
                continue
            polarity = "negative" if match.group("neg") else "positive"
            key = f"allergy:{item}"
            signature = (subject, key, polarity)
            if signature in seen:
                continue
            seen.add(signature)
            extracted.append(
                _FactSignal(
                    subject=subject,
                    fact_key=key,
                    fact_type="constraint",
                    polarity=polarity,
                    value=item,
                    critical=True,
                )
            )

        for pattern in (cls._LIKES_PATTERN, cls._FAN_OF_PATTERN):
            for match in pattern.finditer(normalized):
                subject = cls._normalize_subject(match.group("subject"))
                item = cls._normalize_fact_value(match.group("item"))
                if item is None:
                    continue
                key = f"preference_like:{item}"
                signature = (subject, key, "positive")
                if signature in seen:
                    continue
                seen.add(signature)
                extracted.append(
                    _FactSignal(
                        subject=subject,
                        fact_key=key,
                        fact_type="preference",
                        polarity="positive",
                        value=item,
                        critical=False,
                    )
                )

        for match in cls._WEIGHT_CURRENT_PATTERN.finditer(normalized):
            weight_raw = match.group("weight")
            try:
                weight = int(weight_raw)
            except (TypeError, ValueError):
                continue
            if weight < 25 or weight > 400:
                continue
            key = f"weight_current:{weight}"
            signature = ("user", key, "positive")
            if signature in seen:
                continue
            seen.add(signature)
            extracted.append(
                _FactSignal(
                    subject="user",
                    fact_key=key,
                    fact_type="goal_profile",
                    polarity="positive",
                    value=f"{weight} kg",
                    critical=False,
                )
            )

        for match in cls._WEIGHT_TARGET_PATTERN.finditer(normalized):
            weight_raw = match.group("weight")
            try:
                weight = int(weight_raw)
            except (TypeError, ValueError):
                continue
            if weight < 25 or weight > 400:
                continue
            key = f"weight_target:{weight}"
            signature = ("user", key, "positive")
            if signature in seen:
                continue
            seen.add(signature)
            extracted.append(
                _FactSignal(
                    subject="user",
                    fact_key=key,
                    fact_type="goal_profile",
                    polarity="positive",
                    value=f"{weight} kg",
                    critical=False,
                )
            )

        for match in cls._WEIGHT_REASON_PATTERN.finditer(normalized):
            reason = cls._normalize_fact_value(match.group("reason"))
            if reason is None:
                continue
            key = f"weight_goal_reason:{reason}"
            signature = ("user", key, "positive")
            if signature in seen:
                continue
            seen.add(signature)
            extracted.append(
                _FactSignal(
                    subject="user",
                    fact_key=key,
                    fact_type="goal_context",
                    polarity="positive",
                    value=reason,
                    critical=False,
                )
            )

        return extracted

    def _existing_fact_memories(
        self,
        *,
        entity_id: str,
        subject: str,
        fact_key: str,
        account_key: str | None = None,
    ) -> list[MemoryRecord]:
        matches: list[MemoryRecord] = []
        for memory in self._storage.list_memories(account_key=account_key):
            if entity_id not in memory.entities:
                continue
            memory_subject = self._relationship_value(
                memory.relationships,
                prefix="fact_subject:",
            )
            memory_key = self._relationship_value(
                memory.relationships,
                prefix="fact_key:",
            )
            if memory_subject != subject or memory_key != fact_key:
                continue
            matches.append(memory)
        return matches

    @staticmethod
    def _relationship_value(
        relationships: list[str],
        *,
        prefix: str,
    ) -> str | None:
        for relation in relationships:
            if not relation.startswith(prefix):
                continue
            value = relation.removeprefix(prefix).strip()
            if value:
                return value
        return None

    def _fact_summary(self, *, entity_id: str, signal: _FactSignal) -> str:
        subject_label = self._subject_label(entity_id=entity_id, subject=signal.subject)
        if signal.fact_key.startswith("allergy:"):
            if signal.polarity == "negative":
                return f"{subject_label} reports no current allergy to {signal.value}"
            return f"{subject_label} is allergic to {signal.value}"
        if signal.fact_key.startswith("weight_current:"):
            return f"{subject_label} currently weighs {signal.value}"
        if signal.fact_key.startswith("weight_target:"):
            return f"{subject_label}'s weight target is {signal.value}"
        if signal.fact_key.startswith("weight_goal_reason:"):
            return f"{subject_label}'s weight goal reason is {signal.value}"
        return f"{subject_label} likes {signal.value}"

    def _fact_content(
        self,
        *,
        entity_id: str,
        signal: _FactSignal,
        clarification_required: bool,
    ) -> str:
        subject_label = self._subject_label(entity_id=entity_id, subject=signal.subject)
        if signal.fact_key.startswith("allergy:"):
            if signal.polarity == "negative":
                base = (
                    f"Inferred user fact: {subject_label} reports no current allergy to "
                    f"{signal.value}."
                )
            else:
                base = f"Inferred user fact: {subject_label} is allergic to {signal.value}."
        elif signal.fact_key.startswith("weight_current:"):
            base = f"Inferred user fact: {subject_label} currently weighs {signal.value}."
        elif signal.fact_key.startswith("weight_target:"):
            base = (
                f"Inferred user fact: {subject_label}'s target weight is {signal.value}."
            )
        elif signal.fact_key.startswith("weight_goal_reason:"):
            base = (
                f"Inferred user fact: {subject_label}'s target-weight reason is "
                f"{signal.value}."
            )
        else:
            base = f"Inferred user fact: {subject_label} likes {signal.value}."
        if clarification_required:
            return (
                base
                + " Conflicting statements exist for this fact. Ask a clarification "
                "question before relying on it."
            )
        return base

    @staticmethod
    def _normalize_subject(raw: str) -> str:
        normalized = " ".join(raw.lower().split())
        return AdaptivePersonalizationEngine._SUBJECT_ALIASES.get(normalized, "user")

    @staticmethod
    def _normalize_fact_value(raw: str) -> str | None:
        cleaned = " ".join(raw.lower().split())
        cleaned = re.sub(r"[\"'`]", "", cleaned)
        cleaned = re.sub(r"[^a-z0-9\s-]", "", cleaned)
        cleaned = re.sub(
            r"\b(?:and|but)\s+"
            r"(?:i|it|this|that|we|you|he|she|they|should|must|need|cannot|"
            r"cant|have|has|had|will|would|could|can)\b.*$",
            "",
            cleaned,
        ).strip()
        cleaned = re.sub(r"\b(?:because|since)\b.*$", "", cleaned).strip()
        cleaned = re.sub(
            r"^(a|an|the|some|any|my)\s+",
            "",
            cleaned,
        ).strip()
        if not cleaned:
            return None
        tokens = [token for token in cleaned.split() if token]
        if not tokens:
            return None
        while tokens and tokens[-1] in AdaptivePersonalizationEngine._FACT_TRAILING_TERMS:
            tokens.pop()
        if not tokens:
            return None
        value = " ".join(tokens[:4])
        if len(value) < 2:
            return None
        return value

    def _subject_label(self, *, entity_id: str, subject: str) -> str:
        if subject == "user":
            return entity_id
        return f"{entity_id}'s {subject}"

    @staticmethod
    def _fact_polarity(memory: MemoryRecord) -> str | None:
        return AdaptivePersonalizationEngine._relationship_value(
            memory.relationships,
            prefix="fact_polarity:",
        )

    @classmethod
    def _has_confirmation_signal(cls, text: str) -> bool:
        normalized = text.lower()
        return any(term in normalized for term in cls._CONFIRMATION_TERMS)

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

    @staticmethod
    def _signatures_for_memory(memory: MemoryRecord) -> set[str]:
        signatures: set[str] = set()
        for relation in memory.relationships:
            normalized = relation.strip()
            if normalized.startswith("signature:"):
                signatures.add(normalized.removeprefix("signature:"))
        return signatures

    def _relaxed_similarity_threshold(self) -> float:
        return max(0.1, self._similarity_threshold * 0.12)

    @staticmethod
    def _style_bucket(memory: MemoryRecord) -> str:
        text = memory.content.lower().strip()
        summary_text = memory.summary.lower().strip()
        if not text:
            text = summary_text
        concise_markers = (
            "concise",
            "short",
            "brief",
            "quick steps",
            "minimal reproducible snippet",
            "one fix at a time",
        )
        if any(marker in text for marker in concise_markers):
            return "concise"
        if any(
            marker in text
            for marker in (
                "fuller context",
                "worked examples",
                "postmortem",
                "regression tests",
                "deep dive",
                "comprehensive",
            )
        ):
            return "detailed"
        word_count = len(text.split())
        sentence_count = text.count(".") + text.count("!") + text.count("?")
        if word_count <= 32 and sentence_count <= 2:
            return "concise"
        if word_count >= 36 or sentence_count >= 3:
            return "detailed"
        if any(
            marker in summary_text
            for marker in ("fuller context", "worked examples", "regression tests")
        ):
            return "detailed"
        return "concise"

    @staticmethod
    def _is_assistant_intent(intent: str) -> bool:
        normalized = intent.strip().lower()
        return normalized.startswith("assistant_") or normalized == "assistant_message"
