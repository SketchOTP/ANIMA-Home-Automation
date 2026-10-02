"""Core-only automatic commissioning; controlled synthetic clock/evidence."""

from __future__ import annotations

from dataclasses import replace
from datetime import timedelta
from types import SimpleNamespace
from typing import Any, cast
from uuid import uuid4

import pytest
from test_household_learning import NOW, config, structured_proposal
from test_household_learning import fixture as fixture

from anima_ha.household_forecasts import recurrence_plan
from anima_ha.household_learning import CONFIG_KIND, learning_request_scope
from anima_ha.memory import MemoryStatus, ProvenanceKind
from anima_ha.tasks import DurableTaskDispatcher


def automatic(value: Any, *, lifecycle: str = "NO_ACTION") -> tuple[Any, Any, dict[str, Any]]:
    service, graph, memory, evidence = value
    graph.resources_in_place = lambda _: []
    home = graph.household.canonical_id
    for day in range(8):
        evidence.add(day, event_type="senseguard.opened")
    service.configure(home, graph.owner.canonical_id, config())
    saved = next(
        row for row in memory.records.values() if row.metadata.get("record_kind") == CONFIG_KIND
    )
    memory.records[saved.memory_id] = replace(saved, created_at=NOW - timedelta(days=4))
    service.ensure_review_tasks(home)
    store = service.task_service.store
    task = next(task for task in store.tasks.values() if task.payload["review_kind"] == "ROUTINE")
    run = store.claim_due(NOW, "synthetic-review", 30, 2)[0]
    if run.task_id != task.task_id:
        run = next(run for run in store.runs.values() if run.task_id == task.task_id)
    event = DurableTaskDispatcher.event_for(task, run)
    service.journal = SimpleNamespace(
        get=lambda identifier: event if identifier == event.event_id else None
    )
    request = uuid4()
    terminal = {
        "lifecycle": lifecycle,
        "result_status": lifecycle,
        "provider_invocation_started": True,
        "origin": "DURABLE_TASK",
        "causation_id": event.event_id,
        "provider_id": "sentry",
        "fencing_generation": 1,
        "completed_at": NOW.isoformat(),
    }
    service.request_state_reader = lambda *_: terminal
    packet = service.create_review_packet(
        home, request, review_kind="ROUTINE", source_event_id=event.event_id
    )
    assert packet["automatic_consent"]
    candidate = packet["candidates"][0]
    with learning_request_scope(request, home, candidate["source_event_ids"], [candidate]):
        service.propose(home, None, structured_proposal(candidate), request)
    service.reconcile_reviews(home)
    return service, terminal, packet


@pytest.mark.parametrize(
    "lifecycle", ["FAILED", "UNKNOWN_RESULT", "RECOVERY_REQUIRED", "PROVIDER_RUNNING"]
)
def test_nonterminal_or_failed_review_cannot_commission(fixture: Any, lifecycle: str) -> None:
    service, _, _ = automatic(fixture, lifecycle=lifecycle)
    home = fixture[1].household.canonical_id
    assert service.evaluations(home)["items"] == []
    assert (
        service.status(home)["learning"]["automatic_evaluation"]["status"]
        == "AWAITING_QUALIFIED_TERMINAL_REVIEW"
    )


