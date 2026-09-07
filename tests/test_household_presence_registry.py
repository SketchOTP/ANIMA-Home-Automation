"""Real adapter normalization against synthetic pinned-HA registry fixtures.

Only the qualification boolean may be added to inventory metadata. It qualifies
HA zone semantics, not physical router health, device ownership or human presence.
"""

from __future__ import annotations

import asyncio
import json
from copy import deepcopy
from dataclasses import replace
from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock

import pytest
from test_home_assistant import FakeConnection, snapshot
from test_home_assistant import adapter_parts as adapter_parts

from anima_ha.home_assistant import HassClientConnection


@pytest.mark.parametrize(
    "fields,expected",
    [
        ({}, False),
        ({"options": {}}, True),
        ({"options": {"device_tracker": {}}}, True),
        ({"options": {"device_tracker": {"associated_zone": "zone.home"}}}, True),
        ({"options": {"device_tracker": {"associated_zone": "zone.private_site"}}}, False),
        ({"options": None}, False),
        ({"options": []}, False),
        ({"options": "PRIVATE"}, False),
        ({"options": {"device_tracker": None}}, False),
        ({"options": {"device_tracker": []}}, False),
        ({"options": {"device_tracker": "PRIVATE"}}, False),
        ({"options": {"device_tracker": {"associated_zone": None}}}, False),
        ({"options": {"device_tracker": {"associated_zone": ""}}}, False),
        ({"options": {"device_tracker": {"associated_zone": []}}}, False),
        ({"options": {"device_tracker": {"associated_zone": {}}}}, False),
        ({"options": {"device_tracker": {"associated_zone": True}}}, False),
    ],
)
def test_registry_home_zone_projection_and_no_options_persistence(
    adapter_parts: Any,
    fields: dict[str, Any],
    expected: bool,
) -> None:
    adapter, _, _, store = adapter_parts
    registry = {
        "entity_id": "device_tracker.synthetic",
        "platform": "synthetic_router",
        "disabled_by": None,
        **fields,
    }
    before = deepcopy(registry)
    adapter.start(FakeConnection(replace(snapshot(), entities=(registry,))))
    projected = next(o for o in store.objects if o.kind == "entity")
    assert projected.metadata["presence_home_zone_qualified"] is expected
    assert projected.metadata["platform"] == "synthetic_router"
    assert projected.metadata["disabled_by"] is None
    assert registry == before
    persisted = json.dumps(store.inventory(adapter.config.instance_id))
    for forbidden in ("options", "associated_zone", "zone.private_site", "PRIVATE"):
        assert forbidden not in persisted


def test_private_options_are_not_copied_even_when_home_is_qualified(adapter_parts: Any) -> None:
    adapter, _, _, store = adapter_parts
    registry = {
        "entity_id": "device_tracker.synthetic",
        "options": {
            "device_tracker": {
                "associated_zone": "zone.home",
                "mac": "02:00:00:00:00:01",
                "ssid": "PRIVATE_SSID",
                "latitude": "PRIVATE_LOCATION",
            },
            "another_domain": {"secret": "PRIVATE_SECRET"},
        },
    }
    adapter.start(FakeConnection(replace(snapshot(), entities=(registry,))))
    projected = next(o for o in store.objects if o.kind == "entity")
    assert projected.metadata == {"presence_home_zone_qualified": True}
    persisted = json.dumps(store.inventory(adapter.config.instance_id))
    for forbidden in (
        "options",
        "associated_zone",
        "02:00:00:00:00:01",
        "PRIVATE",
        "latitude",
        "ssid",
        '"mac"',
    ):
        assert forbidden not in persisted


@pytest.mark.parametrize(
    "entity_id", ["sensor.synthetic", "person.synthetic", "device_trackerish.synthetic"]
)
def test_non_tracker_registry_records_do_not_gain_presence_qualification(
    adapter_parts: Any, entity_id: str
) -> None:
    adapter, _, _, _ = adapter_parts
    result = adapter._provider_object(
        "entity",
        {
            "entity_id": entity_id,
            "options": {
                "device_tracker": {"associated_zone": "zone.home"},
            },
        },
    )
    assert "presence_home_zone_qualified" not in result.metadata
    assert "options" not in result.metadata


def test_disabled_flag_preserved_for_separate_runtime_eligibility_gate(adapter_parts: Any) -> None:
    adapter, _, _, _ = adapter_parts
    result = adapter._provider_object(
        "entity", {"entity_id": "device_tracker.synthetic", "disabled_by": "user", "options": {}}
    )
    assert result.metadata == {"disabled_by": "user", "presence_home_zone_qualified": True}
    # This boolean says home-zone semantics only, not that disabled data is usable.


