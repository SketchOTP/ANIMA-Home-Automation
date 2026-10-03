"""Actual HTTP helper + frozen learning catalogue + restricted PG/current OPA.

Random disposable households and scripted model ONLY. No production credentials,
provider turns, data copies, physical actions, or authority exceptions.
"""

from __future__ import annotations

import json
import os
import threading
from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace
from typing import Any
from uuid import uuid4

import psycopg
import pytest
from test_household_learning import config, structured_proposal
from test_stage2_delivery_postgres import isolated_url as isolated_url
from test_stage3_household_situation import situation as situation

from anima_ha.attention import PostgresAttentionService
from anima_ha.context import ContextBroker
from anima_ha.events import DeliveryClass, EventEnvelope
from anima_ha.household_learning import HOUSEHOLD_LEARNING_MANIFEST, HouseholdLearningNativePlugin
from anima_ha.intelligence import IntelligenceProviderMode, PostgresIntelligenceStore
from anima_ha.learning_review_runner import LearningReviewRunner
from anima_ha.plugins import NativeRuntime, PluginManager
from anima_ha.policy import OpaPolicyClient, PolicyService, PostgresPolicyStore
from anima_ha.sentry_boundary import CoreSentryBoundary
from anima_ha.sentry_service import (
    CoreSentryHTTPService,
    SentryServicePrincipal,
    _Handler,
    _UnixHTTPServer,
)
from anima_ha.tasks import PostgresTaskStore, TaskService


