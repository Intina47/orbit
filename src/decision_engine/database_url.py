from __future__ import annotations


def normalize_database_url(value: str | None) -> str | None:
    """Normalize database URLs for SQLAlchemy + psycopg usage."""
    if value is None:
        return None
    stripped = value.strip()
    if not stripped:
        return None

    scheme, separator, rest = stripped.partition("://")
    if separator != "://":
        return stripped

    normalized_scheme = scheme.lower()
    if normalized_scheme in {"postgres", "postgresql"}:
        return f"postgresql+psycopg://{rest}"
    return stripped
