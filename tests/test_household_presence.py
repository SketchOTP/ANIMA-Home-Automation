"""Synthetic household mappings and real pure Truth reduction; no phone scans."""

from __future__ import annotations

import json
import os
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from typing import Any, NotRequired, TypedDict
from uuid import UUID, uuid4

import psycopg
import pytest

from anima_ha.events import EventEnvelope, EvidenceKind, TruthObservation
from anima_ha.graph import (
    CanonicalNode,
    CanonicalRelationship,
    CommissioningDocument,
    NodeKind,
    PostgresHouseholdGraph,
    ProviderReference,
    RelationshipType,
    TargetKind,
    validate_commissioning,
)
from anima_ha.household_presence import (
    HOUSEHOLD_PRESENCE_MANIFEST,
    HouseholdPresenceNativePlugin,
    HouseholdPresenceService,
    PresenceBinding,
    PresenceError,
    PresenceValue,
    SignalKind,
    normalized_router_connection_events,
    presence_signal,
    reduce_presence,
    router_connection_transition,
)
from anima_ha.plugins import InvocationContext, PluginValidationError, ToolDescriptor
from anima_ha.policy import RequestOrigin
from anima_ha.truth import InMemoryTruthState, TruthResolution, TruthStatus

NOW = datetime(2026, 9, 7, 4, tzinfo=UTC)
HOME, PERSON, PHONE, INSTANCE = (UUID(int=i) for i in range(1, 5))


class BindingArguments(TypedDict):
    ha_instance_id: UUID
    person_id: UUID
    source_handle: UUID
    freshness_seconds: int


class BindingOverrides(TypedDict, total=False):
    ha_instance_id: UUID
    person_id: UUID
    source_handle: UUID
    freshness_seconds: int


class TransitionArguments(TypedDict):
    now: datetime
    previous_binding_version: int | None
    source_continuous: bool
    recovery: NotRequired[bool]


def binding(kind: SignalKind = SignalKind.GEOFENCE, index: int = 0) -> PresenceBinding:
    return PresenceBinding(
        UUID(int=100 + index),
        HOME,
        PERSON,
        PHONE,
        UUID(int=200 + index),
        INSTANCE,
        kind,
        300,
        1,
        f"{'person' if kind == SignalKind.HA_PERSON else 'device_tracker'}.synthetic_{index}",
    )


def resolution(b: PresenceBinding, value: Any = "home", *, age: int = 5) -> TruthResolution:
    truth = InMemoryTruthState()
    truth.add(
        TruthObservation(
            truth_key=b.truth_key,
            source=f"provider:home_assistant:{INSTANCE}:{b.entity_id}",
            observed_at=NOW - timedelta(seconds=age),
            received_at=NOW - timedelta(seconds=1),
            value=value,
            evidence_kind=EvidenceKind.DIRECT,
            freshness_seconds=600,
            metadata={"coordinates": "PRIVATE", "mac": "PRIVATE"},
        )
    )
    return truth.get(b.truth_key, now=NOW)


@pytest.mark.parametrize(
    "kind,value,expected",
    [
        (SignalKind.GEOFENCE, "home", PresenceValue.HOME),
        (SignalKind.GEOFENCE, "not_home", PresenceValue.AWAY),
        (SignalKind.ROUTER_WIFI, "home", PresenceValue.HOME),
        (SignalKind.ROUTER_WIFI, "not_home", PresenceValue.NOT_DETECTED),
        (SignalKind.HA_PERSON, "not_home", PresenceValue.NOT_DETECTED),
    ],
)
def test_coarse_signal_semantics(kind: SignalKind, value: str, expected: PresenceValue) -> None:
    b = binding(kind)
    result = presence_signal(b, resolution(b, value), now=NOW)
    assert result["value"] == expected
    assert result["status"] == TruthStatus.CURRENT_KNOWN
    assert result["observed_at"] != result["received_at"]
    assert result["physical_observed_at"] is None


@pytest.mark.parametrize("value", ["Private school", "unknown", "unavailable", None, True, {}, []])
def test_never_emit_zones_or_unrecognized_raw_values(value: Any) -> None:
    b = binding()
    result = presence_signal(b, resolution(b, value), now=NOW)
    assert result["value"] == PresenceValue.UNKNOWN
    assert result["status"] == TruthStatus.UNKNOWN
    assert "Private school" not in json.dumps(result)


