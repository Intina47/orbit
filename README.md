# Orbit

Memory infrastructure for developer-facing AI applications.

Orbit gives your app long-term memory with adaptive personalization, relevance ranking, and feedback learning.  
You integrate once, then use the same simple loop everywhere: `ingest -> retrieve -> feedback`.

Project status: `Alpha` (`0.1.x`)

## Readme language selector

Pick your preferred language. Each link points to a translated README that mirrors the core setup, integration, and operational guidance in the chosen language.

- 🇬🇧 [English (this page)](README.md)
- 🇨🇳 [简体中文](README.zh.md)
- 🇪🇸 [Español](README.es.md)
- 🇩🇪 [Deutsch](README.de.md)
- 🇯🇵 [日本語](README.ja.md)
- 🇧🇷 [Português (Brasil)](README.pt-BR.md)

Translations are community maintained; if you improve a translation, please send a pull request so everyone benefits.

## What Orbit Is

Orbit is a memory layer for AI products where context quality matters over time.

Orbit handles:

- event ingestion and durable memory storage
- semantic retrieval with ranking and intent-aware reweighting
- adaptive inferred memories (learning patterns, progress, preferences)
- feedback-driven ranking updates
- provenance metadata for debugging why a memory was surfaced
- API runtime concerns (JWT auth, rate limits, idempotency, observability)

## Why Orbit

Without a memory layer, many assistants either forget important user signals or overload prompts with noisy history.  
Orbit is built to return small, high-signal context sets that improve answer quality while staying explainable.

## Repository Layout

| Path | Purpose |
| --- | --- |
| `src/orbit/` | Public Python SDK (`MemoryEngine`, `AsyncMemoryEngine`) |
| `src/orbit_api/` | FastAPI runtime (`/v1/ingest`, `/v1/retrieve`, `/v1/feedback`, etc.) |
| `src/memory_engine/` | Memory orchestration and adaptive personalization |
| `src/decision_engine/` | Core decision/ranking/storage primitives |
| `examples/` | Working integration samples |
| `docs/` | Deployment, integration, and operational docs |

## Quickstart (5 Minutes)

### 1) Install

Published package:

```bash
pip install orbit-memory
```

Local repository install:

```bash
pip install -e .
```

### 2) Start Orbit API Locally

Recommended full local stack (API + Postgres + Prometheus + Alertmanager + OpenTelemetry collector):

```bash
docker compose up --build
```

### 3) Generate a Local JWT

```bash
python scripts/generate_jwt.py \
  --secret orbit-dev-secret-change-me \
  --issuer orbit \
  --audience orbit-api \
  --subject local-dev
```

### 4) Integrate with the SDK

```python
from orbit import MemoryEngine

engine = MemoryEngine(
    api_key="<jwt-token>",
    base_url="http://localhost:8000",
)

engine.ingest(
    content="I keep confusing for-loops and while-loops.",
    event_type="user_question",
    entity_id="alice",
)

retrieval = engine.retrieve(
    query="What should I know about alice before answering?",
    entity_id="alice",
    limit=5,
)

if retrieval.memories:
    engine.feedback(
        memory_id=retrieval.memories[0].memory_id,
        helpful=True,
        outcome_value=1.0,
    )
```

### 5) Optional Direct API Call

```bash
curl -X POST http://localhost:8000/v1/ingest \
  -H "Authorization: Bearer <jwt-token>" \
  -H "Content-Type: application/json" \
  -d '{"content":"User completed first lesson","event_type":"learning_progress","entity_id":"alice"}'
```

## Integration Paths

| Mode | Best for | Entry point |
| --- | --- | --- |
| Python SDK | Python apps wanting fastest integration | `from orbit import MemoryEngine` |
| REST API | Non-Python or service-to-service integration | `POST /v1/ingest`, `GET /v1/retrieve`, `POST /v1/feedback` |
| Node.js (no SDK) | JavaScript apps using direct HTTP + API keys | `examples/nodejs_orbit_api_chatbot/` |
| OpenClaw plugin | Agent workflows in OpenClaw | `integrations/openclaw-memory/` |

## Core Concepts

| Concept | Description |
| --- | --- |
| `entity_id` | Stable identity key for a user, agent, or account |
| `ingest` | Add a memory signal (`user_question`, `assistant_response`, etc.) |
| `retrieve` | Fetch ranked context memories for a query |
| `feedback` | Send outcome quality signal (`helpful`, `outcome_value`) |
| inferred memory | Auto-generated memory from repeated patterns/feedback |
| inference provenance | `why/when/type/derived_from` metadata for traceability |

## Architecture Overview

1. Application sends events to Orbit.
2. Orbit processes and stores memories.
3. Retrieval ranks candidate memories for each query.
4. Feedback updates ranking behavior and personalization state.
5. Adaptive engine emits inferred memories when confidence thresholds are met.

High-level flow:

`App -> Orbit API/SDK -> Memory Engine -> Storage/Ranker -> Retrieved Context -> App`

## Configuration

Core settings live in `.env.example`.

Most important environment variables:

