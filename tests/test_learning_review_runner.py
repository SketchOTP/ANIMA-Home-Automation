"""Scoped queue/Attention qualification on the existing disposable PostgreSQL.

Synthetic households only; no production migration, provider/model invocation,
unscoped SQL updates, or claims against unrelated fixture tasks.
"""

from __future__ import annotations

import os
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from typing import Any
from uuid import UUID, uuid4

import psycopg
import pytest
from test_family_routines import Graph

from anima_ha.attention import AttentionProfile, PostgresAttentionService
from anima_ha.context import ContextBroker
from anima_ha.events import DeliveryClass, EventEnvelope
from anima_ha.household_learning import HouseholdLearningService, InitiativeConfig
from anima_ha.intelligence import IntelligenceProviderMode, PostgresIntelligenceStore
from anima_ha.journal import PostgresEventJournal
from anima_ha.learning_review_runner import LearningReviewRunner
from anima_ha.memory import MemoryService
from anima_ha.sentry_autowake import PostgresAutoWakeClaims
from anima_ha.tasks import (
    DurableTask,
    InMemoryTaskStore,
    PostgresTaskStore,
    ScheduleKind,
    TaskRunStatus,
    TaskSchedule,
    TaskService,
    TaskType,
    TaskValidationError,
)

BASE = datetime.now(UTC) - timedelta(days=4)
NOW = BASE + timedelta(days=4)


@pytest.fixture
def database_url() -> str:
    url = os.environ.get("ANIMA_FAMILY_ROUTINES_TEST_DATABASE_URL")
    if not url:
        pytest.skip("requires existing disposable ANIMA_FAMILY_ROUTINES_TEST_DATABASE_URL")
    with psycopg.connect(url) as conn:
        assert conn.execute("SELECT current_database()").fetchone() == (
            "anima_family_routines_test",
        )
    return url


def create_task(store: Any, household: UUID, *, at: datetime = BASE) -> DurableTask:
    return TaskService(store).create(
        household_id=household,
        task_type=TaskType.REASONING_DUE,
        title="Synthetic unrelated task",
        payload={"objective": "Synthetic only"},
        schedule=TaskSchedule(ScheduleKind.ONCE, "UTC", at),
        creation_idempotency_key=str(uuid4()),
        now=BASE,
    )


def scoped(base: Any, household: UUID, ids: tuple[UUID, ...]) -> Any:
    if isinstance(base, PostgresTaskStore):
        return PostgresTaskStore(
            base.database_url, claim_household_id=household, claim_task_ids=ids
        )
    result = InMemoryTaskStore(claim_household_id=household, claim_task_ids=ids)
    result.tasks, result.runs, result.by_creation_key, result._lock = (
        base.tasks,
        base.runs,
        base.by_creation_key,
        base._lock,
    )
    return result


@pytest.fixture(params=["memory", "postgres"])
def store(request: pytest.FixtureRequest) -> Any:
    return (
        InMemoryTaskStore()
        if request.param == "memory"
        else PostgresTaskStore(request.getfixturevalue("database_url"))
    )


def test_claim_scope_never_advances_unrelated_same_or_foreign_household(store: Any) -> None:
    hh, other = uuid4(), uuid4()
    selected, unrelated, foreign = [create_task(store, owner) for owner in (hh, hh, other)]
    before = [(store.get(t.task_id), store.list_runs(t.task_id)) for t in (unrelated, foreign)]
    target = scoped(store, hh, (selected.task_id, foreign.task_id))
    runs = target.claim_due(NOW, "synthetic-selected", 30, 2)
    assert [run.task_id for run in runs] == [selected.task_id]
    assert [
        (store.get(t.task_id), store.list_runs(t.task_id)) for t in (unrelated, foreign)
    ] == before


