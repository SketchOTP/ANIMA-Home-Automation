"""Sanitized, household-scoped signal status for the SENTRY display.

This is a read projection only.  It deliberately does not expose Home
Assistant state payloads, vendor notification text, phone MAC addresses, or
any control capability.  Device indicators are short-lived visual hints based
on the latest qualified journal event; people indicators reflect current
``presence.home`` Truth.
"""

from __future__ import annotations

import re
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID

from anima_ha.graph import CanonicalNode, NodeKind
from anima_ha.truth import TruthStatus

# Keep the drawer indicator visible long enough for a person to notice, while
# still making it a transient signal rather than a representation of current
# device state.  A later event refreshes the window because the projection
# always selects the newest qualified event.
SENSOR_EVENT_WINDOW_SECONDS = 60
MAX_RECENT_EVENTS = 500
WIFI_STATUS_MAX_AGE_SECONDS = 90
SENSOR_EVENT_TYPES = (
    "senseguard.opened",
    "external.android.motion_reported",
    "external.android.lock_reported",
    "household.ring.motion",
    "household.ring.doorbell",
)


@dataclass(frozen=True, slots=True)
class SensorDefinition:
    key: str
    label: str
    trigger: str
    aliases: tuple[str, ...]


SENSOR_DEFINITIONS = (
    SensorDefinition(
        "senseguard_kitchen",
        "SenseGuard Kitchen",
        "opened",
        ("senseguard", "kitchen"),
    ),
    SensorDefinition(
        "senseguard_basement",
        "SenseGuard Basement",
        "opened",
        ("senseguard", "basement"),
    ),
    SensorDefinition(
        "wansview_garage",
        "Wansview Garage",
        "motion",
        ("wansview", "garage"),
    ),
    SensorDefinition(
        "wansview_backyard",
        "Wansview Backyard",
        "motion",
        ("wansview", "backyard"),
    ),
    SensorDefinition("ring", "Ring", "motion or doorbell", ("ring",)),
    SensorDefinition("tapo", "Tapo", "unlocked", ("tapo",)),
)

_SAFE_CONTAINER_KEYS = (
    "provider",
    "vendor",
    "external_id",
    "entity_id",
    "canonical_resource_id",
    "resource_id",
    "resource_name",
    "device_name",
    "notification_type",
    "event_type",
    "event_kind",
    "senseguard_event_type",
    "source_package",
    "camera_resource_id",
    "state",
    "trigger",
    "event",
)
_WORD = re.compile(r"[a-z0-9]+")


def _words(value: Any) -> set[str]:
    return set(_WORD.findall(str(value).casefold()))


def _structured_values(container: Any) -> Iterable[str]:
    if not isinstance(container, dict):
        return ()
    values: list[str] = []
    for key in _SAFE_CONTAINER_KEYS:
        value = container.get(key)
        if isinstance(value, (str, int, float, bool)):
            values.append(str(value))
    return values


def _event_text(event: dict[str, Any]) -> str:
    values = [event.get("event_type"), event.get("source"), event.get("subject_key")]
    values.extend(_structured_values(event.get("payload")))
    values.extend(_structured_values(event.get("metadata")))
    return " ".join(str(value) for value in values if value is not None).casefold()


def _node_text(node: CanonicalNode) -> str:
    values = [node.name, node.kind.value]
    values.extend(_structured_values(node.metadata))
    return " ".join(values).casefold()


def _resource_id(event: dict[str, Any]) -> UUID | None:
    for container_name in ("payload", "metadata"):
        container = event.get(container_name)
        if not isinstance(container, dict):
            continue
        for key in ("canonical_resource_id", "resource_id"):
            value = container.get(key)
            if value is not None:
                try:
                    return UUID(str(value))
                except (TypeError, ValueError):
                    pass
    subject = str(event.get("subject_key", ""))
    for prefix in ("senseguard/", "resource/", "sensor/"):
        if subject.startswith(prefix):
            try:
                return UUID(subject.removeprefix(prefix))
            except ValueError:
                return None
    return None


def _definition_from_text(text: str) -> SensorDefinition | None:
    words = _words(text)
    for definition in SENSOR_DEFINITIONS:
        if all(alias in words for alias in definition.aliases):
            return definition
    return None


