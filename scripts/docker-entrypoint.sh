#!/usr/bin/env sh
set -eu

alembic upgrade head

exec python -m uvicorn orbit_api.app:create_app --factory --host 0.0.0.0 --port "${ORBIT_API_PORT:-8000}"