@pytest.mark.parametrize("pending", [False, True])
def test_reclaim_and_pending_claim_stay_inside_exact_ids(store: Any, pending: bool) -> None:
    hh = uuid4()
    selected, unrelated, foreign = [create_task(store, owner) for owner in (hh, hh, uuid4())]
    runs = {}
    for task in (selected, unrelated, foreign):
        seed = scoped(store, task.household_id, (task.task_id,))
        runs[task.task_id] = seed.claim_due(BASE, "synthetic-original", 10, 1)[0]
        if pending:
            assert seed.reclaim_expired(NOW) == 1
    before = [(store.get(t.task_id), store.list_runs(t.task_id)) for t in (unrelated, foreign)]
    target = scoped(store, hh, (selected.task_id,))
    assert target.reclaim_expired(NOW) == (0 if pending else 1)
    claimed = target.claim_due(NOW, "synthetic-recovery", 30, 2)
    assert [run.run_id for run in claimed] == [runs[selected.task_id].run_id]
    assert [
        (store.get(t.task_id), store.list_runs(t.task_id)) for t in (unrelated, foreign)
    ] == before


def test_empty_scope_is_noop_not_global(store: Any) -> None:
    hh = uuid4()
    task = create_task(store, hh)
    before = store.get(task.task_id)
    target = scoped(store, hh, ())
    assert target.reclaim_expired(NOW) == 0
    assert target.claim_due(NOW, "synthetic-empty", 30, 2) == []
    assert store.get(task.task_id) == before
    assert store.list_runs(task.task_id) == []


@pytest.mark.parametrize(
    "kwargs",
    [
        {"claim_household_id": uuid4()},
        {"claim_task_ids": ()},
        {"claim_household_id": uuid4(), "claim_task_ids": [uuid4()]},
        {"claim_household_id": uuid4(), "claim_task_ids": (uuid4(), uuid4(), uuid4())},
        {"claim_household_id": UUID(int=0), "claim_task_ids": ()},
    ],
)
def test_invalid_scope_fails_before_database_access(kwargs: dict[str, Any]) -> None:
    with pytest.raises(TaskValidationError):
        PostgresTaskStore("not-a-connection", **kwargs)
    with pytest.raises(TaskValidationError):
        InMemoryTaskStore(**kwargs)


@pytest.fixture
def harness(database_url: str) -> Any:
    graph = Graph()
    hh = graph.household.canonical_id
    tasks = PostgresTaskStore(database_url)
    journal = PostgresEventJournal(database_url)
    learning = HouseholdLearningService(
        MemoryService(database_url),
        graph,
        task_service=TaskService(tasks),
        timezone="America/New_York",
        clock=lambda: BASE,
    )
    core = SimpleNamespace(
        journal=journal,
        attention=PostgresAttentionService(database_url),
        context=ContextBroker(database_url),
        intelligence_store=PostgresIntelligenceStore(database_url),
        intelligence_provider=IntelligenceProviderMode.SENTRY,
        plugins=SimpleNamespace(list_tools=lambda: []),
        agent=SimpleNamespace(run=lambda *a, **k: pytest.fail("embedded cognition forbidden")),
    )
    return SimpleNamespace(
        learning=learning,
        core=core,
        tasks=tasks,
        hh=hh,
        owner=graph.owner.canonical_id,
        url=database_url,
        runner=LearningReviewRunner(core, learning, hh),
    )


def configure(h: Any, **changes: Any) -> dict[str, Any]:
    result: dict[str, Any] = h.learning.configure(
        h.hh, h.owner, {**InitiativeConfig().to_payload(), "expected_version": None, **changes}
    )
    return result


def request_rows(h: Any) -> list[Any]:
    with psycopg.connect(h.url) as conn:
        return conn.execute(
            """SELECT request_id, causation_id, provider_id, household_id, lifecycle
            FROM anima_intelligence_requests WHERE household_id=%s ORDER BY request_id""",
            (h.hh,),
        ).fetchall()


def test_runner_is_inert_until_saved_config_and_explicit_reconciliation(harness: Any) -> None:
    h = harness
    unrelated = create_task(h.tasks, h.hh)
    assert h.runner._thread is None
    assert h.runner.run_once(now=NOW)["status"] == "IDLE"
    configure(h)
    assert h.runner.run_once(now=NOW)["status"] == "IDLE"
    assert h.tasks.get(unrelated.task_id) == unrelated
    assert h.tasks.list_runs(unrelated.task_id) == []
    assert request_rows(h) == []


