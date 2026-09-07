from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from typing import Any
from uuid import UUID, uuid4

import pytest

from anima_ha.events import ObservationState, TruthObservation
from anima_ha.graph import (
    CanonicalNode,
    NodeKind,
    ProviderReference,
    TargetKind,
    validate_commissioning,
)
from anima_ha.home_assistant import (
    HAActionOutcome,
    HAAdapterError,
    HAAuthenticationError,
    HADiscoverySnapshot,
    HAHealth,
    HAInstanceConfig,
    HAMappingError,
    HomeAssistantAdapter,
    HomeAssistantPlugin,
    MappingStatus,
    home_assistant_manifest,
    inventory_handle,
)
from anima_ha.plugins import (
    InvocationContext,
    InvocationOutcome,
    NativeRuntime,
    PluginManager,
    PluginValidationError,
    SecretBroker,
)
from anima_ha.policy import Assurance, IdentityContext, PolicyService, RequestOrigin
from anima_ha.truth import InMemoryTruthState, TruthStatus

NOW = datetime(2026, 8, 29, 18, 0, tzinfo=UTC)


class FakeReality:
    def __init__(self) -> None:
        self.events: list[Any] = []
        self.ids: set[str] = set()
        self.projection = InMemoryTruthState()

    def ingest(self, event: Any, *, project: bool = True) -> tuple[Any, None]:
        deduplicated = event.event_id in self.ids
        if not deduplicated:
            self.events.append(event)
            self.ids.add(event.event_id)
            if project and event.event_type == "truth.observation":
                self.projection.add(
                    TruthObservation.from_payload(event.payload, event_id=event.event_id)
                )
        return SimpleNamespace(deduplicated=deduplicated), None


class FakeStore:
    def __init__(self) -> None:
        self.statuses: list[Any] = []
        self.objects: list[Any] = []

    def save_status(self, config: Any, status: Any, enabled: bool) -> None:
        self.statuses.append((config, status, enabled))

    def replace_inventory(self, instance_id: UUID, objects: list[Any], seen_at: Any) -> None:
        self.objects = list(objects)

    def inventory(self, instance_id: UUID) -> list[dict[str, Any]]:
        return [
            {
                "external_object_kind": item.kind,
                "external_id": item.external_id,
                "metadata": item.metadata,
                "present": True,
                "mapping_status": item.mapping_status.value,
            }
            for item in self.objects
        ]


class FakeGraph:
    def __init__(self, scope: str, resource_id: UUID, capability_id: UUID) -> None:
        self.scope = scope
        self.resource_id = resource_id
        self.capability_id = capability_id
        self.mapped: dict[tuple[str, str], Any] = {}
        self.references = [
            ProviderReference(
                uuid4(),
                "home_assistant",
                scope,
                "entity",
                "input_boolean.anima_test_power",
                capability_id,
                TargetKind.CAPABILITY,
            )
        ]

    def resolve_provider_reference(
        self, provider: str, scope: str, kind: str, external_id: str
    ) -> Any:
        return self.mapped.get((kind, external_id))

    def provider_references_for(self, target_id: UUID) -> list[ProviderReference]:
        return self.references if target_id in {self.resource_id, self.capability_id} else []


class CommissioningGraph(FakeGraph):
    def __init__(self, scope: str, resource_id: UUID, capability_id: UUID) -> None:
        super().__init__(scope, resource_id, capability_id)
        self.household_id = uuid4()
        self.place_id = uuid4()
        self.household = CanonicalNode(self.household_id, NodeKind.HOUSEHOLD, "Test household")
        self.place = CanonicalNode(self.place_id, NodeKind.ROOM, "Basement")
        self.commissioned: Any = None

    def get_node(self, canonical_id: UUID) -> CanonicalNode | None:
        return {self.household_id: self.household, self.place_id: self.place}.get(canonical_id)

    def places_in_household(self, household_id: UUID) -> list[CanonicalNode]:
        return [self.place] if household_id == self.household_id else []

    def commission(self, document: Any) -> Any:
        self.commissioned = document
        for node in document.nodes:
            if node.kind in {NodeKind.RESOURCE, NodeKind.SENSOR}:
                self.resource_id = node.canonical_id
        return SimpleNamespace(
            created_nodes=len(document.nodes),
            created_relationships=len(document.relationships),
            created_provider_references=len(document.provider_references),
        )


class LifecycleGraph(CommissioningGraph):
    def __init__(self, scope: str, resource_id: UUID, capability_id: UUID) -> None:
        super().__init__(scope, resource_id, capability_id)
        self.current_place = self.place_id
        self.renamed: list[tuple[UUID, str]] = []
        self.moved: list[tuple[UUID, UUID]] = []
        self.retired: list[UUID] = []
        self.other_place = uuid4()
        self.other_place_node = CanonicalNode(self.other_place, NodeKind.ROOM, "Office")

    def get_node(self, canonical_id: UUID) -> CanonicalNode | None:
        if canonical_id == self.other_place:
            return self.other_place_node
        if canonical_id == self.resource_id and self.commissioned is not None:
            return CanonicalNode(self.resource_id, NodeKind.RESOURCE, "SenseGuard Basement")
        return super().get_node(canonical_id)

    def places_in_household(self, household_id: UUID) -> list[CanonicalNode]:
        if household_id != self.household_id:
            return []
        return [self.place, self.other_place_node]

    def resources_in_place(self, place_id: UUID, recursive: bool = True) -> list[CanonicalNode]:
        del recursive
        if place_id == self.current_place and self.commissioned is not None:
            return [CanonicalNode(self.resource_id, NodeKind.RESOURCE, "SenseGuard Basement")]
        return []

    def rename_node(self, canonical_id: UUID, new_name: str) -> None:
        self.renamed.append((canonical_id, new_name))

    def move_resource(self, resource_id: UUID, place_id: UUID) -> None:
        self.current_place = place_id
        self.moved.append((resource_id, place_id))

    def retire_resource(self, resource_id: UUID) -> None:
        self.retired.append(resource_id)