def test_automatic_forecast_restart_unknown_scoring_feedback_and_correction(fixture: Any) -> None:
    service, _, packet = automatic(fixture)
    _, graph, memory, evidence = fixture
    home = graph.household.canonical_id
    initial = service.evaluations(home)["items"]
    assert len(initial) == 1
    frozen = initial[0]
    assert (
        frozen["commissioning"]["config_source_ref"]
        == f"anima:principal:{graph.owner.canonical_id}"
    )
    assert frozen["authority"] == "NONE" and frozen["planned_opportunities"] == 3
    row = memory.get(
        next(
            iter(
                memory_id
                for memory_id, row in memory.records.items()
                if row.metadata.get("evaluation_id") == frozen["evaluation_id"]
            )
        )
    )
    assert row.provenance.kind == ProvenanceKind.EVENT_JOURNAL
    assert row.provenance.source_ref == f"anima:request:{packet['request_id']}"
    for _ in range(3):
        service.reconcile_reviews(home)
    assert service.evaluations(home)["items"] == initial
    future = frozen["prediction"]["opportunities"]
    from datetime import datetime

    first = datetime.fromisoformat(future[0]["start"]) + timedelta(minutes=1)
    second_closed = datetime.fromisoformat(future[1]["end"]) + timedelta(minutes=2)
    service.clock = lambda: second_closed
    evidence.rows.extend(
        [
            {
                **evidence.rows[0],
                "event_id": str(uuid4()),
                "occurred_at": first.isoformat(),
                "recorded_at": first.isoformat(),
            },
        ]
    )
    evidence.rows.append(dict(evidence.rows[-1]))  # duplicate receipt is not another opportunity
    service.evidence_reader = lambda *_args, **_kwargs: {
        "status": "SUCCEEDED",
        "items": evidence.rows,
        "truncated": False,
    }
    service.reconcile_reviews(home)
    result = service.evaluations(home)["items"][0]
    assert (
        result["known_opportunities"],
        result["unknown_opportunities"],
        result["covered_opportunities"],
    ) == (1, 1, 0)
    assert result["prediction_correct"] == 1 and result["baseline_correct"] == 0
    suggestion = service.suggestions(home)["items"][0]
    assert suggestion["prospective_feedback"][0]["unknown_opportunities"] == 1
    assert service.prospective_feedback(home)[0]["next_comparison"] == future[2]
    service.review(
        home,
        graph.owner.canonical_id,
        {
            "suggestion_id": suggestion["suggestion_id"],
            "decision": "CORRECTED",
            "content": "Owner disputes this hypothesis.",
        },
        uuid4(),
    )
    invalid = service.evaluations(home)["items"][0]
    assert invalid["disposition"] == "SUPERSEDED_HYPOTHESIS"
    assert (
        invalid["windows"] == result["windows"]
        and invalid["hypothesis_version"] == frozen["hypothesis_version"]
    )
    corrected = service.suggestions(home)["items"][0]
    assert corrected["classification"] == "OWNER_CORRECTION"
    assert corrected["prospective_feedback"][0]["invalidation_reason"]
    assert all(
        row.status in {MemoryStatus.ACTIVE, MemoryStatus.SUPERSEDED}
        for row in memory.records.values()
    )


@pytest.mark.parametrize(
    "mutation",
    ["foreign_causation", "wrong_origin", "zero_fence", "future_terminal", "config_version"],
)
def test_binding_fail_closed_without_manual_gate_bypass(fixture: Any, mutation: str) -> None:
    service, terminal, _ = automatic(fixture, lifecycle="PROVIDER_RUNNING")
    home = fixture[1].household.canonical_id
    terminal.update(lifecycle="NO_ACTION", result_status="NO_ACTION")
    if mutation == "foreign_causation":
        terminal["causation_id"] = str(uuid4())
    if mutation == "wrong_origin":
        terminal["origin"] = "DIRECT_SENTRY_INTERACTION"
    if mutation == "zero_fence":
        terminal["fencing_generation"] = 0
    if mutation == "future_terminal":
        terminal["completed_at"] = (NOW + timedelta(days=1)).isoformat()
    if mutation == "config_version":
        current = service.status(home)["config_version"]
        service.configure(
            home,
            fixture[1].owner.canonical_id,
            {**config(proactive_enabled=True), "expected_version": current},
        )
    service.reconcile_reviews(home)
    assert service.evaluations(home)["items"] == []
    assert service.status(home)["learning"]["automatic_evaluation"]["reasons"]


def test_supported_plans_are_source_derived_not_maturity_accuracy(fixture: Any) -> None:
    service, _, packet = automatic(fixture)
    candidate = packet["candidates"][0]
    for fields, expected in [
        ({"candidate_class": "EVENT_SEQUENCE"}, "NO_QUALIFIED_FUTURE_SEQUENCE_TRIGGER"),
        (
            {"contradictory_evidence": ["conflicting qualified receipt"]},
            "CONTRADICTORY_SOURCE_EVIDENCE",
        ),
        ({"observation_count": 2}, "INSUFFICIENT_MULTI_DAY_TEMPORAL_SUPPORT"),
        ({"source_trust": "EXTERNAL_UNTRUSTED"}, "UNQUALIFIED_CANDIDATE"),
        (
            {"evidence_window": {"end": (NOW - timedelta(days=3)).isoformat()}},
            "STALE_OR_FUTURE_SOURCE_CLOCK",
        ),
    ]:
        assert recurrence_plan(
            {**candidate, **cast(dict[str, Any], fields)}, now=NOW, zone=service.zone
        ) == (
            None,
            expected,
        )


def test_revoked_config_between_precheck_and_freeze_is_not_commissioned(fixture: Any) -> None:
    service, terminal, _ = automatic(fixture, lifecycle="PROVIDER_RUNNING")
    home, owner = fixture[1].household.canonical_id, fixture[1].owner.canonical_id
    freeze = service._freeze_automatic

    def revoke_then_freeze(*args: Any) -> Any:
        current = service.status(home)["config_version"]
        service.configure(
            home,
            owner,
            {
                **config(daily_review_enabled=False, routine_review_enabled=False),
                "expected_version": current,
            },
        )
        return freeze(*args)

    service._freeze_automatic = revoke_then_freeze
    terminal.update(lifecycle="NO_ACTION", result_status="NO_ACTION")
    service.reconcile_reviews(home)
    assert service.evaluations(home)["items"] == []
