#!/usr/bin/env python3
"""Run ANIMA's bounded local-router Wi-Fi presence observer."""

from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

from anima_ha.wifi_presence import main  # noqa: E402  # isort: skip


if __name__ == "__main__":
    raise SystemExit(main())
