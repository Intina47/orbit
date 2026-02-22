# Troubleshooting

## 401 Unauthorized

- Ensure bearer token is a valid JWT signed with `ORBIT_JWT_SECRET`.
- Confirm JWT claims include `sub`, `iat`, `exp`, `iss`, and `aud`.
- Ensure `iss` and `aud` match `ORBIT_JWT_ISSUER` and `ORBIT_JWT_AUDIENCE`.
- Pass token via `Authorization: Bearer <token>`.

## 429 Rate Limit Exceeded

- Read `Retry-After` response header.
- Use SDK retries with exponential backoff (`max_retries`, `retry_backoff_factor`).

## Timeout Errors

- Increase `timeout_seconds` in `Config`.
- Verify API server health via `GET /v1/health`.

## Empty Retrieval Results

- Confirm ingestion succeeded with `stored=True`.
- Use `entity_id` filters consistently across ingest and retrieve.

## Inferred Personalization Memories Not Appearing

- Confirm adaptive personalization is enabled: `MDE_ENABLE_ADAPTIVE_PERSONALIZATION=true`.
- Ensure repeated events use the same `entity_id`.
- Send enough signal:
  - repeated topic events (`MDE_PERSONALIZATION_REPEAT_THRESHOLD`, default `3`)
  - enough positive feedback events (`MDE_PERSONALIZATION_MIN_FEEDBACK_EVENTS`, default `4`)
- Verify inferred intents by inspecting retrieval metadata (`inferred_learning_pattern`, `inferred_preference`).
