"""Real Home Assistant 2026.8.2 Phase 6 integration evidence harness."""

from __future__ import annotations

import asyncio
import json
import os
import shutil
import socket
import subprocess
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import replace
from pathlib import Path
from typing import Any
from uuid import NAMESPACE_URL, UUID, uuid4, uuid5

import aiohttp

from anima_ha.db.migrate import migrate
from anima_ha.events import ObservationState
from anima_ha.fixtures import sample_household_document
from anima_ha.graph import (
    CanonicalNode,
    CanonicalRelationship,
    CommissioningDocument,
    NodeKind,
    PostgresHouseholdGraph,
    ProviderReference,
    RelationshipType,
    TargetKind,
)
from anima_ha.home_assistant import (
    HA_IMAGE,
    HAActionOutcome,
    HAAdapterStatus,
    HAAuthenticationError,
    HAConnection,
    HAHealth,
    HAInstanceConfig,
    HassClientConnection,
    HomeAssistantAdapter,
    HomeAssistantPlugin,
    PostgresHAStore,
    home_assistant_manifest,
)
from anima_ha.journal import PostgresRealityStore
from anima_ha.plugins import (
    InvocationOutcome,
    NativeRuntime,
    PluginManager,
    PostgresPluginStore,
    SecretBroker,
)
from anima_ha.policy import (
    Assurance,
    IdentityContext,
    OpaPolicyClient,
    PolicyContext,
    PolicyService,
    PostgresPolicyStore,
)

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "tests/fixtures/home_assistant/configuration.yaml"
TEST_USERNAME = "anima-phase6"
TEST_PASSWORD = "phase6-isolated-test-only"
INSTANCE_ID = uuid5(NAMESPACE_URL, "https://anima-ha.invalid/providers/home-assistant/phase6")
RESOURCE_ID = uuid5(NAMESPACE_URL, "https://anima-ha.invalid/phase6/resource/test-power")
CAPABILITY_ID = uuid5(NAMESPACE_URL, "https://anima-ha.invalid/phase6/capability/test-power")


def docker(*args: str, capture: bool = False) -> str:
    result = subprocess.run(
        ["docker", *args],
        check=True,
        text=True,
        capture_output=capture,
    )
    return result.stdout.strip() if capture else ""


