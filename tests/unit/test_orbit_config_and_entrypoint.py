from __future__ import annotations

import pytest

from orbit.config import Config
from orbit_api.__main__ import main
from orbit_api.config import ApiConfig


def test_orbit_config_from_env(monkeypatch) -> None:
    monkeypatch.setenv("ORBIT_API_KEY", "orbit_pk_aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa")
    monkeypatch.setenv("ORBIT_BASE_URL", "https://api.local")
    monkeypatch.setenv("ORBIT_TIMEOUT", "15")
    monkeypatch.setenv("ORBIT_MAX_RETRIES", "2")
    monkeypatch.setenv("ORBIT_RETRY_BACKOFF_FACTOR", "1.5")
    monkeypatch.setenv("ORBIT_LOG_LEVEL", "debug")
    monkeypatch.setenv("ORBIT_ENABLE_TELEMETRY", "false")

    config = Config.from_env()
    assert config.api_key == "orbit_pk_aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
    assert config.base_url == "https://api.local"
    assert config.timeout_seconds == 15.0
    assert config.max_retries == 2
    assert config.retry_backoff_factor == 1.5
    assert config.log_level == "debug"
    assert config.enable_telemetry is False


def test_api_config_from_env(monkeypatch) -> None:
    monkeypatch.setenv("MDE_SQLITE_PATH", "tmp.db")
    monkeypatch.setenv("MDE_DATABASE_URL", "sqlite:///tmp.db")
    monkeypatch.setenv("ORBIT_RATE_LIMIT_EVENTS_PER_DAY", "50")
    monkeypatch.setenv("ORBIT_RATE_LIMIT_QUERIES_PER_DAY", "250")
    monkeypatch.setenv("ORBIT_JWT_SECRET", "secret")
    monkeypatch.setenv("ORBIT_JWT_ISSUER", "issuer")
    monkeypatch.setenv("ORBIT_JWT_AUDIENCE", "audience")
    monkeypatch.setenv("ORBIT_MAX_INGEST_CONTENT_CHARS", "1234")
    monkeypatch.setenv("ORBIT_MAX_QUERY_CHARS", "321")
    monkeypatch.setenv("ORBIT_MAX_BATCH_ITEMS", "55")
    monkeypatch.setenv(
        "ORBIT_CORS_ALLOW_ORIGINS",
        "https://orbit-web.vercel.app,https://orbit.example.com",
    )
    monkeypatch.setenv("ORBIT_ENV", "production")

    config = ApiConfig.from_env()
    assert config.database_url == "sqlite:///tmp.db"
    assert config.sqlite_fallback_path == "tmp.db"
    assert config.free_events_per_day == 50
    assert config.free_queries_per_day == 250
    assert config.free_events_per_month == 1500
    assert config.free_queries_per_month == 7500
    assert config.jwt_secret == "secret"
    assert config.jwt_issuer == "issuer"
    assert config.jwt_audience == "audience"
    assert config.max_ingest_content_chars == 1234
    assert config.max_query_chars == 321
    assert config.max_batch_items == 55
    assert config.cors_allow_origins == [
        "https://orbit-web.vercel.app",
        "https://orbit.example.com",
    ]
    assert config.environment == "production"


def test_api_config_normalizes_render_database_url() -> None:
    config = ApiConfig(
        database_url="postgres://user:pass@db.render.com:5432/orbit",
        jwt_secret="secret",
    )
    assert (
        config.database_url
        == "postgresql+psycopg://user:pass@db.render.com:5432/orbit"
    )


def test_api_config_rejects_default_jwt_secret_in_production() -> None:
    with pytest.raises(ValueError):
        ApiConfig(environment="production")


def test_api_config_rejects_jwt_none_algorithm() -> None:
    with pytest.raises(ValueError):
        ApiConfig(jwt_algorithm="none")


def test_api_main_calls_uvicorn(monkeypatch) -> None:
    captured = {}

    def fake_run(app, host: str, port: int) -> None:
        captured["app"] = app
        captured["host"] = host
        captured["port"] = port

    monkeypatch.setenv("ORBIT_API_HOST", "127.0.0.1")
    monkeypatch.setenv("ORBIT_API_PORT", "9000")
    monkeypatch.setenv("ORBIT_AUTO_MIGRATE", "false")
    monkeypatch.setenv("MDE_DATABASE_URL", "sqlite:///tmp-main.db")
    monkeypatch.setattr("orbit_api.__main__.uvicorn.run", fake_run)

    main()

    assert captured["host"] == "127.0.0.1"
    assert captured["port"] == 9000
