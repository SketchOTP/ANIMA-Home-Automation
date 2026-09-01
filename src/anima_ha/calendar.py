"""ANIMA-owned local calendar backed by the canonical PostgreSQL substrate."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, replace
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any, Protocol, cast
from uuid import UUID, uuid4
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

import psycopg
from psycopg.rows import dict_row

from anima_ha.events import DeliveryClass, EventEnvelope, EventImportance
from anima_ha.plugins import (
    CORE_VERSION,
    MANIFEST_VERSION,
    ExternalContentTrust,
    Idempotency,
    InvocationContext,
    PluginManifest,
    PluginValidationError,
    RuntimeKind,
    TrustClass,
)

MAX_CALENDAR_DESCRIPTION = 4_000
MAX_CALENDAR_LOCATION = 500
MAX_CALENDAR_RESULTS = 50


class CalendarError(RuntimeError):
    """Base class for local-calendar failures."""


class CalendarNotFound(CalendarError):
    """The requested event does not exist in the household."""


class CalendarConflict(CalendarError):
    """A replay or optimistic update conflicts with canonical state."""


class CalendarStatus(StrEnum):
    ACTIVE = "ACTIVE"
    CANCELLED = "CANCELLED"


def _utc(value: datetime, name: str) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{name} must be timezone-aware")
    return value.astimezone(UTC)


def _zone(value: str) -> str:
    if not value.strip():
        raise ValueError("timezone is required")
    try:
        ZoneInfo(value)
    except ZoneInfoNotFoundError as exc:
        raise ValueError(f"unknown IANA timezone: {value}") from exc
    return value


def _parse_datetime(value: Any, name: str) -> datetime:
    if not isinstance(value, str):
        raise ValueError(f"{name} must be an ISO-8601 string")
    try:
        return _utc(datetime.fromisoformat(value.replace("Z", "+00:00")), name)
    except ValueError:
        raise ValueError(f"{name} must be a timezone-aware ISO-8601 datetime") from None


@dataclass(frozen=True, slots=True)
class CalendarEvent:
    event_id: UUID
    household_id: UUID
    title: str
    start_at: datetime
    end_at: datetime
    timezone: str
    location: str
    description: str
    status: CalendarStatus
    version: int
    creator_principal_id: UUID | None
    creator_episode_id: UUID | None
    creation_idempotency_key: str
    creation_fingerprint: str
    created_at: datetime
    updated_at: datetime

    @classmethod
    def create(
        cls,
        *,
        household_id: UUID,
        title: str,
        start_at: datetime,
        end_at: datetime,
        timezone: str,
        location: str = "",
        description: str = "",
        creation_idempotency_key: str,
        creator_principal_id: UUID | None,
        creator_episode_id: UUID | None,
        now: datetime | None = None,
        event_id: UUID | None = None,
    ) -> CalendarEvent:
        title = title.strip()
        location = location.strip()
        description = description.strip()
        start = _utc(start_at, "start_at")
        end = _utc(end_at, "end_at")
        timezone = _zone(timezone)
        if not 1 <= len(title) <= 200:
            raise ValueError("title must contain 1 to 200 characters")
        if len(location) > MAX_CALENDAR_LOCATION:
            raise ValueError("location exceeds the calendar bound")
        if len(description) > MAX_CALENDAR_DESCRIPTION:
            raise ValueError("description exceeds the calendar bound")
        if end <= start:
            raise ValueError("end_at must be after start_at")
        if not creation_idempotency_key.strip():
            raise ValueError("creation idempotency key is required")
        fingerprint = hashlib.sha256(
            json.dumps(
                {
                    "household_id": str(household_id),
                    "title": title,
                    "start_at": start.isoformat(),
                    "end_at": end.isoformat(),
                    "timezone": timezone,
                    "location": location,
                    "description": description,
                },
                sort_keys=True,
                separators=(",", ":"),
            ).encode()
        ).hexdigest()
        at = _utc(now or datetime.now(UTC), "now")
        return cls(
            event_id=event_id or uuid4(),
            household_id=household_id,
            title=title,
            start_at=start,
            end_at=end,
            timezone=timezone,
            location=location,
            description=description,
            status=CalendarStatus.ACTIVE,
            version=1,
            creator_principal_id=creator_principal_id,
            creator_episode_id=creator_episode_id,
            creation_idempotency_key=creation_idempotency_key,
            creation_fingerprint=fingerprint,
            created_at=at,
            updated_at=at,
        )

    def to_payload(self) -> dict[str, Any]:
        return {
            "event_id": str(self.event_id),
            "household_id": str(self.household_id),
            "title": self.title,
            "start_at": self.start_at.isoformat(),
            "end_at": self.end_at.isoformat(),
            "timezone": self.timezone,
            "location": self.location,
            "description": self.description,
            "status": self.status.value,
            "version": self.version,
            "creator_principal_id": str(self.creator_principal_id)
            if self.creator_principal_id
            else None,
            "creator_episode_id": str(self.creator_episode_id) if self.creator_episode_id else None,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
        }


class CalendarStore(Protocol):
    def create(self, event: CalendarEvent) -> CalendarEvent: ...

    def get(self, household_id: UUID, event_id: UUID) -> CalendarEvent: ...

    def list_events(
        self,
        household_id: UUID,
        start_at: datetime,
        end_at: datetime,
        limit: int,
        *,
        include_cancelled: bool = False,
    ) -> list[CalendarEvent]: ...

    def update(
        self,
        household_id: UUID,
        event_id: UUID,
        expected_version: int,
        changes: dict[str, Any],
        now: datetime,
    ) -> CalendarEvent: ...

    def cancel(
        self, household_id: UUID, event_id: UUID, expected_version: int, now: datetime
    ) -> CalendarEvent: ...


def _updated_event(event: CalendarEvent, changes: dict[str, Any], now: datetime) -> CalendarEvent:
    values: dict[str, Any] = {}
    for key in ("title", "location", "description"):
        if key in changes:
            values[key] = str(changes[key]).strip()
    if "start_at" in changes:
        values["start_at"] = _parse_datetime(changes["start_at"], "start_at")
    if "end_at" in changes:
        values["end_at"] = _parse_datetime(changes["end_at"], "end_at")
    if "timezone" in changes:
        values["timezone"] = _zone(str(changes["timezone"]))
    candidate = replace(event, **values, version=event.version + 1, updated_at=_utc(now, "now"))
    if not 1 <= len(candidate.title) <= 200:
        raise ValueError("title must contain 1 to 200 characters")
    if len(candidate.location) > MAX_CALENDAR_LOCATION:
        raise ValueError("location exceeds the calendar bound")
    if len(candidate.description) > MAX_CALENDAR_DESCRIPTION:
        raise ValueError("description exceeds the calendar bound")
    if candidate.end_at <= candidate.start_at:
        raise ValueError("end_at must be after start_at")
    return candidate


class InMemoryCalendarStore:
    def __init__(self) -> None:
        self.events: dict[UUID, CalendarEvent] = {}
        self.keys: dict[str, UUID] = {}

    def create(self, event: CalendarEvent) -> CalendarEvent:
        existing_id = self.keys.get(event.creation_idempotency_key)
        if existing_id is not None:
            existing = self.events[existing_id]
            if existing.creation_fingerprint != event.creation_fingerprint:
                raise CalendarConflict("calendar creation key was reused with different parameters")
            return existing
        self.events[event.event_id] = event
        self.keys[event.creation_idempotency_key] = event.event_id
        return event

    def get(self, household_id: UUID, event_id: UUID) -> CalendarEvent:
        event = self.events.get(event_id)
        if event is None or event.household_id != household_id:
            raise CalendarNotFound(str(event_id))
        return event

    def list_events(
        self,
        household_id: UUID,
        start_at: datetime,
        end_at: datetime,
        limit: int,
        *,
        include_cancelled: bool = False,
    ) -> list[CalendarEvent]:
        start, end = _utc(start_at, "start_at"), _utc(end_at, "end_at")
        return sorted(
            [
                event
                for event in self.events.values()
                if event.household_id == household_id
                and (include_cancelled or event.status == CalendarStatus.ACTIVE)
                and event.start_at < end
                and event.end_at > start
            ],
            key=lambda event: (event.start_at, event.event_id),
        )[: max(1, min(limit, MAX_CALENDAR_RESULTS))]

    def update(
        self,
        household_id: UUID,
        event_id: UUID,
        expected_version: int,
        changes: dict[str, Any],
        now: datetime,
    ) -> CalendarEvent:
        event = self.get(household_id, event_id)
        if event.status != CalendarStatus.ACTIVE:
            raise CalendarConflict("cancelled calendar events cannot be updated")
        if event.version != expected_version:
            raise CalendarConflict("calendar event version is stale")
        updated = _updated_event(event, changes, now)
        self.events[event_id] = updated
        return updated

    def cancel(
        self, household_id: UUID, event_id: UUID, expected_version: int, now: datetime
    ) -> CalendarEvent:
        event = self.get(household_id, event_id)
        if event.status == CalendarStatus.CANCELLED:
            return event
        if event.version != expected_version:
            raise CalendarConflict("calendar event version is stale")
        updated = replace(
            event,
            status=CalendarStatus.CANCELLED,
            version=event.version + 1,
            updated_at=_utc(now, "now"),
        )
        self.events[event_id] = updated
        return updated


def _from_row(row: dict[str, Any]) -> CalendarEvent:
    return CalendarEvent(
        event_id=row["event_id"],
        household_id=row["household_id"],
        title=row["title"],
        start_at=row["start_at"],
        end_at=row["end_at"],
        timezone=row["timezone"],
        location=row["location"],
        description=row["description"],
        status=CalendarStatus(row["status"]),
        version=row["version"],
        creator_principal_id=row["creator_principal_id"],
        creator_episode_id=row["creator_episode_id"],
        creation_idempotency_key=row["creation_idempotency_key"],
        creation_fingerprint=row["creation_fingerprint"],
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )


class PostgresCalendarStore:
    def __init__(self, database_url: str, connect_timeout: int = 5) -> None:
        self.database_url = database_url
        self.connect_timeout = connect_timeout

    def create(self, event: CalendarEvent) -> CalendarEvent:
        with psycopg.connect(self.database_url, connect_timeout=self.connect_timeout) as connection:
            with connection.cursor(row_factory=dict_row) as cursor:
                cursor.execute(
                    """INSERT INTO anima_calendar_events
                    (event_id, household_id, title, start_at, end_at, timezone, location,
                     description, status, version, creator_principal_id, creator_episode_id,
                     creation_idempotency_key, creation_fingerprint, created_at, updated_at)
                    VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                    ON CONFLICT (creation_idempotency_key) DO NOTHING""",
                    (
                        event.event_id,
                        event.household_id,
                        event.title,
                        event.start_at,
                        event.end_at,
                        event.timezone,
                        event.location,
                        event.description,
                        event.status.value,
                        event.version,
                        event.creator_principal_id,
                        event.creator_episode_id,
                        event.creation_idempotency_key,
                        event.creation_fingerprint,
                        event.created_at,
                        event.updated_at,
                    ),
                )
                cursor.execute(
                    "SELECT * FROM anima_calendar_events WHERE creation_idempotency_key=%s",
                    (event.creation_idempotency_key,),
                )
                row = cursor.fetchone()
                if row is None:
                    raise CalendarConflict("calendar creation could not be resolved")
                stored = _from_row(row)
                if stored.creation_fingerprint != event.creation_fingerprint:
                    raise CalendarConflict(
                        "calendar creation key was reused with different parameters"
                    )
            connection.commit()
        return stored

    def get(self, household_id: UUID, event_id: UUID) -> CalendarEvent:
        with (
            psycopg.connect(
                self.database_url, connect_timeout=self.connect_timeout, row_factory=dict_row
            ) as connection,
            connection.cursor() as cursor,
        ):
            cursor.execute(
                "SELECT * FROM anima_calendar_events WHERE household_id=%s AND event_id=%s",
                (household_id, event_id),
            )
            row = cursor.fetchone()
        if row is None:
            raise CalendarNotFound(str(event_id))
        return _from_row(row)

    def list_events(
        self,
        household_id: UUID,
        start_at: datetime,
        end_at: datetime,
        limit: int,
        *,
        include_cancelled: bool = False,
    ) -> list[CalendarEvent]:
        start, end = _utc(start_at, "start_at"), _utc(end_at, "end_at")
        status_clause = "" if include_cancelled else "AND status = 'ACTIVE'"
        with (
            psycopg.connect(
                self.database_url, connect_timeout=self.connect_timeout, row_factory=dict_row
            ) as connection,
            connection.cursor() as cursor,
        ):
            cursor.execute(
                f"""SELECT * FROM anima_calendar_events
                WHERE household_id=%s AND start_at < %s AND end_at > %s {status_clause}
                ORDER BY start_at, event_id LIMIT %s""",
                (household_id, end, start, max(1, min(limit, MAX_CALENDAR_RESULTS))),
            )
            return [_from_row(row) for row in cursor.fetchall()]

    def update(
        self,
        household_id: UUID,
        event_id: UUID,
        expected_version: int,
        changes: dict[str, Any],
        now: datetime,
    ) -> CalendarEvent:
        current = self.get(household_id, event_id)
        if current.status != CalendarStatus.ACTIVE:
            raise CalendarConflict("cancelled calendar events cannot be updated")
        if current.version != expected_version:
            raise CalendarConflict("calendar event version is stale")
        updated = _updated_event(current, changes, now)
        with psycopg.connect(self.database_url, connect_timeout=self.connect_timeout) as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """UPDATE anima_calendar_events SET title=%s, start_at=%s, end_at=%s,
                    timezone=%s, location=%s, description=%s, version=%s, updated_at=%s
                    WHERE household_id=%s AND event_id=%s AND status='ACTIVE' AND version=%s""",
                    (
                        updated.title,
                        updated.start_at,
                        updated.end_at,
                        updated.timezone,
                        updated.location,
                        updated.description,
                        updated.version,
                        updated.updated_at,
                        household_id,
                        event_id,
                        expected_version,
                    ),
                )
                if cursor.rowcount != 1:
                    raise CalendarConflict("calendar event version is stale")
            connection.commit()
        return updated

    def cancel(
        self, household_id: UUID, event_id: UUID, expected_version: int, now: datetime
    ) -> CalendarEvent:
        current = self.get(household_id, event_id)
        if current.status == CalendarStatus.CANCELLED:
            return current
        if current.version != expected_version:
            raise CalendarConflict("calendar event version is stale")
        updated = replace(
            current,
            status=CalendarStatus.CANCELLED,
            version=current.version + 1,
            updated_at=_utc(now, "now"),
        )
        with psycopg.connect(self.database_url, connect_timeout=self.connect_timeout) as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """UPDATE anima_calendar_events SET status='CANCELLED', version=%s,
                    updated_at=%s WHERE household_id=%s AND event_id=%s
                    AND status='ACTIVE' AND version=%s""",
                    (updated.version, updated.updated_at, household_id, event_id, expected_version),
                )
                if cursor.rowcount != 1:
                    raise CalendarConflict("calendar event version is stale")
            connection.commit()
        return updated


class CalendarService:
    def __init__(self, store: CalendarStore, event_sink: Any | None = None) -> None:
        self.store = store
        self.event_sink = event_sink

    def create(self, *, context: InvocationContext, arguments: dict[str, Any]) -> CalendarEvent:
        event = CalendarEvent.create(
            household_id=context.household_id,
            title=str(arguments["title"]),
            start_at=_parse_datetime(arguments["start_at"], "start_at"),
            end_at=_parse_datetime(arguments["end_at"], "end_at"),
            timezone=str(arguments["timezone"]),
            location=str(arguments.get("location", "")),
            description=str(arguments.get("description", "")),
            creation_idempotency_key=context.system_idempotency_key,
            creator_principal_id=context.principal_id,
            creator_episode_id=context.episode_id,
        )
        stored = self.store.create(event)
        if stored.event_id == event.event_id:
            self._audit(
                "calendar.event_created",
                stored,
                context=context,
                payload={"changed_fields": ["event"]},
            )
        return stored

    def get(self, *, household_id: UUID, event_id: UUID) -> CalendarEvent:
        return self.store.get(household_id, event_id)

    def list_events(
        self,
        *,
        household_id: UUID,
        start_at: datetime,
        end_at: datetime,
        limit: int,
        include_cancelled: bool = False,
    ) -> list[CalendarEvent]:
        return self.store.list_events(
            household_id, start_at, end_at, limit, include_cancelled=include_cancelled
        )

    def update(
        self,
        *,
        context: InvocationContext,
        event_id: UUID,
        expected_version: int,
        changes: dict[str, Any],
    ) -> CalendarEvent:
        event = self.store.update(
            context.household_id,
            event_id,
            expected_version,
            changes,
            datetime.now(UTC),
        )
        self._audit(
            "calendar.event_updated",
            event,
            context=context,
            payload={"changed_fields": sorted(changes)},
        )
        return event

    def cancel(
        self,
        *,
        context: InvocationContext,
        event_id: UUID,
        expected_version: int,
    ) -> CalendarEvent:
        event = self.store.cancel(
            context.household_id, event_id, expected_version, datetime.now(UTC)
        )
        if event.status == CalendarStatus.CANCELLED and event.version == expected_version + 1:
            self._audit(
                "calendar.event_cancelled",
                event,
                context=context,
                payload={"changed_fields": ["status"]},
            )
        return event

    def _audit(
        self,
        event_type: str,
        event: CalendarEvent,
        *,
        context: InvocationContext,
        payload: dict[str, Any],
    ) -> None:
        if self.event_sink is None:
            return
        self.event_sink.append(
            EventEnvelope.create(
                event_id=str(uuid4()),
                event_type=event_type,
                source="anima:calendar",
                subject_key=f"calendar/{event.event_id}",
                occurred_at=event.updated_at,
                payload={
                    "event_id": str(event.event_id),
                    "principal_id": str(context.principal_id) if context.principal_id else None,
                    "episode_id": str(context.episode_id),
                    "origin": context.origin.value,
                    "tool_request_id": str(context.tool_request_id),
                    "system_idempotency_key": context.system_idempotency_key,
                    "version": event.version,
                    **payload,
                },
                importance=EventImportance.IMPORTANT,
                delivery_class=DeliveryClass.GUARANTEED,
                metadata={"household_id": str(event.household_id), "version": event.version},
            )
        )


def _tool(
    name: str, description: str, schema: dict[str, Any], *, read_only: bool
) -> dict[str, Any]:
    return {
        "name": name,
        "description": description,
        "input_schema": schema,
        # Local calendar persistence is a trusted, policy-gated internal
        # mutation, not an external-provider write.  Core still controls the
        # execution boundary; this risk class only selects the existing Phase
        # 4 low-risk authorization semantics.
        "risk_class": "READ_ONLY" if read_only else "LOW_RISK_HOME_CONTROL",
        "semantic_action": f"calendar.{name}",
        "read_only": read_only,
        "idempotency": Idempotency.IDEMPOTENT.value if read_only else Idempotency.KEYED.value,
        "external_content_trust": ExternalContentTrust.LOCAL_TRUSTED.value,
    }


_EVENT_ID = {"type": "string", "format": "uuid"}
_CALENDAR_SCHEMA = {
    "type": "object",
    "properties": {
        "title": {"type": "string", "minLength": 1, "maxLength": 200},
        "start_at": {"type": "string", "maxLength": 64},
        "end_at": {"type": "string", "maxLength": 64},
        "timezone": {"type": "string", "maxLength": 64},
        "location": {"type": "string", "maxLength": MAX_CALENDAR_LOCATION},
        "description": {"type": "string", "maxLength": MAX_CALENDAR_DESCRIPTION},
    },
    "required": ["title", "start_at", "end_at", "timezone"],
    "additionalProperties": False,
}

CALENDAR_MANIFEST = PluginManifest(
    plugin_id="anima.calendar",
    plugin_version="0.1.0",
    manifest_version=MANIFEST_VERSION,
    requires_core=CORE_VERSION,
    name="ANIMA local calendar",
    description="Household-scoped first-party calendar backed by PostgreSQL",
    runtime_kind=RuntimeKind.TRUSTED_NATIVE,
    trust_class=TrustClass.TRUSTED_NATIVE,
    capabilities=("calendar",),
    tools=(
        _tool(
            "list_events",
            "List events in a bounded time window",
            {
                "type": "object",
                "properties": {
                    "start_at": {"type": "string", "maxLength": 64},
                    "end_at": {"type": "string", "maxLength": 64},
                    "limit": {"type": "integer", "minimum": 1, "maximum": MAX_CALENDAR_RESULTS},
                    "include_cancelled": {"type": "boolean"},
                },
                "required": ["start_at", "end_at"],
                "additionalProperties": False,
            },
            read_only=True,
        ),
        _tool(
            "get_event",
            "Get one household calendar event",
            {
                "type": "object",
                "properties": {"event_id": _EVENT_ID},
                "required": ["event_id"],
                "additionalProperties": False,
            },
            read_only=True,
        ),
        _tool("create_event", "Create a local calendar event", _CALENDAR_SCHEMA, read_only=False),
        _tool(
            "update_event",
            "Update a local calendar event with optimistic version protection",
            {
                "type": "object",
                "properties": {
                    "event_id": _EVENT_ID,
                    "expected_version": {"type": "integer", "minimum": 1},
                    **{
                        key: value
                        for key, value in cast(
                            dict[str, Any], _CALENDAR_SCHEMA["properties"]
                        ).items()
                        if key != "title"
                    },
                    "title": {"type": "string", "minLength": 1, "maxLength": 200},
                },
                "required": ["event_id", "expected_version"],
                "additionalProperties": False,
            },
            read_only=False,
        ),
        _tool(
            "cancel_event",
            "Cancel a local calendar event without deleting its history",
            {
                "type": "object",
                "properties": {
                    "event_id": _EVENT_ID,
                    "expected_version": {"type": "integer", "minimum": 1},
                },
                "required": ["event_id", "expected_version"],
                "additionalProperties": False,
            },
            read_only=False,
        ),
    ),
    source="builtin:anima_ha.calendar",
)


class CalendarNativePlugin:
    def __init__(self, service: CalendarService) -> None:
        self.service = service

    def start(self, secret_env: dict[str, str]) -> None:
        if secret_env:
            raise PluginValidationError("local calendar accepts no secrets")

    def stop(self) -> None:
        return None

    def list_tools(self) -> list[dict[str, Any]]:
        return [dict(item) for item in CALENDAR_MANIFEST.tools]

    def invoke(self, name: str, arguments: dict[str, Any], timeout: float) -> Any:
        raise PluginValidationError("local calendar requires trusted invocation context")

    def invoke_with_invocation_context(
        self, name: str, arguments: dict[str, Any], timeout: float, context: InvocationContext
    ) -> Any:
        del timeout
        if any(
            key in arguments
            for key in {"creator_principal_id", "creator_episode_id", "creation_idempotency_key"}
        ):
            raise PluginValidationError("calendar provenance and idempotency are system-owned")
        if name == "create_event":
            return {"event": self.service.create(context=context, arguments=arguments).to_payload()}
        if name == "get_event":
            event = self.service.get(
                household_id=context.household_id, event_id=UUID(str(arguments["event_id"]))
            )
            return {"event": event.to_payload()}
        if name == "list_events":
            events = self.service.list_events(
                household_id=context.household_id,
                start_at=_parse_datetime(arguments["start_at"], "start_at"),
                end_at=_parse_datetime(arguments["end_at"], "end_at"),
                limit=int(arguments.get("limit", 20)),
                include_cancelled=bool(arguments.get("include_cancelled", False)),
            )
            return {"events": [event.to_payload() for event in events]}
        event_id = UUID(str(arguments["event_id"]))
        expected_version = int(arguments["expected_version"])
        if name == "update_event":
            changes = {
                key: value
                for key, value in arguments.items()
                if key not in {"event_id", "expected_version"}
            }
            return {
                "event": self.service.update(
                    context=context,
                    event_id=event_id,
                    expected_version=expected_version,
                    changes=changes,
                ).to_payload()
            }
        if name == "cancel_event":
            return {
                "event": self.service.cancel(
                    context=context, event_id=event_id, expected_version=expected_version
                ).to_payload()
            }
        raise CalendarError(f"unknown calendar operation: {name}")
