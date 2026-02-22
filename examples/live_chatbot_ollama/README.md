# Live Testing: Orbit + Ollama Coding Tutor

This example gives you a realistic local integration test:

1. Orbit API stores/retrieves memory.
2. Ollama generates tutoring responses.
3. User feedback is sent back to Orbit learning loop.
4. Browser UI lets you test chat + retrieval ordering + feedback end-to-end.

## Prerequisites

- Docker + Docker Compose
- Ollama running locally (`http://localhost:11434`)
- Python 3.11+

## 1) Start Orbit Stack

```bash
docker compose up --build
```

This starts:
- PostgreSQL
- Orbit API
- Prometheus
- OpenTelemetry collector

## 2) Generate JWT Token

```bash
python scripts/generate_jwt.py \
  --secret orbit-dev-secret-change-me \
  --issuer orbit \
  --audience orbit-api \
  --subject local-dev
```

Export token:

```bash
export ORBIT_JWT_TOKEN="<paste-token>"
```

## 3) Run Chatbot API

```bash
export ORBIT_API_BASE_URL="http://localhost:8000"
export OLLAMA_HOST="http://localhost:11434"
export OLLAMA_MODEL="llama3.1"

python -m uvicorn examples.live_chatbot_ollama.app:app --reload --port 8010
```

The chatbot app now includes a test UI at:

- `http://localhost:8010/`

From the UI you can:

- chat with the tutor,
- submit helpful/unhelpful feedback for returned memory IDs,
- inspect current retrieval ordering from Orbit (`/context`).
- observe inferred personalization memories (`inferred_learning_pattern`, `inferred_preference`) once enough signal is present.

## 4) Run Live Chat Test

```bash
curl -X POST http://localhost:8010/chat \
  -H "Content-Type: application/json" \
  -d '{"user_id":"alice","message":"What is a for loop?"}'
```

Then submit feedback:

```bash
curl -X POST http://localhost:8010/feedback \
  -H "Content-Type: application/json" \
  -d '{"memory_id":"<memory-id-from-chat-response>","helpful":true,"outcome_value":1.0}'
```

Inspect retrieval ordering directly:

```bash
curl -X POST http://localhost:8010/context \
  -H "Content-Type: application/json" \
  -d '{"user_id":"alice","query":"What should I know about alice to teach coding effectively?","limit":5}'
```

You should eventually see inferred profile signals in returned metadata:

- repeated-topic patterns after similar questions,
- preference signals after helpful feedback on assistant responses.

## 5) Observe Metrics

- Orbit metrics: `http://localhost:8000/v1/metrics`
- Prometheus: `http://localhost:9090`
