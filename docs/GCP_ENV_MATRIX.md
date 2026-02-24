# Orbit GCP Env Matrix

This matrix defines the recommended environment contract for Cloud Run deployments of Orbit API.

## Secret Manager (required)

| Env var in runtime | Secret name (recommended) | Notes |
| --- | --- | --- |
| `MDE_DATABASE_URL` | `orbit-db-url` | Full SQLAlchemy DSN, typically Cloud SQL PostgreSQL. |
| `ORBIT_JWT_SECRET` | `orbit-jwt-secret` | JWT signing secret. Must be high entropy. |

## Required non-secret env vars

| Variable | Example | Purpose |
| --- | --- | --- |
| `ORBIT_ENV` | `production` | Enables production validation paths. |
| `ORBIT_AUTO_MIGRATE` | `true` | Runs Alembic migrations on startup. |
| `ORBIT_JWT_ALGORITHM` | `HS256` | JWT verification algorithm. |
| `ORBIT_JWT_ISSUER` | `orbit` | Required JWT issuer claim. |
| `ORBIT_JWT_AUDIENCE` | `orbit-api` | Required JWT audience claim. |
| `ORBIT_CORS_ALLOW_ORIGINS` | `https://app.orbit.dev` | Browser origin allowlist (comma-separated if multiple). |

## API runtime and quota defaults

| Variable | Default in deployment bundle | Notes |
| --- | --- | --- |
| `ORBIT_API_HOST` | `0.0.0.0` | Cloud Run bind address. |
| `ORBIT_API_PORT` | `8000` | Container internal port. |
| `ORBIT_RATE_LIMIT_EVENTS_PER_DAY` | `1000` | Per-account daily ingest quota. |
| `ORBIT_RATE_LIMIT_QUERIES_PER_DAY` | `5000` | Per-account daily query quota. |
| `ORBIT_RATE_LIMIT_PER_MINUTE` | `300/minute` | Request throttle (slowapi). |
| `ORBIT_MAX_INGEST_CONTENT_CHARS` | `20000` | Per-event content hard cap. |
| `ORBIT_MAX_QUERY_CHARS` | `2000` | Query string hard cap. |
| `ORBIT_MAX_BATCH_ITEMS` | `100` | Batch ingest/feedback hard cap. |

## Observability

| Variable | Recommended value | Purpose |
| --- | --- | --- |
| `ORBIT_OTEL_SERVICE_NAME` | `orbit-api` | OTEL service identity. |
| `ORBIT_OTEL_EXPORTER_ENDPOINT` | `https://otel-collector.<domain>/v1/traces` | Optional OTLP HTTP export endpoint. |

## Cloud Run infrastructure settings (not app env vars)

| Setting | Recommended baseline |
| --- | --- |
| CPU | `1` |
| Memory | `1Gi` |
| Timeout | `300s` |
| Min instances | `0` |
| Max instances | `10` |
| Auth | `allow-unauthenticated` if app-level JWT is enforced |
