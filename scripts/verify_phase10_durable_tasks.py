"""PostgreSQL durability and multi-worker evidence for Phase 10 tasks."""

from __future__ import annotations

import os
import threading
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import psycopg

from anima_ha.action import (
    ActionExecutionCoordinator,
    ActionStatus,
    InMemoryActionStore,
    InMemoryResourceLocker,
    TruthSnapshot,
)
from anima_ha.agent import (
    AgentRuntime,
    CodexTurnResult,
    EpisodeRequest,
    FinalDecision,
    InMemoryEpisodeStore,
    PostgresEpisodeStore,
    ScriptedCodexAdapter,
    TokenUsage,
    ToolRequestDecision,
)
from anima_ha.attention import AttentionProfile, AttentionRule, PostgresAttentionService, RuleAction
from anima_ha.context import ContextBroker
from anima_ha.db.migrate import migrate
from anima_ha.journal import PostgresEventJournal
from anima_ha.plugins import (
    ExternalContentTrust,
    Idempotency,
    InvocationOutcome,
    InvocationResult,
    NativeRuntime,
    PluginManager,
    ToolDescriptor,
)
from anima_ha.policy import Assurance, IdentityContext, PolicyContext, PolicyService, RequestOrigin
from anima_ha.tasks import (
    TASK_MANIFEST,
    DispatchReport,
    DurableTaskDispatcher,
    InMemoryTaskStore,
    PostgresTaskStore,
    ScheduledCognitionBridge,
    ScheduleKind,
    TaskClaimLost,
    TaskNativePlugin,
    TaskSchedule,
    TaskService,
    TaskStatus,
    TaskType,
    deterministic_run_id,
)

DATABASE_URL = os.environ.get(
    "ANIMA_DATABASE_URL", "postgresql://anima:anima_dev_only@localhost:55432/anima"
)


class AllowEvaluator:
    def evaluate(self, document: dict[str, object]) -> dict[str, str]:
        del document
        return {
            "decision": "ALLOW",
            "reason_code": "PHASE10_TASK_ALLOWED",
            "required_assurance": "AUTHENTICATED",
            "policy_version": "phase10-script",
        }


def _agent_packet(trigger_id: str, packet_id: str) -> dict[str, object]:
    return {
        "context_packet_id": packet_id,
        "schema_version": 1,
        "trigger_id": trigger_id,
        "selection_profile_version": "phase10.integration.v1",
        "digest": f"phase10-packet-{packet_id}",
        "omissions": [],
        "sections": {
            "events": {"status": "READY", "items": [], "error_code": None},
            "truth": {"status": "READY", "items": [], "error_code": None},
        },
    }