def test_real_pg_exact_events_no_backlog_and_no_repeat_dispatch(harness: Any) -> None:
    h = harness
    configure(h)
    scheduled = h.learning.ensure_review_tasks(h.hh)
    selected = [UUID(row["task_id"]) for row in scheduled["tasks"]]
    unrelated = create_task(h.tasks, h.hh)
    foreign = create_task(h.tasks, uuid4())
    prior = []
    for _ in range(8):
        event = EventEnvelope.create(
            event_id=str(uuid4()),
            event_type="plugin.healthy",
            source="synthetic",
            subject_key="synthetic",
            occurred_at=BASE,
            payload={},
            delivery_class=DeliveryClass.GUARANTEED,
            metadata={"household_id": str(h.hh)},
        )
        prior.append(h.core.journal.append(event).journal_position)
    profile = AttentionProfile(f"synthetic-backlog:{h.hh}", ())
    consumer = f"synthetic-backlog:{h.hh}"
    h.core.attention.prime_consumer_before(profile, consumer, prior[0] - 1)
    h.core.attention.process(profile, consumer_name=consumer, limit=8)
    cursor = h.core.attention.cursor(consumer)
    first = h.runner.run_once(now=NOW)
    assert first == {
        "status": "DISPATCHED",
        "claimed": 2,
        "dispatched": 2,
        "failed": 0,
        "error_category": None,
        "review_execution": "NOT_OBSERVED",
    }
    assert h.core.attention.cursor(consumer) == cursor
    rows = request_rows(h)
    assert len(rows) == 2
    run_events = {h.tasks.list_runs(task_id)[0].source_event_id for task_id in selected}
    assert {row[1] for row in rows} == run_events
    assert all(row[2:] == ("sentry", h.hh, "PENDING") for row in rows)
    assert all(
        h.tasks.list_runs(task_id)[0].status == TaskRunStatus.COMPLETED for task_id in selected
    )
    assert h.runner.run_once(now=NOW)["claimed"] == 0
    fresh = LearningReviewRunner(h.core, h.learning, h.hh)
    assert fresh.run_once(now=NOW)["claimed"] == 0
    assert request_rows(h) == rows
    assert h.tasks.get(unrelated.task_id) == unrelated
    assert h.tasks.get(foreign.task_id) == foreign
    assert h.tasks.list_runs(unrelated.task_id) == h.tasks.list_runs(foreign.task_id) == []


def test_current_config_disabled_or_changed_cannot_consume_old_tasks(harness: Any) -> None:
    h = harness
    saved = configure(h)
    ids = [UUID(item["task_id"]) for item in h.learning.ensure_review_tasks(h.hh)["tasks"]]
    before = [h.tasks.get(task_id) for task_id in ids]
    # Do not reconcile yet: stale ACTIVE tasks still exist but must not be claimed.
    configure(
        h,
        expected_version=saved["config_version"],
        daily_review_enabled=False,
        routine_review_enabled=False,
    )
    assert h.runner.run_once(now=NOW)["claimed"] == 0
    assert [h.tasks.get(task_id) for task_id in ids] == before
    assert not request_rows(h)