class DockerHomeAssistant:
    def __init__(self) -> None:
        self.name = f"anima-ha-phase6-{str(uuid4())[:8]}"
        self.config_dir = Path(tempfile.mkdtemp(prefix="anima-ha-phase6-config-"))
        shutil.copy2(FIXTURE, self.config_dir / "configuration.yaml")
        with socket.socket() as listener:
            listener.bind(("127.0.0.1", 0))
            self.port = int(listener.getsockname()[1])
        self.base_url = f"http://127.0.0.1:{self.port}"

    def start_new(self) -> None:
        docker(
            "run",
            "-d",
            "--name",
            self.name,
            "-p",
            f"127.0.0.1:{self.port}:8123",
            "-e",
            "TZ=UTC",
            "-v",
            f"{self.config_dir}:/config",
            HA_IMAGE,
        )
        self.wait_ready()

    def wait_ready(self) -> None:
        deadline = time.monotonic() + 120
        while time.monotonic() < deadline:
            try:
                with urllib.request.urlopen(f"{self.base_url}/api/", timeout=2) as response:
                    if response.status == 200:
                        return
            except urllib.error.HTTPError as exc:
                if exc.code in {401, 403}:
                    return
            except (OSError, TimeoutError):
                pass
            time.sleep(1)
        raise TimeoutError("Home Assistant did not become ready")

    def stop(self) -> None:
        docker("stop", "--timeout", "30", self.name)

    def restart(self) -> None:
        docker("start", self.name)
        self.wait_ready()

    def close(self) -> None:
        subprocess.run(
            ["docker", "rm", "-f", self.name],
            check=False,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        shutil.rmtree(self.config_dir, ignore_errors=True)


def http_json(
    base_url: str,
    path: str,
    *,
    data: dict[str, Any] | None = None,
    token: str | None = None,
    form: bool = False,
) -> Any:
    headers: dict[str, str] = {}
    body: bytes | None = None
    if data is not None:
        if form:
            body = urllib.parse.urlencode(data).encode()
            headers["Content-Type"] = "application/x-www-form-urlencoded"
        else:
            body = json.dumps(data).encode()
            headers["Content-Type"] = "application/json"
    if token:
        headers["Authorization"] = f"Bearer {token}"
    request = urllib.request.Request(
        f"{base_url}{path}", data=body, headers=headers, method="POST" if body else "GET"
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        content = response.read()
    return json.loads(content) if content else {}


async def ws_command(base_url: str, token: str, command: dict[str, Any]) -> Any:
    ws_url = base_url.replace("http://", "ws://") + "/api/websocket"
    async with aiohttp.ClientSession() as session:
        async with session.ws_connect(ws_url, heartbeat=30) as websocket:
            assert (await websocket.receive_json())["type"] == "auth_required"
            await websocket.send_json({"type": "auth", "access_token": token})
            assert (await websocket.receive_json())["type"] == "auth_ok"
            await websocket.send_json(command)
            return await websocket.receive_json()


def onboard(base_url: str) -> str:
    steps = http_json(base_url, "/api/onboarding")
    client_id = f"{base_url}/"
    if not any(not step.get("done", False) for step in steps):
        raise RuntimeError("Phase 6 evidence requires a fresh isolated HA configuration")
    user = http_json(
        base_url,
        "/api/onboarding/users",
        data={
            "client_id": client_id,
            "name": "ANIMA Phase 6",
            "username": TEST_USERNAME,
            "password": TEST_PASSWORD,
            "language": "en",
        },
    )
    tokens = http_json(
        base_url,
        "/auth/token",
        data={
            "client_id": client_id,
            "grant_type": "authorization_code",
            "code": user["auth_code"],
        },
        form=True,
    )
    short_token = str(tokens["access_token"])
    for step in ("core_config", "analytics"):
        try:
            http_json(
                base_url,
                f"/api/onboarding/{step}",
                data={"client_id": client_id},
                token=short_token,
            )
        except urllib.error.HTTPError:
            pass
    try:
        http_json(
            base_url,
            "/api/onboarding/integration",
            data={"client_id": client_id, "redirect_uri": client_id},
            token=short_token,
        )
    except urllib.error.HTTPError:
        pass
    result = asyncio.run(
        ws_command(
            base_url,
            short_token,
            {
                "id": 1,
                "type": "auth/long_lived_access_token",
                "client_name": "ANIMA Phase 6 evidence",
                "lifespan": 1,
            },
        )
    )
    assert result["success"] is True
    return str(result["result"])


def commission_phase6_graph(
    graph: PostgresHouseholdGraph, snapshot: Any, provider_scope: str
) -> tuple[UUID, UUID, str, str, str]:
    base = sample_household_document()
    graph.commission(base)
    resource = CanonicalNode(
        RESOURCE_ID,
        NodeKind.RESOURCE,
        "ANIMA Phase 6 Test Power",
        metadata={"resource_type": "low_risk_power"},
    )
    capability = CanonicalNode(
        CAPABILITY_ID,
        NodeKind.CAPABILITY,
        "ANIMA Phase 6 Power Control",
        metadata={"capability_type": "power.set", "readable": True, "writable": True},
    )
    graph.commission(
        CommissioningDocument(
            1,
            (
                next(node for node in base.nodes if node.kind == NodeKind.HOUSEHOLD),
                resource,
                capability,
            ),
            (
                CanonicalRelationship(
                    uuid5(NAMESPACE_URL, "https://anima-ha.invalid/phase6/exposes"),
                    RelationshipType.EXPOSES,
                    RESOURCE_ID,
                    CAPABILITY_ID,
                ),
            ),
        )
    )
    input_entity = "input_boolean.anima_test_power"
    linked_entity = next(
        item
        for item in snapshot.entities
        if item.get("device_id") and item.get("entity_id") != input_entity
    )
    device_id = str(linked_entity["device_id"])
    linked_entity_id = str(linked_entity["entity_id"])
    area_id = str(snapshot.areas[0]["area_id"])
    kitchen_id = next(node.canonical_id for node in base.nodes if node.name == "Kitchen")
    references = (
        ProviderReference(
            uuid5(NAMESPACE_URL, f"ha:{provider_scope}:area:{area_id}"),
            "home_assistant",
            provider_scope,
            "area",
            area_id,
            kitchen_id,
        ),
        ProviderReference(
            uuid5(NAMESPACE_URL, f"ha:{provider_scope}:device:{device_id}"),
            "home_assistant",
            provider_scope,
            "device",
            device_id,
            RESOURCE_ID,
        ),
        ProviderReference(
            uuid5(NAMESPACE_URL, f"ha:{provider_scope}:entity:{linked_entity_id}"),
            "home_assistant",
            provider_scope,
            "entity",
            linked_entity_id,
            RESOURCE_ID,
        ),
        ProviderReference(
            uuid5(NAMESPACE_URL, f"ha:{provider_scope}:entity:{input_entity}"),
            "home_assistant",
            provider_scope,
            "entity",
            input_entity,
            CAPABILITY_ID,
            TargetKind.CAPABILITY,
        ),
    )
    for reference in references:
        graph.map_provider_reference(reference)
    return RESOURCE_ID, CAPABILITY_ID, input_entity, device_id, linked_entity_id


class BlindVerificationConnection:
    """Fault injection: delegate service acknowledgement but hide resulting state."""

    def __init__(self, delegate: HAConnection) -> None:
        self.delegate = delegate
        self.version = delegate.version

    @property
    def connected(self) -> bool:
        return self.delegate.connected

    def start(self) -> Any:
        return self.delegate.start()

    def activate(self) -> list[dict[str, Any]]:
        return self.delegate.activate()

    def stop(self) -> None:
        self.delegate.stop()

    def snapshot(self) -> Any:
        return self.delegate.snapshot()

    def call_service(self, domain: str, service: str, target: dict[str, Any]) -> Any:
        return self.delegate.call_service(domain, service, target)

    def get_state(self, entity_id: str) -> dict[str, Any]:
        return {
            "entity_id": entity_id,
            "state": "off",
            "last_changed": "2026-08-29T18:00:00+00:00",
            "last_updated": "2026-08-29T18:00:00+00:00",
            "attributes": {},
            "context": {"id": "fault-injection"},
        }

    def ping(self) -> None:
        self.delegate.ping()


class GateProbeHomeAssistantPlugin(HomeAssistantPlugin):
    """Reuse an already-online adapter to prove policy blocks before invocation."""

    def start(self, secret_env: dict[str, str]) -> None:
        self.started = True

    def stop(self) -> None:
        self.started = False


def wait_for(predicate: Any, timeout: float = 10.0) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return
        time.sleep(0.1)
    raise TimeoutError("condition did not become true")


def main() -> int:
    database_url = os.environ["ANIMA_DATABASE_URL"]
    opa_url = os.environ.get("ANIMA_OPA_URL", "http://127.0.0.1:18181")
    db_container = os.environ.get("ANIMA_DB_CONTAINER")
    fixture = DockerHomeAssistant()
    manager: PluginManager | None = None
    token = ""
    try:
        fixture.start_new()
        token = onboard(fixture.base_url)
        websocket_url = fixture.base_url.replace("http://", "ws://") + "/api/websocket"
        config = HAInstanceConfig(
            INSTANCE_ID,
            websocket_url,
            "ANIMA_HA_TOKEN",
            ssl=False,
            verification_timeout=1.0,
            reconnect_backoff_seconds=0.1,
        )
        probe = HassClientConnection(
            config,
            token,
            event_callback=lambda event: None,
            disconnect_callback=lambda error: None,
        )
        discovery = probe.start()
        probe.activate()
        probe.stop()
        assert discovery.version == "2026.8.2"
        assert discovery.states and discovery.services
        assert discovery.areas and discovery.devices and discovery.entities

        migrate(database_url, 5)
        reality = PostgresRealityStore(database_url)
        graph = PostgresHouseholdGraph(database_url)
        ha_store = PostgresHAStore(database_url)
        plugin_store = PostgresPluginStore(database_url)
        policy = PolicyService(
            OpaPolicyClient(opa_url), audit_store=PostgresPolicyStore(database_url)
        )
        resource_id, capability_id, entity_id, device_id, linked_entity_id = (
            commission_phase6_graph(graph, discovery, config.provider_scope)
        )
        adapter = HomeAssistantAdapter(config, reality, graph, ha_store)

        def connection_factory(current_token: str) -> HassClientConnection:
            return HassClientConnection(
                config,
                current_token,
                event_callback=adapter.receive_provider_event,
                disconnect_callback=adapter.disconnected,
            )

        plugin = HomeAssistantPlugin(adapter, connection_factory)
        manager = PluginManager(
            journal=reality.journal,
            store=plugin_store,
            secret_broker=SecretBroker({"ANIMA_HA_TOKEN": token}),
        )
        manifest = home_assistant_manifest(config)
        manager.register(
            manifest,
            NativeRuntime(plugin),
            configuration={"instance_id": str(INSTANCE_ID), "websocket_url": websocket_url},
        )
        enabled = manager.enable(manifest.plugin_id)
        assert enabled.enabled and adapter.status.health == HAHealth.ONLINE
        assert {tool.name for tool in manager.list_tools(plugin_id=manifest.plugin_id)} == {
            "read_state",
            "set_power",
        }
        assert all("call_service" not in tool.name for tool in manager.list_tools())
        inventory = adapter.provider_inventory()
        assert any(
            item["external_object_kind"] == "area"
            and item["metadata"]["mapping_status"] == "MAPPED"
            for item in inventory
        )
        assert any(
            item["external_object_kind"] == "device" and item["external_id"] == device_id
            for item in inventory
        )
        assert (
            graph.resolve_provider_reference(
                "home_assistant", config.provider_scope, "device", device_id
            ).canonical_id
            == resource_id
        )
        assert (
            graph.resolve_provider_reference(
                "home_assistant", config.provider_scope, "entity", linked_entity_id
            ).canonical_id
            == resource_id
        )
        assert any(item["metadata"]["mapping_status"] == "UNMAPPED" for item in inventory)

        mapped_area_id = str(discovery.areas[0]["area_id"])
        area_target_before = graph.resolve_provider_reference(
            "home_assistant", config.provider_scope, "area", mapped_area_id
        ).canonical_id
        registry_update = asyncio.run(
            ws_command(
                fixture.base_url,
                token,
                {
                    "id": 2,
                    "type": "config/area_registry/update",
                    "area_id": mapped_area_id,
                    "name": "ANIMA Phase 6 Renamed Provider Area",
                },
            )
        )
        assert registry_update["success"] is True
        wait_for(
            lambda: any(
                item["external_id"] == mapped_area_id
                and item["metadata"].get("name") == "ANIMA Phase 6 Renamed Provider Area"
                for item in adapter.provider_inventory()
            )
        )
        assert (
            graph.resolve_provider_reference(
                "home_assistant", config.provider_scope, "area", mapped_area_id
            ).canonical_id
            == area_target_before
        )
        assert reality.journal.list_events(event_type="home_assistant.registry_changed")

        # Test-side state injection only; this is explicitly not action execution.
        http_json(
            fixture.base_url,
            "/api/states/sensor.anima_phase6_unknown",
            data={"state": "unknown", "attributes": {"friendly_name": "ANIMA Unknown"}},
            token=token,
        )
        http_json(
            fixture.base_url,
            "/api/states/sensor.anima_phase6_unavailable",
            data={
                "state": "unavailable",
                "attributes": {"friendly_name": "ANIMA Unavailable"},
            },
            token=token,
        )
        unknown_key = adapter._truth_key("sensor.anima_phase6_unknown")
        unavailable_key = adapter._truth_key("sensor.anima_phase6_unavailable")
        wait_for(lambda: reality.projection.get(unknown_key).status.value == "UNKNOWN")
        wait_for(lambda: reality.projection.get(unavailable_key).status.value == "UNAVAILABLE")

        household_id = sample_household_document().nodes[0].canonical_id
        principal_id = next(
            node.canonical_id for node in sample_household_document().nodes if node.name == "Alex"
        )
        identity = IdentityContext(
            household_id,
            principal_id,
            Assurance.AUTHENTICATED,
        )
        owner_context = PolicyContext(principal_role="owner")
        allowed = manager.invoke(
            f"{manifest.plugin_id}.set_power",
            {
                "resource_id": str(resource_id),
                "capability_id": str(capability_id),
                "desired_on": True,
            },
            household_id=household_id,
            identity=identity,
            policy_service=policy,
            policy_context=owner_context,
        )
        assert allowed.outcome == InvocationOutcome.SUCCESS, allowed
        assert allowed.result["outcome"] == HAActionOutcome.SUCCESS.value
        assert allowed.result["observed_state"] == "on"

        anonymous = IdentityContext(household_id, None, Assurance.ANONYMOUS)
        denied = manager.invoke(
            f"{manifest.plugin_id}.set_power",
            {"resource_id": str(resource_id), "desired_on": False},
            household_id=household_id,
            identity=anonymous,
            policy_service=policy,
        )
        assert denied.outcome == InvocationOutcome.POLICY_DENIED

        base_tools = list(manifest.tools)
        gate_cases = (
            (
                "confirmation",
                "EXTERNAL_SIDE_EFFECT",
                "send_message",
                InvocationOutcome.REQUIRE_CONFIRMATION,
                identity,
            ),
            (
                "stronger",
                "SECURITY_ACCESS_ACTION",
                "unlock",
                InvocationOutcome.REQUIRE_STRONGER_AUTH,
                IdentityContext(household_id, principal_id, Assurance.RECOGNIZED),
            ),
        )
        for suffix, risk, semantic, expected, gate_identity in gate_cases:
            gate_manifest = replace(
                manifest,
                plugin_id=f"anima.provider.home-assistant.gate-{suffix}",
                tools=(
                    base_tools[0],
                    {**base_tools[1], "risk_class": risk, "semantic_action": semantic},
                ),
            )
            gate_plugin = GateProbeHomeAssistantPlugin(adapter, connection_factory)
            manager.register(
                gate_manifest,
                NativeRuntime(gate_plugin),
                configuration={
                    "instance_id": str(INSTANCE_ID),
                    "websocket_url": websocket_url,
                },
            )
            manager.enable(gate_manifest.plugin_id)
            gate_result = manager.invoke(
                f"{gate_manifest.plugin_id}.set_power",
                {"resource_id": str(resource_id), "desired_on": False},
                household_id=household_id,
                identity=gate_identity,
                policy_service=policy,
                policy_context=owner_context,
            )
            assert gate_result.outcome == expected

        assert adapter.connection is not None
        real_connection = adapter.connection
        adapter.connection = BlindVerificationConnection(real_connection)
        failed_verification = adapter.set_power(resource_id, True, capability_id)
        adapter.connection = real_connection
        assert failed_verification.outcome == HAActionOutcome.VERIFICATION_FAILED
        assert failed_verification.service_acknowledged is True

        # Real invalid-token auth reaches the explicit AUTH_FAILED boundary.
        bad_adapter = HomeAssistantAdapter(config, reality, graph, ha_store)
        bad_connection = HassClientConnection(
            config,
            "invalid-phase6-token",
            event_callback=bad_adapter.receive_provider_event,
            disconnect_callback=bad_adapter.disconnected,
        )
        try:
            bad_adapter.start(bad_connection)
        except HAAuthenticationError:
            pass
        else:
            raise AssertionError("invalid Home Assistant token unexpectedly authenticated")
        finally:
            bad_connection.stop()
        assert bad_adapter.status.health == HAHealth.AUTH_FAILED

        fixture.stop()
        wait_for(lambda: adapter.status.health == HAHealth.OFFLINE, timeout=15)
        fixture.restart()
        assert adapter.reconnect(lambda: connection_factory(token)) is True
        assert adapter.status.health == HAHealth.ONLINE
        gap_source = f"provider:home_assistant:{config.provider_scope}"
        assert reality.journal.list_events(
            event_type="home_assistant.connection_gap_started", source=gap_source
        )
        assert reality.journal.list_events(
            event_type="home_assistant.connection_gap_closed", source=gap_source
        )

        manager.disable(manifest.plugin_id)
        assert manager.list_tools(plugin_id=manifest.plugin_id) == []
        assert adapter.status.health == HAHealth.OFFLINE
        assert manager.enable(manifest.plugin_id).enabled is True
        plugin.stop()  # emulate process exit while persisted Phase 5 enablement remains true

        if db_container:
            docker("restart", db_container)
            time.sleep(2)
            migrate(database_url, 5)

        restored_adapter = HomeAssistantAdapter(config, reality, graph, ha_store)

        def restored_factory(current_token: str) -> HassClientConnection:
            return HassClientConnection(
                config,
                current_token,
                event_callback=restored_adapter.receive_provider_event,
                disconnect_callback=restored_adapter.disconnected,
            )

        restored_manager = PluginManager(
            journal=reality.journal,
            store=plugin_store,
            secret_broker=SecretBroker({"ANIMA_HA_TOKEN": token}),
        )
        restored_manager.restore(
            {
                manifest.plugin_id: NativeRuntime(
                    HomeAssistantPlugin(restored_adapter, restored_factory)
                )
            }
        )
        assert restored_adapter.status.health == HAHealth.ONLINE
        assert restored_manager.list_tools(plugin_id=manifest.plugin_id)
        restored_manager.disable(manifest.plugin_id)

        status_payload = json.dumps(ha_store.inventory(INSTANCE_ID), default=str)
        assert token not in status_payload
        assert TEST_PASSWORD not in status_payload
        assert token not in json.dumps(HAAdapterStatus(HAHealth.ONLINE).to_payload())

        ordinary = reality.projection.get(adapter._truth_key(entity_id))
        unknown = reality.projection.get(unknown_key)
        unavailable = reality.projection.get(unavailable_key)
        assert ordinary.value in {"on", "off"}
        assert unknown.observations[-1].state == ObservationState.UNKNOWN
        assert unavailable.observations[-1].state == ObservationState.UNAVAILABLE
        container_resources = docker(
            "stats",
            "--no-stream",
            "--format",
            "{{.CPUPerc}} cpu; {{.MemUsage}} memory",
            fixture.name,
            capture=True,
        )
        process_status = Path("/proc/self/status").read_text()
        process_rss = next(
            line.split(":", 1)[1].strip()
            for line in process_status.splitlines()
            if line.startswith("VmRSS:")
        )

        print("PHASE6_REAL_HOME_ASSISTANT_INTEGRATION_PASS")
        print(f"ha_version={discovery.version}")
        print(
            "discovery="
            f"states:{len(discovery.states)} services:{len(discovery.services)} "
            f"areas:{len(discovery.areas)} devices:{len(discovery.devices)} "
            f"entities:{len(discovery.entities)}"
        )
        print("mapping=area+device+entity MAPPED; many-to-one PASS; UNMAPPED preserved")
        print("truth=KNOWN+UNKNOWN+UNAVAILABLE PASS; state_changed=real websocket PASS")
        print("policy=DENY+CONFIRMATION+STRONGER_AUTH blocked before HA invocation")
        print("action=input_boolean.turn_on service call + observed state verification PASS")
        print("verification_fault=acknowledged-but-unobserved -> VERIFICATION_FAILED")
        print("disconnect+reconnect+resubscribe+reconcile+gap_honesty PASS")
        print("invalid_auth=AUTH_FAILED bounded retry PASS")
        print("disable+reenable+postgres_restart+persisted_restore PASS")
        print("secrets=runtime-only; no token/password persisted or printed")
        print(f"resources=ha_container:{container_resources}; harness_process_rss:{process_rss}")
        return 0
    finally:
        if manager is not None:
            for registered in list(manager.list_plugins(enabled_only=True)):
                try:
                    manager.disable(registered.manifest.plugin_id)
                except Exception:
                    pass
        token = ""
        fixture.close()


if __name__ == "__main__":
    raise SystemExit(main())
