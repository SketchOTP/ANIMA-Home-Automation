"""Late commissioning against an explicitly supplied, disposable PostgreSQL DB."""

from __future__ import annotations

import os
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from typing import Any, cast
from uuid import UUID, uuid4

import psycopg
import pytest
from test_home_assistant import FakeConnection, FakeStore, snapshot, state

from anima_ha.db.migrate import migrate
from anima_ha.graph import (
    CanonicalNode,
    CanonicalRelationship,
    CommissioningDocument,
    NodeKind,
    PostgresHouseholdGraph,
    RelationshipType,
)
from anima_ha.home_assistant import (
    HAInstanceConfig,
    HomeAssistantAdapter,
    HomeAssistantPlugin,
    inventory_handle,
)
from anima_ha.journal import PostgresRealityStore
from anima_ha.truth import TruthStatus


def test_late_six_entity_commission_survives_dedup_restart_and_rebuild() -> None:
    database_url = os.environ.get("ANIMA_LATE_BINDING_TEST_DATABASE_URL")
    if not database_url:
        pytest.skip("requires a disposable ANIMA_LATE_BINDING_TEST_DATABASE_URL")
    with psycopg.connect(database_url) as connection:
        assert connection.execute("SELECT current_database()").fetchone() == (
            "anima_late_binding_test",
        ), "refuse any database not explicitly named for this isolated test"
    migrate(database_url, 5)
    graph = PostgresHouseholdGraph(database_url)
    reality = PostgresRealityStore(database_url)
    household = CanonicalNode(uuid4(), NodeKind.HOUSEHOLD, "Synthetic household")
    room = CanonicalNode(uuid4(), NodeKind.ROOM, "Basement")
    graph.commission(
        CommissioningDocument(
            1,
            (household, room),
            (
                CanonicalRelationship(
                    uuid4(), RelationshipType.CONTAINS, household.canonical_id, room.canonical_id
                ),
            ),
        )
    )
    config = HAInstanceConfig(
        uuid4(), "ws://synthetic.test/api/websocket", "TEST_ONLY", ssl=False, freshness_seconds=60
    )
    callbacks: list[Any] = []
    adapter = HomeAssistantAdapter(
        config,
        reality,
        graph,
        FakeStore(),  # type: ignore[arg-type]
        normalized_event_callback=callbacks.append,
    )
    transport = FakeConnection(replace(snapshot(), entities=(), states=()))
    adapter.start(transport)
    plugin = HomeAssistantPlugin(adapter, lambda token: transport)
    arguments = {
        "device_handle": inventory_handle(config.instance_id, "device", "ha-device"),
        "name": "SenseGuard Basement",
        "place_id": str(room.canonical_id),
    }

    def commission() -> dict[str, Any]:
        return cast(
            dict[str, Any],
            plugin.invoke_for_household("commission_device", arguments, 5, household.canonical_id),
        )

    try:
        initial = commission()
        resource_id = UUID(initial["resource_id"])
        assert initial["entity_count"] == 0
        assert graph.resource_capabilities(resource_id) == []
        entity_ids = (
            "binary_sensor.synthetic_contact",
            "sensor.synthetic_battery",
            "button.synthetic_identify",
            "update.synthetic_firmware",
            "sensor.synthetic_lqi",
            "sensor.synthetic_rssi",
        )
        old_stamp = (datetime.now(UTC) - timedelta(hours=1)).isoformat()
        raw_states = tuple(
            state(entity, value, old_stamp)
            for entity, value in zip(
                entity_ids[:4], ("off", "100", "unknown", "unknown"), strict=True
            )
        )
        transport.initial = replace(
            transport.initial,
            entities=tuple(
                {
                    "entity_id": entity,
                    "device_id": "ha-device",
                    "platform": "zha",
                    "disabled_by": "integration" if index >= 4 else None,
                }
                for index, entity in enumerate(entity_ids)
            ),
            states=raw_states,
        )
        adapter.reconcile()
        source = f"provider:home_assistant:{config.provider_scope}"
        originals = reality.journal.list_events(event_type="truth.observation", source=source)
        assert len(originals) == 4
        assert all(row["payload"]["truth_key"].startswith("provider/") for row in originals)

        bound = commission()
        assert bound["resource_id"] == str(resource_id)
        assert bound["entity_count"] == 6
        capabilities = graph.resource_capabilities(resource_id)
        assert len(capabilities) == 6
        assert graph.get_node(resource_id).kind == NodeKind.SENSOR  # type: ignore[union-attr]
        assert [item.canonical_id for item in graph.resources_in_place(room.canonical_id)] == [
            resource_id
        ]
        all_events = reality.journal.list_events(event_type="truth.observation", source=source)
        assert len(all_events) == 8
        assert all_events[:4] == originals  # Immutable IDs, payloads, timestamps and positions.
        for original in originals:
            # Compare by causation, not entity/registry ordering.
            matching = next(
                row for row in all_events[4:] if row["causation_id"] == original["event_id"]
            )
            assert matching["occurred_at"] == original["occurred_at"]
            for field in ("observed_at", "received_at", "freshness_seconds", "state", "value"):
                assert matching["payload"][field] == original["payload"][field]

        by_entity = {cap.metadata["provider_entity_id"]: cap for cap in capabilities}
        for index, entity in enumerate(entity_ids):
            bindings = graph.truth_for_node(by_entity[entity].canonical_id, reality.projection)
            assert len(bindings) == 1
            expected = TruthStatus.STALE if index < 2 else TruthStatus.UNKNOWN
            assert bindings[0][1].status == expected
            assert bool(bindings[0][1].observations) == (index < 4)
        assert callbacks == []  # Attribution and snapshots are not physical event callbacks.

        count = reality.journal.count()
        last_position = reality.journal.list_events()[-1]["journal_position"]
        repeat = commission()
        assert repeat["commission"] == {
            "created_nodes": 0,
            "created_relationships": 0,
            "created_provider_references": 0,
        }
        # Reconcile retains its existing audit event, but creates no new evidence.
        assert reality.journal.count() == count + 1
        assert [
            row["event_type"] for row in reality.journal.list_events(after_position=last_position)
        ] == ["home_assistant.reconciled"]
        assert (
            reality.journal.list_events(event_type="truth.observation", source=source) == all_events
        )
        count = reality.journal.count()
        # Fresh facade and rebuild must recover from the journal, not a patched SQL projection.
        restored = PostgresRealityStore(database_url)
        restored.projection.rebuild()
        contact_key = f"state/capability/{by_entity[entity_ids[0]].canonical_id}/value"
        assert restored.projection.get(contact_key).status == TruthStatus.STALE
        assert reality.journal.count() == count

        later = state(entity_ids[0], "on", datetime.now(UTC).isoformat())
        adapter.receive_provider_event(
            {"event_type": "state_changed", "data": {"new_state": later}}
        )
        adapter.seed_commissioned_truth(entity_ids[0])
        resolution = restored.projection.get(contact_key)
        assert resolution.status == TruthStatus.CURRENT_KNOWN
        assert resolution.value == "on"
        assert resolution.last_observed_at == datetime.fromisoformat(later["last_updated"])
        assert len(callbacks) == 1
        assert reality.journal.count() == count + 1
    finally:
        adapter.stop()
