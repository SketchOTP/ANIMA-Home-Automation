"""Synthetic-only qualification; no owner notes, model runs or production state."""

from __future__ import annotations

import json
import os
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID, uuid4

import psycopg
import pytest
from psycopg.errors import UniqueViolation
from test_family_routines import Graph, Memory
from test_preferences import context

from anima_ha.events import EventEnvelope
from anima_ha.household_event_context import HouseholdEventEvidence
from anima_ha.household_learning import (
    CONFIG_KIND,
    EVENT_TYPES,
    HOUSEHOLD_LEARNING_MANIFEST,
    HouseholdLearningError,
    HouseholdLearningNativePlugin,
    HouseholdLearningService,
    InitiativeConfig,
    learning_request_scope,
)
from anima_ha.intelligence import (
    IntelligenceLifecycle,
    IntelligenceOrigin,
    IntelligenceRequestFactory,
    PostgresIntelligenceStore,
)
from anima_ha.journal import PostgresEventJournal
from anima_ha.memory import MemoryRecord, MemoryService, MemoryStatus, MemoryType
from anima_ha.plugins import NativeRuntime, PluginManager, PluginValidationError
from anima_ha.policy import (
    AutonomyPolicy,
    OpaPolicyClient,
    PolicyService,
    PostgresPolicyStore,
    RequestOrigin,
)
from anima_ha.sentry_boundary import CoreSentryBoundary, SentryBoundaryError
from anima_ha.tasks import (
    DurableTaskDispatcher,
    InMemoryTaskStore,
    PostgresTaskStore,
    ScheduleKind,
    TaskSchedule,
    TaskService,
    TaskStatus,
    TaskType,
)

NOW = datetime(2026, 9, 7, 12, tzinfo=UTC)


class LearningMemory(Memory):
    def execute(self, sql: str, parameters: dict[str, Any]) -> None:
        assert "m.metadata->>'record_kind' = %(kind)s" in sql
        assert "ORDER BY m.memory_id ASC LIMIT" in sql
        self.parameters = parameters

    def fetchall(self) -> list[MemoryRecord]:
        p = self.parameters
        return sorted(
            [
                row
                for row in self.records.values()
                if row.household_id == p["household_id"]
                and row.status == MemoryStatus.ACTIVE
                and row.metadata.get("record_kind") == p["kind"]
                and (p["after"] is None or row.memory_id > p["after"])
                and (row.expires_at is None or row.expires_at > p["now"])
            ],
            key=lambda row: row.memory_id,
        )[: p["limit"]]

    def create(self, memory: MemoryRecord) -> MemoryRecord:
        if memory.memory_id in self.records:
            raise UniqueViolation("synthetic duplicate")
        return super().create(memory)


class Evidence:
    def __init__(self, graph: Graph) -> None:
        self.hh = graph.household.canonical_id
        self.canonical = graph.person.canonical_id
        self.rows: list[dict[str, Any]] = []
        self.truncated = False

    def add(self, days_ago: float, **kwargs: Any) -> str:
        stamp = NOW - timedelta(days=days_ago)
        row = {
            "event_id": str(uuid4()),
            "event_type": EVENT_TYPES[2],
            "occurred_at": stamp.isoformat(),
            "recorded_at": stamp.isoformat(),
            "canonical_id": str(self.canonical),
            **kwargs,
        }
        self.rows.append(row)
        return str(row["event_id"])

    def __call__(self, hh: UUID, **kwargs: Any) -> dict[str, Any]:
        assert hh == self.hh
        assert kwargs["since"] == NOW - timedelta(days=28)
        return {
            "status": "SUCCEEDED",
            "items": self.rows[: kwargs["limit"]],
            "truncated": self.truncated or len(self.rows) > kwargs["limit"],
        }


@pytest.fixture
def fixture() -> tuple[HouseholdLearningService, Graph, LearningMemory, Evidence]:
    graph, memory = Graph(), LearningMemory()
    evidence = Evidence(graph)
    service = HouseholdLearningService(
        memory,
        graph,
        evidence_read=evidence,
        task_service=TaskService(InMemoryTaskStore()),
        timezone="America/New_York",
        clock=lambda: NOW,
    )
    return service, graph, memory, evidence