def _definition_for_node(node: CanonicalNode) -> SensorDefinition | None:
    """Resolve the display identity from the commissioned canonical node.

    Vendor-backed Android resources intentionally keep their owner-facing names
    (for example ``Garage Camera``) instead of embedding the vendor name in the
    graph.  Their provider metadata is the authoritative bridge to the display
    identity.  The front-door resource is the commissioned Ring event target;
    the lock remains separately identified as Tapo by its provider metadata.
    """

    text = _node_text(node)
    definition = _definition_from_text(text)
    if definition is not None:
        return definition

    provider = str(node.metadata.get("provider", "")).casefold()
    words = _words(text)
    if "wansview" in provider:
        if "garage" in words:
            return next(item for item in SENSOR_DEFINITIONS if item.key == "wansview_garage")
        if "back" in words and "yard" in words:
            return next(item for item in SENSOR_DEFINITIONS if item.key == "wansview_backyard")
    if "tapo" in provider or (
        str(node.metadata.get("resource_type", "")).casefold() == "lock" and "lock" in words
    ):
        return next(item for item in SENSOR_DEFINITIONS if item.key == "tapo")
    if "ring" in provider or ("front" in words and "camera" in words):
        return next(item for item in SENSOR_DEFINITIONS if item.key == "ring")
    # The commissioned Ring event target is named "Front Door" in the graph,
    # while "Front Door Lock" is handled above as Tapo.
    if "front" in words and "door" in words and "lock" not in words:
        return next(item for item in SENSOR_DEFINITIONS if item.key == "ring")
    return None


def _definition_from_event(text: str) -> SensorDefinition | None:
    """Resolve vendor event families when a resource id is absent or stale."""

    definition = _definition_from_text(text)
    if definition is not None:
        return definition
    if "household.ring" in text or "anima.ring" in text:
        return next(item for item in SENSOR_DEFINITIONS if item.key == "ring")
    if "external.android.lock_reported" in text or "com.tplink.iot" in text:
        return next(item for item in SENSOR_DEFINITIONS if item.key == "tapo")
    if "wansviewplus" in text:
        words = _words(text)
        if "garage" in words:
            return next(item for item in SENSOR_DEFINITIONS if item.key == "wansview_garage")
        if "back" in words and "yard" in words:
            return next(item for item in SENSOR_DEFINITIONS if item.key == "wansview_backyard")
    return None


def _event_trigger_matches(definition: SensorDefinition, text: str) -> bool:
    words = _words(text)
    if definition.key.startswith("senseguard"):
        if words.intersection({"closed", "closing", "close", "off"}):
            return False
        return bool(words.intersection({"opened", "opening", "open", "on"})) or (
            "senseguard.opened" in text
        )
    if definition.key.startswith("wansview"):
        return bool(words.intersection({"motion", "motion_reported"})) and not words.intersection(
            {"nomotion", "clear"}
        )
    if definition.key == "ring":
        return bool(words.intersection({"motion", "doorbell", "ding"}))
    if definition.key == "tapo":
        return bool(words.intersection({"unlock", "unlocked", "unlocking"}))
    return False


def _occurred_at(event: dict[str, Any]) -> datetime | None:
    value = event.get("occurred_at")
    if not isinstance(value, datetime):
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def _event_label(definition: SensorDefinition) -> str:
    return {
        "opened": "Opened",
        "motion": "Motion detected",
        "motion or doorbell": "Motion or doorbell",
        "unlocked": "Unlocked",
    }[definition.trigger]


def _device_row(
    definition: SensorDefinition,
    node: CanonicalNode,
    event: dict[str, Any] | None,
    *,
    now: datetime,
) -> dict[str, Any]:
    occurred = _occurred_at(event or {})
    active = occurred is not None and now - occurred <= timedelta(
        seconds=SENSOR_EVENT_WINDOW_SECONDS
    )
    return {
        "sensor_id": str(node.canonical_id),
        "key": definition.key,
        "label": definition.label,
        "kind": "event",
        "trigger": definition.trigger,
        "active": active,
        "status": "ACTIVE" if active else "QUIET",
        "last_event_at": occurred.isoformat() if occurred else None,
        "last_event": _event_label(definition) if occurred else None,
        "registered_name": node.name,
    }


def _person_row(
    person: CanonicalNode,
    truth: Any,
    graph: Any,
    *,
    now: datetime,
    wifi_presence: dict[str, Any] | None = None,
) -> dict[str, Any]:
    state = "UNKNOWN"
    last_status_changed_at: datetime | None = None
    wifi = (wifi_presence or {}).get(str(person.canonical_id))
    wifi_configured = isinstance(wifi, dict)
    wifi_data: dict[str, Any] = wifi if isinstance(wifi, dict) else {}
    wifi_active = bool(wifi_data.get("active")) if wifi_configured else False
    if wifi_configured:
        state = "HOME" if wifi_active else "UNKNOWN"
        raw_status_changed = wifi_data.get("last_status_changed_at")
        if isinstance(raw_status_changed, str):
            try:
                last_status_changed_at = datetime.fromisoformat(raw_status_changed).astimezone(UTC)
            except (TypeError, ValueError, OverflowError):
                last_status_changed_at = None
    if truth is not None:
        for binding, resolution in graph.truth_for_node(person.canonical_id, truth, now=now):
            if binding.semantic_attribute != "presence.home":
                continue
            if not wifi_configured and resolution.status == TruthStatus.CURRENT_KNOWN:
                state = "HOME" if resolution.value is True else "AWAY"
                last_status_changed_at = resolution.last_observed_at
            break
    return {
        "sensor_id": f"person:{person.canonical_id}",
        "key": f"person:{person.canonical_id}",
        "label": person.name,
        "kind": "presence",
        "trigger": "Wi-Fi / geofence presence",
        "active": wifi_active if wifi_configured else state == "HOME",
        "status": state,
        "last_event_at": last_status_changed_at.astimezone(UTC).isoformat()
        if last_status_changed_at is not None
        else None,
        "last_event": "Phone detected on Wi-Fi / geofence"
        if wifi_active or state == "HOME"
        else "Phone not currently detected"
        if state == "AWAY"
        else "Presence unavailable",
    }


