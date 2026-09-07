"""Presence callback tests: synthetic HA events, no devices, private raw evidence.

Continuity here means the HA stream only. These tests cannot establish that a
router reports its own outages correctly or that a device identifies a person.
"""

from __future__ import annotations

import json
from dataclasses import replace
from typing import Any
from uuid import UUID

import pytest
from test_household_presence import HOME, INSTANCE, NOW, Graph, binding, normalized_event

from anima_ha.events import EventEnvelope
from anima_ha.household_presence import HouseholdPresenceService, SignalKind
from anima_ha.household_presence_runtime import HouseholdPresenceEventRouter
from anima_ha.journal import AppendResult


class Journal:
    def __init__(self) -> None:
        self.events: dict[str, EventEnvelope] = {}
        self.positions: dict[str, int] = {}
        self.fail_next = False
        self.attempts = 0

    def append(self, event: EventEnvelope) -> AppendResult:
        self.attempts += 1
        if self.fail_next:
            self.fail_next = False
            raise RuntimeError("synthetic journal unavailable")
        duplicate = event.event_id in self.events
        if not duplicate:
            self.events[event.event_id] = event
            self.positions[event.event_id] = 500 + len(self.events)
        return AppendResult(event.event_id, self.positions[event.event_id], duplicate)


class Harness:
    def __init__(self) -> None:
        self.binding = binding(SignalKind.ROUTER_WIFI)
        graph = Graph()
        graph.add(self.binding)
        self.service = HouseholdPresenceService(graph, graph.truth)
        self.online = True
        self.epoch: Any = ("synthetic connection", "sync-1")
        self.journal = Journal()
        self.dispatched: list[tuple[EventEnvelope, int]] = []
        self.router = HouseholdPresenceEventRouter(
            self.service,
            HOME,
            INSTANCE,
            continuity=lambda: (self.online, self.epoch),
            journal=self.journal,
            dispatch=lambda event, pos: self.dispatched.append((event, pos)),
            now=lambda: NOW,
        )

    def event(self, value: str, age: int, **metadata: Any) -> EventEnvelope:
        event = normalized_event(self.binding, value, age=age)
        event.payload["metadata"]["attributes"] = {
            "mac": "02:00:00:00:00:01",
            "latitude": "PRIVATE_COORDINATES",
            "friendly_name": "PRIVATE_PERSON",
            "host_name": "PRIVATE_HOST",
        }
        return replace(event, metadata={"external_id": self.binding.entity_id, **metadata})


def test_initial_seed_coarse_edges_duplicate_and_dispatch_identity() -> None:
    h = Harness()
    assert h.router.handle(h.event("home", 30)) == []
    assert h.journal.events == {}
    assert h.dispatched == []
    source = h.event("not_home", 20)
    emitted = h.router.handle(source)
    assert len(emitted) == 1
    edge = h.journal.events[emitted[0]]
    assert edge.payload["transition"] == "DISCONNECTED"
    assert edge.payload["value"] == "NOT_DETECTED"
    assert edge.payload["is_authentication"] is False
    assert edge.payload["door_actor_verified"] is False
    assert edge.metadata["household_id"] == str(HOME)
    assert edge.causation_id == source.event_id
    assert edge.delivery_class.value == "GUARANTEED"
    assert edge.importance.value == "NORMAL"
    assert h.dispatched == [(edge, h.journal.positions[edge.event_id])]
    assert h.dispatched[0][0] is edge
    assert h.router.handle(source) == []
    assert len(h.dispatched) == 1
    reconnected = h.router.handle(h.event("home", 10))
    assert len(reconnected) == 1
    assert h.journal.events[reconnected[0]].payload["transition"] == "RECONNECTED"


def test_no_private_attributes_or_provider_identifiers_in_journal_or_dispatch() -> None:
    h = Harness()
    h.router.handle(h.event("not_home", 30))
    h.router.handle(h.event("home", 20))
    assert h.journal.events
    for event in h.journal.events.values():
        serialized = json.dumps(event.to_dict())
        for forbidden in (
            "attributes",
            "mac",
            "02:00:00:00:00:01",
            "latitude",
            "PRIVATE",
            "host_name",
            "device_tracker.",
            "external_id",
        ):
            assert forbidden not in serialized
        assert event.payload["observed_at"] != event.payload["received_at"]
        assert event.payload["physical_observed_at"] is None
    assert all(event is h.journal.events[event.event_id] for event, _ in h.dispatched)


