# Deployment

## Stack

- Orbit API (`src/orbit_api/`)
- PostgreSQL (default runtime database)
- Prometheus scraping `/v1/metrics`
- Alertmanager routing alerts to Slack/email receivers
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
- Alertmanager UI/API: `http://localhost:9093`
- OTel exporter endpoint: `ORBIT_OTEL_EXPORTER_ENDPOINT`
- Alert rules: `deploy/prometheus/alerts-orbit.yml`
  - `OrbitApiSpike401403429`
  - `OrbitApiSpike5xx`
  - `OrbitDashboardAuthFailures`
  - `OrbitDashboardKeyRotationFailures`
- Dashboard login failures are emitted as structured frontend proxy logs (`dashboard_login_failure`, `dashboard_login_locked`) for log-based alerting.

### Alertmanager receiver routes

`deploy/alertmanager/alertmanager.yml` routes alerts by severity:

- `severity="critical"` -> `critical-slack-email`
- `severity="warning"` -> `warning-slack-email`
- fallback -> `default-webhook`

Configure these env vars for Slack/email delivery:

- `ALERTMANAGER_SLACK_WEBHOOK_URL`
- `ALERTMANAGER_SLACK_CHANNEL`
- `ALERTMANAGER_EMAIL_TO`
- `ALERTMANAGER_EMAIL_FROM`
- `ALERTMANAGER_EMAIL_SMARTHOST`
- `ALERTMANAGER_EMAIL_USERNAME`
- `ALERTMANAGER_EMAIL_PASSWORD`
