"""JWT authentication helpers for Orbit API."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import jwt
from fastapi import HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials
from jwt import ExpiredSignatureError, InvalidTokenError

from orbit_api.config import ApiConfig


@dataclass(frozen=True)
class AuthContext:
    """Validated authentication context extracted from JWT or API key auth."""

    subject: str
    scopes: list[str]
    token: str
    claims: dict[str, Any]


def require_auth_context(
    credentials: HTTPAuthorizationCredentials | None,
    config: ApiConfig,
) -> AuthContext:
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing bearer token.",
        )
    token = credentials.credentials.strip()
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing bearer token.",
        )

    try:
        payload = jwt.decode(
            token,
            key=config.jwt_secret,
            algorithms=[config.jwt_algorithm],
            audience=config.jwt_audience,
            issuer=config.jwt_issuer,
            options={"require": ["exp", "iat", "sub"]},
        )
    except ExpiredSignatureError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="JWT token expired.",
        ) from exc
    except InvalidTokenError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Invalid JWT token: {exc!s}",
        ) from exc

    subject = str(payload.get("sub", "")).strip()
    if not subject:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="JWT token missing subject.",
        )

    scopes = _parse_scopes(payload)
    required_scope = config.jwt_required_scope
    if required_scope and required_scope not in scopes:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"JWT missing required scope: {required_scope}",
        )

    return AuthContext(
        subject=subject,
        scopes=scopes,
        token=token,
        claims=dict(payload),
    )


def _parse_scopes(payload: dict[str, Any]) -> list[str]:
    claim = payload.get("scopes")
    if isinstance(claim, list):
        return [str(item) for item in claim if str(item).strip()]
    if isinstance(claim, str):
        return [value for value in claim.split() if value]
    scope_claim = payload.get("scope")
    if isinstance(scope_claim, str):
        return [value for value in scope_claim.split() if value]
    return []
