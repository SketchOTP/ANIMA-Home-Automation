"""Home Assistant provider adapter behind ANIMA-owned contracts.

Home Assistant identifiers remain scoped provider references.  This module
owns connection supervision, reconciliation, normalization, bounded semantic
actions, and provider-level verification; HA wire objects do not cross it.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass, field, replace
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any, Protocol, cast
from urllib.parse import urlsplit, urlunsplit
from uuid import NAMESPACE_URL, UUID, uuid4, uuid5

import psycopg
from aiohttp import ClientSession
from hass_client import HomeAssistantClient
from hass_client.exceptions import AuthenticationFailed
from psycopg.rows import dict_row

from anima_ha.events import (
    DeliveryClass,
    EventEnvelope,
    EventImportance,
    EvidenceKind,
    ObservationState,
    TruthObservation,
)
from anima_ha.graph import (
    CanonicalNode,
    CanonicalRelationship,
    CommissioningDocument,
    NodeKind,
    PostgresHouseholdGraph,
    ProviderReference,
    RelationshipType,
    TargetKind,
    TruthBinding,
)
from anima_ha.journal import PostgresRealityStore
from anima_ha.plugins import (
    CORE_VERSION,
    MANIFEST_VERSION,
    PluginManifest,
    PluginValidationError,
    ProviderExecutionContext,
    RuntimeKind,
    TrustClass,
)

LOGGER = logging.getLogger(__name__)
PROVIDER = "home_assistant"
EXPECTED_HA_VERSION = "2026.8.2"
HA_IMAGE = (
    "ghcr.io/home-assistant/home-assistant:2026.8.2@"
    "sha256:56690a89c79a0de98035e1719f8324a92d5859c1192ff45adb0230ea81cb42a5"
)


class HAAdapterError(RuntimeError):
    """Base exception for bounded adapter failures."""


class HAAuthenticationError(HAAdapterError):
    """Authentication failed and should not be retried aggressively."""


class HAMappingError(HAAdapterError):
    """A canonical target has no unambiguous commissioned HA mapping."""


class HAHealth(StrEnum):
    STARTING = "STARTING"
    CONNECTING = "CONNECTING"
    RECONCILING = "RECONCILING"
    ONLINE = "ONLINE"
    DEGRADED = "DEGRADED"
    OFFLINE = "OFFLINE"
    AUTH_FAILED = "AUTH_FAILED"


class MappingStatus(StrEnum):
    MAPPED = "MAPPED"
    UNMAPPED = "UNMAPPED"


class HAActionOutcome(StrEnum):
    SUCCESS = "SUCCESS"
    SERVICE_FAILED = "SERVICE_FAILED"
    VERIFICATION_FAILED = "VERIFICATION_FAILED"
    UNKNOWN_RESULT = "UNKNOWN_RESULT"
    TARGET_UNAVAILABLE = "TARGET_UNAVAILABLE"


def _utcnow() -> datetime:
    return datetime.now(UTC)


def _parse_time(value: Any, fallback: datetime | None = None) -> datetime:
    if isinstance(value, datetime):
        parsed = value
    elif value:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    else:
        parsed = fallback or _utcnow()
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def _json(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        return {}
    return cast(dict[str, Any], json.loads(json.dumps(value, default=str)))


def _bounded_attributes(value: Any) -> dict[str, Any]:
    attributes = _json(value)
    allowed = {
        "friendly_name",
        "unit_of_measurement",
        "device_class",
        "state_class",
        "icon",
        "supported_features",
    }
    return {key: attributes[key] for key in sorted(allowed & attributes.keys())}


@dataclass(frozen=True, slots=True)
class HAInstanceConfig:
    instance_id: UUID
    websocket_url: str
    token_secret_name: str
    expected_version: str = EXPECTED_HA_VERSION
    freshness_seconds: int = 300
    command_timeout: float = 10.0
    verification_timeout: float = 8.0
    reconnect_attempts: int = 3
    reconnect_backoff_seconds: float = 0.5
    healthcheck_seconds: float = 1.0
    ssl: bool = True

    def __post_init__(self) -> None:
        if not self.websocket_url.endswith("/api/websocket"):
            raise ValueError("websocket_url must end with /api/websocket")
        if not self.token_secret_name.strip():
            raise ValueError("token_secret_name is required")
        if self.reconnect_attempts not in range(1, 6):
            raise ValueError("reconnect_attempts must be between 1 and 5")

    @property
    def provider_scope(self) -> str:
        return str(self.instance_id)


@dataclass(frozen=True, slots=True)
class HAProviderObject:
    kind: str
    external_id: str
    metadata: dict[str, Any]
    mapping_status: MappingStatus = MappingStatus.UNMAPPED
    canonical_target_id: UUID | None = None


def inventory_handle(instance_id: UUID, object_kind: str, external_id: str) -> str:
    """Return a stable opaque reference for an ANIMA discovery item.

    The handle is only a lookup key.  Core resolves it back to the provider
    identifier inside the Home Assistant adapter; callers never need to see
    or choose the provider identifier itself.
    """

    return str(
        uuid5(
            NAMESPACE_URL,
            f"anima://home-assistant/{instance_id}/inventory/{object_kind}/{external_id}",
        )
    )


@dataclass(frozen=True, slots=True)
class HADiscoverySnapshot:
    version: str
    config: dict[str, Any]
    states: tuple[dict[str, Any], ...]
    services: dict[str, Any]
    areas: tuple[dict[str, Any], ...]
    devices: tuple[dict[str, Any], ...]
    entities: tuple[dict[str, Any], ...]


@dataclass(frozen=True, slots=True)
class HAAdapterStatus:
    health: HAHealth
    connected_version: str | None = None
    last_successful_state_sync: datetime | None = None
    last_received_event: datetime | None = None
    subscriptions_active: bool = False
    discovered_counts: dict[str, int] = field(default_factory=dict)
    mapped_count: int = 0
    unmapped_count: int = 0
    reconnect_attempt: int = 0
    last_error_category: str | None = None

    def to_payload(self) -> dict[str, Any]:
        return {
            "health": self.health.value,
            "connected_version": self.connected_version,
            "last_successful_state_sync": self.last_successful_state_sync.isoformat()
            if self.last_successful_state_sync
            else None,
            "last_received_event": self.last_received_event.isoformat()
            if self.last_received_event
            else None,
            "subscriptions_active": self.subscriptions_active,
            "discovered_counts": self.discovered_counts,
            "mapped_count": self.mapped_count,
            "unmapped_count": self.unmapped_count,
            "reconnect_attempt": self.reconnect_attempt,
            "last_error_category": self.last_error_category,
        }


@dataclass(frozen=True, slots=True)
class HAActionResult:
    outcome: HAActionOutcome
    entity_id: str
    requested_state: str
    observed_state: str | None = None
    service_acknowledged: bool = False
    detail: str | None = None

    def to_payload(self) -> dict[str, Any]:
        return {
            "outcome": self.outcome.value,
            "entity_id": self.entity_id,
            "requested_state": self.requested_state,
            "observed_state": self.observed_state,
            "service_acknowledged": self.service_acknowledged,
            "detail": self.detail,
        }


class HAConnection(Protocol):
    @property
    def version(self) -> str | None: ...

    @property
    def connected(self) -> bool: ...

    def start(self) -> HADiscoverySnapshot: ...
    def activate(self) -> list[dict[str, Any]]: ...
    def stop(self) -> None: ...
    def snapshot(self) -> HADiscoverySnapshot: ...
    def call_service(self, domain: str, service: str, target: dict[str, Any]) -> Any: ...
    def call_service_data(self, domain: str, service: str, data: dict[str, Any]) -> Any: ...
    def get_state(self, entity_id: str) -> dict[str, Any] | None: ...
    def ping(self) -> None: ...
    def start_config_flow(self, handler: str) -> dict[str, Any]: ...
    def continue_config_flow(self, flow_id: str, user_input: dict[str, Any]) -> dict[str, Any]: ...


class HassClientConnection:
    """Supervised synchronous boundary around the async hass-client SDK."""

    def __init__(
        self,
        config: HAInstanceConfig,
        token: str,
        *,
        event_callback: Callable[[dict[str, Any]], None],
        disconnect_callback: Callable[[str], None],
    ) -> None:
        self.config = config
        self._token = token
        self._event_callback = event_callback
        self._disconnect_callback = disconnect_callback
        self._loop = asyncio.new_event_loop()
        self._thread = threading.Thread(target=self._run_loop, daemon=True)
        self._client: HomeAssistantClient | None = None
        self._session: ClientSession | None = None
        self._listener: asyncio.Task[None] | None = None
        self._buffering = True
        self._buffer: list[dict[str, Any]] = []
        self._stopping = False
        self.version: str | None = None

    @property
    def connected(self) -> bool:
        return bool(self._client and self._client.connected)

    def _run_loop(self) -> None:
        asyncio.set_event_loop(self._loop)
        self._loop.run_forever()

    def _submit(self, coroutine: Any, timeout: float | None = None) -> Any:
        future = asyncio.run_coroutine_threadsafe(coroutine, self._loop)
        try:
            return future.result(timeout or self.config.command_timeout)
        except TimeoutError:
            future.cancel()
            raise

    async def _on_event(self, event: dict[str, Any]) -> None:
        normalized = _json(event)
        if self._buffering:
            self._buffer.append(normalized)
        else:
            self._event_callback(normalized)

    def _listener_done(self, task: asyncio.Task[None]) -> None:
        if self._stopping:
            return
        error = "ConnectionClosed"
        if not task.cancelled():
            try:
                exc = task.exception()
                if exc is not None:
                    error = type(exc).__name__
            except asyncio.CancelledError:
                return
        self._disconnect_callback(error)

    async def _start_async(self) -> HADiscoverySnapshot:
        self._session = ClientSession()
        self._client = HomeAssistantClient(
            self.config.websocket_url, self._token, aiohttp_session=self._session
        )
        try:
            await asyncio.wait_for(
                self._client.connect(ssl=self.config.ssl), self.config.command_timeout
            )
        except AuthenticationFailed as exc:
            raise HAAuthenticationError("Home Assistant authentication failed") from exc
        self.version = self._client.version
        self._listener = asyncio.create_task(self._client.start_listening())
        self._listener.add_done_callback(self._listener_done)
        await asyncio.sleep(0)
        await self._client.subscribe_events(self._on_event, "state_changed")
        for event_type in (
            "area_registry_updated",
            "device_registry_updated",
            "entity_registry_updated",
        ):
            await self._client.subscribe_events(self._on_event, event_type)
        return await self._snapshot_async()

    async def _snapshot_async(self) -> HADiscoverySnapshot:
        if self._client is None:
            raise HAAdapterError("Home Assistant client is not started")
        config, states, services, areas, devices, entities = await asyncio.gather(
            self._client.get_config(),
            self._client.get_states(),
            self._client.get_services(),
            self._client.get_area_registry(),
            self._client.get_device_registry(),
            self._client.get_entity_registry(),
        )
        return HADiscoverySnapshot(
            version=str(self._client.version),
            config=_json(config),
            states=tuple(_json(item) for item in states),
            services=_json(services),
            areas=tuple(_json(item) for item in areas),
            devices=tuple(_json(item) for item in devices),
            entities=tuple(_json(item) for item in entities),
        )

    async def _activate_async(self) -> list[dict[str, Any]]:
        buffered = list(self._buffer)
        self._buffer.clear()
        self._buffering = False
        return buffered

    async def _stop_async(self) -> None:
        self._stopping = True
        if self._client is not None and self._client.connected:
            try:
                await asyncio.wait_for(self._client.disconnect(), timeout=2.0)
            except TimeoutError:
                pass
        if self._listener and not self._listener.done():
            self._listener.cancel()
        if self._session is not None and not self._session.closed:
            await self._session.close()

    def start(self) -> HADiscoverySnapshot:
        self._thread.start()
        return cast(
            HADiscoverySnapshot,
            self._submit(self._start_async(), self.config.command_timeout * 3),
        )

    def activate(self) -> list[dict[str, Any]]:
        return cast(list[dict[str, Any]], self._submit(self._activate_async()))

    def stop(self) -> None:
        if self._thread.is_alive():
            try:
                self._submit(self._stop_async())
            finally:
                self._loop.call_soon_threadsafe(self._loop.stop)
                self._thread.join(timeout=self.config.command_timeout)
        self._token = ""

    def snapshot(self) -> HADiscoverySnapshot:
        return cast(
            HADiscoverySnapshot,
            self._submit(self._snapshot_async(), self.config.command_timeout * 3),
        )

    async def _call_service_async(self, domain: str, service: str, target: dict[str, Any]) -> Any:
        if self._client is None:
            raise HAAdapterError("Home Assistant client is not started")
        return await self._client.call_service(domain, service, target=target)

    def call_service(self, domain: str, service: str, target: dict[str, Any]) -> Any:
        return self._submit(
            self._call_service_async(domain, service, target), self.config.command_timeout
        )

    async def _call_service_data_async(
        self, domain: str, service: str, data: dict[str, Any]
    ) -> Any:
        if self._client is None:
            raise HAAdapterError("Home Assistant client is not started")
        return await self._client.call_service(domain, service, service_data=data)

    def call_service_data(self, domain: str, service: str, data: dict[str, Any]) -> Any:
        return self._submit(
            self._call_service_data_async(domain, service, data), self.config.command_timeout
        )

    def get_state(self, entity_id: str) -> dict[str, Any] | None:
        snapshot = self.snapshot()
        return next(
            (state for state in snapshot.states if state.get("entity_id") == entity_id), None
        )

    async def _ping_async(self) -> None:
        if self._client is None:
            raise HAAdapterError("Home Assistant client is not started")
        await self._client.get_config()

    def ping(self) -> None:
        self._submit(self._ping_async(), self.config.command_timeout)

    def _http_base_url(self) -> str:
        parsed = urlsplit(self.config.websocket_url)
        scheme = "https" if parsed.scheme == "wss" else "http"
        path = parsed.path.removesuffix("/api/websocket")
        return urlunsplit((scheme, parsed.netloc, path.rstrip("/"), "", ""))

    async def _post_config_flow_async(self, path: str, payload: dict[str, Any]) -> dict[str, Any]:
        if self._session is None or not self._token:
            raise HAAdapterError("Home Assistant config flow is unavailable")
        url = f"{self._http_base_url()}{path}"
        async with self._session.post(
            url,
            headers={"Authorization": f"Bearer {self._token}"},
            json=payload,
        ) as response:
            if response.status in {401, 403}:
                raise HAAuthenticationError("Home Assistant configuration authorization failed")
            if response.status != 200:
                raise HAAdapterError(
                    f"Home Assistant configuration flow failed ({response.status})"
                )
            body = await response.content.read(512 * 1024 + 1)
            if len(body) > 512 * 1024:
                raise HAAdapterError("Home Assistant configuration response is too large")
            try:
                value = json.loads(body.decode("utf-8"))
            except (UnicodeDecodeError, json.JSONDecodeError) as exc:
                raise HAAdapterError("Home Assistant configuration response is invalid") from exc
            if not isinstance(value, dict):
                raise HAAdapterError("Home Assistant configuration response is not an object")
            return cast(dict[str, Any], value)

    def start_config_flow(self, handler: str) -> dict[str, Any]:
        if handler != "zha":
            raise HAAdapterError("only the bounded ZHA setup flow is supported")
        return cast(
            dict[str, Any],
            self._submit(
                self._post_config_flow_async("/api/config/config_entries/flow", {"handler": "zha"}),
                self.config.command_timeout,
            ),
        )

    def continue_config_flow(self, flow_id: str, user_input: dict[str, Any]) -> dict[str, Any]:
        if not flow_id or len(flow_id) > 128:
            raise HAAdapterError("invalid Home Assistant configuration flow reference")
        return cast(
            dict[str, Any],
            self._submit(
                self._post_config_flow_async(
                    f"/api/config/config_entries/flow/{flow_id}",
                    {"user_input": user_input},
                ),
                self.config.command_timeout,
            ),
        )


class PostgresHAStore:
    def __init__(self, database_url: str, connect_timeout: int = 5) -> None:
        self.database_url = database_url
        self.connect_timeout = connect_timeout

    def _connect(self) -> psycopg.Connection[Any]:
        return psycopg.connect(
            self.database_url, connect_timeout=self.connect_timeout, row_factory=dict_row
        )

    def save_status(self, config: HAInstanceConfig, status: HAAdapterStatus, enabled: bool) -> None:
        payload = status.to_payload()
        with self._connect() as connection, connection.cursor() as cursor:
            cursor.execute(
                """INSERT INTO anima_ha_instances
                   (instance_id, websocket_url, token_secret_name, expected_version, enabled,
                    health, connected_version, last_state_sync, last_event_at, diagnostics)
                   VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s::jsonb)
                   ON CONFLICT (instance_id) DO UPDATE SET
                     websocket_url=EXCLUDED.websocket_url,
                     token_secret_name=EXCLUDED.token_secret_name,
                     expected_version=EXCLUDED.expected_version,
                     enabled=EXCLUDED.enabled,
                     health=EXCLUDED.health,
                     connected_version=EXCLUDED.connected_version,
                     last_state_sync=EXCLUDED.last_state_sync,
                     last_event_at=EXCLUDED.last_event_at,
                     diagnostics=EXCLUDED.diagnostics,
                     updated_at=now()""",
                (
                    config.instance_id,
                    config.websocket_url,
                    config.token_secret_name,
                    config.expected_version,
                    enabled,
                    status.health.value,
                    status.connected_version,
                    status.last_successful_state_sync,
                    status.last_received_event,
                    json.dumps(payload, sort_keys=True),
                ),
            )
            connection.commit()

    def replace_inventory(
        self, instance_id: UUID, objects: list[HAProviderObject], seen_at: datetime
    ) -> None:
        with self._connect() as connection, connection.cursor() as cursor:
            cursor.execute(
                "UPDATE anima_ha_provider_inventory SET present=false WHERE instance_id=%s",
                (instance_id,),
            )
            for item in objects:
                metadata = {
                    **item.metadata,
                    "mapping_status": item.mapping_status.value,
                    "canonical_target_id": str(item.canonical_target_id)
                    if item.canonical_target_id
                    else None,
                }
                cursor.execute(
                    """INSERT INTO anima_ha_provider_inventory
                       (instance_id, external_object_kind, external_id, metadata, present,
                        first_seen_at, last_seen_at)
                       VALUES (%s,%s,%s,%s::jsonb,true,%s,%s)
                       ON CONFLICT (instance_id, external_object_kind, external_id) DO UPDATE SET
                         metadata=EXCLUDED.metadata,
                         present=true,
                         last_seen_at=EXCLUDED.last_seen_at""",
                    (
                        instance_id,
                        item.kind,
                        item.external_id,
                        json.dumps(metadata, sort_keys=True),
                        seen_at,
                        seen_at,
                    ),
                )
            connection.commit()

    def inventory(self, instance_id: UUID) -> list[dict[str, Any]]:
        with self._connect() as connection, connection.cursor() as cursor:
            cursor.execute(
                """SELECT external_object_kind, external_id, metadata, present
                   FROM anima_ha_provider_inventory WHERE instance_id=%s
                   ORDER BY external_object_kind, external_id""",
                (instance_id,),
            )
            rows = [dict(row) for row in cursor.fetchall()]
        for row in rows:
            row["inventory_handle"] = inventory_handle(
                instance_id,
                str(row["external_object_kind"]),
                str(row["external_id"]),
            )
        return rows


class HomeAssistantAdapter:
    def __init__(
        self,
        config: HAInstanceConfig,
        reality: PostgresRealityStore,
        graph: PostgresHouseholdGraph,
        store: PostgresHAStore,
        *,
        normalized_event_callback: Callable[[EventEnvelope], Any] | None = None,
    ) -> None:
        self.config, self.reality, self.graph, self.store = config, reality, graph, store
        self._normalized_event_callback = normalized_event_callback
        self.connection: HAConnection | None = None
        self.status = HAAdapterStatus(HAHealth.STARTING)
        self._enabled = False
        self._transport_online = False
        self._lock = threading.RLock()
        self._reconcile_lock = threading.Lock()
        self._registry_worker_lock = threading.Lock()
        self._registry_dirty = threading.Event()
        self._monitor_stop = threading.Event()
        self._monitor_thread: threading.Thread | None = None

    def _start_monitor(self) -> None:
        self._monitor_stop.set()
        previous = self._monitor_thread
        if (
            previous is not None
            and previous.is_alive()
            and previous is not threading.current_thread()
        ):
            previous.join(timeout=self.config.command_timeout)
        self._monitor_stop = threading.Event()

        def monitor() -> None:
            while not self._monitor_stop.wait(self.config.healthcheck_seconds):
                connection = self.connection
                if not self._enabled or connection is None:
                    return
                try:
                    connection.ping()
                except Exception as exc:
                    self.disconnected(type(exc).__name__)
                    return

        self._monitor_thread = threading.Thread(target=monitor, daemon=True)
        self._monitor_thread.start()

    def _set_status(self, health: HAHealth, **changes: Any) -> None:
        self.status = replace(self.status, health=health, **changes)
        self.store.save_status(self.config, self.status, self._enabled)

    def _audit(self, event_type: str, payload: dict[str, Any], *, important: bool = True) -> None:
        now = _utcnow()
        self.reality.ingest(
            EventEnvelope.create(
                event_id=str(
                    uuid5(
                        NAMESPACE_URL, f"{self.config.instance_id}:{event_type}:{now.isoformat()}"
                    )
                ),
                event_type=event_type,
                source=f"provider:{PROVIDER}:{self.config.provider_scope}",
                subject_key=f"provider/{PROVIDER}/{self.config.provider_scope}",
                occurred_at=now,
                payload=payload,
                importance=EventImportance.IMPORTANT if important else EventImportance.NORMAL,
                delivery_class=DeliveryClass.GUARANTEED,
                metadata={"provider": PROVIDER, "provider_scope": self.config.provider_scope},
            ),
            project=False,
        )

    def _provider_object(self, kind: str, item: dict[str, Any]) -> HAProviderObject:
        key = {"area": "area_id", "device": "id", "entity": "entity_id"}[kind]
        external_id = str(item.get(key, ""))
        target = self.graph.resolve_provider_reference(
            PROVIDER, self.config.provider_scope, kind, external_id
        )
        metadata_keys = {
            "area": {"name", "floor_id", "aliases"},
            # HA 2026.8 uses singular config_entry_id/config_subentry_id and
            # HA 2026.9 may return child-device records with sparse fields.
            # Keep both the current shape and legacy data as bounded metadata;
            # canonical commissioning still derives authority from ANIMA.
            "device": {
                "name",
                "name_by_user",
                "area_id",
                "via_device_id",
                "parent_device_id",
                "config_entry_id",
                "config_subentry_id",
                "config_entries",
                "manufacturer",
                "model",
            },
            "entity": {"name", "original_name", "device_id", "area_id", "platform", "disabled_by"},
        }[kind]
        metadata = {key: item.get(key) for key in sorted(metadata_keys) if key in item}
        if kind == "device":
            # Older HA snapshots exposed config_entries as a list. Preserve a
            # deterministic singular projection when the new field is absent.
            entries = item.get("config_entries")
            if (
                "config_entry_id" not in metadata
                and isinstance(entries, list)
                and len(entries) == 1
            ):
                metadata["config_entry_id"] = entries[0]
            metadata["is_child_device"] = bool(item.get("parent_device_id"))
        return HAProviderObject(
            kind,
            external_id,
            _json(metadata),
            MappingStatus.MAPPED if target else MappingStatus.UNMAPPED,
            target.canonical_id if target else None,
        )

    def _inventory(self, snapshot: HADiscoverySnapshot) -> list[HAProviderObject]:
        return [
            *(self._provider_object("area", item) for item in snapshot.areas),
            *(self._provider_object("device", item) for item in snapshot.devices),
            *(self._provider_object("entity", item) for item in snapshot.entities),
        ]

    def _truth_key(self, entity_id: str) -> str:
        target = self.graph.resolve_provider_reference(
            PROVIDER, self.config.provider_scope, "entity", entity_id
        )
        if target is not None:
            return f"state/{target.kind.value.casefold()}/{target.canonical_id}/value"
        return f"provider/{PROVIDER}/{self.config.provider_scope}/entity/{entity_id}/state"

    def normalize_state_event(
        self, state: dict[str, Any], *, snapshot: bool = False
    ) -> EventEnvelope:
        """Normalize one provider state into the canonical Phase 1 event contract."""
        entity_id = str(state["entity_id"])
        raw_state = str(state.get("state", "unknown"))
        source_updated = str(state.get("last_updated") or state.get("last_changed") or "")
        digest_document = {
            "instance": self.config.provider_scope,
            "entity_id": entity_id,
            "state": raw_state,
            "last_updated": source_updated,
            "attributes": _bounded_attributes(state.get("attributes")),
        }
        digest = hashlib.sha256(
            json.dumps(digest_document, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest()
        received_at = _utcnow()
        observed_at = _parse_time(state.get("last_updated"), received_at)
        observation_state = {
            "unknown": ObservationState.UNKNOWN,
            "unavailable": ObservationState.UNAVAILABLE,
        }.get(raw_state.casefold(), ObservationState.KNOWN)
        observation = TruthObservation(
            truth_key=self._truth_key(entity_id),
            source=f"provider:{PROVIDER}:{self.config.provider_scope}:{entity_id}",
            observed_at=observed_at,
            received_at=received_at,
            state=observation_state,
            value=raw_state if observation_state == ObservationState.KNOWN else None,
            confidence=1.0,
            evidence_kind=(
                EvidenceKind.DIRECT
                if observation_state == ObservationState.KNOWN
                else EvidenceKind.UNKNOWN
                if observation_state == ObservationState.UNKNOWN
                else EvidenceKind.UNAVAILABLE
            ),
            freshness_seconds=self.config.freshness_seconds,
            metadata={
                "provider": PROVIDER,
                "provider_scope": self.config.provider_scope,
                "external_object_kind": "entity",
                "external_id": entity_id,
                "last_changed": state.get("last_changed"),
                "last_updated": state.get("last_updated"),
                "context_id": _json(state.get("context")).get("id"),
                "attributes": _bounded_attributes(state.get("attributes")),
                "snapshot": snapshot,
            },
        )
        return EventEnvelope.create(
            event_id=str(uuid5(NAMESPACE_URL, f"ha-state:{digest}")),
            event_type="truth.observation",
            source=f"provider:{PROVIDER}:{self.config.provider_scope}",
            source_event_id=f"state:{digest}",
            subject_key=f"provider/{PROVIDER}/{self.config.provider_scope}/entity/{entity_id}",
            occurred_at=observed_at,
            payload=observation.to_payload(),
            confidence=1.0,
            evidence_kind=observation.evidence_kind,
            metadata={
                "provider": PROVIDER,
                "provider_scope": self.config.provider_scope,
                "external_id": entity_id,
                "snapshot": snapshot,
            },
        )

    def _ingest_state(self, state: dict[str, Any], *, snapshot: bool) -> None:
        if not state.get("entity_id"):
            return
        event = self.normalize_state_event(state, snapshot=snapshot)
        self.reality.ingest(event)
        callback = self._normalized_event_callback
        if callback is not None and not snapshot:
            callback(event)

    def set_normalized_event_callback(
        self, callback: Callable[[EventEnvelope], Any] | None
    ) -> None:
        """Attach an ANIMA-owned consumer after Core composition is complete."""
        self._normalized_event_callback = callback

    def _apply_snapshot(self, snapshot: HADiscoverySnapshot) -> None:
        if snapshot.version != self.config.expected_version:
            raise HAAdapterError(
                f"Home Assistant version mismatch: expected={self.config.expected_version} "
                f"observed={snapshot.version}"
            )
        inventory = self._inventory(snapshot)
        synced_at = _utcnow()
        self.store.replace_inventory(self.config.instance_id, inventory, synced_at)
        for state in snapshot.states:
            self._ingest_state(state, snapshot=True)
        mapped = sum(item.mapping_status == MappingStatus.MAPPED for item in inventory)
        # A disconnect callback may run while a registry snapshot is being applied.
        # Never let that stale work hide the authoritative OFFLINE transition.
        if self._transport_online or self.status.health == HAHealth.CONNECTING:
            self._set_status(
                HAHealth.RECONCILING,
                connected_version=snapshot.version,
                last_successful_state_sync=synced_at,
                subscriptions_active=True,
                discovered_counts={
                    "states": len(snapshot.states),
                    "services": sum(
                        len(value)
                        for value in snapshot.services.values()
                        if isinstance(value, dict)
                    ),
                    "areas": len(snapshot.areas),
                    "devices": len(snapshot.devices),
                    "entities": len(snapshot.entities),
                },
                mapped_count=mapped,
                unmapped_count=len(inventory) - mapped,
                last_error_category=None,
            )

    def start(self, connection: HAConnection) -> None:
        with self._lock:
            self.connection = connection
            self._enabled = True
            self._transport_online = False
            self._set_status(HAHealth.CONNECTING)
            try:
                snapshot = connection.start()
                self._apply_snapshot(snapshot)
                self._transport_online = True
                buffered = connection.activate()
                for event in buffered:
                    self._handle_event(event)
                self._audit(
                    "home_assistant.reconciled",
                    {
                        "version": snapshot.version,
                        "buffered_events": len(buffered),
                        "missed_transitions_recovered": False,
                    },
                )
                self._set_status(HAHealth.ONLINE, reconnect_attempt=0)
                self._start_monitor()
            except HAAuthenticationError:
                self._transport_online = False
                self._set_status(HAHealth.AUTH_FAILED, last_error_category="AUTH_FAILED")
                raise
            except Exception as exc:
                self._transport_online = False
                self._set_status(HAHealth.OFFLINE, last_error_category=type(exc).__name__)
                raise

    def stop(self) -> None:
        with self._lock:
            self._enabled = False
            self._transport_online = False
            self._monitor_stop.set()
            self._registry_dirty.clear()
            if self.connection is not None:
                self.connection.stop()
            self._set_status(
                HAHealth.OFFLINE,
                subscriptions_active=False,
                last_error_category=None,
            )

    def disconnected(self, error_category: str) -> None:
        if not self._enabled:
            return
        if not self._transport_online and self.status.health == HAHealth.OFFLINE:
            return
        self._transport_online = False
        self._registry_dirty.clear()
        self._set_status(
            HAHealth.OFFLINE,
            subscriptions_active=False,
            last_error_category=error_category,
        )
        self._audit(
            "home_assistant.connection_gap_started",
            {"error_category": error_category, "missed_transitions": "UNKNOWN"},
        )

    def _handle_event(self, event: dict[str, Any]) -> None:
        if not self._enabled or not self._transport_online:
            return
        event_type = str(event.get("event_type", ""))
        now = _utcnow()
        if event_type == "state_changed":
            new_state = _json(_json(event.get("data")).get("new_state"))
            if new_state:
                self._ingest_state(new_state, snapshot=False)
        elif event_type in {
            "area_registry_updated",
            "device_registry_updated",
            "entity_registry_updated",
        }:
            self._audit(
                "home_assistant.registry_changed",
                {
                    "provider_event_type": event_type,
                    "action": _json(event.get("data")).get("action"),
                },
                important=False,
            )
            self._registry_dirty.set()
            threading.Thread(target=self._reconcile_registry_changes, daemon=True).start()
        connection = self.connection
        if self._transport_online and connection is not None and connection.connected:
            self._set_status(HAHealth.ONLINE, last_received_event=now)

    def _reconcile_registry_changes(self) -> None:
        """Coalesce bursts without dropping a change that arrives during reconciliation."""
        if not self._registry_worker_lock.acquire(blocking=False):
            return
        try:
            while self._registry_dirty.is_set():
                self._registry_dirty.clear()
                time.sleep(0.2)
                try:
                    self.reconcile()
                except Exception as exc:
                    if self._enabled and self.status.health != HAHealth.OFFLINE:
                        self._set_status(HAHealth.DEGRADED, last_error_category=type(exc).__name__)
                        self._audit(
                            "home_assistant.registry_reconciliation_failed",
                            {"error_category": type(exc).__name__},
                        )
        finally:
            self._registry_worker_lock.release()
            if self._registry_dirty.is_set():
                threading.Thread(target=self._reconcile_registry_changes, daemon=True).start()

    def receive_provider_event(self, event: dict[str, Any]) -> None:
        """Receive one validated transport event without exposing HA objects upstream."""
        self._handle_event(event)

    def reconcile(self) -> None:
        if not self._reconcile_lock.acquire(blocking=False):
            return
        try:
            connection = self.connection
            if connection is None or not connection.connected or not self._transport_online:
                raise HAAdapterError("Home Assistant is not connected")
            self._set_status(HAHealth.RECONCILING)
            snapshot = connection.snapshot()
            if (
                not self._enabled
                or not self._transport_online
                or connection is not self.connection
                or not connection.connected
            ):
                raise HAAdapterError("Home Assistant disconnected during reconciliation")
            self._apply_snapshot(snapshot)
            if (
                not self._enabled
                or not self._transport_online
                or connection is not self.connection
                or not connection.connected
            ):
                raise HAAdapterError("Home Assistant disconnected during reconciliation")
            self._audit(
                "home_assistant.reconciled",
                {
                    "version": snapshot.version,
                    "missed_transitions_recovered": False,
                    "historical_gap": "NOT_RECOVERABLE_FROM_CURRENT_STATE_SNAPSHOT",
                },
            )
            self._set_status(HAHealth.ONLINE)
        finally:
            self._reconcile_lock.release()

    def reconnect(self, connection_factory: Callable[[], HAConnection]) -> bool:
        self._monitor_stop.set()
        old = self.connection
        if old is not None:
            old.stop()
        for attempt in range(1, self.config.reconnect_attempts + 1):
            self._set_status(HAHealth.CONNECTING, reconnect_attempt=attempt)
            try:
                self.start(connection_factory())
                self._audit(
                    "home_assistant.connection_gap_closed",
                    {"attempt": attempt, "missed_transitions": "UNKNOWN"},
                )
                return True
            except HAAuthenticationError:
                return False
            except Exception:
                if attempt < self.config.reconnect_attempts:
                    time.sleep(min(self.config.reconnect_backoff_seconds * 2 ** (attempt - 1), 5.0))
        return False

    def provider_inventory(self) -> list[dict[str, Any]]:
        return self.store.inventory(self.config.instance_id)

    def resolve_device_handle(self, handle: str) -> str | None:
        """Resolve an ANIMA-owned discovery handle inside the provider boundary."""

        for item in self.provider_inventory():
            if item.get("external_object_kind") != "device":
                continue
            external_id = str(item.get("external_id", ""))
            if (
                external_id
                and inventory_handle(self.config.instance_id, "device", external_id) == handle
            ):
                return external_id
        return None

    def public_device_inventory(self) -> list[dict[str, Any]]:
        """Project discovery metadata without provider identifiers."""

        safe_keys = {
            "name",
            "name_by_user",
            "manufacturer",
            "model",
            "is_child_device",
            "mapping_status",
        }
        result: list[dict[str, Any]] = []
        for item in self.provider_inventory():
            if item.get("external_object_kind") != "device":
                continue
            external_id = str(item.get("external_id", ""))
            metadata = dict(item.get("metadata") or {})
            result.append(
                {
                    "external_object_kind": "device",
                    "device_handle": inventory_handle(
                        self.config.instance_id, "device", external_id
                    ),
                    "present": bool(item.get("present")),
                    "metadata": {
                        key: metadata[key] for key in sorted(safe_keys) if key in metadata
                    },
                }
            )
        return result

    def permit_zigbee_join(self, duration_seconds: int) -> dict[str, Any]:
        """Open a bounded ZHA pairing window through the configured HA instance."""
        duration = max(1, min(int(duration_seconds), 120))
        connection = self.connection
        if connection is None or not connection.connected:
            raise HAAdapterError("Home Assistant is offline")
        call_service_data = getattr(connection, "call_service_data", None)
        if not callable(call_service_data):
            raise HAAdapterError("Home Assistant transport cannot open a pairing window")
        call_service_data("zha", "permit", {"duration": duration})
        self._audit(
            "home_assistant.zigbee_pairing_requested",
            {"duration_seconds": duration},
        )
        return {
            "duration_seconds": duration,
            "provider": PROVIDER,
            "detail": "ZHA pairing window opened",
        }

    def _entity_for(self, resource_id: UUID, capability_id: UUID | None = None) -> str:
        references = []
        if capability_id is not None:
            references.extend(self.graph.provider_references_for(capability_id))
        if not any(
            item.provider == PROVIDER
            and item.provider_scope == self.config.provider_scope
            and item.external_object_kind == "entity"
            for item in references
        ):
            references.extend(self.graph.provider_references_for(resource_id))
        entity_ids = sorted(
            {
                item.external_id
                for item in references
                if item.provider == PROVIDER
                and item.provider_scope == self.config.provider_scope
                and item.external_object_kind == "entity"
            }
        )
        if len(entity_ids) != 1:
            raise HAMappingError(
                "canonical target requires exactly one commissioned Home Assistant entity mapping"
            )
        return entity_ids[0]

    def read_state(self, resource_id: UUID, capability_id: UUID | None = None) -> dict[str, Any]:
        entity_id = self._entity_for(resource_id, capability_id)
        if self.connection is None or not self.connection.connected:
            raise HAAdapterError("Home Assistant is offline")
        state = self.connection.get_state(entity_id)
        if state is None:
            raise HAAdapterError("mapped Home Assistant entity is absent")
        return {
            "entity_provider_reference": entity_id,
            "truth_key": self._truth_key(entity_id),
            "state": state.get("state"),
            "observed_at": state.get("last_updated"),
        }

    def set_power(
        self, resource_id: UUID, desired_on: bool, capability_id: UUID | None = None
    ) -> HAActionResult:
        entity_id = self._entity_for(resource_id, capability_id)
        domain = entity_id.split(".", 1)[0]
        if domain not in {"input_boolean", "light", "switch"}:
            raise HAMappingError("set_power supports only bounded low-risk power domains")
        requested = "on" if desired_on else "off"
        connection = self.connection
        if connection is None or not connection.connected:
            return HAActionResult(
                HAActionOutcome.UNKNOWN_RESULT, entity_id, requested, detail="adapter offline"
            )
        current = connection.get_state(entity_id)
        if current and str(current.get("state")).casefold() == "unavailable":
            return HAActionResult(
                HAActionOutcome.TARGET_UNAVAILABLE,
                entity_id,
                requested,
                observed_state="unavailable",
            )
        try:
            connection.call_service(
                domain, "turn_on" if desired_on else "turn_off", {"entity_id": entity_id}
            )
        except TimeoutError:
            return HAActionResult(
                HAActionOutcome.UNKNOWN_RESULT,
                entity_id,
                requested,
                service_acknowledged=False,
                detail="service call timed out",
            )
        except Exception as exc:
            return HAActionResult(
                HAActionOutcome.SERVICE_FAILED,
                entity_id,
                requested,
                detail=type(exc).__name__,
            )
        deadline = time.monotonic() + self.config.verification_timeout
        observed: str | None = None
        while time.monotonic() < deadline:
            state = connection.get_state(entity_id)
            observed = str(state.get("state")) if state else None
            if observed == requested:
                self._ingest_state(state or {}, snapshot=False)
                return HAActionResult(
                    HAActionOutcome.SUCCESS,
                    entity_id,
                    requested,
                    observed_state=observed,
                    service_acknowledged=True,
                )
            time.sleep(0.1)
        return HAActionResult(
            HAActionOutcome.VERIFICATION_FAILED,
            entity_id,
            requested,
            observed_state=observed,
            service_acknowledged=True,
            detail="provider state did not reach requested result",
        )


@dataclass(slots=True)
class _ZHASetupFlow:
    """Core-owned handle for one short-lived Home Assistant config flow."""

    ha_flow_id: str
    step_id: str
    allowed_values: dict[str, tuple[str, ...]] = field(default_factory=dict)


_ZHA_FLOW_STEPS = frozenset(
    {"choose_serial_port", "manual_pick_radio_type", "manual_port_config", "confirm"}
)
_ZHA_FIELDS = frozenset({"device_path", "radio_type", "baudrate", "flow_control"})
_ZHA_DEVICE_PREFIXES = ("/dev/serial/by-id/", "/dev/ttyUSB", "/dev/ttyACM", "socket://")


def _selector_options(field_schema: dict[str, Any]) -> tuple[str, ...]:
    selector = field_schema.get("selector")
    if not isinstance(selector, dict):
        return ()
    select = selector.get("select")
    if not isinstance(select, dict):
        return ()
    options = select.get("options")
    if not isinstance(options, list):
        return ()
    values: list[str] = []
    for option in options[:32]:
        value = option.get("value") if isinstance(option, dict) else option
        if isinstance(value, str) and value and len(value) <= 120:
            values.append(value)
    return tuple(dict.fromkeys(values))


def _safe_zha_fields(
    result: dict[str, Any],
) -> tuple[list[dict[str, Any]], dict[str, tuple[str, ...]]]:
    raw_schema = result.get("data_schema")
    if not isinstance(raw_schema, list):
        return [], {}
    fields: list[dict[str, Any]] = []
    allowed_values: dict[str, tuple[str, ...]] = {}
    for raw_field in raw_schema[:8]:
        if not isinstance(raw_field, dict):
            continue
        name = str(raw_field.get("name", ""))
        if name not in _ZHA_FIELDS:
            continue
        field_type = str(raw_field.get("type", "string"))
        descriptor: dict[str, Any] = {
            "name": name,
            "required": bool(raw_field.get("required", False)),
            "type": "integer" if field_type in {"integer", "number"} else "string",
        }
        options = _selector_options(raw_field)
        if options:
            descriptor["options"] = list(options)
            allowed_values[name] = options
        fields.append(descriptor)
    return fields, allowed_values


class HomeAssistantPlugin:
    """Trusted built-in plugin exposing only bounded semantic HA operations."""

    def __init__(
        self,
        adapter: HomeAssistantAdapter,
        connection_factory: Callable[[str], HAConnection],
    ) -> None:
        self.adapter = adapter
        self.connection_factory = connection_factory
        self._token: str | None = None
        self._zha_flows: dict[str, _ZHASetupFlow] = {}
        self._zha_flows_lock = threading.RLock()
        self.started = False

    def start(self, secret_env: dict[str, str]) -> None:
        token = secret_env.get(self.adapter.config.token_secret_name)
        if not token:
            raise PluginValidationError("declared Home Assistant token is unavailable")
        self.adapter.start(self.connection_factory(token))
        self._token = token
        self.started = True

    def stop(self) -> None:
        self.adapter.stop()
        self._token = None
        self.started = False

    def list_tools(self) -> list[dict[str, Any]]:
        return [
            {"name": str(tool["name"]), "input_schema": dict(tool["input_schema"])}
            for tool in home_assistant_manifest(self.adapter.config).tools
        ]

    def safe_status(self) -> dict[str, Any]:
        """Return connection health without exposing endpoint or credentials."""
        return self.adapter.status.to_payload()

    @staticmethod
    def _safe_flow_reason(result: dict[str, Any]) -> str:
        reason = str(result.get("reason", "configuration_rejected"))
        known = {
            "single_instance_allowed",
            "already_configured",
            "cannot_connect",
            "usb_probe_failed",
            "wrong_firmware_installed",
            "aborted",
        }
        return reason.upper() if reason in known else "CONFIGURATION_REJECTED"

    def _project_zha_flow(self, setup_id: str, result: dict[str, Any]) -> dict[str, Any]:
        result_type = str(result.get("type", ""))
        if result_type == "create_entry":
            with self._zha_flows_lock:
                self._zha_flows.pop(setup_id, None)
            try:
                self.adapter.reconcile()
            except HAAdapterError:
                # The config entry was created successfully.  Surface that
                # success while preserving the adapter's current health.
                pass
            return {
                "status": "SUCCEEDED",
                "operation": "configure_zha",
                "setup_id": setup_id,
                "state": "CONFIGURED",
                "health": self.safe_status(),
            }
        if result_type == "abort":
            with self._zha_flows_lock:
                self._zha_flows.pop(setup_id, None)
            return {
                "status": "FAILED",
                "operation": "configure_zha",
                "setup_id": setup_id,
                "state": "ABORTED",
                "reason": self._safe_flow_reason(result),
            }
        step_id = str(result.get("step_id", ""))
        if result_type != "form" or step_id not in _ZHA_FLOW_STEPS:
            with self._zha_flows_lock:
                self._zha_flows.pop(setup_id, None)
            return {
                "status": "FAILED",
                "operation": "configure_zha",
                "setup_id": setup_id,
                "state": "UNSUPPORTED_STEP",
                "reason": "UNSUPPORTED_ZHA_CONFIGURATION_STEP",
            }
        fields, allowed_values = _safe_zha_fields(result)
        with self._zha_flows_lock:
            flow = self._zha_flows.get(setup_id)
            if flow is not None:
                flow.step_id = step_id
                flow.allowed_values = allowed_values
        return {
            "status": "IN_PROGRESS",
            "operation": "configure_zha",
            "setup_id": setup_id,
            "state": "AWAITING_INPUT",
            "step_id": step_id,
            "fields": fields,
        }

    def _start_zha_setup(self) -> dict[str, Any]:
        connection = self.adapter.connection
        start = getattr(connection, "start_config_flow", None)
        if connection is None or not connection.connected or not callable(start):
            raise PluginValidationError("Home Assistant ZHA setup is unavailable")
        result = start("zha")
        setup_id = str(uuid4())
        with self._zha_flows_lock:
            self._zha_flows[setup_id] = _ZHASetupFlow(str(result.get("flow_id", "")), "")
        if not self._zha_flows[setup_id].ha_flow_id:
            with self._zha_flows_lock:
                self._zha_flows.pop(setup_id, None)
            raise PluginValidationError("Home Assistant returned no configuration flow reference")
        return self._project_zha_flow(setup_id, result)

    @staticmethod
    def _validate_zha_input(flow: _ZHASetupFlow, user_input: Any) -> dict[str, Any]:
        if not isinstance(user_input, dict):
            raise PluginValidationError("ZHA setup input must be an object")
        if flow.step_id == "confirm" and user_input:
            raise PluginValidationError("ZHA confirmation does not accept fields")
        if not set(user_input).issubset(_ZHA_FIELDS):
            raise PluginValidationError("unsupported ZHA setup field")
        values = dict(user_input)
        if "device_path" in values:
            path = str(values["device_path"])
            if len(path) > 256 or not path.startswith(_ZHA_DEVICE_PREFIXES):
                raise PluginValidationError(
                    "ZHA device path is outside the supported serial boundary"
                )
            values["device_path"] = path
        if "radio_type" in values:
            radio_type = str(values["radio_type"])
            if (
                flow.allowed_values.get("radio_type")
                and radio_type not in flow.allowed_values["radio_type"]
            ):
                raise PluginValidationError("radio type is not offered by Home Assistant")
            values["radio_type"] = radio_type
        if "baudrate" in values:
            try:
                baudrate = int(values["baudrate"])
            except (TypeError, ValueError) as exc:
                raise PluginValidationError("ZHA baud rate must be an integer") from exc
            if baudrate not in {9600, 19200, 38400, 57600, 115200, 230400, 460800}:
                raise PluginValidationError("unsupported ZHA baud rate")
            values["baudrate"] = baudrate
        if "flow_control" in values and str(values["flow_control"]) not in {
            "none",
            "software",
            "hardware",
        }:
            raise PluginValidationError("unsupported ZHA flow control mode")
        return values

    def _continue_zha_setup(self, setup_id: str, user_input: Any) -> dict[str, Any]:
        with self._zha_flows_lock:
            flow = self._zha_flows.get(setup_id)
        if flow is None or not flow.ha_flow_id or flow.step_id not in _ZHA_FLOW_STEPS:
            raise PluginValidationError("ZHA setup flow is missing or expired")
        values = self._validate_zha_input(flow, user_input)
        connection = self.adapter.connection
        continue_flow = getattr(connection, "continue_config_flow", None)
        if connection is None or not connection.connected or not callable(continue_flow):
            raise PluginValidationError("Home Assistant ZHA setup is unavailable")
        return self._project_zha_flow(setup_id, continue_flow(flow.ha_flow_id, values))

    def _resource_in_household(self, household_id: UUID, resource_id: UUID) -> CanonicalNode:
        resource = self.adapter.graph.get_node(resource_id)
        if resource is None or resource.kind not in {NodeKind.RESOURCE, NodeKind.SENSOR}:
            raise PluginValidationError("commissioned device resource is unavailable")
        if not any(
            item.canonical_id == resource_id
            for place in self.adapter.graph.places_in_household(household_id)
            for item in self.adapter.graph.resources_in_place(place.canonical_id)
        ):
            raise PluginValidationError("device is not in the commissioned household")
        return resource

    def _place_in_household(self, household_id: UUID, place_id: UUID) -> None:
        if not any(
            item.canonical_id == place_id
            for item in self.adapter.graph.places_in_household(household_id)
        ):
            raise PluginValidationError("destination is not in the commissioned household")

    def invoke_for_household(
        self, name: str, arguments: dict[str, Any], timeout: float, household_id: UUID
    ) -> Any:
        if name == "reconnect":
            del arguments, timeout, household_id
            token = self._token
            if not token:
                raise PluginValidationError("Home Assistant provider is not started")
            recovered = self.adapter.reconnect(lambda: self.connection_factory(token))
            self.started = recovered
            return {
                "status": "SUCCEEDED" if recovered else "FAILED",
                "health": self.safe_status(),
                "operation": "reconnect_home_assistant",
            }
        if name == "start_zha_setup":
            del arguments, timeout, household_id
            return self._start_zha_setup()
        if name == "continue_zha_setup":
            del timeout, household_id
            return self._continue_zha_setup(
                str(arguments.get("setup_id", "")), arguments.get("user_input", {})
            )
        if name == "refresh_inventory":
            self.adapter.reconcile()
            return {
                "provider": PROVIDER,
                "household_id": str(household_id),
                "items": self.adapter.public_device_inventory(),
            }
        if name == "permit_zigbee_join":
            return self.adapter.permit_zigbee_join(int(arguments["duration_seconds"]))
        if name == "commission_device":
            device_handle = str(arguments["device_handle"])
            device_id = self.adapter.resolve_device_handle(device_handle)
            if device_id is None:
                raise PluginValidationError(
                    "discovered Home Assistant device handle is unavailable"
                )
            return self._commission_device(
                household_id,
                device_id,
                str(arguments["name"]),
                UUID(str(arguments["place_id"])),
                device_handle,
            )
        if name == "rename_device":
            resource_id = UUID(str(arguments["resource_id"]))
            resource = self._resource_in_household(household_id, resource_id)
            new_name = str(arguments["name"]).strip()
            if not new_name or len(new_name) > 120:
                raise PluginValidationError("device name must be 1-120 characters")
            self.adapter.graph.rename_node(resource.canonical_id, new_name)
            return {
                "resource_id": str(resource.canonical_id),
                "name": new_name,
                "operation": "rename_device",
            }
        if name == "reassign_device":
            resource_id = UUID(str(arguments["resource_id"]))
            resource = self._resource_in_household(household_id, resource_id)
            place_id = UUID(str(arguments["place_id"]))
            self._place_in_household(household_id, place_id)
            self.adapter.graph.move_resource(resource.canonical_id, place_id)
            return {
                "resource_id": str(resource.canonical_id),
                "place_id": str(place_id),
                "operation": "reassign_device",
            }
        if name == "retire_device":
            resource_id = UUID(str(arguments["resource_id"]))
            resource = self._resource_in_household(household_id, resource_id)
            self.adapter.graph.retire_resource(resource.canonical_id)
            return {
                "resource_id": str(resource.canonical_id),
                "operation": "retire_device",
                "detail": (
                    "Device removed from ANIMA commissioning; Home Assistant registry unchanged"
                ),
            }
        return self.invoke(name, arguments, timeout)

    def _commission_device(
        self,
        household_id: UUID,
        device_id: str,
        name: str,
        place_id: UUID,
        device_handle: str,
    ) -> dict[str, Any]:
        """Map one discovered HA device into ANIMA's canonical graph.

        The browser can choose a display name and already-commissioned room,
        but it cannot supply provider hosts, arbitrary entity IDs, or graph
        relationships. Those are derived from the HA inventory and ANIMA's
        existing provider scope.
        """
        if not name.strip() or len(name.strip()) > 120:
            raise PluginValidationError("device name must be 1-120 characters")
        place = self.adapter.graph.get_node(place_id)
        household = self.adapter.graph.get_node(household_id)
        if household is None or household.kind != NodeKind.HOUSEHOLD:
            raise PluginValidationError("household is not commissioned")
        if place is None or place_id not in {
            item.canonical_id for item in self.adapter.graph.places_in_household(household_id)
        }:
            raise PluginValidationError("place is not in the commissioned household")
        inventory = self.adapter.provider_inventory()
        device = next(
            (
                item
                for item in inventory
                if item.get("external_object_kind") == "device"
                and str(item.get("external_id")) == device_id
                and bool(item.get("present"))
            ),
            None,
        )
        if device is None:
            raise PluginValidationError("discovered Home Assistant device is unavailable")
        entities = [
            item
            for item in inventory
            if item.get("external_object_kind") == "entity"
            and bool(item.get("present"))
            and str(dict(item.get("metadata") or {}).get("device_id", "")) == device_id
        ]
        resource_id = uuid5(
            NAMESPACE_URL,
            f"anima://home-assistant/{self.adapter.config.provider_scope}/device/{device_id}",
        )
        nodes: list[CanonicalNode] = [household, place]
        nodes.append(
            CanonicalNode(
                resource_id,
                NodeKind.RESOURCE
                if any(
                    str(item["external_id"]).split(".", 1)[0]
                    in {"input_boolean", "light", "switch"}
                    for item in entities
                )
                else NodeKind.SENSOR,
                name.strip(),
                metadata={
                    "provider": PROVIDER,
                    "provider_device_id": device_id,
                    "commissioned_by": "anima.ui",
                },
            )
        )
        relationships = [
            CanonicalRelationship(
                uuid5(NAMESPACE_URL, f"anima://home-assistant/{device_id}/installed-in/{place_id}"),
                RelationshipType.INSTALLED_IN,
                resource_id,
                place_id,
            )
        ]
        references = [
            ProviderReference(
                uuid5(
                    NAMESPACE_URL,
                    f"anima://home-assistant/{self.adapter.config.provider_scope}/device-ref/{device_id}",
                ),
                PROVIDER,
                self.adapter.config.provider_scope,
                "device",
                device_id,
                resource_id,
            )
        ]
        bindings: list[TruthBinding] = []
        capabilities = 0
        for item in entities:
            entity_id = str(item["external_id"])
            capability_id = uuid5(
                NAMESPACE_URL,
                f"anima://home-assistant/{self.adapter.config.provider_scope}/entity-capability/{entity_id}",
            )
            domain = entity_id.split(".", 1)[0]
            writable = domain in {"input_boolean", "light", "switch"}
            capability_type = "power.set" if writable else "state.read"
            nodes.append(
                CanonicalNode(
                    capability_id,
                    NodeKind.CAPABILITY,
                    f"{name.strip()} {domain} capability",
                    metadata={
                        "capability_type": capability_type,
                        "readable": True,
                        "writable": writable,
                        "provider_entity_id": entity_id,
                    },
                )
            )
            relationships.append(
                CanonicalRelationship(
                    uuid5(
                        NAMESPACE_URL, f"anima://home-assistant/{entity_id}/exposes/{resource_id}"
                    ),
                    RelationshipType.EXPOSES,
                    resource_id,
                    capability_id,
                )
            )
            references.append(
                ProviderReference(
                    uuid5(
                        NAMESPACE_URL,
                        f"anima://home-assistant/{self.adapter.config.provider_scope}/entity-ref/{entity_id}",
                    ),
                    PROVIDER,
                    self.adapter.config.provider_scope,
                    "entity",
                    entity_id,
                    capability_id,
                    TargetKind.CAPABILITY,
                )
            )
            bindings.append(
                TruthBinding(
                    uuid5(
                        NAMESPACE_URL, f"anima://home-assistant/{entity_id}/truth/{capability_id}"
                    ),
                    capability_id,
                    TargetKind.CAPABILITY,
                    f"state/capability/{capability_id}/value",
                    "power.state" if writable else "state",
                )
            )
            capabilities += int(writable)
        result = self.adapter.graph.commission(
            CommissioningDocument(
                1,
                tuple(nodes),
                tuple(relationships),
                provider_references=tuple(references),
                truth_bindings=tuple(bindings),
            )
        )
        self.adapter.reconcile()
        return {
            "resource_id": str(resource_id),
            "device_handle": device_handle,
            "place_id": str(place_id),
            "entity_count": len(entities),
            "power_capability_count": capabilities,
            "commission": {
                "created_nodes": result.created_nodes,
                "created_relationships": result.created_relationships,
                "created_provider_references": result.created_provider_references,
            },
        }

    def invoke(
        self,
        name: str,
        arguments: dict[str, Any],
        timeout: float,
        execution_context: ProviderExecutionContext | None = None,
    ) -> Any:
        del timeout, execution_context
        if name == "refresh_inventory":
            self.adapter.reconcile()
            return {"provider": PROVIDER, "items": self.adapter.provider_inventory()}
        if name == "permit_zigbee_join":
            return self.adapter.permit_zigbee_join(int(arguments["duration_seconds"]))
        resource_id = UUID(str(arguments["resource_id"]))
        capability = arguments.get("capability_id")
        capability_id = UUID(str(capability)) if capability else None
        if name == "read_state":
            return self.adapter.read_state(resource_id, capability_id)
        if name == "set_power":
            return self.adapter.set_power(
                resource_id, bool(arguments["desired_on"]), capability_id
            ).to_payload()
        raise PluginValidationError("unknown Home Assistant semantic tool")


def home_assistant_manifest(config: HAInstanceConfig) -> PluginManifest:
    id_schema = {"type": "string", "format": "uuid"}
    refresh_schema: dict[str, Any] = {
        "type": "object",
        "properties": {},
        "additionalProperties": False,
    }
    reconnect_schema: dict[str, Any] = {
        "type": "object",
        "properties": {},
        "additionalProperties": False,
    }
    start_zha_setup_schema: dict[str, Any] = {
        "type": "object",
        "properties": {},
        "additionalProperties": False,
    }
    continue_zha_setup_schema: dict[str, Any] = {
        "type": "object",
        "required": ["setup_id", "user_input"],
        "properties": {
            "setup_id": id_schema,
            "user_input": {
                "type": "object",
                "properties": {
                    "device_path": {"type": "string", "minLength": 1, "maxLength": 256},
                    "radio_type": {"type": "string", "minLength": 1, "maxLength": 120},
                    "baudrate": {"type": "integer", "minimum": 9600, "maximum": 460800},
                    "flow_control": {
                        "type": "string",
                        "enum": ["none", "software", "hardware"],
                    },
                },
                "additionalProperties": False,
            },
        },
        "additionalProperties": False,
    }
    permit_schema: dict[str, Any] = {
        "type": "object",
        "required": ["duration_seconds"],
        "properties": {"duration_seconds": {"type": "integer", "minimum": 1, "maximum": 120}},
        "additionalProperties": False,
    }
    commission_schema: dict[str, Any] = {
        "type": "object",
        "required": ["device_handle", "name", "place_id"],
        "properties": {
            "device_handle": id_schema,
            "name": {"type": "string", "minLength": 1, "maxLength": 120},
            "place_id": id_schema,
        },
        "additionalProperties": False,
    }
    rename_schema: dict[str, Any] = {
        "type": "object",
        "required": ["resource_id", "name"],
        "properties": {
            "resource_id": id_schema,
            "name": {"type": "string", "minLength": 1, "maxLength": 120},
        },
        "additionalProperties": False,
    }
    reassign_schema: dict[str, Any] = {
        "type": "object",
        "required": ["resource_id", "place_id"],
        "properties": {"resource_id": id_schema, "place_id": id_schema},
        "additionalProperties": False,
    }
    retire_schema: dict[str, Any] = {
        "type": "object",
        "required": ["resource_id"],
        "properties": {"resource_id": id_schema},
        "additionalProperties": False,
    }
    common: dict[str, Any] = {
        "type": "object",
        "required": ["resource_id"],
        "properties": {"resource_id": id_schema, "capability_id": id_schema},
        "additionalProperties": False,
    }
    set_power_schema = {
        **common,
        "required": ["resource_id", "desired_on"],
        "properties": {**common["properties"], "desired_on": {"type": "boolean"}},
    }
    return PluginManifest(
        plugin_id="anima.provider.home-assistant",
        plugin_version="0.1.0",
        manifest_version=MANIFEST_VERSION,
        requires_core=CORE_VERSION,
        name="Home Assistant provider",
        description="Bounded Home Assistant household substrate adapter",
        runtime_kind=RuntimeKind.TRUSTED_NATIVE,
        trust_class=TrustClass.TRUSTED_NATIVE,
        capabilities=("home.state", "home.control", "home.discovery", "home.commissioning"),
        tools=(
            {
                "name": "refresh_inventory",
                "description": "Refresh the discovered Home Assistant device inventory",
                "input_schema": refresh_schema,
                "output_schema": {"type": "object"},
                "semantic_action": "refresh_home_assistant",
                "risk_class": "READ_ONLY",
                "read_only": True,
                "idempotency": "IDEMPOTENT",
                "external_content_trust": "PLUGIN_TRUSTED",
            },
            {
                "name": "reconnect",
                "description": "Reconnect the configured Home Assistant instance and reconcile it",
                "input_schema": reconnect_schema,
                "output_schema": {"type": "object"},
                "semantic_action": "recover_home_assistant",
                "risk_class": "LOW_RISK_HOME_CONTROL",
                "read_only": False,
                "idempotency": "IDEMPOTENT",
                "external_content_trust": "PLUGIN_TRUSTED",
            },
            {
                "name": "start_zha_setup",
                "description": "Start the supported Home Assistant ZHA setup flow",
                "input_schema": start_zha_setup_schema,
                "output_schema": {"type": "object"},
                "semantic_action": "configure_zha",
                "risk_class": "SECURITY_SECURE_ACTION",
                "read_only": False,
                "idempotency": "NONE",
                "external_content_trust": "PLUGIN_TRUSTED",
            },
            {
                "name": "continue_zha_setup",
                "description": "Continue the server-owned supported ZHA setup flow",
                "input_schema": continue_zha_setup_schema,
                "output_schema": {"type": "object"},
                "semantic_action": "configure_zha",
                "risk_class": "SECURITY_SECURE_ACTION",
                "read_only": False,
                "idempotency": "NONE",
                "external_content_trust": "PLUGIN_TRUSTED",
            },
            {
                "name": "permit_zigbee_join",
                "description": "Open a short, bounded ZHA pairing window",
                "input_schema": permit_schema,
                "output_schema": {"type": "object"},
                "semantic_action": "permit_zigbee_join",
                "risk_class": "LOW_RISK_HOME_CONTROL",
                "read_only": False,
                "idempotency": "IDEMPOTENT",
                "external_content_trust": "PLUGIN_TRUSTED",
            },
            {
                "name": "commission_device",
                "description": (
                    "Commission one discovered Home Assistant device into the household graph"
                ),
                "input_schema": commission_schema,
                "output_schema": {"type": "object"},
                "semantic_action": "commission_home_device",
                "risk_class": "LOW_RISK_HOME_CONTROL",
                "read_only": False,
                "idempotency": "IDEMPOTENT",
                "external_content_trust": "PLUGIN_TRUSTED",
            },
            {
                "name": "rename_device",
                "description": "Rename a commissioned ANIMA device while preserving its old alias",
                "input_schema": rename_schema,
                "output_schema": {"type": "object"},
                "semantic_action": "rename_home_device",
                "risk_class": "LOW_RISK_HOME_CONTROL",
                "read_only": False,
                "idempotency": "IDEMPOTENT",
                "external_content_trust": "PLUGIN_TRUSTED",
            },
            {
                "name": "reassign_device",
                "description": "Move a commissioned ANIMA device to another household room or zone",
                "input_schema": reassign_schema,
                "output_schema": {"type": "object"},
                "semantic_action": "reassign_home_device",
                "risk_class": "LOW_RISK_HOME_CONTROL",
                "read_only": False,
                "idempotency": "IDEMPOTENT",
                "external_content_trust": "PLUGIN_TRUSTED",
            },
            {
                "name": "retire_device",
                "description": (
                    "Remove a device from ANIMA commissioning without changing Home Assistant"
                ),
                "input_schema": retire_schema,
                "output_schema": {"type": "object"},
                "semantic_action": "retire_home_device",
                "risk_class": "LOW_RISK_HOME_CONTROL",
                "read_only": False,
                "idempotency": "IDEMPOTENT",
                "external_content_trust": "PLUGIN_TRUSTED",
            },
            {
                "name": "read_state",
                "description": "Read a commissioned canonical household resource state",
                "input_schema": common,
                "output_schema": {"type": "object"},
                "semantic_action": "read_state",
                "risk_class": "READ_ONLY",
                "read_only": True,
                "idempotency": "IDEMPOTENT",
                "external_content_trust": "PLUGIN_TRUSTED",
            },
            {
                "name": "set_power",
                "description": "Set power on a commissioned low-risk household resource",
                "input_schema": set_power_schema,
                "output_schema": {"type": "object"},
                "semantic_action": "set_power",
                "risk_class": "LOW_RISK_HOME_CONTROL",
                "read_only": False,
                "idempotency": "IDEMPOTENT",
                "verification_requirement": "PROVIDER_STATE_MATCH",
                "external_content_trust": "PLUGIN_TRUSTED",
                "execution_spec": {
                    "profile": "home_assistant.set_power",
                    "provider_idempotency_supported": False,
                },
            },
        ),
        configuration_schema={
            "type": "object",
            "required": ["instance_id", "websocket_url"],
            "properties": {
                "instance_id": id_schema,
                "websocket_url": {"type": "string"},
            },
            "additionalProperties": False,
        },
        required_secrets=(config.token_secret_name,),
        network_requirements=("specific_home_assistant_instance",),
        healthcheck={"kind": "adapter_state", "expected": "ONLINE"},
        timeouts={
            "startup": 30.0,
            "tool": max(config.command_timeout, config.verification_timeout),
        },
        restart_policy={
            "max_attempts": config.reconnect_attempts,
            "backoff_seconds": config.reconnect_backoff_seconds,
        },
        source="builtin:anima_ha.home_assistant",
    )
