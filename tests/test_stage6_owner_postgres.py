"""Guarded real Core/PG/current OPA; only HA transport is synthetic."""

from __future__ import annotations

import os
from collections.abc import Iterator
from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import UUID, uuid4

import httpx
import psycopg
import pytest
from test_home_assistant import FakeConnection, snapshot, state
from test_stage2_delivery_postgres import isolated_url as isolated_url
from test_stage3_household_situation import situation as situation
from test_stage5_owner_postgres import login, mutate

from anima_ha.agent import ScriptedCodexAdapter
from anima_ha.intelligence import IntelligenceOrigin, IntelligenceRequestFactory
from anima_ha.policy import Assurance, IdentityContext, RequestOrigin
from anima_ha.scenes import Scene
from anima_ha.ui_api import PostgresHouseholdReadModel, UIConfig, UIService, create_app
from anima_ha.ui_runtime import build_postgres_core


class SceneConnection(FakeConnection):
    """Real adapter accepts only existing declared input_boolean services."""

    def __init__(self) -> None:
        entities = ("input_boolean.stage6_a", "input_boolean.stage6_b")
        base = snapshot()
        super().__init__(
            replace(
                base,
                states=tuple(
                    state(entity, "off", datetime.now(UTC).isoformat()) for entity in entities
                ),
                devices=tuple(
                    {"id": f"stage6-device-{i}", "name": f"Stage6 power {i}"} for i in range(2)
                ),
                entities=tuple(
                    {
                        "entity_id": entity,
                        "device_id": f"stage6-device-{i}",
                        "platform": "input_boolean",
                    }
                    for i, entity in enumerate(entities)
                ),
            )
        )
        self.values: dict[str, str] = dict.fromkeys(entities, "off")
        self.unknown_after: int | None = None

    def call_service(self, domain: str, service: str, target: dict[str, Any]) -> dict[str, Any]:
        assert domain == "input_boolean" and service in {"turn_on", "turn_off"}
        result = super().call_service(domain, service, target)
        self.values[str(target["entity_id"])] = "on" if service == "turn_on" else "off"
        return result

    def get_state(self, entity_id: str) -> dict[str, Any] | None:
        if self.unknown_after is not None and len(self.calls) >= self.unknown_after:
            return state(entity_id, "unknown", datetime.now(UTC).isoformat())
        return state(entity_id, self.values[entity_id], datetime.now(UTC).isoformat())


def connected_service(
    value: dict[str, Any],
    transport: SceneConnection,
    patch: pytest.MonkeyPatch,
    root: Path,
    instance: UUID,
) -> UIService:
    """No installed/private connection, credentials, owner boundary or model."""
    for key, content in {
        "ANIMA_HA_INSTANCE_ID": str(instance),
        "ANIMA_HA_PROVIDER_SCOPE": str(instance),
        "ANIMA_HA_WEBSOCKET_URL": "ws://127.0.0.1:9/api/websocket",
        "HA_ACCESS_TOKEN": "SYNTHETIC_TEST_ONLY",
        "ANIMA_HA_CONNECTION_FILE": str(root / "never-created-connection.json"),
        "ANIMA_HOUSEHOLD_ID": str(value["home"]),
        "ANIMA_OWNER_BOUNDARY_MODE": "external",
        "ANIMA_KNOWLEDGE_ROOT": "",
        "ANIMA_BACKUP_DIR": str(root / "backups"),
    }.items():
        patch.setenv(key, content)
    transport.connected = True
    patch.setattr("anima_ha.ui_runtime.HassClientConnection", lambda *args, **kw: transport)
    runtime = build_postgres_core(
        value["url"],
        opa_url=os.environ["ANIMA_STAGE3_TEST_OPA_URL"],
        codex=ScriptedCodexAdapter([]),
        external_transport=httpx.MockTransport(lambda _: httpx.Response(503)),
    )
    return UIService(
        config=UIConfig(test_auth_enabled=True, opa_url=os.environ["ANIMA_STAGE3_TEST_OPA_URL"]),
        core_runtime=runtime,
        read_model=PostgresHouseholdReadModel(
            value["url"],
            graph=runtime.graph,
            truth=runtime.truth.projection,
            plugins=runtime.plugins,
            scene_store=runtime.scene_store,
            automation_store=runtime.automation_store,
            alert_policy_store=runtime.alert_policy_store,
            notification_route_store=runtime.notification_route_store,
            memory_service=runtime.memory_service,
        ),
        ha_user_map={"test-ha-user": (value["home"], value["owner"])},
    )


