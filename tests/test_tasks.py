from __future__ import annotations

from collections.abc import Mapping
from datetime import UTC, datetime, timedelta
from threading import Barrier, Thread
from typing import Any
from uuid import UUID, uuid4

import pytest

from anima_ha.agent import (
    AgentRuntime,
    CodexTurnResult,
    EpisodeRequest,
    EpisodeStatus,
    FinalDecision,
    FinalDisposition,
    InMemoryEpisodeStore,
    ScriptedCodexAdapter,
    TokenUsage,
    ToolRequestDecision,
)
from anima_ha.events import EventEnvelope
from anima_ha.plugins import (
    ExecutionBoundary,
    NativeRuntime,
    PluginManager,
)
from anima_ha.policy import Assurance, IdentityContext, PolicyContext, PolicyService, RequestOrigin
from anima_ha.tasks import (
    TASK_MANIFEST,
    DurableTask,
    DurableTaskDispatcher,
    InMemoryTaskStore,
    MisfirePolicy,
    RecurrenceCalculator,
    ScheduleKind,
    TaskClaimLost,
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


class FixedPolicyEvaluator:
    def __init__(self, decision: str) -> None:
        self.decision = decision

    def evaluate(self, document: dict[str, object]) -> dict[str, Any]:
        del document
        return {
            "decision": self.decision,
            "reason_code": f"TEST_{self.decision}",
            "required_assurance": "AUTHENTICATED",
            "confirmation_required": self.decision == "REQUIRE_CONFIRMATION",
            "policy_version": "phase10-test",
        }


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
    store.begin_dispatch(rerun.run_id, "worker-b", BASE + timedelta(seconds=3))
    store.mark_dispatched(
        rerun.run_id,
        worker_id="worker-b",
        source_event_id=replay.event_id,
        outcome={},
        now=BASE + timedelta(seconds=3),
    )


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
        },
        5,
        HOUSEHOLD,
    )
    task_id = UUID(result["task"]["task_id"])
    with pytest.raises(KeyError):
        plugin.invoke_for_household("get", {"task_id": str(task_id)}, 5, uuid4())


def _agent_task_request(
    manager: PluginManager,
    *,
    trigger_id: UUID,
    policy_service: PolicyService,
    principal_id: UUID,
) -> EpisodeRequest:
    packet_id = uuid4()
    packet = {
        "context_packet_id": str(packet_id),
        "schema_version": 1,
        "trigger_id": str(trigger_id),
        "selection_profile_version": "phase10.test.v1",
        "digest": f"packet-{trigger_id}",
        "omissions": [],
        "sections": {
            "events": {"status": "READY", "items": [], "error_code": None},
            "truth": {"status": "READY", "items": [], "error_code": None},
        },
    }
    return EpisodeRequest(
        trigger_id,
        packet_id,
        HOUSEHOLD,
        packet,
        tuple(manager.list_tools(plugin_id=TASK_MANIFEST.plugin_id)),
        IdentityContext(HOUSEHOLD, principal_id, Assurance.AUTHENTICATED),
        policy_service,
        PolicyContext(principal_role="resident"),
        RequestOrigin.AUTONOMOUS_AGENT,
    )


def _task_tool_turn(
    arguments: Mapping[str, Any], tool_id: str = "anima.durable-tasks.schedule"
) -> CodexTurnResult:
    return CodexTurnResult(
        ToolRequestDecision(tool_id, dict(arguments)),
        TokenUsage(),
        1.0,
        (),
    )


def _final_turn() -> CodexTurnResult:
    return CodexTurnResult(
        FinalDecision("DONE", False, "", "task mutation completed"),
        TokenUsage(),
        1.0,
        (),
    )


def _agent_task_fixture(
    decision: str = "ALLOW",
) -> tuple[TaskService, PluginManager, PolicyService, dict[str, object]]:
    task_service, _, _ = service()
    manager = PluginManager()
    manager.register(TASK_MANIFEST, NativeRuntime(TaskNativePlugin(task_service)))
    manager.enable(TASK_MANIFEST.plugin_id)
    policy_service = PolicyService(FixedPolicyEvaluator(decision))
    arguments: dict[str, object] = {
        "task_type": TaskType.REASONING_DUE.value,
        "title": "Agent-created future cognition",
        "payload": {"objective": "Re-evaluate the household later"},
        "schedule": {
            "kind": ScheduleKind.ONCE.value,
            "timezone": "UTC",
            "run_at": (BASE + timedelta(hours=1)).isoformat(),
        },
    }
    return task_service, manager, policy_service, arguments


