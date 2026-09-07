"""Canonical resource lookup, isolated from live HA and household accounts."""

from __future__ import annotations

import json
import os
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from typing import Any, cast
from uuid import UUID, uuid4

import jsonschema
import psycopg
import pytest
from test_sentry_household_spaces import Evaluator

from anima_ha.db.migrate import migrate
from anima_ha.graph import (
    CanonicalNode,
    CanonicalRelationship,
    CommissioningDocument,
    NodeKind,
    PostgresHouseholdGraph,
    RelationshipType,
)
from anima_ha.household_spaces import HOUSEHOLD_SPACES_MANIFEST, HouseholdSpacesNativePlugin
from anima_ha.intelligence import (
    IntelligenceLifecycle,
    IntelligenceOrigin,
    IntelligenceRequestFactory,
)
from anima_ha.plugins import (
    ExecutionBoundary,
    InvocationContext,
    PluginManager,
    PluginValidationError,
)
from anima_ha.policy import PolicyService, RequestOrigin
from anima_ha.sentry_boundary import CoreSentryBoundary


def context(household: UUID) -> InvocationContext:
    return InvocationContext(
        household, uuid4(), None, uuid4(), 1, "lookup", RequestOrigin.DIRECT_USER
    )


class Graph:
    def __init__(self) -> None:
        self.root = CanonicalNode(uuid4(), NodeKind.HOUSEHOLD, "Synthetic home")
        self.room = CanonicalNode(uuid4(), NodeKind.ROOM, "Synthetic room")
        self.resources = [
            CanonicalNode(UUID(int=index), NodeKind.SENSOR, f"Device {index}")
            for index in (3, 1, 2, 1)
        ]
        self.capabilities = [
            CanonicalNode(
                UUID(int=100 + index),
                NodeKind.CAPABILITY,
                f"Capability {index}",
                metadata={"capability_type": f"sensor.{index}", "provider_entity_id": "PRIVATE"},
            )
            for index in range(6)
        ]
        self.reads: list[UUID] = []

    def get_node(self, key: UUID) -> CanonicalNode | None:
        return self.root if key == self.root.canonical_id else None

    def places_in_household(self, household: UUID) -> list[CanonicalNode]:
        assert household == self.root.canonical_id
        return [self.room]

    def resources_in_place(self, place: UUID) -> list[CanonicalNode]:
        assert place in {self.root.canonical_id, self.room.canonical_id}
        self.reads.append(place)
        return self.resources

    def resource_capabilities(self, resource: UUID) -> list[CanonicalNode]:
        assert resource in {node.canonical_id for node in self.resources}
        return self.capabilities + [self.capabilities[0]]


def lookup(graph: Any, arguments: dict[str, Any], household: UUID | None = None) -> Any:
    return HouseholdSpacesNativePlugin(graph).invoke_with_invocation_context(
        "list_resources", arguments, 5, context(household or graph.root.canonical_id)
    )


def test_scoped_keyset_pagination_deduplicates_and_preserves_six_capabilities() -> None:
    graph = Graph()
    first = lookup(graph, {"limit": 1})
    assert first["items"][0]["resource_id"] == str(UUID(int=1))
    assert len(first["items"][0]["capabilities"]) == 6
    assert first["items"][0]["capabilities_truncated"] is False
    # Renaming/removing a preceding item cannot shift an offset or repeat a page.
    graph.resources = [
        replace(n, name="Renamed") for n in graph.resources if n.canonical_id.int != 1
    ]
    second = lookup(graph, {"limit": 50, "cursor": first["next_cursor"]})
    assert [item["resource_id"] for item in second["items"]] == [str(UUID(int=i)) for i in (2, 3)]
    assert second["next_cursor"] is None
    assert "PRIVATE" not in json.dumps(first)
    assert all(
        set(c) == {"capability_id", "name", "type"} for c in first["items"][0]["capabilities"]
    )
    assert lookup(graph, {"place_id": str(graph.room.canonical_id)})["items"]
    assert graph.reads[-1] == graph.room.canonical_id


