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


def compose(*args: str) -> str:
    project = os.environ.get("ANIMA_COMPOSE_PROJECT", "")
    command = ["docker", "compose"]
    if project:
        command.extend(("-p", project))
    result = subprocess.run([*command, *args], check=True, capture_output=True, text=True)
    return result.stdout.strip()


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
        compose("up", "-d", "opa")
        wait_for_opa()
        stop = subprocess.run(
            ["docker", "compose", "stop", "opa"],
            check=False,
            capture_output=True,
            text=True,
        )
        if stop.returncode != 0:
            container_id = compose("ps", "-q", "opa")
            if not container_id:
                raise RuntimeError(
                    f"unable to stop OPA: {stop.stderr.strip() or stop.stdout.strip()}"
                )
            subprocess.run(["docker", "stop", container_id], check=True, capture_output=True)
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
