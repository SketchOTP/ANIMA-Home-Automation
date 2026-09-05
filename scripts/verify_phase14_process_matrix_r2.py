"""Exercise actual Compose process restart continuity for ANIMA services."""

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
UI_PORT = os.environ.get("ANIMA_UI_PORT", "18090")
SEARXNG_PORT = os.environ.get("ANIMA_SEARXNG_PORT", "18888")


def compose(*args: str) -> str:
    project = os.environ.get("ANIMA_COMPOSE_PROJECT", "")
    command = ["docker", "compose"]
    if project:
        command.extend(("-p", project))
    result = subprocess.run(
        [*command, *args], check=True, text=True, capture_output=True
    )
    return result.stdout.strip()


def metadata(service: str) -> dict[str, str]:
    container_id = compose("ps", "-q", service)
    if not container_id:
        raise RuntimeError(f"Compose service {service!r} is not running")
    parts = subprocess.run(
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
    if len(parts) != 3:
        raise RuntimeError(f"unable to inspect Compose service {service!r}")
    return {"container_id": parts[0], "started_at": parts[1], "status": parts[2]}


def url_ok(url: str) -> bool:
    try:
        with urllib.request.urlopen(url, timeout=3) as response:
            return 200 <= response.status < 400
    except Exception:
        return False


def wait_for(service: str) -> None:
    deadline = time.monotonic() + 45
    while time.monotonic() < deadline:
        if service == "db":
            try:
                with psycopg.connect(DATABASE_URL, connect_timeout=2) as connection:
                    with connection.cursor() as cursor:
                        cursor.execute("SELECT 1")
                        if cursor.fetchone() == (1,):
                            return
            except Exception:
                pass
        elif service == "opa" and url_ok(f"{OPA_URL}/health"):
            return
        elif service == "searxng" and url_ok(
            f"http://127.0.0.1:{SEARXNG_PORT}/search?q=phase14&format=json"
        ):
            return
        elif service == "ui" and url_ok(f"http://127.0.0.1:{UI_PORT}/healthz"):
            return
        time.sleep(1)
    raise TimeoutError(f"Compose service {service!r} did not recover")


def main() -> int:
    if not DATABASE_URL:
        raise RuntimeError("ANIMA_DATABASE_URL is required")
    journal = PostgresEventJournal(DATABASE_URL)
    before_count = len(journal.list_events(limit=5000))
    services = ("db", "opa", "searxng", "ui")
    before = {service: metadata(service) for service in services}
    after: dict[str, dict[str, str]] = {}
    for service in services:
        compose("restart", service)
        wait_for(service)
        after[service] = metadata(service)
        assert after[service]["status"] == "running"
        assert after[service]["started_at"] != before[service]["started_at"]
    after_count = len(journal.list_events(limit=5000))
    assert after_count >= before_count
    payload: dict[str, Any] = {
        "scenario_id": "PROCESS_RESTART_MATRIX_SERVICE_CONTINUITY",
        "evidence_level": "POSTGRES_PROCESS",
        "services": list(services),
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
