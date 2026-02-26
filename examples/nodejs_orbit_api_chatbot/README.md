# Orbit Node.js API-Key Chatbot (No SDK)

This example is a minimal Node.js chatbot demonstrating direct HTTP integration with Orbit and using Ollama for LLM responses. It supports running against local services (local Ollama / local Orbit) or cloud services (Ollama Cloud, Orbit Cloud).

What this demonstrates:

- Integrating `ingest -> retrieve -> response -> ingest` from Node.js without the SDK.
- Using Ollama (local or cloud) for generation, with a deterministic fallback if unavailable.
- A streaming chat endpoint (`/api/chat/stream`) that emits incremental assistant output for better UX.

## Run the example (summary)

1. Choose whether to run local services or use cloud endpoints for Ollama and Orbit.
2. Copy the environment template and set the required keys/hosts.
3. Start the Node.js example.

```bash
cd examples/nodejs_orbit_api_chatbot
cp .env.example .env
npm install
node server.mjs
```

Open `http://localhost:8030` to try the UI, or call the API endpoints directly.

## Local vs Cloud (Ollama and Orbit)

Ollama:

- Local: run an Ollama server on your machine (default: `http://localhost:11434`) and set `OLLAMA_HOST` to that URL.
- Cloud: use the Ollama Cloud host `https://ollama.com` and set `OLLAMA_API_KEY` with your cloud API key.

The example code supports either env var names `OLLAMA_API_KEY` (recommended) or the legacy `OLLAMA_QWEN_API_KEY` as a fallback.

Orbit:

- Local Orbit API: run your Orbit server and point `ORBIT_API_BASE_URL` to `http://localhost:8000` (default for local dev).
- Orbit Cloud: set `ORBIT_API_BASE_URL` to your cloud base URL and `ORBIT_API_KEY` to an API key with `ingest/retrieve/feedback` permissions.

## Environment variables

Required:

```bash
ORBIT_API_BASE_URL=http://localhost:8000
ORBIT_API_KEY=orbit_pk_replace_me
```

Ollama (choose one, depending on local vs cloud):

```bash
# Local Ollama (default local server)
OLLAMA_HOST=http://localhost:11434

# OR
# Ollama Cloud
OLLAMA_HOST=https://ollama.com
OLLAMA_API_KEY=ollama_sk_replace_me
```

Optional:

```bash
OLLAMA_MODEL=llama3.1
ORBIT_RETRIEVE_LIMIT=5
PORT=8030
```

## How streaming works in this example

- The server provides `POST /api/chat` (non-streaming) and `POST /api/chat/stream` (streaming).
- `/api/chat/stream` returns a streaming response framed as Server-Sent Events (SSE)-style lines. The client can POST a JSON body and read the response body as a stream (the example includes a small fetch-based client sketch in `server.mjs` comments).
- Streaming preserves whitespace from the LLM so incremental deltas don't run words together. The server trims the final assembled assistant text before ingesting it into Orbit.

Client suggestion (browser): use `fetch` with `response.body.getReader()` and decode chunks, parsing SSE-like `data:` frames. See the `server.mjs` comments for a minimal client sketch.

## Example run commands (PowerShell and Git Bash)

PowerShell (set env in-session):

```powershell
cd .\examples\nodejs_orbit_api_chatbot
#$env:OLLAMA_API_KEY = 'your_ollama_key' # optional for cloud
#$env:ORBIT_API_KEY = 'your_orbit_key'
node server.mjs
```

Git Bash / MINGW64:

```bash
cd examples/nodejs_orbit_api_chatbot
export OLLAMA_API_KEY='your_ollama_key' # optional for cloud
export ORBIT_API_KEY='your_orbit_key'
node server.mjs
```

## API flow used in this example

1. `POST /v1/ingest` for the user message.
2. `GET /v1/retrieve` for ranked memory context.
3. LLM response generation (Ollama local or cloud, streaming supported).
4. `POST /v1/ingest` for assistant response memory.
5. `POST /v1/feedback` when the user clicks Helpful/Not helpful.

## Files

- `server.mjs`: Express API + Orbit calls and streaming endpoint
- `public/index.html`: browser UI for testing memory behavior (can be extended to consume stream)
- `.env.example`: runtime config template
