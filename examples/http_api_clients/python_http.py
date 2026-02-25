import os
import sys
from urllib.parse import quote

import requests


def required_env(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        raise RuntimeError(f"Missing environment variable: {name}")
    return value


def orbit_request(base_url: str, api_key: str, method: str, path: str, payload=None):
    response = requests.request(
        method=method,
        url=f"{base_url.rstrip('/')}{path}",
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        },
        json=payload,
        timeout=15,
    )
    if response.status_code >= 400:
        try:
            detail = response.json().get("detail")
        except ValueError:
            detail = response.text
        raise RuntimeError(detail or f"HTTP {response.status_code}")
    return response.json() if response.text else {}


def main():
    base_url = required_env("ORBIT_API_BASE_URL")
    api_key = required_env("ORBIT_API_KEY")
    entity_id = os.getenv("ORBIT_ENTITY_ID", "alice")

    question = "I keep forgetting Python list comprehensions."
    ingest = orbit_request(
        base_url,
        api_key,
        "POST",
        "/v1/ingest",
        {
            "content": question,
            "event_type": "user_question",
            "entity_id": entity_id,
        },
    )
    query = quote(f"What should I know about {entity_id}?", safe="")
    retrieve = orbit_request(
        base_url,
        api_key,
        "GET",
        f"/v1/retrieve?query={query}&entity_id={quote(entity_id, safe='')}&limit=5",
    )

    print("ingest.memory_id =", ingest.get("memory_id"))
    memories = retrieve.get("memories", [])
    print("retrieved =", len(memories), "memories")
    for memory in memories:
        print("-", memory.get("content", ""))


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:  # pylint: disable=broad-except
        print(str(exc))
        sys.exit(1)
