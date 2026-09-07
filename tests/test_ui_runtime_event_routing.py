"""Scoped HA capability ownership at the event/alert composition boundary."""

from __future__ import annotations

import os
from dataclasses import replace
from datetime import UTC, datetime, time
from typing import Any, cast
from uuid import UUID, uuid4
from zoneinfo import ZoneInfo

import psycopg
import pytest
from test_home_assistant import FakeConnection, FakeGraph, FakeReality, FakeStore, snapshot, state

from anima_ha.attention import AttentionProfile, PostgresAttentionService
from anima_ha.db.migrate import migrate
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
from anima_ha.home_assistant import HAInstanceConfig, HomeAssistantAdapter
from anima_ha.journal import PostgresRealityStore
from anima_ha.senseguard_alerts import (
    PostgresSenseGuardAlertPolicyStore,
    SenseGuardAlertPolicy,
    SenseGuardEventRouter,
    _is_contact_opening,
)
from anima_ha.ui_runtime import _resolve_ha_event_resource


class OwnershipGraph:
    """Only the active graph read contracts consumed by the resolver."""

    def __init__(self) -> None:
        self.household = CanonicalNode(uuid4(), NodeKind.HOUSEHOLD, "Home")
        self.foreign = CanonicalNode(uuid4(), NodeKind.HOUSEHOLD, "Other home")
        self.device = CanonicalNode(uuid4(), NodeKind.SENSOR, "Kitchen")
        self.other = CanonicalNode(uuid4(), NodeKind.SENSOR, "Other sensor")
        self.capability = CanonicalNode(
            uuid4(), NodeKind.CAPABILITY, "Contact", metadata={"capability_type": "state.read"}
        )
        self.targets = [self.capability]
        self.candidates = [self.device]
        self.exposes = {self.device.canonical_id: [self.capability]}
        self.members = {self.household.canonical_id: [self.device]}
        self.placement_count = 1

    def resolve_provider_references(
        self, provider: str, scope: str, kind: str, external_id: str
    ) -> list[CanonicalNode]:
        assert (provider, scope, kind, external_id) == (
            "home_assistant",
            "instance",
            "entity",
            "binary_sensor.contact",
        )
        return self.targets

    def resources_with_capability(self, kind: str) -> list[CanonicalNode]:
        assert kind == "state.read"
        return self.candidates

    def resource_capabilities(self, resource_id: UUID) -> list[CanonicalNode]:
        return self.exposes.get(resource_id, [])

    def related(self, resource_id: UUID, relationship: RelationshipType) -> list[CanonicalNode]:
        assert relationship == RelationshipType.INSTALLED_IN
        return [self.household] * self.placement_count

    def list_places(self) -> list[CanonicalNode]:
        return [self.household, self.foreign]

    def resources_in_place(self, household_id: UUID) -> list[CanonicalNode]:
        return self.members.get(household_id, [])


@pytest.mark.parametrize(
    "case",
    [
        "capability",
        "direct",
        "missing",
        "ambiguous_reference",
        "retired_exposes",
        "ambiguous_owners",
        "foreign_owner",
        "local_and_foreign_owners",
        "shared_households",
        "orphan",
        "multiple_placements",
        "unsupported",
    ],
)
def test_event_resource_resolution_fails_closed(case: str) -> None:
    graph = OwnershipGraph()
    if case == "direct":
        graph.targets = [graph.device]
    elif case == "missing":
        graph.targets = []
    elif case == "ambiguous_reference":
        graph.targets.append(graph.device)
    elif case == "retired_exposes":
        graph.exposes.clear()  # The global type query can still return the candidate.
    elif case in {"ambiguous_owners", "local_and_foreign_owners"}:
        graph.candidates.append(graph.other)
        graph.exposes[graph.other.canonical_id] = [graph.capability]
        household = graph.household if case == "ambiguous_owners" else graph.foreign
        graph.members.setdefault(household.canonical_id, []).append(graph.other)
    elif case == "foreign_owner":
        graph.members = {graph.foreign.canonical_id: [graph.device]}
    elif case == "shared_households":
        graph.members[graph.foreign.canonical_id] = [graph.device]
    elif case == "orphan":
        graph.members.clear()
    elif case == "multiple_placements":
        graph.placement_count = 2
    elif case == "unsupported":
        graph.targets = [graph.household]
    result = _resolve_ha_event_resource(
        cast(Any, graph), "instance", graph.household.canonical_id, "binary_sensor.contact"
    )
    assert result == (graph.device.canonical_id if case in {"capability", "direct"} else None)


