"""Bounded local ANIMA interface API.

The browser speaks only to this module.  It receives semantic view models and
submits commands to injected Core gateways; it never receives provider tokens,
database rows, policy internals, or raw event payloads.
"""

from __future__ import annotations

import asyncio
import base64
import hashlib
import hmac
import json
import logging
import os
import secrets
import time
from collections import deque
from collections.abc import Awaitable, Callable, Iterator, Mapping
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from threading import Lock
from typing import Any, Protocol
from uuid import UUID, uuid4

import psycopg
from aiohttp import ClientError, ClientSession, ClientTimeout, WSMsgType
from fastapi import FastAPI, Header, HTTPException, Request, Response, status
from fastapi.responses import JSONResponse, RedirectResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from psycopg.rows import dict_row
from pydantic import BaseModel, Field
from starlette.types import Receive, Scope, Send

from anima_ha.events import DeliveryClass, EventEnvelope, EventImportance
from anima_ha.family_routines_api import install_family_routines_api
from anima_ha.ha_connection_setup import (
    HAConnectionStore,
    HASetupError,
    VerifiedHAOwner,
    commission_owner,
)
from anima_ha.household_learning_api import install_household_learning_api
from anima_ha.household_presence_api import install_household_presence_api
from anima_ha.knowledge_api import install_knowledge_api
from anima_ha.live_results import PostgresSentryLiveResultBus
from anima_ha.policy import Assurance, EvidenceType, IdentityEvidence, RequestOrigin
from anima_ha.preferences import PreferenceValidationError, preference_payloads, preferences_page
from anima_ha.ring_api import install_ring_api
from anima_ha.sentry_voice_settings import SentryVoiceSettingsStore, validate_voice_settings
from anima_ha.users import user_payload
from anima_ha.vendor_event_ingress import (
    ExactVendorAttention,
    VendorEventIngress,
    VendorIngressError,
    VendorRelayConfig,
    install_vendor_event_api,
)

UI_VERSION = "0.1.0"
UI_SESSION_COOKIE = "anima_session"
UI_OAUTH_NONCE_COOKIE = "anima_oauth_nonce"
SESSION_ABSOLUTE_TTL = timedelta(hours=8)
SESSION_IDLE_TTL = timedelta(minutes=30)
MAX_CONVERSATION_CHARS = 4_000
MAX_SSE_BUFFER = 64
UI_PAGE_SIZE = 50
UI_MAX_PAGE_SIZE = 100
OAUTH_STATE_TTL = timedelta(minutes=10)
DEFAULT_HOUSEHOLD_ID = UUID("00000000-0000-0000-0000-000000000012")
DEFAULT_PRINCIPAL_ID = UUID("00000000-0000-0000-0000-000000000013")


class UIAuthError(RuntimeError):
    """Raised when an ANIMA session cannot be established."""


class PrincipalMappingRequired(UIAuthError):
    """Raised when a Home Assistant user has no exact ANIMA mapping."""


class PrincipalMappingConflict(UIAuthError):
    """Raised when commissioned identity evidence maps to multiple targets."""


class UICommandError(RuntimeError):
    """Raised when a UI command cannot be routed through Core."""


def _now() -> datetime:
    return datetime.now(UTC)


