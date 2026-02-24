# Deployment

## Stack

- Orbit API (`src/orbit_api/`)
- PostgreSQL (default runtime database)
- Prometheus scraping `/v1/metrics`
- OpenTelemetry collector receiving OTLP traces

## Local Deployment

```bash
docker compose up --build
```

## Google Cloud Deployment

- Cloud Build pipeline config: `cloudbuild.yaml`
- Manual/CI deploy script: `scripts/deploy_gcp_cloud_run.sh`
- Runbook: `docs/DEPLOY_GCP_CLOUD_RUN.md`
- Environment matrix: `docs/GCP_ENV_MATRIX.md`

## Migration Path

Alembic migrations are under `migrations/`.

Run manually:

```bash
python -m alembic upgrade head
```

Or enable automatic startup migrations:

```bash
ORBIT_AUTO_MIGRATE=true
```

## Required Environment Variables

- `MDE_DATABASE_URL` (defaults to PostgreSQL DSN)
- `ORBIT_JWT_SECRET`
- `ORBIT_JWT_ISSUER`
- `ORBIT_JWT_AUDIENCE`

## Observability

- Metrics endpoint: `GET /v1/metrics`
- Prometheus UI: `http://localhost:9090`
- OTel exporter endpoint: `ORBIT_OTEL_EXPORTER_ENDPOINT`
- Alert rules: `deploy/prometheus/alerts-orbit.yml`
  - `OrbitApiSpike401403429`
  - `OrbitApiSpike5xx`
  - `OrbitDashboardAuthFailures`
  - `OrbitDashboardKeyRotationFailures`
- Dashboard login failures are emitted as structured frontend proxy logs (`dashboard_login_failure`, `dashboard_login_locked`) for log-based alerting.
