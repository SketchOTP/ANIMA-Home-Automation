"""Optional bounded vendor intake in the existing Core/FastAPI process.

Lead hook: install_vendor_event_api(app, current_identity, ingress_getter).
The getter returns a lazily composed VendorEventIngress using the current Core
journal/graph and ExactVendorAttention. No UI/SENTRY credential is accepted.
ANIMA_VENDOR_RELAY_CONFIG is an optional private JSON file, never a model input.
Real typed reports validate ANIMA's protocol, not a raw vendor notification.
Server-only producer qualification/version is required; wake defaults off.
Synthetic mode exists only as an explicit constructor seam for isolated tests.
Tapo HA cache observations use ingest_tapo_state, not the HTTP relay, and never
wake SENTRY automatically. No route writes Truth, graph, permissions or devices.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import os
import re
import stat
import threading
import time
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field, replace
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import UUID

from fastapi import FastAPI, HTTPException, Request
from starlette.concurrency import run_in_threadpool

from anima_ha.android_notifications import (
    TAPO_PACKAGE,
    WANSVIEW_PACKAGE,
    Disposition,
    RelayRegistration,
    Transport,
    normalize_notification,
    sanitize_relay_report,
)
from anima_ha.attention import AttentionProfile
from anima_ha.events import DeliveryClass, EventEnvelope
from anima_ha.graph import NodeKind, RelationshipType
from anima_ha.intelligence import SentryAttentionBridge
from anima_ha.tapo_events import TapoLockBinding, normalize_smartthings_ha_lock

MAX_BODY = 8192
MAX_CONFIG = 32768


class VendorIngressError(ValueError):
    """Static, non-sensitive error only."""


def _uuid(value: Any) -> UUID:
    try:
        result = UUID(value) if isinstance(value, str) else value
        if not isinstance(result, UUID) or result.int == 0:
            raise ValueError
        return result
    except (ValueError, TypeError, AttributeError):
        raise VendorIngressError("INVALID_CONFIGURATION") from None


@dataclass(frozen=True)
class VendorRelaySource:
    registration: RelayRegistration = field(repr=False)
    token: str = field(repr=False)
    enabled: bool = False
    official_app_ready: bool = False
    source_privacy_qualified: bool = False
    producer_adapter: str | None = None
    producer_version: str | None = None
    producer_qualified: bool = False
    wake_enabled: bool = False

    def __post_init__(self) -> None:
        if (
            not isinstance(self.token, str)
            or not 32 <= len(self.token) <= 256
            or not self.token.isascii()
            or any(character.isspace() for character in self.token)
            or any(
                type(value) is not bool
                for value in (
                    self.enabled,
                    self.official_app_ready,
                    self.source_privacy_qualified,
                    self.producer_qualified,
                    self.wake_enabled,
                )
            )
            or any(
                value is not None
                and (
                    not isinstance(value, str)
                    or re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,63}", value) is None
                )
                for value in (self.producer_adapter, self.producer_version)
            )
            or (self.producer_qualified and not (self.producer_adapter and self.producer_version))
            or (self.wake_enabled and not self.producer_qualified)
        ):
            raise VendorIngressError("INVALID_CONFIGURATION")


@dataclass(frozen=True)
class VendorRelayConfig:
    enabled: bool = False
    sources: tuple[VendorRelaySource, ...] = field(default=(), repr=False)

    def __post_init__(self) -> None:
        if type(self.enabled) is not bool or len(self.sources) > 16:
            raise VendorIngressError("INVALID_CONFIGURATION")
        identities = [source.registration.relay_id for source in self.sources]
        tokens = [source.token for source in self.sources]
        if len(set(identities)) != len(identities) or len(set(tokens)) != len(tokens):
            raise VendorIngressError("DUPLICATE_RELAY_CONFIGURATION")

    @classmethod
    def from_environment(cls, values: Mapping[str, str] | None = None) -> VendorRelayConfig:
        env = os.environ if values is None else values
        configured_path = env.get("ANIMA_VENDOR_RELAY_CONFIG", "").strip()
        if not configured_path:
            return cls()
        path = Path(configured_path)
        if not path.is_absolute() or ".." in path.parts:
            raise VendorIngressError("UNSAFE_CONFIGURATION_FILE")
        try:
            parent = os.open("/", os.O_RDONLY | os.O_DIRECTORY)
            try:
                for part in path.parts[1:-1]:
                    following = os.open(
                        part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=parent
                    )
                    os.close(parent)
                    parent = following
                descriptor = os.open(
                    path.name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=parent
                )
            finally:
                os.close(parent)
            try:
                info = os.fstat(descriptor)
                if (
                    not stat.S_ISREG(info.st_mode)
                    or info.st_nlink != 1
                    or stat.S_IMODE(info.st_mode) != 0o600
                    or info.st_uid not in {0, os.geteuid()}
                    or info.st_size > MAX_CONFIG
                ):
                    raise VendorIngressError("UNSAFE_CONFIGURATION_FILE")
                with os.fdopen(descriptor, "rb", closefd=False) as stream:
                    raw = stream.read(MAX_CONFIG + 1)
                if len(raw) > MAX_CONFIG:
                    raise VendorIngressError("INVALID_CONFIGURATION")
            finally:
                os.close(descriptor)
            data = json.loads(raw)
            if type(data) is not dict or set(data) != {"version", "enabled", "sources"}:
                raise ValueError
            if type(data["version"]) is not int or data["version"] != 1:
                raise ValueError
            if type(data["sources"]) is not list or len(data["sources"]) > 16:
                raise ValueError
            sources = []
            for item in data["sources"]:
                required = {
                    "household_id",
                    "relay_id",
                    "camera_mappings",
                    "allowed_channels",
                    "token",
                    "enabled",
                    "official_app_ready",
                    "source_privacy_qualified",
                }
                optional = {
                    "transport",
                    "package_name",
                    "producer_adapter",
                    "producer_version",
                    "producer_qualified",
                    "wake_enabled",
                }
                if type(item) is not dict or set(item) - optional != required:
                    raise ValueError
                if (
                    type(item["camera_mappings"]) is not dict
                    or type(item["allowed_channels"]) is not list
                ):
                    raise ValueError
                registration = RelayRegistration(
                    household_id=_uuid(item["household_id"]),
                    relay_id=_uuid(item["relay_id"]),
                    camera_mappings={
                        alias: _uuid(value) for alias, value in item["camera_mappings"].items()
                    },
                    allowed_channels=frozenset(item["allowed_channels"]),
                    allowed_packages=frozenset({str(item.get("package_name", WANSVIEW_PACKAGE))}),
                    transport=Transport(item.get("transport", Transport.ANDROID_LISTENER)),
                )
                sources.append(
                    VendorRelaySource(
                        registration,
                        item["token"],
                        item["enabled"],
                        item["official_app_ready"],
                        item["source_privacy_qualified"],
                        producer_adapter=item.get("producer_adapter"),
                        producer_version=item.get("producer_version"),
                        producer_qualified=item.get("producer_qualified", False),
                        wake_enabled=item.get("wake_enabled", False),
                    )
                )
            return cls(data["enabled"], tuple(sources))
        except (OSError, ValueError, TypeError, KeyError, UnicodeError, RecursionError):
            raise VendorIngressError("INVALID_CONFIGURATION") from None


def _mapped_resource(graph: Any, household: UUID, resource: UUID) -> bool:
    """Reuse active graph ownership, not relay names or reported principals."""
    node = graph.get_node(resource)
    if (
        node is None
        or node.retired_at is not None
        or node.kind not in {NodeKind.RESOURCE, NodeKind.SENSOR}
    ):
        return False
    if len(graph.related(resource, RelationshipType.INSTALLED_IN)) != 1:
        return False
    owners = {
        place.canonical_id
        for place in graph.list_places()
        if place.kind == NodeKind.HOUSEHOLD
        and any(
            item.canonical_id == resource for item in graph.resources_in_place(place.canonical_id)
        )
    }
    return owners == {household}


class ExactVendorAttention:
    """Only the accepted journal ID, never a broad guaranteed-event backlog."""

    def __init__(
        self, attention: Any, context: Any, store: Any, tools: Callable[[], list[Any]]
    ) -> None:
        self.attention, self.context, self.store, self.tools = attention, context, store, tools

    def __call__(self, event: EventEnvelope, position: int) -> list[Any]:
        if (
            position < 1
            or event.metadata.get("synthetic") is not False
            or event.metadata.get("wake_eligible") is not True
            or event.metadata.get("producer_qualified") is not True
            or event.metadata.get("schema_qualification") != "ANIMA_OWNED_SCHEMA"
            or not event.metadata.get("producer_adapter")
            or not event.metadata.get("producer_version")
            or event.metadata.get("external_content_trust") != "EXTERNAL_UNTRUSTED"
            or event.delivery_class != DeliveryClass.GUARANTEED
            or not event.source.startswith("android-relay-report:")
            or event.event_type
            not in {"external.android.motion_reported", "external.android.lock_reported"}
        ):
            raise VendorIngressError("EVENT_NOT_WAKE_ELIGIBLE")
        household = _uuid(event.metadata.get("household_id"))
        profile = AttentionProfile("phase13.vendor-notification.event.v1", ())
        consumer = f"vendor-event:{household}:{event.event_id}"
        self.attention.prime_consumer_before(profile, consumer, position - 1)
        return SentryAttentionBridge(
            attention=self.attention,
            context=self.context,
            store=self.store,
            profile=profile,
        ).run_once(
            household_id=household,
            tools=self.tools(),
            consumer_name=consumer,
            limit=1,
            source_event_id=event.event_id,
        )


class VendorEventIngress:
    def __init__(
        self,
        config: VendorRelayConfig,
        *,
        journal: Any,
        graph: Any,
        dispatch: Callable[[EventEnvelope, int], list[Any]] | None = None,
        synthetic_test_mode: bool = False,
        clock: Callable[[], datetime] = lambda: datetime.now(UTC),
    ) -> None:
        self.config, self.journal, self.graph, self.dispatch = config, journal, graph, dispatch
        self.synthetic_test_mode, self.clock = synthetic_test_mode, clock
        self._lock = threading.Lock()
        self._rates: dict[UUID, tuple[float, int]] = {}
        self._receipts: dict[UUID, str] = {}

    def status(self, household_id: UUID) -> dict[str, Any]:
        scoped = [
            item for item in self.config.sources if item.registration.household_id == household_id
        ]

        def vendor_row(vendor: str, package_name: str) -> dict[str, Any]:
            sources = [
                item for item in scoped if package_name in item.registration.allowed_packages
            ]
            gates: list[str] = []
            if not sources or not all(item.producer_qualified for item in sources):
                gates.append("PRODUCER_UNQUALIFIED")
            if self.synthetic_test_mode:
                gates.append("LIVE_FORMAT_UNQUALIFIED")
            if not sources or not all(item.official_app_ready for item in sources):
                gates.append("WAITING_APP_SETUP")
            if not sources or not all(item.source_privacy_qualified for item in sources):
                gates.append("SOURCE_PRIVACY_UNQUALIFIED")
            if not sources or not all(item.registration.camera_mappings for item in sources):
                gates.append("CANONICAL_MAPPING_REQUIRED")
            enabled = self.config.enabled and any(item.enabled for item in sources)
            if not enabled:
                gates.append("RELAY_DISABLED")
            if vendor == "tapo" and not sources:
                gates.extend(["HA_LOCK_MAPPING_REQUIRED", "SOURCE_SAMPLE_REQUIRED"])
            with self._lock:
                receipts = [
                    self._receipts[item.registration.relay_id]
                    for item in sources
                    if item.registration.relay_id in self._receipts
                ]
            return {
                "vendor": vendor,
                "configured": bool(sources),
                "enabled": enabled,
                "state": "WAITING_APP_SETUP" if gates else "RECEIVED" if receipts else "READY",
                "gates": gates,
                "last_receipt_at": max(receipts) if receipts else None,
            }

        vendors = [
            vendor_row("tapo", TAPO_PACKAGE),
            vendor_row("wansview", WANSVIEW_PACKAGE),
        ]
        gates: list[str] = []
        if not scoped or not all(item.producer_qualified for item in scoped):
            gates.append("PRODUCER_UNQUALIFIED")
        if self.synthetic_test_mode:
            gates.append("LIVE_FORMAT_UNQUALIFIED")
        if not scoped or not all(item.official_app_ready for item in scoped):
            gates.append("WAITING_APP_SETUP")
        if not scoped or not all(item.source_privacy_qualified for item in scoped):
            gates.append("SOURCE_PRIVACY_UNQUALIFIED")
        if not scoped or not all(item.registration.camera_mappings for item in scoped):
            gates.append("CANONICAL_MAPPING_REQUIRED")
        enabled = self.config.enabled and any(item.enabled for item in scoped)
        if not enabled:
            gates.append("RELAY_DISABLED")
        with self._lock:
            receipts = [
                self._receipts[item.registration.relay_id]
                for item in scoped
                if item.registration.relay_id in self._receipts
            ]
        return {
            "configured": bool(scoped),
            "enabled": enabled,
            "state": "WAITING_APP_SETUP" if gates else "RECEIVED" if receipts else "READY",
            "gates": gates,
            "last_receipt_at": max(receipts) if receipts else None,
            "vendors": vendors,
        }

    def authenticate_relay(self, authorization: str) -> VendorRelaySource:
        # Hash to equal-size bytes before constant-time comparison. Never log it.
        if not authorization.startswith("Bearer ") or len(authorization) > 263:
            raise HTTPException(401, "RELAY_AUTHENTICATION_REQUIRED")
        candidate = hashlib.sha256(authorization[7:].encode()).digest()
        import secrets

        match = None
        for source in self.config.sources:
            if secrets.compare_digest(candidate, hashlib.sha256(source.token.encode()).digest()):
                match = source
        if match is None:
            raise HTTPException(401, "RELAY_AUTHENTICATION_REQUIRED")
        if not self.config.enabled or not match.enabled:
            raise HTTPException(503, "RELAY_DISABLED")
        now = time.monotonic()
        with self._lock:
            start, count = self._rates.get(match.registration.relay_id, (now, 0))
            if now - start >= 60:
                start, count = now, 0
            if count >= 30:
                raise HTTPException(429, "RELAY_RATE_LIMIT", headers={"Retry-After": "60"})
            self._rates[match.registration.relay_id] = start, count + 1
        return match

    def receive(self, source: VendorRelaySource, body: dict[str, Any]) -> dict[str, Any]:
        if not self.config.enabled or not source.enabled or source not in self.config.sources:
            raise HTTPException(503, "RELAY_DISABLED")
        if not source.official_app_ready or not source.source_privacy_qualified:
            raise HTTPException(503, "SOURCE_SETUP_REQUIRED")
        if not self.synthetic_test_mode and not source.producer_qualified:
            raise HTTPException(503, "PRODUCER_UNQUALIFIED")
        if set(body) != {"package_name", "fields"} or type(body["package_name"]) is not str:
            raise HTTPException(400, "INVALID_NOTIFICATION")
        if self.synthetic_test_mode:
            result = normalize_notification(
                package_name=body["package_name"],
                load_fields=lambda: body["fields"],
                registration=source.registration,
                received_at=self.clock(),
                synthetic=True,
            )
            expected = Disposition.NORMALIZED_SYNTHETIC
        else:
            result = sanitize_relay_report(
                package_name=body["package_name"],
                load_fields=lambda: body["fields"],
                registration=source.registration,
                received_at=self.clock(),
            )
            expected = Disposition.NORMALIZED_REPORT
        if result.disposition != expected:
            raise HTTPException(422, str(result.disposition))
        event, receipt = result.event, result.receipt
        if event is None or receipt is None:
            raise HTTPException(422, "NOTIFICATION_NOT_ACCEPTED")
        resource = _uuid(event.payload.get("resource_id"))
        if not _mapped_resource(self.graph, source.registration.household_id, resource):
            raise HTTPException(409, "CANONICAL_MAPPING_REQUIRED")
        digest = receipt.content_digest
        if not self.synthetic_test_mode:
            event = replace(
                event,
                delivery_class=(
                    DeliveryClass.GUARANTEED if source.wake_enabled else DeliveryClass.BEST_EFFORT
                ),
                metadata={
                    **event.metadata,
                    "producer_adapter": source.producer_adapter,
                    "producer_version": source.producer_version,
                    "producer_qualified": source.producer_qualified,
                    "wake_eligible": source.wake_enabled,
                },
            )
            # Bind immutable identity to the configured producer, not merely the
            # relay-supplied UUID. Wake is persisted separately, never upgraded.
            digest = hashlib.sha256(
                json.dumps(
                    [
                        digest,
                        source.producer_adapter,
                        source.producer_version,
                        source.producer_qualified,
                    ],
                    separators=(",", ":"),
                ).encode()
            ).hexdigest()
        return self._record(event, digest, source.registration.relay_id)

    def _record(
        self, event: EventEnvelope, digest: str, relay_id: UUID | None = None
    ) -> dict[str, Any]:
        # Append is the existing atomic PostgreSQL unique-ID boundary. A duplicate
        # must match the persisted digest BEFORE retrying its exact handoff.
        event = replace(event, metadata={**event.metadata, "ingress_content_digest": digest})
        currently_eligible = event.metadata.get("wake_eligible") is True
        result = self.journal.append(event)
        if result.deduplicated:
            previous = self.journal.list_events(after_position=result.journal_position - 1, limit=1)
            if (
                len(previous) != 1
                or previous[0]["event_id"] != event.event_id
                or previous[0]["metadata"].get("ingress_content_digest") != digest
            ):
                raise HTTPException(409, "DELIVERY_ID_CONFLICT")
            if event.event_type == "tapo.lock_observed":
                # Compare after the atomic append outcome, not a bounded-prefix
                # preflight scan vulnerable to old IDs or concurrent writers.
                current_fields = {
                    key: value for key, value in event.payload.items() if key != "anima_received_at"
                }
                prior_fields = {
                    key: value
                    for key, value in previous[0]["payload"].items()
                    if key != "anima_received_at"
                }
                if current_fields != prior_fields:
                    raise HTTPException(409, "DELIVERY_ID_CONFLICT")
            # Persisted eligibility is the ceiling. Current configuration can
            # revoke dispatch, but cannot promote an earlier non-wake report.
            event = replace(
                event,
                metadata=previous[0]["metadata"],
                payload=previous[0]["payload"],
                delivery_class=DeliveryClass(previous[0]["delivery_class"]),
            )
        attention = "NOT_ELIGIBLE"
        if (
            currently_eligible
            and event.metadata.get("wake_eligible") is True
            and event.metadata.get("synthetic") is False
        ):
            if self.dispatch is None:
                raise HTTPException(503, "EVENT_RECORDED_ATTENTION_UNAVAILABLE")
            requests = self.dispatch(event, result.journal_position)
            attention = "QUEUED" if requests else "NO_NEW_REQUEST"
        if relay_id is not None:
            with self._lock:
                self._receipts[relay_id] = self.clock().isoformat()
        return {"status": "RECORDED", "deduplicated": result.deduplicated, "attention": attention}

    def ingest_tapo_state(
        self,
        state: Mapping[str, object],
        *,
        binding: TapoLockBinding,
        ha_instance_id: UUID,
        received_at: datetime,
        snapshot: bool,
        source_qualified: bool = False,
    ) -> dict[str, Any]:
        """Trusted HA callback only; not an HTTP or model-selectable operation.

        Caller verifies actual SmartThings registry association and source sample.
        Missing HA revision is not durable operation identity: reject rather than
        invent replay guarantees. No automatic cache-observation Attention wake.
        """
        if not source_qualified:
            raise VendorIngressError("TAPO_SOURCE_UNQUALIFIED")
        if not _mapped_resource(self.graph, binding.household_id, binding.resource_id) or not any(
            capability.canonical_id == binding.capability_id
            for capability in self.graph.resource_capabilities(binding.resource_id)
        ):
            raise VendorIngressError("CANONICAL_MAPPING_REQUIRED")
        event = normalize_smartthings_ha_lock(
            state,
            binding=binding,
            household_id=binding.household_id,
            ha_instance_id=ha_instance_id,
            received_at=received_at,
            snapshot=snapshot,
        )
        if event.source_event_id is None:
            raise VendorIngressError("SOURCE_REVISION_REQUIRED")
        # No attribution prose in a public digest: _record compares the exact
        # stored bounded payload following atomic deduplication instead.
        return self._record(event, event.source_event_id)


def install_vendor_event_api(
    app: FastAPI,
    authenticate: Callable[[Request], Any],
    ingress_getter: Callable[[], VendorEventIngress | None],
) -> None:
    """No new process, database, unauthenticated household status, or credentials UI."""

    disabled = VendorEventIngress(VendorRelayConfig(), journal=None, graph=None)

    def resolve() -> VendorEventIngress:
        try:
            return ingress_getter() or disabled
        except Exception:
            raise HTTPException(503, "VENDOR_INGRESS_CONFIGURATION_UNAVAILABLE") from None

    @app.get("/api/v1/vendor-events/status")
    def status(request: Request) -> dict[str, Any]:
        identity = authenticate(request)
        return resolve().status(identity.household_id)

    @app.post("/api/v1/vendor-events/receive")
    async def receive(request: Request) -> dict[str, Any]:
        ingress = await run_in_threadpool(resolve)
        source = ingress.authenticate_relay(request.headers.get("authorization", ""))
        if "cookie" in request.headers or "origin" in request.headers:
            raise HTTPException(403, "BROWSER_RELAY_FORBIDDEN")
        if request.headers.get("content-type", "").split(";", 1)[0].strip() != "application/json":
            raise HTTPException(415, "JSON_REQUIRED")
        if request.headers.get("content-encoding", "identity") != "identity":
            raise HTTPException(415, "ENCODING_NOT_SUPPORTED")
        raw = bytearray()
        try:
            async with asyncio.timeout(5):
                async for chunk in request.stream():
                    if len(raw) + len(chunk) > MAX_BODY:
                        raise HTTPException(413, "NOTIFICATION_TOO_LARGE")
                    raw.extend(chunk)
            body = json.loads(raw)
            if type(body) is not dict:
                raise ValueError
        except (ValueError, UnicodeError, RecursionError):
            raise HTTPException(400, "INVALID_NOTIFICATION") from None
        except TimeoutError:
            raise HTTPException(408, "NOTIFICATION_READ_TIMEOUT") from None
        finally:
            raw.clear()
        try:
            return await run_in_threadpool(ingress.receive, source, body)
        except HTTPException:
            raise
        except Exception:
            # Neither driver/parser errors nor bodies are emitted into logs or JSON.
            raise HTTPException(503, "VENDOR_INGRESS_UNAVAILABLE") from None