def state(entity_id: str, value: str, stamp: str = "2026-08-29T18:00:00+00:00") -> dict[str, Any]:
    return {
        "entity_id": entity_id,
        "state": value,
        "last_changed": stamp,
        "last_updated": stamp,
        "attributes": {
            "friendly_name": "Synthetic Power",
            "access_token": "must-not-persist",
            "entity_picture": "https://signed.example/private",
        },
        "context": {"id": "context-1", "user_id": "test-user"},
    }


def snapshot(states: tuple[dict[str, Any], ...] | None = None) -> HADiscoverySnapshot:
    return HADiscoverySnapshot(
        version="2026.8.2",
        config={"location_name": "Mutable Test Name", "version": "2026.8.2"},
        states=states
        or (
            state("input_boolean.anima_test_power", "off"),
            state("sensor.anima_unknown", "unknown"),
            state("sensor.anima_unavailable", "unavailable"),
        ),
        services={"input_boolean": {"turn_on": {}, "turn_off": {}}},
        areas=({"area_id": "lab", "name": "Mutable Lab"},),
        devices=({"id": "ha-device", "name": "Provider Device", "area_id": "lab"},),
        entities=(
            {
                "entity_id": "input_boolean.anima_test_power",
                "device_id": "ha-device",
                "area_id": "lab",
                "platform": "input_boolean",
            },
        ),
    )


def presence_snapshot() -> HADiscoverySnapshot:
    return HADiscoverySnapshot(
        version="2026.8.2",
        config={"version": "2026.8.2"},
        states=(state("binary_sensor.hall_presence", "off"),),
        services={"zha": {"permit": {}}},
        areas=({"area_id": "lab", "name": "Mutable Lab"},),
        devices=({"id": "presence-device", "name": "ZHA Presence", "area_id": "lab"},),
        entities=(
            {
                "entity_id": "binary_sensor.hall_presence",
                "device_id": "presence-device",
                "area_id": "lab",
                "platform": "zha",
                "device_class": "presence",
            },
        ),
    )


class FakeConnection:
    def __init__(
        self,
        initial: HADiscoverySnapshot | None = None,
        *,
        buffered: list[dict[str, Any]] | None = None,
        observed_after_call: str = "on",
        start_error: Exception | None = None,
    ) -> None:
        self.version: str | None = "2026.8.2"
        self.connected = True
        self.initial = initial or snapshot()
        self.buffered = buffered or []
        self.observed_after_call = observed_after_call
        self.start_error = start_error
        self.calls: list[tuple[str, str, dict[str, Any]]] = []
        self.data_calls: list[tuple[str, str, dict[str, Any]]] = []
        self.config_flow_calls: list[tuple[str, str, dict[str, Any] | None]] = []
        self.config_flow_results: list[dict[str, Any]] = [
            {
                "flow_id": "ha-flow",
                "type": "form",
                "step_id": "choose_serial_port",
                "data_schema": [{"name": "device_path", "required": True, "type": "string"}],
            },
            {"type": "create_entry", "title": "ZHA", "result": {}},
        ]
        self.stopped = False

    def start(self) -> HADiscoverySnapshot:
        if self.start_error:
            raise self.start_error
        return self.initial

    def activate(self) -> list[dict[str, Any]]:
        return list(self.buffered)

    def stop(self) -> None:
        self.stopped = True
        self.connected = False

    def snapshot(self) -> HADiscoverySnapshot:
        return self.initial

    def call_service(self, domain: str, service: str, target: dict[str, Any]) -> dict[str, Any]:
        self.calls.append((domain, service, target))
        return {"context": {"id": "service-context"}}

    def call_service_data(self, domain: str, service: str, data: dict[str, Any]) -> dict[str, Any]:
        self.data_calls.append((domain, service, data))
        return {"context": {"id": "pairing-context"}}

    def get_state(self, entity_id: str) -> dict[str, Any] | None:
        value = self.observed_after_call if self.calls else "off"
        return state(entity_id, value, "2026-08-29T18:00:01+00:00")

    def ping(self) -> None:
        if not self.connected:
            raise HAAdapterError("offline")

    def start_config_flow(self, handler: str) -> dict[str, Any]:
        result = self.config_flow_results.pop(0)
        self.config_flow_calls.append((handler, "start", None))
        return result

    def continue_config_flow(self, flow_id: str, user_input: dict[str, Any]) -> dict[str, Any]:
        result = self.config_flow_results.pop(0)
        self.config_flow_calls.append((flow_id, "continue", user_input))
        return result


