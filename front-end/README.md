# Orbit Frontend

Next.js frontend for Orbit marketing pages, docs, and dashboard key management UI.

## Local run

```bash
cp .env.example .env.local
npm install
npm run dev
```

Open:

- `http://localhost:3000/` for site/docs
- `http://localhost:3000/dashboard` for API key management

## Dashboard auth model (production-safe)

Browser never stores Orbit API bearer credentials.  
All dashboard requests hit Next.js server routes under `/api/dashboard/*`, and the server forwards to Orbit API with:

- `ORBIT_DASHBOARD_SERVER_BEARER_TOKEN`

Dashboard route access is protected by a server-issued HTTP-only session cookie:

- `ORBIT_DASHBOARD_AUTH_MODE=password`
- `ORBIT_DASHBOARD_AUTH_PASSWORD`
- `ORBIT_DASHBOARD_SESSION_SECRET`
- optional `ORBIT_DASHBOARD_SESSION_TTL_SECONDS`

Optional proxy target override:

- `ORBIT_DASHBOARD_PROXY_BASE_URL`

Public base URL (for UI/docs display):

- `NEXT_PUBLIC_ORBIT_API_BASE_URL`

## Vercel setup

In Vercel Project Settings -> Environment Variables, add:

- `NEXT_PUBLIC_ORBIT_API_BASE_URL`
- `ORBIT_DASHBOARD_PROXY_BASE_URL` (optional)
- `ORBIT_DASHBOARD_SERVER_BEARER_TOKEN`
- `ORBIT_DASHBOARD_AUTH_MODE=password`
- `ORBIT_DASHBOARD_AUTH_PASSWORD`
- `ORBIT_DASHBOARD_SESSION_SECRET`
- `ORBIT_DASHBOARD_SESSION_TTL_SECONDS` (optional)

If frontend and Orbit API are on different domains, set backend CORS:

```bash
ORBIT_CORS_ALLOW_ORIGINS=https://your-app.vercel.app
```
