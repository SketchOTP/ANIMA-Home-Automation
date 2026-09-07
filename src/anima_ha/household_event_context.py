"""Sparse, source-qualified household evidence; never an arrival/identity oracle.

Only Core's bounded normalized event projections are read. Raw HA payloads,
model transcripts and external research content are deliberately not eligible.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID

import psycopg
from psycopg.rows import dict_row

EVENT_SOURCES = {
    "senseguard.opened": "anima:senseguard-policy",
    "senseguard.event": "anima:senseguard-policy",
    "household.presence.connection_changed": "anima.household_presence",
    "household.ring.motion": "anima.ring",
    "household.ring.doorbell": "anima.ring",
}
CORRELATION_GUIDANCE = (
    "These are nearby observations, not a concluded arrival or authenticated identity. "
    "Compare source time, receipt delay, member/device assignments, independence and conflicts. "
    "Ring motion does not identify a visitor; missing doorbell events do not prove nobody rang. "
    "Wi-Fi reconnection is device presence; disconnection is non-detection, not human departure. "
    "A lock actor is usable only when a qualified source links that actor to that exact unlock; "
    "cached labels and expected routines do not do this. Do not invent missing lock or room "
    "motion observations. If evidence supports an arrival, label it an inference, use relevant "
    "preferences, and avoid repeat greetings. Read fresh state for follow-up questions."
)


def _time(value: Any) -> datetime:
    stamp = value if isinstance(value, datetime) else datetime.fromisoformat(str(value))
    if stamp.tzinfo is None or stamp.utcoffset() is None:
        raise ValueError("evidence time must be aware")
    return stamp.astimezone(UTC)


def project_event(
    row: dict[str, Any], household_id: UUID, resources: set[UUID], members: set[UUID]
) -> dict[str, Any] | None:
    """Whitelist fields, exact sources and current household membership."""
    kind = row.get("event_type")
    if kind not in EVENT_SOURCES or row.get("source") != EVENT_SOURCES[kind]:
        return None
    metadata, payload = row.get("metadata"), row.get("payload")
    if not isinstance(metadata, dict) or not isinstance(payload, dict):
        return None
    if metadata.get("household_id") != str(household_id):
        return None
    if any(metadata.get(key) or payload.get(key) for key in ("snapshot", "restored", "recovery")):
        return None
    try:
        stamp, received = _time(row["occurred_at"]), _time(row["recorded_at"])
        # Generated Core event IDs are UUIDs, never free text or arbitrary provider keys.
        event_id = str(UUID(str(row["event_id"])))
        if kind == "household.presence.connection_changed":
            canonical = UUID(str(payload["person_id"]))
            if canonical not in members or payload.get("household_id") != str(household_id):
                return None
            if payload.get("transition") not in {"RECONNECTED", "DISCONNECTED"}:
                return None
            if payload.get("is_authentication") is not False:
                return None
        else:
            canonical = UUID(str(payload.get("canonical_resource_id", payload.get("resource_id"))))
            if canonical not in resources:
                return None
        if stamp > received:
            return None
    except (ValueError, TypeError, KeyError):
        return None
    projected: dict[str, Any] = {
        "event_id": event_id,
        "event_type": kind,
        "occurred_at": stamp.isoformat(),
        "recorded_at": received.isoformat(),
        "canonical_id": str(canonical),
        "authority": "NONE",
        "identity_verified": False,
        "external_content_trust": "EXTERNAL_UNTRUSTED",
        "time_basis": "HA_EVENT_RECEIVED"
        if str(kind).startswith("household.ring.")
        else "SOURCE_OBSERVATION",
    }
    if kind == "household.presence.connection_changed":
        projected["transition"] = payload["transition"]
    try:
        projected["source_event_id"] = str(
            UUID(str(row.get("source_event_id") or row.get("causation_id")))
        )
    except (TypeError, ValueError):
        pass
    return projected


class HouseholdEventEvidence:
    def __init__(self, database_url: str, graph: Any) -> None:
        self.database_url, self.graph = database_url, graph

    def recent_household_evidence(
        self,
        household_id: UUID,
        *,
        limit: int = 30,
        since: datetime | None = None,
        event_ids: tuple[str, ...] | None = None,
        now: datetime | None = None,
    ) -> dict[str, Any]:
        at = _time(now or datetime.now(UTC))
        start = _time(since or at - timedelta(minutes=10))
        if type(limit) is not int or not 1 <= limit <= 2000:
            raise ValueError("evidence limit must be 1..2000")
        if start > at or start < at - timedelta(days=29):
            raise ValueError("evidence window must be within 29 days")
        if event_ids is not None:
            if not 1 <= len(event_ids) <= 12:
                raise ValueError("source reference count must be 1..12")
            event_ids = tuple(str(UUID(value)) for value in event_ids)
        resources = {n.canonical_id for n in self.graph.resources_in_place(household_id)}
        members = {n.canonical_id for n in self.graph.members_of_household(household_id)}
        with psycopg.connect(
            self.database_url,
            row_factory=dict_row,
            connect_timeout=5,
            options="-c statement_timeout=5000",
        ) as connection:
            rows = connection.execute(
                "SELECT event_id,event_type,source,source_event_id,causation_id,"
                "occurred_at,recorded_at,payload,metadata "
                "FROM anima_event_journal WHERE metadata->>'household_id'=%s "
                "AND occurred_at >= %s AND occurred_at <= %s AND recorded_at <= %s "
                "AND event_type=ANY(%s) AND source=ANY(%s) "
                "AND (%s::text[] IS NULL OR event_id=ANY(%s::text[])) "
                "ORDER BY occurred_at DESC,event_id DESC LIMIT %s",
                (
                    str(household_id),
                    start,
                    at,
                    at,
                    list(EVENT_SOURCES),
                    list(set(EVENT_SOURCES.values())),
                    list(event_ids) if event_ids is not None else None,
                    list(event_ids) if event_ids is not None else None,
                    limit + 1,
                ),
            ).fetchall()
        items = [
            value
            for row in rows[:limit]
            if (value := project_event(row, household_id, resources, members)) is not None
        ]
        if event_ids is None:
            unique: dict[tuple[str, str, str], dict[str, Any]] = {}
            for item in items:
                key = (
                    item.get("source_event_id", item["event_id"]),
                    item["event_type"],
                    item["canonical_id"],
                )
                unique.setdefault(key, item)
            items = list(unique.values())
        items.sort(key=lambda item: (item["occurred_at"], item["event_id"]))
        return {
            "status": "SUCCEEDED",
            "items": items,
            "truncated": len(rows) > limit,
            "window_start": start.isoformat(),
            "window_end": at.isoformat(),
            "authority": "NONE",
            "guidance": CORRELATION_GUIDANCE,
            "coverage": "BOUNDED_OBSERVATIONS_NOT_COMPLETE_HOUSEHOLD_HISTORY",
        }
