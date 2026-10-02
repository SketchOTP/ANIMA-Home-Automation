"""Isolated owner API/Core/frozen-catalogue workflows and metadata fencing."""

import os
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any
from uuid import uuid4

import psycopg
import pytest
from fastapi.testclient import TestClient
from test_capability_management import StatusPlugin, optional_manifest
from test_sentry_autowake import Harness
from test_stage2_delivery_postgres import isolated_url as isolated_url
from test_stage3_household_situation import active_boundary
from test_stage3_household_situation import situation as situation

from anima_ha.calendar import (
    CALENDAR_MANIFEST,
    CalendarNativePlugin,
    CalendarService,
    PostgresCalendarStore,
)
from anima_ha.capability_management import (
    CAPABILITY_MANAGEMENT_MANIFEST,
    CapabilityManagementNativePlugin,
)
from anima_ha.intelligence import IntelligenceRequestFactory, PostgresIntelligenceStore
from anima_ha.memory import MemoryService, MemoryStatus
from anima_ha.model_usage import model_call_receipt
from anima_ha.plugins import NativeRuntime, PluginManager, PostgresPluginStore
from anima_ha.policy import OpaPolicyClient, PolicyService, PostgresPolicyStore
from anima_ha.preferences import PREFERENCES_MANIFEST, PreferencesNativePlugin
from anima_ha.sentry_boundary import CoreSentryBoundary
from anima_ha.tasks import TASK_MANIFEST, PostgresTaskStore, TaskNativePlugin, TaskService
from anima_ha.ui_api import PostgresHouseholdReadModel, UIConfig, UIService, create_app
from anima_ha.ui_runtime import CoreUICommandGateway


def owner_service(value: dict[str, Any]) -> UIService:
    url, graph = value["url"], value["graph"]
    manager = PluginManager(store=PostgresPluginStore(url))
    for manifest, plugin in (
        (TASK_MANIFEST, TaskNativePlugin(TaskService(PostgresTaskStore(url), value["journal"]))),
        (
            CALENDAR_MANIFEST,
            CalendarNativePlugin(CalendarService(PostgresCalendarStore(url), value["journal"])),
        ),
        (PREFERENCES_MANIFEST, PreferencesNativePlugin(MemoryService(url), graph)),
        (optional_manifest(), StatusPlugin()),
        (CAPABILITY_MANAGEMENT_MANIFEST, CapabilityManagementNativePlugin(manager)),
    ):
        enabled = manager.store.enabled(manifest.plugin_id) if manager.store else None
        manager.register(manifest, NativeRuntime(plugin))
        if enabled is not False:
            manager.enable(manifest.plugin_id)
    policy = PolicyService(
        OpaPolicyClient(os.environ["ANIMA_STAGE3_TEST_OPA_URL"]),
        audit_store=PostgresPolicyStore(url),
    )
    commands = CoreUICommandGateway(
        manager,
        policy,
        policy_role_resolver=lambda principal: "owner" if principal == value["owner"] else "member",
    )
    service = UIService(
        config=UIConfig(test_auth_enabled=True),
        read_model=PostgresHouseholdReadModel(
            url, graph=graph, plugins=manager, memory_service=MemoryService(url)
        ),
        commands=commands,
        ha_user_map={"test-ha-user": (value["home"], value["owner"])},
    )
    return service


def login(service: UIService) -> tuple[TestClient, dict[str, str]]:
    client = TestClient(create_app(service))
    assert client.get("/api/v1/tasks").status_code == 401
    client.get("/auth/login")
    csrf = client.get("/api/v1/bootstrap").json()["csrf_token"]
    return client, {"Origin": "http://testserver", "X-Anima-CSRF": csrf}


def mutate(
    client: TestClient, headers: dict[str, str], path: str, payload: dict[str, Any]
) -> dict[str, Any]:
    response = client.post(path, headers=headers, json={"payload": payload})
    assert response.status_code == 200, response.text
    return dict(response.json())


