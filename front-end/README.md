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
  - optional: `ORBIT_DASHBOARD_OIDC_REDIRECT_URI`, `ORBIT_DASHBOARD_OIDC_SCOPES`, `ORBIT_DASHBOARD_OIDC_PROMPT`

Security controls:

- optional: `ORBIT_DASHBOARD_ALLOWED_ORIGINS`
- optional: `ORBIT_DASHBOARD_LOGIN_WINDOW_SECONDS`
- optional: `ORBIT_DASHBOARD_LOGIN_MAX_ATTEMPTS`
- optional: `ORBIT_DASHBOARD_LOGIN_LOCKOUT_SECONDS`

Legacy static mode (not recommended):

- `ORBIT_DASHBOARD_PROXY_AUTH_MODE=static`
- `ORBIT_DASHBOARD_SERVER_BEARER_TOKEN`

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