@pytest.fixture
def adapter_parts() -> tuple[HomeAssistantAdapter, FakeGraph, FakeReality, FakeStore]:
    instance_id, resource_id, capability_id = uuid4(), uuid4(), uuid4()
    config = HAInstanceConfig(
        instance_id,
        "ws://home-assistant.test/api/websocket",
        "ANIMA_HA_TOKEN",
        ssl=False,
        verification_timeout=0.01,
    )
    graph = FakeGraph(str(instance_id), resource_id, capability_id)
    reality, store = FakeReality(), FakeStore()
    adapter = HomeAssistantAdapter(config, reality, graph, store)  # type: ignore[arg-type]
    return adapter, graph, reality, store


def test_snapshot_normalizes_truth_and_keeps_unmapped_objects_explicit(
    adapter_parts: tuple[HomeAssistantAdapter, FakeGraph, FakeReality, FakeStore],
) -> None:
    adapter, _, reality, store = adapter_parts
    adapter.start(FakeConnection())
    observed = [event for event in reality.events if event.event_type == "truth.observation"]
    assert [event.payload["state"] for event in observed] == [
        ObservationState.KNOWN.value,
        ObservationState.UNKNOWN.value,
        ObservationState.UNAVAILABLE.value,
    ]
    assert all("must-not-persist" not in json_text(event.to_dict()) for event in observed)
    assert {item.mapping_status for item in store.objects} == {MappingStatus.UNMAPPED}
    assert adapter.status.health == HAHealth.ONLINE
    assert adapter.status.discovered_counts == {
        "states": 3,
        "services": 2,
        "areas": 1,
        "devices": 1,
        "entities": 1,
    }


def json_text(value: Any) -> str:
    import json

    return json.dumps(value, sort_keys=True, default=str)


def test_refresh_inventory_projects_opaque_device_handles(
    adapter_parts: tuple[HomeAssistantAdapter, FakeGraph, FakeReality, FakeStore],
) -> None:
    adapter, _, _, _ = adapter_parts
    adapter.start(FakeConnection())
    plugin = HomeAssistantPlugin(adapter, lambda token: FakeConnection())

    result = plugin.invoke_for_household("refresh_inventory", {}, 5.0, uuid4())

    assert result["provider"] == "home_assistant"
    assert len(result["items"]) == 1
    item = result["items"][0]
    assert item["device_handle"] == inventory_handle(
        adapter.config.instance_id, "device", "ha-device"
    )
    assert "external_id" not in item
    assert "device_id" not in item


def test_inspect_discovered_device_verifies_bounded_semantics_without_provider_ids(
    adapter_parts: tuple[HomeAssistantAdapter, FakeGraph, FakeReality, FakeStore],
) -> None:
    adapter, _, _, _ = adapter_parts
    door = state("binary_sensor.front_door", "on")
    door["attributes"] = {
        **door["attributes"],
        "friendly_name": "Front Door",
        "device_class": "door",
    }
    temperature = state("sensor.entry_temperature", "21.5")
    temperature["attributes"] = {
        **temperature["attributes"],
        "friendly_name": "Entry Temperature",
        "device_class": "temperature",
        "unit_of_measurement": "°C",
    }
    unclassified = state("sensor.unknown_value", "7")
    discovery = replace(
        snapshot(states=(door, temperature, unclassified)),
        devices=(
            {
                "id": "ha-device",
                "name": "Provider Device",
                "manufacturer": "Acme",
                "model": "Sensor Hub",
                "area_id": "lab",
            },
        ),
        entities=(
            {
                "entity_id": "binary_sensor.front_door",
                "device_id": "ha-device",
                "platform": "zha",
            },
            {
                "entity_id": "sensor.entry_temperature",
                "device_id": "ha-device",
                "platform": "zha",
            },
            {
                "entity_id": "sensor.unknown_value",
                "device_id": "ha-device",
                "platform": "zha",
            },
        ),
    )
    adapter.start(FakeConnection(initial=discovery))
    plugin = HomeAssistantPlugin(adapter, lambda token: FakeConnection())

    handle = inventory_handle(adapter.config.instance_id, "device", "ha-device")
    result = plugin.invoke_for_household("inspect_device", {"device_handle": handle}, 5.0, uuid4())

    assert result["status"] == "SUCCEEDED"
    assert result["device_handle"] == handle
    assert result["identity"] == {
        "name": "Provider Device",
        "manufacturer": "Acme",
        "model": "Sensor Hub",
    }
    assert [item["type"] for item in result["capabilities"]] == [
        "opening.state",
        "temperature.read",
        "state.read",
    ]
    assert [item["semantic_verification"] for item in result["capabilities"]] == [
        "VERIFIED",
        "VERIFIED",
        "GENERIC_FALLBACK",
    ]
    assert result["semantic_verification"] == {
        "status": "PARTIAL",
        "verified_count": 2,
        "capability_count": 3,
    }
    assert result["capabilities"][0]["state_status"] == "OBSERVED"
    assert result["capabilities"][0]["device_class"] == "door"
    assert result["capabilities"][1]["observed_state"] == "21.5"
    rendered = json_text(result)
    assert "ha-device" not in rendered
    assert "binary_sensor.front_door" not in rendered


