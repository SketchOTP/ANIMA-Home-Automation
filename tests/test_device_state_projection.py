"""Shared Home/inventory semantic selection; synthetic Truth, no provider I/O."""

import json
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from typing import Any, cast
from unittest.mock import patch
from uuid import UUID, uuid4

import pytest

from anima_ha.events import EvidenceKind, ObservationState, TruthObservation
from anima_ha.graph import NodeKind
from anima_ha.truth import TruthResolution, TruthStatus
from anima_ha.ui_api import PostgresHouseholdReadModel, device_capability_projection
from anima_ha.ui_runtime import CoreUICommandGateway

NOW = datetime.now(UTC)


def capability(
    domain: str,
    device_class: str | None,
    value: Any,
    *,
    status: TruthStatus = TruthStatus.CURRENT_KNOWN,
    explicit_class: bool = False,
) -> tuple[Any, TruthResolution]:
    key = uuid4()
    node = SimpleNamespace(
        canonical_id=key,
        name="Synthetic capability",
        metadata={
            "capability_type": "power.set" if domain == "switch" else "state.read",
            "provider_entity_id": f"{domain}.private_provider_reference",
            "readable": True,
            "writable": domain == "switch",
        },
    )
    if explicit_class and device_class is not None:
        node.metadata["provider_device_class"] = device_class
    observed = NOW - timedelta(hours=1) if status == TruthStatus.STALE else NOW
    observation = TruthObservation(
        str(key),
        "synthetic-provider",
        observed,
        observed,
        value=value,
        freshness_seconds=60,
        metadata={"attributes": {"device_class": device_class} if device_class else {}},
    )
    resolution = TruthResolution(
        str(key),
        status,
        value=value,
        observations=(observation,),
        last_observed_at=observed,
    )
    return node, resolution


class Graph:
    def __init__(self, entries: list[tuple[Any, TruthResolution]]):
        self.entries = entries
        self.root = SimpleNamespace(canonical_id=uuid4(), name="Home", kind=NodeKind.HOUSEHOLD)
        self.room = SimpleNamespace(canonical_id=uuid4(), name="Synthetic room", kind=NodeKind.ROOM)
        self.resource = SimpleNamespace(
            canonical_id=uuid4(), name="Synthetic device", kind=NodeKind.SENSOR
        )

    def get_node(self, key: UUID) -> Any:
        return next(
            (n for n in (self.root, self.room, self.resource) if n.canonical_id == key), None
        )

    def resource_capabilities(self, key: UUID) -> list[Any]:
        assert key == self.resource.canonical_id
        return [node for node, _ in self.entries]

    def truth_for_node(self, key: UUID, truth: Any) -> list[tuple[Any, TruthResolution]]:
        assert truth is not None
        return [
            (SimpleNamespace(semantic_attribute="state"), resolution)
            for node, resolution in self.entries
            if node.canonical_id == key
        ]

    def members_of_household(self, key: UUID) -> list[Any]:
        return []

    def places_in_household(self, key: UUID) -> list[Any]:
        return [self.room]

    def resources_in_place(self, key: UUID) -> list[Any]:
        return [self.resource] if key == self.room.canonical_id else []


def both_surfaces(
    entries: list[tuple[Any, TruthResolution]],
) -> tuple[dict[str, Any], dict[str, Any]]:
    graph = Graph(entries)
    truth = SimpleNamespace(get=lambda *_: None)
    identity = SimpleNamespace(household_id=graph.root.canonical_id)
    adapter = SimpleNamespace(
        config=SimpleNamespace(instance_id=uuid4()),
        graph=graph,
        reality=SimpleNamespace(projection=truth),
        provider_inventory=lambda: [
            {
                "external_object_kind": "device",
                "external_id": "private_device_reference",
                "present": True,
                "metadata": {
                    "canonical_target_id": str(graph.resource.canonical_id),
                    "name": "Old provider name",
                    "name_by_user": "Old provider alias",
                },
            }
        ],
    )
    manager = SimpleNamespace(
        list_tools=lambda: [
            SimpleNamespace(
                plugin_id="anima.provider.home-assistant",
                name="refresh_inventory",
                availability=True,
            )
        ]
    )
    gateway = CoreUICommandGateway(
        cast(Any, manager), cast(Any, None), home_assistant_adapter=cast(Any, adapter)
    )
    inventory = gateway.device_inventory(cast(Any, identity))["items"][0]
    model = PostgresHouseholdReadModel("UNUSED_NO_DATABASE", graph=graph, truth=truth)
    with (
        patch.object(model, "capabilities", return_value=[]),
        patch.object(model, "_notifications", return_value=[]),
        patch.object(model, "_reports", return_value=[]),
        patch.object(model, "_actions", return_value=([], [])),
        patch.object(model, "weather", return_value={}),
        patch.object(model, "calendar", return_value=[]),
        patch.object(model, "tasks", return_value=[]),
        patch.object(model, "activity", return_value=[]),
        patch.object(model, "_connect", side_effect=AssertionError("No database allowed")),
    ):
        home = model.home(cast(Any, identity))["rooms"][0]["devices"][0]
    for key in (
        "state",
        "truth_status",
        "observed_at",
        "provider_device_class",
        "canonical_name",
        "last_reported_state",
        "last_reported_at",
        "last_reported_source",
    ):
        assert inventory.get(key) == home.get(key)
    assert "private_provider_reference" not in json.dumps([inventory, home])
    assert "private_device_reference" not in json.dumps([inventory, home])
    return inventory, home