def config(**changes: Any) -> dict[str, Any]:
    return {**InitiativeConfig().to_payload(), "expected_version": None, **changes}


def proposal(ids: list[str], **changes: Any) -> dict[str, Any]:
    return {
        "kind": "PATTERN",
        "content": "Synthetic reviewable observation, not a routine.",
        "confidence": 0.4,
        "event_ids": ids,
        **changes,
    }


def test_defaults_and_status_never_create_memory_or_tasks(fixture: Any) -> None:
    service, graph, memory, _ = fixture
    result = service.status(graph.household.canonical_id)
    assert result["config"] == InitiativeConfig().to_payload()
    assert result["config_version"] is None and not result["readiness"]["ready"]
    assert not result["proactive_eligible"]
    assert result["scheduling"]["status"] == "NOT_SCHEDULED"
    assert service.ensure_review_tasks(graph.household.canonical_id)["reason"] == "CONFIG_NOT_SAVED"
    assert not memory.records and not service.task_service.store.tasks


@pytest.mark.parametrize(
    "field,value",
    [
        ("learning_days", 2),
        ("learning_days", 15),
        ("learning_days", True),
        ("routine_review_days", 1),
        ("routine_review_days", 15),
        ("proactive_enabled", 1),
        ("daily_review_enabled", "true"),
        ("always_notify", ["*"]),
        ("always_notify", [EVENT_TYPES[0], EVENT_TYPES[0]]),
        ("always_notify", "senseguard.event"),
    ],
)
def test_config_bounds(field: str, value: Any) -> None:
    with pytest.raises(HouseholdLearningError):
        InitiativeConfig(**{field: value})


def test_owner_config_versions_and_no_op(fixture: Any) -> None:
    service, graph, memory, _ = fixture
    hh, owner = graph.household.canonical_id, graph.owner.canonical_id
    with pytest.raises(HouseholdLearningError):
        service.configure(hh, graph.person.canonical_id, config())
    first = service.configure(hh, owner, config(always_notify=[EVENT_TYPES[0]]))
    version = first["config_version"]
    assert len(memory.records) == 1
    retry = service.configure(
        hh, owner, config(expected_version=version, always_notify=[EVENT_TYPES[0]])
    )
    assert retry["config_version"] == version and len(memory.records) == 1
    second = service.configure(hh, owner, config(expected_version=version, proactive_enabled=True))
    assert second["config_version"] != version and not second["proactive_eligible"]
    assert memory.get(UUID(version)).status == MemoryStatus.SUPERSEDED
    with pytest.raises(HouseholdLearningError, match="version changed"):
        service.configure(hh, owner, config(expected_version=version))
    with pytest.raises(HouseholdLearningError):
        service.configure(hh, owner, {**config(), "scope": "owner"})


@pytest.mark.parametrize(
    "offsets,expected",
    [([], False), ([20], False), ([3, 3, 3], False), ([3, 2, 1], False), ([3, 2, 0], True)],
)
def test_readiness_distinct_observed_dates_and_span(
    fixture: Any, offsets: list[int], expected: bool
) -> None:
    service, graph, _, evidence = fixture
    for offset in offsets:
        evidence.add(offset)
    value = service.status(graph.household.canonical_id)
    assert value["readiness"]["ready"] is expected
    assert not value["proactive_eligible"]  # Timing never enables owner's switch.


def test_timezone_fallback_future_old_invalid_and_duplicate_evidence(fixture: Any) -> None:
    service, graph, _, evidence = fixture
    event = evidence.add(3)
    evidence.add(2, source_event_id=event)
    evidence.add(0, source_event_id=event)
    evidence.add(-1)
    evidence.add(29)
    evidence.add(0, event_type="external.product", raw_secret="NEVER_PROJECT")
    value = service.status(graph.household.canonical_id)
    assert value["readiness"]["observed_local_days"] == 1
    assert not value["readiness"]["ready"]
    assert "NEVER_PROJECT" not in json.dumps(service.evidence(graph.household.canonical_id))


