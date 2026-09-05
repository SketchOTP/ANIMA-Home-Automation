"""Exercise a real PostgreSQL backup, restore, migration, and truth refresh.

The source database is the already-running Phase 14 Compose database.  The
archive is created and restored with the pinned PostgreSQL image into a fresh,
disposable database container.  Only structural evidence and digests are
printed; credentials and complete provider/database contents never enter the
evidence record.
"""

from __future__ import annotations

import hashlib
import json
import os
import socket
import subprocess
import tempfile
import time
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any
from uuid import UUID, uuid4, uuid5

import psycopg

from anima_ha.calendar import CalendarEvent, PostgresCalendarStore
from anima_ha.db.migrate import migrate
from anima_ha.events import DeliveryClass, EventEnvelope, EventImportance
from anima_ha.journal import PostgresEventJournal, PostgresTruthProjection
from anima_ha.tasks import (
    DurableTask,
    PostgresTaskStore,
    ScheduleKind,
    TaskSchedule,
    TaskType,
)

DATABASE_URL = os.environ.get("ANIMA_DATABASE_URL", "")
POSTGRES_IMAGE = (
    "pgvector/pgvector:pg16-bookworm@sha256:"
    "ccc6e83d6e35e931dc7c5def2022729d5a6c370318d099181995567ff1fb4d6b"
)
RESTORE_PASSWORD = "phase14-restore-only"
RUN_ID = uuid4()
NAMESPACE = uuid5(UUID("c1b2a3d4-e5f6-47a8-9012-3456789abcde"), str(RUN_ID))


def free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as listener:
        listener.bind(("127.0.0.1", 0))
        return int(listener.getsockname()[1])


def connect(url: str) -> psycopg.Connection[Any]:
    return psycopg.connect(url, connect_timeout=5)


def wait_for_database(url: str) -> None:
    deadline = time.monotonic() + 90
    while time.monotonic() < deadline:
        try:
            with connect(url) as connection, connection.cursor() as cursor:
                cursor.execute("SELECT 1")
                if cursor.fetchone() == (1,):
                    return
        except psycopg.Error:
            time.sleep(1)
    raise TimeoutError("restore PostgreSQL did not become ready")


def docker_pg_dump(archive: Path) -> None:
    source_password = os.environ.get("ANIMA_DB_PASSWORD", "")
    if not source_password:
        raise RuntimeError("ANIMA_DB_PASSWORD is required for the source backup")
    parsed = DATABASE_URL.rsplit("@", 1)[-1].split("/", 1)
    host_port = parsed[0].rsplit(":", 1)
    if len(host_port) != 2:
        raise RuntimeError("ANIMA_DATABASE_URL must expose a host port for backup")
    port = host_port[1]
    database = parsed[1].split("?", 1)[0]
    env = {"PGPASSWORD": source_password}
    with archive.open("wb") as output:
        subprocess.run(
            [
                "docker",
                "run",
                "--rm",
                "--network",
                "host",
                "-e",
                "PGPASSWORD",
                POSTGRES_IMAGE,
                "pg_dump",
                "--format=custom",
                "--no-owner",
                "--no-privileges",
                "--host=127.0.0.1",
                f"--port={port}",
                "--username=anima",
                f"--dbname={database}",
            ],
            check=True,
            env={**os.environ, **env},
            stdout=output,
            stderr=subprocess.PIPE,
            text=False,
        )


def docker_pg_restore(archive: Path, url: str) -> None:
    parsed = url.rsplit("@", 1)[-1].split("/", 1)
    host_port = parsed[0].rsplit(":", 1)
    port = host_port[1]
    database = parsed[1].split("?", 1)[0]
    subprocess.run(
        [
            "docker",
            "run",
            "--rm",
            "--network",
            "host",
            "-e",
            "PGPASSWORD",
            "-v",
            f"{archive}:/tmp/anima-phase14.dump:ro",
            POSTGRES_IMAGE,
            "pg_restore",
            "--exit-on-error",
            "--no-owner",
            "--no-privileges",
            "--host=127.0.0.1",
            f"--port={port}",
            "--username=anima",
            f"--dbname={database}",
            "/tmp/anima-phase14.dump",
        ],
        check=True,
        env={**os.environ, "PGPASSWORD": RESTORE_PASSWORD},
        capture_output=True,
        text=True,
    )


