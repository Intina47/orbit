"""Local mock OIDC provider for Orbit dashboard callback smoke tests."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any
from urllib.parse import parse_qs
from uuid import uuid4

import jwt
from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.responses import RedirectResponse

app = FastAPI(title="Orbit Mock OIDC Provider", version="1.0.0")

_CODES: dict[str, dict[str, str]] = {}
_ACCESS_TOKENS: dict[str, dict[str, str]] = {}

MOCK_SUBJECT = "oidc-user-123"
MOCK_EMAIL = "dev@example.com"
MOCK_NAME = "Orbit Dev"
MOCK_TENANT = "tenant_demo"
MOCK_SECRET = "mock-oidc-secret"


@app.get("/.well-known/openid-configuration")
def discovery(request: Request) -> dict[str, str]:
    base = str(request.base_url).rstrip("/")
    return {
        "issuer": base,
        "authorization_endpoint": f"{base}/authorize",
        "token_endpoint": f"{base}/token",
        "userinfo_endpoint": f"{base}/userinfo",
    }


@app.get("/authorize")
def authorize(
    redirect_uri: str = Query(...),
    state: str = Query(...),
    client_id: str = Query(...),
    code_challenge: str = Query(...),
    nonce: str = Query(...),
) -> RedirectResponse:
    if not redirect_uri.strip():
        raise HTTPException(status_code=400, detail="redirect_uri is required")
    code = f"mock-code-{uuid4().hex[:20]}"
    _CODES[code] = {
        "state": state,
        "client_id": client_id,
        "code_challenge": code_challenge,
        "nonce": nonce,
    }
    separator = "&" if "?" in redirect_uri else "?"
    return RedirectResponse(url=f"{redirect_uri}{separator}code={code}&state={state}", status_code=307)


@app.post("/token")
async def token(request: Request) -> dict[str, Any]:
    form = parse_qs((await request.body()).decode("utf-8"), keep_blank_values=True)
    grant_type = _form_value(form, "grant_type")
    code = _form_value(form, "code")
    client_id = _form_value(form, "client_id")
    client_secret = _form_value(form, "client_secret")
    redirect_uri = _form_value(form, "redirect_uri")
    code_verifier = _form_value(form, "code_verifier")
    if grant_type != "authorization_code":
        raise HTTPException(status_code=400, detail="Unsupported grant_type")
    if not client_secret.strip():
        raise HTTPException(status_code=401, detail="Missing client_secret")
    if not redirect_uri.strip() or not code_verifier.strip():
        raise HTTPException(status_code=400, detail="Missing redirect_uri/code_verifier")
    code_state = _CODES.pop(code, None)
    if code_state is None or code_state["client_id"] != client_id:
        raise HTTPException(status_code=400, detail="Invalid or expired code")

    now = datetime.now(UTC)
    id_token = jwt.encode(
        {
            "sub": MOCK_SUBJECT,
            "iss": "http://127.0.0.1:9100",
            "aud": client_id,
            "iat": int(now.timestamp()),
            "exp": int((now + timedelta(minutes=10)).timestamp()),
            "nonce": code_state["nonce"],
            "email": MOCK_EMAIL,
            "name": MOCK_NAME,
            "tid": MOCK_TENANT,
        },
        MOCK_SECRET,
        algorithm="HS256",
    )
    access_token = f"mock-access-{uuid4().hex}"
    _ACCESS_TOKENS[access_token] = {
        "sub": MOCK_SUBJECT,
        "email": MOCK_EMAIL,
        "name": MOCK_NAME,
        "tid": MOCK_TENANT,
    }
    return {
        "token_type": "Bearer",
        "access_token": access_token,
        "expires_in": 600,
        "id_token": id_token,
    }


@app.get("/userinfo")
def userinfo(request: Request) -> dict[str, str]:
    auth_header = request.headers.get("authorization", "")
    if not auth_header.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail="Missing bearer token")
    token = auth_header.split(" ", 1)[1].strip()
    claims = _ACCESS_TOKENS.get(token)
    if claims is None:
        raise HTTPException(status_code=401, detail="Invalid bearer token")
    return claims


def _form_value(form: dict[str, list[str]], key: str) -> str:
    values = form.get(key)
    if not values:
        raise HTTPException(status_code=400, detail=f"Missing form field: {key}")
    return values[0].strip()