def test_voice_presence_onboarding_qualifies_only_zha_presence_and_reuses_commissioning(
    adapter_parts: tuple[HomeAssistantAdapter, FakeGraph, FakeReality, FakeStore],
) -> None:
    _adapter, _graph, _reality, _store = adapter_parts
    instance_id = uuid4()
    config = HAInstanceConfig(
        instance_id,
        "ws://home-assistant.test/api/websocket",
        "ANIMA_HA_TOKEN",
        ssl=False,
        verification_timeout=0.01,
    )
    graph = CommissioningGraph(str(instance_id), uuid4(), uuid4())
    reality, store = FakeReality(), FakeStore()
    adapter = HomeAssistantAdapter(config, reality, graph, store)  # type: ignore[arg-type]
    connection = FakeConnection(initial=presence_snapshot())
    adapter.start(connection)
    plugin = HomeAssistantPlugin(adapter, lambda token: connection)
    handle = inventory_handle(instance_id, "device", "presence-device")

    inspected = plugin.invoke_for_household(
        "inspect_zigbee_presence_device", {"device_handle": handle}, 5.0, graph.household_id
    )
    assert inspected["classification"] == "ZIGBEE_PRESENCE_SENSOR"
    assert inspected["presence_entity_count"] == 1
    assert inspected["event_type"] == "presence.detected"
    assert "binary_sensor.hall_presence" not in json_text(inspected)

    commissioned = plugin.invoke_for_household(
        "commission_zigbee_presence_sensor",
        {"device_handle": handle, "name": "Hall Presence", "place_id": str(graph.place_id)},
        5.0,
        graph.household_id,
    )
    assert commissioned["entity_count"] == 1
    assert commissioned["place_id"] == str(graph.place_id)
    assert connection.data_calls == []


def test_voice_presence_onboarding_rejects_non_presence_discovery(
    adapter_parts: tuple[HomeAssistantAdapter, FakeGraph, FakeReality, FakeStore],
) -> None:
    adapter, _graph, _reality, _store = adapter_parts
    adapter.start(FakeConnection())
    plugin = HomeAssistantPlugin(adapter, lambda token: FakeConnection())
    handle = inventory_handle(adapter.config.instance_id, "device", "ha-device")
    with pytest.raises(PluginValidationError, match="ZIGBEE_PRESENCE_SENSOR_NOT_FOUND"):
        plugin.invoke_for_household(
            "inspect_zigbee_presence_device", {"device_handle": handle}, 5.0, uuid4()
        )


def test_snapshot_idempotency_and_buffered_newer_event(
    adapter_parts: tuple[HomeAssistantAdapter, FakeGraph, FakeReality, FakeStore],
) -> None:
    adapter, _, reality, _ = adapter_parts
    buffered = [
        {
            "event_type": "state_changed",
            "time_fired": "2026-08-29T18:00:01+00:00",
            "data": {
                "entity_id": "input_boolean.anima_test_power",
                "new_state": state(
                    "input_boolean.anima_test_power", "on", "2026-08-29T18:00:01+00:00"
                ),
            },
        }
    ]
    adapter.start(FakeConnection(buffered=buffered))
    initial_count = len(
        [event for event in reality.events if event.event_type == "truth.observation"]
    )
    adapter.reconcile()
    assert (
        len([event for event in reality.events if event.event_type == "truth.observation"])
        == initial_count
    )
    values = [
        event.payload.get("value")
        for event in reality.events
        if event.event_type == "truth.observation"
        and event.payload["truth_key"].endswith("anima_test_power/state")
    ]
    assert values == ["off", "on"]


def test_mapping_uses_provider_reference_not_name(
    adapter_parts: tuple[HomeAssistantAdapter, FakeGraph, FakeReality, FakeStore],
) -> None:
    adapter, graph, _, store = adapter_parts
    graph.mapped[("entity", "input_boolean.anima_test_power")] = SimpleNamespace(
        canonical_id=graph.capability_id, kind=NodeKind.CAPABILITY
    )
    adapter.start(FakeConnection())
    mapped = next(item for item in store.objects if item.kind == "entity")
    assert mapped.mapping_status == MappingStatus.MAPPED
    assert mapped.canonical_target_id == graph.capability_id
    assert all(
        item.mapping_status == MappingStatus.UNMAPPED
        for item in store.objects
        if item.kind != "entity"
    )


def test_disconnect_reconnect_gap_and_auth_failure(
    adapter_parts: tuple[HomeAssistantAdapter, FakeGraph, FakeReality, FakeStore],
) -> None:
    adapter, _, reality, _ = adapter_parts
    connection = FakeConnection()
    adapter.start(connection)
    adapter.disconnected("ConnectionClosed")
    assert adapter.status.health == HAHealth.OFFLINE
    assert adapter.reconnect(lambda: FakeConnection()) is True
    gap_types = {event.event_type for event in reality.events}
    assert "home_assistant.connection_gap_started" in gap_types
    assert "home_assistant.connection_gap_closed" in gap_types

    failed, graph, reality2, store = adapter_parts
    with pytest.raises(HAAuthenticationError):
        failed.start(FakeConnection(start_error=HAAuthenticationError("bad token")))
    assert failed.status.health == HAHealth.AUTH_FAILED
    assert "bad token" not in json_text(store.statuses)