def device_capability_projection(
    graph: Any,
    truth: Any,
    resource_id: UUID,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """One semantic primary for Home and inventory; never promote stale values.

    Provider references are used locally only to distinguish entity domains.
    Class evidence comes from explicit metadata or the latest resolved Truth
    observations, never names, model guesses, or an older observation lookup.
    """
    unknown: dict[str, Any] = {"truth_status": "UNKNOWN", "state": "UNKNOWN", "observed_at": None}
    contacts = {"door", "window", "opening"}
    diagnostic_binary = {"battery", "battery_charging", "connectivity", "problem", "update"}
    primary_sensors = {
        "temperature",
        "humidity",
        "illuminance",
        "pressure",
        "atmospheric_pressure",
        "carbon_dioxide",
        "carbon_monoxide",
        "pm1",
        "pm10",
        "pm25",
        "moisture",
    }
    descriptors: list[dict[str, Any]] = []
    candidates: list[tuple[int, dict[str, Any]]] = []
    for capability in graph.resource_capabilities(resource_id):
        metadata = capability.metadata
        capability_type = str(metadata.get("capability_type", ""))
        if not capability_type:
            continue
        entity = metadata.get("provider_entity_id", "")
        domain = metadata.get("provider_domain")
        if not isinstance(domain, str) and isinstance(entity, str) and "." in entity:
            domain = entity.split(".", 1)[0]
        readings = (
            [
                resolution
                for binding, resolution in graph.truth_for_node(capability.canonical_id, truth)
                if binding.semantic_attribute in {"power.state", "state"}
            ]
            if truth is not None
            else []
        )
        resolution = readings[0] if len(readings) == 1 else None
        classes = []
        explicit_class = metadata.get("provider_device_class")
        if explicit_class is not None:
            classes.append(explicit_class)
        if resolution is not None:
            for observation in getattr(resolution, "observations", ()):
                if observation.observed_at != resolution.last_observed_at:
                    continue
                attributes = observation.metadata.get("attributes", {})
                if isinstance(attributes, dict) and attributes.get("device_class") is not None:
                    classes.append(attributes["device_class"])
        qualified_classes = {
            value
            for value in classes
            if isinstance(value, str)
            and 1 <= len(value) <= 48
            and all(c in "abcdefghijklmnopqrstuvwxyz_0123456789" for c in value)
        }
        device_class = next(iter(qualified_classes)) if len(qualified_classes) == 1 else None
        snapshot = dict(unknown)
        if device_class is not None:
            snapshot["provider_device_class"] = device_class
        if resolution is not None:
            status = getattr(resolution.status, "value", str(resolution.status))
            state = "UNKNOWN"
            if status == "CURRENT/KNOWN":
                value = resolution.value
                normalized = str(value).casefold()
                on = value is True or normalized in {"on", "true"}
                off = value is False or normalized in {"off", "false"}
                contact = domain == "binary_sensor" and device_class in contacts
                if contact and (on or normalized == "open"):
                    state = "OPEN"
                elif contact and (off or normalized == "closed"):
                    state = "CLOSED"
                elif on or off:
                    state = "ON" if on else "OFF"
                elif (
                    domain != "binary_sensor"
                    and capability_type != "power.set"
                    and normalized not in {"open", "closed"}
                    and isinstance(value, (str, int, float))
                    and not isinstance(value, bool)
                ):
                    state = str(value)[:80]
            elif status in {"STALE", "UNKNOWN", "UNAVAILABLE", "CONFLICTING"}:
                state = status
            if status == "STALE" and domain == "binary_sensor" and device_class in contacts:
                normalized = str(resolution.value).casefold()
                last_state = (
                    "OPEN"
                    if normalized in {"on", "true", "open"}
                    else "CLOSED"
                    if normalized in {"off", "false", "closed"}
                    else None
                )
                reported_at = [
                    observation.observed_at
                    for observation in getattr(resolution, "observations", ())
                    if getattr(observation, "state", None) == "KNOWN"
                    and getattr(observation, "evidence_kind", None) == "DIRECT"
                    and observation.value == resolution.value
                    and isinstance(observation.observed_at, datetime)
                ]
                if last_state is not None and reported_at:
                    # Separate historical provenance, never current state or
                    # the timestamp of a newer unknown/other-source observation.
                    snapshot["last_reported_state"] = last_state
                    snapshot["last_reported_at"] = max(reported_at).isoformat()
                    snapshot["last_reported_source"] = "ANIMA_TRUTH"
            snapshot.update(
                truth_status=status,
                state=state,
                observed_at=(
                    resolution.last_observed_at.isoformat()
                    if resolution.last_observed_at is not None
                    else None
                ),
            )
        readable = bool(metadata.get("readable", True))
        descriptors.append(
            {
                "type": capability_type,
                "label": capability.name,
                "readable": readable,
                "writable": bool(metadata.get("writable", False)),
                **snapshot,
            }
        )
        rank = None
        if readable and capability_type == "power.set":
            rank = 0
        elif readable and capability_type == "state.read":
            if domain == "binary_sensor" and device_class in contacts:
                rank = 1
            elif domain == "binary_sensor" and device_class not in diagnostic_binary:
                rank = 2
            elif domain == "sensor" and device_class in primary_sensors:
                rank = 3
        if rank is not None:
            candidates.append((rank, snapshot))
    primary = []
    if candidates:
        best = min(rank for rank, _ in candidates)
        primary = [snapshot for rank, snapshot in candidates if rank == best]
    # Multiple equally eligible primaries are ambiguous, not first-row wins.
    selected = dict(primary[0] if len(primary) == 1 else unknown)
    resource = graph.get_node(resource_id)
    if resource is not None and isinstance(resource.name, str) and resource.name.strip():
        # Display authority is the canonical graph name, not provider name_by_user.
        selected["canonical_name"] = resource.name
    return descriptors, selected


def _hash(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _session_csrf(secret_hash: str) -> str:
    # Stable across tabs/reloads, distinct per authenticated session. No raw
    # session cookie is exposed and Origin validation remains mandatory.
    return hmac.new(secret_hash.encode(), b"anima-ui-csrf-v1", hashlib.sha256).hexdigest()


def _configured_ttl(source: Mapping[str, str], name: str, default: timedelta) -> timedelta:
    raw = source.get(name)
    if raw is None or not raw.strip():
        return default
    try:
        seconds = int(raw)
    except ValueError as exc:
        raise ValueError(f"{name} must be an integer number of seconds") from exc
    if seconds < 60:
        raise ValueError(f"{name} must be at least 60 seconds")
    return timedelta(seconds=seconds)


@dataclass(frozen=True, slots=True)
class UIConfig:
    """Non-secret UI configuration."""

    environment: str = "development"
    bind_host: str = "127.0.0.1"
    bind_port: int = 8090
    static_dir: Path = Path("ui/dist")
    ha_base_url: str | None = None
    ha_browser_url: str | None = None
    ha_client_id: str | None = None
    ha_redirect_uri: str | None = None
    opa_url: str = "http://127.0.0.1:8181"
    test_auth_enabled: bool = False
    session_absolute_ttl: timedelta = SESSION_ABSOLUTE_TTL
    session_idle_ttl: timedelta = SESSION_IDLE_TTL

    @classmethod
    def from_environment(cls, values: dict[str, str] | None = None) -> UIConfig:
        source = os.environ if values is None else values
        try:
            port = int(source.get("ANIMA_UI_PORT", "8090"))
        except ValueError as exc:
            raise ValueError("ANIMA_UI_PORT must be an integer") from exc
        if not 1 <= port <= 65_535:
            raise ValueError("ANIMA_UI_PORT must be between 1 and 65535")
        absolute_ttl = _configured_ttl(
            source, "ANIMA_UI_SESSION_ABSOLUTE_SECONDS", SESSION_ABSOLUTE_TTL
        )
        idle_ttl = _configured_ttl(source, "ANIMA_UI_SESSION_IDLE_SECONDS", SESSION_IDLE_TTL)
        if idle_ttl > absolute_ttl:
            raise ValueError("ANIMA_UI_SESSION_IDLE_SECONDS cannot exceed the absolute session TTL")
        return cls(
            environment=source.get("ANIMA_ENV", "development"),
            bind_host=source.get("ANIMA_UI_BIND", "127.0.0.1"),
            bind_port=port,
            static_dir=Path(source.get("ANIMA_UI_STATIC_DIR", "ui/dist")),
            ha_base_url=source.get("ANIMA_HA_BASE_URL") or None,
            ha_browser_url=source.get("ANIMA_HA_BROWSER_URL") or None,
            ha_client_id=source.get("ANIMA_HA_OAUTH_CLIENT_ID") or None,
            ha_redirect_uri=source.get("ANIMA_HA_OAUTH_REDIRECT_URI") or None,
            opa_url=source.get("ANIMA_OPA_URL", "http://127.0.0.1:8181").rstrip("/"),
            test_auth_enabled=source.get("ANIMA_UI_TEST_AUTH", "0") == "1",
            session_absolute_ttl=absolute_ttl,
            session_idle_ttl=idle_ttl,
        )


def _set_ui_session_cookie(response: Response, cookie: str, config: UIConfig) -> None:
    """Persist the opaque credential for the bounded server-side session lifetime."""

    response.set_cookie(
        UI_SESSION_COOKIE,
        cookie,
        httponly=True,
        samesite="strict",
        secure=False,
        max_age=max(1, int(config.session_absolute_ttl.total_seconds())),
        path="/",
    )


@dataclass(frozen=True, slots=True)
class SessionRecord:
    session_id: UUID
    secret_hash: str
    household_id: UUID
    principal_id: UUID
    created_at: datetime
    last_seen_at: datetime
    expires_at: datetime
    csrf_hash: str
    device_label: str | None = None
    revoked_at: datetime | None = None


class SessionStore(Protocol):
    def create(self, record: SessionRecord) -> None: ...

    def get(self, session_id: UUID) -> SessionRecord | None: ...

    def save(self, record: SessionRecord) -> None: ...

    def revoke(self, session_id: UUID, at: datetime) -> None: ...


class InMemorySessionStore:
    def __init__(self) -> None:
        self.records: dict[UUID, SessionRecord] = {}

    def create(self, record: SessionRecord) -> None:
        self.records[record.session_id] = record

    def get(self, session_id: UUID) -> SessionRecord | None:
        return self.records.get(session_id)

    def save(self, record: SessionRecord) -> None:
        self.records[record.session_id] = record

    def revoke(self, session_id: UUID, at: datetime) -> None:
        existing = self.records.get(session_id)
        if existing:
            self.records[session_id] = SessionRecord(
                existing.session_id,
                existing.secret_hash,
                existing.household_id,
                existing.principal_id,
                existing.created_at,
                existing.last_seen_at,
                existing.expires_at,
                existing.csrf_hash,
                existing.device_label,
                at,
            )


class PostgresSessionStore:
    """Server-side session persistence; only digests are stored."""

    def __init__(self, database_url: str, connect_timeout: int = 5) -> None:
        self.database_url = database_url
        self.connect_timeout = connect_timeout

    def _connect(self) -> psycopg.Connection[Any]:
        return psycopg.connect(
            self.database_url, connect_timeout=self.connect_timeout, row_factory=dict_row
        )

    @staticmethod
    def _record(row: dict[str, Any]) -> SessionRecord:
        return SessionRecord(
            UUID(str(row["session_id"])),
            str(row["secret_hash"]),
            UUID(str(row["household_id"])),
            UUID(str(row["principal_id"])),
            row["created_at"],
            row["last_seen_at"],
            row["expires_at"],
            str(row["csrf_hash"]),
            str(row["device_label"]) if row["device_label"] else None,
            row["revoked_at"],
        )

    def create(self, record: SessionRecord) -> None:
        with self._connect() as connection, connection.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO anima_ui_sessions
                (session_id, secret_hash, household_id, principal_id, created_at,
                 last_seen_at, expires_at, device_label, csrf_hash)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)
                """,
                (
                    record.session_id,
                    record.secret_hash,
                    record.household_id,
                    record.principal_id,
                    record.created_at,
                    record.last_seen_at,
                    record.expires_at,
                    record.device_label,
                    record.csrf_hash,
                ),
            )
            connection.commit()

    def get(self, session_id: UUID) -> SessionRecord | None:
        with self._connect() as connection, connection.cursor() as cursor:
            cursor.execute("SELECT * FROM anima_ui_sessions WHERE session_id=%s", (session_id,))
            row = cursor.fetchone()
        return self._record(row) if row else None

    def save(self, record: SessionRecord) -> None:
        with self._connect() as connection, connection.cursor() as cursor:
            cursor.execute(
                "UPDATE anima_ui_sessions SET last_seen_at=%s, csrf_hash=%s WHERE session_id=%s",
                (record.last_seen_at, record.csrf_hash, record.session_id),
            )
            connection.commit()

    def revoke(self, session_id: UUID, at: datetime) -> None:
        with self._connect() as connection, connection.cursor() as cursor:
            cursor.execute(
                "UPDATE anima_ui_sessions SET revoked_at=%s WHERE session_id=%s", (at, session_id)
            )
            connection.commit()


@dataclass(frozen=True, slots=True)
class UIIdentity:
    household_id: UUID
    principal_id: UUID
    ha_user_id: str
    evidence: IdentityEvidence
    display_name: str = "Household member"

    def to_payload(self) -> dict[str, Any]:
        return {
            "display_name": self.display_name,
            "assurance": Assurance.AUTHENTICATED.value,
            "evidence": EvidenceType.AUTHENTICATED_SESSION.value,
        }


class CommissionedIdentityResolver(Protocol):
    """ANIMA-owned mapping boundary for authenticated provider identities."""

    def resolve_ha_user(self, ha_user_id: str) -> tuple[UUID, UUID]: ...

    def resolve_principal(self, principal_id: UUID) -> tuple[UUID, UUID, str | None]: ...

    def resolve_role(self, principal_id: UUID) -> str | None: ...

    def resolve_access_level(self, principal_id: UUID) -> str: ...


DEFAULT_UI_PREFERENCES: dict[str, Any] = {
    "version": 2,
    "appearance": "night",
    "accent": "purple",
    "density": "comfortable",
    "reduced_motion": False,
    "text_scale": "normal",
    "display_mode": "desktop",
    "visible_widgets": [
        "status",
        "presence",
        "weather",
        "agenda",
        "tasks",
        "controls",
        "conversation",
        "activity",
        "household",
        "reports",
        "health",
    ],
    "widget_order": [
        "status",
        "presence",
        "weather",
        "agenda",
        "tasks",
        "controls",
        "conversation",
        "activity",
        "household",
        "reports",
        "health",
    ],
}
UI_WIDGETS = frozenset(DEFAULT_UI_PREFERENCES["visible_widgets"])


def validate_ui_preferences(value: dict[str, Any]) -> dict[str, Any]:
    """Validate presentation-only settings; values cannot express authority."""
    if set(value) - set(DEFAULT_UI_PREFERENCES):
        raise ValueError("unknown UI preference")
    result = dict(DEFAULT_UI_PREFERENCES)
    result.update(value)
    stored_version = value.get("version", 1)
    if not isinstance(stored_version, int) or stored_version < 1:
        raise ValueError("version is not supported")
    if stored_version < 2:
        for key in ("visible_widgets", "widget_order"):
            result[key] = list(dict.fromkeys([*result[key], "household", "reports", "health"]))
    if result["appearance"] not in {"system", "light", "night"}:
        raise ValueError("appearance is not supported")
    if result["accent"] not in {"ember", "sage", "sky", "purple"}:
        raise ValueError("accent is not supported")
    if result["density"] not in {"comfortable", "compact"}:
        raise ValueError("density is not supported")
    if result["text_scale"] not in {"small", "normal", "large"}:
        raise ValueError("text_scale is not supported")
    if result["display_mode"] not in {"wall", "tablet", "phone", "desktop"}:
        raise ValueError("display_mode is not supported")
    if not isinstance(result["reduced_motion"], bool):
        raise ValueError("reduced_motion must be boolean")
    for key in ("visible_widgets", "widget_order"):
        items = result[key]
        if (
            not isinstance(items, list)
            or len(items) > len(UI_WIDGETS)
            or len(set(items)) != len(items)
            or not all(isinstance(item, str) and item in UI_WIDGETS for item in items)
        ):
            raise ValueError(f"{key} contains an unsupported widget")
    result["widget_order"] = [
        *result["widget_order"],
        *[
            item
            for item in DEFAULT_UI_PREFERENCES["widget_order"]
            if item not in result["widget_order"]
        ],
    ]
    result["version"] = 2
    return result


def _encode_page_cursor(sort_value: str, item_id: str) -> str:
    payload = json.dumps({"sort": sort_value, "id": item_id}, separators=(",", ":"))
    return base64.urlsafe_b64encode(payload.encode("utf-8")).decode("ascii").rstrip("=")


def _decode_page_cursor(value: str | None) -> tuple[str, str] | None:
    if value is None:
        return None
    if len(value) > 512:
        raise ValueError("cursor is too long")
    try:
        padded = value + "=" * (-len(value) % 4)
        payload = json.loads(base64.urlsafe_b64decode(padded).decode("utf-8"))
        sort_value, item_id = payload["sort"], payload["id"]
    except (KeyError, TypeError, ValueError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError("cursor is invalid") from exc
    if not isinstance(sort_value, str) or not isinstance(item_id, str):
        raise ValueError("cursor is invalid")
    return sort_value, item_id


def _page_limit(value: int) -> int:
    if not 1 <= value <= UI_MAX_PAGE_SIZE:
        raise ValueError("page size is out of bounds")
    return value


def _page(items: list[dict[str, Any]], cursor: str | None, limit: int) -> dict[str, Any]:
    bounded = _page_limit(limit)
    start = 0
    if cursor is not None:
        for index, item in enumerate(items):
            if item.get("_cursor") == cursor:
                start = index + 1
                break
        else:
            raise ValueError("cursor is invalid")
    selected = items[start : start + bounded]
    next_cursor = selected[-1].get("_cursor") if start + bounded < len(items) and selected else None
    return {
        "items": [
            {key: value for key, value in item.items() if key != "_cursor"} for item in selected
        ],
        "next_cursor": next_cursor,
    }


class HouseholdReadModel(Protocol):
    def bootstrap(self, identity: UIIdentity) -> dict[str, Any]: ...

    def home(self, identity: UIIdentity) -> dict[str, Any]: ...

    def tasks(self, identity: UIIdentity) -> list[dict[str, Any]]: ...

    def tasks_page(
        self, identity: UIIdentity, *, cursor: str | None = None, limit: int = UI_PAGE_SIZE
    ) -> dict[str, Any]: ...

    def calendar(self, identity: UIIdentity) -> list[dict[str, Any]]: ...

    def calendar_page(
        self, identity: UIIdentity, *, cursor: str | None = None, limit: int = UI_PAGE_SIZE
    ) -> dict[str, Any]: ...

    def activity(self, identity: UIIdentity) -> list[dict[str, Any]]: ...

    def capabilities(self, identity: UIIdentity) -> list[dict[str, Any]]: ...

    def integrations(self, identity: UIIdentity) -> list[dict[str, Any]]: ...

    def places(self, identity: UIIdentity) -> list[dict[str, Any]]: ...

    def alert_policies(self, identity: UIIdentity) -> list[dict[str, Any]]: ...

    def alert_events(
        self, identity: UIIdentity, *, cursor: str | None = None, limit: int = UI_PAGE_SIZE
    ) -> dict[str, Any]: ...

    def notification_routes(self, identity: UIIdentity) -> list[dict[str, Any]]: ...

    def backups(self, identity: UIIdentity) -> list[dict[str, Any]]: ...

    def scenes(self, identity: UIIdentity) -> list[dict[str, Any]]: ...

    def automations(self, identity: UIIdentity) -> list[dict[str, Any]]: ...

    def settings(self, identity: UIIdentity) -> dict[str, Any]: ...

    def update_settings(self, identity: UIIdentity, value: dict[str, Any]) -> dict[str, Any]: ...

    def preferences(self, identity: UIIdentity) -> list[dict[str, Any]]: ...

    def users(self, identity: UIIdentity) -> list[dict[str, Any]]: ...

    def sentry_voice_settings(self, identity: UIIdentity) -> dict[str, Any]: ...

    def update_sentry_voice_settings(
        self, identity: UIIdentity, value: dict[str, Any]
    ) -> dict[str, Any]: ...


def _health_view(
    capabilities: list[dict[str, Any]], *, core_available: bool = True
) -> dict[str, Any]:
    unavailable = [
        str(item["label"]) for item in capabilities if item.get("state") == "unavailable"
    ]
    degraded = [str(item["label"]) for item in capabilities if item.get("state") == "degraded"]
    if not core_available:
        status = "UNAVAILABLE"
        summary = "ANIMA Core is unavailable; household state was not substituted."
    elif unavailable or degraded:
        status = "DEGRADED"
        summary = "Core is connected, but some capabilities are unavailable or degraded."
    else:
        status = "CURRENT"
        summary = "Core and commissioned capabilities are available."
    return {
        "status": status,
        "summary": summary,
        "unavailable": unavailable,
        "degraded": degraded,
    }


class UICommandGateway(Protocol):
    def task_mutation(
        self, identity: UIIdentity, operation: str, payload: dict[str, Any]
    ) -> dict[str, Any]: ...

    def calendar_mutation(
        self, identity: UIIdentity, operation: str, payload: dict[str, Any]
    ) -> dict[str, Any]: ...

    def device_inventory(self, identity: UIIdentity) -> dict[str, Any]: ...

    def device_mutation(
        self, identity: UIIdentity, operation: str, payload: dict[str, Any]
    ) -> dict[str, Any]: ...

    def control(
        self, identity: UIIdentity, control_id: str, payload: dict[str, Any]
    ) -> dict[str, Any]: ...

    def confirmation(
        self, identity: UIIdentity, approval_id: str, decision: str
    ) -> dict[str, Any]: ...

    def alert_policy_mutation(
        self, identity: UIIdentity, operation: str, payload: dict[str, Any]
    ) -> dict[str, Any]: ...

    def notification_route_mutation(
        self, identity: UIIdentity, operation: str, payload: dict[str, Any]
    ) -> dict[str, Any]: ...

    def integration_mutation(
        self, identity: UIIdentity, operation: str, payload: dict[str, Any]
    ) -> dict[str, Any]: ...

    def space_mutation(
        self, identity: UIIdentity, operation: str, payload: dict[str, Any]
    ) -> dict[str, Any]: ...

    def backup_mutation(
        self, identity: UIIdentity, operation: str, payload: dict[str, Any]
    ) -> dict[str, Any]: ...

    def scene_mutation(
        self, identity: UIIdentity, operation: str, payload: dict[str, Any]
    ) -> dict[str, Any]: ...

    def apply_scene(self, identity: UIIdentity, scene_id: str) -> dict[str, Any]: ...

    def automation_mutation(
        self, identity: UIIdentity, operation: str, payload: dict[str, Any]
    ) -> dict[str, Any]: ...

    def preference_mutation(
        self, identity: UIIdentity, operation: str, payload: dict[str, Any]
    ) -> dict[str, Any]: ...

    def user_mutation(
        self, identity: UIIdentity, operation: str, payload: dict[str, Any]
    ) -> dict[str, Any]: ...


class UnavailableCommandGateway:
    """Fail closed until the host wires the existing Core gateway adapters."""

    @staticmethod
    def _unavailable(operation: str) -> dict[str, Any]:
        return {
            "status": "unavailable",
            "operation": operation,
            "reason": "CORE_COMMAND_GATEWAY_NOT_CONFIGURED",
        }

    def task_mutation(
        self, identity: UIIdentity, operation: str, payload: dict[str, Any]
    ) -> dict[str, Any]:
        return self._unavailable(f"task.{operation}")

    def calendar_mutation(
        self, identity: UIIdentity, operation: str, payload: dict[str, Any]
    ) -> dict[str, Any]:
        return self._unavailable(f"calendar.{operation}")

    def device_inventory(self, identity: UIIdentity) -> dict[str, Any]:
        return {"status": "UNAVAILABLE", "items": [], "reason": "CORE_NOT_CONFIGURED"}

    def device_mutation(
        self, identity: UIIdentity, operation: str, payload: dict[str, Any]
    ) -> dict[str, Any]:
        return self._unavailable(f"device.{operation}")

    def control(
        self, identity: UIIdentity, control_id: str, payload: dict[str, Any]
    ) -> dict[str, Any]:
        return self._unavailable(f"control.{control_id}")

    def confirmation(self, identity: UIIdentity, approval_id: str, decision: str) -> dict[str, Any]:
        return self._unavailable(f"confirmation.{approval_id}")

    def alert_policy_mutation(
        self, identity: UIIdentity, operation: str, payload: dict[str, Any]
    ) -> dict[str, Any]:
        return self._unavailable(f"alert_policy.{operation}")

    def notification_route_mutation(
        self, identity: UIIdentity, operation: str, payload: dict[str, Any]
    ) -> dict[str, Any]:
        return self._unavailable(f"notification_route.{operation}")

    def integration_mutation(
        self, identity: UIIdentity, operation: str, payload: dict[str, Any]
    ) -> dict[str, Any]:
        return self._unavailable(f"integration.{operation}")

    def space_mutation(
        self, identity: UIIdentity, operation: str, payload: dict[str, Any]
    ) -> dict[str, Any]:
        return self._unavailable(f"space.{operation}")

    def backup_mutation(
        self, identity: UIIdentity, operation: str, payload: dict[str, Any]
    ) -> dict[str, Any]:
        return self._unavailable(f"backup.{operation}")

    def scene_mutation(
        self, identity: UIIdentity, operation: str, payload: dict[str, Any]
    ) -> dict[str, Any]:
        return self._unavailable(f"scene.{operation}")

    def apply_scene(self, identity: UIIdentity, scene_id: str) -> dict[str, Any]:
        return self._unavailable(f"scene.apply.{scene_id}")

    def automation_mutation(
        self, identity: UIIdentity, operation: str, payload: dict[str, Any]
    ) -> dict[str, Any]:
        return self._unavailable(f"automation.{operation}")

    def preference_mutation(
        self, identity: UIIdentity, operation: str, payload: dict[str, Any]
    ) -> dict[str, Any]:
        return self._unavailable(f"preference.{operation}")

    def user_mutation(
        self, identity: UIIdentity, operation: str, payload: dict[str, Any]
    ) -> dict[str, Any]:
        return self._unavailable(f"user.{operation}")


class ConversationIngress(Protocol):
    def submit(self, identity: UIIdentity, text: str) -> dict[str, Any]: ...


class ConversationPipeline(Protocol):
    def run(self, identity: UIIdentity, event: EventEnvelope) -> dict[str, Any]: ...


class UIEventCapacityError(RuntimeError):
    """This session already holds its bounded live-update connections."""


class UIEventBroadcaster:
    """Bounded invalidation-only event fanout."""

    def __init__(self) -> None:
        self._subscribers: dict[int, tuple[UUID | None, deque[str]]] = {}
        self._lock = Lock()

    def publish(self, name: str) -> None:
        if name not in {
            "home.invalidated",
            "tasks.changed",
            "calendar.changed",
            "alerts.changed",
            "activity.changed",
            "conversation.completed",
            "capabilities.changed",
            "preferences.changed",
            "household.changed",
        }:
            raise ValueError("unsafe UI event")
        with self._lock:
            for _, queue in self._subscribers.values():
                if len(queue) >= MAX_SSE_BUFFER:
                    queue.clear()
                    queue.append("refresh.required")
                else:
                    queue.append(name)

    def subscribe(self, session_id: UUID | None = None) -> deque[str]:
        queue: deque[str] = deque(maxlen=MAX_SSE_BUFFER)
        with self._lock:
            # HTTP/1 browsers share six connections per origin across tabs.
            # Leave capacity for authenticated reads/mutations and new tabs.
            if (
                session_id is not None
                and sum(owner == session_id for owner, _ in self._subscribers.values()) >= 2
            ):
                raise UIEventCapacityError("LIVE_UPDATE_CONNECTION_LIMIT")
            self._subscribers[id(queue)] = (session_id, queue)
        return queue

    def unsubscribe(self, queue: deque[str]) -> None:
        with self._lock:
            # Empty deques compare equal; removal must use identity.
            self._subscribers.pop(id(queue), None)

    def drain(self, queue: deque[str]) -> list[str]:
        with self._lock:
            names = list(queue)
            queue.clear()
            return names


class _UIEventStreamingResponse(StreamingResponse):
    """Release the reserved slot even when headers fail before iteration."""

    def __init__(
        self,
        stream: Iterator[str],
        broadcaster: UIEventBroadcaster,
        queue: deque[str],
    ) -> None:
        super().__init__(
            stream,
            media_type="text/event-stream",
            headers={"Cache-Control": "no-store", "X-Accel-Buffering": "no"},
        )
        self._broadcaster = broadcaster
        self._queue = queue

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        try:
            await super().__call__(scope, receive, send)
        finally:
            # No await: cancellation cannot interrupt identity-based release.
            # Generator-finally cleanup remains safe to run a second time.
            self._broadcaster.unsubscribe(self._queue)


class DemoHouseholdReadModel:
    """Safe deterministic fallback used by the local prototype and tests."""

    def __init__(self) -> None:
        self._settings = validate_ui_preferences({})
        self._tasks = [
            {"task_id": "task-demo", "title": "Review Anima updates", "status": "ACTIVE"}
        ]
        self._calendar = [
            {
                "event_id": "event-demo",
                "title": "Household planning",
                "start_at": "2026-09-02T18:00:00+00:00",
                "end_at": "2026-09-02T18:30:00+00:00",
                "status": "ACTIVE",
                "version": 1,
            }
        ]

    def bootstrap(self, identity: UIIdentity) -> dict[str, Any]:
        settings = self.settings(identity)
        return {
            "identity": identity.to_payload(),
            "household": {"name": "Anima Home", "mode": "prototype"},
            "theme": {
                key: settings[key]
                for key in ("appearance", "accent", "density", "reduced_motion", "text_scale")
            },
            "layout": {
                key: settings[key] for key in ("display_mode", "visible_widgets", "widget_order")
            },
            "capabilities": [
                "home.status",
                "weather.current",
                "tasks",
                "calendar.local",
                "conversation",
                "activity",
            ],
            "server_version": UI_VERSION,
            "ui_version": UI_VERSION,
        }

    def home(self, identity: UIIdentity) -> dict[str, Any]:
        capabilities = self.capabilities(identity)
        return {
            "household": {
                "name": "Anima Home",
                "status": "CURRENT",
                "summary": "Your home is steady.",
            },
            "security": {"status": "UNKNOWN", "label": "Security status unavailable"},
            "presence": {
                "status": "CURRENT",
                "people": [{"name": "Household member", "state": "home"}],
            },
            "attention": [],
            "weather": {"status": "UNAVAILABLE", "summary": "Weather provider not connected"},
            "calendar": self.calendar(identity)[:20],
            "tasks": self.tasks(identity)[:20],
            "controls": [],
            "activity": self.activity(identity)[:8],
            "voice": {"status": "UNAVAILABLE", "label": "Voice is planned for a later phase"},
            "rooms": [
                {
                    "place_id": "room-demo",
                    "name": "Living room",
                    "kind": "ROOM",
                    "devices": [
                        {
                            "device_id": "device-demo",
                            "name": "Demo lamp",
                            "kind": "RESOURCE",
                            "state": "UNKNOWN",
                        }
                    ],
                }
            ],
            "notifications": [
                {
                    "notification_id": "notification-demo",
                    "summary": "Anima interface ready",
                    "status": "CURRENT",
                    "occurred_at": _now().isoformat(),
                }
            ],
            "reports": [
                {
                    "report_id": "report-demo",
                    "summary": "No completed household reports yet.",
                    "status": "UNKNOWN",
                }
            ],
            "recent_actions": [],
            "pending_approvals": [],
            "health": _health_view(capabilities),
        }

    def tasks(self, identity: UIIdentity) -> list[dict[str, Any]]:
        return [dict(item) for item in self._tasks]

    def tasks_page(
        self, identity: UIIdentity, *, cursor: str | None = None, limit: int = UI_PAGE_SIZE
    ) -> dict[str, Any]:
        del identity
        items = [
            {**dict(item), "_cursor": _encode_page_cursor(str(index), str(item["task_id"]))}
            for index, item in enumerate(self._tasks)
        ]
        return _page(items, cursor, limit)

    def calendar(self, identity: UIIdentity) -> list[dict[str, Any]]:
        return [dict(item) for item in self._calendar]

    def calendar_page(
        self, identity: UIIdentity, *, cursor: str | None = None, limit: int = UI_PAGE_SIZE
    ) -> dict[str, Any]:
        del identity
        items = [
            {**dict(item), "_cursor": _encode_page_cursor(str(index), str(item["event_id"]))}
            for index, item in enumerate(self._calendar)
        ]
        return _page(items, cursor, limit)

    def activity(self, identity: UIIdentity) -> list[dict[str, Any]]:
        return [
            {
                "kind": "system",
                "summary": "Anima interface ready",
                "status": "CURRENT",
                "occurred_at": _now().isoformat(),
            }
        ]

    def capabilities(self, identity: UIIdentity) -> list[dict[str, Any]]:
        return [
            {"id": "home.status", "label": "Home status", "state": "available"},
            {"id": "weather.current", "label": "Current weather", "state": "unavailable"},
            {"id": "calendar.local", "label": "Local calendar", "state": "available"},
            {
                "id": "voice",
                "label": "Voice software path",
                "state": "unavailable",
                "detail": "Phase 13",
            },
        ]

    def integrations(self, identity: UIIdentity) -> list[dict[str, Any]]:
        del identity
        return []

    def places(self, identity: UIIdentity) -> list[dict[str, Any]]:
        del identity
        return [
            {
                "place_id": "household-demo",
                "name": "Anima Home",
                "kind": "HOUSEHOLD",
                "parent_id": None,
            },
            {
                "place_id": "room-demo",
                "name": "Living room",
                "kind": "ROOM",
                "parent_id": "household-demo",
            },
        ]

    def alert_policies(self, identity: UIIdentity) -> list[dict[str, Any]]:
        del identity
        return []

    def alert_events(
        self, identity: UIIdentity, *, cursor: str | None = None, limit: int = UI_PAGE_SIZE
    ) -> dict[str, Any]:
        del identity, cursor
        _page_limit(limit)
        return {"items": [], "next_cursor": None}

    def notification_routes(self, identity: UIIdentity) -> list[dict[str, Any]]:
        del identity
        return []

    def backups(self, identity: UIIdentity) -> list[dict[str, Any]]:
        del identity
        return []

    def scenes(self, identity: UIIdentity) -> list[dict[str, Any]]:
        del identity
        return []

    def automations(self, identity: UIIdentity) -> list[dict[str, Any]]:
        del identity
        return []

    def settings(self, identity: UIIdentity) -> dict[str, Any]:
        del identity
        return dict(self._settings)

    def update_settings(self, identity: UIIdentity, value: dict[str, Any]) -> dict[str, Any]:
        del identity
        self._settings = validate_ui_preferences(value)
        return dict(self._settings)

    def preferences(self, identity: UIIdentity) -> list[dict[str, Any]]:
        del identity
        return []

    def users(self, identity: UIIdentity) -> list[dict[str, Any]]:
        del identity
        return []

    def sentry_voice_settings(self, identity: UIIdentity) -> dict[str, Any]:
        del identity
        return validate_voice_settings(None)

    def update_sentry_voice_settings(
        self, identity: UIIdentity, value: dict[str, Any]
    ) -> dict[str, Any]:
        del identity
        return validate_voice_settings(value)


class UnavailableHouseholdReadModel:
    """Explicit degraded view used when production Core dependencies are absent."""

    def bootstrap(self, identity: UIIdentity) -> dict[str, Any]:
        return {
            "identity": identity.to_payload(),
            "household": {"name": "Household", "mode": "unavailable"},
            "theme": {"appearance": "night", "accent": "ember", "density": "comfortable"},
            "layout": {"display_mode": "desktop", "visible_widgets": ["status"]},
            "capabilities": ["core.unavailable"],
            "server_version": UI_VERSION,
            "ui_version": UI_VERSION,
        }

    def home(self, identity: UIIdentity) -> dict[str, Any]:
        return {
            "household": {
                "name": "Household",
                "status": "UNKNOWN",
                "summary": "ANIMA Core is unavailable; no household state was substituted.",
            },
            "security": {"status": "UNKNOWN", "label": "Security status unavailable"},
            "presence": {"status": "UNKNOWN", "people": []},
            "attention": [],
            "weather": {"status": "UNAVAILABLE", "summary": "Weather provider unavailable"},
            "calendar": [],
            "tasks": [],
            "controls": [],
            "activity": [],
            "voice": {"status": "UNAVAILABLE", "label": "Voice is planned for a later phase"},
            "rooms": [],
            "notifications": [],
            "reports": [],
            "recent_actions": [],
            "pending_approvals": [],
            "health": _health_view(self.capabilities(identity), core_available=False),
        }

    def tasks(self, identity: UIIdentity) -> list[dict[str, Any]]:
        del identity
        return []

    def tasks_page(
        self, identity: UIIdentity, *, cursor: str | None = None, limit: int = UI_PAGE_SIZE
    ) -> dict[str, Any]:
        del identity, cursor
        _page_limit(limit)
        return {"items": [], "next_cursor": None}

    def calendar(self, identity: UIIdentity) -> list[dict[str, Any]]:
        del identity
        return []

    def calendar_page(
        self, identity: UIIdentity, *, cursor: str | None = None, limit: int = UI_PAGE_SIZE
    ) -> dict[str, Any]:
        del identity, cursor
        _page_limit(limit)
        return {"items": [], "next_cursor": None}

    def activity(self, identity: UIIdentity) -> list[dict[str, Any]]:
        del identity
        return []

    def capabilities(self, identity: UIIdentity) -> list[dict[str, Any]]:
        del identity
        return [
            {
                "id": "core.unavailable",
                "label": "ANIMA Core",
                "state": "unavailable",
                "detail": "ANIMA_DATABASE_URL is not configured",
            },
            {
                "id": "voice",
                "label": "Voice software path",
                "state": "unavailable",
                "detail": "Phase 13",
            },
        ]

    def integrations(self, identity: UIIdentity) -> list[dict[str, Any]]:
        del identity
        return []

    def places(self, identity: UIIdentity) -> list[dict[str, Any]]:
        del identity
        return []

    def alert_policies(self, identity: UIIdentity) -> list[dict[str, Any]]:
        del identity
        return []

    def alert_events(
        self, identity: UIIdentity, *, cursor: str | None = None, limit: int = UI_PAGE_SIZE
    ) -> dict[str, Any]:
        del identity, cursor
        _page_limit(limit)
        return {"items": [], "next_cursor": None}

    def notification_routes(self, identity: UIIdentity) -> list[dict[str, Any]]:
        del identity
        return []

    def backups(self, identity: UIIdentity) -> list[dict[str, Any]]:
        del identity
        return []

    def scenes(self, identity: UIIdentity) -> list[dict[str, Any]]:
        del identity
        return []

    def automations(self, identity: UIIdentity) -> list[dict[str, Any]]:
        del identity
        return []

    def settings(self, identity: UIIdentity) -> dict[str, Any]:
        del identity
        return validate_ui_preferences({})

    def update_settings(self, identity: UIIdentity, value: dict[str, Any]) -> dict[str, Any]:
        del identity, value
        raise UICommandError("CORE_PREFERENCES_UNAVAILABLE")

    def preferences(self, identity: UIIdentity) -> list[dict[str, Any]]:
        del identity
        return []

    def users(self, identity: UIIdentity) -> list[dict[str, Any]]:
        del identity
        return []

    def sentry_voice_settings(self, identity: UIIdentity) -> dict[str, Any]:
        del identity
        return validate_voice_settings(None)

    def update_sentry_voice_settings(
        self, identity: UIIdentity, value: dict[str, Any]
    ) -> dict[str, Any]:
        del identity, value
        raise UICommandError("CORE_PREFERENCES_UNAVAILABLE")


class PostgresHouseholdReadModel:
    """Normalized read façade over existing Core persistence tables."""

    def __init__(
        self,
        database_url: str,
        connect_timeout: int = 5,
        *,
        graph: Any | None = None,
        truth: Any | None = None,
        plugins: Any | None = None,
        alert_policy_store: Any | None = None,
        notification_route_store: Any | None = None,
        backup_coordinator: Any | None = None,
        scene_store: Any | None = None,
        automation_store: Any | None = None,
        memory_service: Any | None = None,
    ) -> None:
        self.database_url = database_url
        self.connect_timeout = connect_timeout
        self.graph = graph
        self.truth = truth
        self.plugins = plugins
        self.alert_policy_store = alert_policy_store
        self.notification_route_store = notification_route_store
        self.backup_coordinator = backup_coordinator
        self.scene_store = scene_store
        self.automation_store = automation_store
        self.memory_service = memory_service
        self.sentry_voice_settings_store = SentryVoiceSettingsStore(database_url)

    def _connect(self) -> psycopg.Connection[Any]:
        return psycopg.connect(
            self.database_url, connect_timeout=self.connect_timeout, row_factory=dict_row
        )

    def bootstrap(self, identity: UIIdentity) -> dict[str, Any]:
        household = self.graph.get_node(identity.household_id) if self.graph else None
        capabilities = self.capabilities(identity)
        settings = self.settings(identity)
        return {
            "identity": identity.to_payload(),
            "household": {
                "name": household.name if household else "Household",
                "mode": "commissioned" if household else "unavailable",
            },
            "theme": {
                key: settings[key]
                for key in ("appearance", "accent", "density", "reduced_motion", "text_scale")
            },
            "layout": {
                key: settings[key] for key in ("display_mode", "visible_widgets", "widget_order")
            },
            "capabilities": [str(item["id"]) for item in capabilities],
            "server_version": UI_VERSION,
            "ui_version": UI_VERSION,
        }

    def tasks(self, identity: UIIdentity) -> list[dict[str, Any]]:
        return list(self.tasks_page(identity, limit=UI_MAX_PAGE_SIZE)["items"])

    def tasks_page(
        self, identity: UIIdentity, *, cursor: str | None = None, limit: int = UI_PAGE_SIZE
    ) -> dict[str, Any]:
        bounded = _page_limit(limit)
        decoded = _decode_page_cursor(cursor)
        where = "household_id=%s"
        params: list[Any] = [identity.household_id]
        if decoded is not None:
            sort_value, item_id = decoded
            where += " AND (next_run_at, task_id) > (%s, %s)"
            params.extend([sort_value, item_id])
        with self._connect() as connection, connection.cursor() as db_cursor:
            db_cursor.execute(
                f"""
                SELECT task_id, title, status, next_run_at
                FROM anima_durable_tasks
                WHERE {where}
                ORDER BY next_run_at, task_id
                LIMIT %s
                """,
                (*params, bounded + 1),
            )
            rows = list(db_cursor.fetchall())
        has_more = len(rows) > bounded
        rows = rows[:bounded]
        items = [
            {
                "task_id": str(row["task_id"]),
                "title": str(row["title"]),
                "status": str(row["status"]),
                "next_run_at": row["next_run_at"].isoformat(),
            }
            for row in rows
        ]
        next_cursor = (
            _encode_page_cursor(rows[-1]["next_run_at"].isoformat(), str(rows[-1]["task_id"]))
            if has_more and rows
            else None
        )
        return {"items": items, "next_cursor": next_cursor}

    def calendar(self, identity: UIIdentity) -> list[dict[str, Any]]:
        return list(self.calendar_page(identity, limit=UI_MAX_PAGE_SIZE)["items"])

    def calendar_page(
        self, identity: UIIdentity, *, cursor: str | None = None, limit: int = UI_PAGE_SIZE
    ) -> dict[str, Any]:
        bounded = _page_limit(limit)
        decoded = _decode_page_cursor(cursor)
        where = "household_id=%s"
        params: list[Any] = [identity.household_id]
        if decoded is not None:
            sort_value, item_id = decoded
            where += " AND (start_at, event_id) > (%s, %s)"
            params.extend([sort_value, item_id])
        with self._connect() as connection, connection.cursor() as db_cursor:
            db_cursor.execute(
                f"""
                SELECT event_id, title, start_at, end_at, status, version
                FROM anima_calendar_events
                WHERE {where}
                ORDER BY start_at, event_id
                LIMIT %s
                """,
                (*params, bounded + 1),
            )
            rows = list(db_cursor.fetchall())
        has_more = len(rows) > bounded
        rows = rows[:bounded]
        items = [
            {
                "event_id": str(row["event_id"]),
                "title": str(row["title"]),
                "start_at": row["start_at"].isoformat(),
                "end_at": row["end_at"].isoformat(),
                "status": str(row["status"]),
                "version": int(row["version"]),
            }
            for row in rows
        ]
        next_cursor = (
            _encode_page_cursor(rows[-1]["start_at"].isoformat(), str(rows[-1]["event_id"]))
            if has_more and rows
            else None
        )
        return {"items": items, "next_cursor": next_cursor}

    def home(self, identity: UIIdentity) -> dict[str, Any]:
        from anima_ha.graph import NodeKind
        from anima_ha.truth import TruthStatus

        household = self.graph.get_node(identity.household_id) if self.graph else None
        members = self.graph.members_of_household(identity.household_id) if self.graph else []
        people: list[dict[str, Any]] = []
        for member in members:
            state = "unknown"
            if self.truth is not None and self.graph is not None:
                for binding, resolution in self.graph.truth_for_node(
                    member.canonical_id, self.truth
                ):
                    if binding.semantic_attribute != "presence.home":
                        continue
                    if resolution.status == TruthStatus.CURRENT_KNOWN:
                        state = "home" if resolution.value is True else "away"
                    break
            people.append({"name": member.name, "state": state})

        controls: list[dict[str, Any]] = []
        if self.graph is not None:
            for resource in self.graph.resources_in_place(identity.household_id):
                capabilities = self.graph.resource_capabilities(resource.canonical_id)
                power = next(
                    (
                        capability
                        for capability in capabilities
                        if str(capability.metadata.get("capability_type", "")).startswith("power.")
                    ),
                    None,
                )
                if power is not None and resource.kind == NodeKind.RESOURCE:
                    state = "UNKNOWN"
                    if self.truth is not None:
                        for binding, resolution in self.graph.truth_for_node(
                            resource.canonical_id, self.truth
                        ):
                            if not str(binding.semantic_attribute).startswith("power"):
                                continue
                            if resolution.status == TruthStatus.CURRENT_KNOWN:
                                value = resolution.value
                                state = (
                                    "ON"
                                    if value is True or str(value).lower() in {"on", "true"}
                                    else "OFF"
                                    if value is False or str(value).lower() in {"off", "false"}
                                    else "UNKNOWN"
                                )
                            break
                    controls.append(
                        {
                            "control_id": str(resource.canonical_id),
                            "label": resource.name,
                            "state": state,
                            "capability": power.metadata.get("capability_type"),
                        }
                    )

        capabilities = self.capabilities(identity)
        rooms: list[dict[str, Any]] = []
        if self.graph is not None and callable(getattr(self.graph, "places_in_household", None)):
            places = self.graph.places_in_household(identity.household_id)
            for place in places:
                if place.kind not in {NodeKind.ROOM, NodeKind.ZONE}:
                    continue
                devices = []
                for resource in self.graph.resources_in_place(place.canonical_id):
                    if resource.canonical_id in {
                        UUID(str(item["device_id"])) for room in rooms for item in room["devices"]
                    }:
                        continue
                    _, device_state = device_capability_projection(
                        self.graph,
                        self.truth,
                        resource.canonical_id,
                    )
                    devices.append(
                        {
                            "device_id": str(resource.canonical_id),
                            "name": resource.name,
                            "kind": resource.kind.value,
                            **device_state,
                        }
                    )
                rooms.append(
                    {
                        "place_id": str(place.canonical_id),
                        "name": place.name,
                        "kind": place.kind.value,
                        "devices": devices,
                    }
                )

        notifications = self._notifications(identity)
        reports = self._reports(identity)
        recent_actions, pending_approvals = self._actions(identity)

        presence_status = (
            "CURRENT" if any(item["state"] != "unknown" for item in people) else "UNKNOWN"
        )
        return {
            "household": {
                "name": household.name if household else "Household",
                "status": "CURRENT" if household else "UNKNOWN",
                "summary": (
                    "Commissioned household state is available."
                    if household
                    else "Household graph is unavailable."
                ),
            },
            "security": {"status": "UNKNOWN", "label": "Security status unavailable"},
            "presence": {
                "status": presence_status,
                "people": people,
            },
            "attention": [],
            "weather": self.weather(identity),
            "calendar": self.calendar(identity)[:20],
            "tasks": self.tasks(identity)[:20],
            "controls": controls,
            "activity": self.activity(identity)[:8],
            "voice": {"status": "UNAVAILABLE", "label": "Voice is planned for a later phase"},
            "rooms": rooms,
            "notifications": notifications,
            "reports": reports,
            "recent_actions": recent_actions,
            "pending_approvals": pending_approvals,
            "health": _health_view(capabilities, core_available=household is not None),
        }

    def _notifications(self, identity: UIIdentity) -> list[dict[str, Any]]:
        try:
            with self._connect() as connection, connection.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT event_type, occurred_at, importance
                    FROM anima_event_journal
                    WHERE metadata->>'household_id'=%s AND importance <> 'NORMAL'
                    ORDER BY journal_position DESC
                    LIMIT 12
                    """,
                    (str(identity.household_id),),
                )
                rows = cursor.fetchall()
        except psycopg.Error:
            return []
        return [
            {
                "notification_id": f"event:{row['event_type']}:{row['occurred_at'].isoformat()}",
                "summary": (
                    f"Household event recorded: {str(row['event_type']).replace('.', ' · ')}"
                ),
                "status": "CURRENT",
                "importance": str(row["importance"]),
                "occurred_at": row["occurred_at"].isoformat(),
            }
            for row in rows
        ]

    def _reports(self, identity: UIIdentity) -> list[dict[str, Any]]:
        try:
            with self._connect() as connection, connection.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT episode_id, status, final_disposition, completed_at
                    FROM anima_agent_episodes
                    WHERE household_id=%s
                    ORDER BY COALESCE(completed_at, started_at) DESC
                    LIMIT 12
                    """,
                    (identity.household_id,),
                )
                rows = cursor.fetchall()
        except psycopg.Error:
            return []
        return [
            {
                "report_id": str(row["episode_id"]),
                "summary": f"Anima episode {str(row['status']).replace('_', ' ').lower()}",
                "status": str(row["status"]),
                "disposition": str(row["final_disposition"] or "UNKNOWN"),
                "completed_at": row["completed_at"].isoformat() if row["completed_at"] else None,
            }
            for row in rows
        ]

    def _actions(self, identity: UIIdentity) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
        try:
            with self._connect() as connection, connection.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT action_id, tool_id, status, detail, updated_at
                    FROM anima_actions
                    WHERE household_id=%s
                    ORDER BY updated_at DESC
                    LIMIT 20
                    """,
                    (identity.household_id,),
                )
                rows = cursor.fetchall()
                cursor.execute(
                    """
                    UPDATE anima_pending_approvals SET status='EXPIRED'
                    WHERE household_id=%s AND principal_id=%s AND status='PENDING'
                      AND expires_at <= now()
                    """,
                    (identity.household_id, identity.principal_id),
                )
                cursor.execute(
                    """
                    SELECT approval_id, action_id, tool_id, summary, expires_at
                    FROM anima_pending_approvals
                    WHERE household_id=%s AND principal_id=%s AND status='PENDING'
                    ORDER BY expires_at, issued_at
                    """,
                    (identity.household_id, identity.principal_id),
                )
                approval_rows = cursor.fetchall()
                connection.commit()
        except psycopg.Error:
            return [], []
        actions = [
            {
                "action_id": str(row["action_id"]),
                "tool_id": str(row["tool_id"]),
                "status": str(row["status"]),
                "detail": str(row["detail"] or "No further detail recorded."),
                "updated_at": row["updated_at"].isoformat(),
            }
            for row in rows
        ]
        pending = [
            {
                "approval_id": str(item["approval_id"]),
                "action_id": str(item["action_id"]),
                "tool_id": str(item["tool_id"]),
                "status": "REQUIRE_CONFIRMATION",
                "summary": str(item["summary"]),
                "expires_at": item["expires_at"].isoformat(),
                "continuation": "AVAILABLE",
            }
            for item in approval_rows
        ]
        return actions, pending

    def activity(self, identity: UIIdentity) -> list[dict[str, Any]]:
        with self._connect() as connection, connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT event_type, occurred_at, importance
                FROM anima_event_journal
                WHERE metadata->>'household_id'=%s
                ORDER BY journal_position DESC
                LIMIT 20
                """,
                (str(identity.household_id),),
            )
            rows = cursor.fetchall()
        return [
            {
                "kind": "event",
                "summary": f"Anima recorded {row['event_type']}",
                "status": "CURRENT",
                "importance": str(row["importance"]),
                "occurred_at": row["occurred_at"].isoformat(),
            }
            for row in rows
        ]

    def capabilities(self, identity: UIIdentity) -> list[dict[str, Any]]:
        result = [{"id": "home.status", "label": "Home status", "state": "available"}]
        if self.plugins is not None:
            for plugin in self.plugins.list_plugins():
                state = "available" if plugin.enabled else "unavailable"
                detail = plugin.last_error
                plugin_id = str(getattr(plugin.manifest, "plugin_id", ""))
                provider_names = {
                    "anima.external.weather": ("open-meteo",),
                    "anima.external.discovery": ("searxng",),
                    "anima.external.shopping.upcitemdb": ("upcitemdb",),
                    "anima.external.recipes": ("themealdb",),
                    "anima.external.notifications": ("ntfy",),
                }
                for capability in plugin.manifest.capabilities:
                    capability_state = state
                    if plugin.enabled and plugin_id.startswith("anima.external"):
                        providers = provider_names.get(plugin_id, ())
                        if plugin_id == "anima.external.discovery":
                            providers = ("overpass",) if capability == "places" else ("searxng",)
                        health = self._latest_external_health(providers)
                        if health is not None:
                            capability_state, detail = health
                    entry: dict[str, Any] = {
                        "id": capability,
                        "label": plugin.manifest.name,
                        "state": capability_state,
                    }
                    if detail:
                        entry["detail"] = detail
                    result.append(entry)
        result.append(
            {
                "id": "conversation",
                "label": "Anima conversation",
                "state": "available" if self.plugins is not None else "unavailable",
            }
        )
        result.append(
            {
                "id": "voice",
                "label": "Voice software path",
                "state": "unavailable",
                "detail": "Phase 13",
            }
        )
        return result

    def integrations(self, identity: UIIdentity) -> list[dict[str, Any]]:
        del identity
        if self.plugins is None:
            return []
        from anima_ha.capability_management import integration_items

        return integration_items(self.plugins)

    def places(self, identity: UIIdentity) -> list[dict[str, Any]]:
        if self.graph is None:
            return []
        root = self.graph.get_node(identity.household_id)
        if root is None:
            return []
        places = [root, *self.graph.places_in_household(identity.household_id)]
        return [
            {
                "place_id": str(place.canonical_id),
                "name": place.name,
                "kind": place.kind.value,
                "parent_id": (
                    str(parent_id)
                    if (
                        parent_id := self.graph.parent_of_place(
                            identity.household_id, place.canonical_id
                        )
                    )
                    else None
                ),
            }
            for place in places
        ]

    def alert_policies(self, identity: UIIdentity) -> list[dict[str, Any]]:
        if self.alert_policy_store is None:
            return []
        return [
            policy.to_payload()
            for policy in self.alert_policy_store.list_all(identity.household_id)
        ]

    def alert_events(
        self, identity: UIIdentity, *, cursor: str | None = None, limit: int = UI_PAGE_SIZE
    ) -> dict[str, Any]:
        """Project matched SenseGuard events from the authoritative journal."""

        bounded = _page_limit(limit)
        decoded = _decode_page_cursor(cursor)
        clauses = [
            "metadata->>'household_id'=%s",
            "source='anima:senseguard-policy'",
        ]
        params: list[Any] = [str(identity.household_id)]
        if decoded is not None:
            occurred_at, event_id = decoded
            clauses.append("(occurred_at, event_id) < (%s, %s)")
            params.extend([occurred_at, event_id])
        with self._connect() as connection, connection.cursor() as cursor_db:
            cursor_db.execute(
                f"""
                SELECT event_id, occurred_at, payload, metadata
                FROM anima_event_journal
                WHERE {" AND ".join(clauses)}
                ORDER BY occurred_at DESC, event_id DESC
                LIMIT %s
                """,
                (*params, bounded + 1),
            )
            rows = list(cursor_db.fetchall())
            event_ids = [str(row["event_id"]) for row in rows]
            delivery_by_alert: dict[str, str] = {}
            if event_ids:
                cursor_db.execute(
                    """
                    SELECT payload->>'alert_event_id' AS alert_event_id,
                           payload->>'status' AS status
                    FROM anima_event_journal
                    WHERE event_type='notification.delivery'
                      AND metadata->>'household_id'=%s
                      AND payload->>'alert_event_id' = ANY(%s)
                    ORDER BY journal_position DESC
                    """,
                    (str(identity.household_id), event_ids),
                )
                for delivery in cursor_db.fetchall():
                    alert_id = str(delivery["alert_event_id"])
                    if alert_id not in delivery_by_alert:
                        delivery_by_alert[alert_id] = str(delivery["status"])
        selected = rows[:bounded]
        items: list[dict[str, Any]] = []
        for row in selected:
            payload = dict(row["payload"] or {})
            metadata = dict(row["metadata"] or {})
            resource_id = str(payload.get("canonical_resource_id", ""))
            resource_name = None
            if self.graph is not None and resource_id:
                try:
                    resource = self.graph.get_node(UUID(resource_id))
                except (ValueError, TypeError):
                    resource = None
                resource_name = resource.name if resource is not None else None
            items.append(
                {
                    "alert_id": str(row["event_id"]),
                    "source_event_id": payload.get("source_event_id"),
                    "resource_id": resource_id,
                    "resource_name": resource_name or "SenseGuard resource",
                    "event_type": str(payload.get("event_type", "senseguard.event")),
                    "occurred_at": row["occurred_at"].isoformat(),
                    "priority": int(metadata.get("priority", 0)),
                    "delivery_mode": str(metadata.get("delivery_mode", "SENTRY_COGNITION")),
                    "delivery_status": delivery_by_alert.get(str(row["event_id"]), "RECORDED"),
                }
            )
        has_more = len(rows) > bounded
        next_cursor = (
            _encode_page_cursor(
                selected[-1]["occurred_at"].isoformat(), str(selected[-1]["event_id"])
            )
            if has_more and selected
            else None
        )
        return {"items": items, "next_cursor": next_cursor}

    def notification_routes(self, identity: UIIdentity) -> list[dict[str, Any]]:
        if self.notification_route_store is None:
            return []
        return [
            route.to_payload()
            for route in self.notification_route_store.list_all(identity.household_id)
        ]

    def backups(self, identity: UIIdentity) -> list[dict[str, Any]]:
        if self.backup_coordinator is None:
            return []
        return [
            record.to_payload()
            for record in self.backup_coordinator.list_for_household(identity.household_id)
        ]

    def scenes(self, identity: UIIdentity) -> list[dict[str, Any]]:
        if self.scene_store is None:
            return []
        return [scene.to_payload() for scene in self.scene_store.list(identity.household_id)]

    def automations(self, identity: UIIdentity) -> list[dict[str, Any]]:
        if self.automation_store is None:
            return []
        return [
            automation.to_payload()
            for automation in self.automation_store.list(identity.household_id)
        ]

    def _latest_external_health(self, providers: tuple[str, ...]) -> tuple[str, str | None] | None:
        if not providers:
            return None
        with self._connect() as connection, connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT payload FROM anima_event_journal
                WHERE event_type='external.request.audit'
                  AND payload->>'provider' = ANY(%s)
                ORDER BY journal_position DESC LIMIT 1
                """,
                (list(providers),),
            )
            row = cursor.fetchone()
        if not row:
            return None
        payload = dict(row["payload"] or {})
        result_class = str(payload.get("result_class", ""))
        if result_class in {"SUCCESS", "RESPONSE_SUCCESS"}:
            return "available", None
        if result_class in {"HTTP_ERROR", "TIMEOUT", "TRANSPORT_ERROR", "PROVIDER_ERROR"}:
            return "degraded", result_class
        return None

    def weather(self, identity: UIIdentity) -> dict[str, Any]:
        del identity
        with self._connect() as connection, connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT sanitized_result, created_at FROM anima_agent_tool_requests
                WHERE tool_id='anima.external.weather.get' AND outcome='SUCCESS'
                ORDER BY created_at DESC LIMIT 1
                """
            )
            row = cursor.fetchone()
        if not row:
            return {"status": "UNKNOWN", "summary": "No retained weather observation yet."}
        result = dict(row["sanitized_result"] or {})
        payload = result.get("result") if isinstance(result.get("result"), dict) else result
        data = payload.get("data", {}) if isinstance(payload, dict) else {}
        current = data.get("current", {}) if isinstance(data, dict) else {}
        temperature = current.get("temperature_2m") if isinstance(current, dict) else None
        retrieved = payload.get("retrieved_at") if isinstance(payload, dict) else None
        if temperature is None:
            return {"status": "UNKNOWN", "summary": "Latest weather observation is incomplete."}
        age = _now() - row["created_at"]
        state = "CURRENT" if age <= timedelta(hours=6) else "STALE"
        suffix = f" · observed {retrieved}" if retrieved else ""
        return {"status": state, "summary": f"{temperature}° · Open-Meteo observation{suffix}"}

    def settings(self, identity: UIIdentity) -> dict[str, Any]:
        with self._connect() as connection, connection.cursor() as cursor:
            cursor.execute(
                "SELECT preferences FROM anima_ui_preferences "
                "WHERE household_id=%s AND principal_id=%s",
                (identity.household_id, identity.principal_id),
            )
            row = cursor.fetchone()
        return validate_ui_preferences(dict(row["preferences"]) if row else {})

    def update_settings(self, identity: UIIdentity, value: dict[str, Any]) -> dict[str, Any]:
        preferences = validate_ui_preferences(value)
        with self._connect() as connection, connection.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO anima_ui_preferences (household_id, principal_id, preferences)
                VALUES (%s,%s,%s::jsonb)
                ON CONFLICT (household_id, principal_id) DO UPDATE
                SET preferences=EXCLUDED.preferences, updated_at=now()
                """,
                (identity.household_id, identity.principal_id, json.dumps(preferences)),
            )
            connection.commit()
        return preferences

    def preferences(self, identity: UIIdentity) -> list[dict[str, Any]]:
        if self.memory_service is None:
            return []
        return preference_payloads(self.memory_service, identity.household_id)

    def users(self, identity: UIIdentity) -> list[dict[str, Any]]:
        if self.graph is None:
            return []
        return [
            user_payload(person)
            for person in self.graph.members_of_household(identity.household_id)
        ]

    def sentry_voice_settings(self, identity: UIIdentity) -> dict[str, Any]:
        return self.sentry_voice_settings_store.get(identity.household_id)

    def update_sentry_voice_settings(
        self, identity: UIIdentity, value: dict[str, Any]
    ) -> dict[str, Any]:
        return self.sentry_voice_settings_store.update(identity.household_id, value)


