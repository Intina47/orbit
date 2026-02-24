# Live Example: Personalized Meal Coach (Ollama + Orbit)

Consumer-facing test project to evaluate memory quality in a realistic product flow.

This app runs the same Ollama model in two modes:

- `baseline`: only short local chat history
- `orbit`: persistent Orbit memory via SDK (`ingest`, `retrieve`, `feedback`)

Use it to see personalization quality differences over repeated sessions.

## What this tests

- durable user facts (allergies, dislikes, goals)
- short-term request context (this week, quick meals)
- feedback loop impact on retrieval ranking
- memory quality over multiple turns

## Prerequisites

- Orbit API running locally (`http://localhost:8000`)
- Ollama running locally (`http://localhost:11434`)
- Python 3.11+

## Configure with `.env` (recommended)

Create a root `.env` file (or update existing one):

```env
ORBIT_JWT_TOKEN=<your-jwt>
ORBIT_API_BASE_URL=http://localhost:8000
OLLAMA_HOST=http://localhost:11434
OLLAMA_MODEL=llama3.1
MEAL_COACH_BASELINE_ITEMS=12
MEAL_COACH_ORBIT_LIMIT=5
```

This example auto-loads the nearest `.env` file at startup.

## Run the app

```powershell
python -m uvicorn examples.live_meal_coach_ollama.app:app --reload --port 8020
```

Open:

- `http://localhost:8020/`

## UI workflow

1. Keep mode on `orbit`
2. Click `Seed Demo Profile (Orbit)`
3. Ask meal-planning questions (allergies, budget, timing)
4. Rate returned memory IDs as helpful/unhelpful
5. Switch to `baseline` and ask similar questions
6. Compare context preview + answer quality

## CLI comparison harness

```powershell
python examples/live_meal_coach_ollama/compare_modes.py --base-url http://localhost:8020 --user-id ava
```

This runs the same message sequence through both modes and prints:

- returned context count
- top context preview snippets
- truncated answer output

## API endpoints

- `POST /chat`
- `POST /feedback`
- `POST /seed-profile`
- `POST /context`
- `POST /reset`

## Notes

- If `ORBIT_JWT_TOKEN` is missing, `baseline` still works; `orbit` endpoints return a clear error.
- `/reset` only clears local baseline history. Orbit memory persists in Orbit storage.