def test_bounded_action_requires_observed_state(
    adapter_parts: tuple[HomeAssistantAdapter, FakeGraph, FakeReality, FakeStore],
) -> None:
    adapter, graph, _, _ = adapter_parts
    connection = FakeConnection(observed_after_call="on")
    adapter.start(connection)
    result = adapter.set_power(graph.resource_id, True, graph.capability_id)
    assert result.outcome == HAActionOutcome.SUCCESS
    assert result.service_acknowledged is True
    assert result.observed_state == "on"
    assert connection.calls == [
        (
            "input_boolean",
            "turn_on",
            {"entity_id": "input_boolean.anima_test_power"},
        )
    ]

    failed_adapter, failed_graph, _, _ = adapter_parts
    failed_connection = FakeConnection(observed_after_call="off")
    failed_adapter.start(failed_connection)
    failed_result = failed_adapter.set_power(
        failed_graph.resource_id, True, failed_graph.capability_id
    )
    assert failed_result.outcome == HAActionOutcome.VERIFICATION_FAILED
    assert failed_result.service_acknowledged is True


def test_canonical_mapping_must_be_unique(
    adapter_parts: tuple[HomeAssistantAdapter, FakeGraph, FakeReality, FakeStore],
) -> None:
    adapter, graph, _, _ = adapter_parts
    graph.references.append(
        ProviderReference(
            uuid4(),
            "home_assistant",
            graph.scope,
            "entity",
            "light.second_reference",
            graph.resource_id,
        )
    )
    adapter.start(FakeConnection())
    with pytest.raises(HAMappingError):
        adapter.set_power(graph.resource_id, True)


class DecisionEvaluator:
    def __init__(self, decision: str) -> None:
        self.decision = decision

    def evaluate(self, document: dict[str, Any]) -> dict[str, Any]:
        return {
            "decision": self.decision,
            "reason_code": f"TEST_{self.decision}",
            "policy_version": "phase4-v1",
            "required_assurance": "STRONG_AUTHENTICATED"
            if self.decision == "REQUIRE_STRONGER_AUTH"
            else None,
            "confirmation_required": self.decision == "REQUIRE_CONFIRMATION",
        }


def authenticated_identity(household_id: UUID) -> IdentityContext:
    return IdentityContext(
        household_id=household_id,
        principal_id=uuid4(),
        assurance=Assurance.AUTHENTICATED,
    )


@pytest.mark.parametrize(
    ("decision", "outcome"),
    [
        ("DENY", InvocationOutcome.POLICY_DENIED),
        ("REQUIRE_CONFIRMATION", InvocationOutcome.REQUIRE_CONFIRMATION),
        ("REQUIRE_STRONGER_AUTH", InvocationOutcome.REQUIRE_STRONGER_AUTH),
    ],
)
def test_policy_non_allow_never_calls_home_assistant(
    adapter_parts: tuple[HomeAssistantAdapter, FakeGraph, FakeReality, FakeStore],
    decision: str,
    outcome: InvocationOutcome,
) -> None:
    adapter, graph, _, _ = adapter_parts
    connection = FakeConnection()
    plugin = HomeAssistantPlugin(adapter, lambda token: connection)
    manager = PluginManager(secret_broker=SecretBroker({"ANIMA_HA_TOKEN": "fake-token"}))
    manager.register(
        home_assistant_manifest(adapter.config),
        NativeRuntime(plugin),
        configuration={
            "instance_id": str(adapter.config.instance_id),
            "websocket_url": adapter.config.websocket_url,
        },
    )
    manager.enable("anima.provider.home-assistant")
    household_id = uuid4()
    result = manager.invoke(
        "anima.provider.home-assistant.set_power",
        {
            "resource_id": str(graph.resource_id),
            "capability_id": str(graph.capability_id),
            "desired_on": True,
        },
        household_id=household_id,
        identity=authenticated_identity(household_id),
        policy_service=PolicyService(DecisionEvaluator(decision)),
    )
    assert result.outcome == outcome
    assert connection.calls == []


def test_allowed_gateway_invokes_once_and_disable_stops_adapter(
    adapter_parts: tuple[HomeAssistantAdapter, FakeGraph, FakeReality, FakeStore],
) -> None:
    adapter, graph, _, _ = adapter_parts
    connection = FakeConnection()
    plugin = HomeAssistantPlugin(adapter, lambda token: connection)
    manager = PluginManager(secret_broker=SecretBroker({"ANIMA_HA_TOKEN": "fake-token"}))
    manager.register(
        home_assistant_manifest(adapter.config),
        NativeRuntime(plugin),
        configuration={
            "instance_id": str(adapter.config.instance_id),
            "websocket_url": adapter.config.websocket_url,
        },
    )
    manager.enable("anima.provider.home-assistant")
    tools = {tool.name: tool for tool in manager.list_tools()}
    assert set(tools) == {
        "refresh_inventory",
        "reconnect",
        "start_zha_setup",
        "continue_zha_setup",
        "permit_zigbee_join",
        "inspect_device",
        "inspect_zigbee_presence_device",
        "commission_zigbee_presence_sensor",
        "commission_device",
        "rename_device",
        "reassign_device",
        "retire_device",
        "read_state",
        "set_power",
    }
    permit_boundary = tools["permit_zigbee_join"].execution_boundary
    commission_boundary = tools["commission_device"].execution_boundary
    assert permit_boundary is not None
    assert commission_boundary is not None
    assert permit_boundary.value == "POLICY_GATED_INTERNAL"
    assert commission_boundary.value == "POLICY_GATED_INTERNAL"
    assert all("call_service" not in tool.name for tool in manager.list_tools())
    household_id = uuid4()
    result = manager.invoke(
        "anima.provider.home-assistant.set_power",
        {
            "resource_id": str(graph.resource_id),
            "capability_id": str(graph.capability_id),
            "desired_on": True,
        },
        household_id=household_id,
        identity=authenticated_identity(household_id),
        policy_service=PolicyService(DecisionEvaluator("ALLOW")),
    )
    assert result.outcome == InvocationOutcome.SUCCESS
    assert len(connection.calls) == 1
    manager.disable("anima.provider.home-assistant")
    assert manager.list_tools() == []
    assert connection.stopped is True