def run_agent_and_scheduled_cognition(
    task_service: TaskService,
    store: PostgresTaskStore,
    journal: PostgresEventJournal,
) -> None:
    household_id = uuid4()
    principal_id = uuid4()
    trigger_id = uuid4()
    creation_packet_id = uuid4()
    now = datetime.now(UTC).replace(microsecond=0)
    manager = PluginManager(journal=journal)
    manager.register(TASK_MANIFEST, NativeRuntime(TaskNativePlugin(task_service)))
    manager.enable(TASK_MANIFEST.plugin_id)
    policy = PolicyService(AllowEvaluator())
    arguments = {
        "task_type": TaskType.REASONING_DUE.value,
        "title": "Phase 10 scheduled cognition",
        "payload": {"objective": "Re-evaluate current household state"},
        "schedule": {
            "kind": ScheduleKind.ONCE.value,
            "timezone": "UTC",
            "run_at": now.isoformat(),
        },
    }
    initial_request = EpisodeRequest(
        trigger_id=trigger_id,
        context_packet_id=creation_packet_id,
        household_id=household_id,
        context_packet=_agent_packet(str(trigger_id), str(creation_packet_id)),
        tools=tuple(manager.list_tools()),
        identity=IdentityContext(household_id, principal_id, Assurance.AUTHENTICATED),
        policy_service=policy,
        policy_context=PolicyContext(principal_role="resident"),
        origin=RequestOrigin.AUTONOMOUS_AGENT,
    )
    creation_runtime = AgentRuntime(
        ScriptedCodexAdapter(
            [
                CodexTurnResult(
                    ToolRequestDecision("anima.durable-tasks.schedule", arguments),
                    TokenUsage(),
                    1.0,
                    (),
                ),
                CodexTurnResult(
                    FinalDecision("DONE", False, "", "scheduled"),
                    TokenUsage(),
                    1.0,
                    (),
                ),
            ]
        ),
        manager,
        InMemoryEpisodeStore(),
        journal=journal,
    )
    created = creation_runtime.run(initial_request)
    assert created.episode.final_disposition is not None
    task = task_service.list_tasks(household_id)[0]
    assert task.creator_principal_id == principal_id
    assert task.creator_episode_id == created.episode.episode_id

    profile = AttentionProfile(
        f"phase10.integration.{uuid4()}",
        (
            AttentionRule(
                "scheduled-reasoning",
                RuleAction.TRIGGER,
                event_types=("scheduled_reasoning_due",),
                priority=100,
            ),
        ),
    )
    attention = PostgresAttentionService(DATABASE_URL)
    context = ContextBroker(DATABASE_URL, selection_profile_version=profile.profile_version)
    consumer_name = f"phase10-cognition-{uuid4()}"
    attention.register_profile(profile)
    with psycopg.connect(DATABASE_URL) as connection, connection.cursor() as cursor:
        cursor.execute(
            "SELECT COALESCE(MAX(journal_position), 0) AS position FROM anima_event_journal"
        )
        journal_position = cursor.fetchone()
        assert journal_position is not None
        cursor.execute(
            """
            INSERT INTO anima_attention_cursors (consumer_name, profile_version, last_position)
            VALUES (%s, %s, %s)
            ON CONFLICT (consumer_name) DO NOTHING
            """,
            (consumer_name, profile.profile_version, journal_position[0]),
        )
        connection.commit()

    class FutureActionGateway:
        def __init__(self) -> None:
            self.calls = 0

        def invoke(
            self, tool_id: str, arguments: dict[str, object], **kwargs: object
        ) -> InvocationResult:
            del arguments, kwargs
            self.calls += 1
            return InvocationResult(
                InvocationOutcome.SUCCESS,
                tool_id,
                "anima.synthetic-provider",
                "1.0.0",
                1.0,
                result={"acknowledged": True},
            )

    future_tool = ToolDescriptor(
        tool_id="anima.synthetic.set_power",
        plugin_id="anima.synthetic-provider",
        capability_id="home.control",
        name="set_power",
        description="Synthetic future consequential action",
        input_schema={"type": "object"},
        output_schema={"type": "object"},
        risk_class="LOW_RISK_HOME_CONTROL",
        semantic_action="set_power",
        read_only=False,
        idempotency=Idempotency.KEYED,
        timeout=2.0,
        verification_requirement="PROVIDER_STATE_MATCH",
        external_content_trust=ExternalContentTrust.PLUGIN_TRUSTED,
        availability=True,
        version="1.0.0",
        provenance="phase10-synthetic",
        execution_spec={"profile": "set_power"},
    )
    future_gateway = FutureActionGateway()
    future_action_store = InMemoryActionStore()
    future_action_executor = ActionExecutionCoordinator(
        future_gateway,
        future_action_store,
        InMemoryResourceLocker(),
    )
    future_state = iter(
        [
            TruthSnapshot({"power": {"state": "KNOWN", "value": "off", "version": "1"}}),
            TruthSnapshot({"power": {"state": "KNOWN", "value": "on", "version": "2"}}),
        ]
    )
    due_runtime = AgentRuntime(
        ScriptedCodexAdapter(
            [
                CodexTurnResult(
                    ToolRequestDecision(
                        future_tool.tool_id,
                        {"resource_id": str(uuid4()), "desired_on": True},
                    ),
                    TokenUsage(),
                    1.0,
                    (),
                ),
                CodexTurnResult(
                    FinalDecision("DONE", False, "", "fresh due-time cognition and action"),
                    TokenUsage(),
                    1.0,
                    (),
                ),
            ]
        ),
        manager,
        PostgresEpisodeStore(DATABASE_URL),
        journal=journal,
        action_executor=future_action_executor,
    )
    bridge = ScheduledCognitionBridge(
        DurableTaskDispatcher(store, journal, worker_id=f"phase10-cognition-{uuid4()}"),
        attention,
        context,
        due_runtime,
    )
    result = bridge.run_once(
        profile=profile,
        household_id=household_id,
        consumer_name=consumer_name,
        request_factory=lambda trigger, packet: EpisodeRequest(
            trigger_id=trigger.trigger_id,
            context_packet_id=packet.context_packet_id,
            household_id=household_id,
            context_packet=packet.to_payload(),
            tools=(future_tool,),
            identity=IdentityContext(household_id, None, Assurance.ANONYMOUS),
            policy_service=policy,
            policy_context=PolicyContext(),
            origin=RequestOrigin.DURABLE_SYSTEM_TASK,
            action_refresher=lambda resources: next(future_state),
        ),
        now=now,
    )
    assert result.dispatch.dispatched == 1
    assert len(result.episodes) == 1
    assert result.episodes[0].episode.context_packet_id != creation_packet_id
    assert future_gateway.calls == 1
    future_records = list(future_action_store.records.values())
    assert len(future_records) == 1
    assert future_records[0].status == ActionStatus.SUCCEEDED
    print("agent_task_schedule=PASS")
    print("scheduled_cognition_fresh_context=PASS")
    print("scheduled_future_action_phase9=PASS")
    print("creator_provenance_not_future_auth=PASS")


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
    errors: list[str] = []

    def dispatch(dispatcher: DurableTaskDispatcher) -> None:
        try:
            barrier.wait()
            reports.append(dispatcher.run_once(now=now, limit=1))
        except BaseException as exc:
            errors.append(f"{type(exc).__name__}: {exc}")

    threads = [threading.Thread(target=dispatch, args=(dispatcher,)) for dispatcher in dispatchers]
    for thread in threads:
        thread.start()
    barrier.wait()
    for thread in threads:
        thread.join(timeout=10)
    assert not any(thread.is_alive() for thread in threads)
    assert not errors, errors
    target_run_id = deterministic_run_id(task.task_id, now)
    assert sum(target_run_id in report.run_ids for report in reports) == 1, reports
    assert store.get_run(target_run_id).status.value == "COMPLETED"

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
    lifecycle_mem = InMemoryTaskStore()
    lifecycle_mem_service = TaskService(lifecycle_mem)
    lifecycle_schedule = TaskSchedule(
        ScheduleKind.ONCE,
        "UTC",
        now + timedelta(hours=1),
    )
    mem_task = lifecycle_mem_service.create(
        household_id=household_id,
        task_type=TaskType.REASONING_DUE,
        title="Lifecycle parity",
        payload={"objective": "lifecycle"},
        schedule=lifecycle_schedule,
        creation_idempotency_key=f"lifecycle-mem-{uuid4()}",
        now=now,
    )
    pg_task = service.create(
        household_id=household_id,
        task_type=TaskType.REASONING_DUE,
        title="Lifecycle parity",
        payload={"objective": "lifecycle"},
        schedule=lifecycle_schedule,
        creation_idempotency_key=f"lifecycle-pg-{uuid4()}",
        now=now,
    )
    mem_states = [
        lifecycle_mem_service.pause(mem_task.task_id).task.status,
        lifecycle_mem_service.resume(mem_task.task_id).task.status,
        lifecycle_mem_service.cancel(mem_task.task_id).task.status,
        lifecycle_mem_service.resume(mem_task.task_id).task.status,
    ]
    pg_states = [
        service.pause(pg_task.task_id).task.status,
        service.resume(pg_task.task_id).task.status,
        service.cancel(pg_task.task_id).task.status,
        service.resume(pg_task.task_id).task.status,
    ]
    assert (
        mem_states
        == pg_states
        == [
            TaskStatus.PAUSED,
            TaskStatus.ACTIVE,
            TaskStatus.CANCELLED,
            TaskStatus.CANCELLED,
        ]
    )
    race_task = service.create(
        household_id=household_id,
        task_type=TaskType.REASONING_DUE,
        title="Lease ownership race",
        payload={"objective": "lease ownership"},
        schedule=TaskSchedule(ScheduleKind.ONCE, "UTC", now),
        creation_idempotency_key=f"claim-race-{uuid4()}",
        now=now,
    )
    claimed_a = store.claim_due(now, "worker-a", 1, 1)[0]
    assert claimed_a.task_id == race_task.task_id
    assert store.reclaim_expired(now + timedelta(seconds=2)) == 1
    claimed_b = store.claim_due(now + timedelta(seconds=3), "worker-b", 1, 1)[0]
    try:
        store.begin_dispatch(claimed_a.run_id, "worker-a", now + timedelta(seconds=3))
    except TaskClaimLost:
        pass
    else:
        raise AssertionError("stale worker was allowed to begin dispatch")
    current_b = store.begin_dispatch(claimed_b.run_id, "worker-b", now + timedelta(seconds=3))
    race_event = DurableTaskDispatcher.event_for(race_task, current_b)
    journal.append(race_event)
    store.mark_dispatched(
        current_b.run_id,
        worker_id="worker-b",
        source_event_id=race_event.event_id,
        outcome={},
        now=now + timedelta(seconds=3),
    )
    cancel_task = service.create(
        household_id=household_id,
        task_type=TaskType.REASONING_DUE,
        title="Cancellation race",
        payload={"objective": "cancellation"},
        schedule=TaskSchedule(ScheduleKind.INTERVAL, "UTC", now, interval_seconds=60),
        creation_idempotency_key=f"cancel-race-{uuid4()}",
        now=now,
    )
    cancel_claim = store.claim_due(now, "cancel-worker", 30, 1)[0]
    service.cancel(cancel_task.task_id, now=now)
    assert store.get_run(cancel_claim.run_id).status.value == "CANCELLED"
    try:
        store.begin_dispatch(cancel_claim.run_id, "cancel-worker", now)
    except TaskClaimLost:
        pass
    else:
        raise AssertionError("cancelled run remained dispatchable")
    assert not [
        run
        for run in store.list_runs(cancel_task.task_id)
        if run.status.value in {"PENDING", "CLAIMED", "DISPATCHING"}
    ]
    print("lifecycle_parity=PASS")
    print("stale_worker_rejected=PASS")
    print("cancellation_before_dispatch=PASS")
    run_agent_and_scheduled_cognition(service, store, journal)
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
