from __future__ import annotations

import argparse
from typing import Any

import httpx


def post_json(client: httpx.Client, url: str, payload: dict[str, Any]) -> dict[str, Any]:
    response = client.post(url, json=payload, timeout=60.0)
    response.raise_for_status()
    return dict(response.json())


def run_sequence(base_url: str, user_id: str, mode: str, messages: list[str]) -> None:
    print(f"\n=== {mode.upper()} | user={user_id} ===")

    with httpx.Client() as client:
        post_json(client, f"{base_url}/reset", {"user_id": user_id})

        if mode == "orbit":
            seed_payload = {
                "user_id": user_id,
                "goals": ["Eat high-protein dinners", "Lose weight steadily"],
                "allergies": ["Peanuts"],
                "dislikes": ["Mushrooms"],
                "preferred_cuisines": ["Mediterranean", "Mexican"],
                "budget": "medium",
                "cooking_level": "beginner",
                "extra_notes": "Weeknight meals should be under 25 minutes.",
            }
            seed_result = post_json(client, f"{base_url}/seed-profile", seed_payload)
            print(f"Seeded profile events: {seed_result.get('events_written', 0)}")

        for idx, message in enumerate(messages, start=1):
            payload = {"user_id": user_id, "message": message, "mode": mode}
            result = post_json(client, f"{base_url}/chat", payload)

            preview = result.get("context_preview", [])
            memory_ids = result.get("memory_ids", [])
            answer = str(result.get("response", "")).replace("\n", " ")

            print(f"\nTurn {idx}: {message}")
            print(f"Context items: {result.get('context_items', 0)}")
            if preview:
                print("Top context preview:")
                for item in preview[:3]:
                    print(f"  - {item}")
            else:
                print("Top context preview: (none)")
            print(f"Answer: {answer[:220]}{'...' if len(answer) > 220 else ''}")

            if mode == "orbit" and memory_ids:
                feedback_payload = {
                    "memory_id": memory_ids[0],
                    "helpful": True,
                    "outcome_value": 1.0,
                }
                post_json(client, f"{base_url}/feedback", feedback_payload)



def main() -> None:
    parser = argparse.ArgumentParser(
        description="Compare baseline vs orbit memory behavior for meal coach example."
    )
    parser.add_argument("--base-url", default="http://localhost:8020")
    parser.add_argument("--user-id", default="ava")
    args = parser.parse_args()

    messages = [
        "I need quick dinner ideas for weekdays.",
        "I am allergic to peanuts and I hate mushrooms.",
        "Give me a high-protein idea under 25 minutes.",
        "Can you make it budget-friendly for this week?",
    ]

    run_sequence(args.base_url, f"{args.user_id}_baseline", "baseline", messages)
    run_sequence(args.base_url, f"{args.user_id}_orbit", "orbit", messages)

    print("\nDone. You should see richer context preview and tighter personalization in orbit mode.")


if __name__ == "__main__":
    main()
