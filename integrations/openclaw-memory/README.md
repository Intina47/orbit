# @orbit/openclaw-memory

OpenClaw plugin skeleton that connects agent runs to Orbit Memory Infrastructure.

What this skeleton already does:

- registers as an OpenClaw `memory` slot plugin
- loads Orbit config from environment variables
- retrieves top memories in `before_agent_start` and injects them into the prompt
- ingests user input and assistant output on `agent_end`
- exposes utility interfaces:
  - command: `orbit-memory-status`
  - tool: `orbit_recall`
  - tool: `orbit_feedback`

## Directory

- `openclaw.plugin.json`: OpenClaw plugin manifest
- `src/index.ts`: plugin entrypoint and hook wiring
- `src/orbit-client.ts`: Orbit REST API client wrapper
- `src/identity.ts`: entity-id mapping from OpenClaw context
- `src/config.ts`: env-based config parsing

## Build

```bash
cd integrations/openclaw-memory
npm install
npm run build
```

## Required env vars

At runtime, set:

- `ORBIT_JWT_TOKEN`: Orbit API JWT (Bearer token)
- `ORBIT_API_URL`: Orbit API base URL (default: `http://127.0.0.1:8000`)

Optional tuning:

- `ORBIT_MEMORY_LIMIT` (default `5`)
- `ORBIT_ENTITY_PREFIX` (default `openclaw`)
- `ORBIT_USER_EVENT_TYPE` (default `user_prompt`)
- `ORBIT_ASSISTANT_EVENT_TYPE` (default `assistant_response`)
- `ORBIT_CAPTURE_ASSISTANT_OUTPUT` (default `true`)

## OpenClaw install notes

This package exports:

```json
"openclaw.extensions": {
  "plugin": "./dist/index.js"
}
```

and includes `openclaw.plugin.json` with `category: "memory"` and a `memory` slot definition.

Install it into your OpenClaw environment as a normal npm package, then enable it in your OpenClaw plugin/memory slot configuration.

## Smoke test flow

1. Start Orbit API (`http://127.0.0.1:8000`) with valid JWT settings.
2. Set plugin env vars (`ORBIT_JWT_TOKEN`, `ORBIT_API_URL`).
3. Start OpenClaw with this plugin enabled.
4. Run one agent task with repeated user context.
5. Confirm:
   - `before_agent_start` injects `Orbit memory context (already ranked): ...`
   - `agent_end` writes user and assistant events into Orbit
   - `orbit-memory-status` returns Orbit status JSON

## Next hardening steps

- bind to OpenClaw identity-links/session APIs for first-class entity mapping
- add retry/circuit-breaker logic around Orbit API calls
- add redaction policy before ingesting assistant output
- add plugin unit tests with mocked OpenClaw API and mocked Orbit API