def close_service(service: UIService) -> None:
    # Stop only the adapter monitor created by this fixture, never host services.
    service.close_owner_boundary()
    runtime = service.core_runtime
    assert runtime is not None
    runtime.home_assistant_adapter.stop()


@pytest.fixture
def connected(
    situation: dict[str, Any], monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> Iterator[dict[str, Any]]:
    if not os.environ.get("ANIMA_STAGE3_TEST_OPA_URL"):
        pytest.skip("requires explicit current stateless OPA test endpoint")
    value = situation
    instance, transport = uuid4(), SceneConnection()
    service = connected_service(value, transport, monkeypatch, tmp_path, instance)
    try:
        client, headers = login(service)
        home = client.get("/api/v1/places").json()["items"]
        room = next(item["place_id"] for item in home if item["kind"] == "ROOM")
        inventory = client.get("/api/v1/devices").json()["items"]
        resources = []
        for index, device in enumerate(inventory):
            result = mutate(
                client,
                headers,
                "/api/v1/devices/commission",
                {
                    "device_handle": device["device_handle"],
                    "name": f"Stage6 power {index}",
                    "place_id": room,
                },
            )
            assert result["status"] == "SUCCEEDED", result
            resources.append(UUID(result["result"]["resource_id"]))
        value.update(
            service=service,
            transport=transport,
            client=client,
            headers=headers,
            resources=resources,
            instance=instance,
            root=tmp_path,
        )
        yield value
    finally:
        close_service(service)
        with psycopg.connect(value["url"]) as conn:
            # Retire only nodes created by this random household's fixture;
            # retain Journal/action/approval/history evidence append-only.
            ids = [r.canonical_id for r in value["graph"].resources_in_place(value["home"])]
            conn.execute(
                "UPDATE anima_graph_nodes SET retired_at=now() WHERE canonical_id=ANY(%s)", (ids,)
            )


def saved_scene(value: dict[str, Any]) -> dict[str, Any]:
    return dict(
        mutate(
            value["client"],
            value["headers"],
            "/api/v1/scenes",
            {
                "name": "Actual bounded scene",
                "steps": [{"resource_id": str(r), "desired_on": True} for r in value["resources"]],
            },
        )["result"]["scene"]
    )


def frozen_request(value: dict[str, Any]) -> tuple[Any, Any]:
    core = value["service"].core_runtime
    # Actual identity/access mapping, not a permissive boundary callback.
    core.graph.update_person_profile(value["home"], value["owner"], access_level="UNRESTRICTED")
    pending = IntelligenceRequestFactory.for_direct_sentry_interaction(
        sentry_request_id=str(uuid4()),
        household_id=value["home"],
        principal_id=value["owner"],
        source_surface="isolated-stage6",
        user_text="Synthetic",
        tools=core.plugins.list_tools(),
        service_client_id="isolated",
    )
    # Configuration requires the existing authenticated UI-issued provenance;
    # direct SENTRY recognized speech does not grant authenticated authority.
    pending = replace(pending, origin=IntelligenceOrigin.DIRECT_UI_USER)
    store = core.intelligence_store
    store.enqueue(pending)
    request = store.claim_specific(
        pending.request_id, "isolated", household_id=value["home"], provider_id="sentry"
    )
    assert request
    boundary = core.sentry_boundary()
    assert boundary.start_provider(request, "isolated")
    return boundary, store.get(pending.request_id)


def test_actual_core_owner_scene_duplicate_restart_and_typed_transport(
    connected: dict[str, Any],
) -> None:
    value = connected
    scene = saved_scene(value)
    path = f"/api/v1/scenes/{scene['scene_id']}/apply"
    payload = {"expected_version": 1, "attempt_id": str(uuid4())}
    assert value["client"].post(path, json={"payload": payload}).status_code == 403
    assert (
        value["client"]
        .post(path, headers=value["headers"], json={"payload": {**payload, "entity_id": "private"}})
        .status_code
        == 422
    )
    result = mutate(value["client"], value["headers"], path, payload)
    assert result["status"] == "SUCCEEDED", result
    assert len(value["transport"].calls) == 2
    assert result["result"]["saved_scene"] == scene
    close_service(value["service"])
    with pytest.MonkeyPatch.context() as patch:
        service = connected_service(
            value, value["transport"], patch, value["root"], value["instance"]
        )
        try:
            client, headers = login(service)
            repeated = mutate(client, headers, path, payload)
            assert repeated["duplicate"] and repeated["action_id"] == result["action_id"]
            assert repeated["result"] == result["result"] and len(value["transport"].calls) == 2
            schema = create_app(service).openapi()["paths"][
                path.replace(scene["scene_id"], "{scene_id}")
            ]
            assert (
                schema["post"]["responses"]["200"]["content"]["application/json"]["schema"][
                    "properties"
                ]["operation"]["const"]
                == "anima.scenes.apply_scene"
            )
        finally:
            close_service(service)


def test_actual_frozen_scene_partial_isolation_version_and_catalogue(
    connected: dict[str, Any],
) -> None:
    value = connected
    scene = saved_scene(value)
    boundary, request = frozen_request(value)
    value["transport"].unknown_after = 2
    arguments = {"scene_id": scene["scene_id"], "expected_version": 1}
    result = boundary.invoke_tool(request, "anima.scenes.apply_scene", arguments, ordinal=1)
    assert result["status"] == "PARTIAL", result
    assert [s["status"] for s in result["result"]["steps"]] == ["SUCCEEDED", "UNKNOWN_RESULT"]
    assert boundary.invoke_tool(request, "anima.scenes.apply_scene", arguments, ordinal=1)[
        "duplicate"
    ]
    assert len(value["transport"].calls) == 2
    foreign = value["service"].core_runtime.scene_store.create(
        Scene.create(
            household_id=value["foreign"],
            creator_principal_id=None,
            name="Foreign",
            steps=[{"resource_id": str(value["other_sensor"]), "desired_on": True}],
        )
    )
    assert (
        boundary.invoke_tool(
            request,
            "anima.scenes.apply_scene",
            {"scene_id": str(foreign.scene_id), "expected_version": 1},
            ordinal=2,
        )["status"]
        == "PRECONDITION_FAILED"
    )
    assert (
        boundary.invoke_tool(
            request, "anima.scenes.apply_scene", {**arguments, "expected_version": 2}, ordinal=3
        )["status"]
        == "PRECONDITION_FAILED"
    )
    value["service"].core_runtime.plugins.disable("anima.scenes")
    with pytest.raises(Exception, match="UNAVAILABLE"):
        boundary.invoke_tool(request, "anima.scenes.apply_scene", arguments, ordinal=4)
    assert len(value["transport"].calls) == 2


def test_actual_setup_automation_alert_ui_mcp_lifecycle_without_execution(
    connected: dict[str, Any],
) -> None:
    value = connected
    client, headers = value["client"], value["headers"]
    scene = saved_scene(value)
    boundary, request = frozen_request(value)
    resources = value["resources"]
    automation = {
        "name": "Synthetic automation",
        "trigger_resource_id": str(resources[0]),
        "trigger_state": "on",
        "action_resource_id": str(resources[1]),
        "action_desired_on": True,
        "enabled": True,
    }
    saved = mutate(client, headers, "/api/v1/automations", automation)["result"]["automation"]
    changed = boundary.invoke_tool(
        request,
        "anima.automations.update_automation",
        {
            **automation,
            "automation_id": saved["automation_id"],
            "expected_version": 1,
            "enabled": False,
        },
        ordinal=1,
    )
    assert changed["status"] == "SUCCEEDED", changed
    assert client.get("/api/v1/automations").json()["items"][0]["enabled"] is False
    alert = {
        "resource_ids": [str(resources[0])],
        "event_type": "senseguard.event",
        "timezone": "UTC",
        "start_local": "00:00",
        "end_local": "05:00",
        "priority": 90,
        "guaranteed_attention": True,
        "delivery_mode": "SENTRY_COGNITION",
        "enabled": True,
    }
    rule = mutate(client, headers, "/api/v1/alerts/policies", alert)["result"]["policy"]
    tools = {item["tool_id"] for item in boundary.catalogue(request)}
    update = next(t for t in tools if t == "anima.senseguard-alerts.save_policy")
    updated = boundary.invoke_tool(
        request,
        update,
        {**alert, "policy_id": rule["policy_id"], "expected_version": 1, "enabled": False},
        ordinal=2,
    )
    assert updated["status"] == "SUCCEEDED", updated
    assert client.get("/api/v1/alerts/policies").json()["items"][0]["enabled"] is False
    space = boundary.invoke_tool(
        request,
        "anima.household-spaces.create_space",
        {"name": "Synthetic zone", "kind": "ZONE", "parent_id": str(value["home"])},
        ordinal=3,
    )
    assert space["status"] == "SUCCEEDED", space
    assert any(s["name"] == "Synthetic zone" for s in client.get("/api/v1/places").json()["items"])
    disabled = mutate(
        client,
        headers,
        "/api/v1/scenes",
        {
            "scene_id": scene["scene_id"],
            "name": scene["name"],
            "steps": scene["steps"],
            "expected_version": 1,
            "enabled": False,
        },
    )
    assert disabled["status"] == "SUCCEEDED"
    assert not value["transport"].calls  # Saving setup is not physical execution.


def test_actual_pg_crash_restart_and_fresh_request_returns_retained_attempt(
    connected: dict[str, Any],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    value = connected
    scene = saved_scene(value)
    transport = value["transport"]
    original = transport.call_service

    class ProcessCrash(BaseException):
        pass

    def interrupted(*args: Any) -> Any:
        original(*args)
        raise ProcessCrash()

    identity = IdentityContext(value["home"], value["owner"], Assurance.AUTHENTICATED)
    application = value["service"].core_runtime.scene_application
    arguments = {"scene_id": scene["scene_id"], "expected_version": 1}
    monkeypatch.setattr(transport, "call_service", interrupted)
    with pytest.raises(ProcessCrash):
        application.apply(
            arguments,
            identity=identity,
            origin=RequestOrigin.DIRECT_USER,
            idempotency_key="isolated-crash",
        )
    root = value["service"].core_runtime.action_executor.store.latest_scene_application(
        value["home"], UUID(scene["scene_id"])
    )
    assert root and root.status.value == "EXECUTING" and len(transport.calls) == 1
    monkeypatch.setattr(transport, "call_service", original)
    close_service(value["service"])
    with pytest.MonkeyPatch.context() as patch:
        fresh = connected_service(value, transport, patch, value["root"], value["instance"])
        try:
            fresh_core = fresh.core_runtime
            assert fresh_core is not None
            result = fresh_core.scene_application.apply(
                arguments,
                identity=identity,
                origin=RequestOrigin.DIRECT_USER,
                idempotency_key="new-request-after-real-composition-restart",
            )
            assert result["duplicate"] and result["action_id"] == str(root.action_id)
            assert result["status"] == "UNKNOWN_RESULT" and result["recorded_status"] == "EXECUTING"
            assert result["result"]["saved_scene"]["version"] == 1
            assert len(result["result"]["steps"]) == 1 and len(transport.calls) == 1
        finally:
            close_service(fresh)
