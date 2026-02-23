# Orbit Deployment: Render (API) + Vercel (Frontend)

This runbook deploys Orbit API on Render using Docker + managed PostgreSQL, and a frontend on Vercel.

## 1) Render API Deployment

### Option A: Blueprint (recommended)

1. Push repository to GitHub.
2. In Render, create a new Blueprint and select this repository.
3. Render will detect `render.yaml` and create:
   - web service: `orbit-api`
   - postgres database: `orbit-postgres`
4. Review env vars and deploy.

### Option B: Manual service setup

1. Create a new **Web Service** from this repo.
2. Runtime: **Docker**.
3. Dockerfile path: `./Dockerfile`.
4. Health check path: `/v1/health`.
5. Create a Render PostgreSQL instance and set:
   - `MDE_DATABASE_URL` = database connection string
6. Set required API env vars:
   - `ORBIT_ENV=production`
   - `ORBIT_AUTO_MIGRATE=true`
   - `ORBIT_JWT_SECRET=<long-random-secret>`
   - `ORBIT_JWT_ALGORITHM=HS256`
   - `ORBIT_JWT_ISSUER=orbit`
   - `ORBIT_JWT_AUDIENCE=orbit-api`
   - `ORBIT_CORS_ALLOW_ORIGINS=https://<your-vercel-domain>`

## 2) Render Runtime Notes

- Container startup runs migrations when `ORBIT_AUTO_MIGRATE=true`.
- API port auto-binds from Render `PORT` env var.
- Render DB URLs like `postgres://...` and `postgresql://...` are normalized to `postgresql+psycopg://...`.

## 3) Vercel Frontend Integration

Frontend should call Orbit API from browser, but JWT signing must happen server-side.

### Vercel env vars

- `ORBIT_API_URL=https://<your-render-service>.onrender.com`
- `ORBIT_JWT_SECRET=<same secret as Render API>`
- `ORBIT_JWT_ISSUER=orbit`
- `ORBIT_JWT_AUDIENCE=orbit-api`

Do not expose JWT secret via `NEXT_PUBLIC_*`.

### Example Next.js token route (`app/api/orbit-token/route.ts`)

```ts
import { SignJWT } from "jose";

function required(name: string): string {
  const value = process.env[name];
  if (!value) throw new Error(`${name} missing`);
  return value;
}

export async function POST(req: Request) {
  const { userId } = await req.json();
  if (!userId || typeof userId !== "string") {
    return new Response(JSON.stringify({ error: "userId required" }), { status: 400 });
  }

  const secret = new TextEncoder().encode(required("ORBIT_JWT_SECRET"));
  const issuer = required("ORBIT_JWT_ISSUER");
  const audience = required("ORBIT_JWT_AUDIENCE");
  const now = Math.floor(Date.now() / 1000);

  const token = await new SignJWT({ scopes: ["read", "write", "feedback"] })
    .setProtectedHeader({ alg: "HS256" })
    .setSubject(userId)
    .setIssuedAt(now)
    .setExpirationTime(now + 60 * 30)
    .setIssuer(issuer)
    .setAudience(audience)
    .sign(secret);

  return new Response(JSON.stringify({ token }), {
    headers: { "Content-Type": "application/json" },
  });
}
```

Install dependency in frontend:

```bash
npm install jose
```

## 4) End-to-End Smoke Test

1. Get JWT from Vercel token endpoint.
2. Test ingest:

```bash
curl -X POST "https://<render-url>/v1/ingest" \
  -H "Authorization: Bearer <jwt>" \
  -H "Idempotency-Key: smoke-ingest-1" \
  -H "Content-Type: application/json" \
  -d '{"content":"Alice struggles with loops","event_type":"user_question","entity_id":"alice"}'
```

3. Replay same request with same idempotency key and verify:
   - status remains success
   - `X-Idempotency-Replayed: true`
4. Test retrieve:

```bash
curl "https://<render-url>/v1/retrieve?query=What%20should%20I%20know%20about%20alice%3F&entity_id=alice&limit=5" \
  -H "Authorization: Bearer <jwt>"
```

## 5) Recommended Production Additions

- Set `ORBIT_JWT_REQUIRED_SCOPE` for stricter auth policy.
- Rotate `ORBIT_JWT_SECRET` on a regular schedule.
- Enable `ORBIT_OTEL_EXPORTER_ENDPOINT` to your telemetry backend.
- Add uptime + 5xx + latency alerts in Render.
