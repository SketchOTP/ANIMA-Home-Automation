"""Exercise real PostgreSQL and OPA container restart continuity."""

from __future__ import annotations

import json
import os
import subprocess
import time
import urllib.request
from datetime import UTC, datetime
from typing import Any

import psycopg

from anima_ha.journal import PostgresEventJournal

DATABASE_URL = os.environ.get("ANIMA_DATABASE_URL", "")
OPA_URL = os.environ.get("ANIMA_OPA_URL", "http://127.0.0.1:18181")


def compose(*args: str) -> str:
    project = os.environ.get("ANIMA_COMPOSE_PROJECT", "")
    command = ["docker", "compose"]
    if project:
        command.extend(("-p", project))
    result = subprocess.run(
        [*command, *args], check=True, text=True, capture_output=True
    )
    return result.stdout.strip()


def container_metadata(service: str) -> dict[str, str]:
    container_id = compose("ps", "-q", service)
    inspect = subprocess.run(
        [
            "docker",
            "inspect",
            "--format",
            "{{.Id}}|{{.State.StartedAt}}|{{.State.Status}}",
            container_id,
        ],
        check=True,
        text=True,
        capture_output=True,
    ).stdout.strip().split("|", 2)
    return {"container_id": inspect[0], "started_at": inspect[1], "status": inspect[2]}


def wait_healthy() -> None:
    deadline = time.monotonic() + 45
    while time.monotonic() < deadline:
        try:
            with urllib.request.urlopen(f"{OPA_URL}/health", timeout=2) as response:
                if response.status == 200:
                    with psycopg.connect(DATABASE_URL, connect_timeout=2) as connection:
                        with connection.cursor() as cursor:
                            cursor.execute("SELECT 1")
                            if cursor.fetchone() == (1,):
                                return
        except Exception:
            time.sleep(1)
    raise TimeoutError("PostgreSQL and OPA did not recover")


def main() -> int:
    if not DATABASE_URL:
        raise RuntimeError("ANIMA_DATABASE_URL is required")
    journal = PostgresEventJournal(DATABASE_URL)
    before_count = len(journal.list_events(limit=5000))
    before = {service: container_metadata(service) for service in ("db", "opa")}
    compose("restart", "db", "opa")
    wait_healthy()
    after_count = len(journal.list_events(limit=5000))
    after = {service: container_metadata(service) for service in ("db", "opa")}
    assert after_count >= before_count
    assert all(value["status"] == "running" for value in after.values())
    payload: dict[str, Any] = {
        "scenario_id": "PROCESS_RESTART_DB_OPA_IDLE_CONTINUITY",
        "evidence_level": "POSTGRES_OPA_CORE",
        "before": before,
        "after": after,
        "journal_records_before": before_count,
        "journal_records_after": after_count,
        "recovered_at": datetime.now(UTC).isoformat(),
        "status": "PASS",
        "phase15": False,
    }
    print(json.dumps(payload, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