class DemoCommandGateway:
    def __init__(self, read_model: DemoHouseholdReadModel, events: UIEventBroadcaster) -> None:
        self.read_model = read_model
        self.events = events

    def task_mutation(
        self, identity: UIIdentity, operation: str, payload: dict[str, Any]
    ) -> dict[str, Any]:
        self.events.publish("tasks.changed")
        return {
            "status": "accepted",
            "operation": operation,
            "policy": "routed_through_core",
            "payload": payload,
        }

    def calendar_mutation(
        self, identity: UIIdentity, operation: str, payload: dict[str, Any]
    ) -> dict[str, Any]:
        self.events.publish("calendar.changed")
        return {
            "status": "accepted",
            "operation": operation,
            "policy": "routed_through_core",
            "payload": payload,
        }

    def control(
        self, identity: UIIdentity, control_id: str, payload: dict[str, Any]
    ) -> dict[str, Any]:
        self.events.publish("home.invalidated")
        return {
            "status": "accepted",
            "control_id": control_id,
            "outcome": "UNKNOWN_RESULT",
            "detail": "Verification is pending",
        }

    def alert_policy_mutation(
        self, identity: UIIdentity, operation: str, payload: dict[str, Any]
    ) -> dict[str, Any]:
        del identity
        self.events.publish("alerts.changed")
        return {
            "status": "SUCCEEDED",
            "operation": f"alert_policy.{operation}",
            "result": {"policy": payload},
        }

    def notification_route_mutation(
        self, identity: UIIdentity, operation: str, payload: dict[str, Any]
    ) -> dict[str, Any]:
        del identity
        self.events.publish("capabilities.changed")
        return {
            "status": "SUCCEEDED",
            "operation": f"notification_route.{operation}",
            "result": {"route": payload},
        }

    def integration_mutation(
        self, identity: UIIdentity, operation: str, payload: dict[str, Any]
    ) -> dict[str, Any]:
        del identity, payload
        self.events.publish("capabilities.changed")
        return {"status": "UNAVAILABLE", "operation": f"integration.{operation}"}

    def space_mutation(
        self, identity: UIIdentity, operation: str, payload: dict[str, Any]
    ) -> dict[str, Any]:
        del identity, payload
        self.events.publish("home.invalidated")
        return {"status": "UNAVAILABLE", "operation": f"space.{operation}"}

    def backup_mutation(
        self, identity: UIIdentity, operation: str, payload: dict[str, Any]
    ) -> dict[str, Any]:
        del identity, payload
        self.events.publish("capabilities.changed")
        return {"status": "UNAVAILABLE", "operation": f"backup.{operation}"}

    def scene_mutation(
        self, identity: UIIdentity, operation: str, payload: dict[str, Any]
    ) -> dict[str, Any]:
        del identity
        self.events.publish("capabilities.changed")
        return {"status": "SUCCEEDED", "operation": f"scene.{operation}", "result": payload}

    def apply_scene(self, identity: UIIdentity, scene_id: str) -> dict[str, Any]:
        del identity
        self.events.publish("home.invalidated")
        return {"status": "UNAVAILABLE", "operation": "scene.apply", "scene_id": scene_id}

    def preference_mutation(
        self, identity: UIIdentity, operation: str, payload: dict[str, Any]
    ) -> dict[str, Any]:
        del identity
        self.events.publish("preferences.changed")
        return {
            "status": "SUCCEEDED",
            "operation": f"preference.{operation}",
            "result": {"preference": payload},
        }

    def user_mutation(
        self, identity: UIIdentity, operation: str, payload: dict[str, Any]
    ) -> dict[str, Any]:
        del identity
        self.events.publish("household.changed")
        return {
            "status": "SUCCEEDED",
            "operation": f"user.{operation}",
            "result": {"user": payload},
        }