def test_local_midnight_and_dst_do_not_count_utc_dates_as_local_days(fixture: Any) -> None:
    service, graph, _, evidence = fixture
    for hour in (1, 4):
        stamp = datetime(2026, 9, 7, hour, tzinfo=UTC).isoformat()
        evidence.add(0, occurred_at=stamp, recorded_at=stamp)
    value = service.status(graph.household.canonical_id)["readiness"]
    assert value["observed_local_days"] == 2  # 21:00 Sep6 and 00:00 Sep7 EDT.
    service.clock = lambda: datetime(2026, 11, 1, 9, tzinfo=UTC)
    service.evidence_reader = lambda *args, **kwargs: {
        "status": "SUCCEEDED",
        "truncated": False,
        "items": [
            {
                "event_id": str(uuid4()),
                "event_type": EVENT_TYPES[2],
                "canonical_id": str(graph.person.canonical_id),
                "occurred_at": f"2026-11-01T0{hour}:30:00+00:00",
                "recorded_at": f"2026-11-01T0{hour}:30:00+00:00",
            }
            for hour in (5, 6)
        ],
    }
    value = service.status(graph.household.canonical_id)["readiness"]
    assert value["observed_local_days"] == 1 and value["elapsed_seconds"] == 3600


def test_proactive_requires_switch_and_sample_readiness(fixture: Any) -> None:
    service, graph, _, evidence = fixture
    for offset in (3, 2, 0):
        evidence.add(offset)
    evidence.truncated = True
    value = service.configure(
        graph.household.canonical_id,
        graph.owner.canonical_id,
        config(proactive_enabled=True, always_notify=[EVENT_TYPES[0]]),
    )
    assert value["proactive_eligible"]
    assert value["readiness"]["truncated"]
    assert value["readiness"]["coverage"].startswith("BOUNDED_OBSERVATIONS")
    assert value["config"]["always_notify"] == [EVENT_TYPES[0]]


def test_unavailable_evidence_not_false_success(fixture: Any) -> None:
    service, graph, _, _ = fixture

    def unavailable(*args: Any, **kwargs: Any) -> Any:
        raise RuntimeError("SYNTHETIC_PRIVATE_ERROR")

    service.evidence_reader = unavailable
    value = service.status(graph.household.canonical_id)
    assert value["readiness"]["evidence_status"] == "UNAVAILABLE"
    assert not value["proactive_eligible"] and "SYNTHETIC_PRIVATE_ERROR" not in json.dumps(value)


def test_historical_batch_received_today_does_not_qualify_learning(fixture: Any) -> None:
    service, graph, _, evidence = fixture
    for day in (5, 4, 0):
        evidence.add(day, recorded_at=NOW.isoformat())
    result = service.status(graph.household.canonical_id)["readiness"]
    assert result["observed_local_days"] == 3 and result["elapsed_seconds"] >= 3 * 86400
    assert result["received_local_days"] == 1 and result["received_elapsed_seconds"] == 0
    assert not result["ready"]


def test_worker_projection_never_calls_event_reader(fixture: Any) -> None:
    service, graph, memory, _ = fixture

    def forbidden(*args: Any, **kwargs: Any) -> Any:
        pytest.fail("worker scheduling scope must not read event history")

    service.evidence_reader = forbidden
    scope = service.review_task_scope(graph.household.canonical_id)
    assert scope["config_version"] is None and not memory.records


def test_suggestion_pages_are_scoped_and_bounded(fixture: Any) -> None:
    service, graph, _, evidence = fixture
    hh, event = graph.household.canonical_id, evidence.add(0)
    for _ in range(3):
        request_id = uuid4()
        with learning_request_scope(request_id, hh, [event]):
            service.propose(hh, None, proposal([event]), request_id)
    page = service.suggestions(hh, limit=2)
    second = service.suggestions(hh, limit=2, cursor=page["next_cursor"])
    assert len(page["items"]) == 2 and len(second["items"]) == 1
    assert second["next_cursor"] is None
    assert {item["suggestion_id"] for item in page["items"]}.isdisjoint(
        item["suggestion_id"] for item in second["items"]
    )
    with pytest.raises(ValueError):
        service.suggestions(uuid4())
    with pytest.raises(HouseholdLearningError):
        service.suggestions(hh, limit=21)