def test_age_expiry_and_existing_truth_status_cannot_be_freshened() -> None:
    b = binding()
    assert (
        presence_signal(b, resolution(b, age=299), now=NOW)["status"] == TruthStatus.CURRENT_KNOWN
    )
    assert presence_signal(b, resolution(b, age=300), now=NOW)["status"] == TruthStatus.STALE
    for status in (
        TruthStatus.STALE,
        TruthStatus.UNKNOWN,
        TruthStatus.UNAVAILABLE,
        TruthStatus.CONFLICTING,
    ):
        result = presence_signal(b, replace(resolution(b), status=status), now=NOW)
        assert result["status"] == status
        assert result["value"] == PresenceValue.UNKNOWN


@pytest.mark.parametrize(
    "changes",
    [
        {"last_observed_at": None},
        {"last_received_at": None},
        {"last_observed_at": NOW.replace(tzinfo=None)},
        {"last_received_at": NOW + timedelta(seconds=1)},
        {"last_observed_at": NOW + timedelta(seconds=1)},
        {"last_received_at": NOW - timedelta(days=1)},
        {"evidence_kind": EvidenceKind.INFERRED},
        {"observations": ()},
    ],
)
def test_invalid_or_unqualified_evidence_is_unknown(changes: dict[str, Any]) -> None:
    b = binding()
    result = presence_signal(b, replace(resolution(b), **changes), now=NOW)
    assert result["status"] == TruthStatus.UNKNOWN
    assert result["value"] == PresenceValue.UNKNOWN


def test_truth_key_and_source_are_exact_not_guessed() -> None:
    b = binding()
    r = resolution(b)
    with pytest.raises(PresenceError):
        presence_signal(b, replace(r, truth_key="foreign"), now=NOW)
    r = replace(r, observations=(replace(r.observations[0], source="foreign"),))
    assert presence_signal(b, r, now=NOW)["status"] == TruthStatus.UNKNOWN


def test_fresh_conflict_wifi_absence_and_calculated_person_not_double_counted() -> None:
    gps, wifi, person = (
        binding(),
        binding(SignalKind.ROUTER_WIFI, 1),
        binding(SignalKind.HA_PERSON, 2),
    )

    def signal(b: PresenceBinding, value: str) -> dict[str, Any]:
        return presence_signal(b, resolution(b, value), now=NOW)

    assert reduce_presence([signal(gps, "not_home"), signal(wifi, "home")]) == (
        TruthStatus.CONFLICTING,
        PresenceValue.UNKNOWN,
    )
    assert reduce_presence([signal(wifi, "not_home")]) == (
        TruthStatus.UNKNOWN,
        PresenceValue.UNKNOWN,
    )
    assert reduce_presence([signal(person, "not_home")]) == (
        TruthStatus.UNKNOWN,
        PresenceValue.UNKNOWN,
    )
    assert reduce_presence([signal(gps, "not_home"), signal(person, "home")]) == (
        TruthStatus.CURRENT_KNOWN,
        PresenceValue.AWAY,
    )
    # Configured but stale raw tracker is not silently replaced by its aggregate.
    stale = presence_signal(gps, resolution(gps, age=500), now=NOW)
    assert reduce_presence([stale, signal(person, "home")]) == (
        TruthStatus.STALE,
        PresenceValue.UNKNOWN,
    )
    with pytest.raises(PresenceError):
        reduce_presence([signal(gps, "home")] * 9)