class JournalConversationIngress:
    def __init__(
        self,
        event_sink: Any | None = None,
        events: UIEventBroadcaster | None = None,
        pipeline: ConversationPipeline | None = None,
        fallback_enabled: bool = False,
    ) -> None:
        self.event_sink = event_sink
        self.events = events
        self.pipeline = pipeline
        self.fallback_enabled = fallback_enabled
        self.events_seen: list[EventEnvelope] = []

    def submit(self, identity: UIIdentity, text: str) -> dict[str, Any]:
        request_id = str(uuid4())
        event = EventEnvelope.create(
            event_id=request_id,
            event_type="user.request",
            source="anima.ui",
            subject_key=f"household/{identity.household_id}",
            occurred_at=_now(),
            payload={"text": text, "origin": RequestOrigin.DIRECT_USER.value},
            importance=EventImportance.IMPORTANT,
            delivery_class=DeliveryClass.GUARANTEED,
            correlation_id=request_id,
            metadata={
                "household_id": str(identity.household_id),
                "principal_id": str(identity.principal_id),
                "ui_version": UI_VERSION,
            },
        )
        self.events_seen.append(event)
        if self.event_sink is not None:
            self.event_sink.append(event)
        if self.pipeline is not None:
            result = self.pipeline.run(identity, event)
        elif self.fallback_enabled:
            result = {
                "response": f"I heard you: {text}",
                "disposition": "RESPONSE_ONLY",
                "trace": {"pipeline": "journal_only_test_fallback"},
            }
        else:
            raise UICommandError("CONVERSATION_PIPELINE_UNAVAILABLE")
        response = str(result.get("response", "Anima completed the request."))[:4000]
        if self.events:
            self.events.publish("conversation.completed")
        return {
            # A queued intelligence request has a different identity from the
            # journal event. The browser polls that durable request, while the
            # event/correlation identity remains in the pipeline trace.
            "request_id": str(result.get("request_id", request_id)),
            "episode_id": str(result.get("episode_id", uuid4())),
            "response": response,
            "disposition": str(result.get("disposition", "RESPONSE_ONLY")),
            "trace": {
                **(result.get("trace", {}) if isinstance(result.get("trace", {}), dict) else {}),
                "origin": RequestOrigin.DIRECT_USER.value,
                "event_type": event.event_type,
                "context": "normal_phase7_phase8_pipeline"
                if self.pipeline is not None
                else "journal_only_test_fallback",
            },
        }


