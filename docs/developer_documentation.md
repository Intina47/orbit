# Orbit Developer Documentation

This is the canonical integration guide for Orbit.

If you are building with Orbit, start here.

## What Orbit Is

Orbit is a memory infrastructure layer for developer-facing AI applications.

You send events (`ingest`), fetch relevant context (`retrieve`), and feed quality signals (`feedback`).
Orbit handles:

- memory storage and ranking
- decay and compression
- adaptive personalization (inferred profile memories)
- API runtime concerns (auth, quotas, rate limits, observability)

## Integration Modes

You can integrate Orbit in three ways.

| Mode | Use when | Entry point |
| --- | --- | --- |
| Python SDK | Your app is Python and you want fastest integration | `from orbit import MemoryEngine` |
| REST API | Non-Python stack or service-to-service architecture | `POST /v1/ingest`, `GET /v1/retrieve`, `POST /v1/feedback` |
| OpenClaw Plugin | You run OpenClaw agents and want memory wiring without custom glue code | `integrations/openclaw-memory/` |

## 5-Minute Integration (SDK)

Install:

```bash
pip install orbit-memory
```

Use:

```python
from orbit import MemoryEngine

engine = MemoryEngine(api_key="<jwt-token>", base_url="http://localhost:8000")

# 1) store user event
engine.ingest(
    content="I still don't understand Python for loops.",
    event_type="user_question",
    entity_id="alice",
)

# 2) retrieve context
results = engine.retrieve(
    query="What should I know about alice before answering?",
    entity_id="alice",
    limit=5,
)

# 3) send outcome signal
if results.memories:
    engine.feedback(
        memory_id=results.memories[0].memory_id,
        helpful=True,
        outcome_value=1.0,
    )
```

## Core Integration Contract

Always do these three things:

1. Use a stable `entity_id` for each user/agent.
2. Ingest both sides of the interaction:
   - user events (`user_question`, `assessment_result`, `learning_progress`)
   - assistant outputs (`assistant_response`)
3. Send feedback whenever you can (`helpful` plus `outcome_value`).

Without consistent `entity_id` and feedback, personalization quality will be limited.

## Recommended Event Taxonomy

Use consistent event types across your app.

| Event type | Meaning |
| --- | --- |
| `user_question` | User asks for help or clarification |
| `assistant_response` | Assistant/tutorial response |
| `learning_progress` | Milestone completed |
| `assessment_result` | Quiz/test/check outcome |
| `user_attempt` | User attempted a task/problem |
| `preference_stated` | Explicit user preference |

## Adaptive Personalization (Automatic Inferred Memory)

Orbit now creates inferred memories automatically when enough signal exists.

### Inferred memory types

- `inferred_learning_pattern`
  - Trigger: repeated semantically similar user patterns for same entity.
  - Example: "alice repeatedly asks about for loops."
  - Also triggers on recurring failure clusters from `user_attempt` / `assessment_result`.
  - Example: "alice repeatedly struggles with list indexing TypeError."
- `inferred_preference`
  - Trigger: consistent positive feedback trend on assistant response style.
  - Example: "alice prefers concise explanations."
- `learning_progress` (inferred)
  - Trigger: repeated positive progress/assessment signals over time.
  - Example: "alice has progressed in class design and project structure."

These inferred memories are stored as regular memories and appear in normal retrieval.

### Personalization controls

| Env var | Default | Purpose |
| --- | --- | --- |
| `MDE_ENABLE_ADAPTIVE_PERSONALIZATION` | `true` | Master switch |
| `MDE_PERSONALIZATION_REPEAT_THRESHOLD` | `3` | Repetitions needed for pattern inference |
| `MDE_PERSONALIZATION_SIMILARITY_THRESHOLD` | `0.82` | Semantic similarity threshold |
| `MDE_PERSONALIZATION_WINDOW_DAYS` | `30` | Pattern observation window |
| `MDE_PERSONALIZATION_MIN_FEEDBACK_EVENTS` | `4` | Feedback count needed for preference inference |
| `MDE_PERSONALIZATION_PREFERENCE_MARGIN` | `2.0` | Confidence margin before writing preference |
| `MDE_PERSONALIZATION_INFERRED_TTL_DAYS` | `45` | TTL for inferred memories before lifecycle expiry |
| `MDE_PERSONALIZATION_INFERRED_REFRESH_DAYS` | `14` | Minimum age before same-signature inferred memory can be refreshed/superseded |
| `MDE_PERSONALIZATION_LIFECYCLE_CHECK_INTERVAL_SECONDS` | `30` | Frequency of inferred-memory lifecycle scans (`0` = scan each write/feedback) |

