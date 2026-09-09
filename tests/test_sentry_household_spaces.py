"""Real SENTRY/PluginManager/policy path with a synthetic graph, never live HA."""

from dataclasses import replace
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from typing import Any, cast
from uuid import UUID, uuid4

import pytest

from anima_ha.external import external_manifests
from anima_ha.graph import NodeKind
from anima_ha.home_assistant import HAInstanceConfig, home_assistant_manifest
from anima_ha.household_spaces import HOUSEHOLD_SPACES_MANIFEST, HouseholdSpacesNativePlugin
from anima_ha.intelligence import (
    IntelligenceLifecycle,
    IntelligenceOrigin,
    IntelligenceRequestFactory,
)
from anima_ha.plugins import (
    ExecutionBoundary,
    PluginManager,
    RuntimeKind,
    ToolDescriptor,
    TrustClass,
)
from anima_ha.policy import PolicyService
from anima_ha.sentry_boundary import CoreSentryBoundary

WRITES = ("create_space", "rename_space", "move_space", "remove_space")


def test_ha_power_and_notification_boundaries_are_unchanged() -> None:
    manifest = home_assistant_manifest(
        HAInstanceConfig(
            uuid4(),
            "ws://synthetic.invalid/api/websocket",
            "SYNTHETIC_NOT_READ",
        )
    )
    internal = {
        "permit_zigbee_join",
        "commission_zigbee_presence_sensor",
        "commission_device",
        "commission_presence_source",
    }
    for item in manifest.tools:
        expected = (
            ExecutionBoundary.POLICY_GATED_INTERNAL
            if item["name"] in internal
            else ExecutionBoundary.READ_ONLY
            if item.get("read_only")
            else ExecutionBoundary.COORDINATED_CONSEQUENTIAL
        )
        assert ToolDescriptor.from_manifest(manifest, item).execution_boundary == expected
    notifications = next(
        m for m in external_manifests() if m.plugin_id == "anima.external.notifications"
    )
    for item in notifications.tools:
        assert ToolDescriptor.from_manifest(notifications, item).execution_boundary == (
            ExecutionBoundary.COORDINATED_CONSEQUENTIAL
        )


class Graph:
    def __init__(self, household: UUID):
        self.household = household
        self.writes: list[str] = []

    def get_node(self, key: UUID) -> Any:
        assert key == self.household
        return SimpleNamespace(canonical_id=key, name="Home", kind=NodeKind.HOUSEHOLD)

    def places_in_household(self, household: UUID) -> list[Any]:
        assert household == self.household
        return []

    def parent_of_place(self, household: UUID, place: UUID) -> UUID:
        assert household == self.household
        return household

    def _write(self, operation: str, household: UUID) -> Any:
        assert household == self.household
        self.writes.append(operation)
        return SimpleNamespace(canonical_id=uuid4(), name="Synthetic room", kind=NodeKind.ROOM)

    def create_place(self, household: UUID, parent: UUID, name: str, kind: NodeKind) -> Any:
        assert parent == household
        return self._write("create_space", household)

    def rename_place(self, household: UUID, place: UUID, name: str) -> Any:
        return self._write("rename_space", household)

    def move_place(self, household: UUID, place: UUID, parent: UUID) -> Any:
        return self._write("move_space", household)

    def retire_place(self, household: UUID, place: UUID) -> Any:
        return self._write("remove_space", household)


class Evaluator:
    def __init__(self, decision: str):
        self.decision = decision
        self.documents: list[dict[str, Any]] = []

    def evaluate(self, document: dict[str, Any]) -> dict[str, Any]:
        self.documents.append(document)
        return {"decision": self.decision, "reason_code": "TEST_POLICY", "policy_version": "test"}