class HomeAssistantOAuth:
    """Small OAuth contract adapter; bearer tokens never enter SessionStore."""

    def __init__(self, config: UIConfig) -> None:
        self.config = config

    def authorization_url(self, state: str) -> str:
        browser_base_url = self.config.ha_browser_url or self.config.ha_base_url
        if not browser_base_url or not self.config.ha_client_id or not self.config.ha_redirect_uri:
            raise UIAuthError("Home Assistant OAuth is not configured")
        from urllib.parse import urlencode

        params = {
            "client_id": self.config.ha_client_id,
            "redirect_uri": self.config.ha_redirect_uri,
            "state": state,
            "response_type": "code",
        }
        return f"{browser_base_url.rstrip('/')}/auth/authorize?{urlencode(params)}"

    async def resolve_user_id(self, code: str) -> str:
        """Exchange one authorization code and query HA's authenticated user.

        The bearer is held only in this coroutine.  It is never returned to
        the browser or passed to the ANIMA session store.
        """
        if not self.config.ha_base_url or not self.config.ha_client_id:
            raise UIAuthError("Home Assistant OAuth is not configured")
        token_url = f"{self.config.ha_base_url.rstrip('/')}/auth/token"
        payload = {
            "grant_type": "authorization_code",
            "code": code,
            "client_id": self.config.ha_client_id,
        }
        async with ClientSession() as session:
            async with session.post(
                token_url, data=payload, timeout=ClientTimeout(total=10)
            ) as response:
                if response.status != 200:
                    raise UIAuthError("HOME_ASSISTANT_OAUTH_EXCHANGE_FAILED")
                token_payload = await response.json()
            access_token = token_payload.get("access_token")
            if not isinstance(access_token, str) or not access_token:
                raise UIAuthError("HOME_ASSISTANT_OAUTH_TOKEN_MISSING")
            websocket_url = self.config.ha_base_url.rstrip("/") + "/api/websocket"
            async with session.ws_connect(websocket_url, receive_timeout=10) as websocket:
                first = await websocket.receive()
                if (
                    first.type != WSMsgType.TEXT
                    or json.loads(first.data).get("type") != "auth_required"
                ):
                    raise UIAuthError("HOME_ASSISTANT_AUTH_HANDSHAKE_FAILED")
                await websocket.send_json({"type": "auth", "access_token": access_token})
                authenticated = await websocket.receive()
                if (
                    authenticated.type != WSMsgType.TEXT
                    or json.loads(authenticated.data).get("type") != "auth_ok"
                ):
                    raise UIAuthError("HOME_ASSISTANT_AUTH_REJECTED")
                await websocket.send_json({"id": 1, "type": "auth/current_user"})
                result = await websocket.receive()
                if result.type != WSMsgType.TEXT:
                    raise UIAuthError("HOME_ASSISTANT_USER_LOOKUP_FAILED")
                data = json.loads(result.data)
                user_id = data.get("result", {}).get("id")
                if not isinstance(user_id, str) or not user_id:
                    raise UIAuthError("HOME_ASSISTANT_USER_ID_MISSING")
                return user_id

    async def connect_owner(self, code: str, store: HAConnectionStore) -> VerifiedHAOwner:
        """Exchange owner consent for a server-held dedicated integration credential."""
        if not self.config.ha_base_url or not self.config.ha_client_id:
            raise UIAuthError("HOME_ASSISTANT_OAUTH_UNAVAILABLE")
        base = self.config.ha_base_url.rstrip("/")
        async with ClientSession(timeout=ClientTimeout(total=30)) as session:
            async with session.post(
                base + "/auth/token",
                data={
                    "grant_type": "authorization_code",
                    "code": code,
                    "client_id": self.config.ha_client_id,
                },
                allow_redirects=False,
            ) as response:
                if response.status != 200:
                    raise UIAuthError("HOME_ASSISTANT_OAUTH_EXCHANGE_FAILED")
                tokens = await response.json()
            token = tokens.get("access_token")
            if not isinstance(token, str) or not token:
                raise UIAuthError("HOME_ASSISTANT_OAUTH_TOKEN_MISSING")
            try:
                async with session.ws_connect(base + "/api/websocket", receive_timeout=10) as ws:
                    if (await ws.receive_json()).get("type") != "auth_required":
                        raise UIAuthError("HOME_ASSISTANT_AUTH_HANDSHAKE_FAILED")
                    await ws.send_json({"type": "auth", "access_token": token})
                    if (await ws.receive_json()).get("type") != "auth_ok":
                        raise UIAuthError("HOME_ASSISTANT_AUTH_REJECTED")

                    async def command(number: int, operation: str, **fields: Any) -> Any:
                        await ws.send_json({"id": number, "type": operation, **fields})
                        result = await ws.receive_json()
                        if result.get("id") != number or result.get("success") is not True:
                            raise UIAuthError("HOME_ASSISTANT_SETUP_REQUEST_FAILED")
                        return result.get("result")

                    user = await command(1, "auth/current_user")
                    if not isinstance(user, dict) or user.get("is_owner") is not True:
                        raise UIAuthError("HOME_ASSISTANT_OWNER_REQUIRED")
                    user_id = user.get("id")
                    if not isinstance(user_id, str) or not user_id:
                        raise UIAuthError("HOME_ASSISTANT_USER_ID_MISSING")
                    existing = store.read()
                    if existing is not None and (
                        existing["user_id"] != user_id
                        or existing["base_url"] != base
                        or existing["instance_id"] != os.environ.get("ANIMA_HA_INSTANCE_ID", "")
                    ):
                        raise UIAuthError("HA_CONNECTION_ALREADY_COMMISSIONED")
                    config = await command(2, "get_config")
                    if not isinstance(config, dict):
                        raise UIAuthError("HOME_ASSISTANT_SETUP_REQUEST_FAILED")
                    credential = (
                        existing["token"]
                        if existing
                        else await command(
                            3,
                            "auth/long_lived_access_token",
                            client_name="ANIMA household connection",
                            lifespan=365,
                        )
                    )
                    if not isinstance(credential, str) or not 32 <= len(credential) <= 8192:
                        raise UIAuthError("HOME_ASSISTANT_OAUTH_TOKEN_MISSING")
                    return VerifiedHAOwner(
                        user_id,
                        str(user.get("name", "Owner"))[:120],
                        str(config.get("location_name", "My home"))[:120],
                        str(config.get("time_zone", "UTC"))[:100],
                        credential,
                    )
            finally:
                # Dispose of this short-lived OAuth grant; the dedicated integration
                # credential is the only credential retained by ANIMA.
                refresh_token = tokens.get("refresh_token")
                if isinstance(refresh_token, str) and refresh_token:
                    try:
                        async with session.post(
                            base + "/auth/token",
                            data={
                                "action": "revoke",
                                "token": refresh_token,
                            },
                            allow_redirects=False,
                        ) as revoked:
                            await revoked.read()
                    except (ClientError, OSError, TimeoutError):
                        pass