def test_real_agent_runtime_task_schedule_injects_trusted_provenance() -> None:
    task_service, manager, policy_service, arguments = _agent_task_fixture()
    trigger_id = uuid4()
    principal_id = uuid4()
    request = _agent_task_request(
        manager,
        trigger_id=trigger_id,
        policy_service=policy_service,
        principal_id=principal_id,
    )
    runtime = AgentRuntime(
        ScriptedCodexAdapter([_task_tool_turn(arguments), _final_turn()]),
        manager,
        InMemoryEpisodeStore(),
    )

    result = runtime.run(request)

    assert result.episode.status == EpisodeStatus.COMPLETED
    assert result.episode.final_disposition == FinalDisposition.TOOL_SEQUENCE_COMPLETED
    tasks = task_service.list_tasks(HOUSEHOLD)
    assert len(tasks) == 1
    task = tasks[0]
    assert task.creator_principal_id == principal_id
    assert task.creator_episode_id == result.episode.episode_id
    assert task.creation_idempotency_key.startswith(f"anima:{trigger_id}:1:")
    assert task.provenance["created_via"] == "tasks.schedule"
    descriptor = manager.list_tools(plugin_id=TASK_MANIFEST.plugin_id)
    assert {tool.name: tool.execution_boundary for tool in descriptor}["schedule"] == (
        ExecutionBoundary.POLICY_GATED_INTERNAL
    )
    assert len(manager.list_tools(plugin_id=TASK_MANIFEST.plugin_id)) == 6


@pytest.mark.parametrize(
    ("decision", "expected_status"),
    [
        ("DENY", EpisodeStatus.COMPLETED),
        ("REQUIRE_CONFIRMATION", EpisodeStatus.WAITING_CONFIRMATION),
        ("REQUIRE_STRONGER_AUTH", EpisodeStatus.WAITING_STRONGER_AUTH),
    ],
)
def test_task_mutation_policy_outcomes_prevent_persistence(
    decision: str, expected_status: EpisodeStatus
) -> None:
    task_service, manager, policy_service, arguments = _agent_task_fixture(decision)
    request = _agent_task_request(
        manager,
        trigger_id=uuid4(),
        policy_service=policy_service,
        principal_id=uuid4(),
    )
    result = AgentRuntime(
        ScriptedCodexAdapter([_task_tool_turn(arguments), _final_turn()]),
        manager,
        InMemoryEpisodeStore(),
    ).run(request)

    assert result.episode.status == expected_status
    assert task_service.list_tasks(HOUSEHOLD) == []


def test_real_agent_runtime_task_lifecycle_tools_use_internal_gateway() -> None:
    task_service, manager, policy_service, arguments = _agent_task_fixture()
    created = task_service.create(
        household_id=HOUSEHOLD,
        task_type=TaskType.REASONING_DUE,
        title="Lifecycle through AgentRuntime",
        payload={"objective": "test lifecycle routing"},
        schedule=TaskSchedule(ScheduleKind.ONCE, "UTC", BASE + timedelta(hours=1)),
        creation_idempotency_key="lifecycle-direct",
        now=BASE,
    )
    del arguments
    principal_id = uuid4()
    for tool_id, expected_status in (
        ("anima.durable-tasks.pause", TaskStatus.PAUSED),
        ("anima.durable-tasks.resume", TaskStatus.ACTIVE),
        ("anima.durable-tasks.cancel", TaskStatus.CANCELLED),
    ):
        request = _agent_task_request(
            manager,
            trigger_id=uuid4(),
            policy_service=policy_service,
            principal_id=principal_id,
        )
        tool_args = {"task_id": str(created.task_id)}
        result = AgentRuntime(
            ScriptedCodexAdapter(
                [
                    _task_tool_turn(tool_args, tool_id),
                    _final_turn(),
                ]
            ),
            manager,
            InMemoryEpisodeStore(),
        ).run(request)
        assert result.episode.final_disposition == FinalDisposition.TOOL_SEQUENCE_COMPLETED
        assert task_service.get(created.task_id).status == expected_status