def test_status_cannot_use_forged_or_duplicate_config_records(fixture: Any) -> None:
    service, graph, memory, _ = fixture
    hh = graph.household.canonical_id
    service.configure(hh, graph.owner.canonical_id, config())
    row = next(iter(memory.records.values()))
    memory.records[row.memory_id] = replace(row, memory_type=MemoryType.INFERRED_PATTERN)
    with pytest.raises(HouseholdLearningError):
        service.status(hh)
    memory.records[row.memory_id] = row
    other = replace(row, memory_id=uuid4())
    memory.records[other.memory_id] = other
    with pytest.raises(HouseholdLearningError, match="multiple active"):
        service.status(hh)


def test_proposal_requires_real_bound_request_and_scoped_journal(fixture: Any) -> None:
    service, graph, memory, evidence = fixture
    hh, request_id = graph.household.canonical_id, uuid4()
    event = evidence.add(0)
    with pytest.raises(HouseholdLearningError, match="binding unavailable"):
        service.propose(hh, None, proposal([event]), request_id)
    with learning_request_scope(request_id, hh, [event]):
        result = service.propose(hh, None, proposal([event]), request_id)
        assert result == service.propose(hh, None, proposal([event]), request_id)
        with pytest.raises(HouseholdLearningError):
            service.propose(hh, None, proposal([str(uuid4())]), request_id)
        with pytest.raises(HouseholdLearningError, match="scope mismatch"):
            service.propose(hh, None, proposal([event]), uuid4())
        with pytest.raises(HouseholdLearningError):
            service.propose(
                hh, None, proposal([event], content="Changed same invocation"), request_id
            )
    assert len(memory.records) == 1
    saved = next(iter(memory.records.values()))
    assert saved.memory_type == MemoryType.INFERRED_PATTERN
    assert saved.provenance.source_ref == f"anima:request:{request_id}"
    assert saved.provenance.source_event_id == event
    assert result["suggestion"]["evidence_status"] == "JOURNAL_LINKED_NOT_VERIFIED_TRUTH"


@pytest.mark.parametrize(
    "changes",
    [
        {"confidence": True},
        {"confidence": float("nan")},
        {"confidence": 0.9},
        {"kind": "EXPLICIT_FACT"},
        {"code": "do something"},
        {"content": "x" * 1001},
        {"event_ids": []},
        {"authority": "owner"},
        {"source_refs": []},
    ],
)
def test_proposal_bounds(fixture: Any, changes: dict[str, Any]) -> None:
    service, graph, memory, evidence = fixture
    event, request_id = evidence.add(0), uuid4()
    with learning_request_scope(request_id, graph.household.canonical_id, [event]):
        with pytest.raises(HouseholdLearningError):
            service.propose(
                graph.household.canonical_id, None, proposal([event], **changes), request_id
            )
    assert not memory.records


def test_review_versions_only_acknowledges_no_owner_routine(fixture: Any) -> None:
    service, graph, memory, evidence = fixture
    hh, event, request_id = graph.household.canonical_id, evidence.add(0), uuid4()
    with learning_request_scope(request_id, hh, [event]):
        saved = service.propose(hh, None, proposal([event], kind="LESSON"), request_id)[
            "suggestion"
        ]
    payload = {"suggestion_id": saved["suggestion_id"], "decision": "ACKNOWLEDGED"}
    review_id = uuid4()
    with pytest.raises(HouseholdLearningError):
        service.review(hh, graph.person.canonical_id, payload, review_id)
    reviewed = service.review(hh, graph.owner.canonical_id, payload, review_id)
    assert reviewed == service.review(hh, graph.owner.canonical_id, payload, review_id)
    assert reviewed["suggestion"]["classification"] == "INFERRED"
    assert reviewed["suggestion"]["review_status"] == "ACKNOWLEDGED"
    assert reviewed["suggestion"]["source_refs"] == saved["source_refs"]
    assert all(row.memory_type == MemoryType.AGENT_LESSON for row in memory.records.values())
    assert len(service.suggestions(hh)["items"]) == 1


