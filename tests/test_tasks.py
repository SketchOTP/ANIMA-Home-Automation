from __future__ import annotations

from datetime import UTC, datetime, timedelta
from threading import Barrier, Thread
from uuid import UUID, uuid4

import pytest

from anima_ha.events import EventEnvelope
from anima_ha.tasks import (
    DurableTask,
    DurableTaskDispatcher,
    InMemoryTaskStore,
    MisfirePolicy,
    RecurrenceCalculator,
    ScheduleKind,
    TaskConflict,
    TaskNativePlugin,
    TaskSchedule,
    TaskService,
    TaskStatus,
    TaskType,
    TaskValidationError,
    deterministic_run_id,
)

HOUSEHOLD = UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")
BASE = datetime(2026, 1, 1, tzinfo=UTC)


class Sink:
    def __init__(self) -> None:
        self.events: list[EventEnvelope] = []

    def append(self, event: EventEnvelope) -> str:
        self.events.append(event)
        return event.event_id


def service() -> tuple[TaskService, InMemoryTaskStore, Sink]:
    store = InMemoryTaskStore()
    sink = Sink()
    return TaskService(store, sink), store, sink


def create_task(
    task_service: TaskService,
    *,
    key: str = "create-1",
    run_at: datetime = BASE,
    task_schedule: TaskSchedule | None = None,
) -> DurableTask:
    return task_service.create(
        household_id=HOUSEHOLD,
        task_type=TaskType.REASONING_DUE,
        title="Review the evening state",
        payload={"objective": "Review the evening state", "subject_refs": ["room:kitchen"]},
        schedule=task_schedule or TaskSchedule(ScheduleKind.ONCE, "UTC", run_at),
        creation_idempotency_key=key,
        now=BASE - timedelta(minutes=1),
    )


def test_schedule_contract_and_declarative_payload_safety() -> None:
    with pytest.raises(TaskValidationError):
        TaskSchedule(ScheduleKind.CRON, "UTC", BASE, cron_expression="every hour")
    task_service, _, _ = service()
    with pytest.raises(TaskValidationError):
        task_service.create(
            household_id=HOUSEHOLD,
            task_type=TaskType.REASONING_DUE,
            title="unsafe",
            payload={"objective": "x", "tool_id": "arbitrary"},
            schedule=TaskSchedule(ScheduleKind.ONCE, "UTC", BASE),
            creation_idempotency_key="unsafe",
        )


def test_cron_dst_policy_is_one_wall_clock_occurrence() -> None:
    calculator = RecurrenceCalculator()
    spring = calculator.next_after(
        "30 2 * * *", datetime(2026, 3, 8, 1, 59, tzinfo=UTC), "America/New_York"
    )
    assert spring.isoformat() == "2026-03-08T07:00:00+00:00"
    fall_first = calculator.next_after(
        "30 1 * * *", datetime(2026, 11, 1, 0, 59, tzinfo=UTC), "America/New_York"
    )
    fall_second = calculator.next_after("30 1 * * *", fall_first, "America/New_York")
    assert fall_first.isoformat() == "2026-11-01T05:30:00+00:00"
    assert fall_second.isoformat() == "2026-11-02T06:30:00+00:00"


def test_creation_idempotency_and_household_scoping() -> None:
    task_service, _, _ = service()
    first = create_task(task_service)
    second = create_task(task_service)
    assert first.task_id == second.task_id
    with pytest.raises(TaskConflict):
        task_service.create(
            household_id=HOUSEHOLD,
            task_type=TaskType.REASONING_DUE,
            title="different",
            payload={"objective": "different"},
            schedule=TaskSchedule(ScheduleKind.ONCE, "UTC", BASE + timedelta(hours=1)),
            creation_idempotency_key="create-1",
        )


def test_dispatch_is_deterministic_and_emits_guaranteed_bounded_intent() -> None:
    task_service, store, sink = service()
    task = create_task(task_service)
    dispatcher = DurableTaskDispatcher(store, sink, worker_id="worker-a")
    report = dispatcher.run_once(now=BASE, limit=10)
    assert report.claimed == report.dispatched == 1
    task_events = [event for event in sink.events if event.event_type == "scheduled_reasoning_due"]
    assert len(task_events) == 1
    event = task_events[0]
    assert event.event_type == "scheduled_reasoning_due"
    assert event.delivery_class.value == "GUARANTEED"
    assert event.payload["task_id"] == str(task.task_id)
    assert "tool_id" not in event.payload and "arguments" not in event.payload
    run = store.list_runs(task.task_id)[0]
    assert run.run_id == deterministic_run_id(task.task_id, run.scheduled_for)
    assert store.get(task.task_id).status == TaskStatus.COMPLETED


