from __future__ import annotations

from datetime import UTC, datetime, timedelta

import jwt
import pytest
from fastapi import HTTPException
from fastapi.security import HTTPAuthorizationCredentials

from orbit_api.auth import require_auth_context
from orbit_api.config import ApiConfig


def _token(secret: str, scope: str | None = None) -> str:
    now = datetime.now(UTC)
    payload = {
        "sub": "user_1",
        "iss": "issuer",
        "aud": "audience",
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(hours=1)).timestamp()),
    }
    if scope is not None:
        payload["scope"] = scope
    return str(jwt.encode(payload, secret, algorithm="HS256"))


def test_require_auth_context_success() -> None:
    config = ApiConfig(
        database_url="sqlite:///tmp.db",
        jwt_secret="secret",
        jwt_issuer="issuer",
        jwt_audience="audience",
    )
    token = _token("secret", scope="read write")
    credentials = HTTPAuthorizationCredentials(scheme="Bearer", credentials=token)
    context = require_auth_context(credentials=credentials, config=config)
    assert context.subject == "user_1"
    assert "write" in context.scopes


def test_require_auth_context_rejects_invalid_token() -> None:
    config = ApiConfig(
        database_url="sqlite:///tmp.db",
        jwt_secret="secret",
        jwt_issuer="issuer",
        jwt_audience="audience",
    )
    token = _token("different")
    credentials = HTTPAuthorizationCredentials(scheme="Bearer", credentials=token)
    with pytest.raises(HTTPException) as exc_info:
        require_auth_context(credentials=credentials, config=config)
    assert exc_info.value.status_code == 401


def test_require_auth_context_requires_scope() -> None:
    config = ApiConfig(
        database_url="sqlite:///tmp.db",
        jwt_secret="secret",
        jwt_issuer="issuer",
        jwt_audience="audience",
        jwt_required_scope="feedback",
    )
    token = _token("secret", scope="read write")
    credentials = HTTPAuthorizationCredentials(scheme="Bearer", credentials=token)
    with pytest.raises(HTTPException) as exc_info:
        require_auth_context(credentials=credentials, config=config)
    assert exc_info.value.status_code == 403