def test_reconnect_is_core_owned_and_status_projection_is_secret_free(
    adapter_parts: tuple[HomeAssistantAdapter, FakeGraph, FakeReality, FakeStore],
) -> None:
    adapter, graph, _, _ = adapter_parts
    connections = [FakeConnection(), FakeConnection()]
    plugin = HomeAssistantPlugin(adapter, lambda token: connections.pop(0))
    plugin.start({"ANIMA_HA_TOKEN": "must-not-escape"})
    status = plugin.safe_status()
    assert status["health"] == "ONLINE"
    assert status["connected_version"] == "2026.8.2"
    assert "websocket_url" not in status
    assert "token" not in status

    result = plugin.invoke_for_household("reconnect", {}, 5.0, uuid4())
    assert result["status"] == "SUCCEEDED"
    assert result["health"]["health"] == "ONLINE"
    plugin.stop()


def test_zha_setup_is_bounded_core_owned_and_keeps_ha_flow_reference_private(
    adapter_parts: tuple[HomeAssistantAdapter, FakeGraph, FakeReality, FakeStore],
) -> None:
    adapter, _, _, _ = adapter_parts
    connection = FakeConnection()
    adapter.start(connection)
    plugin = HomeAssistantPlugin(adapter, lambda token: connection)

    started = plugin.invoke_for_household("start_zha_setup", {}, 5.0, uuid4())
    setup_id = str(started["setup_id"])
    assert started["status"] == "IN_PROGRESS"
    assert started["step_id"] == "choose_serial_port"
    assert "ha-flow" not in started

    with pytest.raises(PluginValidationError, match="outside the supported serial boundary"):
        plugin.invoke_for_household(
            "continue_zha_setup",
            {"setup_id": setup_id, "user_input": {"device_path": "/tmp/anything"}},
            5.0,
            uuid4(),
        )
    assert len(connection.config_flow_calls) == 1

    completed = plugin.invoke_for_household(
        "continue_zha_setup",
        {
            "setup_id": setup_id,
            "user_input": {"device_path": "/dev/serial/by-id/usb-sonoff-dongle"},
        },
        5.0,
        uuid4(),
    )
    assert completed["status"] == "SUCCEEDED"
    assert completed["state"] == "CONFIGURED"
    assert connection.config_flow_calls[-1] == (
        "ha-flow",
        "continue",
        {"device_path": "/dev/serial/by-id/usb-sonoff-dongle"},
    )


def test_pairing_window_uses_bounded_internal_zha_service(
    adapter_parts: tuple[HomeAssistantAdapter, FakeGraph, FakeReality, FakeStore],
) -> None:
    adapter, _, _, _ = adapter_parts
    connection = FakeConnection()
    adapter.start(connection)
    assert adapter.permit_zigbee_join(999)["duration_seconds"] == 120
    assert connection.data_calls == [("zha", "permit", {"duration": 120})]


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("off", TruthStatus.STALE),
        ("unknown", TruthStatus.UNKNOWN),
        ("unavailable", TruthStatus.UNAVAILABLE),
    ],
)
def test_late_truth_binding_preserves_evidence_and_deduplicates(
    adapter_parts: tuple[HomeAssistantAdapter, FakeGraph, FakeReality, FakeStore],
    value: str,
    expected: TruthStatus,
) -> None:
    adapter, graph, reality, _ = adapter_parts
    entity_id = "binary_sensor.senseguard_contact"
    raw = state(entity_id, value)
    original = adapter.normalize_state_event(raw)
    reality.ingest(original)
    original_payload = dict(original.payload)
    target = CanonicalNode(uuid4(), NodeKind.CAPABILITY, "Contact")
    graph.mapped[("entity", entity_id)] = target
    callbacks: list[Any] = []
    adapter.set_normalized_event_callback(callbacks.append)

    # The unchanged snapshot is still the same event, even after mapping.
    remapped = adapter.normalize_state_event(raw, snapshot=True)
    assert remapped.event_id == original.event_id
    assert remapped.source_event_id == original.source_event_id
    assert reality.ingest(remapped)[0].deduplicated
    canonical_key = adapter._truth_key(entity_id)
    assert reality.projection.get(canonical_key).status == TruthStatus.UNKNOWN

    adapter.seed_commissioned_truth(entity_id)
    adapter.seed_commissioned_truth(entity_id)
    assert len(reality.events) == 2
    assert reality.events[0].payload == original_payload
    attributed = reality.events[1]
    assert attributed.causation_id == original.event_id
    assert attributed.event_id != original.event_id
    assert attributed.occurred_at == original.occurred_at
    assert attributed.payload["metadata"]["binding_source_event_id"] == original.event_id
    for field in (
        "observed_at",
        "received_at",
        "freshness_seconds",
        "source",
        "state",
        "value",
        "confidence",
        "evidence_kind",
    ):
        assert attributed.payload[field] == original.payload[field]
    expired_at = NOW + timedelta(seconds=adapter.config.freshness_seconds + 1)
    assert reality.projection.get(canonical_key, now=expired_at).status == expected
    assert callbacks == []

    # A genuinely newer provider event wins; replay cannot roll it back.
    later = adapter.normalize_state_event(
        state(entity_id, "on", (expired_at + timedelta(seconds=1)).isoformat())
    )
    reality.ingest(later)
    adapter.seed_commissioned_truth(entity_id)
    current = reality.projection.get(canonical_key, now=later.occurred_at)
    assert current.status == TruthStatus.CURRENT_KNOWN
    assert current.value == "on"
    assert current.last_observed_at == later.occurred_at
    assert len(reality.events) == 3


