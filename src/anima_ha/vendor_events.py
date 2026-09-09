"""Bounded SENTRY read access to sanitized passive-vendor Journal events.

The Android relay has already discarded notification prose, images, actions,
links, and credentials before these records reach PostgreSQL.  This plugin
exposes only canonical resource identity and the minimized event facts needed
for a fresh household follow-up.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import UUID

import psycopg
from psycopg.rows import dict_row

from anima_ha.graph import NodeKind, PostgresHouseholdGraph
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

_EVENT_TYPES = ("external.android.lock_reported", "external.android.motion_reported")
_MAX_RESULTS = 50


class VendorEventReadError(ValueError):
    """A bounded vendor-event read could not be satisfied safely."""


class PostgresVendorEventStore:
    def __init__(self, database_url: str, graph: PostgresHouseholdGraph) -> None:
        self.database_url, self.graph = database_url, graph

    def _resource_names(self, household_id: UUID) -> dict[UUID, str]:
        names: dict[UUID, str] = {}
        places = [
            self.graph.get_node(household_id),
            *self.graph.places_in_household(household_id),
        ]
        for place in places:
            if place is None or place.retired_at is not None:
                continue
            for resource in self.graph.resources_in_place(place.canonical_id):
                if resource.retired_at is None and resource.kind in {
                    NodeKind.RESOURCE,
                    NodeKind.SENSOR,
                }:
                    names[resource.canonical_id] = resource.name
        return names

    def list_recent(
        self, household_id: UUID, *, limit: int, before_position: int | None = None
    ) -> dict[str, Any]:
        if not 1 <= limit <= _MAX_RESULTS:
            raise VendorEventReadError("limit must be between 1 and 50")
        if before_position is not None and before_position < 1:
            raise VendorEventReadError("invalid cursor")
        names = self._resource_names(household_id)
        params: dict[str, Any] = {
            "household_id": str(household_id),
            "event_types": list(_EVENT_TYPES),
            "limit": limit + 1,
        }
        cursor_clause = ""
        if before_position is not None:
            cursor_clause = "AND journal_position < %(before_position)s"
            params["before_position"] = before_position
        with (
            psycopg.connect(
                self.database_url, row_factory=dict_row, connect_timeout=5
            ) as connection,
            connection.cursor() as cursor,
        ):
            cursor.execute(
                f"""
                SELECT journal_position, event_id, event_type, occurred_at, recorded_at,
                       payload, metadata
                FROM anima_event_journal
                WHERE metadata->>'household_id' = %(household_id)s
                  AND event_type = ANY(%(event_types)s)
                  {cursor_clause}
                ORDER BY journal_position DESC
                LIMIT %(limit)s
                """,
                params,
            )
            rows = list(cursor.fetchall())
        has_more = len(rows) > limit
        rows = rows[:limit]
        items: list[dict[str, Any]] = []
        for row in rows:
            payload = row["payload"] if isinstance(row["payload"], dict) else {}
            try:
                resource_id = UUID(str(payload.get("resource_id", "")))
            except ValueError:
                continue
            resource_name = names.get(resource_id)
            if resource_name is None:
                continue
            item: dict[str, Any] = {
                "event_id": str(row["event_id"]),
                "event_type": str(row["event_type"]),
                "resource_id": str(resource_id),
                "resource_name": resource_name,
                "event_kind": str(payload.get("event_kind", "unknown")),
                "occurred_at": row["occurred_at"].astimezone(UTC).isoformat(),
                "recorded_at": row["recorded_at"].astimezone(UTC).isoformat(),
                "timestamp_basis": str(payload.get("timestamp_basis", "UNKNOWN")),
                "report_freshness": str(payload.get("report_freshness", "UNKNOWN")),
                "identity_status": str(payload.get("identity_status", "UNKNOWN")),
                "authority": "NONE",
            }
            if item["event_type"] == "external.android.lock_reported":
                profile = payload.get("reported_profile_ref")
                method = payload.get("reported_method")
                if isinstance(profile, str) and profile:
                    item["reported_profile_ref"] = profile[:80]
                if isinstance(method, str) and method:
                    item["reported_method"] = method[:40]
            items.append(item)
        return {
            "schema_version": 1,
            "as_of": datetime.now(UTC).isoformat(),
            "items": items,
            "next_cursor": str(rows[-1]["journal_position"]) if has_more and rows else None,
            "external_content_trust": "EXTERNAL_UNTRUSTED",
            "identity_warning": "Reported lock identity is device-reported and unverified.",
        }


class VendorEventsNativePlugin:
    def __init__(self, store: PostgresVendorEventStore) -> None:
        self.store = store

    def start(self, secret_env: dict[str, str]) -> None:
        del secret_env

    def stop(self) -> None:
        return None

    def list_tools(self) -> list[dict[str, Any]]:
        return [dict(item) for item in VENDOR_EVENTS_MANIFEST.tools]

    def invoke(self, name: str, arguments: dict[str, Any], timeout: float) -> Any:
        del name, arguments, timeout
        raise PluginValidationError("vendor events require trusted household context")

    def invoke_with_invocation_context(
        self,
        name: str,
        arguments: dict[str, Any],
        timeout: float,
        context: InvocationContext,
    ) -> dict[str, Any]:
        del timeout
        if name != "list_recent_events" or arguments.keys() - {"limit", "cursor"}:
            raise PluginValidationError("unsupported vendor-event read")
        limit = arguments.get("limit", 20)
        if type(limit) is not int or not 1 <= limit <= _MAX_RESULTS:
            raise VendorEventReadError("limit must be between 1 and 50")
        cursor = arguments.get("cursor")
        before: int | None = None
        if cursor is not None:
            if not isinstance(cursor, str) or not cursor.isascii() or not cursor.isdigit():
                raise VendorEventReadError("invalid cursor")
            before = int(cursor)
        return self.store.list_recent(context.household_id, limit=limit, before_position=before)


VENDOR_EVENTS_MANIFEST = PluginManifest(
    plugin_id="anima.vendor-events",
    plugin_version="1.0.0",
    manifest_version=MANIFEST_VERSION,
    requires_core=CORE_VERSION,
    name="Passive vendor events",
    description="Read bounded sanitized Tapo lock and Wansview motion reports",
    runtime_kind=RuntimeKind.TRUSTED_NATIVE,
    trust_class=TrustClass.TRUSTED_NATIVE,
    capabilities=("household.vendor-events",),
    source="builtin:anima_ha.vendor_events",
    tools=(
        {
            "name": "list_recent_events",
            "description": "Read recent canonical lock and camera-motion reports",
            "input_schema": {
                "type": "object",
                "properties": {
                    "limit": {"type": "integer", "minimum": 1, "maximum": _MAX_RESULTS},
                    "cursor": {"type": "string", "pattern": "^[1-9][0-9]*$", "maxLength": 20},
                },
                "additionalProperties": False,
            },
            "output_schema": {
                "type": "object",
                "required": ["schema_version", "items", "external_content_trust"],
                "properties": {
                    "schema_version": {"type": "integer", "const": 1},
                    "items": {"type": "array", "maxItems": _MAX_RESULTS},
                    "next_cursor": {"type": ["string", "null"]},
                    "external_content_trust": {"type": "string"},
                    "identity_warning": {"type": "string"},
                    "as_of": {"type": "string"},
                },
                "additionalProperties": False,
            },
            "semantic_action": "capabilities.read",
            "risk_class": "READ_ONLY",
            "read_only": True,
            "idempotency": Idempotency.IDEMPOTENT.value,
            "external_content_trust": ExternalContentTrust.EXTERNAL_UNTRUSTED.value,
        },
    ),
)
