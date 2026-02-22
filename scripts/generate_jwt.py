from __future__ import annotations

import argparse
from datetime import UTC, datetime, timedelta

import jwt


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate Orbit API JWT token.")
    parser.add_argument("--secret", required=True)
    parser.add_argument("--issuer", default="orbit")
    parser.add_argument("--audience", default="orbit-api")
    parser.add_argument("--subject", default="developer")
    parser.add_argument("--scopes", nargs="*", default=["read", "write", "feedback"])
    parser.add_argument("--ttl-minutes", type=int, default=60)
    args = parser.parse_args()

    now = datetime.now(UTC)
    payload = {
        "sub": args.subject,
        "iss": args.issuer,
        "aud": args.audience,
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(minutes=args.ttl_minutes)).timestamp()),
        "scopes": args.scopes,
    }
    token = jwt.encode(payload, args.secret, algorithm="HS256")
    print(token)


if __name__ == "__main__":
    main()