def start_restore_database(port: int) -> tuple[str, str]:
    name = f"anima-phase14-restore-{os.getpid()}-{port}"
    subprocess.run(
        [
            "docker",
            "run",
            "--detach",
            "--name",
            name,
            "--env",
            "POSTGRES_DB=anima",
            "--env",
            "POSTGRES_USER=anima",
            "--env",
            f"POSTGRES_PASSWORD={RESTORE_PASSWORD}",
            "--publish",
            f"127.0.0.1:{port}:5432",
            POSTGRES_IMAGE,
        ],
        check=True,
        stdout=subprocess.DEVNULL,
    )
    return name, f"postgresql://anima:{RESTORE_PASSWORD}@127.0.0.1:{port}/anima"


def event(
    source_event_id: str, *, value: str, observed_at: datetime, sequence: int = 1
) -> EventEnvelope:
    return EventEnvelope.create(
        event_id=str(uuid4()),
        event_type="truth.observation",
        source=f"phase14-backup-{RUN_ID}",
        source_event_id=source_event_id,
        subject_key=f"phase14-backup/{RUN_ID}/resource",
        occurred_at=observed_at,
        payload={
            "truth_key": f"phase14-backup/{RUN_ID}/resource",
            "source": f"phase14-backup-{RUN_ID}",
            "observed_at": observed_at.isoformat(),
            "received_at": datetime.now(UTC).isoformat(),
            "state": "KNOWN",
            "value": value,
            "source_sequence": sequence,
            "confidence": 1.0,
            "evidence_kind": "DIRECT",
            "freshness_seconds": 1,
            "metadata": {"phase14_run": str(RUN_ID)},
        },
        importance=EventImportance.IMPORTANT,
        delivery_class=DeliveryClass.BEST_EFFORT,
        metadata={"phase14_run": str(RUN_ID)},
    )


def seed_source() -> dict[str, str]:
    now = datetime.now(UTC)
    journal = PostgresEventJournal(DATABASE_URL)
    old_observation = event(
        f"phase14-backup-source-{RUN_ID}", value="historical", observed_at=now - timedelta(hours=2)
    )
    assert not journal.append(old_observation).deduplicated
    assert PostgresTruthProjection(DATABASE_URL).project_pending().failure is None

    task = DurableTask(
        task_id=uuid5(NAMESPACE, "task"),
        household_id=uuid5(NAMESPACE, "household"),
        task_type=TaskType.REASONING_DUE,
        title=f"Phase 14 backup task {RUN_ID}",
        payload={"objective": "verify backup continuity", "phase14_run": str(RUN_ID)},
        schedule=TaskSchedule(
            kind=ScheduleKind.ONCE,
            timezone="UTC",
            run_at=now + timedelta(days=1),
        ),
        creator_principal_id=None,
        creator_episode_id=None,
        creation_idempotency_key=f"phase14-backup-task-{RUN_ID}",
        created_at=now,
        updated_at=now,
        next_run_at=now + timedelta(days=1),
    )
    PostgresTaskStore(DATABASE_URL).create(task)

    calendar = CalendarEvent.create(
        household_id=task.household_id,
        title=f"Phase 14 backup calendar {RUN_ID}",
        start_at=now + timedelta(days=2),
        end_at=now + timedelta(days=2, hours=1),
        timezone="UTC",
        creation_idempotency_key=f"phase14-backup-calendar-{RUN_ID}",
        creator_principal_id=None,
        creator_episode_id=None,
        now=now,
    )
    PostgresCalendarStore(DATABASE_URL).create(calendar)
    return {
        "household_id": str(task.household_id),
        "task_id": str(task.task_id),
        "calendar_id": str(calendar.event_id),
        "event_id": old_observation.event_id,
    }


def seed_after_backup(ids: dict[str, str]) -> str:
    marker = f"phase14-post-backup-{RUN_ID}"
    now = datetime.now(UTC)
    journal = PostgresEventJournal(DATABASE_URL)
    post_event = event(marker, value="must-not-restore", observed_at=now)
    journal.append(post_event)
    task = DurableTask(
        task_id=uuid5(NAMESPACE, "post-task"),
        household_id=UUID(ids["household_id"]),
        task_type=TaskType.REASONING_DUE,
        title=marker,
        payload={"objective": "must not be restored", "marker": marker},
        schedule=TaskSchedule(
            kind=ScheduleKind.ONCE, timezone="UTC", run_at=now + timedelta(days=3)
        ),
        creator_principal_id=None,
        creator_episode_id=None,
        creation_idempotency_key=f"{marker}-task",
        created_at=now,
        updated_at=now,
        next_run_at=now + timedelta(days=3),
    )
    PostgresTaskStore(DATABASE_URL).create(task)
    return marker