@pytest.mark.parametrize("case", ["fresh", "wrong_outcome", "wrong_source", "stale"])
def test_real_pg_review_autowake_requires_fresh_exact_completed_run(
    harness: Any, case: str
) -> None:
    h = harness
    # SQL eligibility uses real now(); leave the broad fixture's BASE unchanged.
    now = datetime.now(UTC)
    due = now - timedelta(seconds=180 if case == "stale" else 2)
    h.learning.clock = lambda: due - timedelta(days=3)
    configure(h, daily_review_enabled=False, routine_review_days=3)
    runner = LearningReviewRunner(h.core, h.learning, h.hh, reconcile=True)
    assert runner.run_once(now=now)["dispatched"] == 1
    task_id = UUID(h.learning.review_task_scope(h.hh)["scheduling"]["tasks"][0]["task_id"])
    run = h.tasks.list_runs(task_id)[0]
    rows = request_rows(h)
    assert len(rows) == 1
    request_id, event_id, provider_id, household_id, lifecycle = rows[0]
    assert (provider_id, household_id, lifecycle) == ("sentry", h.hh, "PENDING")
    assert run.status == TaskRunStatus.COMPLETED
    assert run.source_event_id == event_id
    assert run.outcome is not None and run.outcome["event_id"] == event_id
    assert run.scheduled_for == due
    with psycopg.connect(h.url) as conn:
        assert conn.execute(
            "SELECT occurred_at FROM anima_event_journal WHERE event_id=%s",
            (event_id,),
        ).fetchone() == (due,)
        # Fault injection is confined to this test's synthetic run, never Journal.
        if case == "wrong_outcome":
            conn.execute(
                "UPDATE anima_durable_task_runs SET outcome="
                "jsonb_set(outcome,'{event_id}',to_jsonb(%s::text)) WHERE run_id=%s",
                (str(uuid4()), run.run_id),
            )
        elif case == "wrong_source":
            conn.execute(
                "UPDATE anima_durable_task_runs SET source_event_id=%s WHERE run_id=%s",
                (str(uuid4()), run.run_id),
            )
    epoch = now - timedelta(minutes=10)
    claims = PostgresAutoWakeClaims(h.url, enabled_at=epoch)
    window = claims.window(
        {"origin": "AUTONOMOUS_ATTENTION", "not_before": epoch.isoformat(), "max_age_seconds": 120}
    )
    eligible = claims.eligible(h.hh, "sentry", window, limit=2)
    if case != "fresh":
        assert eligible == []
        assert claims.claim(request_id, h.hh, "sentry", "synthetic-review", window) is None
        assert request_rows(h) == rows
        return
    assert [row["request_id"] for row in eligible] == [str(request_id)]
    claimed = claims.claim(request_id, h.hh, "sentry", "synthetic-review", window)
    assert claimed is not None
    assert claimed[0].request_id == request_id
    assert claimed[0].causation_id == event_id
    assert claims.claim(request_id, h.hh, "sentry", "synthetic-review", window) is None
    assert claims.eligible(h.hh, "sentry", window, limit=2) == []
    assert runner.run_once(now=datetime.now(UTC))["claimed"] == 0
    assert len(h.tasks.list_runs(task_id)) == len(request_rows(h)) == 1


