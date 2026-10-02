"""Isolated existing PostgreSQL/current OPA; no owner trials or model calls."""

from __future__ import annotations

import os
import time
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any
from uuid import UUID, uuid4

import psycopg
import pytest
from test_household_learning import structured_proposal
from test_stage2_delivery_postgres import isolated_url as isolated_url
from test_stage3_household_situation import active_boundary
from test_stage3_household_situation import situation as situation

from anima_ha.context import PostgresContextSource
from anima_ha.events import DeliveryClass, EventEnvelope
from anima_ha.household_learning import (
    HOUSEHOLD_LEARNING_MANIFEST,
    HouseholdLearningNativePlugin,
    HouseholdLearningService,
)
from anima_ha.intelligence import (
    IntelligenceResult,
    IntelligenceResultStatus,
    PostgresIntelligenceStore,
)
from anima_ha.knowledge import KnowledgeConfig, KnowledgeNativePlugin
from anima_ha.memory import MemoryService, MemoryStatus
from anima_ha.plugins import InvocationContext, NativeRuntime, PluginManager
from anima_ha.policy import (
    Assurance,
    EvidenceType,
    IdentityEvidence,
    OpaPolicyClient,
    PolicyService,
    PostgresPolicyStore,
    RequestOrigin,
)
from anima_ha.ui_api import UIIdentity
from anima_ha.ui_runtime import CoreUICommandGateway


def prepared(value: dict[str, Any]) -> tuple[Any, Any, dict[str, Any]]:
    now = datetime.now(UTC)
    for index in range(8):
        value["journal"].append(
            EventEnvelope.create(
                event_id=str(uuid4()),
                delivery_class=DeliveryClass.GUARANTEED,
                event_type="household.ring.motion",
                source="anima.ring",
                source_event_id=str(uuid4()),
                subject_key=f"resource/{value['sensor']}",
                occurred_at=now - timedelta(days=index),
                payload={"resource_id": str(value["sensor"])},
                metadata={"household_id": str(value["home"])},
            )
        )
    service = value["service"]
    service.request_state_reader = PostgresIntelligenceStore(value["url"]).learning_state
    boundary, request = active_boundary(value)
    packet = service.create_review_packet(
        value["home"], request.request_id, review_kind="ROUTINE", source_event_id=str(uuid4())
    )
    assert len(packet["candidates"]) == 1
    response = boundary.invoke_tool(
        request, "anima.household-learning.propose", structured_proposal(packet["candidates"][0])
    )
    assert response["status"] == "SUCCEEDED", response
    return boundary, request, response["result"]["suggestion"]


def finish(boundary: Any, request: Any, status: IntelligenceResultStatus) -> None:
    recorded, _, _ = boundary.finalize_result(
        request, request.claim_owner, IntelligenceResult(request.request_id, status)
    )
    assert recorded


def retrieved(value: dict[str, Any]) -> tuple[set[str], set[str]]:
    memory = MemoryService(value["url"])
    direct = {
        str(row.memory.memory_id)
        for row in memory.retrieve("", household_id=value["home"], top_k=100)
    }
    context = {
        str(row["memory_id"])
        for row in PostgresContextSource(value["url"]).memories(
            value["home"], [], "", now=datetime.now(UTC), limit=100
        )
    }
    return direct, context


def owner_gateway(value: dict[str, Any]) -> tuple[Any, UIIdentity, dict[str, Any]]:
    opa = os.environ.get("ANIMA_STAGE3_TEST_OPA_URL")
    if not opa:
        pytest.skip("requires explicit stateless current OPA")
    manager = PluginManager()
    manager.register(
        HOUSEHOLD_LEARNING_MANIFEST, NativeRuntime(HouseholdLearningNativePlugin(value["service"]))
    )
    manager.enable(HOUSEHOLD_LEARNING_MANIFEST.plugin_id)
    role: dict[str, Any] = {"value": "owner"}
    gateway = CoreUICommandGateway(
        manager,
        PolicyService(OpaPolicyClient(opa), audit_store=PostgresPolicyStore(value["url"])),
        policy_role_resolver=lambda _: role["value"],
    )
    now = datetime.now(UTC)
    evidence = IdentityEvidence(
        uuid4(),
        value["home"],
        value["owner"],
        EvidenceType.AUTHENTICATED_SESSION,
        "isolated-stage4",
        now,
        now,
        now + timedelta(minutes=5),
        Assurance.AUTHENTICATED,
        70,
        "ISOLATED_NOT_OWNER_AUTH",
    )
    return gateway, UIIdentity(value["home"], value["owner"], "isolated", evidence), role