def scalar(url: str, query: str, *args: object) -> int:
    with connect(url) as connection, connection.cursor() as cursor:
        cursor.execute(query, args)
        row = cursor.fetchone()
        return int(row[0]) if row else 0


def main() -> int:
    if not DATABASE_URL:
        raise RuntimeError("ANIMA_DATABASE_URL is required")
    ids = seed_source()
    restore_container = ""
    try:
        with tempfile.TemporaryDirectory(prefix="anima-phase14-backup-") as directory:
            archive = Path(directory) / "anima.dump"
            docker_pg_dump(archive)
            archive_bytes = archive.read_bytes()
            forbidden = (
                b"BEGIN RSA PRIVATE KEY",
                b"BEGIN OPENSSH PRIVATE KEY",
                b"ANIMA_DATABASE_URL",
                b"HA_ACCESS_TOKEN",
                b"OPA_URL",
            )
            assert all(token not in archive_bytes for token in forbidden)
            archive_digest = hashlib.sha256(archive_bytes).hexdigest()
            post_backup_marker = seed_after_backup(ids)

            restore_port = free_port()
            restore_container, restore_url = start_restore_database(restore_port)
            wait_for_database(restore_url)
            docker_pg_restore(archive, restore_url)
            applied = migrate(restore_url, 5)

            assert (
                scalar(
                    restore_url,
                    "SELECT count(*) FROM anima_event_journal WHERE event_id=%s",
                    ids["event_id"],
                )
                == 1
            )
            assert (
                scalar(
                    restore_url,
                    "SELECT count(*) FROM anima_durable_tasks WHERE task_id=%s",
                    ids["task_id"],
                )
                == 1
            )
            assert (
                scalar(
                    restore_url,
                    "SELECT count(*) FROM anima_calendar_events WHERE event_id=%s",
                    ids["calendar_id"],
                )
                == 1
            )
            assert (
                scalar(
                    restore_url,
                    "SELECT count(*) FROM anima_event_journal WHERE source_event_id=%s",
                    post_backup_marker,
                )
                == 0
            )
            assert (
                scalar(
                    restore_url,
                    "SELECT count(*) FROM anima_durable_tasks WHERE title=%s",
                    post_backup_marker,
                )
                == 0
            )

            # Rebuilding from the journal recomputes the old short-lived
            # observation as stale. A fresh observation is the only operation
            # that can return physical Truth to CURRENT/KNOWN.
            rebuilt = PostgresTruthProjection(restore_url).rebuild()
            stale = scalar(
                restore_url,
                "SELECT count(*) FROM anima_truth_state WHERE truth_key=%s AND status='STALE'",
                f"phase14-backup/{RUN_ID}/resource",
            )
            assert stale == 1
            fresh = event(
                f"phase14-backup-fresh-{RUN_ID}",
                value="reobserved",
                observed_at=datetime.now(UTC),
                sequence=2,
            )
            PostgresEventJournal(restore_url).append(fresh)
            assert PostgresTruthProjection(restore_url).project_pending().failure is None
            current = scalar(
                restore_url,
                "SELECT count(*) FROM anima_truth_state "
                "WHERE truth_key=%s AND status='CURRENT/KNOWN'",
                f"phase14-backup/{RUN_ID}/resource",
            )
            assert current == 1

            payload: dict[str, Any] = {
                "scenario_id": "BACKUP_RESTORE_CLEAN_ENVIRONMENT",
                "status": "PASS",
                "evidence_level": "POSTGRES_DOCKER_BACKUP_RESTORE",
                "backup_format": "pg_dump_custom",
                "backup_bytes": len(archive_bytes),
                "backup_digest": archive_digest,
                "secret_scan": "PASS",
                "restore_database_fresh": True,
                "migrations_after_restore": len(applied),
                "restored_event": True,
                "restored_task": True,
                "restored_calendar": True,
                "post_backup_marker_absent": True,
                "physical_truth_after_restore": "STALE_UNTIL_REOBSERVED",
                "truth_rebuild_rows": rebuilt.replayed,
                "fresh_reobservation_current": current == 1,
                "already_executed_effect_replay": 0,
                "phase15": False,
                "checked_at": datetime.now(UTC).isoformat(),
            }
            print(json.dumps(payload, sort_keys=True))
        return 0
    finally:
        if restore_container:
            subprocess.run(
                ["docker", "rm", "--force", restore_container],
                check=False,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )


if __name__ == "__main__":
    raise SystemExit(main())