## FastAPI Integration Pattern

```python
from fastapi import FastAPI
from orbit import MemoryEngine

app = FastAPI()
orbit = MemoryEngine(api_key="<jwt-token>", base_url="http://localhost:8000")

@app.post("/chat")
async def chat(user_id: str, message: str) -> dict[str, str]:
    orbit.ingest(
        content=message,
        event_type="user_question",
        entity_id=user_id,
    )

    context = orbit.retrieve(
        query=f"What should I know about {user_id} for: {message}",
        entity_id=user_id,
        limit=5,
    )

    prompt_context = "\n".join(f"- {m.content}" for m in context.memories)
    answer = f"(LLM answer using context)\n{prompt_context}"

    orbit.ingest(
        content=answer,
        event_type="assistant_response",
        entity_id=user_id,
    )
    return {"response": answer}

@app.post("/feedback")
async def feedback(memory_id: str, helpful: bool) -> dict[str, bool]:
    orbit.feedback(
        memory_id=memory_id,
        helpful=helpful,
        outcome_value=1.0 if helpful else -1.0,
    )
    return {"recorded": True}
```

## OpenClaw Plugin Integration (Skeleton)

Orbit now includes an OpenClaw plugin scaffold:

- package: `integrations/openclaw-memory/`
- npm name: `@orbit/openclaw-memory`
- plugin manifest: `integrations/openclaw-memory/openclaw.plugin.json`

Build:

```bash
cd integrations/openclaw-memory
npm install
npm run build
```

Required runtime env:

- `ORBIT_JWT_TOKEN`
- `ORBIT_API_URL` (default `http://127.0.0.1:8000`)

Behavior:

- `before_agent_start`: retrieves top Orbit memories and appends them to prompt input.
- `agent_end`: ingests user input and assistant output into Orbit.
- utility command/tool surfaces:
  - command: `orbit-memory-status`
  - tool: `orbit_recall`
  - tool: `orbit_feedback`

## SDK API Surface

Sync client:

- `MemoryEngine.ingest(content, event_type=None, metadata=None, entity_id=None)`
- `MemoryEngine.retrieve(query, limit=10, entity_id=None, event_type=None, time_range=None)`
- `MemoryEngine.feedback(memory_id, helpful, outcome_value=None)`
- `MemoryEngine.status()`
- `MemoryEngine.ingest_batch(events)`
- `MemoryEngine.feedback_batch(feedback)`

Async client:

- `AsyncMemoryEngine` provides async equivalents for the same methods.

## REST API Contract

Auth:

- Bearer JWT: `Authorization: Bearer <token>`
- Required claims: `sub`, `iat`, `exp`, `iss`, `aud`
- Optional required scope via `ORBIT_JWT_REQUIRED_SCOPE`
- Optional write idempotency: `Idempotency-Key: <key>` on `POST` endpoints

Endpoints:

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

### Ingest example

```bash
curl -X POST http://localhost:8000/v1/ingest \
  -H "Authorization: Bearer <jwt-token>" \
  -H "Idempotency-Key: ingest-alice-0001" \
  -H "Content-Type: application/json" \
  -d '{
    "content":"I keep confusing while loops and for loops",
    "event_type":"user_question",
    "entity_id":"alice"
  }'
```

### Retrieve example

```bash
curl "http://localhost:8000/v1/retrieve?query=What%20should%20I%20know%20about%20alice?&entity_id=alice&limit=5" \
  -H "Authorization: Bearer <jwt-token>"
```

Retrieve results include normalized inference provenance for debugging:

```json
{
  "memories": [
    {
      "memory_id": "mem_123",
      "metadata": {
        "intent": "inferred_learning_pattern",
        "inference_provenance": {
          "is_inferred": true,
          "why": "Repeated failure/error signals were detected across related attempts.",
          "when": "2026-02-23T18:20:00+00:00",
          "inference_type": "recurring_failure_pattern",
          "signature": "alice|recurring_failure_pattern|list indexing",
          "derived_from_memory_ids": ["mem_a", "mem_b"],
          "supersedes_memory_ids": ["mem_old_1"]
        }
      }
    }
  ]
}
```

### Feedback example

```bash
curl -X POST http://localhost:8000/v1/feedback \
  -H "Authorization: Bearer <jwt-token>" \
  -H "Idempotency-Key: feedback-alice-0001" \
  -H "Content-Type: application/json" \
  -d '{"memory_id":"<memory-id>","helpful":true,"outcome_value":1.0}'
```

## Local Self-Hosted Runtime

Start full stack:

```bash
docker compose up --build
```

Stack includes:

- Orbit API
- PostgreSQL
- Prometheus
- OpenTelemetry collector

Generate JWT for local tests:

```bash
python scripts/generate_jwt.py \
  --secret orbit-dev-secret-change-me \
  --issuer orbit \
  --audience orbit-api \
  --subject local-dev
```

Run migrations manually if needed:

```bash
python -m alembic upgrade head
```

Hosted deployment runbook:

- `docs/DEPLOY_RENDER_VERCEL.md` (Render API + Postgres + Vercel frontend)

## Configuration Reference (Most Important)

Core:

- `MDE_DATABASE_URL` (PostgreSQL runtime DSN)
- `MDE_SQLITE_PATH` (local fallback path)
- `MDE_EMBEDDING_DIM`

Provider selection:

- `MDE_EMBEDDING_PROVIDER`: `deterministic|openai|anthropic|gemini|ollama`
- `MDE_SEMANTIC_PROVIDER`: `context|openai|anthropic|gemini|ollama`

Auth:

- `ORBIT_ENV` (`development|production`; production enforces non-default JWT secret)
- `ORBIT_JWT_SECRET`
- `ORBIT_JWT_ISSUER`
- `ORBIT_JWT_AUDIENCE`
- `ORBIT_JWT_ALGORITHM`
- `ORBIT_JWT_REQUIRED_SCOPE` (optional)
- `ORBIT_CORS_ALLOW_ORIGINS` (comma-separated frontend origins, e.g. Vercel URL)

Rate limits:

- `ORBIT_RATE_LIMIT_EVENTS_PER_MONTH`
- `ORBIT_RATE_LIMIT_QUERIES_PER_MONTH`
- `ORBIT_RATE_LIMIT_FREE_API_KEYS`
- `ORBIT_RATE_LIMIT_PILOT_PRO_EVENTS_PER_MONTH`
- `ORBIT_RATE_LIMIT_PILOT_PRO_QUERIES_PER_MONTH`
- `ORBIT_RATE_LIMIT_PILOT_PRO_API_KEYS`
- `ORBIT_PILOT_PRO_ACCOUNT_KEYS` (invite-only Pilot Pro account allowlist)
- `ORBIT_USAGE_WARNING_THRESHOLD_PERCENT`
- `ORBIT_USAGE_CRITICAL_THRESHOLD_PERCENT`
- `ORBIT_RATE_LIMIT_PER_MINUTE`
- `ORBIT_MAX_INGEST_CONTENT_CHARS`
- `ORBIT_MAX_QUERY_CHARS`
- `ORBIT_MAX_BATCH_ITEMS`

Persistence:

- Quota counters are persisted in PostgreSQL table `api_account_usage`
- Idempotent write state/replay cache is persisted in PostgreSQL table `api_idempotency`

Observability:

- `ORBIT_OTEL_SERVICE_NAME`
- `ORBIT_OTEL_EXPORTER_ENDPOINT`

See `.env.example` for the full list.

## Provider Adapters

Orbit supports pluggable adapters for semantic + embedding paths.

Available:

- OpenAI
- Anthropic
- Gemini
- Ollama
- Deterministic local fallback