def test_task_creation_replay_uses_stable_system_idempotency_identity() -> None:
    task_service, manager, policy_service, arguments = _agent_task_fixture()
    trigger_id = uuid4()
    principal_id = uuid4()

    first = AgentRuntime(
        ScriptedCodexAdapter([_task_tool_turn(arguments), _final_turn()]),
        manager,
        InMemoryEpisodeStore(),
    ).run(
        _agent_task_request(
            manager,
            trigger_id=trigger_id,
            policy_service=policy_service,
            principal_id=principal_id,
        )
    )
    second = AgentRuntime(
        ScriptedCodexAdapter([_task_tool_turn(arguments), _final_turn()]),
        manager,
        InMemoryEpisodeStore(),
    ).run(
        _agent_task_request(
            manager,
            trigger_id=trigger_id,
            policy_service=policy_service,
            principal_id=principal_id,
        )
    )

    assert first.episode.status == second.episode.status == EpisodeStatus.COMPLETED
    tasks = task_service.list_tasks(HOUSEHOLD)
    assert len(tasks) == 1
    assert tasks[0].creator_episode_id == first.episode.episode_id


def test_lifecycle_terminal_states_are_stable_and_audit_is_not_duplicated() -> None:
    task_service, _, sink = service()
    task = create_task(task_service, key="lifecycle")
    cancelled = task_service.cancel(task.task_id).task
    assert cancelled.status == TaskStatus.CANCELLED
    assert task_service.pause(task.task_id).task.status == TaskStatus.CANCELLED
    assert task_service.resume(task.task_id).task.status == TaskStatus.CANCELLED
    lifecycle_events = [
        event.event_type for event in sink.events if event.event_type.startswith("task.")
    ]
    assert lifecycle_events == ["task.created", "task.cancelled"]


def test_stale_worker_cannot_begin_reclaimed_run() -> None:
    task_service, store, sink = service()
    task = create_task(task_service, key="claim-race")
    claimed_a = store.claim_due(BASE, "worker-a", 1, 1)[0]
    assert store.reclaim_expired(BASE + timedelta(seconds=2)) == 1
    claimed_b = store.claim_due(BASE + timedelta(seconds=3), "worker-b", 1, 1)[0]

    with pytest.raises(TaskClaimLost):
        store.begin_dispatch(claimed_a.run_id, "worker-a", BASE + timedelta(seconds=3))
    current = store.begin_dispatch(claimed_b.run_id, "worker-b", BASE + timedelta(seconds=3))
    event = DurableTaskDispatcher.event_for(task, current)
    sink.append(event)
    store.mark_dispatched(
        current.run_id,
        worker_id="worker-b",
        source_event_id=event.event_id,
        outcome={},
        now=BASE + timedelta(seconds=3),
    )
    assert len([item for item in sink.events if item.event_type == "scheduled_reasoning_due"]) == 1


def test_cancellation_before_dispatch_cancels_claimed_run_without_event() -> None:
    task_service, store, sink = service()
    task = create_task(
        task_service,
        key="cancel-race",
        task_schedule=TaskSchedule(
            ScheduleKind.INTERVAL,
            "UTC",
            BASE,
            interval_seconds=60,
        ),
    )
    claimed = store.claim_due(BASE, "worker-a", 30, 1)[0]
    assert task_service.cancel(task.task_id).task.status == TaskStatus.CANCELLED
    assert store.get_run(claimed.run_id).status.value == "CANCELLED"
    with pytest.raises(TaskClaimLost):
        store.begin_dispatch(claimed.run_id, "worker-a", BASE)
    assert not [item for item in sink.events if item.event_type == "scheduled_reasoning_due"]


def test_cancellation_during_dispatch_transition_leaves_no_orphaned_run() -> None:
    task_service, store, sink = service()
    task = create_task(
        task_service,
        key="cancel-dispatching",
        task_schedule=TaskSchedule(
            ScheduleKind.INTERVAL,
            "UTC",
            BASE,
            interval_seconds=60,
        ),
    )
    claimed = store.claim_due(BASE, "worker-a", 30, 1)[0]
    dispatching = store.begin_dispatch(claimed.run_id, "worker-a", BASE)
    assert dispatching.status.value == "DISPATCHING"
    assert task_service.cancel(task.task_id).task.status == TaskStatus.CANCELLED
    cancelled = store.cancel_run(dispatching.run_id, BASE)
    assert cancelled.status.value == "CANCELLED"
    assert not [
        run
        for run in store.list_runs(task.task_id)
        if run.status.value in {"PENDING", "CLAIMED", "DISPATCHING"}
    ]
    assert not [item for item in sink.events if item.event_type == "scheduled_reasoning_due"]