@pytest.mark.parametrize("device_class", ["door", "window", "opening"])
@pytest.mark.parametrize("value,expected", [("on", "OPEN"), ("off", "CLOSED")])
def test_contact_beats_battery_button_and_temperature_on_both_surfaces(
    device_class: str,
    value: str,
    expected: str,
) -> None:
    entries = [
        capability("button", None, "2026-09-06T00:00:00Z"),
        capability("sensor", "battery", "89"),
        capability("sensor", "temperature", "20.5"),
        capability("binary_sensor", device_class, value),
    ]
    for ordered in (entries, list(reversed(entries))):
        inventory, _ = both_surfaces(ordered)
        assert inventory["state"] == expected
        assert inventory["provider_device_class"] == device_class


@pytest.mark.parametrize(
    "status",
    [TruthStatus.STALE, TruthStatus.UNKNOWN, TruthStatus.UNAVAILABLE, TruthStatus.CONFLICTING],
)
def test_noncurrent_contact_never_promotes_old_value_or_fresh_secondary(
    status: TruthStatus,
) -> None:
    inventory, _ = both_surfaces(
        [
            capability("sensor", "temperature", "20"),
            capability("sensor", "battery", "100"),
            capability("binary_sensor", "door", "on", status=status),
        ]
    )
    assert inventory["state"] == status.value
    assert inventory["truth_status"] == status.value


def test_power_has_priority_even_when_stale() -> None:
    inventory, _ = both_surfaces(
        [
            capability("binary_sensor", "door", "on"),
            capability("switch", None, "off", status=TruthStatus.STALE),
        ]
    )
    assert inventory["state"] == "STALE"


@pytest.mark.parametrize("device_class", [None, "motion", "occupancy"])
def test_binary_without_proven_contact_class_is_on_off(device_class: str | None) -> None:
    inventory, _ = both_surfaces([capability("binary_sensor", device_class, "on")])
    assert inventory["state"] == "ON"
    if device_class is None:
        assert "provider_device_class" not in inventory


def test_explicit_contact_metadata_works_without_old_truth_observation() -> None:
    node, resolution = capability("binary_sensor", "door", "off", explicit_class=True)
    graph = Graph([(node, TruthResolution(resolution.truth_key, TruthStatus.UNKNOWN))])
    _, state = device_capability_projection(graph, object(), graph.resource.canonical_id)
    assert state["state"] == "UNKNOWN"
    assert state["provider_device_class"] == "door"


def test_appropriate_single_sensor_can_be_primary_but_diagnostics_cannot() -> None:
    inventory, _ = both_surfaces(
        [
            capability("button", None, "timestamp"),
            capability("sensor", "battery", "89"),
            capability("sensor", "temperature", "20.5"),
        ]
    )
    assert inventory["state"] == "20.5"
    inventory, _ = both_surfaces(
        [
            capability("button", None, "timestamp"),
            capability("sensor", "battery", "89"),
            capability("binary_sensor", "battery", "on"),
        ]
    )
    assert inventory["state"] == "UNKNOWN"


def test_equally_qualified_primaries_are_unknown_not_order_dependent() -> None:
    inventory, _ = both_surfaces(
        [
            capability("binary_sensor", "door", "on"),
            capability("binary_sensor", "window", "off"),
        ]
    )
    assert inventory["state"] == "UNKNOWN"


def test_old_class_metadata_is_not_resurrected_for_current_unclassified_binary() -> None:
    node, resolution = capability("binary_sensor", None, "on")
    old = SimpleNamespace(
        observed_at=NOW - timedelta(days=1),
        metadata={"attributes": {"device_class": "door"}},
    )
    resolution = replace(resolution, observations=(*resolution.observations, cast(Any, old)))
    inventory, _ = both_surfaces([(node, resolution)])
    assert inventory["state"] == "ON"
    assert "provider_device_class" not in inventory


