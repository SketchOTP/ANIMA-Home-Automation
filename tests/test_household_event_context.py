from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import uuid4

import pytest

from anima_ha.household_event_context import CORRELATION_GUIDANCE, project_event
from anima_ha.household_initiative import device_notification_matches, notification_disposition

NOW = datetime(2026, 9, 7, 18, tzinfo=UTC)


def row() -> tuple[Any, Any, dict[str, Any]]:
    home, resource = uuid4(), uuid4()
    return (
        home,
        resource,
        {
            "event_id": str(uuid4()),
            "source": "anima.ring",
            "event_type": "household.ring.motion",
            "occurred_at": NOW,
            "recorded_at": NOW + timedelta(seconds=1),
            "metadata": {"household_id": str(home)},
            "payload": {
                "resource_id": str(resource),
                "password": "SECRET_SENTINEL",
                "identity": "Jaden authenticated",
                "video_url": "https://not-allowed.invalid",
            },
        },
    )


def test_ring_projection_keeps_uncertainty_and_omits_untrusted_fields() -> None:
    home, resource, event = row()
    projected = project_event(event, home, {resource}, set())
    assert projected and projected["time_basis"] == "HA_EVENT_RECEIVED"
    assert projected["identity_verified"] is False
    assert projected["authority"] == "NONE"
    assert "SECRET_SENTINEL" not in json.dumps(projected)
    assert "Jaden" not in json.dumps(projected)
    assert "video_url" not in json.dumps(projected)
    assert "missing doorbell events do not prove nobody rang" in CORRELATION_GUIDANCE


@pytest.mark.parametrize(
    "change", ["source", "household", "resource", "future", "snapshot", "transcript"]
)
def test_reject_unqualified_event(change: str) -> None:
    home, resource, event = row()
    if change == "source":
        event["source"] = "model"
    if change == "household":
        event["metadata"]["household_id"] = str(uuid4())
    if change == "resource":
        event["payload"]["resource_id"] = str(uuid4())
    if change == "future":
        event["occurred_at"] = NOW + timedelta(days=1)
    if change == "snapshot":
        event["metadata"]["snapshot"] = True
    if change == "transcript":
        event["event_type"] = "user.request"
    assert project_event(event, home, {resource}, set()) is None


@pytest.mark.parametrize(
    "ready,enabled,always,explicit,review,expected",
    [
        (False, False, False, False, False, "LEARNING_REQUIRED"),
        (False, False, True, False, False, "ALWAYS_NOTIFY"),
        (False, False, False, True, False, "ALWAYS_NOTIFY"),
        (True, False, False, False, False, "PROACTIVE_DISABLED"),
        (True, True, False, False, False, "LEARNED_PROACTIVE"),
        (True, True, True, True, True, "REVIEW_SILENT"),
    ],
)
def test_notification_ceiling(
    ready: bool, enabled: bool, always: bool, explicit: bool, review: bool, expected: str
) -> None:
    request_id = uuid4()
    value = notification_disposition(
        request_id=request_id,
        event_type="household.ring.motion",
        ready=ready,
        config={
            "proactive_enabled": enabled,
            "always_notify": ["household.ring.motion"] if always else [],
        },
        explicit_alert=explicit,
        review=review,
        now=NOW,
    )
    assert value["reason"] == expected
    assert value["allowed"] == (expected in {"ALWAYS_NOTIFY", "LEARNED_PROACTIVE"})
    assert value["required"] == (expected == "ALWAYS_NOTIFY")
    assert value["request_id"] == str(request_id)


def test_unqualified_source_never_acquires_permission_from_model_config() -> None:
    result = notification_disposition(
        request_id=uuid4(),
        event_type=None,
        config={"always_notify": ["everything"], "proactive_enabled": True},
        ready=True,
        explicit_alert=True,
    )
    assert result["allowed"] is False


@pytest.mark.parametrize(
    "mode,hour,allowed,required",
    [
        ("ALWAYS", 18, True, True),
        ("NEVER", 18, False, False),
        ("TIME_WINDOW", 1, True, True),
        ("TIME_WINDOW", 12, False, False),
        ("CONTEXTUAL", 18, True, False),
    ],
)
def test_device_notification_rule_is_authoritative_before_household_default(
    mode: str, hour: int, allowed: bool, required: bool
) -> None:
    event_time = datetime(2026, 9, 7, hour, tzinfo=UTC)
    result = notification_disposition(
        request_id=uuid4(),
        event_type="household.ring.doorbell",
        config={"always_notify": ["household.ring.doorbell"], "proactive_enabled": True},
        ready=True,
        device_rule={
            "resource_id": str(uuid4()),
            "mode": mode,
            "start_local": "00:00",
            "end_local": "05:00",
            "timezone": "UTC",
        },
        event_occurred_at=event_time,
        now=event_time,
    )
    assert result["allowed"] is allowed
    assert result["required"] is required


@pytest.mark.parametrize(
    "selected,event_type,payload,expected",
    [
        ("UNLOCKED", "external.android.lock_reported", {"event_kind": "unlocked"}, True),
        ("UNLOCKED", "external.android.lock_reported", {"event_kind": "locked"}, False),
        ("DOORBELL", "household.ring.doorbell", {}, True),
        ("MOTION", "external.android.motion_reported", {}, True),
        ("ANY", "senseguard.opened", {}, True),
    ],
)
def test_device_notification_event_selector_is_bounded(
    selected: str, event_type: str, payload: dict[str, object], expected: bool
) -> None:
    assert device_notification_matches({"event_kind": selected}, event_type, payload) is expected