def test_native_schema_blocks_extra_scope_and_owner_mutations(fixture: Any) -> None:
    service, graph, _, evidence = fixture
    plugin = HouseholdLearningNativePlugin(service)
    hh, event, request_id = graph.household.canonical_id, evidence.add(0), uuid4()
    ctx = context(hh, graph.owner.canonical_id)
    with pytest.raises(PluginValidationError):
        plugin.invoke("get_status", {}, 1)
    with pytest.raises(PluginValidationError):
        plugin.invoke_with_invocation_context("get_status", {"household_id": str(uuid4())}, 1, ctx)
    with pytest.raises(HouseholdLearningError):
        plugin.invoke_with_invocation_context(
            "configure", config(), 1, replace(ctx, origin=RequestOrigin.AUTONOMOUS_AGENT)
        )
    with pytest.raises(HouseholdLearningError):
        plugin.invoke_with_invocation_context("propose", proposal([event]), 1, ctx)
    with learning_request_scope(request_id, hh, [event]):
        one = plugin.invoke_with_invocation_context("propose", proposal([event]), 1, ctx)
        two = plugin.invoke_with_invocation_context(
            "propose", proposal([event]), 1, replace(ctx, tool_request_id=uuid4())
        )
    assert one["suggestion"]["suggestion_id"] != two["suggestion"]["suggestion_id"]
    assert len(plugin.list_tools()) == 6
    assert not any(
        tool["read_only"]
        for tool in HOUSEHOLD_LEARNING_MANIFEST.tools
        if tool["name"] in {"configure", "propose", "review"}
    )


def test_context_scope_does_not_leak_to_other_thread_or_after_exception(fixture: Any) -> None:
    service, graph, _, evidence = fixture
    hh, event, request_id = graph.household.canonical_id, evidence.add(0), uuid4()
    with learning_request_scope(request_id, hh, [event]):
        with ThreadPoolExecutor(max_workers=1) as pool:
            call = pool.submit(service.propose, hh, None, proposal([event]), request_id)
            with pytest.raises(HouseholdLearningError):
                call.result()
        with pytest.raises(RuntimeError), learning_request_scope(uuid4(), hh, []):
            raise RuntimeError("synthetic")
        service.propose(hh, None, proposal([event]), request_id)
    with pytest.raises(HouseholdLearningError):
        service.propose(hh, None, proposal([event]), request_id)


def test_review_tasks_reconcile_only_owned_versioned_keys(fixture: Any) -> None:
    service, graph, _, _ = fixture
    hh, owner = graph.household.canonical_id, graph.owner.canonical_id
    other = service.task_service.create(
        household_id=hh,
        task_type=TaskType.REASONING_DUE,
        title="Unrelated synthetic task",
        payload={"objective": "Unrelated"},
        schedule=TaskSchedule(ScheduleKind.ONCE, "UTC", NOW),
        creation_idempotency_key="synthetic-unrelated",
        now=NOW,
    )
    first = service.configure(hh, owner, config())
    assert first["scheduling"]["status"] == "NOT_SCHEDULED"
    result = service.ensure_review_tasks(hh)
    assert result["status"] == "SCHEDULED" and len(result["tasks"]) == 2
    assert result["execution_status"] == "NOT_OBSERVED"
    assert service.ensure_review_tasks(hh) == result
    tasks = [service.task_service.get(UUID(row["task_id"])) for row in result["tasks"]]
    assert {task.schedule.interval_seconds for task in tasks} == {86400, 259200}
    assert all(task.payload["objective"] for task in tasks)
    service.configure(
        hh,
        owner,
        config(
            expected_version=first["config_version"],
            daily_review_enabled=False,
            routine_review_enabled=False,
        ),
    )
    assert service.ensure_review_tasks(hh)["status"] == "NOT_SCHEDULED"
    assert all(
        service.task_service.get(task.task_id).status == TaskStatus.CANCELLED for task in tasks
    )
    assert service.task_service.get(other.task_id).status == TaskStatus.ACTIVE