class UIService:
    def __init__(
        self,
        *,
        config: UIConfig | None = None,
        sessions: SessionStore | None = None,
        read_model: HouseholdReadModel | None = None,
        commands: UICommandGateway | None = None,
        conversation: ConversationIngress | None = None,
        core_runtime: Any | None = None,
        identity_resolver: CommissionedIdentityResolver | None = None,
        ha_user_map: dict[str, tuple[UUID, UUID]] | None = None,
        sentry_results: PostgresSentryLiveResultBus | None = None,
    ) -> None:
        self.config = config or UIConfig()
        self.core_runtime = core_runtime
        self.sessions = sessions or InMemorySessionStore()
        self.events = UIEventBroadcaster()
        self.read_model = read_model or (
            DemoHouseholdReadModel()
            if self.config.test_auth_enabled
            else UnavailableHouseholdReadModel()
        )
        self.identity_resolver = identity_resolver
        self.sentry_results = sentry_results
        if core_runtime is not None:
            self.commands = commands or core_runtime.commands(self.events)
            self.conversation = conversation or JournalConversationIngress(
                event_sink=core_runtime.journal,
                events=self.events,
                pipeline=core_runtime.conversation(self.events),
                fallback_enabled=False,
            )
        else:
            self.commands = commands or UnavailableCommandGateway()
            self.conversation = conversation or JournalConversationIngress(
                events=self.events, fallback_enabled=self.config.test_auth_enabled
            )
        self.ha_user_map = (
            dict(ha_user_map or {"test-ha-user": (DEFAULT_HOUSEHOLD_ID, DEFAULT_PRINCIPAL_ID)})
            if self.config.test_auth_enabled
            else {}
        )
        self.oauth = HomeAssistantOAuth(self.config)
        self._oauth_states: dict[str, tuple[str, datetime]] = {}
        self._oauth_connection_states: set[str] = set()
        self._connection_lock = asyncio.Lock()
        self._owner_boundary: Any | None = None
        self.owner_boundary_status = "NOT_CONFIGURED"

    def start_owner_boundary(self) -> None:
        directory = os.environ.get("ANIMA_OWNER_BOUNDARY_DIR", "")
        if not directory or self._owner_boundary is not None or self.core_runtime is None:
            return
        from anima_ha.ha_connection_setup import configured_connection
        from anima_ha.owner_boundary import OwnerBoundary

        try:
            connection = configured_connection()
            if connection is None:
                self.owner_boundary_status = "HA_SETUP_REQUIRED"
                return
            group = os.environ.get("ANIMA_OWNER_BOUNDARY_GROUP", "")
            self._owner_boundary = OwnerBoundary(
                self.core_runtime,
                UUID(connection["household_id"]),
                os.environ["ANIMA_DATABASE_URL"],
                Path(directory),
                socket_group=int(group) if group else None,
            )
            self.owner_boundary_status = "READY"
        except Exception as exc:
            # A provider-boundary outage must not take away direct household UI.
            self.owner_boundary_status = "UNAVAILABLE"
            logging.getLogger(__name__).warning(
                "Owner provider boundary unavailable: %s", type(exc).__name__
            )

    def close_owner_boundary(self) -> None:
        if self._owner_boundary is not None:
            self._owner_boundary.close()
            self._owner_boundary = None

    def connection_status(self, identity: UIIdentity | None = None) -> dict[str, Any]:
        adapter = getattr(self.core_runtime, "home_assistant_adapter", None)
        configured = adapter is not None
        state = adapter.status.health.value if adapter is not None else "SETUP_REQUIRED"
        source = "uncommissioned"
        if identity is not None and self.core_runtime is not None:
            household = self.core_runtime.graph.get_node(identity.household_id)
            source = (
                str(household.metadata.get("source", "qualification_or_manual"))
                if household
                else "unknown"
            )
        return {
            "configured": configured,
            "connected": state == "ONLINE",
            "state": state,
            "can_connect": bool(
                os.environ.get("ANIMA_HA_CONNECTION_FILE") and self.config.ha_base_url
            ),
            "setup_required": not configured,
            "household_source": source,
            "assistant_service": self.owner_boundary_status,
        }

    def rebuild_connected_core(self) -> None:
        """Recompose after first owner setup, preserving sessions and UI invalidations."""
        from anima_ha.ui_runtime import build_postgres_core

        database_url = os.environ.get("ANIMA_DATABASE_URL", "")
        if not database_url:
            raise UIAuthError("HOUSEHOLD_DATABASE_UNAVAILABLE")
        if getattr(self.core_runtime, "home_assistant_adapter", None) is not None:
            return
        core = build_postgres_core(database_url, opa_url=self.config.opa_url)
        self.core_runtime = core
        self.identity_resolver = core.identity_resolver
        self.commands = core.commands(self.events)
        self.conversation = JournalConversationIngress(
            event_sink=core.journal,
            events=self.events,
            pipeline=core.conversation(self.events),
            fallback_enabled=False,
        )
        self.read_model = PostgresHouseholdReadModel(
            database_url,
            graph=core.graph,
            truth=core.truth.projection,
            plugins=core.plugins,
            alert_policy_store=core.alert_policy_store,
            notification_route_store=core.notification_route_store,
            backup_coordinator=core.backup_coordinator,
            scene_store=core.scene_store,
            automation_store=core.automation_store,
            memory_service=core.memory_service,
        )
        self.events.publish("home.invalidated")
        self.start_owner_boundary()

    def conversation_result(self, identity: UIIdentity, request_id: str) -> dict[str, Any]:
        """Return one household-scoped SENTRY result without durable text."""

        try:
            request_uuid = UUID(request_id)
        except ValueError as exc:
            raise UICommandError("CONVERSATION_RESULT_NOT_FOUND") from exc
        store = getattr(self.core_runtime, "intelligence_store", None)
        request = store.get(request_uuid) if store is not None else None
        if request is None or request.household_id != identity.household_id:
            raise UICommandError("CONVERSATION_RESULT_NOT_FOUND")
        live = (
            self.sentry_results.get(request_uuid, identity.household_id)
            if self.sentry_results is not None
            else None
        )
        if live is not None:
            return {
                "request_id": request_id,
                "status": str(live.get("status", "UNKNOWN_RESULT")),
                "lifecycle": request.lifecycle.value,
                "response": live.get("response"),
                "detail": live.get("detail"),
                "provider_ambiguous": bool(live.get("provider_ambiguous", False)),
                "available": True,
            }
        terminal = request.lifecycle.value in {
            "COMPLETED",
            "NO_ACTION",
            "FAILED",
            "UNKNOWN_RESULT",
            "RECOVERY_REQUIRED",
            "CANCELLED",
        }
        return {
            "request_id": request_id,
            "status": request.lifecycle.value,
            "lifecycle": request.lifecycle.value,
            "response": None,
            "detail": (
                "SENTRY response is not available in the current live delivery window"
                if terminal
                else "SENTRY is still reasoning through ANIMA"
            ),
            "available": False,
        }

    def create_oauth_state(self) -> str:
        state = secrets.token_urlsafe(24)
        self._oauth_states[state] = (secrets.token_urlsafe(32), _now() + OAUTH_STATE_TTL)
        return state

    def oauth_nonce(self, state: str) -> str | None:
        record = self._oauth_states.get(state)
        return record[0] if record and record[1] > _now() else None

    def consume_oauth_state(self, state: str, nonce: str | None = None) -> bool:
        record = self._oauth_states.pop(state, None)
        if (
            record is None
            or record[1] <= _now()
            or not nonce
            or not hmac.compare_digest(record[0], nonce)
        ):
            return False
        return True

    def map_ha_user(self, ha_user_id: str) -> UIIdentity:
        mapping = (
            self.identity_resolver.resolve_ha_user(ha_user_id)
            if self.identity_resolver is not None
            else self.ha_user_map.get(ha_user_id)
        )
        if mapping is None:
            raise PrincipalMappingRequired("PRINCIPAL_MAPPING_REQUIRED")
        household_id, principal_id = mapping
        now = _now()
        evidence = IdentityEvidence(
            evidence_id=uuid4(),
            household_id=household_id,
            claimed_principal_id=principal_id,
            evidence_type=EvidenceType.AUTHENTICATED_SESSION,
            issuer="home_assistant_oauth",
            issued_at=now,
            observed_at=now,
            expires_at=now + self.config.session_absolute_ttl,
            assurance=Assurance.AUTHENTICATED,
            strength=70,
            provenance="ha_oauth_user_lookup",
        )
        node = self.core_runtime.graph.get_node(principal_id) if self.core_runtime else None
        return UIIdentity(
            household_id,
            principal_id,
            ha_user_id,
            evidence,
            str(node.name)[:120] if node else "Household member",
        )

    def issue_session(
        self, identity: UIIdentity, device_label: str | None = None
    ) -> tuple[str, str]:
        session_id = uuid4()
        secret = secrets.token_urlsafe(32)
        csrf = _session_csrf(_hash(secret))
        now = _now()
        record = SessionRecord(
            session_id,
            _hash(secret),
            identity.household_id,
            identity.principal_id,
            now,
            now,
            now + self.config.session_absolute_ttl,
            _hash(csrf),
            device_label,
        )
        self.sessions.create(record)
        return f"{session_id}.{secret}", csrf

    def authenticate(self, cookie: str | None) -> tuple[SessionRecord, str]:
        if not cookie or "." not in cookie:
            raise UIAuthError("AUTHENTICATION_REQUIRED")
        raw_id, secret = cookie.split(".", 1)
        try:
            session_id = UUID(raw_id)
        except ValueError as exc:
            raise UIAuthError("AUTHENTICATION_REQUIRED") from exc
        record = self.sessions.get(session_id)
        now = _now()
        if (
            record is None
            or record.revoked_at
            or record.expires_at <= now
            or record.last_seen_at + self.config.session_idle_ttl <= now
        ):
            raise UIAuthError("SESSION_EXPIRED")
        if not hmac.compare_digest(record.secret_hash, _hash(secret)):
            raise UIAuthError("AUTHENTICATION_REQUIRED")
        refreshed = SessionRecord(
            record.session_id,
            record.secret_hash,
            record.household_id,
            record.principal_id,
            record.created_at,
            now,
            record.expires_at,
            record.csrf_hash,
            record.device_label,
            record.revoked_at,
        )
        self.sessions.save(refreshed)
        return refreshed, secret

    def identity_from_session(self, record: SessionRecord) -> UIIdentity:
        if self.identity_resolver is not None:
            household_id, principal_id, ha_user_id = self.identity_resolver.resolve_principal(
                record.principal_id
            )
            if household_id != record.household_id:
                raise UIAuthError("PRINCIPAL_MAPPING_REQUIRED")
            now = _now()
            evidence = IdentityEvidence(
                evidence_id=uuid4(),
                household_id=household_id,
                claimed_principal_id=principal_id,
                evidence_type=EvidenceType.AUTHENTICATED_SESSION,
                issuer="anima_session",
                issued_at=record.created_at,
                observed_at=now,
                expires_at=record.expires_at,
                assurance=Assurance.AUTHENTICATED,
                strength=70,
                provenance="commissioned_graph_identity",
            )
            node = self.core_runtime.graph.get_node(principal_id) if self.core_runtime else None
            return UIIdentity(
                household_id,
                principal_id,
                ha_user_id or "",
                evidence,
                str(node.name)[:120] if node else "Household member",
            )
        for ha_user_id, value in self.ha_user_map.items():
            if value == (record.household_id, record.principal_id):
                return self.map_ha_user(ha_user_id)
        raise UIAuthError("PRINCIPAL_MAPPING_REQUIRED")


