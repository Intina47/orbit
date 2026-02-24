# Orbit Frontend

Next.js frontend for Orbit docs, marketing pages, and dashboard key management.

## Local run

```bash
cp .env.example .env.local
npm install
npm run dev
```

Open:

- `http://localhost:3000/` for site/docs
- `http://localhost:3000/dashboard` for API key management

## Production auth model

Browser never holds Orbit API bearer credentials.

1. User signs in to dashboard (`password` or `oidc` mode).
2. Next.js server stores session in HTTP-only cookie.
3. `/api/dashboard/*` proxy exchanges session principal for a short-lived tenant-scoped Orbit JWT.
4. Proxy forwards request to Orbit API with that JWT.

## Required envs (recommended: exchange mode)

- `NEXT_PUBLIC_ORBIT_API_BASE_URL`
- `ORBIT_DASHBOARD_PROXY_AUTH_MODE=exchange`
- `ORBIT_DASHBOARD_ORBIT_JWT_SECRET`
- optional: `ORBIT_DASHBOARD_ORBIT_JWT_ISSUER`, `ORBIT_DASHBOARD_ORBIT_JWT_AUDIENCE`, `ORBIT_DASHBOARD_ORBIT_JWT_ALGORITHM`, `ORBIT_DASHBOARD_ORBIT_JWT_TTL_SECONDS`
- `ORBIT_DASHBOARD_SESSION_SECRET`
- optional: `ORBIT_DASHBOARD_SESSION_TTL_SECONDS`

Auth mode envs:

- Password mode:
  - `ORBIT_DASHBOARD_AUTH_MODE=password`
  - `ORBIT_DASHBOARD_AUTH_PASSWORD`
- OIDC mode:
  - `ORBIT_DASHBOARD_AUTH_MODE=oidc`
  - `ORBIT_DASHBOARD_OIDC_ISSUER_URL`
  - `ORBIT_DASHBOARD_OIDC_CLIENT_ID`
  - `ORBIT_DASHBOARD_OIDC_CLIENT_SECRET`
  - optional: `ORBIT_DASHBOARD_OIDC_REDIRECT_URI`, `ORBIT_DASHBOARD_OIDC_SCOPES`, `ORBIT_DASHBOARD_OIDC_PROMPT`, `ORBIT_DASHBOARD_OIDC_TENANT_CLAIMS`

Security controls:

- optional: `ORBIT_DASHBOARD_ALLOWED_ORIGINS`
- optional: `ORBIT_DASHBOARD_LOGIN_WINDOW_SECONDS`
- optional: `ORBIT_DASHBOARD_LOGIN_MAX_ATTEMPTS`
- optional: `ORBIT_DASHBOARD_LOGIN_LOCKOUT_SECONDS`

Legacy static mode (not recommended):

- `ORBIT_DASHBOARD_PROXY_AUTH_MODE=static`
- `ORBIT_DASHBOARD_SERVER_BEARER_TOKEN`

## OIDC provider quick envs

Google:

```bash
ORBIT_DASHBOARD_AUTH_MODE=oidc
ORBIT_DASHBOARD_OIDC_ISSUER_URL=https://accounts.google.com
ORBIT_DASHBOARD_OIDC_CLIENT_ID=<google-client-id>
ORBIT_DASHBOARD_OIDC_CLIENT_SECRET=<google-client-secret>
ORBIT_DASHBOARD_OIDC_SCOPES="openid profile email"
```

Auth0:

```bash
ORBIT_DASHBOARD_AUTH_MODE=oidc
ORBIT_DASHBOARD_OIDC_ISSUER_URL=https://<tenant>.us.auth0.com
ORBIT_DASHBOARD_OIDC_CLIENT_ID=<auth0-client-id>
ORBIT_DASHBOARD_OIDC_CLIENT_SECRET=<auth0-client-secret>
ORBIT_DASHBOARD_OIDC_SCOPES="openid profile email"
ORBIT_DASHBOARD_OIDC_TENANT_CLAIMS=org_id,organization
```

Clerk:

```bash
ORBIT_DASHBOARD_AUTH_MODE=oidc
ORBIT_DASHBOARD_OIDC_ISSUER_URL=https://<your-clerk-domain>
ORBIT_DASHBOARD_OIDC_CLIENT_ID=<clerk-client-id>
ORBIT_DASHBOARD_OIDC_CLIENT_SECRET=<clerk-client-secret>
ORBIT_DASHBOARD_OIDC_SCOPES="openid profile email"
```

## Vercel setup

In Vercel Project Settings -> Environment Variables, add the envs above for your chosen mode.

If frontend and Orbit API are on different domains, allow frontend origin in API CORS:

```bash
ORBIT_CORS_ALLOW_ORIGINS=https://your-app.vercel.app
```

## E2E tests

Playwright specs are in `tests/e2e/dashboard-auth.spec.ts`.

```bash
npm run test:e2e
```

If your app is already running, set:

```bash
PLAYWRIGHT_BASE_URL=http://127.0.0.1:3000
```

GitHub Actions workflow:

- `.github/workflows/front-end-e2e.yml`
- auto-runs only when repo variable `RUN_FRONTEND_E2E=true` (or manual dispatch).

## Live OIDC callback smoke test

Use local mock OIDC provider:

```bash
python -m uvicorn examples.mock_oidc_provider.app:app --host 127.0.0.1 --port 9100
```

Set frontend env (example):

```bash
ORBIT_DASHBOARD_AUTH_MODE=oidc
ORBIT_DASHBOARD_OIDC_ISSUER_URL=http://127.0.0.1:9100
ORBIT_DASHBOARD_OIDC_CLIENT_ID=orbit-dashboard-local
ORBIT_DASHBOARD_OIDC_CLIENT_SECRET=orbit-dashboard-local-secret
ORBIT_DASHBOARD_OIDC_REDIRECT_URI=http://127.0.0.1:3000/api/dashboard/auth/oidc/callback
```

Then run:

```bash
python scripts/live_oidc_callback_smoke.py
```
