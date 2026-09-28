from __future__ import annotations

from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from uuid import UUID

import pytest

from anima_ha.graph import CanonicalNode, NodeKind
from anima_ha.sentry_boundary import CoreSentryBoundary, SentryBoundaryError
from anima_ha.sentry_sensor_status import build_sensor_status
from anima_ha.truth import TruthResolution, TruthStatus

HOUSEHOLD = UUID("00000000-0000-0000-0000-000000000001")
KITCHEN = UUID("00000000-0000-0000-0000-000000000101")
BASEMENT = UUID("00000000-0000-0000-0000-000000000102")
TAPO = UUID("00000000-0000-0000-0000-000000000103")
TYM = UUID("00000000-0000-0000-0000-000000000201")
GARAGE = UUID("00000000-0000-0000-0000-000000000104")
BACKYARD = UUID("00000000-0000-0000-0000-000000000105")
FRONT_DOOR = UUID("00000000-0000-0000-0000-000000000106")


class Graph:
    def __init__(self) -> None:
        self.resources = [
            CanonicalNode(KITCHEN, NodeKind.SENSOR, "SenseGuard Kitchen"),
            CanonicalNode(BASEMENT, NodeKind.SENSOR, "SenseGuard Basement"),
            CanonicalNode(
                TAPO,
                NodeKind.RESOURCE,
                "Front Door Lock",
                metadata={"provider": "tapo_android_notification", "resource_type": "lock"},
            ),
            CanonicalNode(
                GARAGE,
                NodeKind.SENSOR,
                "Garage Camera",
                metadata={"provider": "wansview_android_notification"},
            ),
            CanonicalNode(
                BACKYARD,
                NodeKind.SENSOR,
                "Back Yard Camera",
                metadata={"provider": "wansview_android_notification"},
            ),
            CanonicalNode(FRONT_DOOR, NodeKind.RESOURCE, "Front Door"),
        ]
        self.people = [CanonicalNode(TYM, NodeKind.PERSON, "Tym")]

    def resources_in_place(self, household_id, recursive=True):
        assert household_id == HOUSEHOLD
        assert recursive is True
        return self.resources

    def members_of_household(self, household_id):
        assert household_id == HOUSEHOLD
        return self.people

    def truth_for_node(self, target_id, truth, *, now):
        assert truth is not None
        assert target_id == TYM
        return [
            (
                SimpleNamespace(semantic_attribute="presence.home"),
                TruthResolution(
                    "presence:tym",
                    TruthStatus.CURRENT_KNOWN,
                    value=True,
                    last_observed_at=now - timedelta(seconds=2),
                ),
            )
        ]


class Journal:
    def __init__(self, events):
        self.events = events

    def list_recent_events(self, *, limit):
        assert limit == 500
        return self.events


class FilteredJournal(Journal):
    def list_recent_events(self, *, limit, event_type=None):
        assert limit == 500
        if event_type is None:
            return self.events
        return [item for item in self.events if item.get("event_type") == event_type]


def event(event_type, source, subject_key, occurred_at, resource_id=None, **payload):
    if resource_id:
        payload.setdefault("resource_id", str(resource_id))
    return {
        "event_type": event_type,
        "source": source,
        "subject_key": subject_key,
        "occurred_at": occurred_at,
        "payload": payload,
        "metadata": {"household_id": str(HOUSEHOLD)},
    }


def test_build_sensor_status_maps_qualified_events_and_current_presence():
    now = datetime(2026, 9, 10, 12, 0, tzinfo=UTC)
    payload = build_sensor_status(
        HOUSEHOLD,
        graph=Graph(),
        truth=object(),
        journal=Journal(
            [
                event(
                    "senseguard.opened",
                    "anima:senseguard-policy",
                    f"senseguard/{KITCHEN}",
                    now - timedelta(seconds=3),
                    KITCHEN,
                    canonical_resource_id=str(KITCHEN),
                ),
                event(
                    "external.android.lock_reported",
                    "android-relay-report",
                    "lock/front-door",
                    now - timedelta(seconds=3),
                    TAPO,
                    event_kind="unlocked",
                    source_package="com.tplink.iot",
                ),
                event(
                    "external.android.motion_reported",
                    "android-relay-report",
                    "camera/garage",
                    now - timedelta(seconds=3),
                    GARAGE,
                    event_kind="motion_reported",
                    source_package="net.ajcloud.wansviewplus",
                ),
                event(
                    "household.ring.motion",
                    "anima.ring",
                    f"resource/{FRONT_DOOR}",
                    now - timedelta(seconds=3),
                    FRONT_DOOR,
                ),
            ]
        ),
        now=now,
    )
    rows = {row["key"]: row for row in payload["items"]}
    assert payload["status"] == "CURRENT"
    assert rows["senseguard_kitchen"]["active"] is True
    assert rows["tapo"]["active"] is True
    assert rows["wansview_garage"]["active"] is True
    assert rows["wansview_backyard"]["active"] is False
    assert rows["ring"]["active"] is True
    assert rows["senseguard_basement"]["active"] is False
    assert rows["person:" + str(TYM)]["status"] == "HOME"
    assert rows["person:" + str(TYM)]["active"] is True
    assert all("mac" not in key.casefold() for row in payload["items"] for key in row)


