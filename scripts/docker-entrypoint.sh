#!/usr/bin/env sh
set -eu

AUTO_MIGRATE="$(printf '%s' "${ORBIT_AUTO_MIGRATE:-true}" | tr '[:upper:]' '[:lower:]')"
if [ "$AUTO_MIGRATE" = "1" ] || [ "$AUTO_MIGRATE" = "true" ] || [ "$AUTO_MIGRATE" = "yes" ] || [ "$AUTO_MIGRATE" = "on" ]; then
  alembic upgrade head
fi

PORT_VALUE="${PORT:-${ORBIT_API_PORT:-8000}}"
exec python -m uvicorn orbit_api.app:create_app --factory --host 0.0.0.0 --port "$PORT_VALUE"
