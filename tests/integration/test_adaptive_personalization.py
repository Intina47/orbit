from __future__ import annotations

import sqlite3
from datetime import UTC, datetime, timedelta
from pathlib import Path

from memory_engine.config import EngineConfig
from memory_engine.engine import DecisionEngine
from memory_engine.models.event import Event


def _store_event(engine, event: Event) -> str:
    processed = engine.process_input(event)
    decision = engine.make_storage_decision(processed)
    stored = engine.store_memory(processed, decision)
    assert stored is not None
    return stored.memory_id


def _relation_value(memory, prefix: str) -> str | None:
    for relation in memory.relationships:
        if relation.startswith(prefix):
            value = relation.removeprefix(prefix).strip()
            if value:
                return value
    return None


def test_repeated_questions_create_inferred_learning_pattern(engine) -> None:
    for idx in range(3):
        _store_event(
            engine,
            Event(
                timestamp=1_700_100_000 + idx,
                entity_id="alice",
                event_type="user_question",
                description="What is a for loop in Python?",
                metadata={"intent": "user_question"},
            ),
        )

    memories = engine.get_memory(entity_id="alice")
    inferred = [item for item in memories if item.intent == "inferred_learning_pattern"]

    assert len(inferred) == 1
    assert "repeatedly asks" in inferred[0].content.lower()


def test_inferred_learning_pattern_is_not_duplicated_for_same_topic(engine) -> None:
    for idx in range(5):
        _store_event(
            engine,
            Event(
                timestamp=1_700_200_000 + idx,
                entity_id="alice",
                event_type="user_question",
                description="I still don't understand Python for loops.",
                metadata={"intent": "user_question"},
            ),
        )

    memories = engine.get_memory(entity_id="alice")
    inferred = [item for item in memories if item.intent == "inferred_learning_pattern"]

    assert len(inferred) == 1


def test_feedback_creates_inferred_preference_memory(engine) -> None:
    assistant_ids: list[str] = []
    for idx in range(4):
        memory_id = _store_event(
            engine,
            Event(
                timestamp=1_700_300_000 + idx,
                entity_id="alice",
                event_type="assistant_response",
                description="Use a for loop when you need to repeat a step a fixed number of times.",
                metadata={"intent": "assistant_response"},
            ),
        )
        assistant_ids.append(memory_id)

    for memory_id in assistant_ids:
        engine.record_feedback(
            query=f"feedback-{memory_id}",
            ranked_memory_ids=[memory_id],
            helpful_memory_ids=[memory_id],
            outcome_signal=1.0,
        )

    memories = engine.get_memory(entity_id="alice")
    preferences = [item for item in memories if item.intent == "inferred_preference"]

    assert len(preferences) >= 1
    assert "concise explanations" in preferences[-1].content.lower()
    derived = [
        relation
        for relation in preferences[-1].relationships
        if relation.startswith("derived_from:")
    ]
    assert len(derived) >= 1


def test_feedback_creates_detailed_inferred_preference_memory(engine) -> None:
    assistant_ids: list[str] = []
    for idx in range(4):
        memory_id = _store_event(
            engine,
            Event(
                timestamp=1_700_350_000 + idx,
                entity_id="alice",
                event_type="assistant_response",
                description=(
                    "Start by isolating the failing path, then map preconditions and "
                    "runtime state. Document assumptions, add validation checks, "
                    "refactor module boundaries, and finish with regression tests."
                ),
                metadata={"intent": "assistant_response"},
            ),
        )
        assistant_ids.append(memory_id)

    for memory_id in assistant_ids:
        engine.record_feedback(
            query=f"feedback-detailed-{memory_id}",
            ranked_memory_ids=[memory_id],
            helpful_memory_ids=[memory_id],
            outcome_signal=1.0,
        )

    memories = engine.get_memory(entity_id="alice")
    preferences = [item for item in memories if item.intent == "inferred_preference"]

    assert len(preferences) >= 1
    assert "detailed explanations" in preferences[-1].content.lower()
    derived = [
        relation
        for relation in preferences[-1].relationships
        if relation.startswith("derived_from:")
    ]
    assert len(derived) >= 1


def test_negative_feedback_on_detailed_style_infers_concise_preference(engine) -> None:
    assistant_ids: list[str] = []
    for idx in range(4):
        memory_id = _store_event(
            engine,
            Event(
                timestamp=1_700_360_000 + idx,
                entity_id="alice",
                event_type="assistant_response",
                description=(
                    "Start by isolating the failing path, then map preconditions and "
                    "runtime state. Document assumptions, add validation checks, "
                    "refactor module boundaries, and finish with regression tests."
                ),
                metadata={"intent": "assistant_response"},
            ),
        )
        assistant_ids.append(memory_id)

    for memory_id in assistant_ids:
        engine.record_feedback(
            query=f"feedback-negative-{memory_id}",
            ranked_memory_ids=[memory_id],
            helpful_memory_ids=[],
            outcome_signal=-1.0,
        )

    memories = engine.get_memory(entity_id="alice")
    preferences = [item for item in memories if item.intent == "inferred_preference"]

    assert len(preferences) >= 1
    assert "concise explanations" in preferences[-1].content.lower()
    derived = [
        relation
        for relation in preferences[-1].relationships
        if relation.startswith("derived_from:")
    ]
    assert len(derived) >= 1