def test_missing_truth_never_borrows_state_from_another_capability() -> None:
    node, resolution = capability("binary_sensor", "door", "off", explicit_class=True)
    resolution = TruthResolution(resolution.truth_key, TruthStatus.UNKNOWN)
    inventory, _ = both_surfaces(
        [
            (node, resolution),
            capability("sensor", "temperature", "21"),
        ]
    )
    assert inventory["state"] == "UNKNOWN"


@pytest.mark.parametrize(
    "domain,device_class", [("binary_sensor", None), ("sensor", "temperature")]
)
def test_open_word_does_not_invent_contact_semantics(domain: str, device_class: str | None) -> None:
    inventory, _ = both_surfaces([capability(domain, device_class, "OPEN")])
    assert inventory["state"] == "UNKNOWN"


def test_mapped_canonical_name_wins_over_provider_alias_without_renaming_provider() -> None:
    inventory, home = both_surfaces([capability("binary_sensor", "door", "off")])
    assert inventory["canonical_name"] == home["name"] == "Synthetic device"
    assert inventory["metadata"]["name_by_user"] == "Old provider alias"
    assert inventory["canonical_name"] != inventory["metadata"]["name_by_user"]


@pytest.mark.parametrize("value,expected", [("on", "OPEN"), ("off", "CLOSED")])
def test_stale_contact_exposes_separate_direct_last_report_not_current(
    value: str, expected: str
) -> None:
    node, resolution = capability("binary_sensor", "door", value, status=TruthStatus.STALE)
    observed = NOW - timedelta(hours=1)
    observation = TruthObservation(
        resolution.truth_key,
        "synthetic-provider",
        observed,
        observed,
        state=ObservationState.KNOWN,
        value=value,
        evidence_kind=EvidenceKind.DIRECT,
        freshness_seconds=60,
        metadata={"attributes": {"device_class": "door"}},
    )
    resolution = replace(resolution, observations=(observation,))
    inventory, _ = both_surfaces([(node, resolution)])
    assert inventory["state"] == inventory["truth_status"] == "STALE"
    assert inventory["last_reported_state"] == expected
    assert inventory["last_reported_at"] == observed.isoformat()
    assert inventory["last_reported_source"] == "ANIMA_TRUTH"
    assert "synthetic-provider" not in json.dumps(inventory)


@pytest.mark.parametrize(
    "status",
    [
        TruthStatus.UNKNOWN,
        TruthStatus.UNAVAILABLE,
        TruthStatus.CONFLICTING,
        TruthStatus.CURRENT_KNOWN,
    ],
)
def test_last_report_not_exposed_for_nonstale_truth(status: TruthStatus) -> None:
    inventory, _ = both_surfaces([capability("binary_sensor", "door", "on", status=status)])
    assert "last_reported_state" not in inventory


@pytest.mark.parametrize("device_class", [None, "motion", "battery"])
def test_last_report_never_invents_contact_class(device_class: str | None) -> None:
    inventory, _ = both_surfaces(
        [capability("binary_sensor", device_class, "on", status=TruthStatus.STALE)]
    )
    assert "last_reported_state" not in inventory


def test_last_report_timestamp_belongs_to_matching_known_observation() -> None:
    node, resolution = capability(
        "binary_sensor", "door", "off", status=TruthStatus.STALE, explicit_class=True
    )
    reported = NOW - timedelta(hours=2)
    old = TruthObservation(
        resolution.truth_key,
        "synthetic-known",
        reported,
        reported,
        value="off",
        freshness_seconds=60,
    )
    newer = TruthObservation(
        resolution.truth_key,
        "synthetic-unknown",
        NOW,
        NOW,
        state=ObservationState.UNKNOWN,
    )
    resolution = replace(resolution, observations=(old, newer), last_observed_at=NOW)
    inventory, _ = both_surfaces([(node, resolution)])
    assert inventory["state"] == "STALE"
    assert inventory["observed_at"] == NOW.isoformat()
    assert inventory["last_reported_at"] == reported.isoformat()


def test_stale_contact_without_supporting_direct_observation_omits_last_report() -> None:
    node, resolution = capability(
        "binary_sensor",
        "door",
        "on",
        status=TruthStatus.STALE,
        explicit_class=True,
    )
    resolution = replace(resolution, observations=())
    inventory, _ = both_surfaces([(node, resolution)])
    assert inventory["state"] == "STALE"
    assert "last_reported_state" not in inventory


def test_inferred_stale_value_is_not_described_as_direct_last_report() -> None:
    node, resolution = capability("binary_sensor", "door", "on", status=TruthStatus.STALE)
    inferred = replace(resolution.observations[0], evidence_kind=EvidenceKind.INFERRED)
    inventory, _ = both_surfaces([(node, replace(resolution, observations=(inferred,)))])
    assert inventory["state"] == "STALE"
    assert "last_reported_state" not in inventory
