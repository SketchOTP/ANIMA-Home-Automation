"""Automatic review -> future forecast -> feedback on guarded real PG/OPA.

Only this disposable household is written. Scripted proposals do not invoke a
model/provider; no owner audit, identity, database, config or physical fixture.
"""

from __future__ import annotations

import os
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace
from typing import Any
from uuid import UUID, uuid4

import psycopg
import pytest
from test_household_learning import config, structured_proposal
from test_stage2_delivery_postgres import isolated_url as isolated_url
from test_stage3_household_situation import situation as situation
from test_stage4_learning_postgres import finish, owner_gateway, retrieved

from anima_ha.attention import PostgresAttentionService
from anima_ha.context import ContextBroker
from anima_ha.events import DeliveryClass, EventEnvelope
from anima_ha.household_learning import (
    HOUSEHOLD_LEARNING_MANIFEST,
    HouseholdLearningNativePlugin,
    HouseholdLearningService,
)
from anima_ha.intelligence import (
    IntelligenceProviderMode,
    IntelligenceResultStatus,
    PostgresIntelligenceStore,
)
from anima_ha.knowledge import KnowledgeConfig, KnowledgeNativePlugin
from anima_ha.learning_review_runner import LearningReviewRunner
from anima_ha.memory import MemoryService
from anima_ha.plugins import NativeRuntime, PluginManager
from anima_ha.policy import OpaPolicyClient, PolicyService, PostgresPolicyStore
from anima_ha.sentry_boundary import CoreSentryBoundary
from anima_ha.tasks import PostgresTaskStore, TaskService


def connect_review(value: dict[str, Any], root: Path) -> tuple[Any, Any, dict[str, Any]]:
    service, home = value["service"], value["home"]
    service.journal = value["journal"]
    now = datetime.now(UTC)
    clock = {"now": now - timedelta(days=4)}
    service.clock = lambda: clock["now"]
    service.task_service = TaskService(PostgresTaskStore(value["url"]))
    service.configure(home, value["owner"], config())
    service.ensure_review_tasks(home)
    clock["now"] = now
    for day in range(1, 9):
        stamp = now - timedelta(days=day)
        value["journal"].append(
            EventEnvelope.create(
                event_id=str(uuid4()),
                delivery_class=DeliveryClass.GUARANTEED,
                event_type="household.ring.motion",
                source="anima.ring",
                source_event_id=str(uuid4()),
                subject_key=f"resource/{value['sensor']}",
                occurred_at=stamp,
                payload={"resource_id": str(value["sensor"]), "raw_text": "PRIVATE_SENTINEL"},
                metadata={"household_id": str(home)},
            )
        )
    manager = PluginManager()
    manager.register(
        HOUSEHOLD_LEARNING_MANIFEST, NativeRuntime(HouseholdLearningNativePlugin(service))
    )
    manager.enable(HOUSEHOLD_LEARNING_MANIFEST.plugin_id)
    store = PostgresIntelligenceStore(value["url"])
    service.request_state_reader = store.learning_state
    root.mkdir(mode=0o700, parents=True, exist_ok=True)
    service.knowledge_plugin = KnowledgeNativePlugin(KnowledgeConfig(root))
    boundary = CoreSentryBoundary(
        manager,
        PolicyService(
            OpaPolicyClient(os.environ["ANIMA_STAGE3_TEST_OPA_URL"]),
            audit_store=PostgresPolicyStore(value["url"]),
        ),
        store,
        learning_service=service,
        agent_memory_enabled=True,
        access_level_resolver=lambda _: "LIMITED",
    )
    clock["now"] = datetime.now(UTC)
    core = SimpleNamespace(
        journal=value["journal"],
        attention=PostgresAttentionService(value["url"]),
        context=ContextBroker(value["url"]),
        intelligence_store=store,
        intelligence_provider=IntelligenceProviderMode.SENTRY,
        plugins=manager,
        agent=SimpleNamespace(
            run=lambda *_args, **_kwargs: pytest.fail("No embedded/model cognition")
        ),
    )
    runner = LearningReviewRunner(core, service, home)
    report = runner.run_once(now=clock["now"])
    assert report["dispatched"] == 2 and report["failed"] == 0, report
    task = next(
        task
        for task in service.task_service.store.list_tasks(home)
        if task.payload.get("review_kind") == "ROUTINE"
    )
    run = service.task_service.store.list_runs(task.task_id)[0]
    with psycopg.connect(value["url"]) as connection:
        queued = connection.execute(
            "SELECT request_id FROM anima_intelligence_requests "
            "WHERE household_id=%s AND causation_id=%s",
            (home, run.source_event_id),
        ).fetchone()
        assert queued is not None
        request_id = queued[0]
    request = store.get(request_id)
    assert request is not None and request.principal_id is None
    assert [tool["tool_id"] for tool in request.catalogue] == ["anima.household-learning.propose"]
    packet = service.review_packet(home, request.request_id)
    assert packet is not None
    assert LearningReviewRunner(core, service, home).run_once(now=clock["now"])["claimed"] == 0
    assert packet["automatic_consent"]["run_id"] == str(run.run_id)
    claimed = store.claim_specific(
        request.request_id, "stage7-scripted", household_id=home, provider_id="sentry"
    )
    assert claimed and claimed.claim_owner
    assert boundary.start_provider(claimed, claimed.claim_owner)
    active = store.get(request.request_id)
    assert active is not None
    request = active
    response = boundary.invoke_tool(
        request, "anima.household-learning.propose", structured_proposal(packet["candidates"][0])
    )
    assert response["status"] == "SUCCEEDED", response
    value.update(clock=clock, boundary=boundary, request=request, packet=packet, runner=runner)
    return boundary, request, packet


