"""PostgreSQL durability and multi-worker evidence for Phase 10 tasks."""

from __future__ import annotations

import os
import threading
from datetime import UTC, datetime, timedelta
from uuid import uuid4

from anima_ha.db.migrate import migrate
from anima_ha.journal import PostgresEventJournal
from anima_ha.tasks import (
    DispatchReport,
    DurableTaskDispatcher,
    PostgresTaskStore,
    ScheduleKind,
    TaskSchedule,
    TaskService,
    TaskType,
)

DATABASE_URL = os.environ.get(
    "ANIMA_DATABASE_URL", "postgresql://anima:anima_dev_only@localhost:55432/anima"
)


def main() -> int:
    migrate(DATABASE_URL, 5)
    household_id = uuid4()
    now = datetime.now(UTC).replace(microsecond=0)
    store = PostgresTaskStore(DATABASE_URL)
    journal = PostgresEventJournal(DATABASE_URL)
    service = TaskService(store, journal)
    task = service.create(
        household_id=household_id,
        task_type=TaskType.REASONING_DUE,
        title="Phase 10 durable task evidence",
        payload={"objective": "Produce a bounded evidence packet", "subject_refs": ["phase10"]},
        schedule=TaskSchedule(ScheduleKind.ONCE, "UTC", now),
        creation_idempotency_key=f"phase10-{uuid4()}",
        now=now,
    )
    duplicate = service.create(
        household_id=household_id,
        task_type=TaskType.REASONING_DUE,
        title="Phase 10 durable task evidence",
        payload={"objective": "Produce a bounded evidence packet", "subject_refs": ["phase10"]},
        schedule=TaskSchedule(ScheduleKind.ONCE, "UTC", now),
        creation_idempotency_key=task.creation_idempotency_key,
        now=now,
    )
    assert duplicate.task_id == task.task_id

    dispatchers = [
        DurableTaskDispatcher(store, journal, worker_id=f"p10-worker-{i}") for i in range(2)
    ]
    barrier = threading.Barrier(3)
    reports: list[DispatchReport] = []

    def dispatch(dispatcher: DurableTaskDispatcher) -> None:
        barrier.wait()
        reports.append(dispatcher.run_once(now=now, limit=1))

    threads = [threading.Thread(target=dispatch, args=(dispatcher,)) for dispatcher in dispatchers]
    for thread in threads:
        thread.start()
    barrier.wait()
    for thread in threads:
        thread.join(timeout=10)
    assert not any(thread.is_alive() for thread in threads)
    assert sum(report.dispatched for report in reports) == 1

    run = store.list_runs(task.task_id)[0]
    event = DurableTaskDispatcher.event_for(task, run)
    first = journal.append(event)
    second = journal.append(event)
    assert first.deduplicated is True
    assert second.deduplicated is True

    crash_task = service.create(
        household_id=household_id,
        task_type=TaskType.REASONING_DUE,
        title="Lease recovery evidence",
        payload={"objective": "Recover a claimed occurrence"},
        schedule=TaskSchedule(ScheduleKind.ONCE, "UTC", now + timedelta(seconds=1)),
        creation_idempotency_key=f"phase10-crash-{uuid4()}",
        now=now,
    )
    claimed = store.claim_due(now + timedelta(seconds=1), "crashed-worker", 1, 1)
    assert claimed and claimed[0].task_id == crash_task.task_id
    assert store.reclaim_expired(now + timedelta(seconds=3)) == 1
    recovered = DurableTaskDispatcher(store, journal, worker_id="recovery-worker").run_once(
        now=now + timedelta(seconds=4), limit=1
    )
    assert recovered.dispatched == 1
    print("PHASE10_POSTGRES_DURABLE_TASKS_PASS")
    print(f"task_id={task.task_id}")
    print("creation_idempotency=same key returned same task")
    print("concurrent_claims=one occurrence dispatched by two PostgreSQL workers")
    print("event_replay=source-event uniqueness deduplicated replay")
    print("lease_recovery=expired claim reclaimed and dispatched once")
    idle_ms = DurableTaskDispatcher(store, journal, worker_id="idle").diagnostics()[
        "poll_elapsed_ms"
    ]
    print(f"idle_dispatcher_ms={idle_ms:.3f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
