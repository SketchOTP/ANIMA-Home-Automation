"""Synthetic learning outcomes; isolated stores, never an owner trial."""

from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, cast
from uuid import UUID, uuid4

import pytest
from test_household_learning import (
    NOW,
    structured_proposal,
)
from test_household_learning import (
    fixture as fixture,
)
from test_preferences import context

from anima_ha.household_learning import (
    HOUSEHOLD_LEARNING_MANIFEST,
    REVIEW_COMPLETION_KIND,
    REVIEW_PACKET_KIND,
    HouseholdLearningError,
    HouseholdLearningNativePlugin,
    learning_request_scope,
)
from anima_ha.household_shadow import score_window
from anima_ha.knowledge import KnowledgeConfig, KnowledgeNativePlugin
from anima_ha.memory import MemoryType, ProvenanceKind
from anima_ha.policy import RequestOrigin


def materialize(fixture: Any) -> tuple[Any, Any, Any, dict[str, Any], dict[str, Any]]:
    service, graph, memory, evidence = fixture
    graph.resources_in_place = lambda _: []
    for day in range(8):
        evidence.add(day, event_type="senseguard.opened")
    home, request = graph.household.canonical_id, uuid4()
    packet = service.create_review_packet(
        home, request, review_kind="ROUTINE", source_event_id=evidence.rows[0]["event_id"]
    )
    candidate = packet["candidates"][0]
    with learning_request_scope(request, home, candidate["source_event_ids"], [candidate]):
        result = service.propose(
            home,
            None,
            structured_proposal(candidate),
            request,
            invocation_context=context(home, graph.owner.canonical_id),
        )
    return service, graph, memory, packet, result["suggestion"]


@pytest.mark.parametrize(
    "lifecycle", ["FAILED", "UNKNOWN_RESULT", "RECOVERY_REQUIRED", "PROVIDER_RUNNING"]
)
def test_materialization_does_not_prove_success(fixture: Any, lifecycle: str) -> None:
    service, graph, memory, packet, _ = materialize(fixture)
    service.request_state_reader = lambda *_: {
        "lifecycle": lifecycle,
        "result_status": None,
        "provider_invocation_started": True,
    }
    service.reconcile_reviews(graph.household.canonical_id)
    state = service.review_state(graph.household.canonical_id, packet)
    assert state["candidate_materialized"] and not state["terminal_success"]
    assert service.status(graph.household.canonical_id)["learning"]["review_count"] == 0
    assert any(
        row.metadata.get("terminal_success") is True for row in memory.records.values()
    )  # history preserved


def test_chronology_and_counts_over_fifty(fixture: Any) -> None:
    service, graph, _, _ = fixture
    home = graph.household.canonical_id
    service.evidence_reader = lambda *_a, **_kw: {
        "status": "SUCCEEDED",
        "items": [],
        "truncated": False,
    }
    for index in range(62):
        service.clock = lambda index=index: NOW + timedelta(seconds=index)
        service.create_review_packet(
            home, uuid4(), review_kind="DAILY", source_event_id=str(uuid4())
        )
    status = service.status(home)["learning"]
    assert (
        status["packet_count"] == status["review_count"] == status["completion_record_count"] == 62
    )
    assert datetime.fromisoformat(status["last_review"]["completed_at"]) == NOW + timedelta(
        seconds=61
    )
    first = service._records(home, REVIEW_PACKET_KIND, limit=20)
    second = service._records(home, REVIEW_PACKET_KIND, limit=20, cursor=first[-1].memory_id)
    assert first[-1].created_at < second[0].created_at
    with pytest.raises(HouseholdLearningError):
        service._records(home, REVIEW_COMPLETION_KIND, limit=20, cursor=first[-1].memory_id)


def test_owner_correction_and_retraction_propagate(fixture: Any) -> None:
    service, graph, memory, _, suggestion = materialize(fixture)
    home, owner = graph.household.canonical_id, graph.owner.canonical_id
    corrected = service.review(
        home,
        owner,
        {
            "suggestion_id": suggestion["suggestion_id"],
            "decision": "CORRECTED",
            "content": "Owner correction, not an executable rule.",
        },
        uuid4(),
    )["suggestion"]
    row = memory.get(UUID(corrected["suggestion_id"]))
    assert (
        row.memory_type == MemoryType.EXPLICIT_FACT
        and row.provenance.kind == ProvenanceKind.EXPLICIT_INPUT
    )
    assert corrected["classification"] == "OWNER_CORRECTION" and corrected["authority"] == "NONE"
    with pytest.raises(HouseholdLearningError, match="version changed"):
        service.review(
            home,
            owner,
            {"suggestion_id": suggestion["suggestion_id"], "decision": "ACKNOWLEDGED"},
            uuid4(),
        )
    assert (
        service.review(
            home,
            owner,
            {"suggestion_id": corrected["suggestion_id"], "decision": "RETRACTED"},
            uuid4(),
        )["suggestion"]["learned_routine"]
        is None
    )