def test_connected_automatic_review_future_outcomes_correction_retrieval(
    situation: dict[str, Any], tmp_path: Path
) -> None:
    value = situation
    boundary, request, packet = connect_review(value, tmp_path / "vault")
    service, home = value["service"], value["home"]
    assert service.evaluations(home)["items"] == []
    finish(boundary, request, IntelligenceResultStatus.NO_ACTION)
    # DB terminal timestamp is actual now; move only the isolated evaluation
    # clock forward past it. We do not rewrite a provider/request receipt.
    value["clock"]["now"] = datetime.now(UTC)
    with ThreadPoolExecutor(max_workers=2) as pool:
        list(pool.map(lambda _: service.reconcile_reviews(home), range(2)))
    frozen = service.evaluations(home)["items"][0]
    restarted = HouseholdLearningService(
        MemoryService(value["url"]),
        value["graph"],
        value["journal"],
        evidence_reader=service.evidence_reader,
        task_service=service.task_service,
        knowledge_plugin=service.knowledge_plugin,
        request_state_reader=service.request_state_reader,
        timezone=service.zone.key,
        clock=service.clock,
    )
    restarted.reconcile_reviews(home)
    assert restarted.evaluations(home)["items"][0] == frozen
    assert frozen["commissioning"]["request_id"] == packet["request_id"]
    assert len(frozen["prediction"]["opportunities"]) == 3
    first, second, third = frozen["prediction"]["opportunities"]
    stamp = datetime.fromisoformat(first["start"]) + timedelta(minutes=1)
    # Journal recorded_at is a real DB receipt, not the test clock. A positive
    # future event is supplied via the existing trusted-reader test seam so
    # both occurrence AND receipt clocks are controlled, never owner rows.
    historical = service.evidence_reader
    positive = {
        "event_id": str(uuid4()),
        "event_type": "household.ring.motion",
        "canonical_id": str(value["sensor"]),
        "occurred_at": stamp.isoformat(),
        "recorded_at": stamp.isoformat(),
    }

    def evidence(hh: UUID, **kwargs: Any) -> dict[str, Any]:
        page = historical(hh, **kwargs)
        return {**page, "items": page["items"] + ([positive, dict(positive)] if hh == home else [])}

    service.evidence_reader = evidence
    value["clock"]["now"] = datetime.fromisoformat(third["end"]) + timedelta(minutes=2)
    # Only the second interval has actual qualified (synthetic) coverage. The
    # third silence remains unknown. No production coverage reader is inferred.
    service.coverage_reader = lambda _hh, _id, _type, start, end: (
        {
            "status": "COMPLETE",
            "basis": "QUALIFIED_SOURCE_INTERVAL",
            "start": start.isoformat(),
            "end": end.isoformat(),
        }
        if start.isoformat() == second["start"]
        else {"status": "UNKNOWN"}
    )
    with ThreadPoolExecutor(max_workers=2) as pool:
        list(pool.map(lambda _: service.reconcile_reviews(home), range(2)))
    scored = service.evaluations(home)["items"][0]
    assert (scored["known_opportunities"], scored["misses"], scored["unknown_opportunities"]) == (
        2,
        1,
        1,
    )
    assert (scored["prediction_correct"], scored["baseline_correct"]) == (1, 1)
    assert scored["covered_opportunities"] == 1
    assert all(row["physical_occurrence_at"] is None for row in scored["windows"])
    service.reconcile_reviews(home)  # synchronize measured feedback to Obsidian
    suggestion = service.suggestions(home)["items"][0]
    assert suggestion["prospective_feedback"][0]["misses"] == 1
    assert all(suggestion["suggestion_id"] in ids for ids in retrieved(value))
    notes = list((tmp_path / "vault").rglob("*.md"))
    assert len(notes) == 1  # no orphan from concurrent healthy reconcilers
    assert notes[0].stem == suggestion["knowledge_note"]["note_id"]
    assert "Prospective source-window feedback" in notes[0].read_text()
    assert service.evaluations(value["foreign"])["items"] == []
    gateway, owner, _ = owner_gateway(value)
    correction = gateway.learning_operation(
        owner,
        "review",
        {
            "suggestion_id": suggestion["suggestion_id"],
            "decision": "CORRECTED",
            "content": "Synthetic owner disputes recurrence.",
        },
    )
    assert correction["status"] == "SUCCEEDED", correction
    service.reconcile_reviews(home)
    final = service.evaluations(home)["items"][0]
    assert final["windows"] == scored["windows"] and final["disposition"] == "SUPERSEDED_HYPOTHESIS"
    assert final["hypothesis_version"] == frozen["hypothesis_version"]
    corrected = service.suggestions(home)["items"][0]
    assert (
        corrected["classification"] == "OWNER_CORRECTION"
        and corrected["prospective_feedback"][0]["invalidation_reason"]
    )
    assert all(corrected["suggestion_id"] in ids for ids in retrieved(value))
    assert (
        PostgresIntelligenceStore(value["url"]).claim_specific(
            request.request_id, "no-replay", household_id=home, provider_id="sentry"
        )
        is None
    )