@pytest.mark.parametrize(
    ("domain", "device_class", "value", "case", "expected"),
    [
        ("binary_sensor", "door", "on", "live", True),
        ("binary_sensor", "window", "on", "live", True),
        ("binary_sensor", "opening", "open", "live", True),
        ("binary_sensor", "door", "off", "live", False),
        ("binary_sensor", "door", "closed", "live", False),
        ("binary_sensor", "door", "unknown", "live", False),
        ("binary_sensor", "door", "unavailable", "live", False),
        ("binary_sensor", "door", "on", "snapshot", False),
        ("binary_sensor", "door", "on", "attribute_only", False),
        ("binary_sensor", "door", "on", "missing_changed", False),
        ("binary_sensor", "door", "on", "attribution", False),
        ("binary_sensor", "door", "on", "naive_changed", False),
        ("binary_sensor", "battery", "on", "live", False),
        ("binary_sensor", "", "on", "live", False),
        ("sensor", "door", "on", "live", False),
        ("button", "door", "on", "live", False),
    ],
)
def test_opening_requires_live_contact_transition_evidence(
    domain: str, device_class: str, value: str, case: str, expected: bool
) -> None:
    config = HAInstanceConfig(uuid4(), "ws://synthetic.test/api/websocket", "TEST_ONLY", ssl=False)
    adapter = HomeAssistantAdapter(
        config,
        cast(Any, FakeReality()),
        cast(Any, FakeGraph(config.provider_scope, uuid4(), uuid4())),
        cast(Any, FakeStore()),
    )
    raw = state(f"{domain}.kitchen_door", value, "2026-09-07T00:38:31+00:00")
    raw["attributes"]["device_class"] = device_class
    if case == "attribute_only":
        raw["last_changed"] = "2026-09-07T00:38:30+00:00"
    elif case == "missing_changed":
        raw.pop("last_changed")
    elif case == "naive_changed":
        raw["last_changed"] = "2026-09-07T00:38:31"
    event = adapter.normalize_state_event(raw, snapshot=case == "snapshot")
    if case == "attribution":
        event = replace(event, metadata=event.metadata | {"binding_attribution": True})
    assert _is_contact_opening(event) is expected