def private_connection(entry: Any, states: Any) -> tuple[HassClientConnection, Any]:
    # Exercise the actual coroutine without creating a socket, SDK loop/thread,
    # token, or production connection. AsyncMock stands in for the exact SDK API.
    client = SimpleNamespace(
        get_entity_registry_entry=AsyncMock(return_value=entry),
        get_states=AsyncMock(return_value=states),
    )
    connection = object.__new__(HassClientConnection)
    connection._client = client
    return connection, client


@pytest.mark.parametrize(
    "fields",
    [
        {},
        {"options": None},
        {"options": []},
        {"options": {"device_tracker": None}},
        {"options": {"device_tracker": {"associated_zone": "zone.private_site"}}},
        {"options": {"device_tracker": {"associated_zone": None}}},
        {"options": {}, "disabled_by": "user"},
        {"options": {}, "disabled_by": "integration"},
        {"options": {}, "entity_id": "device_tracker.other"},
    ],
)
def test_private_helper_registry_gate_precedes_state_read(fields: dict[str, Any]) -> None:
    entry = {"entity_id": "device_tracker.synthetic", **fields}
    connection, client = private_connection(entry, [])
    assert asyncio.run(connection._presence_source_kind_async("device_tracker.synthetic")) is None
    client.get_entity_registry_entry.assert_awaited_once_with("device_tracker.synthetic")
    client.get_states.assert_not_awaited()


@pytest.mark.parametrize(
    "options", [{}, {"device_tracker": {}}, {"device_tracker": {"associated_zone": "zone.home"}}]
)
@pytest.mark.parametrize("kind", ["gps", "router"])
def test_private_helper_returns_only_qualified_kind(options: dict[str, Any], kind: str) -> None:
    entry = {
        "entity_id": "device_tracker.synthetic",
        "disabled_by": None,
        "options": {
            **options,
            "private_domain": {"mac": "02:00:00:00:00:01", "location": "PRIVATE"},
        },
    }
    states = [
        {
            "entity_id": "device_tracker.synthetic",
            "state": "home",
            "attributes": {
                "source_type": kind,
                "mac": "02:00:00:00:00:01",
                "latitude": "PRIVATE",
            },
        }
    ]
    entry_before, states_before = deepcopy(entry), deepcopy(states)
    connection, client = private_connection(entry, states)
    result = asyncio.run(connection._presence_source_kind_async("device_tracker.synthetic"))
    assert result == kind
    assert isinstance(result, str)
    assert "PRIVATE" not in result and "02:00" not in result
    assert (entry, states) == (entry_before, states_before)
    client.get_entity_registry_entry.assert_awaited_once_with("device_tracker.synthetic")
    client.get_states.assert_awaited_once_with()


@pytest.mark.parametrize("kind", [None, "bluetooth", "UNKNOWN", "PRIVATE", True, [], {}])
def test_private_helper_rejects_invalid_source_type(kind: Any) -> None:
    connection, _ = private_connection(
        {"entity_id": "device_tracker.synthetic", "options": {}},
        [{"entity_id": "device_tracker.synthetic", "attributes": {"source_type": kind}}],
    )
    assert asyncio.run(connection._presence_source_kind_async("device_tracker.synthetic")) is None


@pytest.mark.parametrize("attributes", [None, [], "PRIVATE", {}])
def test_private_helper_rejects_malformed_attributes(attributes: Any) -> None:
    connection, _ = private_connection(
        {"entity_id": "device_tracker.synthetic", "options": {}},
        [{"entity_id": "device_tracker.synthetic", "attributes": attributes}],
    )
    assert asyncio.run(connection._presence_source_kind_async("device_tracker.synthetic")) is None


def test_private_helper_missing_state_never_uses_another_entity() -> None:
    connection, _ = private_connection(
        {"entity_id": "device_tracker.synthetic", "options": {}},
        [{"entity_id": "device_tracker.other", "attributes": {"source_type": "router"}}],
    )
    assert asyncio.run(connection._presence_source_kind_async("device_tracker.synthetic")) is None


def test_private_helper_non_tracker_and_missing_client_require_no_sdk_calls() -> None:
    connection, client = private_connection({}, [])
    assert asyncio.run(connection._presence_source_kind_async("sensor.synthetic")) is None
    client.get_entity_registry_entry.assert_not_awaited()
    connection._client = None
    assert asyncio.run(connection._presence_source_kind_async("device_tracker.synthetic")) is None
