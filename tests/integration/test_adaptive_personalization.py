from __future__ import annotations

from memory_engine.models.event import Event


def _store_event(engine, event: Event) -> str:
    processed = engine.process_input(event)
    decision = engine.make_storage_decision(processed)
    stored = engine.store_memory(processed, decision)
    assert stored is not None
    return stored.memory_id


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
