# Orbit Node.js API-Key Chatbot (No SDK)

This example is a minimal Node.js chatbot that integrates with Orbit using direct HTTP calls and an `orbit_pk_...` API key.

What this proves:

- Orbit can be integrated from Node.js without the Python SDK.
- `ingest -> retrieve -> feedback` works with API key auth.
- You can run a personalization test loop with only REST endpoints.

## Run locally

1. Start Orbit API (self-hosted) or use your Orbit Cloud base URL.
2. Copy environment file and fill in your API key.
3. Start the chatbot web app.

```bash
cd examples/nodejs_orbit_api_chatbot
cp .env.example .env
npm install
npm run dev
```

Open `http://localhost:8030`.

## Required environment variables

```bash
ORBIT_API_BASE_URL=http://localhost:8000
ORBIT_API_KEY=orbit_pk_replace_me
```

Optional:

```bash
OLLAMA_HOST=http://localhost:11434
OLLAMA_MODEL=llama3.1
ORBIT_RETRIEVE_LIMIT=5
PORT=8030
```

## API flow used in this example

1. `POST /v1/ingest` for the user message.
2. `GET /v1/retrieve` for ranked memory context.
3. LLM response generation (Ollama, with deterministic fallback).
4. `POST /v1/ingest` for assistant response memory.
5. `POST /v1/feedback` when the user clicks Helpful/Not helpful.

## Files

- `server.mjs`: Express API + Orbit calls
- `public/index.html`: browser UI for testing memory behavior
- `.env.example`: runtime config template