class Graph:
    def __init__(self) -> None:
        self.root = CanonicalNode(HOME, NodeKind.HOUSEHOLD, "PRIVATE")
        self.people = [
            CanonicalNode(PERSON, NodeKind.PERSON, "PRIVATE", metadata={"semantic_role": "owner"})
        ]
        self.resources = [CanonicalNode(PHONE, NodeKind.SENSOR, "PRIVATE")]
        self.associated = {PERSON: self.resources}
        self.caps: list[CanonicalNode] = []
        self.refs: dict[UUID, list[ProviderReference]] = {}
        self.truth = InMemoryTruthState()
        self.commissions: list[CommissioningDocument] = []

    def add(self, b: PresenceBinding, value: str = "home") -> None:
        self.caps.append(CanonicalNode(b.capability_id, NodeKind.CAPABILITY, "PRIVATE"))
        self.refs[b.capability_id] = [
            ProviderReference(
                b.binding_id,
                "anima.household_presence",
                str(HOME),
                "binding",
                str(b.capability_id),
                b.capability_id,
                TargetKind.CAPABILITY,
                {
                    "household_presence": {
                        "schema_version": 1,
                        "household_id": str(HOME),
                        "person_id": str(PERSON),
                        "ha_reference_id": str(UUID(int=b.binding_id.int + 1000)),
                        "signal_kind": b.signal_kind.value,
                        "freshness_seconds": b.freshness_seconds,
                        "version": b.version,
                        "home_semantics_verified": True,
                    }
                },
            ),
            ProviderReference(
                UUID(int=b.binding_id.int + 1000),
                "home_assistant",
                str(INSTANCE),
                "entity",
                b.entity_id,
                b.capability_id,
                TargetKind.CAPABILITY,
            ),
        ]
        self.truth.add(resolution(b, value).observations[0])

    def get_node(self, canonical_id: UUID) -> CanonicalNode | None:
        return next(
            (
                n
                for n in [self.root, *self.people, *self.resources, *self.caps]
                if n.canonical_id == canonical_id
            ),
            None,
        )

    def commission(self, document: CommissioningDocument) -> None:
        validate_commissioning(document)
        self.commissions.append(document)
        for ref in document.provider_references:
            self.refs.setdefault(ref.target_id, []).append(ref)
        for edge in document.relationships:
            node = self.get_node(edge.target_id)
            assert node is not None
            self.associated.setdefault(edge.source_id, [])
            if node not in self.associated[edge.source_id]:
                self.associated[edge.source_id].append(node)

    def members_of_household(self, household_id: UUID) -> list[CanonicalNode]:
        assert household_id == HOME
        return self.people

    def resources_in_place(self, place_id: UUID, recursive: bool = True) -> list[CanonicalNode]:
        assert place_id == HOME
        return self.resources

    def related(self, source_id: UUID, relationship_type: RelationshipType) -> list[CanonicalNode]:
        assert relationship_type == RelationshipType.ASSOCIATED_WITH
        return self.associated.get(source_id, [])

    def resource_capabilities(self, resource_id: UUID) -> list[CanonicalNode]:
        assert resource_id == PHONE
        return self.caps

    def provider_references_for(self, target_id: UUID) -> list[ProviderReference]:
        return self.refs.get(target_id, [])


def snapshot(graph: Graph, **changes: Any) -> dict[str, Any]:
    args: dict[str, Any] = {"ha_instance_id": INSTANCE, "now": NOW} | changes
    return HouseholdPresenceService(graph, graph.truth).snapshot(HOME, **args)


def test_graph_binding_and_privacy_projection() -> None:
    graph = Graph()
    graph.add(binding())
    graph.add(binding(SignalKind.ROUTER_WIFI, 1), "not_home")
    result = snapshot(graph)
    item = result["items"][0]
    assert item["person_id"] == str(PERSON)
    assert item["binding_status"] == "CONFIGURED"
    assert item["value"] == "HOME"
    assert item["is_authentication"] is False
    assert item["door_actor_verified"] is False
    assert len(item["signals"]) == 2
    assert result["external_content_trust"] == "EXTERNAL_UNTRUSTED"
    output = json.dumps(result)
    for forbidden in (
        "PRIVATE",
        "device_tracker.",
        "coordinates",
        "mac",
        "provider_scope",
        "truth_key",
    ):
        assert forbidden not in output


def test_unconfigured_and_unavailable_are_not_away() -> None:
    graph = Graph()
    item = snapshot(graph)["items"][0]
    assert item["binding_status"] == "UNCONFIGURED"
    assert item["value"] == "UNKNOWN"
    graph.add(binding())
    graph.truth.observations.clear()
    assert snapshot(graph)["items"][0]["status"] == "UNKNOWN"


@pytest.mark.parametrize(
    "field,value",
    [
        ("household_id", str(UUID(int=99))),
        ("person_id", str(UUID(int=99))),
        ("home_semantics_verified", False),
        ("schema_version", True),
        ("signal_kind", "MAC_GUESS"),
        ("freshness_seconds", 0),
        ("freshness_seconds", 86401),
        ("freshness_seconds", True),
        ("version", 0),
    ],
)
def test_bad_private_binding_metadata_fails_closed(field: str, value: Any) -> None:
    graph = Graph()
    graph.add(binding())
    graph.refs[binding().capability_id][0].metadata["household_presence"][field] = value
    with pytest.raises(PresenceError):
        snapshot(graph)


