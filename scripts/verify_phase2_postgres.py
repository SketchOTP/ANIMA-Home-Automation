"""Bounded PostgreSQL integration evidence for the Phase 2 graph substrate."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import uuid4

from anima_ha.events import EventEnvelope, EvidenceKind, ObservationState, TruthObservation
from anima_ha.fixtures import sample_household_document
from anima_ha.graph import PostgresHouseholdGraph, ProviderReference
from anima_ha.journal import PostgresRealityStore

DATABASE_URL = "postgresql://anima:anima_dev_only@localhost:55432/anima"


def main() -> int:
    graph = PostgresHouseholdGraph(DATABASE_URL)
    document = sample_household_document()
    expected_front_lock = next(node for node in document.nodes if node.name == "Front Door Lock")
    graph.map_provider_reference(
        ProviderReference(
            uuid4(),
            "home_assistant",
            "sample",
            "device",
            "ha-device-front",
            expected_front_lock.canonical_id,
        ),
        allow_remap=True,
    )
    first = graph.commission(document)
    second = graph.commission(document)
    assert 0 <= first.created_nodes <= 27 and 0 <= first.created_relationships <= 31
    assert second.audit_events == 0
    house = next(node for node in graph.list_places() if node.name == "House")
    garage = next(node for node in graph.list_places() if node.name == "Garage")
    office = next(node for node in graph.list_places() if node.name == "Office")
    assert {node.name for node in graph.resources_in_place(house.canonical_id)} >= {
        "Front Door Lock",
        "Garage Door",
        "Garage Door Contact",
    }
    assert {
        node.name for node in graph.resources_in_place(garage.canonical_id, recursive=False)
    } == {
        "Garage Door",
        "Garage Door Contact",
    }
    assert {node.name for node in graph.exterior_entrances()} == {"Front Door", "Garage Door"}
    front_entrance = next(node for node in graph.exterior_entrances() if node.name == "Front Door")
    assert {node.name for node in graph.entrance_connections(front_entrance.canonical_id)} == {
        "Outside",
        "Foyer",
    }
    garage_door = next(
        node
        for node in graph.resources_in_place(garage.canonical_id, recursive=False)
        if node.name == "Garage Door"
    )
    assert [
        node.name
        for node in graph.sensors_monitoring(
            next(
                node for node in graph.exterior_entrances() if node.name == "Garage Door"
            ).canonical_id
        )
    ] == ["Garage Door Contact"]
    front_lock = graph.resolve_provider_reference(
        "home_assistant", "sample", "device", "ha-device-front"
    )
    assert front_lock is not None and front_lock.name == "Front Door Lock"
    assert {node.name for node in graph.resource_capabilities(front_lock.canonical_id)} == {
        "Lock State",
        "Lock",
        "Unlock",
    }
    assert len(graph.provider_references_for(front_lock.canonical_id)) >= 3
    assert graph.resolve_alias("my office").candidates[0].canonical_id == office.canonical_id
    assert {node.name for node in graph.resources_with_capability("lock.lock")} == {
        "Front Door Lock"
    }
    assert {node.name for node in graph.security_sensitive_resources()} >= {
        "Front Door Lock",
        "Front Door",
    }
    assert garage_door.name == "Garage Door"

    truth_store = PostgresRealityStore(DATABASE_URL)
    alex = next(node for node in document.nodes if node.name == "Alex")
    truth_key = f"presence/person/{alex.canonical_id}/home"
    now = datetime.now(UTC).replace(microsecond=0)
    observation = TruthObservation(
        truth_key=truth_key,
        source="phase2-simulator",
        state=ObservationState.KNOWN,
        value=True,
        observed_at=now,
        received_at=now + timedelta(seconds=1),
        confidence=0.99,
        evidence_kind=EvidenceKind.DIRECT,
        freshness_seconds=300,
    )
    event = EventEnvelope.create(
        event_id=f"phase2-presence-{uuid4()}",
        event_type="truth.observation",
        source=observation.source,
        subject_key=truth_key,
        occurred_at=observation.observed_at,
        recorded_at=observation.received_at,
        payload=observation.to_payload(),
        source_event_id=f"phase2-presence-source-{uuid4()}",
    )
    truth_store.ingest(event)
    home = graph.people_currently_home(truth_store.projection)
    assert [item["person"].name for item in home] == ["Alex"]
    assert home[0]["truth"].observations[0].event_id == event.event_id

    replacement_target = next(node for node in document.nodes if node.name == "Garage Door")
    remap = ProviderReference(
        uuid4(),
        "home_assistant",
        "phase2-test",
        "device",
        "remap-device",
        replacement_target.canonical_id,
    )
    original_target = ProviderReference(
        uuid4(),
        "home_assistant",
        "phase2-test",
        "device",
        "remap-device",
        front_lock.canonical_id,
    )
    graph.map_provider_reference(original_target, allow_remap=True)
    try:
        graph.map_provider_reference(remap)
    except Exception as exc:
        assert "collision" in str(exc)
    else:
        raise AssertionError("provider collision was not rejected")
    graph.map_provider_reference(remap, allow_remap=True)
    assert (
        graph.resolve_provider_reference(
            "home_assistant", "phase2-test", "device", "remap-device"
        ).name
        == "Garage Door"
    )

    graph.rename_node(office.canonical_id, "Study")
    assert graph.get_node(office.canonical_id).name == "Study"
    assert graph.resolve_alias("office").candidates[0].canonical_id == office.canonical_id
    assert len(graph.audit_events()) >= first.audit_events
    print("PHASE2_POSTGRES_INTEGRATION_PASS")
    print(f"commission_first={first}")
    print(f"commission_second={second}")
    print(f"audit_events={len(graph.audit_events())}")
    print(f"home={[item['person'].name for item in home]}")
    print("semantic_queries=PASS")
    print("truth_binding_provenance=PASS")
    print("provider_collision_and_remap=PASS")
    print("rename_identity_and_alias=PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