def _fresh_wifi_presence(value: dict[str, Any] | None, *, now: datetime) -> dict[str, Any] | None:
    if not isinstance(value, dict):
        return None
    observed_at = value.get("observed_at")
    if not isinstance(observed_at, str):
        return None
    try:
        observed = datetime.fromisoformat(observed_at).astimezone(UTC)
    except (TypeError, ValueError, OverflowError):
        return None
    age = now - observed
    if age < timedelta(0) or age > timedelta(seconds=WIFI_STATUS_MAX_AGE_SECONDS):
        return None
    return value


def _recent_sensor_events(journal: Any) -> list[dict[str, Any]]:
    """Read a bounded recent slice for each sensor family.

    The global journal is intentionally high-volume: Truth refreshes can push
    an older but still important device event beyond a single global window.
    Per-family slices preserve bounded reads while keeping each drawer signal's
    last qualified event discoverable.  Small test doubles and older adapters
    that only support the original call shape retain the old bounded fallback.
    """

    events: list[dict[str, Any]] = []
    try:
        for event_type in SENSOR_EVENT_TYPES:
            events.extend(
                journal.list_recent_events(limit=MAX_RECENT_EVENTS, event_type=event_type)
            )
    except TypeError:
        fallback = journal.list_recent_events(limit=MAX_RECENT_EVENTS)
        return fallback if isinstance(fallback, list) else []
    return events


def build_sensor_status(
    household_id: UUID,
    *,
    graph: Any,
    truth: Any,
    journal: Any,
    now: datetime | None = None,
    wifi_presence: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build a small, sanitized status packet for the SENTRY display."""

    current = (now or datetime.now(UTC)).astimezone(UTC)
    resources = list(graph.resources_in_place(household_id, recursive=True))
    nodes_by_id = {node.canonical_id: node for node in resources}
    definitions_by_id: dict[UUID, SensorDefinition] = {}
    rows: list[dict[str, Any]] = []
    for node in resources:
        definition = _definition_for_node(node)
        if definition is None:
            continue
        definitions_by_id[node.canonical_id] = definition

    latest: dict[UUID, tuple[datetime, dict[str, Any]]] = {}
    latest_by_definition: dict[str, tuple[datetime, dict[str, Any]]] = {}
    for event in _recent_sensor_events(journal):
        if not isinstance(event, dict):
            continue
        metadata = event.get("metadata")
        if not isinstance(metadata, dict) or str(metadata.get("household_id")) != str(household_id):
            continue
        occurred = _occurred_at(event)
        if occurred is None:
            continue
        resource_id = _resource_id(event)
        definition = definitions_by_id.get(resource_id) if resource_id is not None else None
        if definition is None:
            definition = _definition_from_event(_event_text(event))
        if definition is None or not _event_trigger_matches(definition, _event_text(event)):
            continue
        if resource_id is not None and resource_id in nodes_by_id:
            previous = latest.get(resource_id)
            if previous is None or occurred > previous[0]:
                latest[resource_id] = (occurred, event)
        previous_definition = latest_by_definition.get(definition.key)
        if previous_definition is None or occurred > previous_definition[0]:
            latest_by_definition[definition.key] = (occurred, event)

    for node in resources:
        definition = definitions_by_id.get(node.canonical_id)
        if definition is None:
            continue
        event_entry: tuple[datetime, dict[str, Any]] | None = latest.get(node.canonical_id)
        if event_entry is None:
            fallback = latest_by_definition.get(definition.key)
            event_entry = fallback
        device_event: dict[str, Any] | None = event_entry[1] if event_entry is not None else None
        rows.append(_device_row(definition, node, device_event, now=current))

    wifi_presence = _fresh_wifi_presence(wifi_presence, now=current)
    households = (wifi_presence or {}).get("households", {})
    scoped_wifi = households.get(str(household_id), {}) if isinstance(households, dict) else {}
    scoped_people = scoped_wifi.get("people", {}) if isinstance(scoped_wifi, dict) else {}
    for person in graph.members_of_household(household_id):
        if person.kind == NodeKind.PERSON:
            rows.append(
                _person_row(
                    person,
                    truth,
                    graph,
                    now=current,
                    wifi_presence=scoped_people if isinstance(scoped_people, dict) else None,
                )
            )

    return {
        "status": "CURRENT",
        "generated_at": current.isoformat(),
        "event_window_seconds": SENSOR_EVENT_WINDOW_SECONDS,
        "items": rows,
    }