def test_foreign_retired_source_and_cross_instance_guards() -> None:
    graph = Graph()
    graph.add(binding())
    with pytest.raises(PresenceError):
        snapshot(graph, person_id=UUID(int=99))
    with pytest.raises(PresenceError):
        snapshot(graph, ha_instance_id=UUID(int=99))
    graph.resources = []
    with pytest.raises(PresenceError):
        snapshot(graph)
    graph.root = replace(graph.root, retired_at=NOW)
    with pytest.raises(PresenceError):
        snapshot(graph)


def test_stable_bounded_person_pagination_and_cursor_scope() -> None:
    graph = Graph()
    graph.people = [
        CanonicalNode(UUID(int=i), NodeKind.PERSON, "PRIVATE") for i in range(60, 5, -1)
    ]
    first = snapshot(graph, limit=50)
    assert len(first["items"]) == 50
    second = snapshot(graph, limit=50, cursor=first["next_cursor"])
    assert len(second["items"]) == 5
    assert second["next_cursor"] is None
    assert len({i["person_id"] for i in first["items"] + second["items"]}) == 55
    with pytest.raises(PresenceError):
        snapshot(graph, cursor=first["next_cursor"], person_id=UUID(int=6))
    with pytest.raises(PresenceError):
        snapshot(graph, cursor=first["next_cursor"], ha_instance_id=UUID(int=99))


@pytest.mark.parametrize("limit", [0, 51, True, "5", None])
def test_invalid_limits(limit: Any) -> None:
    with pytest.raises(PresenceError):
        snapshot(Graph(), limit=limit)


def test_duplicate_bindings_do_not_corroborate_and_overflow_does_not_drop_conflicts() -> None:
    graph = Graph()
    graph.add(binding())
    graph.refs[binding().capability_id] *= 2
    assert len(snapshot(graph)["items"][0]["signals"]) == 1
    graph.refs[binding().capability_id].append(
        replace(graph.refs[binding().capability_id][0], provider_reference_id=UUID(int=999))
    )
    with pytest.raises(PresenceError):
        snapshot(graph)


def context(**changes: Any) -> InvocationContext:
    return replace(
        InvocationContext(
            HOME, PERSON, None, UUID(int=90), 1, "synthetic", RequestOrigin.DIRECT_USER
        ),
        **changes,
    )


def unbound_service() -> tuple[Graph, HouseholdPresenceService, UUID]:
    graph = Graph()
    graph.add(binding(SignalKind.ROUTER_WIFI))
    graph.refs[binding().capability_id] = graph.refs[binding().capability_id][1:]
    graph.associated = {}
    service = HouseholdPresenceService(
        graph, graph.truth, classify_source=lambda ref: SignalKind.ROUTER_WIFI
    )
    handle = UUID(service.list_sources(HOME, ha_instance_id=INSTANCE)["items"][0]["source_handle"])
    return graph, service, handle


def test_binding_persists_private_reference_and_association_without_changing_ha_ref() -> None:
    graph, service, handle = unbound_service()
    original = graph.refs[binding().capability_id][0]
    args: BindingArguments = {
        "ha_instance_id": INSTANCE,
        "person_id": PERSON,
        "source_handle": handle,
        "freshness_seconds": 300,
    }
    result = service.bind_source(context(), **args)
    assert result["status"] == "SUCCEEDED"
    assert graph.refs[binding().capability_id][0] == original
    assert original.metadata == {}
    assert len(graph.commissions) == 1
    assert (
        graph.commissions[0].relationships[0].relationship_type == RelationshipType.ASSOCIATED_WITH
    )
    assert service.bind_source(context(), **args) == result
    assert len(graph.commissions) == 1
    assert snapshot(graph)["items"][0]["binding_status"] == "CONFIGURED"
    changed_args: BindingArguments = {**args, "freshness_seconds": 600}
    with pytest.raises(PresenceError):
        service.bind_source(context(), **changed_args)
    assert len(graph.commissions) == 1


