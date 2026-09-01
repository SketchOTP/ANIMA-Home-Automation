"""Bounded local ANIMA interface API.

The browser speaks only to this module.  It receives semantic view models and
submits commands to injected Core gateways; it never receives provider tokens,
database rows, policy internals, or raw event payloads.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import os
import secrets
import time
from collections import deque
from collections.abc import Awaitable, Callable, Iterator
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any, Protocol
from uuid import UUID, uuid4

import psycopg
from aiohttp import ClientSession, ClientTimeout, WSMsgType
from fastapi import FastAPI, Header, HTTPException, Request, Response, status
from fastapi.responses import JSONResponse, RedirectResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from psycopg.rows import dict_row
from pydantic import BaseModel, Field

from anima_ha.events import DeliveryClass, EventEnvelope, EventImportance
from anima_ha.policy import Assurance, EvidenceType, IdentityEvidence, RequestOrigin

UI_VERSION = "0.1.0"
UI_SESSION_COOKIE = "anima_session"
SESSION_ABSOLUTE_TTL = timedelta(hours=8)
SESSION_IDLE_TTL = timedelta(minutes=30)
MAX_CONVERSATION_CHARS = 4_000
MAX_SSE_BUFFER = 64
DEFAULT_HOUSEHOLD_ID = UUID("00000000-0000-0000-0000-000000000012")
DEFAULT_PRINCIPAL_ID = UUID("00000000-0000-0000-0000-000000000013")


class UIAuthError(RuntimeError):
    """Raised when an ANIMA session cannot be established."""


class PrincipalMappingRequired(UIAuthError):
    """Raised when a Home Assistant user has no exact ANIMA mapping."""


class UICommandError(RuntimeError):
    """Raised when a UI command cannot be routed through Core."""


def _now() -> datetime:
    return datetime.now(UTC)


def _hash(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


@dataclass(frozen=True, slots=True)
class UIConfig:
    """Non-secret UI configuration."""

    environment: str = "development"
    bind_host: str = "127.0.0.1"
    bind_port: int = 8090
    static_dir: Path = Path("ui/dist")
    ha_base_url: str | None = None
    ha_client_id: str | None = None
    ha_redirect_uri: str | None = None
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
        return cls(
            environment=source.get("ANIMA_ENV", "development"),
            bind_host=source.get("ANIMA_UI_BIND", "127.0.0.1"),
            bind_port=port,
            static_dir=Path(source.get("ANIMA_UI_STATIC_DIR", "ui/dist")),
            ha_base_url=source.get("ANIMA_HA_BASE_URL") or None,
            ha_client_id=source.get("ANIMA_HA_OAUTH_CLIENT_ID") or None,
            ha_redirect_uri=source.get("ANIMA_HA_OAUTH_REDIRECT_URI") or None,
            test_auth_enabled=source.get("ANIMA_UI_TEST_AUTH", "0") == "1",
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

    def to_payload(self) -> dict[str, Any]:
        return {
            "display_name": "Household member",
            "assurance": Assurance.AUTHENTICATED.value,
            "evidence": EvidenceType.AUTHENTICATED_SESSION.value,
        }


class HouseholdReadModel(Protocol):
    def bootstrap(self, identity: UIIdentity) -> dict[str, Any]: ...

    def home(self, identity: UIIdentity) -> dict[str, Any]: ...

    def tasks(self, identity: UIIdentity) -> list[dict[str, Any]]: ...

    def calendar(self, identity: UIIdentity) -> list[dict[str, Any]]: ...

    def activity(self, identity: UIIdentity) -> list[dict[str, Any]]: ...

    def capabilities(self, identity: UIIdentity) -> list[dict[str, Any]]: ...


class UICommandGateway(Protocol):
    def task_mutation(
        self, identity: UIIdentity, operation: str, payload: dict[str, Any]
    ) -> dict[str, Any]: ...

    def calendar_mutation(
        self, identity: UIIdentity, operation: str, payload: dict[str, Any]
    ) -> dict[str, Any]: ...

    def control(
        self, identity: UIIdentity, control_id: str, payload: dict[str, Any]
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

    def control(
        self, identity: UIIdentity, control_id: str, payload: dict[str, Any]
    ) -> dict[str, Any]:
        return self._unavailable(f"control.{control_id}")


class ConversationIngress(Protocol):
    def submit(self, identity: UIIdentity, text: str) -> dict[str, Any]: ...


class ConversationPipeline(Protocol):
    def run(self, identity: UIIdentity, event: EventEnvelope) -> dict[str, Any]: ...


class UIEventBroadcaster:
    """Bounded invalidation-only event fanout."""

    def __init__(self) -> None:
        self._subscribers: list[deque[str]] = []

    def publish(self, name: str) -> None:
        if name not in {
            "home.invalidated",
            "tasks.changed",
            "calendar.changed",
            "activity.changed",
            "conversation.completed",
            "capabilities.changed",
        }:
            raise ValueError("unsafe UI event")
        for queue in tuple(self._subscribers):
            if len(queue) >= MAX_SSE_BUFFER:
                queue.clear()
                queue.append("refresh.required")
            else:
                queue.append(name)

    def subscribe(self) -> deque[str]:
        queue: deque[str] = deque(maxlen=MAX_SSE_BUFFER)
        self._subscribers.append(queue)
        return queue

    def unsubscribe(self, queue: deque[str]) -> None:
        try:
            self._subscribers.remove(queue)
        except ValueError:
            pass


class DemoHouseholdReadModel:
    """Safe deterministic fallback used by the local prototype and tests."""

    def __init__(self) -> None:
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
            }
        ]

    def bootstrap(self, identity: UIIdentity) -> dict[str, Any]:
        return {
            "identity": identity.to_payload(),
            "household": {"name": "Anima Home", "mode": "prototype"},
            "theme": {
                "appearance": "night",
                "accent": "ember",
                "density": "comfortable",
                "reduced_motion": False,
                "text_scale": "normal",
            },
            "layout": {
                "display_mode": "desktop",
                "visible_widgets": [
                    "status",
                    "presence",
                    "weather",
                    "agenda",
                    "tasks",
                    "conversation",
                    "activity",
                ],
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
            "calendar": self.calendar(identity)[:5],
            "tasks": self.tasks(identity)[:5],
            "controls": [],
            "activity": self.activity(identity)[:8],
            "voice": {"status": "UNAVAILABLE", "label": "Voice is planned for a later phase"},
        }

    def tasks(self, identity: UIIdentity) -> list[dict[str, Any]]:
        return [dict(item) for item in self._tasks]

    def calendar(self, identity: UIIdentity) -> list[dict[str, Any]]:
        return [dict(item) for item in self._calendar]

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


class PostgresHouseholdReadModel:
    """Normalized read façade over existing Core persistence tables."""

    def __init__(self, database_url: str, connect_timeout: int = 5) -> None:
        self.database_url = database_url
        self.connect_timeout = connect_timeout

    def _connect(self) -> psycopg.Connection[Any]:
        return psycopg.connect(
            self.database_url, connect_timeout=self.connect_timeout, row_factory=dict_row
        )

    def bootstrap(self, identity: UIIdentity) -> dict[str, Any]:
        return DemoHouseholdReadModel().bootstrap(identity)

    def tasks(self, identity: UIIdentity) -> list[dict[str, Any]]:
        with self._connect() as connection, connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT task_id, title, status, next_run_at
                FROM anima_durable_tasks
                WHERE household_id=%s
                ORDER BY next_run_at, task_id
                LIMIT 50
                """,
                (identity.household_id,),
            )
            rows = cursor.fetchall()
        return [
            {
                "task_id": str(row["task_id"]),
                "title": str(row["title"]),
                "status": str(row["status"]),
                "next_run_at": row["next_run_at"].isoformat(),
            }
            for row in rows
        ]

    def calendar(self, identity: UIIdentity) -> list[dict[str, Any]]:
        with self._connect() as connection, connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT event_id, title, start_at, end_at, status
                FROM anima_calendar_events
                WHERE household_id=%s
                ORDER BY start_at, event_id
                LIMIT 50
                """,
                (identity.household_id,),
            )
            rows = cursor.fetchall()
        return [
            {
                "event_id": str(row["event_id"]),
                "title": str(row["title"]),
                "start_at": row["start_at"].isoformat(),
                "end_at": row["end_at"].isoformat(),
                "status": str(row["status"]),
            }
            for row in rows
        ]

    def home(self, identity: UIIdentity) -> dict[str, Any]:
        demo = DemoHouseholdReadModel()
        result = demo.home(identity)
        result["tasks"] = self.tasks(identity)[:5]
        result["calendar"] = self.calendar(identity)[:5]
        result["activity"] = self.activity(identity)[:8]
        return result

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
        return DemoHouseholdReadModel().capabilities(identity)


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
            metadata={"principal_id": str(identity.principal_id), "ui_version": UI_VERSION},
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
            "request_id": request_id,
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
        if (
            not self.config.ha_base_url
            or not self.config.ha_client_id
            or not self.config.ha_redirect_uri
        ):
            raise UIAuthError("Home Assistant OAuth is not configured")
        from urllib.parse import urlencode

        params = {
            "client_id": self.config.ha_client_id,
            "redirect_uri": self.config.ha_redirect_uri,
            "state": state,
            "response_type": "code",
        }
        return f"{self.config.ha_base_url.rstrip('/')}/auth/authorize?{urlencode(params)}"

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


class UIService:
    def __init__(
        self,
        *,
        config: UIConfig | None = None,
        sessions: SessionStore | None = None,
        read_model: HouseholdReadModel | None = None,
        commands: UICommandGateway | None = None,
        conversation: ConversationIngress | None = None,
        ha_user_map: dict[str, tuple[UUID, UUID]] | None = None,
    ) -> None:
        self.config = config or UIConfig()
        self.sessions = sessions or InMemorySessionStore()
        self.events = UIEventBroadcaster()
        self.read_model = read_model or DemoHouseholdReadModel()
        self.commands = commands or UnavailableCommandGateway()
        self.conversation = conversation or JournalConversationIngress(
            events=self.events, fallback_enabled=self.config.test_auth_enabled
        )
        self.ha_user_map = ha_user_map or {
            "test-ha-user": (DEFAULT_HOUSEHOLD_ID, DEFAULT_PRINCIPAL_ID)
        }
        self.oauth = HomeAssistantOAuth(self.config)
        self._oauth_states: set[str] = set()

    def create_oauth_state(self) -> str:
        state = secrets.token_urlsafe(24)
        self._oauth_states.add(state)
        return state

    def consume_oauth_state(self, state: str) -> bool:
        if state not in self._oauth_states:
            return False
        self._oauth_states.remove(state)
        return True

    def map_ha_user(self, ha_user_id: str) -> UIIdentity:
        mapping = self.ha_user_map.get(ha_user_id)
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
        return UIIdentity(household_id, principal_id, ha_user_id, evidence)

    def issue_session(
        self, identity: UIIdentity, device_label: str | None = None
    ) -> tuple[str, str]:
        session_id = uuid4()
        secret = secrets.token_urlsafe(32)
        csrf = secrets.token_urlsafe(32)
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
        for ha_user_id, value in self.ha_user_map.items():
            if value == (record.household_id, record.principal_id):
                return self.map_ha_user(ha_user_id)
        raise UIAuthError("PRINCIPAL_MAPPING_REQUIRED")


class ConversationRequest(BaseModel):
    text: str = Field(min_length=1, max_length=MAX_CONVERSATION_CHARS)


class MutationRequest(BaseModel):
    payload: dict[str, Any] = Field(default_factory=dict)


def create_app(service: UIService | None = None) -> FastAPI:
    if service is None:
        config = UIConfig.from_environment()
        database_url = os.environ.get("ANIMA_DATABASE_URL", "").strip()
        sessions: SessionStore | None = (
            PostgresSessionStore(database_url) if database_url else InMemorySessionStore()
        )
        read_model: HouseholdReadModel | None = (
            PostgresHouseholdReadModel(database_url) if database_url else None
        )
        svc = UIService(config=config, sessions=sessions, read_model=read_model)
    else:
        svc = service
    app = FastAPI(title="ANIMA local interface", version=UI_VERSION, docs_url=None, redoc_url=None)
    app.state.ui_service = svc

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
        if not x_anima_csrf or not hmac.compare_digest(session.csrf_hash, _hash(x_anima_csrf)):
            raise HTTPException(status_code=403, detail="CSRF_REJECTED")

    @app.get("/healthz")
    async def healthz() -> dict[str, str]:
        return {"status": "ok", "service": "anima-ui", "version": UI_VERSION}

    @app.get("/auth/login")
    async def login() -> Response:
        state = svc.create_oauth_state()
        if svc.config.test_auth_enabled:
            return RedirectResponse(f"/auth/callback?code=anima-test-code&state={state}")
        try:
            return RedirectResponse(svc.oauth.authorization_url(state))
        except UIAuthError as exc:
            raise HTTPException(status_code=503, detail="HOME_ASSISTANT_OAUTH_UNAVAILABLE") from exc

    @app.get("/auth/callback")
    async def callback(code: str, state: str) -> Response:
        if not svc.consume_oauth_state(state):
            raise HTTPException(status_code=400, detail="OAUTH_STATE_REJECTED")
        if svc.config.test_auth_enabled and code == "anima-test-code":
            identity = svc.map_ha_user("test-ha-user")
            cookie, csrf = svc.issue_session(identity, "browser")
            response = RedirectResponse("/")
            response.set_cookie(
                UI_SESSION_COOKIE, cookie, httponly=True, samesite="strict", secure=False, path="/"
            )
            response.headers["X-Anima-CSRF"] = csrf
            return response
        try:
            ha_user_id = await svc.oauth.resolve_user_id(code)
            identity = svc.map_ha_user(ha_user_id)
        except UIAuthError as exc:
            raise HTTPException(status_code=502, detail=str(exc)) from exc
        cookie, csrf = svc.issue_session(identity, "browser")
        response = RedirectResponse("/")
        response.set_cookie(
            UI_SESSION_COOKIE, cookie, httponly=True, samesite="strict", secure=False, path="/"
        )
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
        csrf = secrets.token_urlsafe(32)
        svc.sessions.save(
            SessionRecord(
                session.session_id,
                session.secret_hash,
                session.household_id,
                session.principal_id,
                session.created_at,
                session.last_seen_at,
                session.expires_at,
                _hash(csrf),
                session.device_label,
                session.revoked_at,
            )
        )
        result = svc.read_model.bootstrap(identity)
        result["csrf_token"] = csrf
        return result

    @app.get("/api/v1/home")
    async def home(request: Request) -> dict[str, Any]:
        return svc.read_model.home(current_identity(request))

    @app.get("/api/v1/tasks")
    async def tasks(request: Request) -> dict[str, Any]:
        return {"items": svc.read_model.tasks(current_identity(request))}

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
                svc.identity_from_session(session), operation, {"task_id": task_id, **body.payload}
            )
        except UICommandError as exc:
            raise HTTPException(status_code=503, detail=str(exc)) from exc

    @app.get("/api/v1/calendar")
    async def calendar(request: Request) -> dict[str, Any]:
        return {"items": svc.read_model.calendar(current_identity(request))}

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
                svc.identity_from_session(session), "create", body.payload
            )
        except UICommandError as exc:
            raise HTTPException(status_code=503, detail=str(exc)) from exc

    @app.get("/api/v1/activity")
    async def activity(request: Request) -> dict[str, Any]:
        return {"items": svc.read_model.activity(current_identity(request))}

    @app.get("/api/v1/capabilities")
    async def capabilities(request: Request) -> dict[str, Any]:
        return {"items": svc.read_model.capabilities(current_identity(request))}

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

    @app.get("/api/v1/events")
    async def events(request: Request) -> StreamingResponse:
        current_session(request)
        queue = svc.events.subscribe()

        def stream() -> Iterator[str]:
            try:
                yield ": connected\n\n"
                deadline = time.monotonic() + 15
                while time.monotonic() < deadline:
                    while queue:
                        name = queue.popleft()
                        yield f"event: {name}\ndata: {{}}\n\n"
                    time.sleep(0.05)
                yield "event: refresh.required\ndata: {}\n\n"
            finally:
                svc.events.unsubscribe(queue)

        return StreamingResponse(
            stream(),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-store", "X-Accel-Buffering": "no"},
        )

    static_dir = svc.config.static_dir
    if static_dir.is_dir():
        app.mount("/", StaticFiles(directory=static_dir, html=True), name="ui")
    return app


app = create_app()


def main() -> None:
    import uvicorn

    config = UIConfig.from_environment()
    uvicorn.run("anima_ha.ui_api:app", host=config.bind_host, port=config.bind_port, reload=False)
