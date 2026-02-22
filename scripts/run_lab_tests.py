from __future__ import annotations

import subprocess
import sys


def run(cmd: list[str]) -> int:
    process = subprocess.run(cmd, check=False)
    return int(process.returncode)


def main() -> int:
    commands = [
        [sys.executable, "-m", "pytest", "tests/lab", "-q"],
        [sys.executable, "-m", "pytest", "tests/integration", "-q"],
    ]
    for command in commands:
        code = run(command)
        if code != 0:
            return code
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
