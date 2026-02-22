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