@pytest.mark.parametrize("name", WRITES)
@pytest.mark.parametrize("decision", ["ALLOW", "DENY"])
def test_sentry_space_writes_obey_real_policy_gate(name: str, decision: str) -> None:
    household = uuid4()
    graph = Graph(household)
    manager = PluginManager()
    manager.register(HOUSEHOLD_SPACES_MANIFEST, HouseholdSpacesNativePlugin(cast(Any, graph)))
    manager.enable(HOUSEHOLD_SPACES_MANIFEST.plugin_id)
    request = IntelligenceRequestFactory.for_trigger(
        uuid4(),
        household_id=household,
        origin=IntelligenceOrigin.DIRECT_UI_USER,
        context_packet_id=uuid4(),
        context_digest="synthetic",
        tools=manager.list_tools(),
        provider_id="sentry",
        provider_version="1",
        principal_id=uuid4(),
    )
    request = replace(
        request,
        lifecycle=IntelligenceLifecycle.PROVIDER_RUNNING,
        claim_owner="synthetic-worker",
        fencing_generation=1,
        lease_expires_at=datetime.now(UTC) + timedelta(minutes=2),
        provider_invocation_started=True,
    )
    evaluator = Evaluator("ALLOW")
    boundary = CoreSentryBoundary(
        manager,
        PolicyService(evaluator),
        cast(Any, SimpleNamespace(get=lambda _: request)),
        # A wrong classification must not accidentally fall back to the manager.
        action_executor=SimpleNamespace(execute=lambda _: pytest.fail("coordinator must not run")),
    )
    discovery = boundary.invoke_tool(
        request,
        "anima.household-spaces.list_spaces",
        {},
        ordinal=1,
    )
    assert discovery["status"] == "SUCCEEDED"
    parent = discovery["result"]["items"][0]["place_id"]
    assert parent == str(household)
    evaluator.decision = decision
    arguments = {
        "create_space": {"name": "Synthetic room", "kind": "ROOM", "parent_id": parent},
        "rename_space": {"place_id": str(uuid4()), "name": "Synthetic room"},
        "move_space": {"place_id": str(uuid4()), "parent_id": parent},
        "remove_space": {"place_id": str(uuid4())},
    }[name]
    result = boundary.invoke_tool(request, f"anima.household-spaces.{name}", arguments, ordinal=2)
    assert result["status"] == ("SUCCEEDED" if decision == "ALLOW" else "DENIED")
    assert graph.writes == ([name] if decision == "ALLOW" else [])
    assert len(evaluator.documents) == 2


@pytest.mark.parametrize("name", WRITES)
def test_only_exact_space_tool_and_trusted_source_pair_is_internal(name: str) -> None:
    manifest = HOUSEHOLD_SPACES_MANIFEST
    item = next(t for t in manifest.tools if t["name"] == name)
    descriptor = ToolDescriptor.from_manifest(manifest, item)
    assert descriptor.execution_boundary == ExecutionBoundary.POLICY_GATED_INTERNAL
    assert descriptor.read_only is False
    assert descriptor.risk_class == "SECURITY_SECURE_ACTION"
    for source in ("local", "builtin:anima_ha.tasks", "builtin:anima_ha.home_assistant"):
        assert ToolDescriptor.from_manifest(
            replace(manifest, source=source), item
        ).execution_boundary == (ExecutionBoundary.COORDINATED_CONSEQUENTIAL)
    external = replace(
        manifest, runtime_kind=RuntimeKind.MCP_STDIO, trust_class=TrustClass.OPTIONAL_EXTERNAL
    )
    assert ToolDescriptor.from_manifest(external, item).execution_boundary == (
        ExecutionBoundary.COORDINATED_CONSEQUENTIAL
    )
    unknown = {**item, "name": "unknown_mutation", "execution_boundary": "POLICY_GATED_INTERNAL"}
    assert ToolDescriptor.from_manifest(manifest, unknown).execution_boundary == (
        ExecutionBoundary.COORDINATED_CONSEQUENTIAL
    )
    wrong_namespace = replace(manifest, plugin_id="anima.external.space-spoof")
    assert ToolDescriptor.from_manifest(wrong_namespace, item).execution_boundary == (
        ExecutionBoundary.COORDINATED_CONSEQUENTIAL
    )
