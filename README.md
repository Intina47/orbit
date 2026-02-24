# Orbit Memory Infrastructure

This repository now contains two layers:

- `src/orbit/`: public Python SDK (`MemoryEngine`, `AsyncMemoryEngine`).
- `src/orbit_api/`: FastAPI REST API (`/v1/ingest`, `/v1/retrieve`, `/v1/feedback`, etc).
- `src/memory_engine/` and `src/decision_engine/`: intelligent memory core used by the API.

## SDK Quickstart

```python
from orbit import MemoryEngine

engine = MemoryEngine(api_key="<jwt-token>")
engine.ingest(content="User completed task X", event_type="agent_decision")
results = engine.retrieve("What did the user do?")
```

## API Quickstart

Run full stack (PostgreSQL + API + Prometheus + OTel):

```bash
docker compose up --build
```

Generate a JWT token:

```bash
python scripts/generate_jwt.py \
  --secret orbit-dev-secret-change-me \
  --issuer orbit \
  --audience orbit-api \
  --subject local-dev
```

Call API:

```bash
curl -X POST http://localhost:8000/v1/ingest \
  -H "Authorization: Bearer <jwt-token>" \
  -H "Content-Type: application/json" \
  -d '{"content":"Agent selected strategy A","event_type":"agent_decision"}'
```

Live chatbot integration sample (Orbit + Ollama):

- `examples/live_chatbot_ollama/app.py`
- `examples/live_chatbot_ollama/README.md`

OpenClaw plugin scaffold (Orbit memory slot):

- `integrations/openclaw-memory/README.md`

Evaluation harness (baseline vs Orbit):

- `python scripts/run_orbit_eval.py --output-dir eval_reports/latest`

Long-horizon personalization soak (hard gate matrix + failed traces):

- `python scripts/soak_personalization.py --output-dir soak_reports/latest --sqlite-path tmp/orbit_soak.db --turns-per-persona 500`

## Core Quality Gates

```bash
python -m black --check src tests
python -m ruff check src tests
python -m mypy src
python -m pytest -q
python -m pylint src --fail-under=9.0
```

## Optional Provider Adapters

Runtime provider selection for core memory intelligence:

- `MDE_EMBEDDING_PROVIDER`: `deterministic`, `openai`, `anthropic`, `gemini`, `ollama`
- `MDE_SEMANTIC_PROVIDER`: `context`, `openai`, `anthropic`, `gemini`, `ollama`

Optional extras:

- `anthropic`
- `gemini`
- `ollama`
- `llm-adapters` (all adapter SDKs)

## Documentation

- `docs/developer_documentation.md`: canonical end-to-end integration guide (SDK, API, auth, personalization, deployment, ops).
- `docs/DEPLOY_RENDER_VERCEL.md`: production deployment runbook for Render API + Vercel frontend.
- `docs/GITHUB_PAGES_SETUP.md`: publish docs via GitHub Pages from branch (`main` + `/docs`, no Actions).
- `metaData.md`: repository SEO metadata (keywords, technologies, packages, integrations, discovery terms).
- `BUILD_AND_SPEC.md`: single implementation/spec tracking log.
- `docs/`: supplemental focused docs and reference materials.
