# Quickstart

## Install

```bash
pip install orbit-memory
```

## Initialize

```python
from orbit import MemoryEngine

engine = MemoryEngine(api_key="<jwt-token>")
```

## Ingest

```python
engine.ingest(content="User completed lesson 10", event_type="learning_progress")
```

## Retrieve

```python
results = engine.retrieve("What do I know about this user?", limit=5)
```

## Feedback

```python
engine.feedback(memory_id=results.memories[0].memory_id, helpful=True, outcome_value=1.0)
```

## Adaptive Personalization

Orbit automatically creates inferred user-profile memories when it sees repeated patterns and feedback outcomes.

- Repeated similar questions -> `inferred_learning_pattern`
- Feedback trend on assistant responses -> `inferred_preference`

See `docs/personalization.md` for a full integration template.