def test_truth_binding_without_provider_observation_invents_nothing(
    adapter_parts: tuple[HomeAssistantAdapter, FakeGraph, FakeReality, FakeStore],
) -> None:
    adapter, graph, reality, _ = adapter_parts
    entity_id = "sensor.no_state"
    graph.mapped[("entity", entity_id)] = CanonicalNode(uuid4(), NodeKind.CAPABILITY, "No state")
    adapter.seed_commissioned_truth(entity_id)
    assert reality.events == []


def test_discovered_device_commissions_from_registry_into_canonical_graph(
    adapter_parts: tuple[HomeAssistantAdapter, FakeGraph, FakeReality, FakeStore],
) -> None:
    adapter, _, _, store = adapter_parts
    graph = CommissioningGraph(str(adapter.config.instance_id), uuid4(), uuid4())
    adapter.graph = graph  # type: ignore[assignment]
    adapter.start(FakeConnection())
    plugin = HomeAssistantPlugin(adapter, lambda token: FakeConnection())
    result = plugin.invoke_for_household(
        "commission_device",
        {
            "device_handle": inventory_handle(adapter.config.instance_id, "device", "ha-device"),
            "name": "SenseGuard Basement",
            "place_id": str(graph.place_id),
        },
        5.0,
        graph.household_id,
    )
    assert result["device_handle"] == inventory_handle(
        adapter.config.instance_id, "device", "ha-device"
    )
    assert "device_id" not in result
    assert result["power_capability_count"] == 1
    assert graph.commissioned is not None
    assert len(store.objects) == 3


@pytest.mark.parametrize("sparse_current_registry", [False, True])
@pytest.mark.parametrize("decision", ["ALLOW", "DENY"])
def test_commission_device_through_trusted_ui_invocation_context(
    adapter_parts: tuple[HomeAssistantAdapter, FakeGraph, FakeReality, FakeStore],
    sparse_current_registry: bool,
    decision: str,
) -> None:
    adapter, _, _, _ = adapter_parts
    graph = CommissioningGraph(str(adapter.config.instance_id), uuid4(), uuid4())
    adapter.graph = graph  # type: ignore[assignment]
    discovery = snapshot()
    if sparse_current_registry:
        # Synthetic current registry shape: optional names, manufacturer,
        # model, area, platform and legacy config_entries may all be absent.
        adapter.config = replace(adapter.config, expected_version="2026.9.0")
        discovery = replace(
            discovery,
            version="2026.9.0",
            config={"version": "2026.9.0"},
            devices=({"id": "ha-device", "config_entry_id": "zha-entry"},),
            entities=({"entity_id": "binary_sensor.presence", "device_id": "ha-device"},),
            states=(state("binary_sensor.presence", "off"),),
        )
    connection = FakeConnection(initial=discovery)
    manager = PluginManager(secret_broker=SecretBroker({"ANIMA_HA_TOKEN": "fake-token"}))
    manager.register(
        home_assistant_manifest(adapter.config),
        NativeRuntime(HomeAssistantPlugin(adapter, lambda token: connection)),
        configuration={
            "instance_id": str(adapter.config.instance_id),
            "websocket_url": adapter.config.websocket_url,
        },
    )
    manager.enable("anima.provider.home-assistant")
    identity = authenticated_identity(graph.household_id)
    handle = inventory_handle(adapter.config.instance_id, "device", "ha-device")
    try:
        result = manager.invoke(
            "anima.provider.home-assistant.commission_device",
            {
                "device_handle": handle,
                "name": "SenseGuard Basement",
                "place_id": str(graph.place_id),
            },
            household_id=graph.household_id,
            identity=identity,
            origin=RequestOrigin.DIRECT_USER,
            policy_service=PolicyService(DecisionEvaluator(decision)),
            invocation_context=InvocationContext(
                household_id=graph.household_id,
                principal_id=identity.principal_id,
                episode_id=None,
                tool_request_id=uuid4(),
                ordinal=1,
                system_idempotency_key=f"ui:test-commission:{uuid4()}",
                origin=RequestOrigin.DIRECT_USER,
            ),
        )
        assert connection.calls == []
        assert connection.data_calls == []
        if decision == "DENY":
            assert result.outcome == InvocationOutcome.POLICY_DENIED
            assert graph.commissioned is None
            return
        assert result.outcome == InvocationOutcome.SUCCESS, result.error_class
        assert result.policy_decision is not None
        assert result.policy_decision.reason_code == "TEST_ALLOW"
        assert result.result["device_handle"] == handle
        assert result.result["entity_count"] == 1
        assert result.result["power_capability_count"] == (0 if sparse_current_registry else 1)
        assert graph.commissioned is not None
        validate_commissioning(graph.commissioned)
        assert len(graph.commissioned.provider_references) == 2
        assert len(graph.commissioned.truth_bindings) == 1
        device_node = next(
            node for node in graph.commissioned.nodes if node.name == "SenseGuard Basement"
        )
        assert device_node.kind == (
            NodeKind.SENSOR if sparse_current_registry else NodeKind.RESOURCE
        )
    finally:
        manager.disable("anima.provider.home-assistant")


