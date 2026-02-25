# Orbit Cloud Dashboard Plan (API Key Management)

This is the initial plan for the frontend dashboard where users manage Orbit API keys.

## Product goals

- Let a developer create and rotate API keys without support tickets.
- Keep key handling safe: show full secret exactly once.
- Make usage and quota visibility immediate after key creation.

## Phase 0 scope (first usable dashboard)

1. Authentication
   - Dashboard user login (Google/GitHub or email magic link).
   - Each user belongs to one `account`.

2. API key lifecycle
   - `Create key` (name + optional scope profile).
   - `List keys` (masked prefix + created_at + last_used_at + status).
   - `Revoke key`.
   - `Rotate key` (create new, revoke old in one guided flow).

3. Basic usage panel
   - Show current daily/monthly usage from Orbit API usage tables.
   - Show quota limits and reset windows.

## Backend model (proposed)

Table: `api_keys`
- `id` (uuid)
- `account_id` (uuid)
- `key_prefix` (string, indexed)
- `key_hash` (argon2/bcrypt hash of secret part)
- `name` (string)
- `scopes_json` (jsonb)
- `status` (`active`, `revoked`)
- `created_at`, `last_used_at`, `revoked_at`

Rules:
- Never store raw API keys.
- Key format suggestion: `orbit_pk_<public_prefix>_<secret>`.
- JWT can remain for internal/testing paths; cloud users should use API keys issued by dashboard.

## API surface (proposed)

- `POST /v1/dashboard/keys` -> create key (returns plaintext once)
- `GET /v1/dashboard/keys` -> list masked keys
- `POST /v1/dashboard/keys/{id}/revoke` -> revoke
- `POST /v1/dashboard/keys/{id}/rotate` -> rotate

## Frontend UX (proposed)

- `/dashboard`:
  - account overview + usage meters
  - key list table with quick actions
  - "Create key" modal with copy-once warning
- mandatory confirmation before revoke/rotate
- activity timeline: key created/revoked/used

## Security requirements

- Rate limit key-management endpoints separately.
- Audit log every key lifecycle operation.
- Require re-auth for destructive actions (revoke/rotate).
- Prevent exposing secret in logs, analytics, and error traces.

## Next implementation step

Start with backend key issuance primitives (hashing + storage + validation middleware), then wire dashboard UI after stable API contract.
