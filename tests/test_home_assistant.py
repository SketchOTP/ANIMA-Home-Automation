from __future__ import annotations

from datetime import UTC, datetime
from types import SimpleNamespace
from typing import Any
from uuid import UUID, uuid4

import pytest

from anima_ha.events import ObservationState
from anima_ha.graph import CanonicalNode, NodeKind, ProviderReference, TargetKind
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
)
from anima_ha.plugins import (
    InvocationOutcome,
    NativeRuntime,
    PluginManager,
    SecretBroker,
)
from anima_ha.policy import Assurance, IdentityContext, PolicyService

NOW = datetime(2026, 8, 29, 18, 0, tzinfo=UTC)


class FakeReality:
    def __init__(self) -> None:
        self.events: list[Any] = []
        self.ids: set[str] = set()

    def ingest(self, event: Any, *, project: bool = True) -> tuple[Any, None]:
        if event.event_id not in self.ids:
            self.events.append(event)
            self.ids.add(event.event_id)
        return SimpleNamespace(deduplicated=event.event_id in self.ids), None


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
        return SimpleNamespace(
            created_nodes=len(document.nodes),
            created_relationships=len(document.relationships),
            created_provider_references=len(document.provider_references),
        )


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
        "permit_zigbee_join",
        "commission_device",
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


def test_pairing_window_uses_bounded_internal_zha_service(
    adapter_parts: tuple[HomeAssistantAdapter, FakeGraph, FakeReality, FakeStore],
) -> None:
    adapter, _, _, _ = adapter_parts
    connection = FakeConnection()
    adapter.start(connection)
    assert adapter.permit_zigbee_join(999)["duration_seconds"] == 120
    assert connection.data_calls == [("zha", "permit", {"duration": 120})]


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
            "device_id": "ha-device",
            "name": "SenseGuard Basement",
            "place_id": str(graph.place_id),
        },
        5.0,
        graph.household_id,
    )
    assert result["device_id"] == "ha-device"
    assert result["power_capability_count"] == 1
    assert graph.commissioned is not None
    assert len(store.objects) == 3


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
