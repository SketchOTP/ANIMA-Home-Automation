"""Bounded read-only readiness probes; never claim work or invoke a provider."""

from __future__ import annotations

import argparse
import http.client
import os
import sys
import time
import urllib.request
from pathlib import Path

PROJECT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT / "integrations/sentry/anima-household"))


def check_core() -> None:
    from anima_household_client import AnimaHouseholdClient

    client = AnimaHouseholdClient(
        endpoint=os.environ["ANIMA_SENTRY_SOCKET"],
        token_file=os.environ["ANIMA_SENTRY_SERVICE_TOKEN_FILE"],
        timeout=2,
    )
    payload = client.call("/v1/health")
    if payload.get("provider_id") != "anima-core" or payload.get("state") != "available":
        raise ValueError("Core not ready")


def check_stack() -> None:
    # Compose --wait proves DB health; its OPA health command only checks policy
    # syntax. This additional probe proves the running policy HTTP listener.
    with urllib.request.urlopen("http://127.0.0.1:18181/health?bundles", timeout=2) as response:
        if response.status != 200:
            raise ValueError("OPA not ready")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    choice = parser.add_mutually_exclusive_group(required=True)
    choice.add_argument("--core", action="store_true")
    choice.add_argument("--stack", action="store_true")
    parser.add_argument("--timeout", type=float, default=90)
    args = parser.parse_args()
    if not 0 < args.timeout <= 90:
        parser.error("timeout must be in (0, 90]")
    deadline = time.monotonic() + args.timeout
    while True:
        try:
            (check_core if args.core else check_stack)()
            print("AUTHENTICATED_CORE_READY" if args.core else "STACK_READY")
            return 0
        except (OSError, ValueError, RuntimeError, KeyError, http.client.HTTPException):
            # No credentials, HTTP bodies or exception text in readiness logs.
            if time.monotonic() >= deadline:
                print("CORE_NOT_READY" if args.core else "STACK_NOT_READY", file=sys.stderr)
                return 1
            time.sleep(0.5)


if __name__ == "__main__":
    raise SystemExit(main())