def test_capability_event_reaches_policy_and_durable_attention() -> None:
    database_url = os.environ.get("ANIMA_LATE_BINDING_TEST_DATABASE_URL")
    if not database_url:
        pytest.skip("requires disposable ANIMA_LATE_BINDING_TEST_DATABASE_URL")
    with psycopg.connect(database_url) as connection:
        assert connection.execute("SELECT current_database()").fetchone() == (
            "anima_late_binding_test",
        )
    migrate(database_url, 5)
    graph = PostgresHouseholdGraph(database_url)
    reality = PostgresRealityStore(database_url)
    config = HAInstanceConfig(uuid4(), "ws://synthetic.test/api/websocket", "TEST_ONLY", ssl=False)
    household = CanonicalNode(uuid4(), NodeKind.HOUSEHOLD, "Synthetic household")
    room = CanonicalNode(uuid4(), NodeKind.ROOM, "Kitchen")
    device = CanonicalNode(uuid4(), NodeKind.SENSOR, "SenseGuard Kitchen")
    capability = CanonicalNode(
        uuid4(), NodeKind.CAPABILITY, "Contact", metadata={"capability_type": "state.read"}
    )
    entity_id = "binary_sensor.synthetic_kitchen"
    relationships = (
        CanonicalRelationship(
            uuid4(), RelationshipType.CONTAINS, household.canonical_id, room.canonical_id
        ),
        CanonicalRelationship(
            uuid4(), RelationshipType.INSTALLED_IN, device.canonical_id, room.canonical_id
        ),
        CanonicalRelationship(
            uuid4(), RelationshipType.EXPOSES, device.canonical_id, capability.canonical_id
        ),
    )
    graph.commission(
        CommissioningDocument(
            1,
            (household, room, device, capability),
            relationships,
            provider_references=(
                ProviderReference(
                    uuid4(),
                    "home_assistant",
                    config.provider_scope,
                    "entity",
                    entity_id,
                    capability.canonical_id,
                    TargetKind.CAPABILITY,
                ),
            ),
        )
    )
    policy_store = PostgresSenseGuardAlertPolicyStore(database_url)
    for start, end in ((time(0), time(12)), (time(12), time(0))):
        policy_store.save(
            SenseGuardAlertPolicy(
                uuid4(),
                household.canonical_id,
                (device.canonical_id,),
                "senseguard.opened",
                "America/New_York",
                start,
                end,
                delivery_mode="SENTRY_COGNITION",
            )
        )
    attention = PostgresAttentionService(database_url)
    profile = AttentionProfile(f"test.capability-route.{uuid4()}", ())
    attention_calls: list[Any] = []

    def dispatch_attention() -> None:
        result = attention.process(profile, consumer_name=profile.profile_version)
        assert result.failure is None
        attention_calls.append(result)

    router = SenseGuardEventRouter(
        household_id=household.canonical_id,
        policy_store=policy_store,
        resource_resolver=lambda external: _resolve_ha_event_resource(
            graph, config.provider_scope, household.canonical_id, external
        ),
        event_sink=reality.journal,
        dispatch_attention=dispatch_attention,
    )
    adapter = HomeAssistantAdapter(
        config,
        reality,
        graph,
        FakeStore(),  # type: ignore[arg-type]
        normalized_event_callback=router.handle,
    )
    adapter.start(FakeConnection(replace(snapshot(), entities=(), states=())))
    try:
        # Real adapter envelope; 20:38 EDT is 00:38 UTC on the following date.
        occurred_at = datetime(2026, 9, 7, 0, 38, 31, tzinfo=UTC)
        raw = state(entity_id, "on", occurred_at.isoformat())
        raw["attributes"]["device_class"] = "door"
        event = adapter.normalize_state_event(raw)
        adapter.receive_provider_event({"event_type": "state_changed", "data": {"new_state": raw}})
        alerts = reality.journal.list_events(
            event_type="senseguard.opened", subject_key=f"senseguard/{device.canonical_id}"
        )
        assert len(alerts) == 1
        assert alerts[0]["occurred_at"] == occurred_at
        assert alerts[0]["causation_id"] == event.event_id
        assert alerts[0]["payload"]["canonical_resource_id"] == str(device.canonical_id)
        assert len(attention_calls) == 1
        triggers = [
            trigger
            for trigger in attention.list_triggers(profile.profile_version)
            if alerts[0]["event_id"] in trigger.source_event_ids
        ]
        assert len(triggers) == 1
        # Attention creation has its own processing time; original occurrence
        # time remains on the causally linked journal events, not rewritten.
        assert triggers[0].source_event_ids == (alerts[0]["event_id"],)
        observations = reality.journal.list_events(
            event_type="truth.observation", source=event.source, subject_key=event.subject_key
        )
        assert observations[0]["occurred_at"] == occurred_at
        assert observations[0]["payload"]["observed_at"] == occurred_at.isoformat()
        router.handle(event)
        assert len(attention_calls) == 1  # Duplicate source event does not redispatch Attention.
        # Closing and a new attribute report while still on are not openings.
        closing = state(entity_id, "off", "2026-09-07T00:38:34+00:00")
        closing["attributes"]["device_class"] = "door"
        assert router.handle(adapter.normalize_state_event(closing)) == []
        attributes_only = dict(raw, last_updated="2026-09-07T00:38:35+00:00")
        assert router.handle(adapter.normalize_state_event(attributes_only)) == []
        assert router.handle(adapter.normalize_state_event(raw, snapshot=True)) == []
        assert len(attention_calls) == 1
    finally:
        adapter.stop()


@pytest.mark.parametrize(("hour", "minute"), [(0, 0), (11, 59), (12, 0), (23, 59)])
def test_two_half_day_opening_policies_cover_every_boundary_once(hour: int, minute: int) -> None:
    household_id, resource_id = uuid4(), uuid4()
    policies = [
        SenseGuardAlertPolicy(
            uuid4(),
            household_id,
            (resource_id,),
            "senseguard.opened",
            "America/New_York",
            start,
            end,
        )
        for start, end in ((time(0), time(12)), (time(12), time(0)))
    ]
    occurred_at = datetime(2026, 9, 6, hour, minute, tzinfo=ZoneInfo("America/New_York"))
    assert (
        sum(
            policy.matches(
                resource_id=resource_id, event_type="senseguard.opened", occurred_at=occurred_at
            )
            for policy in policies
        )
        == 1
    )
    assert not replace(policies[0], end_local=time(0)).matches(
        resource_id=resource_id, event_type="senseguard.opened", occurred_at=occurred_at
    )
