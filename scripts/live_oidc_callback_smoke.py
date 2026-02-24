"""Live smoke test for dashboard OIDC start -> callback -> session flow.

Prerequisites:
1) Next.js frontend running with OIDC mode enabled.
2) Reachable OIDC provider (for local test, run examples/mock_oidc_provider/app.py).
"""

from __future__ import annotations

import os
from urllib.parse import urljoin

import httpx


def main() -> int:
    base_url = os.getenv("ORBIT_FRONTEND_BASE_URL", "http://127.0.0.1:3000").strip()
    if not base_url:
        print("ERROR: ORBIT_FRONTEND_BASE_URL is empty")
        return 1
    start_url = urljoin(base_url.rstrip("/") + "/", "api/dashboard/auth/oidc/start")
    session_url = urljoin(base_url.rstrip("/") + "/", "api/dashboard/auth/session")

    with httpx.Client(follow_redirects=False, timeout=20.0) as client:
        start = client.get(start_url)
        if start.status_code not in (302, 303, 307, 308):
            print(f"ERROR: start route returned {start.status_code}: {start.text[:300]}")
            return 1
        next_url = _resolve_location(start)
        if not next_url:
            print("ERROR: start route did not return redirect location")
            return 1

        print(f"OIDC start redirect: {next_url}")
        redirect_hops = 0
        current_response = start
        while redirect_hops < 8 and next_url:
            redirect_hops += 1
            current_response = client.get(next_url)
            if current_response.status_code in (302, 303, 307, 308):
                next_url = _resolve_location(current_response)
                if next_url:
                    print(f"redirect[{redirect_hops}] -> {next_url}")
                continue
            break

        session = client.get(session_url)
        if session.status_code != 200:
            print(f"ERROR: session route returned {session.status_code}: {session.text[:300]}")
            return 1
        payload = session.json()
        if not payload.get("authenticated"):
            print(f"ERROR: session not authenticated: {payload}")
            return 1
        if str(payload.get("mode")) != "oidc":
            print(f"ERROR: expected mode=oidc, got: {payload}")
            return 1

        print("PASS: OIDC callback flow authenticated dashboard session.")
        print(f"Session subject: {payload.get('subject')}")
        return 0


def _resolve_location(response: httpx.Response) -> str | None:
    location = response.headers.get("location", "").strip()
    if not location:
        return None
    return str(response.request.url.join(location))


if __name__ == "__main__":
    raise SystemExit(main())