def test_commissioned_device_lifecycle_stays_household_scoped(
    adapter_parts: tuple[HomeAssistantAdapter, FakeGraph, FakeReality, FakeStore],
) -> None:
    adapter, _, _, _ = adapter_parts
    graph = LifecycleGraph(str(adapter.config.instance_id), uuid4(), uuid4())
    adapter.graph = graph  # type: ignore[assignment]
    adapter.start(FakeConnection())
    plugin = HomeAssistantPlugin(adapter, lambda token: FakeConnection())
    plugin.invoke_for_household(
        "commission_device",
        {
            "device_handle": inventory_handle(adapter.config.instance_id, "device", "ha-device"),
            "name": "SenseGuard Basement",
            "place_id": str(graph.place_id),
        },
        5.0,
        graph.household_id,
    )

    renamed = plugin.invoke_for_household(
        "rename_device",
        {"resource_id": str(graph.resource_id), "name": "SenseGuard Lower Level"},
        5.0,
        graph.household_id,
    )
    moved = plugin.invoke_for_household(
        "reassign_device",
        {"resource_id": str(graph.resource_id), "place_id": str(graph.other_place)},
        5.0,
        graph.household_id,
    )
    retired = plugin.invoke_for_household(
        "retire_device", {"resource_id": str(graph.resource_id)}, 5.0, graph.household_id
    )

    assert renamed["name"] == "SenseGuard Lower Level"
    assert moved["place_id"] == str(graph.other_place)
    assert retired["operation"] == "retire_device"
    assert graph.renamed == [(graph.resource_id, "SenseGuard Lower Level")]
    assert graph.moved == [(graph.resource_id, graph.other_place)]
    assert graph.retired == [graph.resource_id]

    with pytest.raises(PluginValidationError, match="not in the commissioned household"):
        plugin.invoke_for_household(
            "rename_device",
            {"resource_id": str(graph.resource_id), "name": "Nope"},
            5.0,
            uuid4(),
        )


def test_current_home_assistant_device_registry_fields_are_preserved(
    adapter_parts: tuple[HomeAssistantAdapter, FakeGraph, FakeReality, FakeStore],
) -> None:
    adapter, _, _, _ = adapter_parts
    child = adapter._provider_object(
        "device",
        {
            "id": "child-device",
            "name": "SenseGuard child",
            "parent_device_id": "parent-device",
            "config_entry_id": "entry-2026",
            "config_subentry_id": "subentry-2026",
        },
    )
    assert child.metadata["parent_device_id"] == "parent-device"
    assert child.metadata["config_entry_id"] == "entry-2026"
    assert child.metadata["config_subentry_id"] == "subentry-2026"
    assert child.metadata["is_child_device"] is True


def test_verification_failure_is_not_gateway_success(
    adapter_parts: tuple[HomeAssistantAdapter, FakeGraph, FakeReality, FakeStore],
) -> None:
    adapter, graph, _, _ = adapter_parts
    connection = FakeConnection(observed_after_call="off")
    manager = PluginManager(secret_broker=SecretBroker({"ANIMA_HA_TOKEN": "fake-token"}))
    manager.register(
        home_assistant_manifest(adapter.config),
        NativeRuntime(HomeAssistantPlugin(adapter, lambda token: connection)),
        configuration={
            "instance_id": str(adapter.config.instance_id),
            "websocket_url": adapter.config.websocket_url,
        },
    )
    manager.enable("anima.provider.home-assistant")
    household_id = uuid4()
    result = manager.invoke(
        "anima.provider.home-assistant.set_power",
        {"resource_id": str(graph.resource_id), "desired_on": True},
        household_id=household_id,
        identity=authenticated_identity(household_id),
        policy_service=PolicyService(DecisionEvaluator("ALLOW")),
    )
    assert result.outcome == InvocationOutcome.VERIFICATION_FAILED
    assert result.result["outcome"] == HAActionOutcome.VERIFICATION_FAILED.value


def test_version_mismatch_fails_closed(
    adapter_parts: tuple[HomeAssistantAdapter, FakeGraph, FakeReality, FakeStore],
) -> None:
    adapter, _, _, _ = adapter_parts
    wrong = HADiscoverySnapshot("2026.9.0", {}, (), {}, (), (), ())
    with pytest.raises(HAAdapterError, match="version mismatch"):
        adapter.start(FakeConnection(initial=wrong))
    assert adapter.status.health == HAHealth.OFFLINE