@pytest.mark.parametrize(
    "change",
    [
        {"principal_id": None},
        {"principal_id": UUID(int=999)},
        {"origin": RequestOrigin.AUTONOMOUS_AGENT},
    ],
)
def test_binding_requires_direct_commissioned_owner(change: dict[str, Any]) -> None:
    graph, service, handle = unbound_service()
    with pytest.raises(PresenceError):
        service.bind_source(
            context(**change),
            ha_instance_id=INSTANCE,
            person_id=PERSON,
            source_handle=handle,
            freshness_seconds=300,
        )
    assert not graph.commissions


def test_binding_rejects_foreign_person_handle_and_unqualified_source() -> None:
    graph, service, handle = unbound_service()
    cases: tuple[BindingOverrides, ...] = (
        {"person_id": UUID(int=998)},
        {"source_handle": UUID(int=998)},
        {"freshness_seconds": True},
    )
    for changes in cases:
        args: BindingArguments = {
            "ha_instance_id": INSTANCE,
            "person_id": PERSON,
            "source_handle": handle,
            "freshness_seconds": 300,
        }
        args.update(changes)
        with pytest.raises(PresenceError):
            service.bind_source(context(), **args)
    service.classify_source = lambda ref: None
    assert service.list_sources(HOME, ha_instance_id=INSTANCE)["items"] == []
    with pytest.raises(PresenceError):
        service.bind_source(
            context(),
            ha_instance_id=INSTANCE,
            person_id=PERSON,
            source_handle=handle,
            freshness_seconds=300,
        )
    assert not graph.commissions


def test_opaque_sources_default_closed_and_scoped_pagination() -> None:
    graph, service, handle = unbound_service()
    assert (
        HouseholdPresenceService(graph, graph.truth).list_sources(HOME, ha_instance_id=INSTANCE)[
            "items"
        ]
        == []
    )
    page = service.list_sources(HOME, ha_instance_id=INSTANCE)
    for forbidden in ("PRIVATE", "device_tracker.", "external_id", "mac", "provider"):
        assert forbidden not in json.dumps(page)
    assert service.list_sources(HOME, ha_instance_id=UUID(int=999))["items"] == []
    for i in range(1, 3):
        graph.add(binding(SignalKind.ROUTER_WIFI, i))
    first = service.list_sources(HOME, ha_instance_id=INSTANCE, limit=2)
    second = service.list_sources(
        HOME, ha_instance_id=INSTANCE, limit=2, cursor=first["next_cursor"]
    )
    assert len(second["items"]) == 1
    with pytest.raises(PresenceError):
        service.list_sources(HOME, ha_instance_id=UUID(int=999), cursor=first["next_cursor"])


def test_native_manifest_and_invocation_scope() -> None:
    graph, service, handle = unbound_service()
    plugin = HouseholdPresenceNativePlugin(service, INSTANCE, now=lambda: NOW)
    descriptors = [
        ToolDescriptor.from_manifest(HOUSEHOLD_PRESENCE_MANIFEST, item)
        for item in plugin.list_tools()
    ]
    assert {d.name for d in descriptors} == {"snapshot", "list_sources", "bind_source"}
    assert all(d.read_only == (d.name != "bind_source") for d in descriptors)
    for name in ("snapshot", "list_sources", "bind_source"):
        with pytest.raises(PluginValidationError):
            plugin.invoke(name, {}, 1)
        with pytest.raises(PluginValidationError):
            plugin.invoke_with_invocation_context(name, {"household_id": str(HOME)}, 1, context())
    result = plugin.invoke_with_invocation_context(
        "bind_source",
        {"person_id": str(PERSON), "source_handle": str(handle), "freshness_seconds": 300},
        1,
        context(),
    )
    assert result["status"] == "SUCCEEDED"
    assert (
        plugin.invoke_with_invocation_context("snapshot", {}, 1, context())["items"][0]["value"]
        == "HOME"
    )
    assert plugin.invoke_with_invocation_context("list_sources", {}, 1, context())["items"]


