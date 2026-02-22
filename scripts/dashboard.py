from __future__ import annotations

import json
from pathlib import Path


def main() -> None:
    path = Path("metrics.json")
    if not path.exists():
        print("metrics.json not found")
        return
    payload = json.loads(path.read_text(encoding="utf-8"))
    print("Memory Decision Engine Metrics")
    print(f"Generated at: {payload.get('generated_at')}")
    for key, value in payload.get("metrics", {}).items():
        print(f"- {key}: {value}")
    print(f"- storage_ratio: {payload.get('storage_ratio')}")


if __name__ == "__main__":
    main()
