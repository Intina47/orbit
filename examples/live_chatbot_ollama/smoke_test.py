from __future__ import annotations

import argparse

import httpx


def main() -> None:
    parser = argparse.ArgumentParser(description="Smoke test live chatbot endpoint.")
    parser.add_argument("--base-url", default="http://localhost:8010")
    parser.add_argument("--user-id", default="alice")
    parser.add_argument("--message", default="What is a Python class?")
    args = parser.parse_args()

    response = httpx.post(
        f"{args.base_url}/chat",
        json={"user_id": args.user_id, "message": args.message},
        timeout=30.0,
    )
    response.raise_for_status()
    payload = response.json()
    print(payload)


if __name__ == "__main__":
    main()