def test_fact_inference_extracts_allergy_constraint(engine) -> None:
    source_id = _store_event(
        engine,
        Event(
            timestamp=1_700_380_000,
            entity_id="alice",
            event_type="user_question",
            description="I am allergic to pineapple and should avoid it.",
            metadata={"intent": "user_question"},
        ),
    )

    facts = [
        item for item in engine.get_memory(entity_id="alice") if item.intent == "inferred_user_fact"
    ]
    assert len(facts) >= 1
    allergy = facts[-1]
    assert "allergic to pineapple" in allergy.content.lower()
    assert _relation_value(allergy, "fact_subject:") == "user"
    assert _relation_value(allergy, "fact_key:") == "allergy:pineapple"
    assert _relation_value(allergy, "fact_polarity:") == "positive"
    assert f"derived_from:{source_id}" in allergy.relationships


def test_fact_inference_is_subject_aware(engine) -> None:
    _store_event(
        engine,
        Event(
            timestamp=1_700_390_000,
            entity_id="alice",
            event_type="user_question",
            description="I am allergic to pineapple.",
            metadata={"intent": "user_question"},
        ),
    )
    _store_event(
        engine,
        Event(
            timestamp=1_700_390_100,
            entity_id="alice",
            event_type="user_question",
            description="My father is a big fan of pineapple pie.",
            metadata={"intent": "user_question"},
        ),
    )

    facts = [
        item for item in engine.get_memory(entity_id="alice") if item.intent == "inferred_user_fact"
    ]
    subjects = {_relation_value(item, "fact_subject:") for item in facts}
    assert "user" in subjects
    assert "father" in subjects
    conflicts = [
        item
        for item in engine.get_memory(entity_id="alice")
        if item.intent == "inferred_user_fact_conflict"
    ]
    assert len(conflicts) == 0


def test_fact_inference_normalizes_preference_entities(engine) -> None:
    _store_event(
        engine,
        Event(
            timestamp=1_700_391_000,
            entity_id="alice",
            event_type="user_question",
            description=(
                "I love me some taylor swift and I love it when someone knows me well. "
                "My favourite car is none other than porshe cayen."
            ),
            metadata={"intent": "user_question"},
        ),
    )

    facts = [
        item for item in engine.get_memory(entity_id="alice") if item.intent == "inferred_user_fact"
    ]
    fact_keys = {_relation_value(item, "fact_key:") for item in facts}
    summaries = {item.summary.lower() for item in facts}
    assert "preference_like:taylor_swift" in fact_keys
    assert "preference_like:porsche_cayenne" in fact_keys
    assert not any("someone knows" in summary for summary in summaries)


def test_contradicting_allergy_creates_conflict_guard(engine) -> None:
    _store_event(
        engine,
        Event(
            timestamp=1_700_395_000,
            entity_id="alice",
            event_type="user_question",
            description="I am allergic to pineapple.",
            metadata={"intent": "user_question"},
        ),
    )
    _store_event(
        engine,
        Event(
            timestamp=1_700_395_100,
            entity_id="alice",
            event_type="user_question",
            description="I am not allergic to pineapple anymore.",
            metadata={"intent": "user_question"},
        ),
    )

    memories = engine.get_memory(entity_id="alice")
    conflict_guards = [
        item for item in memories if item.intent == "inferred_user_fact_conflict"
    ]
    assert len(conflict_guards) == 1
    guard = conflict_guards[0]
    assert "clarification" in guard.content.lower()
    assert _relation_value(guard, "fact_key:") == "allergy:pineapple"
    assert _relation_value(guard, "clarification_required:") == "true"

    contested_facts = [
        item
        for item in memories
        if item.intent == "inferred_user_fact"
        and _relation_value(item, "fact_key:") == "allergy:pineapple"
        and _relation_value(item, "fact_status:") == "contested"
    ]
    assert len(contested_facts) >= 1
    assert any(
        relation.startswith("conflicts_with:")
        for relation in contested_facts[-1].relationships
    )