def test_scope_change_between_claim_and_append_fails_closed(
    harness: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    h = harness
    configure(h)
    h.learning.ensure_review_tasks(h.hh)
    original = h.learning.review_task_scope
    calls = 0

    def changed(hh: UUID) -> dict[str, Any]:
        nonlocal calls
        calls += 1
        result = original(hh)
        return result if calls == 1 else {**result, "config_version": None}

    monkeypatch.setattr(h.learning, "review_task_scope", changed)
    report = h.runner.run_once(now=NOW)
    assert report["failed"] == 2
    assert report["dispatched"] == 0
    assert not request_rows(h)


def test_enqueue_failure_reclaims_only_review_and_reuses_event_request_ids(
    harness: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    h = harness
    configure(h, routine_review_enabled=False)
    selected = UUID(h.learning.ensure_review_tasks(h.hh)["tasks"][0]["task_id"])
    original = h.core.intelligence_store.enqueue
    calls = []

    def fail_after_enqueue(request: Any) -> Any:
        saved = original(request)
        calls.append(saved.request_id)
        if len(calls) == 1:
            raise RuntimeError("PRIVATE_PAYLOAD_DO_NOT_LOG")
        return saved

    monkeypatch.setattr(h.core.intelligence_store, "enqueue", fail_after_enqueue)
    first = h.runner.run_once(now=NOW)
    assert first["failed"] == 1 and first["error_category"] == "SENTRY_ATTENTION_ENQUEUE_FAILED"
    assert "PRIVATE" not in str(first)
    run = h.tasks.list_runs(selected)[0]
    rows = request_rows(h)
    assert len(rows) == 1
    assert h.runner.run_once(now=NOW + timedelta(seconds=61))["dispatched"] == 1
    assert calls == [rows[0][0], rows[0][0]]
    assert request_rows(h) == rows
    assert h.tasks.get_run(run.run_id).status == TaskRunStatus.COMPLETED
    assert len(h.tasks.list_runs(selected)) == 1


def test_two_postgres_runners_do_not_double_enqueue(harness: Any) -> None:
    h = harness
    configure(h)
    h.learning.ensure_review_tasks(h.hh)
    runners = [LearningReviewRunner(h.core, h.learning, h.hh) for _ in range(2)]
    with ThreadPoolExecutor(max_workers=2) as pool:
        reports = list(pool.map(lambda runner: runner.run_once(now=NOW), runners))
    assert sum(report["dispatched"] for report in reports) == 2
    assert len(request_rows(h)) == 2


def test_no_embedded_fallback_or_exception_payload_logging(
    harness: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    h = harness
    configure(h)
    h.learning.ensure_review_tasks(h.hh)
    h.core.intelligence_provider = IntelligenceProviderMode.EMBEDDED_REFERENCE
    assert h.runner.run_once(now=NOW)["status"] == "DISABLED"
    assert not request_rows(h)
    h.core.intelligence_provider = IntelligenceProviderMode.SENTRY

    def broken(hh: UUID) -> Any:
        raise RuntimeError("PRIVATE_PAYLOAD_DO_NOT_LOG")

    monkeypatch.setattr(h.learning, "review_task_scope", broken)
    report = h.runner.run_once(now=NOW)
    assert report["error_category"] == "LEARNING_REVIEW_FAILED"
    assert "PRIVATE" not in str(report)
    assert h.runner.stop() is True


def test_opt_in_reconciliation_saved_config_restart_and_absent_noop(harness: Any) -> None:
    h = harness
    unrelated = create_task(h.tasks, h.hh)
    runner = LearningReviewRunner(h.core, h.learning, h.hh, reconcile=True)
    assert runner.run_once(now=NOW)["claimed"] == 0
    assert h.learning.review_task_scope(h.hh)["config_version"] is None
    saved = configure(h)
    assert saved["scheduling"]["status"] == "NOT_SCHEDULED"
    assert runner.run_once(now=NOW)["dispatched"] == 2
    rows = request_rows(h)
    assert len(rows) == 2
    restarted = LearningReviewRunner(h.core, h.learning, h.hh, reconcile=True)
    assert restarted.run_once(now=NOW)["claimed"] == 0
    assert request_rows(h) == rows
    assert h.tasks.get(unrelated.task_id) == unrelated
    assert h.tasks.list_runs(unrelated.task_id) == []


@pytest.mark.parametrize("case", ["foreign", "unrelated", "duplicate", "wrong_kind", "disabled"])
def test_invalid_resolved_scope_fails_before_any_claim(
    harness: Any, monkeypatch: pytest.MonkeyPatch, case: str
) -> None:
    h = harness
    configure(h)
    h.learning.ensure_review_tasks(h.hh)
    scope = h.learning.review_task_scope(h.hh)
    candidate = create_task(h.tasks, uuid4() if case == "foreign" else h.hh)
    review_ids = [UUID(item["task_id"]) for item in scope["scheduling"]["tasks"]]
    if case in {"foreign", "unrelated"}:
        scope["scheduling"]["tasks"][0]["task_id"] = str(candidate.task_id)
    elif case == "duplicate":
        scope["scheduling"]["tasks"][1] = dict(scope["scheduling"]["tasks"][0])
    elif case == "wrong_kind":
        scope["scheduling"]["tasks"][0]["kind"] = "UNRELATED"
    else:
        scope["config"]["daily_review_enabled"] = False
    before = [h.tasks.get(task_id) for task_id in [candidate.task_id, *review_ids]]
    monkeypatch.setattr(h.learning, "review_task_scope", lambda hh: scope)
    assert h.runner.run_once(now=NOW)["status"] == "FAILED"
    assert [h.tasks.get(task_id) for task_id in [candidate.task_id, *review_ids]] == before
    assert all(not h.tasks.list_runs(task_id) for task_id in [candidate.task_id, *review_ids])
    assert not request_rows(h)


def test_optional_loop_stops_and_busy_tick_does_not_claim(
    harness: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    h = harness
    assert h.runner._thread is None
    h.runner._tick_lock.acquire()
    try:
        assert h.runner.run_once()["status"] == "BUSY"
    finally:
        h.runner._tick_lock.release()
    calls = []

    def one_tick() -> dict[str, Any]:
        calls.append(True)
        h.runner._stop.set()
        report: dict[str, Any] = h.runner.last_report
        return report

    monkeypatch.setattr(h.runner, "run_once", one_tick)
    h.runner.start()
    assert h.runner.stop(timeout=2) is True
    assert calls == [True]
    assert not request_rows(h)