@pytest.mark.parametrize("limit", [0, 51, True, "2", 1.5, None])
def test_rejects_invalid_limits_before_graph_read(limit: Any) -> None:
    graph = Graph()
    with pytest.raises(PluginValidationError):
        lookup(graph, {"limit": limit})
    assert graph.reads == []


def test_default_and_maximum_pages_do_not_dump_large_inventory() -> None:
    graph = Graph()
    graph.resources = [
        CanonicalNode(UUID(int=i), NodeKind.RESOURCE, f"Resource {i}") for i in range(1, 55)
    ]
    assert len(lookup(graph, {})["items"]) == 20
    first = lookup(graph, {"limit": 50})
    assert len(first["items"]) == 50
    assert first["next_cursor"]
    last = lookup(graph, {"limit": 50, "cursor": first["next_cursor"]})
    assert len(last["items"]) == 4
    assert last["next_cursor"] is None
    assert not {r["resource_id"] for r in first["items"]} & {
        r["resource_id"] for r in last["items"]
    }


def test_foreign_place_cursor_and_authority_arguments_are_rejected() -> None:
    graph = Graph()
    page = lookup(graph, {"limit": 1})
    for arguments in (
        {"place_id": str(uuid4())},
        {"place_id": "invalid"},
        {"household_id": str(uuid4())},
        {"cursor": page["next_cursor"], "place_id": str(graph.room.canonical_id)},
        {"cursor": page["next_cursor"].replace(str(graph.root.canonical_id), str(uuid4()), 1)},
        {"cursor": "invalid"},
        {"cursor": page["next_cursor"].rsplit("/", 1)[0] + "/not-a-uuid"},
        {"cursor": None},
    ):
        graph.reads.clear()
        with pytest.raises(PluginValidationError):
            lookup(graph, arguments)
        assert graph.reads == []
    with pytest.raises(PluginValidationError):
        lookup(graph, {}, uuid4())
    graph.root = replace(graph.root, retired_at=datetime.now(UTC))
    with pytest.raises(PluginValidationError):
        lookup(graph, {})
    with pytest.raises(PluginValidationError):
        HouseholdSpacesNativePlugin(cast(Any, graph)).invoke("list_resources", {}, 1)


def test_empty_retired_and_bounded_output_validate_against_manifest() -> None:
    graph = Graph()
    graph.resources += [CanonicalNode(UUID(int=4), NodeKind.PERSON, "Not a device")]
    graph.resources += [
        replace(graph.resources[0], canonical_id=UUID(int=5), retired_at=datetime.now(UTC))
    ]
    graph.capabilities += [
        CanonicalNode(
            UUID(int=200 + i),
            NodeKind.CAPABILITY,
            "X" * 200,
            metadata={"capability_type": {"private": "PRIVATE"}},
        )
        for i in range(60)
    ]
    graph.capabilities += [
        replace(graph.capabilities[0], canonical_id=UUID(int=90), retired_at=datetime.now(UTC)),
        CanonicalNode(UUID(int=91), NodeKind.PERSON, "Not a capability"),
    ]
    page = lookup(graph, {})
    assert len(page["items"]) == 3
    assert len(page["items"][0]["capabilities"]) == 50
    assert page["items"][0]["capabilities_truncated"] is True
    assert page["items"][0]["capabilities"][-1]["type"] is None
    tool = next(t for t in HOUSEHOLD_SPACES_MANIFEST.tools if t["name"] == "list_resources")
    jsonschema.validate(page, tool["output_schema"])
    for arguments in ({"limit": 51}, {"household_id": str(uuid4())}, {"provider_id": "PRIVATE"}):
        with pytest.raises(jsonschema.ValidationError):
            jsonschema.validate(arguments, tool["input_schema"])
    graph.resources = []
    assert lookup(graph, {}) == {"status": "SUCCEEDED", "items": [], "next_cursor": None}