| Area | Variables |
| --- | --- |
| Storage | `MDE_DATABASE_URL`, `MDE_SQLITE_PATH`, `MDE_EMBEDDING_DIM` |
| Providers | `MDE_EMBEDDING_PROVIDER`, `MDE_SEMANTIC_PROVIDER` |
| Auth | `ORBIT_JWT_SECRET`, `ORBIT_JWT_ISSUER`, `ORBIT_JWT_AUDIENCE`, `ORBIT_JWT_REQUIRED_SCOPE` |
| API runtime | `ORBIT_API_HOST`, `ORBIT_API_PORT`, `ORBIT_ENV` |
| Limits | `ORBIT_RATE_LIMIT_EVENTS_PER_DAY`, `ORBIT_RATE_LIMIT_QUERIES_PER_DAY`, `ORBIT_RATE_LIMIT_PER_MINUTE` |
| Personalization | `MDE_ENABLE_ADAPTIVE_PERSONALIZATION` and `MDE_PERSONALIZATION_*` |
| Observability | `ORBIT_OTEL_SERVICE_NAME`, `ORBIT_OTEL_EXPORTER_ENDPOINT`, `ALERTMANAGER_SLACK_WEBHOOK_URL`, `ALERTMANAGER_EMAIL_*` |

## Provider Adapters

Supported adapter families:

- OpenAI
- Anthropic
- Gemini
- Ollama
- deterministic/context local fallback

Optional extras:

```bash
pip install "orbit-memory[anthropic]"
pip install "orbit-memory[gemini]"
pip install "orbit-memory[ollama]"
pip install "orbit-memory[llm-adapters]"
```

## Production Readiness Checklist

- use PostgreSQL (`MDE_DATABASE_URL`) instead of SQLite fallback
- run schema migrations (`python -m alembic upgrade head`)
- enforce strict JWT verification (`ORBIT_ENV=production` + non-default secrets)
- configure API limits and batch caps
- enable metrics + tracing and scrape `/v1/metrics`
- configure Alertmanager routes for Slack/email delivery
- set backup/retention policies for primary database
- load-test retrieval quality under long horizons

## Monitoring and Operations

Operational endpoints:

- `GET /v1/health`
- `GET /v1/status`
- `GET /v1/metrics`
- `GET /v1/memories` (paginated memory inspection)

Response headers include:

- `X-RateLimit-Limit`
- `X-RateLimit-Remaining`
- `X-RateLimit-Reset`
- `Retry-After` (`429`)
- `X-Idempotency-Replayed` (write endpoints)

## Examples

- Live Orbit + Ollama chatbot: `examples/live_chatbot_ollama/`
- Node.js API-key chatbot (no SDK): `examples/nodejs_orbit_api_chatbot/`
- Polyglot direct API clients (Node/Python/Go): `examples/http_api_clients/`
- OpenClaw memory plugin scaffold: `integrations/openclaw-memory/`
- API + deployment runbook: `docs/DEPLOY_RENDER_VERCEL.md`
- GCP Cloud Run deployment runbook: `docs/DEPLOY_GCP_CLOUD_RUN.md`
- GCP environment matrix: `docs/GCP_ENV_MATRIX.md`

## Evaluation and Quality

Baseline scorecard:

```bash
python scripts/run_orbit_eval.py --output-dir eval_reports/latest
```

Long-horizon personalization soak:

```bash
python scripts/soak_personalization.py \
  --output-dir soak_reports/latest \
  --sqlite-path tmp/orbit_soak.db \
  --turns-per-persona 500
```

## Troubleshooting

| Symptom | Likely cause | Fix |
| --- | --- | --- |
| `401 Unauthorized` | invalid/missing JWT or claim mismatch | verify `iss`, `aud`, `exp`, signing secret |
| `429 Too Many Requests` | rate limit exhausted | respect `Retry-After`, tune limits |
| `409 Conflict` on writes | idempotency key reused with different payload | use unique keys per payload |
| weak personalization | unstable `entity_id` or missing feedback | keep stable entity mapping and send feedback |

## Contributing

Local validation commands:

```bash
python -m ruff check src tests
python -m mypy src
python -m pytest -q
python -m pylint src tests scripts --fail-under=9.0
```

Make targets:

```bash
make lint
make type-check
make format-check
make test
make migrate
make run-api
```

## Documentation

- Canonical developer integration guide: `docs/developer_documentation.md`
- Deployment (Render/Vercel): `docs/DEPLOY_RENDER_VERCEL.md`
- Deployment (GCP Cloud Run): `docs/DEPLOY_GCP_CLOUD_RUN.md`
- GCP env matrix: `docs/GCP_ENV_MATRIX.md`
- Cloud dashboard/API-key plan: `docs/ORBIT_CLOUD_DASHBOARD_PLAN.md`
- Engine internal manual: `docs/ENGINE_MANUAL.md`
- Build and implementation log: `BUILD_AND_SPEC.md`
- Repo metadata for discovery: `metaData.md`

## License, Security, Support

- License: add a `LICENSE` file before public OSS distribution.
- Security policy: add a `SECURITY.md` for vulnerability reporting.
- Support: use GitHub Issues for bugs, feature requests, and integration questions.