class ConversationRequest(BaseModel):
    text: str = Field(min_length=1, max_length=MAX_CONVERSATION_CHARS)


class MutationRequest(BaseModel):
    payload: dict[str, Any] = Field(default_factory=dict)


def create_app(
    service: UIService | None = None,
    *,
    codex: Any | None = None,
    external_transport: Any | None = None,
) -> FastAPI:
    if service is None:
        config = UIConfig.from_environment()
        database_url = os.environ.get("ANIMA_DATABASE_URL", "").strip()
        sessions: SessionStore | None = (
            PostgresSessionStore(database_url) if database_url else InMemorySessionStore()
        )
        core_runtime = None
        read_model: HouseholdReadModel | None = None
        sentry_results: PostgresSentryLiveResultBus | None = None
        if database_url:
            from anima_ha.ui_runtime import build_postgres_core

            core_runtime = build_postgres_core(
                database_url,
                opa_url=config.opa_url,
                codex=codex,
                external_transport=external_transport,
            )
            read_model = PostgresHouseholdReadModel(
                database_url,
                graph=core_runtime.graph,
                truth=core_runtime.truth.projection,
                plugins=core_runtime.plugins,
                alert_policy_store=core_runtime.alert_policy_store,
                notification_route_store=core_runtime.notification_route_store,
                backup_coordinator=core_runtime.backup_coordinator,
                scene_store=core_runtime.scene_store,
                automation_store=core_runtime.automation_store,
                memory_service=core_runtime.memory_service,
            )
            if core_runtime.intelligence_provider.value == "sentry":
                sentry_results = PostgresSentryLiveResultBus(database_url)
        svc = UIService(
            config=config,
            sessions=sessions,
            read_model=read_model,
            core_runtime=core_runtime,
            identity_resolver=core_runtime.identity_resolver if core_runtime else None,
            sentry_results=sentry_results,
        )
    else:
        svc = service
    app = FastAPI(title="ANIMA local interface", version=UI_VERSION, docs_url=None, redoc_url=None)
    app.state.ui_service = svc
    app.router.add_event_handler("startup", svc.start_owner_boundary)
    app.router.add_event_handler("shutdown", svc.close_owner_boundary)
    if svc.sentry_results is not None:
        app.router.add_event_handler("shutdown", svc.sentry_results.close)

    @app.middleware("http")
    async def security_headers(
        request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        response = await call_next(request)
        response.headers["Content-Security-Policy"] = "; ".join(
            (
                "default-src 'self'",
                "script-src 'self'",
                "style-src 'self' 'unsafe-inline'",
                "img-src 'self' data:",
                "connect-src 'self'",
                "font-src 'self'",
                "frame-ancestors 'none'",
            )
        )
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
        response.headers["Cache-Control"] = "no-store"
        return response

    def current_session(request: Request) -> SessionRecord:
        try:
            return svc.authenticate(request.cookies.get(UI_SESSION_COOKIE))[0]
        except UIAuthError as exc:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(exc)) from exc

    def current_identity(request: Request) -> UIIdentity:
        return svc.identity_from_session(current_session(request))

    def require_mutation(
        request: Request, x_anima_csrf: str | None, session: SessionRecord
    ) -> None:
        origin = request.headers.get("origin")
        expected_origin = f"{request.url.scheme}://{request.headers.get('host', '')}"
        if not origin or origin != expected_origin:
            raise HTTPException(status_code=403, detail="ORIGIN_REJECTED")
        if not x_anima_csrf or not (
            hmac.compare_digest(_session_csrf(session.secret_hash), x_anima_csrf)
            or hmac.compare_digest(session.csrf_hash, _hash(x_anima_csrf))
        ):
            raise HTTPException(status_code=403, detail="CSRF_REJECTED")

    install_knowledge_api(app, svc, current_identity, current_session, require_mutation)
    install_household_learning_api(
        app,
        svc,
        current_identity=current_identity,
        current_session=current_session,
        require_mutation=require_mutation,
    )
    install_ring_api(
        app,
        svc,
        current_identity=current_identity,
        current_session=current_session,
        require_mutation=require_mutation,
    )
    install_household_presence_api(
        app,
        svc,
        current_identity=current_identity,
        current_session=current_session,
        require_mutation=require_mutation,
    )
    install_family_routines_api(
        app,
        svc,
        current_identity=current_identity,
        current_session=current_session,
        require_mutation=require_mutation,
    )

    # The optional relay is separate from owner/SENTRY authentication. Resolve
    # the current Core lazily so first-time HA commissioning cannot leave a
    # receiver attached to obsolete stores. No parser or token comes from UI.
    vendor_ingress_lock = Lock()
    vendor_ingress: VendorEventIngress | None = None
    vendor_runtime: Any = None

    def current_vendor_ingress() -> VendorEventIngress:
        nonlocal vendor_ingress, vendor_runtime
        with vendor_ingress_lock:
            runtime = svc.core_runtime
            if vendor_ingress is None or vendor_runtime is not runtime:
                try:
                    relay_config = VendorRelayConfig.from_environment()
                except (VendorIngressError, OSError, ValueError):
                    raise HTTPException(503, "VENDOR_CONFIGURATION_UNAVAILABLE") from None
                dispatch = None
                if runtime is not None and runtime.intelligence_store is not None:
                    dispatch = ExactVendorAttention(
                        runtime.attention,
                        runtime.context,
                        runtime.intelligence_store,
                        runtime.plugins.list_tools,
                    )
                vendor_ingress = VendorEventIngress(
                    relay_config,
                    journal=getattr(runtime, "journal", None),
                    graph=getattr(runtime, "graph", None),
                    dispatch=dispatch,
                )
                vendor_runtime = runtime
            return vendor_ingress

    install_vendor_event_api(app, current_identity, current_vendor_ingress)

    @app.get("/healthz")
    async def healthz() -> dict[str, str]:
        return {"status": "ok", "service": "anima-ui", "version": UI_VERSION}

    @app.get("/auth/login")
    async def login(connect: bool = False) -> Response:
        state = svc.create_oauth_state()
        if connect:
            if not os.environ.get("ANIMA_HA_CONNECTION_FILE") or svc.config.test_auth_enabled:
                raise HTTPException(status_code=503, detail="HA_OWNER_SETUP_UNAVAILABLE")
            svc._oauth_connection_states.add(state)
        nonce = svc.oauth_nonce(state)
        if svc.config.test_auth_enabled:
            response = RedirectResponse(f"/auth/callback?code=anima-test-code&state={state}")
            if nonce:
                response.set_cookie(
                    UI_OAUTH_NONCE_COOKIE,
                    nonce,
                    httponly=True,
                    samesite="strict",
                    secure=False,
                    max_age=int(OAUTH_STATE_TTL.total_seconds()),
                    path="/",
                )
            return response
        try:
            response = RedirectResponse(svc.oauth.authorization_url(state))
            if nonce:
                response.set_cookie(
                    UI_OAUTH_NONCE_COOKIE,
                    nonce,
                    httponly=True,
                    samesite="strict",
                    secure=False,
                    max_age=int(OAUTH_STATE_TTL.total_seconds()),
                    path="/",
                )
            return response
        except UIAuthError as exc:
            raise HTTPException(status_code=503, detail="HOME_ASSISTANT_OAUTH_UNAVAILABLE") from exc

    @app.get("/auth/callback")
    async def callback(request: Request, code: str, state: str) -> Response:
        connect = state in svc._oauth_connection_states
        svc._oauth_connection_states.discard(state)
        if not svc.consume_oauth_state(state, request.cookies.get(UI_OAUTH_NONCE_COOKIE)):
            raise HTTPException(status_code=400, detail="OAUTH_STATE_REJECTED")
        if svc.config.test_auth_enabled and code == "anima-test-code":
            identity = svc.map_ha_user("test-ha-user")
            cookie, csrf = svc.issue_session(identity, "browser")
            response = RedirectResponse("/")
            _set_ui_session_cookie(response, cookie, svc.config)
            response.delete_cookie(UI_OAUTH_NONCE_COOKIE, path="/")
            response.headers["X-Anima-CSRF"] = csrf
            return response
        try:
            if connect:
                async with svc._connection_lock:
                    store = HAConnectionStore(Path(os.environ["ANIMA_HA_CONNECTION_FILE"]))
                    owner = await svc.oauth.connect_owner(code, store)
                    if svc.core_runtime is None:
                        raise UIAuthError("HOUSEHOLD_DATABASE_UNAVAILABLE")
                    await asyncio.to_thread(
                        commission_owner,
                        svc.core_runtime.graph,
                        store,
                        owner,
                        instance_id=UUID(os.environ["ANIMA_HA_INSTANCE_ID"]),
                        base_url=svc.config.ha_base_url or "",
                    )
                    await asyncio.to_thread(svc.rebuild_connected_core)
                    ha_user_id = owner.user_id
            else:
                ha_user_id = await svc.oauth.resolve_user_id(code)
            identity = svc.map_ha_user(ha_user_id)
        except (UIAuthError, HASetupError) as exc:
            raise HTTPException(status_code=502, detail=str(exc)) from exc
        cookie, csrf = svc.issue_session(identity, "browser")
        response = RedirectResponse("/")
        _set_ui_session_cookie(response, cookie, svc.config)
        response.delete_cookie(UI_OAUTH_NONCE_COOKIE, path="/")
        response.headers["X-Anima-CSRF"] = csrf
        return response

    @app.post("/auth/logout")
    async def logout(
        request: Request, x_anima_csrf: str | None = Header(default=None, alias="X-Anima-CSRF")
    ) -> Response:
        session = current_session(request)
        require_mutation(request, x_anima_csrf, session)
        svc.sessions.revoke(session.session_id, _now())
        response = JSONResponse({"status": "signed_out"})
        response.delete_cookie(UI_SESSION_COOKIE, path="/")
        return response

    @app.get("/api/v1/bootstrap")
    async def bootstrap(request: Request) -> dict[str, Any]:
        session = current_session(request)
        identity = svc.identity_from_session(session)
        csrf = _session_csrf(session.secret_hash)
        result = svc.read_model.bootstrap(identity)
        result["csrf_token"] = csrf
        return result

    @app.get("/api/v1/setup/status")
    async def setup_status() -> dict[str, Any]:
        connection = svc.connection_status()
        return {"state": connection["state"], "available": connection["can_connect"]}

    @app.get("/api/v1/connection")
    async def connection_status(request: Request) -> dict[str, Any]:
        return svc.connection_status(current_identity(request))

    @app.get("/api/v1/home")
    async def home(request: Request) -> dict[str, Any]:
        return svc.read_model.home(current_identity(request))

    @app.get("/api/v1/tasks")
    async def tasks(request: Request) -> dict[str, Any]:
        try:
            limit = int(request.query_params.get("limit", str(UI_PAGE_SIZE)))
            cursor = request.query_params.get("cursor")
            return svc.read_model.tasks_page(current_identity(request), cursor=cursor, limit=limit)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail="INVALID_TASK_PAGE") from exc

    @app.post("/api/v1/tasks")
    async def create_task(
        request: Request,
        body: MutationRequest,
        x_anima_csrf: str | None = Header(default=None, alias="X-Anima-CSRF"),
    ) -> dict[str, Any]:
        session = current_session(request)
        require_mutation(request, x_anima_csrf, session)
        try:
            return svc.commands.task_mutation(
                svc.identity_from_session(session), "schedule", body.payload
            )
        except UICommandError as exc:
            raise HTTPException(status_code=503, detail=str(exc)) from exc

    @app.post("/api/v1/tasks/{task_id}/{operation}")
    async def mutate_task(
        task_id: str,
        operation: str,
        request: Request,
        body: MutationRequest,
        x_anima_csrf: str | None = Header(default=None, alias="X-Anima-CSRF"),
    ) -> dict[str, Any]:
        if operation not in {"pause", "resume", "cancel"}:
            raise HTTPException(status_code=404, detail="UNKNOWN_TASK_OPERATION")
        session = current_session(request)
        require_mutation(request, x_anima_csrf, session)
        try:
            return svc.commands.task_mutation(
                svc.identity_from_session(session), operation, {**body.payload, "task_id": task_id}
            )
        except UICommandError as exc:
            raise HTTPException(status_code=503, detail=str(exc)) from exc

    @app.get("/api/v1/settings")
    async def settings(request: Request) -> dict[str, Any]:
        return {"settings": svc.read_model.settings(current_identity(request))}

    @app.put("/api/v1/settings")
    async def update_settings(
        request: Request,
        body: MutationRequest,
        x_anima_csrf: str | None = Header(default=None, alias="X-Anima-CSRF"),
    ) -> dict[str, Any]:
        session = current_session(request)
        require_mutation(request, x_anima_csrf, session)
        try:
            return {
                "settings": svc.read_model.update_settings(
                    svc.identity_from_session(session), body.payload
                )
            }
        except UICommandError as exc:
            raise HTTPException(status_code=503, detail=str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(status_code=400, detail="INVALID_UI_PREFERENCES") from exc

    @app.get("/api/v1/sentry/voice-settings")
    async def sentry_voice_settings(request: Request) -> dict[str, Any]:
        return {"settings": svc.read_model.sentry_voice_settings(current_identity(request))}

    @app.put("/api/v1/sentry/voice-settings")
    async def update_sentry_voice_settings(
        request: Request,
        body: MutationRequest,
        x_anima_csrf: str | None = Header(default=None, alias="X-Anima-CSRF"),
    ) -> dict[str, Any]:
        session = current_session(request)
        require_mutation(request, x_anima_csrf, session)
        try:
            settings = svc.read_model.update_sentry_voice_settings(
                svc.identity_from_session(session), body.payload
            )
            return {"status": "SUCCEEDED", "settings": settings}
        except UICommandError as exc:
            raise HTTPException(status_code=503, detail=str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(status_code=400, detail="INVALID_SENTRY_VOICE_SETTINGS") from exc

    @app.get("/api/v1/preferences")
    def preferences(
        request: Request,
        scope: str | None = None,
        person_id: str | None = None,
        category: str | None = None,
        limit: int = 50,
        cursor: str | None = None,
    ) -> dict[str, Any]:
        from anima_ha.family_routines import family_routine_options

        identity = current_identity(request)
        memory = getattr(svc.read_model, "memory_service", None)
        graph = getattr(svc.read_model, "graph", None)
        if memory is None or graph is None:
            return {
                "items": svc.read_model.preferences(identity),
                "next_cursor": None,
                "members": [],
                "can_edit": False,
            }
        try:
            page = preferences_page(
                memory,
                identity.household_id,
                graph=graph,
                scope=scope,
                person_id=person_id,
                category=category,
                limit=limit,
                cursor=cursor,
            )
            options = family_routine_options(graph, identity.household_id)
            principal = graph.get_node(identity.principal_id)
            return {
                **page,
                "members": options["members"],
                "can_edit": bool(
                    principal
                    and principal.retired_at is None
                    and principal.metadata.get("semantic_role") == "owner"
                    and any(
                        item["person_id"] == str(identity.principal_id)
                        for item in options["members"]
                    )
                ),
            }
        except (PreferenceValidationError, ValueError, TypeError):
            raise HTTPException(400, "INVALID_PREFERENCE_FILTER") from None

    @app.post("/api/v1/preferences/{operation}")
    def mutate_preference(
        operation: str,
        request: Request,
        body: MutationRequest,
        x_anima_csrf: str | None = Header(default=None, alias="X-Anima-CSRF"),
    ) -> dict[str, Any]:
        if operation not in {"create", "update", "retract"}:
            raise HTTPException(status_code=404, detail="UNKNOWN_PREFERENCE_OPERATION")
        session = current_session(request)
        require_mutation(request, x_anima_csrf, session)
        try:
            return svc.commands.preference_mutation(
                svc.identity_from_session(session), operation, body.payload
            )
        except UICommandError as exc:
            raise HTTPException(status_code=503, detail=str(exc)) from exc
        except (ValueError, TypeError) as exc:
            raise HTTPException(status_code=400, detail="INVALID_PREFERENCE") from exc

    @app.get("/api/v1/users")
    async def users(request: Request) -> dict[str, Any]:
        return {"items": svc.read_model.users(current_identity(request))}

    @app.post("/api/v1/users/{operation}")
    async def mutate_users(
        operation: str,
        request: Request,
        body: MutationRequest,
        x_anima_csrf: str | None = Header(default=None, alias="X-Anima-CSRF"),
    ) -> dict[str, Any]:
        if operation not in {
            "create",
            "update",
            "face-start",
            "face-capture",
            "face-remove-sample",
            "face-commit",
            "face-cancel",
            "face-delete",
        }:
            raise HTTPException(status_code=404, detail="UNKNOWN_USER_OPERATION")
        session = current_session(request)
        require_mutation(request, x_anima_csrf, session)
        try:
            return svc.commands.user_mutation(
                svc.identity_from_session(session), operation, body.payload
            )
        except UICommandError as exc:
            raise HTTPException(status_code=503, detail=str(exc)) from exc
        except (ValueError, TypeError) as exc:
            raise HTTPException(status_code=400, detail="INVALID_USER") from exc

    @app.get("/api/v1/scenes")
    async def scenes(request: Request) -> dict[str, Any]:
        return {"items": svc.read_model.scenes(current_identity(request))}

    @app.get("/api/v1/automations")
    async def automations(request: Request) -> dict[str, Any]:
        return {"items": svc.read_model.automations(current_identity(request))}

    @app.post("/api/v1/automations")
    async def save_automation(
        request: Request,
        body: MutationRequest,
        x_anima_csrf: str | None = Header(default=None, alias="X-Anima-CSRF"),
    ) -> dict[str, Any]:
        session = current_session(request)
        require_mutation(request, x_anima_csrf, session)
        operation = "update" if body.payload.get("automation_id") else "create"
        try:
            return svc.commands.automation_mutation(
                svc.identity_from_session(session), operation, body.payload
            )
        except UICommandError as exc:
            raise HTTPException(status_code=503, detail=str(exc)) from exc

    @app.post("/api/v1/scenes")
    async def save_scene(
        request: Request,
        body: MutationRequest,
        x_anima_csrf: str | None = Header(default=None, alias="X-Anima-CSRF"),
    ) -> dict[str, Any]:
        session = current_session(request)
        require_mutation(request, x_anima_csrf, session)
        operation = "update" if body.payload.get("scene_id") else "create"
        try:
            return svc.commands.scene_mutation(
                svc.identity_from_session(session), operation, body.payload
            )
        except UICommandError as exc:
            raise HTTPException(status_code=503, detail=str(exc)) from exc

    @app.post("/api/v1/scenes/{scene_id}/apply")
    async def apply_scene(
        scene_id: str,
        request: Request,
        x_anima_csrf: str | None = Header(default=None, alias="X-Anima-CSRF"),
    ) -> dict[str, Any]:
        session = current_session(request)
        require_mutation(request, x_anima_csrf, session)
        try:
            return svc.commands.apply_scene(svc.identity_from_session(session), scene_id)
        except UICommandError as exc:
            raise HTTPException(status_code=503, detail=str(exc)) from exc

    @app.get("/api/v1/calendar")
    async def calendar(request: Request) -> dict[str, Any]:
        try:
            limit = int(request.query_params.get("limit", str(UI_PAGE_SIZE)))
            cursor = request.query_params.get("cursor")
            return svc.read_model.calendar_page(
                current_identity(request), cursor=cursor, limit=limit
            )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail="INVALID_CALENDAR_PAGE") from exc

    @app.post("/api/v1/calendar")
    async def create_calendar(
        request: Request,
        body: MutationRequest,
        x_anima_csrf: str | None = Header(default=None, alias="X-Anima-CSRF"),
    ) -> dict[str, Any]:
        session = current_session(request)
        require_mutation(request, x_anima_csrf, session)
        try:
            return svc.commands.calendar_mutation(
                svc.identity_from_session(session), "create_event", body.payload
            )
        except UICommandError as exc:
            raise HTTPException(status_code=503, detail=str(exc)) from exc

    @app.post("/api/v1/calendar/{event_id}/{operation}")
    async def mutate_calendar(
        event_id: str,
        operation: str,
        request: Request,
        body: MutationRequest,
        x_anima_csrf: str | None = Header(default=None, alias="X-Anima-CSRF"),
    ) -> dict[str, Any]:
        if operation not in {"update", "cancel"}:
            raise HTTPException(status_code=404, detail="UNKNOWN_CALENDAR_OPERATION")
        session = current_session(request)
        require_mutation(request, x_anima_csrf, session)
        try:
            payload = {**body.payload, "event_id": event_id}
            return svc.commands.calendar_mutation(
                svc.identity_from_session(session), f"{operation}_event", payload
            )
        except UICommandError as exc:
            raise HTTPException(status_code=503, detail=str(exc)) from exc

    @app.get("/api/v1/activity")
    async def activity(request: Request) -> dict[str, Any]:
        return {"items": svc.read_model.activity(current_identity(request))}

    @app.get("/api/v1/capabilities")
    async def capabilities(request: Request) -> dict[str, Any]:
        return {"items": svc.read_model.capabilities(current_identity(request))}

    @app.get("/api/v1/integrations")
    async def integrations(request: Request) -> dict[str, Any]:
        return {"items": svc.read_model.integrations(current_identity(request))}

    @app.get("/api/v1/backups")
    async def backups(request: Request) -> dict[str, Any]:
        return {"items": svc.read_model.backups(current_identity(request))}

    @app.post("/api/v1/backups/{operation}")
    async def mutate_backups(
        operation: str,
        request: Request,
        body: MutationRequest,
        x_anima_csrf: str | None = Header(default=None, alias="X-Anima-CSRF"),
    ) -> dict[str, Any]:
        if operation not in {"create", "inspect", "restore"}:
            raise HTTPException(status_code=404, detail="UNKNOWN_BACKUP_OPERATION")
        session = current_session(request)
        require_mutation(request, x_anima_csrf, session)
        try:
            return svc.commands.backup_mutation(
                svc.identity_from_session(session), operation, body.payload
            )
        except UICommandError as exc:
            raise HTTPException(status_code=503, detail=str(exc)) from exc

    @app.get("/api/v1/places")
    async def places(request: Request) -> dict[str, Any]:
        return {"items": svc.read_model.places(current_identity(request))}

    @app.post("/api/v1/places/{operation}")
    async def mutate_places(
        operation: str,
        request: Request,
        body: MutationRequest,
        x_anima_csrf: str | None = Header(default=None, alias="X-Anima-CSRF"),
    ) -> dict[str, Any]:
        if operation not in {"create", "rename", "move", "remove"}:
            raise HTTPException(status_code=404, detail="UNKNOWN_SPACE_OPERATION")
        session = current_session(request)
        require_mutation(request, x_anima_csrf, session)
        try:
            return svc.commands.space_mutation(
                svc.identity_from_session(session), operation, body.payload
            )
        except UICommandError as exc:
            raise HTTPException(status_code=503, detail=str(exc)) from exc

    @app.post("/api/v1/integrations/{operation}")
    async def mutate_integrations(
        operation: str,
        request: Request,
        body: MutationRequest,
        x_anima_csrf: str | None = Header(default=None, alias="X-Anima-CSRF"),
    ) -> dict[str, Any]:
        if operation not in {"set-enabled", "reconnect", "setup-zha", "continue-zha"}:
            raise HTTPException(status_code=404, detail="UNKNOWN_INTEGRATION_OPERATION")
        session = current_session(request)
        require_mutation(request, x_anima_csrf, session)
        try:
            return svc.commands.integration_mutation(
                svc.identity_from_session(session), operation, body.payload
            )
        except UICommandError as exc:
            raise HTTPException(status_code=503, detail=str(exc)) from exc

    @app.get("/api/v1/devices")
    async def devices(request: Request) -> dict[str, Any]:
        return svc.commands.device_inventory(current_identity(request))

    @app.get("/api/v1/alerts/policies")
    async def alert_policies(request: Request) -> dict[str, Any]:
        return {"items": svc.read_model.alert_policies(current_identity(request))}

    @app.get("/api/v1/alerts/events")
    async def alert_events(request: Request) -> dict[str, Any]:
        try:
            limit = int(request.query_params.get("limit", str(UI_PAGE_SIZE)))
            cursor = request.query_params.get("cursor")
            return svc.read_model.alert_events(
                current_identity(request), cursor=cursor, limit=limit
            )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail="INVALID_ALERT_PAGE") from exc

    @app.post("/api/v1/alerts/policies")
    async def save_alert_policy(
        request: Request,
        body: MutationRequest,
        x_anima_csrf: str | None = Header(default=None, alias="X-Anima-CSRF"),
    ) -> dict[str, Any]:
        session = current_session(request)
        require_mutation(request, x_anima_csrf, session)
        try:
            return svc.commands.alert_policy_mutation(
                svc.identity_from_session(session), "save_policy", body.payload
            )
        except UICommandError as exc:
            raise HTTPException(status_code=503, detail=str(exc)) from exc

    @app.get("/api/v1/notifications/routes")
    async def notification_routes(request: Request) -> dict[str, Any]:
        return {"items": svc.read_model.notification_routes(current_identity(request))}

    @app.post("/api/v1/notifications/routes")
    async def save_notification_route(
        request: Request,
        body: MutationRequest,
        x_anima_csrf: str | None = Header(default=None, alias="X-Anima-CSRF"),
    ) -> dict[str, Any]:
        session = current_session(request)
        require_mutation(request, x_anima_csrf, session)
        try:
            return svc.commands.notification_route_mutation(
                svc.identity_from_session(session), "save_route", body.payload
            )
        except UICommandError as exc:
            raise HTTPException(status_code=503, detail=str(exc)) from exc

    @app.post("/api/v1/devices/{operation}")
    async def mutate_devices(
        operation: str,
        request: Request,
        body: MutationRequest,
        x_anima_csrf: str | None = Header(default=None, alias="X-Anima-CSRF"),
    ) -> dict[str, Any]:
        if operation not in {
            "refresh",
            "permit-pairing",
            "commission",
            "rename",
            "reassign",
            "retire",
        }:
            raise HTTPException(status_code=404, detail="UNKNOWN_DEVICE_OPERATION")
        session = current_session(request)
        require_mutation(request, x_anima_csrf, session)
        try:
            return svc.commands.device_mutation(
                svc.identity_from_session(session), operation, body.payload
            )
        except UICommandError as exc:
            raise HTTPException(status_code=503, detail=str(exc)) from exc

    @app.post("/api/v1/conversation")
    async def conversation(
        request: Request,
        body: ConversationRequest,
        x_anima_csrf: str | None = Header(default=None, alias="X-Anima-CSRF"),
    ) -> dict[str, Any]:
        session = current_session(request)
        require_mutation(request, x_anima_csrf, session)
        try:
            return svc.conversation.submit(svc.identity_from_session(session), body.text.strip())
        except UICommandError as exc:
            raise HTTPException(status_code=503, detail=str(exc)) from exc

    @app.get("/api/v1/conversation/{request_id}")
    async def conversation_result(request: Request, request_id: str) -> dict[str, Any]:
        try:
            return svc.conversation_result(current_identity(request), request_id)
        except UICommandError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @app.post("/api/v1/controls/{control_id}")
    async def control(
        control_id: str,
        request: Request,
        body: MutationRequest,
        x_anima_csrf: str | None = Header(default=None, alias="X-Anima-CSRF"),
    ) -> dict[str, Any]:
        session = current_session(request)
        require_mutation(request, x_anima_csrf, session)
        try:
            return svc.commands.control(
                svc.identity_from_session(session), control_id, body.payload
            )
        except UICommandError as exc:
            raise HTTPException(status_code=503, detail=str(exc)) from exc

    @app.post("/api/v1/approvals/{approval_id}")
    async def approval(
        approval_id: str,
        request: Request,
        body: MutationRequest,
        x_anima_csrf: str | None = Header(default=None, alias="X-Anima-CSRF"),
    ) -> dict[str, Any]:
        session = current_session(request)
        require_mutation(request, x_anima_csrf, session)
        if set(body.payload) != {"decision"} or str(body.payload["decision"]).upper() not in {
            "APPROVE",
            "REJECT",
        }:
            raise HTTPException(status_code=400, detail="INVALID_APPROVAL_DECISION")
        try:
            return svc.commands.confirmation(
                svc.identity_from_session(session),
                approval_id,
                str(body.payload["decision"]),
            )
        except UICommandError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc

    @app.get("/api/v1/events")
    async def events(request: Request) -> StreamingResponse:
        session = current_session(request)
        try:
            queue = svc.events.subscribe(session.session_id)
        except UIEventCapacityError as exc:
            raise HTTPException(
                status_code=429,
                detail="LIVE_UPDATE_CONNECTION_LIMIT",
                headers={"Retry-After": "15"},
            ) from exc

        def stream() -> Iterator[str]:
            try:
                yield ": connected\n\n"
                deadline = time.monotonic() + 15
                while time.monotonic() < deadline:
                    for name in svc.events.drain(queue):
                        yield f"event: {name}\ndata: {{}}\n\n"
                    time.sleep(0.05)
                yield "event: refresh.required\ndata: {}\n\n"
            finally:
                svc.events.unsubscribe(queue)

        return _UIEventStreamingResponse(stream(), svc.events, queue)

    static_dir = svc.config.static_dir
    if static_dir.is_dir():
        app.mount("/", StaticFiles(directory=static_dir, html=True), name="ui")
    return app


app = create_app()


def main() -> None:
    import uvicorn

    config = UIConfig.from_environment()
    # Typed Core audit remains enabled. Raw access logs would retain OAuth codes
    # from callback query strings, which are authentication secrets.
    uvicorn.run(
        "anima_ha.ui_api:app",
        host=config.bind_host,
        port=config.bind_port,
        reload=False,
        access_log=False,
    )