@pytest.mark.parametrize(
    "epoch", [("synthetic connection", "sync-2"), ("new connection", "sync-1")]
)
def test_reconcile_or_connection_epoch_resets_initial_baseline(epoch: Any) -> None:
    h = Harness()
    h.router.handle(h.event("home", 30))
    h.epoch = epoch
    assert h.router.handle(h.event("not_home", 20)) == []
    assert not h.journal.events
    assert len(h.router.handle(h.event("home", 10))) == 1


def test_offline_clears_baseline_even_when_sync_epoch_is_unchanged() -> None:
    h = Harness()
    h.router.handle(h.event("home", 30))
    h.online = False
    assert h.router.handle(h.event("not_home", 20)) == []
    h.online = True
    assert h.router.handle(h.event("not_home", 15)) == []
    assert len(h.router.handle(h.event("home", 10))) == 1


@pytest.mark.parametrize("unknown", ["unknown", "unavailable", "PRIVATE_NAMED_ZONE"])
def test_unknown_and_unavailable_clear_matching_baseline_then_reseed(unknown: str) -> None:
    h = Harness()
    h.router.handle(h.event("home", 30))
    assert h.router.handle(h.event(unknown, 20)) == []
    assert h.router.handle(h.event("not_home", 15)) == []
    assert not h.journal.events
    assert len(h.router.handle(h.event("home", 10))) == 1


@pytest.mark.parametrize("flag", ["snapshot", "reconcile", "recovery", "binding_attribution"])
def test_non_live_observation_clears_baseline_and_cannot_emit_edge(flag: str) -> None:
    h = Harness()
    h.router.handle(h.event("home", 30))
    assert h.router.handle(h.event("not_home", 20, **{flag: True})) == []
    assert h.router.handle(h.event("not_home", 15)) == []
    assert not h.dispatched


def test_late_event_does_not_roll_back_baseline() -> None:
    h = Harness()
    h.router.handle(h.event("home", 30))
    assert len(h.router.handle(h.event("not_home", 20))) == 1
    assert h.router.handle(h.event("home", 25)) == []
    assert len(h.router.handle(h.event("home", 10))) == 1
    assert len(h.dispatched) == 2


def test_unrelated_traffic_does_not_query_household(monkeypatch: pytest.MonkeyPatch) -> None:
    h = Harness()

    def forbidden(*args: Any, **kwargs: Any) -> Any:
        raise AssertionError("unrelated traffic queried Graph")

    monkeypatch.setattr(h.service, "bindings_for_event", forbidden)
    assert (
        h.router.handle(replace(h.event("home", 20), metadata={"external_id": "sensor.synthetic"}))
        == []
    )


def test_foreign_instance_never_journals_or_dispatches() -> None:
    h = Harness()
    first = h.event("home", 30)
    second = h.event("not_home", 20)
    for event in (first, second):
        assert (
            h.router.handle(replace(event, source=f"provider:home_assistant:{UUID(int=999)}")) == []
        )
    assert not h.journal.events
    assert not h.dispatched


def test_failed_append_does_not_consume_transition_before_retry() -> None:
    h = Harness()
    h.router.handle(h.event("home", 30))
    edge = h.event("not_home", 20)
    h.journal.fail_next = True
    with pytest.raises(RuntimeError, match="synthetic journal unavailable"):
        h.router.handle(edge)
    assert not h.journal.events
    assert not h.dispatched
    assert len(h.router.handle(edge)) == 1
    assert len(h.journal.events) == 1
    assert len(h.dispatched) == 1


def test_failed_dispatch_retry_reuses_journal_event_id_and_position() -> None:
    h = Harness()
    attempts: list[tuple[EventEnvelope, int]] = []

    def dispatch(event: EventEnvelope, position: int) -> None:
        attempts.append((event, position))
        if len(attempts) == 1:
            raise RuntimeError("synthetic attention unavailable")
        h.dispatched.append((event, position))

    h.router.dispatch = dispatch
    h.router.handle(h.event("home", 30))
    source = h.event("not_home", 20)
    with pytest.raises(RuntimeError, match="synthetic attention unavailable"):
        h.router.handle(source)
    assert len(h.journal.events) == 1
    assert not h.dispatched
    assert len(h.router.handle(source)) == 1
    assert len(h.journal.events) == 1
    assert len(h.dispatched) == 1
    assert attempts[0] == attempts[1]
    assert attempts[0][0].event_id == h.dispatched[0][0].event_id
    assert attempts[0][1] == h.dispatched[0][1]
    assert h.router.handle(source) == []
    # This proves caller-driven same-event retry, not background delivery.
    assert len(attempts) == 2