@pytest.mark.parametrize(
    "status",
    [
        IntelligenceResultStatus.FAILED,
        IntelligenceResultStatus.UNKNOWN_RESULT,
        IntelligenceResultStatus.NO_ACTION,
    ],
)
def test_actual_terminal_lifecycle_controls_retrieval_and_restart(
    situation: dict[str, Any],
    status: IntelligenceResultStatus,
) -> None:
    boundary, request, suggestion = prepared(situation)
    identifier = suggestion["suggestion_id"]
    assert all(identifier not in rows for rows in retrieved(situation))
    assert situation["service"].status(situation["home"])["learning"]["review_count"] == 0
    finish(boundary, request, status)
    success = status == IntelligenceResultStatus.NO_ACTION
    assert all((identifier in rows) == success for rows in retrieved(situation))
    store = PostgresIntelligenceStore(situation["url"])
    reloaded = HouseholdLearningService(
        MemoryService(situation["url"]),
        situation["graph"],
        evidence_reader=situation["service"].evidence_reader,
        request_state_reader=store.learning_state,
    )
    reloaded.reconcile_reviews(situation["home"])
    report = reloaded.status(situation["home"])["learning"]
    assert report["review_count"] == int(success)
    assert report["failed_review_count"] == int(not success)
    assert (
        store.claim_specific(
            request.request_id, "no-replay", household_id=situation["home"], provider_id="sentry"
        )
        is None
    )
    assert store.learning_state(situation["foreign"], request.request_id) == {}


def test_owner_correction_retraction_current_opa_and_cross_household(
    situation: dict[str, Any],
) -> None:
    boundary, request, suggestion = prepared(situation)
    finish(boundary, request, IntelligenceResultStatus.FAILED)
    gateway, identity, role = owner_gateway(situation)
    payload = {
        "suggestion_id": suggestion["suggestion_id"],
        "decision": "CORRECTED",
        "content": "Explicit isolated owner correction outranks failed inference.",
    }
    response = gateway.learning_operation(identity, "review", payload)
    assert response["status"] == "SUCCEEDED", response
    corrected = response["result"]["suggestion"]["suggestion_id"]
    assert all(corrected in rows for rows in retrieved(situation))
    row = MemoryService(situation["url"]).get(UUID(corrected))
    assert row and row.provenance.kind.value == "EXPLICIT_INPUT"
    assert gateway.learning_operation(identity, "review", payload)["status"] == "FAILED"
    role["value"] = None
    assert (
        gateway.learning_operation(
            identity, "review", {"suggestion_id": corrected, "decision": "RETRACTED"}
        )["status"]
        == "DENIED"
    )
    role["value"] = "owner"
    with pytest.raises(ValueError, match="does not belong"):
        situation["service"].review(
            situation["foreign"],
            situation["owner"],
            {"suggestion_id": corrected, "decision": "RETRACTED"},
            uuid4(),
        )
    assert (
        gateway.learning_operation(
            identity, "review", {"suggestion_id": corrected, "decision": "RETRACTED"}
        )["status"]
        == "SUCCEEDED"
    )
    assert all(corrected not in rows for rows in retrieved(situation))
    original = MemoryService(situation["url"]).get(UUID(suggestion["suggestion_id"]))
    assert original and original.status == MemoryStatus.SUPERSEDED