def test_actual_task_dispatch_emits_review_objective_without_claiming_model_execution(
    fixture: Any,
) -> None:
    service, graph, _, _ = fixture
    hh = graph.household.canonical_id
    service.configure(hh, graph.owner.canonical_id, config())
    service.ensure_review_tasks(hh)
    events: list[Any] = []

    class Sink:
        def append(self, event: Any) -> None:
            events.append(event)

    result = DurableTaskDispatcher(
        service.task_service.store, Sink(), worker_id="synthetic"
    ).run_once(now=NOW + timedelta(days=1), limit=2)
    assert result.dispatched == 1
    assert events[0].event_type == "scheduled_reasoning_due"
    assert events[0].payload["objective"].startswith("Read bounded household evidence")
    assert service.status(hh)["scheduling"]["execution_status"] == "NOT_OBSERVED"


def test_real_pg_config_initial_uniqueness_cas_restart_and_journal_scope() -> None:
    url = os.environ.get("ANIMA_FAMILY_ROUTINES_TEST_DATABASE_URL")
    if not url:
        pytest.skip("requires explicitly isolated ANIMA_FAMILY_ROUTINES_TEST_DATABASE_URL")
    with psycopg.connect(url) as connection:
        assert connection.execute("SELECT current_database()").fetchone() == (
            "anima_family_routines_test",
        )
    # Existing migrated fixture only. No migrations or owner resources.
    graph, memory = Graph(), MemoryService(url)
    graph.resources_in_place = lambda _: []  # type: ignore[attr-defined]
    hh, owner = graph.household.canonical_id, graph.owner.canonical_id
    journal = PostgresEventJournal(url)
    for days in (3, 2, 0):
        journal.append(
            EventEnvelope.create(
                event_id=str(uuid4()),
                event_type=EVENT_TYPES[2],
                source="anima.household_presence",
                subject_key=f"household/{hh}",
                occurred_at=NOW - timedelta(days=days),
                recorded_at=NOW,
                payload={
                    "household_id": str(hh),
                    "person_id": str(graph.person.canonical_id),
                    "transition": "RECONNECTED",
                    "is_authentication": False,
                    "private_raw": "NEVER_PROJECT_SYNTHETIC",
                },
                metadata={"household_id": str(hh)},
            )
        )
    reader = HouseholdEventEvidence(url, graph)
    service = HouseholdLearningService(
        memory,
        graph,
        evidence_reader=lambda hh, **kwargs: reader.recent_household_evidence(
            hh, now=NOW, **kwargs
        ),
        task_service=TaskService(PostgresTaskStore(url)),
        clock=lambda: NOW,
    )

    def save(payload: dict[str, Any]) -> Any:
        try:
            return service.configure(hh, owner, payload)
        except (HouseholdLearningError, ValueError):
            return None

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(save, [config(learning_days=3), config(learning_days=4)]))
    assert sum(item is not None for item in results) == 1
    first = next(item for item in results if item is not None)
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(
            pool.map(
                save,
                [
                    config(expected_version=first["config_version"], learning_days=5),
                    config(expected_version=first["config_version"], learning_days=6),
                ],
            )
        )
    assert sum(item is not None for item in results) == 1
    with memory._connect() as connection:
        rows = connection.execute(
            "SELECT * FROM anima_memory_records WHERE household_id=%s AND status='ACTIVE' "
            "AND metadata->>'record_kind'=%s",
            (hh, CONFIG_KIND),
        ).fetchall()
    assert len(rows) == 1
    reloaded = HouseholdLearningService(MemoryService(url), graph, clock=lambda: NOW)
    assert reloaded.status(hh)["config_version"] == service.status(hh)["config_version"]
    page = service.evidence(hh)
    assert len(page["items"]) == 3 and "NEVER_PROJECT_SYNTHETIC" not in json.dumps(page)
    request_id, event_id = uuid4(), page["items"][0]["event_id"]
    with learning_request_scope(request_id, hh, [event_id]):
        saved = service.propose(hh, None, proposal([event_id]), request_id)["suggestion"]
    assert saved in service.suggestions(hh)["items"]
    assert (
        reader.recent_household_evidence(uuid4(), since=NOW - timedelta(days=28), now=NOW)["items"]
        == []
    )
    scheduled = service.ensure_review_tasks(hh)
    assert scheduled["status"] == "SCHEDULED" and service.ensure_review_tasks(hh) == scheduled