def test_projection_failure_is_durable_and_retry_has_no_model(fixture: Any) -> None:
    service, graph, memory, _, suggestion = materialize(fixture)
    row = memory.get(UUID(suggestion["suggestion_id"]))

    class Notes:
        fails = True
        calls = 0

        def invoke_with_invocation_context(self, *_: Any) -> dict[str, Any]:
            self.calls += 1
            if self.fails:
                raise OSError("no raw error detail may escape")
            return {"note": {"note_id": str(uuid4()), "digest": "f" * 64}}

    notes = Notes()
    service.knowledge_plugin = notes
    metadata = {
        **row.metadata,
        "projection_candidate": {
            "candidate_key": "fixture",
            "title": "Fixture",
            "maturity_evidence": {},
        },
        "projection_status": "PENDING",
    }
    # Test-only qualified Memory setup, never owner state.
    row = replace(row, memory_id=uuid4(), metadata=metadata)
    memory.create(row)
    failed = service._sync_projection(row)
    assert failed.metadata["projection_status"] == "FAILED" and notes.calls == 1
    assert "raw error" not in str(failed.metadata)
    assert service._sync_projection(failed) == failed and notes.calls == 1
    notes.fails = False
    service.clock = lambda: NOW + timedelta(minutes=2)
    synced = service._sync_projection(failed)
    assert synced.metadata["projection_status"] == "SYNCHRONIZED" and notes.calls == 2
    assert service._sync_projection(synced) == synced and notes.calls == 2


def test_new_review_same_concept_uses_distinct_note_update_not_idempotency_collision(
    fixture: Any,
    tmp_path: Path,
) -> None:
    service, graph, _, evidence = fixture
    root = tmp_path / "ANIMA"
    root.mkdir(mode=0o700)
    service.knowledge_plugin = KnowledgeNativePlugin(KnowledgeConfig(root))
    _, _, _, _, first = materialize(fixture)
    request = uuid4()
    packet = service.create_review_packet(
        graph.household.canonical_id,
        request,
        review_kind="ROUTINE",
        source_event_id=evidence.rows[0]["event_id"],
    )
    candidate = packet["candidates"][0]
    with learning_request_scope(
        request, graph.household.canonical_id, candidate["source_event_ids"], [candidate]
    ):
        second = service.propose(
            graph.household.canonical_id,
            None,
            structured_proposal(candidate),
            request,
            invocation_context=context(graph.household.canonical_id, graph.owner.canonical_id),
        )["suggestion"]
    assert first["projection_status"] == second["projection_status"] == "SYNCHRONIZED"
    assert first["knowledge_note"]["note_id"] == second["knowledge_note"]["note_id"]
    assert first["knowledge_note"]["digest"] != second["knowledge_note"]["digest"]


def freeze(service: Any, graph: Any, suggestion: dict[str, Any]) -> dict[str, Any]:
    ref = suggestion["source_refs"][0]
    return cast(
        dict[str, Any],
        service.freeze_shadow(
            graph.household.canonical_id,
            graph.owner.canonical_id,
            {
                "suggestion_id": suggestion["suggestion_id"],
                "canonical_id": ref["canonical_id"],
                "event_type": ref["event_type"],
                "predicts_occurrence": True,
                "starts_at": (NOW + timedelta(minutes=1)).isoformat(),
                "window_seconds": 300,
                "window_count": 2,
            },
            uuid4(),
        )["evaluation"],
    )


def test_future_windows_restart_no_fake_accuracy_and_feedback(fixture: Any) -> None:
    service, graph, memory, _, suggestion = materialize(fixture)
    frozen = freeze(service, graph, suggestion)
    assert frozen["disposition"] == "EVIDENCE_PENDING" and frozen["planned_opportunities"] == 2
    service.evaluate_shadows(graph.household.canonical_id)
    assert not service.evaluations(graph.household.canonical_id)["items"][0]["windows"]
    service.evidence_reader = lambda *_a, **_kw: {
        "status": "SUCCEEDED",
        "items": [],
        "truncated": False,
    }
    service.clock = lambda: NOW + timedelta(minutes=13)
    service.evaluate_shadows(graph.household.canonical_id)
    closed = service.evaluations(graph.household.canonical_id)["items"][0]
    assert (
        closed["unknown_opportunities"] == 2
        and closed["covered_opportunities"] == closed["misses"] == 0
    )
    count = len(memory.records)
    service.evaluate_shadows(graph.household.canonical_id)
    assert len(memory.records) == count
    assert (
        frozen["prediction"] == closed["prediction"] and frozen["frozen_at"] == closed["frozen_at"]
    )
    service.review(
        graph.household.canonical_id,
        graph.owner.canonical_id,
        {"suggestion_id": suggestion["suggestion_id"], "decision": "RETRACTED"},
        uuid4(),
    )
    assert (
        service.evaluations(graph.household.canonical_id)["items"][0]["disposition"]
        == "SUPERSEDED_HYPOTHESIS"
    )


