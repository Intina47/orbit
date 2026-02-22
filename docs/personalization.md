# Adaptive Personalization Guide

Orbit now supports adaptive personalization out of the box.

You do not need a separate personalization service. If you ingest events and send feedback, Orbit creates inferred profile memories automatically.

## What Orbit Infers Automatically

- `inferred_learning_pattern`:
  Orbit detects repeated semantically similar questions from the same user and stores a profile memory such as:
  "User repeatedly asks about X; reinforce this topic before advancing."
- `inferred_preference`:
  Orbit tracks feedback outcomes on assistant responses and stores preference memories such as:
  "User responds better to concise explanations."

These inferred memories are persisted and returned by normal retrieval calls.

## Minimal Integration (FastAPI Chatbot)

```python
from orbit import MemoryEngine

orbit = MemoryEngine(api_key="<jwt-token>")

def handle_chat(user_id: str, message: str) -> str:
    # 1) Store user input
    orbit.ingest(
        content=message,
        event_type="user_question",
        entity_id=user_id,
    )

    # 2) Retrieve personalized context (includes inferred memories)
    context = orbit.retrieve(
        query=f"What should I know about {user_id} for: {message}",
        entity_id=user_id,
        limit=5,
    )

    # 3) Call your LLM and generate answer
    answer = "<llm-response>"

    # 4) Store assistant response
    orbit.ingest(
        content=answer,
        event_type="assistant_response",
        entity_id=user_id,
    )
    return answer

def handle_feedback(memory_id: str, helpful: bool) -> None:
    orbit.feedback(
        memory_id=memory_id,
        helpful=helpful,
        outcome_value=1.0 if helpful else -1.0,
    )
```

## Recommended Event Taxonomy

Use consistent `event_type` values:

- `user_question`: user asks for help
- `assistant_response`: model response
- `learning_progress`: user milestone ("completed lesson 7")
- `assessment_result`: result of a check or quiz

For best personalization quality, always include `entity_id` as the stable user ID.

## Testing Personalization Quickly

1. Ask the same topic in different ways 3+ times with the same `entity_id`.
2. Mark relevant memories as helpful/unhelpful using `feedback`.
3. Run retrieval with the same `entity_id`.
4. Verify inferred memories appear:

```python
results = orbit.retrieve(
    query="What do we know about this learner's weak spots?",
    entity_id="alice",
    limit=10,
)
for memory in results.memories:
    print(memory.metadata.get("intent"), memory.content)
```

You should see `inferred_learning_pattern` and `inferred_preference` entries after enough signal.

## Runtime Controls (Env Vars)

- `MDE_ENABLE_ADAPTIVE_PERSONALIZATION` (default: `true`)
- `MDE_PERSONALIZATION_REPEAT_THRESHOLD` (default: `3`)
- `MDE_PERSONALIZATION_SIMILARITY_THRESHOLD` (default: `0.82`)
- `MDE_PERSONALIZATION_WINDOW_DAYS` (default: `30`)
- `MDE_PERSONALIZATION_MIN_FEEDBACK_EVENTS` (default: `4`)
- `MDE_PERSONALIZATION_PREFERENCE_MARGIN` (default: `2.0`)