@pytest.mark.parametrize(
    "status", [IntelligenceResultStatus.FAILED, IntelligenceResultStatus.UNKNOWN_RESULT]
)
def test_actual_failed_or_ambiguous_review_never_commissions(
    situation: dict[str, Any], tmp_path: Path, status: IntelligenceResultStatus
) -> None:
    boundary, request, _ = connect_review(situation, tmp_path / "vault")
    finish(boundary, request, status)
    situation["clock"]["now"] = datetime.now(UTC)
    situation["service"].reconcile_reviews(situation["home"])
    assert situation["service"].evaluations(situation["home"])["items"] == []
    assert not situation["service"].review_state(situation["home"], situation["packet"])[
        "terminal_success"
    ]


def test_actual_saved_config_disable_preserves_frozen_plan(
    situation: dict[str, Any], tmp_path: Path
) -> None:
    boundary, request, _ = connect_review(situation, tmp_path / "vault")
    finish(boundary, request, IntelligenceResultStatus.NO_ACTION)
    situation["clock"]["now"] = datetime.now(UTC)
    service, home = situation["service"], situation["home"]
    service.reconcile_reviews(home)
    frozen = service.evaluations(home)["items"][0]
    saved = service.status(home)["config_version"]
    service.configure(
        home,
        situation["owner"],
        {
            **config(daily_review_enabled=False, routine_review_enabled=False),
            "expected_version": saved,
        },
    )
    service.reconcile_reviews(home)
    cancelled = service.evaluations(home)["items"][0]
    assert (
        cancelled["disposition"] == "CANCELLED_SAVED_REVIEW"
        and cancelled["prediction"] == frozen["prediction"]
    )
    assert (
        service.suggestions(home)["items"][0]["prospective_feedback"][0]["disposition"]
        == "CANCELLED_SAVED_REVIEW"
    )
    with psycopg.connect(situation["url"]) as connection:
        assert connection.execute(
            "SELECT count(*) FROM anima_intelligence_requests WHERE household_id=%s", (home,)
        ).fetchone() == (2,)
