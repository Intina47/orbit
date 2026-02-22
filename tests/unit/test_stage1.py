from __future__ import annotations

from memory_engine.models.event import Event


def test_stage1_processes_event(engine) -> None:
    event = Event(
        timestamp=1_700_000_000,
        entity_id="user_123",
        event_type="preference_stated",
        description="User prefers concise API docs",
        metadata={"entities": ["project:orbit"], "intent": "preference_stated"},
    )
    processed = engine.process_input(event)
    assert processed.entity_id == "user_123"
    assert processed.event_type == "preference_stated"
    assert len(processed.embedding) == 64
    assert "user_123" in processed.entity_references


def test_stage1_compacts_default_assistant_response_summary(engine) -> None:
    long_response = "Assistant response: " + ("This explanation is intentionally verbose. " * 80)
    event = Event(
        timestamp=1_700_000_100,
        entity_id="user_123",
        event_type="assistant_response",
        description=long_response,
        metadata={},
    )

    processed = engine.process_input(event)

    assert processed.semantic_summary
    assert "assistant response:" not in processed.semantic_summary.lower()
    assert len(processed.semantic_summary.split()) <= 33
