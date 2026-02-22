# API Reference

## SDK

- `MemoryEngine.ingest(content, event_type=None, metadata=None, entity_id=None) -> IngestResponse`
- `MemoryEngine.retrieve(query, limit=10, entity_id=None, event_type=None, time_range=None) -> RetrieveResponse`
- `MemoryEngine.feedback(memory_id, helpful, outcome_value=None) -> FeedbackResponse`
- `MemoryEngine.status() -> StatusResponse`
- `MemoryEngine.ingest_batch(events) -> list[IngestResponse]`
- `MemoryEngine.feedback_batch(feedback) -> list[FeedbackResponse]`
- `AsyncMemoryEngine` supports async equivalents for all methods.

## Adaptive Personalization Behavior

When adaptive personalization is enabled, Orbit can store inferred memories automatically:

- `inferred_learning_pattern`
- `inferred_preference`

These appear in normal retrieval results and can be filtered with `event_type` in `retrieve(...)`.

## REST Endpoints

- Auth: Bearer JWT (`Authorization: Bearer <jwt-token>`)

- `POST /v1/ingest`
- `GET /v1/retrieve`
- `POST /v1/feedback`
- `POST /v1/ingest/batch`
- `POST /v1/feedback/batch`
- `GET /v1/status`
- `GET /v1/health`
- `GET /v1/metrics`
- `POST /v1/auth/validate`
- `GET /v1/memories`