def test_confirmed_allergy_change_supersedes_old_fact(engine) -> None:
    _store_event(
        engine,
        Event(
            timestamp=1_700_396_000,
            entity_id="alice",
            event_type="user_question",
            description="I am allergic to pineapple.",
            metadata={"intent": "user_question"},
        ),
    )
    _store_event(
        engine,
        Event(
            timestamp=1_700_396_100,
            entity_id="alice",
            event_type="user_question",
            description="Doctor confirmed I am not allergic to pineapple anymore.",
            metadata={"intent": "user_question"},
        ),
    )

    memories = engine.get_memory(entity_id="alice")
    allergy_facts = [
        item
        for item in memories
        if item.intent == "inferred_user_fact"
        and _relation_value(item, "fact_key:") == "allergy:pineapple"
    ]
    assert len(allergy_facts) == 1
    assert _relation_value(allergy_facts[0], "fact_polarity:") == "negative"
    assert _relation_value(allergy_facts[0], "fact_status:") == "superseding"


def test_failed_attempts_create_recurring_failure_inference(engine) -> None:
    attempts = [
        "I failed again: TypeError when indexing a list with string keys.",
        "Still failing with TypeError list indexing in Python.",
        "Another wrong attempt: list index TypeError keeps happening.",
    ]
    for idx, description in enumerate(attempts):
        _store_event(
            engine,
            Event(
                timestamp=1_700_400_000 + idx,
                entity_id="alice",
                event_type="user_attempt",
                description=description,
                metadata={"intent": "user_attempt"},
            ),
        )

    memories = engine.get_memory(entity_id="alice")
    inferred = [
        item
        for item in memories
        if item.intent == "inferred_learning_pattern"
        and "repeatedly struggles with" in item.content.lower()
    ]

    assert len(inferred) == 1
    assert "typeerror" in inferred[0].content.lower()


def test_repeated_positive_assessments_create_progress_inference(engine) -> None:
    outcomes = [
        "Assessment passed: Alice correctly solved a Python class design task.",
        "Assessment passed: Alice completed a module architecture exercise correctly.",
        "Assessment passed: Alice solved project structure planning with the right approach.",
    ]
    for idx, description in enumerate(outcomes):
        _store_event(
            engine,
            Event(
                timestamp=1_700_500_000 + idx,
                entity_id="alice",
                event_type="assessment_result",
                description=description,
                metadata={"intent": "assessment_result"},
            ),
        )

    memories = engine.get_memory(entity_id="alice")
    inferred_progress = [
        item
        for item in memories
        if item.intent == "learning_progress"
        and item.content.lower().startswith("inferred progress:")
    ]

    assert len(inferred_progress) == 1
    assert "has progressed" in inferred_progress[0].content.lower()


def test_inferred_signature_refresh_supersedes_old_memory(tmp_path: Path) -> None:
    config = EngineConfig(
        sqlite_path=str(tmp_path / "refresh.db"),
        metrics_path=str(tmp_path / "metrics.json"),
        embedding_dim=64,
        persistent_confidence_prior=0.0,
        ephemeral_confidence_prior=0.0,
        ranker_min_training_samples=2,
        ranker_training_batch_size=2,
        personalization_repeat_threshold=2,
        personalization_similarity_threshold=0.1,
        personalization_inferred_refresh_days=0,
        personalization_lifecycle_check_interval_seconds=0,
    )
    local_engine = DecisionEngine(config=config)
    try:
        for idx in range(2):
            _store_event(
                local_engine,
                Event(
                    timestamp=1_700_600_000 + idx,
                    entity_id="alice",
                    event_type="user_attempt",
                    description="Still failing list indexing with TypeError in Python.",
                    metadata={"intent": "user_attempt"},
                ),
            )
        first_snapshot = [
            item
            for item in local_engine.get_memory(entity_id="alice")
            if item.intent == "inferred_learning_pattern"
            and "repeatedly struggles with" in item.content.lower()
        ]
        assert len(first_snapshot) == 1
        first_id = first_snapshot[0].memory_id

        _store_event(
            local_engine,
            Event(
                timestamp=1_700_600_100,
                entity_id="alice",
                event_type="user_attempt",
                description="I keep failing list indexing and get a TypeError again.",
                metadata={"intent": "user_attempt"},
            ),
        )
        refreshed_snapshot = [
            item
            for item in local_engine.get_memory(entity_id="alice")
            if item.intent == "inferred_learning_pattern"
            and "repeatedly struggles with" in item.content.lower()
        ]
        assert len(refreshed_snapshot) == 1
        assert refreshed_snapshot[0].memory_id != first_id
    finally:
        local_engine.close()


