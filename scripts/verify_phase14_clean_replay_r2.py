"""Replay real Phase 14 store scenarios in two fresh PostgreSQL environments.

This is a test-process orchestrator only.  It starts disposable pinned
PostgreSQL containers, applies the repository migrations, and invokes the
existing real-store verifier.  It never copies credentials into evidence and
removes both containers in a finally block.
"""

from __future__ import annotations

import hashlib
import json
import os
import socket
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Any

import psycopg

from anima_ha.db.migrate import migrate

ROOT = Path(__file__).resolve().parents[1]
POSTGRES_IMAGE = (
    "pgvector/pgvector:pg16-bookworm@sha256:"
    "ccc6e83d6e35e931dc7c5def2022729d5a6c370318d099181995567ff1fb4d6b"
)
DATABASE_PASSWORD = "phase14-replay-only"


def free_port() -> int:
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        return int(listener.getsockname()[1])


def wait_for_database(url: str) -> None:
    deadline = time.monotonic() + 90
    while time.monotonic() < deadline:
        try:
            with psycopg.connect(url, connect_timeout=2) as connection:
                with connection.cursor() as cursor:
                    cursor.execute("SELECT 1")
                    if cursor.fetchone() == (1,):
                        return
        except Exception:
            time.sleep(1)
    raise TimeoutError("fresh replay PostgreSQL did not become ready")


def run_fresh(output_path: Path) -> dict[str, Any]:
    port = free_port()
    name = f"anima-phase14-replay-{os.getpid()}-{port}"
    url = f"postgresql://anima:{DATABASE_PASSWORD}@127.0.0.1:{port}/anima"
    subprocess.run(
        [
            "docker",
            "run",
            "-d",
            "--name",
            name,
            "-e",
            "POSTGRES_DB=anima",
            "-e",
            f"POSTGRES_PASSWORD={DATABASE_PASSWORD}",
            "-e",
            "POSTGRES_USER=anima",
            "-p",
            f"127.0.0.1:{port}:5432",
            POSTGRES_IMAGE,
        ],
        check=True,
        stdout=subprocess.DEVNULL,
    )
    try:
        wait_for_database(url)
        applied = migrate(url, 5)
        environment = {
            **os.environ,
            "ANIMA_DATABASE_URL": url,
            "GITHUB_SHA": os.environ.get("GITHUB_SHA", "local"),
        }
        subprocess.run(
            [
                sys.executable,
                str(ROOT / "scripts" / "verify_phase14_r2.py"),
                "--output",
                str(output_path),
            ],
            check=True,
            env=environment,
            capture_output=True,
            text=True,
        )
        payload = json.loads(output_path.read_text(encoding="utf-8"))
        payload["migration_count"] = len(applied)
        payload["fresh_database"] = True
        return payload
    finally:
        subprocess.run(
            ["docker", "rm", "-f", name],
            check=False,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )


def behavior_fingerprint(payload: dict[str, Any]) -> list[dict[str, Any]]:
    """Compare durable behavior, excluding run-scoped UUIDs and timestamps."""
    return [
        {
            key: result[key]
            for key in (
                "scenario_id",
                "status",
                "terminal_state",
                "side_effect_count",
                "transitions",
                "recovery_behavior",
                "evidence_level",
            )
        }
        for result in payload["results"]
    ]


def digest(value: Any) -> str:
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(encoded).hexdigest()


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="anima-phase14-clean-replay-") as directory:
        first = run_fresh(Path(directory) / "first.json")
        second = run_fresh(Path(directory) / "second.json")
        first_behavior = behavior_fingerprint(first)
        second_behavior = behavior_fingerprint(second)
        assert len(first_behavior) >= 5
        assert first_behavior == second_behavior
        matched_digest = digest(first_behavior)

        intentional = [dict(item) for item in second_behavior]
        intentional[0] = {**intentional[0], "terminal_state": "INTENTIONAL_EXPECTED_DIFF"}
        differences = [
            item["scenario_id"]
            for item, expected in zip(first_behavior, intentional, strict=True)
            if item != expected
        ]
        assert differences == [first_behavior[0]["scenario_id"]]
        payload = {
            "scenario_id": "REAL_STORE_CLEAN_REPLAY",
            "status": "PASS",
            "evidence_level": "REAL_STORE_REPLAY",
            "fresh_runs": 2,
            "scenario_count": len(first_behavior),
            "matched_behavior_digest": matched_digest,
            "intentional_diff_detected": differences,
            "migration_count": first["migration_count"],
            "postgres_image": POSTGRES_IMAGE.split("@", 1)[0],
            "phase15": False,
        }
        print(json.dumps(payload, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