def test_manifest_reaches_frozen_sentry_catalogue_and_read_only_execution() -> None:
    graph = Graph()
    manager = PluginManager()
    manager.register(HOUSEHOLD_SPACES_MANIFEST, HouseholdSpacesNativePlugin(cast(Any, graph)))
    manager.enable(HOUSEHOLD_SPACES_MANIFEST.plugin_id)
    tool = next(t for t in manager.list_tools() if t.name == "list_resources")
    assert tool.execution_boundary == ExecutionBoundary.READ_ONLY
    assert tool.read_only and tool.risk_class == "READ_ONLY"
    request = IntelligenceRequestFactory.for_trigger(
        uuid4(),
        household_id=graph.root.canonical_id,
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
        claim_owner="synthetic",
        fencing_generation=1,
        lease_expires_at=datetime.now(UTC) + timedelta(minutes=2),
        provider_invocation_started=True,
    )
    boundary = CoreSentryBoundary(
        manager,
        PolicyService(Evaluator("ALLOW")),
        cast(Any, SimpleNamespace(get=lambda _: request)),
        action_executor=SimpleNamespace(execute=lambda _: pytest.fail("must remain read only")),
    )
    assert any(
        t["tool_id"] == tool.tool_id and t["availability"] for t in boundary.catalogue(request)
    )
    result = boundary.invoke_tool(request, tool.tool_id, {"limit": 1}, ordinal=1)
    assert result["status"] == "SUCCEEDED"
    assert len(result["result"]["items"][0]["capabilities"]) == 6


def test_real_postgres_scopes_and_deduplicates_commissioned_resources() -> None:
    database_url = os.environ.get("ANIMA_LATE_BINDING_TEST_DATABASE_URL")
    if not database_url:
        pytest.skip("requires existing disposable ANIMA_LATE_BINDING_TEST_DATABASE_URL fixture")
    with psycopg.connect(database_url) as connection:
        assert connection.execute("SELECT current_database()").fetchone() == (
            "anima_late_binding_test",
        )
    migrate(database_url, 5)
    graph = PostgresHouseholdGraph(database_url)
    home = CanonicalNode(uuid4(), NodeKind.HOUSEHOLD, "Synthetic lookup home")
    foreign = CanonicalNode(uuid4(), NodeKind.HOUSEHOLD, "Foreign synthetic home")
    room = CanonicalNode(uuid4(), NodeKind.ROOM, "Synthetic room")
    other = CanonicalNode(uuid4(), NodeKind.ROOM, "Other synthetic room")
    device = CanonicalNode(uuid4(), NodeKind.SENSOR, "Synthetic six-capability sensor")
    foreign_device = CanonicalNode(uuid4(), NodeKind.SENSOR, "Foreign sensor")
    caps = tuple(
        CanonicalNode(
            uuid4(),
            NodeKind.CAPABILITY,
            f"Sensor {i}",
            metadata={"capability_type": f"sensor.{i}", "provider_entity_id": "PRIVATE"},
        )
        for i in range(6)
    )
    edges = [
        (RelationshipType.CONTAINS, home, room),
        (RelationshipType.CONTAINS, foreign, other),
        (RelationshipType.INSTALLED_IN, device, home),
        (RelationshipType.INSTALLED_IN, device, room),
        (RelationshipType.INSTALLED_IN, foreign_device, other),
    ] + [(RelationshipType.EXPOSES, device, cap) for cap in caps]
    graph.commission(
        CommissioningDocument(
            1,
            (home, foreign, room, other, device, foreign_device, *caps),
            tuple(
                CanonicalRelationship(uuid4(), kind, source.canonical_id, target.canonical_id)
                for kind, source, target in edges
            ),
        )
    )
    page = lookup(graph, {}, home.canonical_id)
    assert [item["resource_id"] for item in page["items"]] == [str(device.canonical_id)]
    assert {c["capability_id"] for c in page["items"][0]["capabilities"]} == {
        str(c.canonical_id) for c in caps
    }
    assert "PRIVATE" not in json.dumps(page)
    assert lookup(graph, {"place_id": str(room.canonical_id)}, home.canonical_id) == page
    with pytest.raises(PluginValidationError):
        lookup(graph, {"place_id": str(other.canonical_id)}, home.canonical_id)
