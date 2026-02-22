from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path


def main() -> None:
    output = Path("synthetic_events.jsonl")
    now = datetime.now(UTC)
    with output.open("w", encoding="utf-8") as handle:
        for idx in range(1000):
            event = {
                "timestamp": int((now - timedelta(minutes=idx)).timestamp()),
                "entity_id": f"user_{idx % 50}",
                "event_type": "interaction" if idx % 2 == 0 else "task_execution",
                "description": f"Synthetic developer event {idx}",
                "metadata": {
                    "summary": f"Synthetic summary {idx}",
                    "intent": "interaction" if idx % 2 == 0 else "task_execution",
                    "entities": [f"user_{idx % 50}", f"repo_{idx % 10}"],
                    "relationships": [f"user_{idx % 50}->repo_{idx % 10}"],
                },
            }
            handle.write(json.dumps(event, ensure_ascii=True) + "\n")
    print(f"Wrote {output}")


if __name__ == "__main__":
    main()
