from __future__ import annotations

import os
from pathlib import Path


def load_env_file(filename: str = ".env", start: Path | None = None) -> Path | None:
    """Load environment variables from the nearest .env file.

    Resolution order:
    1) starting directory
    2) each parent directory up to filesystem root

    Existing environment variables are preserved.
    """

    current = (start or Path.cwd()).resolve()
    for directory in (current, *current.parents):
        candidate = directory / filename
        if candidate.is_file():
            _apply_env(candidate)
            return candidate
    return None


def _apply_env(path: Path) -> None:
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[len("export ") :].lstrip()
        if "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        if not key:
            continue

        value = value.strip()
        if (value.startswith('"') and value.endswith('"')) or (
            value.startswith("'") and value.endswith("'")
        ):
            value = value[1:-1]
        elif " #" in value:
            value = value.split(" #", 1)[0].rstrip()

        os.environ.setdefault(key, value)
