# Dashboard OIDC Setup

This guide configures Orbit dashboard auth with OIDC and validates callback flow.

## Required shared env

```bash
ORBIT_DASHBOARD_AUTH_MODE=oidc
ORBIT_DASHBOARD_PROXY_AUTH_MODE=exchange
ORBIT_DASHBOARD_ORBIT_JWT_SECRET=<same-secret-used-by-orbit-api-jwt-verifier>
ORBIT_DASHBOARD_SESSION_SECRET=<long-random-secret>
```

Optional tenant mapping:

```bash
ORBIT_DASHBOARD_OIDC_TENANT_CLAIMS=tid,org_id,organization
```

## Google

```bash
ORBIT_DASHBOARD_OIDC_ISSUER_URL=https://accounts.google.com
ORBIT_DASHBOARD_OIDC_CLIENT_ID=<google-client-id>
ORBIT_DASHBOARD_OIDC_CLIENT_SECRET=<google-client-secret>
ORBIT_DASHBOARD_OIDC_SCOPES="openid profile email"
ORBIT_DASHBOARD_OIDC_REDIRECT_URI=https://<dashboard-domain>/api/dashboard/auth/oidc/callback
```

## Auth0

```bash
ORBIT_DASHBOARD_OIDC_ISSUER_URL=https://<tenant>.us.auth0.com
ORBIT_DASHBOARD_OIDC_CLIENT_ID=<auth0-client-id>
ORBIT_DASHBOARD_OIDC_CLIENT_SECRET=<auth0-client-secret>
ORBIT_DASHBOARD_OIDC_SCOPES="openid profile email"
ORBIT_DASHBOARD_OIDC_REDIRECT_URI=https://<dashboard-domain>/api/dashboard/auth/oidc/callback
```

## Clerk

```bash
ORBIT_DASHBOARD_OIDC_ISSUER_URL=https://<your-clerk-domain>
ORBIT_DASHBOARD_OIDC_CLIENT_ID=<clerk-client-id>
ORBIT_DASHBOARD_OIDC_CLIENT_SECRET=<clerk-client-secret>
ORBIT_DASHBOARD_OIDC_SCOPES="openid profile email"
ORBIT_DASHBOARD_OIDC_REDIRECT_URI=https://<dashboard-domain>/api/dashboard/auth/oidc/callback
```

## Live callback smoke test (local)

1. Start mock OIDC provider:

```bash
python -m uvicorn examples.mock_oidc_provider.app:app --host 127.0.0.1 --port 9100
```

2. Set frontend OIDC env to mock provider and run frontend app.

3. Run smoke test:

```bash
python scripts/live_oidc_callback_smoke.py
```

Expected output:

- `PASS: OIDC callback flow authenticated dashboard session.`