@pytest.mark.parametrize(
    "before,after,transition,value",
    [
        ("home", "not_home", "DISCONNECTED", "NOT_DETECTED"),
        ("not_home", "home", "RECONNECTED", "HOME"),
    ],
)
def test_router_edges_are_coarse_private_and_deterministic(
    before: str, after: str, transition: str, value: str
) -> None:
    b = binding(SignalKind.ROUTER_WIFI)
    args: TransitionArguments = dict(now=NOW, previous_binding_version=1, source_continuous=True)
    event = router_connection_transition(
        b, resolution(b, before, age=20), resolution(b, after), **args
    )
    assert event is not None
    assert event.payload["transition"] == transition
    assert event.payload["value"] == value
    assert event.payload["is_authentication"] is False
    assert event.metadata["household_id"] == str(HOME)
    assert event.delivery_class.value == "GUARANTEED"
    assert event.importance.value == "NORMAL"
    assert event.payload["observed_at"] != event.payload["received_at"]
    assert event == router_connection_transition(
        b, resolution(b, before, age=20), resolution(b, after), **args
    )
    for forbidden in ("PRIVATE", "device_tracker.", "mac", "coordinates", "AWAY"):
        assert forbidden not in json.dumps(event.to_dict())


@pytest.mark.parametrize(
    "reason",
    [
        "initial",
        "stale",
        "unknown",
        "unavailable",
        "conflicting",
        "same",
        "late",
        "recovery",
        "gap",
        "version",
        "snapshot",
        "reconcile",
    ],
)
def test_router_edges_suppress_uncertain_or_non_transitions(reason: str) -> None:
    b = binding(SignalKind.ROUTER_WIFI)
    known_prior = resolution(b, "home", age=20)
    prior: TruthResolution | None = known_prior
    current = resolution(b, "not_home")
    args: TransitionArguments = dict(
        now=NOW, previous_binding_version=1, source_continuous=True, recovery=False
    )
    if reason == "initial":
        prior = None
    elif reason in {"stale", "unknown", "unavailable", "conflicting"}:
        prior = replace(known_prior, status=TruthStatus(reason.upper()))
    elif reason == "same":
        current = resolution(b, "home")
    elif reason == "late":
        current = resolution(b, "not_home", age=21)
    elif reason == "recovery":
        args["recovery"] = True
    elif reason == "gap":
        args["source_continuous"] = False
    elif reason == "version":
        args["previous_binding_version"] = 2
    else:
        current = replace(
            current, observations=(replace(current.observations[0], metadata={reason: True}),)
        )
    assert router_connection_transition(b, prior, current, **args) is None


def normalized_event(b: PresenceBinding, value: str, *, age: int = 5) -> EventEnvelope:
    observation = resolution(b, value, age=age).observations[0]
    observation = replace(
        observation,
        metadata={"last_updated": observation.observed_at.isoformat(), "mac": "PRIVATE"},
    )
    return EventEnvelope.create(
        event_id=str(UUID(int=10000 + age)),
        event_type="truth.observation",
        source=f"provider:home_assistant:{INSTANCE}",
        subject_key="PRIVATE",
        occurred_at=observation.observed_at,
        recorded_at=NOW,
        payload=observation.to_payload(),
    )


def test_normalized_callback_initial_edges_unknown_reset_and_causal_dedup() -> None:
    b = binding(SignalKind.ROUTER_WIFI)
    graph = Graph()
    graph.add(b)
    first = normalized_event(b, "home", age=20)
    assert HouseholdPresenceService(graph, graph.truth).bindings_for_event(
        HOME, ha_instance_id=INSTANCE, event=first
    ) == [b]
    events, baseline = normalized_router_connection_events(
        first, [b], {}, now=NOW, source_continuous=True
    )
    assert events == []
    assert baseline[b.binding_id][1].observations[0].metadata == {}
    second = normalized_event(b, "not_home")
    edges, updated = normalized_router_connection_events(
        second, [b], baseline, now=NOW, source_continuous=True
    )
    assert len(edges) == 1
    assert edges[0].causation_id == second.event_id
    assert (
        normalized_router_connection_events(second, [b], baseline, now=NOW, source_continuous=True)[
            0
        ]
        == edges
    )
    assert (
        normalized_router_connection_events(second, [b], updated, now=NOW, source_continuous=True)[
            0
        ]
        == []
    )
    # Losing the source invalidates baseline; next home is initialization, not arrival.
    unknown = normalized_event(b, "unknown", age=3)
    assert normalized_router_connection_events(
        unknown, [b], updated, now=NOW, source_continuous=True
    ) == ([], {})
    assert (
        normalized_router_connection_events(
            normalized_event(b, "home", age=2), [b], {}, now=NOW, source_continuous=True
        )[0]
        == []
    )
    for forbidden in ("PRIVATE", "device_tracker.", "mac", "AWAY"):
        assert forbidden not in json.dumps(edges[0].to_dict())