def test_freeze_real_current_policy_future_window_restart_feedback(
    situation: dict[str, Any],
) -> None:
    boundary, request, suggestion = prepared(situation)
    finish(boundary, request, IntelligenceResultStatus.NO_ACTION)
    gateway, identity, role = owner_gateway(situation)
    now = datetime.now(UTC)
    payload = {
        "suggestion_id": suggestion["suggestion_id"],
        "canonical_id": str(situation["sensor"]),
        "event_type": "household.ring.motion",
        "starts_at": (now + timedelta(minutes=1)).isoformat(),
        "window_seconds": 300,
        "window_count": 2,
        "predicts_occurrence": True,
    }
    role["value"] = None
    assert gateway.learning_operation(identity, "freeze_shadow", payload)["status"] == "DENIED"
    role["value"] = "owner"
    assert (
        gateway.learning_operation(
            identity, "freeze_shadow", {**payload, "canonical_id": str(situation["other_sensor"])}
        )["status"]
        == "FAILED"
    )
    frozen = gateway.learning_operation(identity, "freeze_shadow", payload)
    assert frozen["status"] == "SUCCEEDED", frozen
    evaluation = frozen["result"]["evaluation"]
    service = HouseholdLearningService(
        MemoryService(situation["url"]),
        situation["graph"],
        evidence_reader=situation["service"].evidence_reader,
        request_state_reader=PostgresIntelligenceStore(situation["url"]).learning_state,
        clock=lambda: now + timedelta(minutes=15),
    )
    service.evaluate_shadows(situation["home"])
    closed = service.evaluations(situation["home"])["items"][0]
    assert closed["closed_opportunities"] == closed["unknown_opportunities"] == 2
    assert closed["misses"] == closed["prediction_correct"] == closed["baseline_correct"] == 0
    assert closed["prediction"] == evaluation["prediction"]
    with psycopg.connect(situation["url"]) as conn:
        count_row = conn.execute(
            "SELECT count(*) FROM anima_memory_records WHERE household_id=%s", (situation["home"],)
        ).fetchone()
        assert count_row
        count = count_row[0]
    service.evaluate_shadows(situation["home"])
    with psycopg.connect(situation["url"]) as conn:
        checked = conn.execute(
            "SELECT count(*) FROM anima_memory_records WHERE household_id=%s",
            (situation["home"],),
        ).fetchone()
        assert checked and checked[0] == count
    assert (
        gateway.learning_operation(
            identity,
            "review",
            {"suggestion_id": suggestion["suggestion_id"], "decision": "DISMISSED"},
        )["status"]
        == "SUCCEEDED"
    )
    assert (
        service.evaluations(situation["home"])["items"][0]["disposition"] == "SUPERSEDED_HYPOTHESIS"
    )
    assert service.evaluations(situation["foreign"])["items"] == []


