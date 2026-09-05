"""Prove consequential work fails closed while the real OPA service is down."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

import psycopg

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.verify_phase14_action_recovery_r2 import (  # noqa: E402
    DATABASE_URL,
    OPA_URL,
    Gateway,
    request,
    success_result,
)

from anima_ha.action import ActionStatus, TruthSnapshot  # noqa: E402


def compose(*args: str) -> None:
    project = os.environ.get("ANIMA_COMPOSE_PROJECT", "")
    command = ["docker", "compose"]
    if project:
        command.extend(("-p", project))
    subprocess.run([*command, *args], check=True, capture_output=True, text=True)


def opa_ready() -> bool:
    try:
        with urllib.request.urlopen(f"{OPA_URL}/health", timeout=2) as response:
            return response.status == 200
    except Exception:
        return False


def wait_for_opa() -> None:
    deadline = time.monotonic() + 30
    while time.monotonic() < deadline:
        if opa_ready():
            return
        time.sleep(1)
    raise TimeoutError("OPA did not recover")


def main() -> int:
    if not DATABASE_URL:
        raise RuntimeError("ANIMA_DATABASE_URL is required")
    gateway = Gateway(success_result())
    coordinator, action = request(
        "opa-outage", gateway=gateway, refresher=lambda _: TruthSnapshot()
    )
    stopped = False
    try:
        compose("stop", "opa")
        stopped = True
        outcome = coordinator.execute(action)
        assert outcome.record.status == ActionStatus.POLICY_DENIED
        assert gateway.calls == 0
        with psycopg.connect(DATABASE_URL) as connection, connection.cursor() as cursor:
            cursor.execute(
                "SELECT reason_code FROM anima_policy_decisions "
                "WHERE action_intent_id=%s ORDER BY evaluated_at DESC LIMIT 1",
                (action.action_intent_id,),
            )
            row = cursor.fetchone()
        assert row == ("POLICY_UNAVAILABLE",), row
        print(
            json.dumps(
                {
                    "scenario_id": "OPA_OUTAGE_FAIL_CLOSED",
                    "status": "PASS",
                    "evidence_level": "POSTGRES_PROCESS",
                    "terminal_status": outcome.record.status.value,
                    "policy_reason": row[0],
                    "provider_dispatches": gateway.calls,
                    "zero_side_effect": True,
                    "phase15": False,
                },
                sort_keys=True,
            )
        )
        return 0
    finally:
        if stopped:
            compose("start", "opa")
            wait_for_opa()


if __name__ == "__main__":
    raise SystemExit(main())
