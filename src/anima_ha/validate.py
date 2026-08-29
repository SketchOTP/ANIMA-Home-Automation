"""Local deterministic validation command."""

from __future__ import annotations

import subprocess
import sys


def main() -> int:
    commands = [
        ["ruff", "format", "--check", "src", "tests"],
        ["ruff", "check", "src", "tests"],
        ["mypy", "src", "tests"],
        ["pytest"],
    ]
    for command in commands:
        result = subprocess.run([sys.executable, "-m", *command], check=False)
        if result.returncode:
            return result.returncode
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
