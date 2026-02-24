#!/usr/bin/env bash
set -euo pipefail

required_env() {
  local name="$1"
  if [[ -z "${!name:-}" ]]; then
    echo "Missing required environment variable: ${name}" >&2
    exit 1
  fi
}

required_env PROJECT_ID
required_env REGION
required_env SERVICE_NAME
required_env IMAGE_URI

ALLOW_UNAUTHENTICATED="${ALLOW_UNAUTHENTICATED:-true}"
MIN_INSTANCES="${MIN_INSTANCES:-0}"
MAX_INSTANCES="${MAX_INSTANCES:-10}"
CPU="${CPU:-1}"
MEMORY="${MEMORY:-1Gi}"
TIMEOUT_SECONDS="${TIMEOUT_SECONDS:-300}"
CLOUDSQL_INSTANCE="${CLOUDSQL_INSTANCE:-}"

DB_URL_SECRET_NAME="${DB_URL_SECRET_NAME:-orbit-db-url}"
DB_URL_SECRET_VERSION="${DB_URL_SECRET_VERSION:-latest}"
JWT_SECRET_NAME="${JWT_SECRET_NAME:-orbit-jwt-secret}"
JWT_SECRET_VERSION="${JWT_SECRET_VERSION:-latest}"

ORBIT_ENV="${ORBIT_ENV:-production}"
ORBIT_JWT_ISSUER="${ORBIT_JWT_ISSUER:-orbit}"
ORBIT_JWT_AUDIENCE="${ORBIT_JWT_AUDIENCE:-orbit-api}"
ORBIT_JWT_ALGORITHM="${ORBIT_JWT_ALGORITHM:-HS256}"
ORBIT_RATE_LIMIT_EVENTS_PER_DAY="${ORBIT_RATE_LIMIT_EVENTS_PER_DAY:-1000}"
ORBIT_RATE_LIMIT_QUERIES_PER_DAY="${ORBIT_RATE_LIMIT_QUERIES_PER_DAY:-5000}"
ORBIT_RATE_LIMIT_PER_MINUTE="${ORBIT_RATE_LIMIT_PER_MINUTE:-300/minute}"
ORBIT_MAX_INGEST_CONTENT_CHARS="${ORBIT_MAX_INGEST_CONTENT_CHARS:-20000}"
ORBIT_MAX_QUERY_CHARS="${ORBIT_MAX_QUERY_CHARS:-2000}"
ORBIT_MAX_BATCH_ITEMS="${ORBIT_MAX_BATCH_ITEMS:-100}"
ORBIT_CORS_ALLOW_ORIGINS="${ORBIT_CORS_ALLOW_ORIGINS:-https://your-frontend.vercel.app}"
ORBIT_OTEL_SERVICE_NAME="${ORBIT_OTEL_SERVICE_NAME:-orbit-api}"
ORBIT_OTEL_EXPORTER_ENDPOINT="${ORBIT_OTEL_EXPORTER_ENDPOINT:-}"

env_vars=(
  "ORBIT_API_HOST=0.0.0.0"
  "ORBIT_API_PORT=8000"
  "ORBIT_AUTO_MIGRATE=true"
  "ORBIT_ENV=${ORBIT_ENV}"
  "ORBIT_JWT_ISSUER=${ORBIT_JWT_ISSUER}"
  "ORBIT_JWT_AUDIENCE=${ORBIT_JWT_AUDIENCE}"
  "ORBIT_JWT_ALGORITHM=${ORBIT_JWT_ALGORITHM}"
  "ORBIT_RATE_LIMIT_EVENTS_PER_DAY=${ORBIT_RATE_LIMIT_EVENTS_PER_DAY}"
  "ORBIT_RATE_LIMIT_QUERIES_PER_DAY=${ORBIT_RATE_LIMIT_QUERIES_PER_DAY}"
  "ORBIT_RATE_LIMIT_PER_MINUTE=${ORBIT_RATE_LIMIT_PER_MINUTE}"
  "ORBIT_MAX_INGEST_CONTENT_CHARS=${ORBIT_MAX_INGEST_CONTENT_CHARS}"
  "ORBIT_MAX_QUERY_CHARS=${ORBIT_MAX_QUERY_CHARS}"
  "ORBIT_MAX_BATCH_ITEMS=${ORBIT_MAX_BATCH_ITEMS}"
  "ORBIT_CORS_ALLOW_ORIGINS=${ORBIT_CORS_ALLOW_ORIGINS}"
  "ORBIT_OTEL_SERVICE_NAME=${ORBIT_OTEL_SERVICE_NAME}"
)

if [[ -n "${ORBIT_OTEL_EXPORTER_ENDPOINT}" ]]; then
  env_vars+=("ORBIT_OTEL_EXPORTER_ENDPOINT=${ORBIT_OTEL_EXPORTER_ENDPOINT}")
fi

gcloud_args=(
  run
  deploy
  "${SERVICE_NAME}"
  --project
  "${PROJECT_ID}"
  --image
  "${IMAGE_URI}"
  --region
  "${REGION}"
  --platform
  managed
  --port
  "8000"
  --cpu
  "${CPU}"
  --memory
  "${MEMORY}"
  --min-instances
  "${MIN_INSTANCES}"
  --max-instances
  "${MAX_INSTANCES}"
  --timeout
  "${TIMEOUT_SECONDS}s"
  --set-env-vars
  "$(IFS=,; echo "${env_vars[*]}")"
  --set-secrets
  "MDE_DATABASE_URL=${DB_URL_SECRET_NAME}:${DB_URL_SECRET_VERSION},ORBIT_JWT_SECRET=${JWT_SECRET_NAME}:${JWT_SECRET_VERSION}"
)

if [[ "${ALLOW_UNAUTHENTICATED}" == "true" ]]; then
  gcloud_args+=(--allow-unauthenticated)
else
  gcloud_args+=(--no-allow-unauthenticated)
fi

if [[ -n "${CLOUDSQL_INSTANCE}" ]]; then
  gcloud_args+=(--add-cloudsql-instances "${CLOUDSQL_INSTANCE}")
fi

echo "Deploying ${SERVICE_NAME} to Cloud Run (${REGION})..."
gcloud "${gcloud_args[@]}"

service_url="$(
  gcloud run services describe "${SERVICE_NAME}" \
    --project "${PROJECT_ID}" \
    --region "${REGION}" \
    --format="value(status.url)"
)"

echo "Cloud Run service URL: ${service_url}"