def test_crash_after_claim_is_reclaimed_and_not_lost() -> None:
    task_service, store, sink = service()
    task = create_task(task_service)
    claimed = store.claim_due(BASE, "worker-a", 1, 1)
    assert len(claimed) == 1
    assert store.reclaim_expired(BASE + timedelta(seconds=2)) == 1
    report = DurableTaskDispatcher(store, sink, worker_id="worker-b").run_once(
        now=BASE + timedelta(seconds=3)
    )
    assert report.dispatched == 1
    assert (
        len([event for event in sink.events if event.event_type == "scheduled_reasoning_due"]) == 1
    )
    assert len(store.list_runs(task.task_id)) == 1


def test_ambiguous_event_append_can_be_replayed_without_duplicate_event() -> None:
    task_service, store, sink = service()
    task = create_task(task_service)
    run = store.claim_due(BASE, "worker-a", 1, 1)[0]
    event = DurableTaskDispatcher.event_for(task, run)
    sink.append(event)
    assert store.reclaim_expired(BASE + timedelta(seconds=2)) == 1
    rerun = store.claim_due(BASE + timedelta(seconds=3), "worker-b", 1, 1)[0]
    replay = DurableTaskDispatcher.event_for(task, rerun)
    # A journal with source_event_id uniqueness deduplicates the replay.
    assert replay.event_id == event.event_id
    store.mark_dispatched(rerun.run_id, source_event_id=replay.event_id, outcome={}, now=BASE)


def test_concurrent_workers_claim_each_occurrence_once() -> None:
    task_service, store, _ = service()
    create_task(
        task_service,
        key="interval",
        task_schedule=TaskSchedule(
            ScheduleKind.INTERVAL,
            "UTC",
            BASE,
            interval_seconds=60,
            misfire_policy=MisfirePolicy.COALESCE_ONE,
        ),
    )
    barrier = Barrier(3)
    results: list[int] = []

    def claim(worker: str) -> None:
        barrier.wait()
        results.append(len(store.claim_due(BASE, worker, 10, 1)))

    threads = [Thread(target=claim, args=(f"worker-{i}",)) for i in range(2)]
    for thread in threads:
        thread.start()
    barrier.wait()
    for thread in threads:
        thread.join()
    assert sorted(results) == [0, 1]


def test_misfire_skip_pause_resume_and_cancel() -> None:
    task_service, store, sink = service()
    task = create_task(
        task_service,
        key="skip",
        task_schedule=TaskSchedule(
            ScheduleKind.INTERVAL,
            "UTC",
            BASE,
            interval_seconds=60,
            misfire_policy=MisfirePolicy.SKIP,
            misfire_grace_seconds=10,
        ),
    )
    assert store.claim_due(BASE + timedelta(seconds=20), "worker", 10, 1) == []
    assert store.list_runs(task.task_id)[0].status.value == "MISSED"
    paused = task_service.pause(task.task_id).task
    assert paused.status == TaskStatus.PAUSED
    resumed = task_service.resume(task.task_id, now=BASE + timedelta(minutes=5)).task
    assert resumed.status == TaskStatus.ACTIVE
    task_service.cancel(task.task_id)
    assert store.get(task.task_id).status == TaskStatus.CANCELLED
    assert not [event for event in sink.events if event.event_type == "scheduled_reasoning_due"]


def test_task_plugin_cannot_cross_households() -> None:
    task_service, _, _ = service()
    plugin = TaskNativePlugin(task_service)
    result = plugin.invoke_for_household(
        "schedule",
        {
            "task_type": "REASONING_DUE",
            "title": "A task",
            "payload": {"objective": "A task"},
            "schedule": {"kind": "ONCE", "timezone": "UTC", "run_at": BASE.isoformat()},
            "creation_idempotency_key": "plugin-1",
        },
        5,
        HOUSEHOLD,
    )
    task_id = UUID(result["task"]["task_id"])
    with pytest.raises(KeyError):
        plugin.invoke_for_household("get", {"task_id": str(task_id)}, 5, uuid4())