def test_shadow_invalidation_does_not_rewrite_frozen_hypothesis(fixture: Any) -> None:
    service, graph, _, _, suggestion = materialize(fixture)
    frozen = freeze(service, graph, suggestion)
    service.review(
        graph.household.canonical_id,
        graph.owner.canonical_id,
        {"suggestion_id": suggestion["suggestion_id"], "decision": "DISMISSED"},
        uuid4(),
    )
    value = service.evaluations(graph.household.canonical_id)["items"][0]
    assert (
        value["disposition"] == "SUPERSEDED_HYPOTHESIS"
        and value["hypothesis_version"] == frozen["hypothesis_version"]
    )


def test_scoring_coverage_misses_baseline_duplicates_and_late_records() -> None:
    start, end = NOW + timedelta(seconds=1), NOW + timedelta(minutes=6)
    coverage = {
        "status": "COMPLETE",
        "basis": "QUALIFIED_SOURCE_INTERVAL",
        "start": start.isoformat(),
        "end": end.isoformat(),
    }
    arguments: dict[str, Any] = dict(
        start=start,
        end=end,
        frozen_at=NOW,
        closed_at=end + timedelta(minutes=1),
        event_type="senseguard.opened",
        canonical_id=str(uuid4()),
        predicts_occurrence=True,
        coverage=coverage,
        truncated=False,
    )
    empty = score_window(**arguments, events=[])
    assert empty["miss"] is True and empty["baseline_correct"] is True
    event = {
        "event_id": str(uuid4()),
        "canonical_id": arguments["canonical_id"],
        "event_type": arguments["event_type"],
        "occurred_at": start.isoformat(),
        "recorded_at": start.isoformat(),
    }
    seen = score_window(**arguments, events=[event, event])
    assert (
        seen["prediction_correct"] is True
        and seen["observed_receipt_count"] == 1
        and seen["physical_occurrence_at"] is None
    )
    late = score_window(
        **arguments, events=[{**event, "recorded_at": (end + timedelta(minutes=2)).isoformat()}]
    )
    assert late["unknown"] and late["prediction_correct"] is None


def test_qualified_positive_receipt_is_evaluable_without_invented_negative_coverage() -> None:
    resource = str(uuid4())
    start, end = NOW + timedelta(minutes=1), NOW + timedelta(minutes=6)
    event = {
        "event_id": str(uuid4()),
        "event_type": "household.ring.motion",
        "canonical_id": resource,
        "occurred_at": start.isoformat(),
        "recorded_at": start.isoformat(),
    }
    arguments: dict[str, Any] = dict(
        start=start,
        end=end,
        frozen_at=NOW,
        closed_at=end + timedelta(minutes=1),
        event_type="household.ring.motion",
        canonical_id=resource,
        coverage={"status": "UNKNOWN"},
        truncated=False,
    )
    positive = score_window(**arguments, predicts_occurrence=True, events=[event, event])
    assert positive["prediction_correct"] is True and positive["baseline_correct"] is False
    assert positive["coverage"] == "UNKNOWN" and positive["unknown"] is False
    assert positive["physical_occurrence_at"] is None
    assert positive["observed_receipt_count"] == 1
    unpredicted = score_window(**arguments, predicts_occurrence=False, events=[event])
    assert unpredicted["miss"] is True and unpredicted["miss_kind"] == "UNPREDICTED_SOURCE_RECEIPT"
    quiet = score_window(**arguments, predicts_occurrence=False, events=[])
    assert quiet["unknown"] and quiet["baseline_correct"] is None


def test_shadow_writer_is_direct_owner_only(fixture: Any) -> None:
    service, graph, _, _, suggestion = materialize(fixture)
    plugin = HouseholdLearningNativePlugin(service)
    ctx = context(graph.household.canonical_id, graph.owner.canonical_id)
    tool = next(
        item for item in HOUSEHOLD_LEARNING_MANIFEST.tools if item["name"] == "freeze_shadow"
    )
    assert not tool["read_only"] and tool["semantic_action"] == "capabilities.configure"
    with pytest.raises(HouseholdLearningError, match="direct commissioned"):
        plugin.invoke_with_invocation_context(
            "freeze_shadow",
            {
                "suggestion_id": suggestion["suggestion_id"],
                "canonical_id": suggestion["source_refs"][0]["canonical_id"],
                "event_type": "senseguard.opened",
                "predicts_occurrence": True,
                "starts_at": (NOW + timedelta(minutes=1)).isoformat(),
                "window_seconds": 300,
                "window_count": 1,
            },
            1,
            replace(ctx, origin=RequestOrigin.AUTONOMOUS_AGENT),
        )