def test_core_frozen_request_real_opa_proposal_to_real_pg_without_owner_authority() -> None:
    url = os.environ.get("ANIMA_FAMILY_ROUTINES_TEST_DATABASE_URL")
    opa = os.environ.get("ANIMA_FAMILY_ROUTINES_TEST_OPA_URL")
    if not url or not opa:
        pytest.skip("requires isolated routines PostgreSQL and real OPA")
    with psycopg.connect(url) as connection:
        assert connection.execute("SELECT current_database()").fetchone() == (
            "anima_family_routines_test",
        )
    graph, memory = Graph(), MemoryService(url)
    graph.resources_in_place = lambda _: []  # type: ignore[attr-defined]
    hh, event_id = graph.household.canonical_id, str(uuid4())
    PostgresEventJournal(url).append(
        EventEnvelope.create(
            event_id=event_id,
            event_type="household.presence.connection_changed",
            source="anima.household_presence",
            subject_key=f"household/{hh}",
            occurred_at=NOW,
            recorded_at=NOW,
            metadata={"household_id": str(hh)},
            payload={
                "household_id": str(hh),
                "person_id": str(graph.person.canonical_id),
                "transition": "RECONNECTED",
                "is_authentication": False,
                "raw": "SYNTHETIC_PROVIDER_PAYLOAD_NOT_FOR_MODEL",
            },
        )
    )
    reader = HouseholdEventEvidence(url, graph)
    learning = HouseholdLearningService(
        memory,
        graph,
        evidence_reader=lambda household, **kwargs: reader.recent_household_evidence(
            household, now=NOW, **kwargs
        ),
        clock=lambda: NOW,
    )
    manager = PluginManager()
    manager.register(
        HOUSEHOLD_LEARNING_MANIFEST, NativeRuntime(HouseholdLearningNativePlugin(learning))
    )
    manager.enable(HOUSEHOLD_LEARNING_MANIFEST.plugin_id)
    store = PostgresIntelligenceStore(url)
    audit = PostgresPolicyStore(url)
    boundary = CoreSentryBoundary(
        manager,
        PolicyService(OpaPolicyClient(opa), audit_store=audit),
        store,
        agent_memory_enabled=True,
        learning_service=learning,
    )

    def active_request(*, known_owner: bool = False) -> Any:
        pending = IntelligenceRequestFactory.for_direct_sentry_interaction(
            sentry_request_id=str(uuid4()),
            household_id=hh,
            source_surface="synthetic-learning-qualification",
            user_text="Synthetic bounded learning review",
            tools=manager.list_tools(),
            service_client_id="synthetic-learning-client",
        )
        if known_owner:
            pending = replace(
                pending,
                origin=IntelligenceOrigin.AUTONOMOUS_ATTENTION,
                principal_id=graph.owner.canonical_id,
            )
        store.enqueue(pending)
        claimed = store.claim_specific(
            pending.request_id,
            "synthetic-learning-worker",
            household_id=hh,
            provider_id="sentry",
        )
        assert claimed is not None and claimed.claim_owner is not None
        assert boundary.start_provider(claimed, claimed.claim_owner)
        request = store.get(pending.request_id)
        assert request is not None and request.lifecycle == IntelligenceLifecycle.PROVIDER_RUNNING
        assert request.catalogue == pending.catalogue
        return request

    request = active_request()
    tool_id = "anima.household-learning.propose"
    arguments = proposal([event_id], content="SYNTHETIC_PROPOSAL_NOT_POLICY_INPUT")
    # No manually injected learning_request_scope: Core must establish it.
    result = boundary.invoke_tool(request, tool_id, arguments)
    assert result["status"] == "SUCCEEDED", result
    assert boundary.invoke_tool(request, tool_id, arguments) == result
    suggestion = result["result"]["suggestion"]
    saved = memory.get(UUID(suggestion["suggestion_id"]))
    assert saved is not None and saved.household_id == hh
    assert saved.memory_type == MemoryType.INFERRED_PATTERN
    assert saved.provenance.source_ref == f"anima:request:{request.request_id}"
    assert saved.provenance.source_event_id == event_id
    assert saved.metadata["review_status"] == "PENDING"
    assert "SYNTHETIC_PROVIDER_PAYLOAD_NOT_FOR_MODEL" not in json.dumps(result)

    with psycopg.connect(url) as connection:
        decisions = connection.execute(
            "SELECT decision,reason_code,principal_id,input_snapshot FROM anima_policy_decisions "
            "WHERE household_id=%s ORDER BY evaluated_at",
            (hh,),
        ).fetchall()
    assert len(decisions) == 2
    for decision, reason, principal, snapshot in decisions:
        assert decision == "ALLOW" and reason == "EXPLICIT_ANIMA_SECURE_AUTONOMY"
        assert principal is None and snapshot["identity"]["principal_id"] is None
        assert snapshot["origin"] == "AUTONOMOUS_AGENT"
        assert snapshot["identity"]["assurance"] not in {"AUTHENTICATED", "STRONG_AUTHENTICATED"}
        assert snapshot["identity"]["evidence_ids"] == [] and snapshot["policy"]["role"] is None
    assert arguments["content"] not in json.dumps(decisions, default=str)

    # Missing/request-foreign refs cannot produce a second suggestion.
    rejected = boundary.invoke_tool(request, tool_id, proposal([str(uuid4())]), ordinal=2)
    assert rejected["status"] != "SUCCEEDED"
    with pytest.raises(SentryBoundaryError, match="TOOL_NOT_BOUND_TO_REQUEST"):
        boundary.invoke_tool(request, "anima.household-learning.not-frozen", {})
    boundary.agent_memory_enabled = False
    assert boundary.invoke_tool(request, tool_id, arguments, ordinal=3) == {
        "status": "DENIED",
        "operation": tool_id,
        "reason": "AGENT_LEARNING_NOT_ENABLED",
    }
    boundary.agent_memory_enabled = True
    boundary.learning_service = None
    assert boundary.invoke_tool(request, tool_id, arguments, ordinal=3)["status"] == "DENIED"
    boundary.learning_service = learning
    plugin = manager.plugins[HOUSEHOLD_LEARNING_MANIFEST.plugin_id]
    plugin.manifest = replace(plugin.manifest, source="builtin:synthetic-wrong-source")
    with pytest.raises(SentryBoundaryError, match="AGENT_LEARNING_SOURCE_INVALID"):
        boundary.invoke_tool(request, tool_id, arguments, ordinal=3)
    plugin.manifest = HOUSEHOLD_LEARNING_MANIFEST
    boundary.policy_service = PolicyService(
        OpaPolicyClient(opa),
        autonomy=AutonomyPolicy(security_secure_action=False),
        audit_store=audit,
    )
    assert boundary.invoke_tool(request, tool_id, arguments, ordinal=3)["status"] == "DENIED"
    boundary.policy_service = PolicyService(OpaPolicyClient(opa), audit_store=audit)

    # The deployment grant never grants owner config rights. Even an autonomous
    # request carrying a known owner's canonical ID fails the native direct-user guard.
    blocked = boundary.invoke_tool(
        request, "anima.household-learning.configure", config(), ordinal=4
    )
    assert blocked["status"] != "SUCCEEDED"
    owner_request = active_request(known_owner=True)
    blocked_owner = boundary.invoke_tool(
        owner_request,
        "anima.household-learning.configure",
        config(),
        ordinal=1,
    )
    assert blocked_owner["status"] != "SUCCEEDED"
    assert learning.status(hh)["config_version"] is None
    assert len(learning.suggestions(hh)["items"]) == 1
    with psycopg.connect(url) as connection:
        assert connection.execute(
            "SELECT count(*) FROM anima_identity_evidence WHERE household_id=%s",
            (hh,),
        ).fetchone() == (0,)
        assert connection.execute(
            "SELECT count(*) FROM anima_memory_records WHERE household_id=%s",
            (hh,),
        ).fetchone() == (1,)