def test_persisted_owner_tasks_calendar_preferences_settings_and_integrations(
    situation: dict[str, Any],
) -> None:
    client, headers = login(owner_service(situation))
    when = (datetime.now(UTC) + timedelta(days=8)).isoformat()
    assert (
        client.post("/api/v1/tasks", json={"payload": {"title": "t", "when": when}}).status_code
        == 403
    )
    task = mutate(
        client,
        headers,
        "/api/v1/tasks",
        {"title": "Isolated reminder", "when": when, "note": "Synthetic"},
    )
    assert task["status"] == "SUCCEEDED" and task["dispatch_state"] == "ACKNOWLEDGED"
    key = task["result"]["task"]["task_id"]
    for operation, state in (("pause", "PAUSED"), ("resume", "ACTIVE"), ("cancel", "CANCELLED")):
        result = mutate(client, headers, f"/api/v1/tasks/{key}/{operation}", {})
        assert result["result"]["task"]["status"] == state
    event = mutate(
        client,
        headers,
        "/api/v1/calendar",
        {
            "title": "Synthetic event",
            "start_at": when,
            "end_at": (datetime.now(UTC) + timedelta(days=9)).isoformat(),
            "timezone": "UTC",
        },
    )["result"]["event"]
    edited = mutate(
        client,
        headers,
        f"/api/v1/calendar/{event['event_id']}/update",
        {"expected_version": 1, "title": "Corrected"},
    )
    assert edited["status"] == "SUCCEEDED" and edited["result"]["event"]["version"] == 2
    stale = mutate(
        client,
        headers,
        f"/api/v1/calendar/{event['event_id']}/update",
        {"expected_version": 1, "title": "Stale"},
    )
    assert stale["status"] != "SUCCEEDED"
    assert stale["connector_outcome"] == "PLUGIN_ERROR"
    preference = mutate(
        client,
        headers,
        "/api/v1/preferences/create",
        {"content": "Synthetic old preference", "category": "meals"},
    )["result"]["preference"]
    corrected = mutate(
        client,
        headers,
        "/api/v1/preferences/update",
        {"preference_id": preference["preference_id"], "content": "Synthetic corrected preference"},
    )["result"]["preference"]
    memory = MemoryService(situation["url"])
    original = memory.get(__import__("uuid").UUID(preference["preference_id"]))
    assert original and original.status == MemoryStatus.SUPERSEDED
    settings = client.put(
        "/api/v1/settings",
        headers=headers,
        json={"payload": {"accent": "purple", "reduced_motion": True}},
    )
    assert settings.status_code == 200
    disabled = mutate(
        client,
        headers,
        "/api/v1/integrations/set-enabled",
        {"plugin_id": "anima.external.weather", "enabled": False},
    )
    assert (
        disabled["status"] == "SUCCEEDED" and disabled["result"]["integration"]["enabled"] is False
    )
    fresh, fresh_headers = login(owner_service(situation))
    assert fresh.get("/api/v1/tasks").json()["items"][0]["status"] == "CANCELLED"
    assert fresh.get("/api/v1/calendar").json()["items"][0]["title"] == "Corrected"
    assert (
        fresh.get("/api/v1/preferences").json()["items"][0]["preference_id"]
        == corrected["preference_id"]
    )
    assert fresh.get("/api/v1/settings").json()["settings"]["accent"] == "purple"
    integrations = fresh.get("/api/v1/integrations").json()["items"]
    assert (
        next(item for item in integrations if item["plugin_id"] == "anima.external.weather")[
            "enabled"
        ]
        is False
    )
    assert (
        mutate(
            fresh,
            fresh_headers,
            "/api/v1/integrations/set-enabled",
            {"plugin_id": "anima.external.weather", "enabled": True},
        )["status"]
        == "SUCCEEDED"
    )
    assert (
        mutate(
            fresh,
            fresh_headers,
            "/api/v1/calendar/" + event["event_id"] + "/cancel",
            {"expected_version": 2},
        )["result"]["event"]["status"]
        == "CANCELLED"
    )
    assert (
        mutate(
            fresh,
            fresh_headers,
            "/api/v1/preferences/retract",
            {"preference_id": corrected["preference_id"]},
        )["status"]
        == "SUCCEEDED"
    )
    assert fresh.get("/api/v1/preferences").json()["items"] == []


def test_frozen_mcp_catalogue_retains_contracts_and_rechecks_disabled_plugin(
    situation: dict[str, Any],
) -> None:
    service = owner_service(situation)
    commands = service.commands
    assert isinstance(commands, CoreUICommandGateway)
    store = PostgresIntelligenceStore(situation["url"])
    pending = IntelligenceRequestFactory.for_direct_sentry_interaction(
        sentry_request_id=str(uuid4()),
        household_id=situation["home"],
        source_surface="isolated-stage5",
        user_text="Synthetic",
        tools=commands.manager.list_tools(),
        service_client_id="isolated",
        principal_id=situation["owner"],
    )
    store.enqueue(pending)
    request = store.claim_specific(
        pending.request_id, "isolated", household_id=situation["home"], provider_id="sentry"
    )
    assert request
    boundary = CoreSentryBoundary(
        commands.manager, commands.policy_service, store, policy_role_resolver=lambda _: "owner"
    )
    assert boundary.start_provider(request, "isolated")
    request = store.get(request.request_id)
    assert request
    catalogue = boundary.catalogue(request)
    assert (
        next(item for item in catalogue if item["tool_id"] == "anima.calendar.create_event")[
            "output_schema"
        ]["properties"]["event"]["properties"]["version"]["type"]
        == "integer"
    )
    result = boundary.invoke_tool(
        request,
        "anima.calendar.list_events",
        {
            "start_at": datetime.now(UTC).isoformat(),
            "end_at": (datetime.now(UTC) + timedelta(days=30)).isoformat(),
        },
    )
    assert result["status"] == "SUCCEEDED"
    descriptor = next(
        item
        for item in commands.manager.list_tools()
        if item.tool_id == "anima.calendar.list_events"
    )
    # Frozen input alone is insufficient: a changed result contract must also
    # become unavailable rather than silently replacing the owner's contract.
    commands.manager.tools[descriptor.tool_id] = replace(
        descriptor, output_schema={"type": "object"}
    )
    assert not next(
        item for item in boundary.catalogue(request) if item["tool_id"] == descriptor.tool_id
    )["availability"]
    commands.manager.tools[descriptor.tool_id] = descriptor
    commands.manager.disable("anima.external.weather")

    from anima_ha.sentry_boundary import SentryBoundaryError

    with pytest.raises(SentryBoundaryError, match="TOOL_UNAVAILABLE"):
        boundary.invoke_tool(request, "anima.external.weather.status", {})


