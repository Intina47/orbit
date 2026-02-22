"""CLI entrypoint to run Orbit API with Uvicorn."""

from __future__ import annotations

import os

import uvicorn
from alembic import command
from alembic.config import Config as AlembicConfig

from orbit_api.app import create_app


def main() -> None:
    _run_migrations_if_enabled()
    app = create_app()
    uvicorn.run(
        app,
        host=os.getenv("ORBIT_API_HOST", "0.0.0.0"),
        port=int(os.getenv("ORBIT_API_PORT", "8000")),
    )


def _run_migrations_if_enabled() -> None:
    enabled = os.getenv("ORBIT_AUTO_MIGRATE", "true").strip().lower()
    if enabled not in {"1", "true", "yes", "on"}:
        return
    alembic_cfg = AlembicConfig("alembic.ini")
    database_url = os.getenv("MDE_DATABASE_URL")
    if database_url:
        alembic_cfg.set_main_option("sqlalchemy.url", database_url)
    command.upgrade(alembic_cfg, "head")


if __name__ == "__main__":
    main()
