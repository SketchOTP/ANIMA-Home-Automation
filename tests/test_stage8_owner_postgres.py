"""Current Core/PG/current OPA scripted owner-result composition; no model/audio."""

from __future__ import annotations

import time
from collections.abc import Iterator
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import uuid4

import httpx
import psycopg
import pytest
from test_stage2_delivery_postgres import isolated_url as isolated_url
from test_stage3_household_situation import situation as situation
from test_stage6_owner_postgres import connected as connected
from test_stage6_owner_postgres import frozen_request

from anima_ha.events import EventEnvelope
from anima_ha.intelligence import IntelligenceResult, IntelligenceResultStatus
from anima_ha.learning_review_runner import LearningReviewRunner
from anima_ha.live_results import PostgresSentryLivePublisher, PostgresSentryLiveResultBus
from anima_ha.owner_task_results import OwnerTaskError
from anima_ha.plugins import NativeRuntime


@pytest.fixture(autouse=True)
def explicit_sentry_provider(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ANIMA_INTELLIGENCE_PROVIDER", "sentry")


@pytest.fixture
def commissioned_weather(connected: dict[str, Any]) -> Iterator[dict[str, Any]]:
    """Declare this synthetic capability before freezing; restore its prior choice."""
    from anima_ha.external import external_plugin

    core = connected["service"].core_runtime
    plugin_id = "anima.external.weather"
    plugin = core.plugins.plugins[plugin_id]
    previous_runtime, previous_enabled = plugin.runtime, plugin.enabled
    calls: list[str] = []

    def weather(req: httpx.Request) -> httpx.Response:
        assert req.url.host == "api.open-meteo.com"
        calls.append(str(req.url))
        return httpx.Response(
            200,
            request=req,
            json={"timezone": "UTC", "current": {"temperature_2m": 21.5}, "current_units": {}},
        )

    _, native = external_plugin(plugin_id, transport=httpx.MockTransport(weather))
    core.plugins.disable(plugin_id)
    plugin.runtime = NativeRuntime(native)
    try:
        core.plugins.enable(plugin_id)
        assert plugin.enabled
        assert any(t.tool_id == f"{plugin_id}.get" for t in core.plugins.list_tools())
        yield {**connected, "weather_calls": calls}
    finally:
        core.plugins.disable(plugin_id)
        plugin.runtime = previous_runtime
        if previous_enabled:
            core.plugins.enable(plugin_id)
        assert plugin.enabled is previous_enabled


def test_saved_future_task_to_frozen_current_external_result(
    commissioned_weather: dict[str, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    value = commissioned_weather
    core, client, headers = value["service"].core_runtime, value["client"], value["headers"]
    core.intelligence_provider = "sentry"
    assert core.owner_task_results is not None
    created = client.post(
        "/api/v1/tasks",
        headers=headers,
        json={
            "payload": {
                "title": "Future weather",
                "note": "Get the current forecast at due time.",
                "when": (datetime.now(UTC) + timedelta(seconds=1)).isoformat(),
            }
        },
    ).json()
    assert created["status"] == "SUCCEEDED", created
    task = created["result"]["task"]
    time.sleep(1.05)
    runner = LearningReviewRunner(core, core.learning_service, value["home"])
    report = runner.run_once()
    assert report["owner_tasks"]["dispatched"] == 1, report
    with psycopg.connect(value["url"]) as conn:
        row = conn.execute(
            "SELECT request_id FROM anima_intelligence_requests WHERE "
            "household_id=%s AND request_metadata->'owner_task'->>'task_id'=%s",
            (value["home"], task["task_id"]),
        ).fetchone()
    assert row is not None
    store, boundary = core.intelligence_store, core.sentry_boundary()
    claimed = store.claim_specific(
        row[0], "stage8-scripted", household_id=value["home"], provider_id="sentry"
    )
    assert claimed and boundary.start_provider(claimed, "stage8-scripted")
    request = store.get(row[0])
    context = boundary.request_context(request)
    assert (
        context["household_context"]["initiative"]["notification"]["reason"]
        == "EXPLICIT_OWNER_TASK"
    )
    assert all(
        t["read_only"] or t["semantic_action"] == "notifications.send" for t in request.catalogue
    )
    assert any(t["tool_id"] == "anima.external.weather.get" for t in request.catalogue)
    reply = boundary.invoke_tool(
        request,
        "anima.external.weather.get",
        {
            "latitude": 40.0,
            "longitude": -74.0,
            "timezone": "UTC",
        },
    )
    assert reply["status"] == "SUCCEEDED", reply
    assert reply["result"]["data"]["current"]["temperature_2m"] == 21.5
    result = IntelligenceResult(
        request.request_id,
        IntelligenceResultStatus.RESPONSE,
        response_text="Current synthetic weather is 21.5 degrees.",
    )
    recorded, result, permission = boundary.finalize_result(request, "stage8-scripted", result)
    assert recorded and permission["reason"] == "EXPLICIT_OWNER_TASK"
    bus = PostgresSentryLiveResultBus(value["url"])
    value["service"].sentry_results = bus
    try:
        # Observe the actual cross-process ephemeral transport. Re-publishing
        # this synthetic result tests LISTEN readiness, never provider replay.
        for _ in range(20):
            PostgresSentryLivePublisher(value["url"]).publish(
                {**result.to_live_payload(), "household_id": str(value["home"])}
            )
            time.sleep(0.05)
            if bus.get(request.request_id, value["home"]):
                break
        presented = client.get(f"/api/v1/conversation/{request.request_id}").json()
        assert presented["available"] and presented["response"] == result.response_text
    finally:
        bus.close()
        value["service"].sentry_results = None
    projected = client.get("/api/v1/tasks").json()["items"]
    owner_task = next(item for item in projected if item["task_id"] == task["task_id"])
    assert owner_task["latest_run"]["result_status"] == "RESPONSE"
    assert owner_task["latest_run"]["delivery"] == "NOT_OBSERVED_BY_TASK_DISPATCH"
    assert len(value["weather_calls"]) == 1 and runner.run_once()["owner_tasks"]["dispatched"] == 0
    event = core.journal.get(request.causation_id)
    with psycopg.connect(value["url"]) as conn:
        row = conn.execute(
            "SELECT journal_position FROM anima_event_journal WHERE event_id=%s", (event.event_id,)
        ).fetchone()
        assert row is not None
        position = row[0]
    core.owner_task_results.handoff(event, position)


def test_due_current_owner_cancellation_is_not_authority(connected: dict[str, Any]) -> None:
    core = connected["service"].core_runtime
    from anima_ha.owner_task_results import OwnerTaskResults
    from anima_ha.tasks import PostgresTaskStore

    tasks = PostgresTaskStore(connected["url"])
    scope = OwnerTaskResults(core, tasks, connected["home"])
    assert scope.run_once()["claimed"] == 0
    with pytest.raises(OwnerTaskError):
        scope.validate_event(
            EventEnvelope.create(
                event_id=str(uuid4()),
                occurred_at=datetime.now(UTC),
                event_type="scheduled_reasoning_due",
                source="anima:durable-task",
                subject_key="task/missing",
                payload={},
            )
        )


def test_actual_approval_result_association_has_no_provider_replay(
    connected: dict[str, Any],
) -> None:
    value, core = connected, connected["service"].core_runtime
    boundary, request = frozen_request(value)
    # Same accepted native HA transport/coordinator; the synthetic test catalogue
    # declares an external side effect so CURRENT OPA requires confirmation.
    plugin = core.plugins.plugins["anima.provider.home-assistant"]
    tool = next(t for t in plugin.tools.values() if t.name == "set_power")
    changed = replace(tool, risk_class="EXTERNAL_SIDE_EFFECT")
    plugin.tools[tool.tool_id] = core.plugins.tools[tool.tool_id] = changed
    boundary, request = frozen_request(value)
    result = boundary.invoke_tool(
        request,
        tool.tool_id,
        {
            "resource_id": str(value["resources"][0]),
            "desired_on": True,
            "capability_id": str(
                core.graph.resource_capabilities(value["resources"][0])[0].canonical_id
            ),
        },
    )
    assert result["status"] == "REQUIRE_CONFIRMATION", result
    approval = result["result"]["approval_id"]
    gate = IntelligenceResult(request.request_id, IntelligenceResultStatus.WAITING_CONFIRMATION)
    assert boundary.submit_result(request, "isolated", gate)
    assert not value["transport"].calls
    response = value["client"].post(
        f"/api/v1/approvals/{approval}",
        headers=value["headers"],
        json={"payload": {"decision": "APPROVE"}},
    )
    assert response.status_code == 200, response.text
    assert response.json()["status"] == "SUCCEEDED", response.json()
    assert len(value["transport"].calls) == 1
    current = core.intelligence_store.get(request.request_id)
    assert current.lifecycle.value == "COMPLETED"
    assert current.attempt_count == 1 and current.provider_invocation_started
    restored_response = value["client"].get(f"/api/v1/conversation/{request.request_id}")
    assert restored_response.status_code == 200, restored_response.text
    restored = restored_response.json()
    assert restored["available"] and "verified" in restored["response"]
