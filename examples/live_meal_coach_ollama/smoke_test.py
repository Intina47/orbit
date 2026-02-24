from __future__ import annotations

import argparse

import httpx


def main() -> None:
    parser = argparse.ArgumentParser(description="Smoke test meal coach chat endpoint.")
    parser.add_argument("--base-url", default="http://localhost:8020")
    parser.add_argument("--user-id", default="ava")
    parser.add_argument("--mode", choices=["baseline", "orbit"], default="orbit")
    parser.add_argument(
        "--message",
        default="Give me two high-protein dinner ideas under 25 minutes.",
    )
    args = parser.parse_args()

    response = httpx.post(
        f"{args.base_url}/chat",
        json={
            "user_id": args.user_id,
            "message": args.message,
            "mode": args.mode,
        },
        timeout=60.0,
    )
    response.raise_for_status()
    print(response.json())


if __name__ == "__main__":
    main()