def test_build_sensor_status_expires_event_glow_and_ignores_closing_event():
    now = datetime(2026, 9, 10, 12, 0, tzinfo=UTC)
    payload = build_sensor_status(
        HOUSEHOLD,
        graph=Graph(),
        truth=object(),
        journal=Journal(
            [
                event(
                    "senseguard.opened",
                    "anima:senseguard-policy",
                    f"senseguard/{KITCHEN}",
                    now - timedelta(seconds=61),
                    KITCHEN,
                ),
                event(
                    "senseguard.closed",
                    "anima:senseguard-policy",
                    f"senseguard/{BASEMENT}",
                    now - timedelta(seconds=1),
                    BASEMENT,
                ),
            ]
        ),
        now=now,
    )
    rows = {row["key"]: row for row in payload["items"]}
    assert rows["senseguard_kitchen"]["active"] is False
    assert rows["senseguard_basement"]["last_event_at"] is None


def test_build_sensor_status_uses_status_transition_not_router_last_seen():
    now = datetime(2026, 9, 10, 12, 0, tzinfo=UTC)
    payload = build_sensor_status(
        HOUSEHOLD,
        graph=Graph(),
        truth=object(),
        journal=Journal([]),
        now=now,
        wifi_presence={
            "version": 1,
            "state": "READY",
            "observed_at": now.isoformat(),
            "households": {
                str(HOUSEHOLD): {
                    "people": {
                        str(TYM): {
                            "active": True,
                            "status": "HOME",
                            "last_seen_at": (now + timedelta(minutes=3)).isoformat(),
                            "last_status_changed_at": (
                                now - timedelta(minutes=8)
                            ).isoformat(),
                            "source": "LOCAL_ROUTER_MAC",
                        }
                    }
                }
            },
        },
    )
    row = next(item for item in payload["items"] if item["key"] == "person:" + str(TYM))
    assert row["active"] is True
    assert row["status"] == "HOME"
    assert row["last_event_at"] == (now - timedelta(minutes=8)).isoformat()
    assert "mac" not in str(row).casefold()


def test_build_sensor_status_does_not_turn_missing_wifi_transition_into_a_ping():
    now = datetime(2026, 9, 10, 12, 0, tzinfo=UTC)
    payload = build_sensor_status(
        HOUSEHOLD,
        graph=Graph(),
        truth=object(),
        journal=Journal([]),
        now=now,
        wifi_presence={
            "version": 1,
            "state": "READY",
            "observed_at": now.isoformat(),
            "households": {
                str(HOUSEHOLD): {
                    "people": {
                        str(TYM): {
                            "active": False,
                            "status": "UNKNOWN",
                            "last_seen_at": (now - timedelta(seconds=5)).isoformat(),
                            "source": "LOCAL_ROUTER_MAC",
                        }
                    }
                }
            },
        },
    )
    row = next(item for item in payload["items"] if item["key"] == "person:" + str(TYM))
    assert row["last_event_at"] is None


def test_build_sensor_status_keeps_sensor_history_outside_global_journal_window():
    now = datetime(2026, 9, 10, 12, 0, tzinfo=UTC)
    tapo_event = event(
        "external.android.lock_reported",
        "android-relay-report",
        "lock/front-door",
        now - timedelta(minutes=10),
        TAPO,
        event_kind="unlocked",
        source_package="com.tplink.iot",
    )
    noisy_events = [
        event(
            "truth.observation",
            "home-assistant",
            f"noise/{index}",
            now - timedelta(seconds=index),
        )
        for index in range(600)
    ]
    payload = build_sensor_status(
        HOUSEHOLD,
        graph=Graph(),
        truth=object(),
        journal=FilteredJournal([*noisy_events, tapo_event]),
        now=now,
    )
    row = next(item for item in payload["items"] if item["key"] == "tapo")
    assert row["active"] is False
    assert row["last_event_at"] == tapo_event["occurred_at"].isoformat()


def test_sentry_boundary_exposes_status_only_through_scoped_loader():
    seen = []
    payload = {"status": "CURRENT", "items": []}
    boundary = CoreSentryBoundary(
        object(),
        object(),
        object(),
        sensor_status_loader=lambda household_id: seen.append(household_id) or payload,
    )
    assert boundary.sensor_status(HOUSEHOLD) == payload
    assert seen == [HOUSEHOLD]


def test_sentry_boundary_fails_closed_when_status_loader_is_missing():
    boundary = CoreSentryBoundary(object(), object(), object())
    with pytest.raises(SentryBoundaryError, match="SENSOR_STATUS_UNAVAILABLE"):
        boundary.sensor_status(HOUSEHOLD)