def test_receipts_persist_fenced_in_existing_lifecycle_audit(situation: dict[str, Any]) -> None:
    boundary, request = active_boundary(situation)
    receipt = model_call_receipt(
        {
            "call_id": str(uuid4()),
            "purpose": "PLANNER",
            "model": "gpt-5.6-luna",
            "phase": "ATTEMPTED",
            "status": "UNKNOWN",
            "usage": None,
            "usage_status": "UNKNOWN",
            "elapsed_ms": 0,
        }
    )
    assert boundary.renew_request(request, request.claim_owner, receipt)
    completed = {
        **receipt,
        "phase": "FINISHED",
        "status": "SUCCEEDED",
        "usage": {"output_tokens": 4},
        "usage_status": "REPORTED",
        "elapsed_ms": 5,
    }
    assert boundary.renew_request(request, request.claim_owner, completed)
    assert not boundary.renew_request(
        request, request.claim_owner, {**completed, "call_id": str(uuid4())}
    )
    assert boundary.renew_request(request, request.claim_owner, completed)
    assert not boundary.renew_request(request, request.claim_owner, {**completed, "elapsed_ms": 6})
    store = PostgresIntelligenceStore(situation["url"])
    assert (
        store.renew(
            request.request_id,
            request.claim_owner,
            request.fencing_generation + 1,
            model_call=completed,
        )
        is False
    )
    with psycopg.connect(situation["url"]) as conn:
        rows = conn.execute(
            "SELECT metadata->'model_call' FROM anima_intelligence_transitions "
            "WHERE request_id=%s AND metadata ? 'model_call' ORDER BY transition_id",
            (request.request_id,),
        ).fetchall()
    assert [item[0]["phase"] for item in rows] == ["ATTEMPTED", "FINISHED"]
    assert rows[1][0]["usage"] == {"output_tokens": 4}


def test_actual_authenticated_http_receipt_transport(isolated_url: str, tmp_path: Path) -> None:
    harness = Harness(isolated_url, tmp_path)
    try:
        request_id = harness.enqueue()
        code, claimed = harness.claim(request_id)
        assert code == 200 and claimed["status"] == "CLAIMED"
        binding = {"binding": claimed["binding"], "request_id": str(request_id)}
        receipt = {
            "call_id": str(uuid4()),
            "purpose": "PLANNER",
            "model": "gpt-5.6-luna",
            "phase": "ATTEMPTED",
            "status": "UNKNOWN",
            "usage": None,
            "usage_status": "UNKNOWN",
            "elapsed_ms": 0,
        }
        path = "/v1/requests/renew"
        assert harness.post(path, {**binding, "model_call": receipt}, token="wrong")[0] == 401
        assert harness.post(path, {**binding, "model_call": receipt})[1]["status"] == "CLAIM_LOST"
        assert (
            harness.post(f"/v1/requests/{request_id}/provider-start", binding)[1]["status"]
            == "PROVIDER_RUNNING"
        )
        assert (
            harness.post(path, {**binding, "model_call": {**receipt, "prompt": "private"}})[0]
            == 400
        )
        assert harness.post(path, {**binding, "model_call": receipt}) == (
            200,
            {"status": "RENEWED"},
        )
        finished = {**receipt, "phase": "FINISHED", "status": "TIMEOUT", "elapsed_ms": 20}
        assert harness.post(path, {**binding, "model_call": finished})[1]["status"] == "RENEWED"
        result = harness.post(
            f"/v1/requests/{request_id}/result",
            {
                **binding,
                "status": "FAILED",
                "provider_ambiguous": True,
                "metadata": {"model_calls": [finished]},
            },
        )
        assert result[0] == 200 and result[1]["status"] == "RECORDED"
        assert harness.claim(request_id) == (200, {"status": "EMPTY"})
        assert harness.post(path, {**binding, "model_call": finished})[0] == 409
        with psycopg.connect(isolated_url) as conn:
            rows = conn.execute(
                "SELECT metadata->'model_call' FROM anima_intelligence_transitions "
                "WHERE request_id=%s AND metadata ? 'model_call' ORDER BY transition_id",
                (request_id,),
            ).fetchall()
        assert [row[0]["phase"] for row in rows] == ["ATTEMPTED", "FINISHED"]
    finally:
        harness.close()
