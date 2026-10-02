"""Actual current worker/client/PG/OPA and controlled saved due-time semantics."""

from __future__ import annotations

import sys
import threading
import time
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any
from uuid import uuid4

import psycopg
import pytest
from test_stage2_delivery_postgres import isolated_url as isolated_url
from test_stage3_household_situation import situation as situation
from test_stage6_owner_postgres import connected as connected

from anima_ha.intelligence import IntelligenceResult, IntelligenceResultStatus
from anima_ha.live_results import PostgresSentryLivePublisher, PostgresSentryLiveResultBus
from anima_ha.owner_task_results import OwnerTaskError
from anima_ha.sentry_autowake import PostgresAutoWakeClaims
from anima_ha.sentry_service import (
    CoreSentryHTTPService,
    SentryServicePrincipal,
    _Handler,
    _UnixHTTPServer,
)
from anima_ha.tasks import TaskSchedule, TaskType


@pytest.fixture(autouse=True)
def explicit_sentry_provider(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ANIMA_INTELLIGENCE_PROVIDER", "sentry")


def due_task(value: dict[str, Any], **schedule: Any) -> Any:
    core = value["service"].core_runtime
    now = datetime.now(UTC)
    return core.learning_service.task_service.create(
        household_id=value["home"],
        creator_principal_id=value["owner"],
        task_type=TaskType.REASONING_DUE,
        title="Synthetic delayed future result",
        payload={"objective": "Return the current supported result."},
        schedule=TaskSchedule.from_payload(
            {
                "kind": "ONCE",
                "timezone": "UTC",
                "run_at": (now - timedelta(minutes=3)).isoformat(),
                **schedule,
            }
        ),
        creation_idempotency_key=str(uuid4()),
        now=now - timedelta(minutes=5),
        provenance={
            "created_via": "tasks.schedule",
            "origin": "DIRECT_USER",
            "tool_request_id": str(uuid4()),
            "invocation_ordinal": 1,
            "owner_result_contract": 1,
        },
    )


def request_for(value: dict[str, Any], task: Any) -> Any:
    core = value["service"].core_runtime
    with psycopg.connect(value["url"]) as conn:
        row = conn.execute(
            "SELECT request_id FROM anima_intelligence_requests WHERE household_id=%s "
            "AND request_metadata->'owner_task'->>'task_id'=%s",
            (value["home"], str(task.task_id)),
        ).fetchone()
    assert row is not None
    return core.intelligence_store.get(row[0])


def test_delayed_current_worker_actual_client_subscriber_result(
    connected: dict[str, Any], monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    value, core = connected, connected["service"].core_runtime
    task = due_task(value)
    assert core.owner_task_results.run_once()["dispatched"] == 1
    request = request_for(value, task)
    # Exact Core auto-wake also permits this explicitly commissioned task even
    # though its saved due time precedes the household event 120s window.
    claims = PostgresAutoWakeClaims(
        value["url"], enabled_at=datetime.now(UTC) - timedelta(seconds=5)
    )
    filters = {
        "origin": "AUTONOMOUS_ATTENTION",
        "not_before": datetime.now(UTC).isoformat(),
        "max_age_seconds": 120,
    }
    listing = claims.eligible(value["home"], "sentry", claims.window(filters), limit=1)
    assert listing[0]["request_id"] == str(request.request_id)
    path = Path(__file__).resolve().parents[1] / "integrations/sentry/anima-household"
    monkeypatch.syspath_prepend(str(path))
    from anima_household_client import AnimaHouseholdClient  # type: ignore[import-not-found]
    from household_worker import HouseholdWorker  # type: ignore[import-not-found]

    assert Path(str(sys.modules["household_worker"].__file__)).is_relative_to(path)
    token, credential = "synthetic-service-token-never-owner-credential", tmp_path / "service.token"
    credential.write_text(token)
    credential.chmod(0o600)
    principal = SentryServicePrincipal.from_secret(
        client_id="stage8-scripted-worker",
        household_id=value["home"],
        provider_id="sentry",
        token=token,
    )
    service = CoreSentryHTTPService(
        core.sentry_boundary(),
        lambda: token,
        service_principal=principal,
        live_result_publisher=PostgresSentryLivePublisher(value["url"]),
    )
    server = _UnixHTTPServer(str(tmp_path / "core.sock"), _Handler)
    server.service = service
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    bus = PostgresSentryLiveResultBus(value["url"])
    value["service"].sentry_results = bus
    client = AnimaHouseholdClient(str(tmp_path / "core.sock"), str(credential))
    calls = []

    class ScriptedModel:
        heartbeat: Any = None

        def check_auth(self) -> bool:
            return True

        def plan(self, context: Any, tools: Any) -> dict[str, Any]:
            self.heartbeat()
            calls.append("plan")
            return {"calls": []}

        def final(self, context: Any, results: Any) -> str:
            self.heartbeat()
            calls.append("final")
            return "Synthetic current future task reply from the actual worker."

    try:
        # Wait for the actual LISTEN subscriber, not a fixed sleep; no response
        # is manually published and the provider's terminal submission is once.
        with psycopg.connect(value["url"]) as conn:
            for _ in range(100):
                if conn.execute(
                    "SELECT 1 FROM pg_stat_activity WHERE usename=current_user "
                    "AND query LIKE 'LISTEN anima_sentry_live_result%' LIMIT 1"
                ).fetchone():
                    break
                time.sleep(0.02)
        assert HouseholdWorker(client, ScriptedModel()).run_once() == {"status": "RECORDED"}
        for _ in range(100):
            if bus.get(request.request_id, value["home"]):
                break
            time.sleep(0.02)
        presented = value["client"].get(f"/api/v1/conversation/{request.request_id}").json()
        assert presented["available"] and presented["response"].startswith(
            "Synthetic current future"
        )
        assert calls == ["plan", "final"]
        current = core.intelligence_store.get(request.request_id)
        assert current.attempt_count == 1 and current.provider_invocation_started
        assert HouseholdWorker(client, ScriptedModel()).run_once() == {"status": "IDLE"}
        assert calls == ["plan", "final"] and not value["transport"].calls
    finally:
        value["service"].sentry_results = None
        bus.close()
        server.shutdown()
        server.server_close()
        thread.join(timeout=3)


@pytest.mark.parametrize(
    "case",
    [
        "legacy_backlog",
        "cancelled_pending",
        "grace_expired",
        "expired",
        "current_creator_revoked",
        "slow_provider",
    ],
)
def test_saved_task_current_scope_and_late_accountability(
    connected: dict[str, Any], case: str
) -> None:
    value, core = connected, connected["service"].core_runtime
    schedule: dict[str, Any] = {"misfire_grace_seconds": 10} if case == "grace_expired" else {}
    if case == "expired":
        schedule["expires_at"] = (datetime.now(UTC) - timedelta(minutes=1)).isoformat()
    task = due_task(value, **schedule)
    if case == "legacy_backlog":
        with psycopg.connect(value["url"]) as conn:
            conn.execute(
                "UPDATE anima_durable_tasks SET provenance=provenance-'owner_result_contract' "
                "WHERE task_id=%s",
                (task.task_id,),
            )
        assert core.owner_task_results.run_once()["claimed"] == 0
        assert core.learning_service.task_service.store.list_runs(task.task_id) == []
        return
    if case == "current_creator_revoked":
        core.graph.update_person_profile(value["home"], value["owner"], semantic_role="guest")
    report = core.owner_task_results.run_once()
    if case in {"grace_expired", "expired", "current_creator_revoked"}:
        assert report["dispatched"] == 0
        runs = core.learning_service.task_service.store.list_runs(task.task_id)
        assert runs and runs[0].status.value in {"MISSED", "FAILED"}
        assert not value["transport"].calls
        return
    assert report["dispatched"] == 1
    request = request_for(value, task)
    if case == "cancelled_pending":
        result = (
            value["client"]
            .post(
                f"/api/v1/tasks/{task.task_id}/cancel",
                headers=value["headers"],
                json={"payload": {}},
            )
            .json()
        )
        assert result["status"] == "SUCCEEDED", result
        assert core.intelligence_store.get(request.request_id).lifecycle.value == "CANCELLED"
        with pytest.raises(OwnerTaskError):
            core.owner_task_results.validate_request(request)
        assert (
            core.intelligence_store.claim_specific(
                request.request_id, "scripted", household_id=value["home"], provider_id="sentry"
            )
            is None
        )
    else:
        claimed = core.intelligence_store.claim_specific(
            request.request_id, "scripted", household_id=value["home"], provider_id="sentry"
        )
        boundary = core.sentry_boundary()
        assert boundary.start_provider(claimed, "scripted")
        current = core.intelligence_store.get(request.request_id)
        # A provider >120s into execution does not invalidate the explicit
        # task merely by age. Its ordinary claim/renewal fence still applies.
        core.owner_task_results.validate_event(
            core.journal.get(request.causation_id), now=datetime.now(UTC) + timedelta(seconds=180)
        )
        assert boundary.submit_result(
            current,
            "scripted",
            IntelligenceResult(
                request.request_id,
                IntelligenceResultStatus.RESPONSE,
                response_text="Synthetic delayed result.",
            ),
        )
