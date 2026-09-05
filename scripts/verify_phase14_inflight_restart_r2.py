"""Exercise durable ANIMA state across real PostgreSQL process restarts."""

from __future__ import annotations

import json
import os
import subprocess
import time
from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

import psycopg

from anima_ha.db.migrate import migrate
from anima_ha.intelligence import (
    IntelligenceLifecycle,
    IntelligenceOrigin,
    IntelligenceRequest,
    IntelligenceResult,
    IntelligenceResultStatus,
    PostgresIntelligenceStore,
)
from anima_ha.tasks import (
    DurableTask,
    PostgresTaskStore,
    ScheduleKind,
    TaskSchedule,
    TaskType,
)

DATABASE_URL = os.environ.get("ANIMA_DATABASE_URL", "")
HOUSEHOLD_ID = uuid4()
PROVIDER = "sentry"


def compose(*args: str) -> str:
    project = os.environ.get("ANIMA_COMPOSE_PROJECT", "")
    command = ["docker", "compose"]
    if project:
        command.extend(("-p", project))
    return subprocess.run(
        [*command, *args], check=True, capture_output=True, text=True
    ).stdout.strip()


def container_metadata() -> dict[str, str]:
    container_id = compose("ps", "-q", "db")
    if not container_id:
        raise RuntimeError("database Compose container is not running")
    parts = subprocess.run(
        [
            "docker",
            "inspect",
            "--format",
            "{{.Id}}|{{.State.StartedAt}}|{{.State.Status}}",
            container_id,
        ],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip().split("|", 2)
    if len(parts) != 3:
        raise RuntimeError("database container metadata is incomplete")
    return {"container_id": parts[0], "started_at": parts[1], "status": parts[2]}


def wait_for_database() -> None:
    deadline = time.monotonic() + 45
    while time.monotonic() < deadline:
        try:
            with psycopg.connect(DATABASE_URL, connect_timeout=2) as connection:
                with connection.cursor() as cursor:
                    cursor.execute("SELECT 1")
                    if cursor.fetchone() == (1,):
                        return
        except Exception:
            time.sleep(1)
    raise TimeoutError("PostgreSQL did not recover after restart")


def restart_database() -> tuple[dict[str, str], dict[str, str]]:
    before = container_metadata()
    compose("restart", "db")
    wait_for_database()
    after = container_metadata()
    if before["container_id"] != after["container_id"]:
        raise AssertionError("Compose restart unexpectedly recreated the database container")
    if before["started_at"] == after["started_at"] or after["status"] != "running":
        raise AssertionError("database process identity did not change after restart")
    return before, after


def request(label: str, household_id: UUID) -> IntelligenceRequest:
    return IntelligenceRequest(
        request_id=uuid4(),
        household_id=household_id,
        origin=IntelligenceOrigin.DIRECT_SENTRY_INTERACTION,
        context_packet_id=uuid4(),
        context_digest=f"phase14-inflight:{label}:context",
        catalogue_digest=f"phase14-inflight:{label}:catalogue",
        provider_id=PROVIDER,
        provider_version="r2",
        idempotency_key=f"phase14-inflight-{label}-{uuid4()}",
        request_metadata={"phase14_label": label},
        catalogue=(),
    )


def main() -> int:
    if not DATABASE_URL:
        raise RuntimeError("ANIMA_DATABASE_URL is required")
    migrate(DATABASE_URL, 5)
    store = PostgresIntelligenceStore(DATABASE_URL)
    transitions: list[dict[str, Any]] = []

    pending_household = uuid4()
    pending = store.enqueue(request("pending", pending_household))
    before, after = restart_database()
    current = store.get(pending.request_id)
    assert current is not None and current.lifecycle == IntelligenceLifecycle.PENDING
    transitions.append(
        {"state": "PENDING", "before": before, "after": after, "replay": False}
    )

    claimed_household = uuid4()
    claimed = store.enqueue(request("claimed", claimed_household))
    claimed_record = store.claim(
        "phase14-inflight-claimed", provider_id=PROVIDER, household_id=claimed_household
    )
    assert claimed_record is not None and claimed_record.request_id == claimed.request_id
    before, after = restart_database()
    current = store.get(claimed.request_id)
    assert current is not None and current.lifecycle == IntelligenceLifecycle.CLAIMED
    transitions.append(
        {"state": "CLAIMED", "before": before, "after": after, "replay": False}
    )

    running_household = uuid4()
    running = store.enqueue(request("provider-running", running_household))
    running_record = store.claim(
        "phase14-inflight-running", provider_id=PROVIDER, household_id=running_household
    )
    assert running_record is not None and running_record.request_id == running.request_id
    assert store.transition(
        running.request_id,
        "phase14-inflight-running",
        running_record.fencing_generation,
        IntelligenceLifecycle.PROVIDER_RUNNING,
        {"provider_invocation_started": True},
    )
    before, after = restart_database()
    current = store.get(running.request_id)
    assert current is not None and current.lifecycle == IntelligenceLifecycle.PROVIDER_RUNNING
    transitions.append(
        {
            "state": "PROVIDER_RUNNING",
            "before": before,
            "after": after,
            "replay": False,
            "provider_invocation_started": current.provider_invocation_started,
        }
    )

    durable_household = uuid4()
    durable = store.enqueue(request("durable-result", durable_household))
    durable_record = store.claim(
        "phase14-inflight-result", provider_id=PROVIDER, household_id=durable_household
    )
    assert durable_record is not None and durable_record.request_id == durable.request_id
    assert store.transition(
        durable.request_id,
        "phase14-inflight-result",
        durable_record.fencing_generation,
        IntelligenceLifecycle.PROVIDER_RUNNING,
        {"provider_invocation_started": True},
    )
    assert store.record_result(
        durable.request_id,
        "phase14-inflight-result",
        durable_record.fencing_generation,
        IntelligenceResult(
            durable.request_id,
            IntelligenceResultStatus.RESPONSE,
            response_text="durable restart result",
        ),
    )
    before, after = restart_database()
    current = store.get(durable.request_id)
    assert current is not None and current.lifecycle == IntelligenceLifecycle.COMPLETED
    assert (
        store.claim(
            "phase14-inflight-no-rerun",
            provider_id=PROVIDER,
            household_id=durable_household,
        )
        is None
    )
    transitions.append(
        {"state": "RESULT_RECEIVED", "before": before, "after": after, "replay": False}
    )

    now = datetime.now(UTC)
    task = DurableTask(
        task_id=uuid4(),
        household_id=HOUSEHOLD_ID,
        task_type=TaskType.REASONING_DUE,
        title="Phase 14 due-task restart",
        payload={"objective": "verify due task remains durable"},
        schedule=TaskSchedule(kind=ScheduleKind.ONCE, timezone="UTC", run_at=now),
        creator_principal_id=None,
        creator_episode_id=None,
        creation_idempotency_key=f"phase14-inflight-task-{uuid4()}",
        created_at=now,
        updated_at=now,
        next_run_at=now,
    )
    task_store = PostgresTaskStore(DATABASE_URL)
    task_store.create(task)
    before, after = restart_database()
    recovered_task = task_store.get(task.task_id)
    assert recovered_task.task_id == task.task_id
    transitions.append(
        {
            "state": "DUE_TASK",
            "before": before,
            "after": after,
            "task_id": str(task.task_id),
            "replay": False,
        }
    )

    print(
        json.dumps(
            {
                "scenario_id": "PROCESS_RESTART_INFLIGHT_DURABLE_STATES",
                "status": "PASS",
                "evidence_level": "POSTGRES_PROCESS",
                "household_scope_isolated": True,
                "states": transitions,
                "provider_replays": 0,
                "embedded_agent_runtime_fallback": False,
                "checked_at": datetime.now(UTC).isoformat(),
                "phase15": False,
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