def test_inferred_memory_ttl_expires_and_is_pruned(tmp_path: Path) -> None:
    db_path = tmp_path / "ttl.db"
    config = EngineConfig(
        sqlite_path=str(db_path),
        metrics_path=str(tmp_path / "metrics.json"),
        embedding_dim=64,
        persistent_confidence_prior=0.0,
        ephemeral_confidence_prior=0.0,
        ranker_min_training_samples=2,
        ranker_training_batch_size=2,
        personalization_repeat_threshold=2,
        personalization_similarity_threshold=0.1,
        personalization_inferred_ttl_days=1,
        personalization_lifecycle_check_interval_seconds=0,
    )
    local_engine = DecisionEngine(config=config)
    try:
        for idx in range(2):
            _store_event(
                local_engine,
                Event(
                    timestamp=1_700_700_000 + idx,
                    entity_id="alice",
                    event_type="user_attempt",
                    description="I failed with TypeError on list indexing.",
                    metadata={"intent": "user_attempt"},
                ),
            )
        inferred = [
            item
            for item in local_engine.get_memory(entity_id="alice")
            if item.intent == "inferred_learning_pattern"
            and "repeatedly struggles with" in item.content.lower()
        ]
        assert len(inferred) == 1
        inferred_id = inferred[0].memory_id

        stale_timestamp = (datetime.now(UTC) - timedelta(days=3)).isoformat()
        with sqlite3.connect(db_path) as conn:
            conn.execute(
                "UPDATE memories SET created_at = ?, updated_at = ? WHERE memory_id = ?",
                (stale_timestamp, stale_timestamp, inferred_id),
            )
            conn.commit()

        _store_event(
            local_engine,
            Event(
                timestamp=1_700_700_200,
                entity_id="alice",
                event_type="user_question",
                description="What should I focus on now?",
                metadata={"intent": "user_question"},
            ),
        )

        remaining_ids = {
            item.memory_id for item in local_engine.get_memory(entity_id="alice")
        }
        assert inferred_id not in remaining_ids
    finally:
        local_engine.close()


def test_fact_extraction_uses_raw_ingest_text_before_truncation(tmp_path: Path) -> None:
    config = EngineConfig(
        sqlite_path=str(tmp_path / "raw_fact_capture.db"),
        metrics_path=str(tmp_path / "metrics.json"),
        embedding_dim=64,
        max_content_chars=180,
        assistant_max_content_chars=180,
        persistent_confidence_prior=0.0,
        ephemeral_confidence_prior=0.0,
        ranker_min_training_samples=2,
        ranker_training_batch_size=2,
        personalization_lifecycle_check_interval_seconds=0,
    )
    local_engine = DecisionEngine(config=config)
    try:
        filler = " ".join(f"padding{i}" for i in range(180))
        source_id = _store_event(
            local_engine,
            Event(
                timestamp=1_700_800_000,
                entity_id="alice",
                event_type="user_question",
                description=(
                    f"{filler}. "
                    "I am allergic to pineapple. "
                    "I am currently at 58 and I need to be at 64 by the end of the month "
                    "for army medical interview."
                ),
                metadata={"intent": "user_question"},
            ),
        )

        memories = local_engine.get_memory(entity_id="alice")
        source_memory = next(item for item in memories if item.memory_id == source_id)
        assert "truncated" in source_memory.content.lower()

        inferred_facts = [
            item for item in memories if item.intent == "inferred_user_fact"
        ]
        assert any(
            _relation_value(item, "fact_key:") == "allergy:pineapple"
            for item in inferred_facts
        )
        assert any(
            _relation_value(item, "fact_key:") == "weight_current:58"
            for item in inferred_facts
        )
        assert any(
            _relation_value(item, "fact_key:") == "weight_target:64"
            for item in inferred_facts
        )
        assert any(
            (_relation_value(item, "fact_key:") or "").startswith("weight_goal_reason:")
            and "army medical interview"
            in ((_relation_value(item, "fact_key:") or "").replace("_", " "))
            for item in inferred_facts
        )
    finally:
        local_engine.close()


def test_weight_current_fact_supersedes_previous_value(engine) -> None:
    _store_event(
        engine,
        Event(
            timestamp=1_700_900_000,
            entity_id="alice",
            event_type="user_question",
            description="I am currently at 58 kg.",
            metadata={"intent": "user_question"},
        ),
    )
    _store_event(
        engine,
        Event(
            timestamp=1_700_900_100,
            entity_id="alice",
            event_type="user_question",
            description="Update: I am currently at 61 kg now.",
            metadata={"intent": "user_question"},
        ),
    )

    inferred_facts = [
        item for item in engine.get_memory(entity_id="alice") if item.intent == "inferred_user_fact"
    ]
    current_weights = [
        item
        for item in inferred_facts
        if (_relation_value(item, "fact_key:") or "").startswith("weight_current:")
    ]
    assert len(current_weights) == 1
    assert _relation_value(current_weights[0], "fact_key:") == "weight_current:61"
    assert _relation_value(current_weights[0], "fact_status:") == "superseding"
    assert any(
        relation.startswith("supersedes:") for relation in current_weights[0].relationships
    )