@pytest.mark.parametrize(
    "reason", ["snapshot", "reconcile", "wrong_source", "missing_time", "overflow"]
)
def test_normalized_callback_rejects_unqualified_input(reason: str) -> None:
    b = binding(SignalKind.ROUTER_WIFI)
    event = normalized_event(b, "not_home")
    if reason in {"snapshot", "reconcile"}:
        event = replace(event, metadata={reason: True})
    elif reason == "wrong_source":
        event = replace(event, source="foreign")
    elif reason == "missing_time":
        event.payload["metadata"].pop("last_updated")
    else:
        with pytest.raises(PresenceError):
            normalized_router_connection_events(event, [b] * 9, {}, now=NOW)
        return
    assert normalized_router_connection_events(event, [b], {}, now=NOW, source_continuous=True) == (
        [],
        {},
    )


def test_nine_bindings_fail_without_dropping_conflict() -> None:
    graph = Graph()
    for index in range(9):
        graph.add(binding(index=index))
    with pytest.raises(PresenceError):
        snapshot(graph)


def test_real_postgres_presence_binding_when_disposable_fixture_is_provided() -> None:
    database_url = os.environ.get("ANIMA_LATE_BINDING_TEST_DATABASE_URL")
    if not database_url:
        pytest.skip("requires existing disposable ANIMA_LATE_BINDING_TEST_DATABASE_URL fixture")
    with psycopg.connect(database_url) as connection:
        assert connection.execute("SELECT current_database()").fetchone() == (
            "anima_late_binding_test",
        )
    from anima_ha.db.migrate import migrate

    migrate(database_url, 5)
    graph = PostgresHouseholdGraph(database_url)
    home = CanonicalNode(uuid4(), NodeKind.HOUSEHOLD, "Synthetic presence household")
    person = CanonicalNode(
        uuid4(), NodeKind.PERSON, "Synthetic owner", metadata={"semantic_role": "owner"}
    )
    resource = CanonicalNode(uuid4(), NodeKind.SENSOR, "Synthetic tracker")
    cap = CanonicalNode(uuid4(), NodeKind.CAPABILITY, "Synthetic presence")
    instance = uuid4()
    original = ProviderReference(
        uuid4(),
        "home_assistant",
        str(instance),
        "entity",
        "device_tracker.synthetic_" + cap.canonical_id.hex,
        cap.canonical_id,
        TargetKind.CAPABILITY,
        {"preserved": "synthetic"},
    )
    graph.commission(
        CommissioningDocument(
            1,
            (home, person, resource, cap),
            tuple(
                CanonicalRelationship(uuid4(), kind, source.canonical_id, target.canonical_id)
                for kind, source, target in (
                    (RelationshipType.MEMBER_OF, person, home),
                    (RelationshipType.INSTALLED_IN, resource, home),
                    (RelationshipType.EXPOSES, resource, cap),
                )
            ),
            provider_references=(original,),
        )
    )
    service = HouseholdPresenceService(
        graph, InMemoryTruthState(), classify_source=lambda ref: SignalKind.ROUTER_WIFI
    )
    handle = UUID(
        service.list_sources(home.canonical_id, ha_instance_id=instance)["items"][0][
            "source_handle"
        ]
    )
    args: BindingArguments = {
        "ha_instance_id": instance,
        "person_id": person.canonical_id,
        "source_handle": handle,
        "freshness_seconds": 300,
    }
    invocation = context(household_id=home.canonical_id, principal_id=person.canonical_id)
    result = service.bind_source(invocation, **args)
    assert service.bind_source(invocation, **args) == result
    refs = graph.provider_references_for(cap.canonical_id)
    assert len(refs) == 2
    assert next(r for r in refs if r.provider == "home_assistant") == original
    assert graph.related(person.canonical_id, RelationshipType.ASSOCIATED_WITH) == [resource]
    item = service.snapshot(home.canonical_id, ha_instance_id=instance, now=NOW)["items"][0]
    assert item["binding_status"] == "CONFIGURED"
    assert item["value"] == "UNKNOWN"