Optional dependency groups:

- `anthropic`
- `gemini`
- `ollama`
- `llm-adapters` (all three)

## Retrieval and Memory Quality Guidelines

For best results:

- Keep `entity_id` stable and scoped per user/session owner.
- Keep event types semantically correct.
- Capture assistant outputs, not just user prompts.
- Send feedback frequently.
- Use `limit=5` to `limit=10` for most chat cases.
- Filter by `entity_id` whenever personalization matters.

## Monitoring and Operations

Health:

- `GET /v1/health`

Metrics:

- `GET /v1/metrics` (Prometheus format)
- Prometheus UI: `http://localhost:9090`

Status:

- `GET /v1/status` (usage, storage, quota)

Rate limit headers:

- `X-RateLimit-Limit`
- `X-RateLimit-Remaining`
- `X-RateLimit-Reset`
- `Retry-After` on `429`
- `X-Idempotency-Replayed` on write endpoints (`true|false`)

## Evaluation Harness (Baseline vs Orbit)

Use the scorecard harness to measure whether Orbit is actually improving retrieval quality:

```bash
python scripts/run_orbit_eval.py --output-dir eval_reports/latest
```

Artifacts produced:

- `orbit_eval_scorecard.json`
- `orbit_eval_scorecard.md`

Key tracked metrics:

- `Precision@5`
- `Top1 relevant rate`
- `Personalization hit rate`
- `Predicted helpfulness rate`
- `Assistant noise rate`
- `Stale memory rate`

## Long-Horizon Soak Harness (Personalization Under Load)

Run the soak harness to stress personalization over long conversations (4 personas, 500-1000 turns each) with hard pass/fail gates:

```bash
python scripts/soak_personalization.py \
  --output-dir soak_reports/latest \
  --sqlite-path tmp/orbit_soak.db \
  --turns-per-persona 500
```

Artifacts produced:

- `personalization_soak_report.json`
- `personalization_soak_report.md`

Hard gate matrix includes:

- `precision_at_5`
- `top1_relevant_rate`
- `stale_memory_rate`
- `assistant_noise_rate`
- `provenance_type_coverage`
- `provenance_derived_from_coverage`

The JSON/Markdown reports include concrete failed retrieval traces with top-5 payloads and inference provenance.

## Troubleshooting

401 Unauthorized:

- JWT missing/invalid.
- `iss`/`aud` mismatch with API config.
- token expired.

429 Too Many Requests:

- Respect `Retry-After`.
- reduce call rate or increase configured limits.

409 Conflict:

- Same `Idempotency-Key` was reused with a different payload.

No personalization:

- ensure same `entity_id` is used.
- ensure adaptive personalization is enabled.
- ensure enough repeated signals and feedback were sent.

Slow or noisy retrieval:

- keep event taxonomy consistent.
- avoid very broad query text.
- send feedback on low quality memories.

## Production Readiness Checklist

- JWT secret/issuer/audience configured securely.
- PostgreSQL backup and retention configured.
- Prometheus scraping enabled.
- OTel export endpoint configured.
- Alerting on 401/429/5xx and latency SLOs.
- Migration workflow defined (`alembic upgrade head` in CI/CD).
- Integration tests include ingest -> retrieve -> feedback loop.

## Developer Validation Checklist

1. Ingest a user question and verify `stored=true`.
2. Retrieve with same `entity_id` and verify memory appears.
3. Send feedback and verify `recorded=true`.
4. Repeat a topic 3+ times and verify `inferred_learning_pattern` appears.
5. Run full quality gates:
   - `python -m ruff check src tests examples scripts`
   - `python -m mypy src`
   - `python -m pytest -q`
   - `python -m pylint src tests scripts --fail-under=9.0`

## Reference Files

- SDK: `src/orbit/`
- API service: `src/orbit_api/`
- Core engine: `src/memory_engine/`, `src/decision_engine/`
- Local chatbot integration: `examples/live_chatbot_ollama/`
- OpenClaw plugin skeleton: `integrations/openclaw-memory/`
- Build/spec log: `BUILD_AND_SPEC.md`