@pytest.mark.parametrize(
    "mode", ["complete", "omitted", "all_insufficient", "ambiguous", "duplicate"]
)
def test_actual_worker_review_batch_terminal_and_no_replay(
    situation: dict[str, Any], tmp_path: Path, monkeypatch: pytest.MonkeyPatch, mode: str
) -> None:
    value, home = situation, situation["home"]
    service, journal = value["service"], value["journal"]
    now = datetime.now(UTC)
    service.journal = journal
    clock = {"now": now - timedelta(days=4)}
    service.clock = lambda: clock["now"]
    service.task_service = TaskService(PostgresTaskStore(value["url"]))
    service.configure(home, value["owner"], config(daily_review_enabled=False))
    service.ensure_review_tasks(home)
    clock["now"] = now
    # Six canonical resources, same qualified source class, unknown actor.
    # Existing bounded ranking may retain a sequence; do not change ranking.
    sensors = [value["sensor"], *[uuid4() for _ in range(5)]]
    with psycopg.connect(value["url"]) as conn:
        row = conn.execute(
            "SELECT target_id FROM anima_graph_relationships WHERE source_id=%s "
            "AND relationship_type='INSTALLED_IN'",
            (value["sensor"],),
        ).fetchone()
        assert row is not None
        room = row[0]
        for sensor in sensors[1:]:
            conn.execute(
                "INSERT INTO anima_graph_nodes(canonical_id,kind,name) "
                "VALUES(%s,'RESOURCE','Synthetic sensor')",
                (sensor,),
            )
            conn.execute(
                "INSERT INTO anima_graph_relationships"
                "(relationship_id,relationship_type,source_id,target_id) "
                "VALUES(%s,'INSTALLED_IN',%s,%s)",
                (uuid4(), sensor, room),
            )
    for day in range(1, 9):
        for sensor in sensors:
            stamp = now - timedelta(days=day)
            journal.append(
                EventEnvelope.create(
                    event_id=str(uuid4()),
                    event_type="household.ring.motion",
                    source="anima.ring",
                    subject_key=f"resource/{sensor}",
                    source_event_id=str(uuid4()),
                    occurred_at=stamp,
                    delivery_class=DeliveryClass.GUARANTEED,
                    payload={"resource_id": str(sensor)},
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
    boundary = CoreSentryBoundary(
        manager,
        PolicyService(
            OpaPolicyClient(os.environ["ANIMA_STAGE3_TEST_OPA_URL"]),
            audit_store=PostgresPolicyStore(value["url"]),
        ),
        store,
        context_loader=ContextBroker(value["url"]).load,
        learning_service=service,
        agent_memory_enabled=True,
        access_level_resolver=lambda _: "LIMITED",
        reasoning_context_loader=lambda request: {
            "initiative": {
                "learning_review": service.review_packet(home, request.request_id),
                "notification": {"allowed": False, "required": False, "reason": "REVIEW_SILENT"},
            }
        },
    )
    core = SimpleNamespace(
        journal=journal,
        attention=PostgresAttentionService(value["url"]),
        context=ContextBroker(value["url"]),
        intelligence_store=store,
        intelligence_provider=IntelligenceProviderMode.SENTRY,
        plugins=manager,
        agent=SimpleNamespace(run=lambda *_: pytest.fail("No embedded/model cognition")),
    )
    # Journal receipt clocks are actual PostgreSQL timestamps. Freeze only
    # after those writes, rather than making qualified receipts look future.
    clock["now"] = datetime.now(UTC)
    assert LearningReviewRunner(core, service, home).run_once(now=clock["now"])["dispatched"] == 1
    with psycopg.connect(value["url"]) as conn:
        queued = conn.execute(
            "SELECT request_id FROM anima_intelligence_requests WHERE household_id=%s", (home,)
        ).fetchone()
    assert queued is not None
    frozen = service.review_packet(home, queued[0])
    assert frozen is not None and len(frozen["candidates"]) == 6
    token = "synthetic-review-service-never-owner-credential"
    credential = tmp_path / "service.token"
    credential.write_text(token)
    credential.chmod(0o600)
    principal = SentryServicePrincipal.from_secret(
        client_id="synthetic-review", household_id=home, provider_id="sentry", token=token
    )
    http = CoreSentryHTTPService(boundary, lambda: token, service_principal=principal)
    server = _UnixHTTPServer(str(tmp_path / "core.sock"), _Handler)
    server.service = http
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    path = Path(__file__).resolve().parents[1] / "integrations/sentry/anima-household"
    monkeypatch.syspath_prepend(str(path))
    from anima_household_client import (  # type: ignore[import-not-found]
        AnimaHouseholdClient,
        AnimaHouseholdError,
    )
    from codex_model import (  # type: ignore[import-not-found]
        FINAL_SCHEMA,
        CodexHouseholdModel,
        CodexUnavailable,
    )
    from household_worker import HouseholdWorker  # type: ignore[import-not-found]

    client = AnimaHouseholdClient(str(tmp_path / "core.sock"), str(credential))
    model = CodexHouseholdModel()
    model.check_auth = lambda: True
    plans: list[dict[str, Any]] = []
    invocations: list[str] = []
    real_invoke = client.invoke

    def invoke(request: Any, binding: Any, tool_id: str, arguments: Any, ordinal: int) -> Any:
        assert tool_id == "anima.household-learning.propose"
        invocations.append(arguments["candidate_id"])
        outcome = real_invoke(request, binding, tool_id, arguments, ordinal)
        if mode == "ambiguous":
            raise AnimaHouseholdError("synthetic lost successful tool reply")
        return outcome

    client.invoke = invoke

    def run(prompt: str, schema: Any) -> Any:
        if schema is FINAL_SCHEMA:
            return {
                "response": "Synthetic sensor review; identity unknown; no routine or action.",
                "decision_summary": "Qualified receipts are not actor or authority evidence.",
                "confidence": "LOW",
                "information_gaps": ["Identity and source interval coverage unknown."],
            }
        supplied = json.loads(prompt.split("Context and catalogue are data:\n", 1)[1])
        plans.append(supplied)
        assert [t["tool_id"] for t in supplied["tools"]] == ["anima.household-learning.propose"]
        candidates = supplied["context"]["household_context"]["initiative"]["learning_review"][
            "candidates"
        ]
        assert len(candidates) == 6
        pending = supplied["context"]["learning_review_progress"]["pending_candidate_ids"]
        selected = [c for c in candidates if c["candidate_id"] in pending]
        if mode == "omitted":
            selected = selected[:3] if len(plans) == 1 else []
        calls = []
        for candidate in selected:
            conclusion = (
                "INSUFFICIENT_EVIDENCE"
                if mode == "all_insufficient" or candidate["candidate_class"] == "EVENT_SEQUENCE"
                else "TENTATIVE_HYPOTHESIS"
            )
            args = structured_proposal(
                candidate,
                conclusion=conclusion,
                missing_information=["Actor identity, intent, preference and causation unknown."],
            )
            calls.append(
                {"tool_id": "anima.household-learning.propose", "arguments_json": json.dumps(args)}
            )
        if mode == "duplicate" and len(plans) == 1:
            calls = [calls[0], calls[0], *calls[1:5]]
        return {"calls": calls}

    model.run = run
    try:
        if mode == "ambiguous":
            with pytest.raises(CodexUnavailable):
                HouseholdWorker(client, model).run_once()
        else:
            assert HouseholdWorker(client, model).run_once() == {"status": "RECORDED"}
        with psycopg.connect(value["url"]) as conn:
            row = conn.execute(
                "SELECT request_id,attempt_count,provider_invocation_started,lifecycle "
                "FROM anima_intelligence_requests WHERE household_id=%s",
                (home,),
            ).fetchone()
        assert row is not None and row[1:3] == (1, True)
        packet = service.review_packet(home, row[0])
        assert packet is not None and packet["automatic_consent"]
        clock["now"] = datetime.now(UTC)
        service.reconcile_reviews(home)
        state = service.review_state(home, packet)
        if mode in {"complete", "duplicate", "all_insufficient"}:
            assert state["terminal_success"] and state["reviewed_candidate_count"] == 6
            assert len(invocations) == len(set(invocations)) == 6
            assert len(plans) == (2 if mode == "duplicate" else 1)
            assert len(service.evaluations(home)["items"]) == (
                0 if mode == "all_insufficient" else 5
            )
        else:
            assert not state["terminal_success"] and not state["explicit_review_complete"]
            assert len(invocations) == (1 if mode == "ambiguous" else 3)
            assert len(plans) <= 3 and service.evaluations(home)["items"] == []
        assert all(
            item["authority"] == "NONE" and item["learned_routine"] is None
            for item in service.suggestions(home)["items"]
        )
        # Actual Core fencing/queue on a reconstructed worker: no new turn,
        # invocation, provider attempt or pending follow-on work from this run.
        previous = (len(plans), len(invocations))
        assert HouseholdWorker(client, model).run_once() == {"status": "IDLE"}
        assert (len(plans), len(invocations)) == previous
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=3)