@pytest.mark.parametrize(
    "terminal", [IntelligenceResultStatus.NO_ACTION, IntelligenceResultStatus.FAILED]
)
def test_real_note_projection_owner_correction_and_retraction(
    situation: dict[str, Any],
    tmp_path: Path,
    terminal: IntelligenceResultStatus,
) -> None:
    root = tmp_path / "ANIMA"
    root.mkdir(mode=0o700)
    notes = KnowledgeNativePlugin(KnowledgeConfig(root))
    situation["service"].knowledge_plugin = notes
    boundary, request, suggestion = prepared(situation)
    assert suggestion["projection_status"] == "PENDING"
    finish(boundary, request, terminal)
    situation["service"].reconcile_reviews(situation["home"])
    active = situation["service"].suggestions(situation["home"])["items"][0]
    assert active["projection_status"] == (
        "SYNCHRONIZED" if terminal == IntelligenceResultStatus.NO_ACTION else "PENDING"
    )
    ctx = InvocationContext(
        situation["home"],
        situation["owner"],
        uuid4(),
        uuid4(),
        1,
        "isolated-note-read",
        RequestOrigin.DIRECT_USER,
    )
    before = (
        notes.invoke_with_invocation_context(
            "get_note", {"note_id": active["knowledge_note"]["note_id"]}, 10, ctx
        )
        if active["knowledge_note"]
        else None
    )
    gateway, identity, _ = owner_gateway(situation)
    corrected = gateway.learning_operation(
        identity,
        "review",
        {
            "suggestion_id": active["suggestion_id"],
            "decision": "CORRECTED",
            "content": "Owner-specific isolated correction; not a policy or action.",
        },
    )
    assert corrected["status"] == "SUCCEEDED", corrected
    changed = corrected["result"]["suggestion"]
    assert changed["projection_status"] == "SYNCHRONIZED"
    note = changed["knowledge_note"]
    situation["service"].reconcile_reviews(situation["home"])
    changed = situation["service"].suggestions(situation["home"])["items"][0]
    after = notes.invoke_with_invocation_context("get_note", {"note_id": note["note_id"]}, 10, ctx)
    assert after["note"]["enabled"] is True
    assert before is None or after["note"]["digest"] != before["note"]["digest"]
    assert after["note"]["classification"] == "USER_STATED"
    assert "Owner-specific isolated correction" in after["note"]["body"]
    acknowledged = gateway.learning_operation(
        identity, "review", {"suggestion_id": changed["suggestion_id"], "decision": "ACKNOWLEDGED"}
    )
    assert acknowledged["status"] == "SUCCEEDED", acknowledged
    changed = acknowledged["result"]["suggestion"]
    situation["service"].reconcile_reviews(situation["home"])
    changed = situation["service"].suggestions(situation["home"])["items"][0]
    assert all(changed["suggestion_id"] in rows for rows in retrieved(situation))
    assert (
        notes.invoke_with_invocation_context("get_note", {"note_id": note["note_id"]}, 10, ctx)[
            "note"
        ]["enabled"]
        is True
    )
    retracted = gateway.learning_operation(
        identity, "review", {"suggestion_id": changed["suggestion_id"], "decision": "RETRACTED"}
    )
    assert retracted["status"] == "SUCCEEDED", retracted
    final = notes.invoke_with_invocation_context("get_note", {"note_id": note["note_id"]}, 10, ctx)
    assert final["note"]["enabled"] is False
    assert final["note"]["digest"] != after["note"]["digest"]
    search = notes.invoke_with_invocation_context("search_notes", {"query": "isolated"}, 10, ctx)
    assert search["items"] == []


@pytest.mark.parametrize("prediction", [True, False])
def test_production_reader_positive_without_coverage_callback_and_unknown_quiet_window(
    situation: dict[str, Any],
    prediction: bool,
) -> None:
    boundary, request, suggestion = prepared(situation)
    finish(boundary, request, IntelligenceResultStatus.NO_ACTION)
    service = situation["service"]
    assert service.coverage_reader is None
    now = datetime.now(UTC)
    starts = now + timedelta(seconds=1)
    frozen = service.freeze_shadow(
        situation["home"],
        situation["owner"],
        {
            "suggestion_id": suggestion["suggestion_id"],
            "canonical_id": str(situation["sensor"]),
            "event_type": "household.ring.motion",
            "predicts_occurrence": prediction,
            "starts_at": starts.isoformat(),
            "window_seconds": 300,
            "window_count": 2,
        },
        uuid4(),
    )["evaluation"]
    # An actual fixture receipt is appended AFTER the future hypothesis was
    # frozen. Only closure time is simulated; this is not a household trial.
    time.sleep(1.05)
    situation["journal"].append(
        EventEnvelope.create(
            event_id=str(uuid4()),
            delivery_class=DeliveryClass.GUARANTEED,
            event_type="household.ring.motion",
            source="anima.ring",
            source_event_id=str(uuid4()),
            subject_key=f"resource/{situation['sensor']}",
            occurred_at=datetime.now(UTC),
            payload={"resource_id": str(situation["sensor"])},
            metadata={"household_id": str(situation["home"])},
        )
    )
    service.clock = lambda: now + timedelta(minutes=15)
    service.evaluate_shadows(situation["home"])
    result = service.evaluations(situation["home"])["items"][0]
    assert result["observed_positive_opportunities"] == result["known_opportunities"] == 1
    assert result["covered_opportunities"] == 0 and result["unknown_opportunities"] == 1
    assert result["prediction_correct"] == int(prediction)
    assert result["misses"] == int(not prediction) and result["baseline_correct"] == 0
    assert result["windows"][0]["physical_occurrence_at"] is None
    assert result["prediction"] == frozen["prediction"]
    assert result["windows"][1]["observed_occurrence"] is None
