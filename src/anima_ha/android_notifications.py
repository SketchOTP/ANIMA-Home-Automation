"""ANIMA-owned typed relay report validation; no raw Wansview text extraction.

The caller owns authenticated relay registration. Package identity must come
from Android's callback, not notification text. No network, Android APIs, journal
writes, Truth projection or SENTRY dispatch occurs here. Schema validity does
not qualify the producer: receiver-owned registration gates source eligibility
and wake permission. The legacy synthetic wrapper never authorizes ingestion.
"""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from types import MappingProxyType
from uuid import NAMESPACE_URL, UUID, uuid5

from anima_ha.events import DeliveryClass, EventEnvelope, EvidenceKind

WANSVIEW_PACKAGE = "net.ajcloud.wansviewplus"
SYNTHETIC_FORMAT = "anima.android.motion.fixture.v1"
REAL_REPORT_FORMAT = "anima.android.motion.report.v1"
_LABEL = re.compile(r"[A-Za-z0-9_.-]{1,64}\Z")
_FIELDS = frozenset(
    {
        "format",
        "delivery_id",
        "camera_alias",
        "channel_id",
        "kind",
        "android_posted_at",
        "source_occurred_at",
        "relay_received_at",
        "is_group_summary",
        "reported_loss_count",
    }
)


class Disposition(StrEnum):
    NORMALIZED_REPORT = "NORMALIZED_REPORT"
    NORMALIZED_SYNTHETIC = "NORMALIZED_SYNTHETIC"
    PACKAGE_REJECTED = "PACKAGE_REJECTED"
    LIVE_FORMAT_UNQUALIFIED = "LIVE_FORMAT_UNQUALIFIED"
    FORMAT_REJECTED = "FORMAT_REJECTED"
    INVALID_FIELDS = "INVALID_FIELDS"
    FIELD_READ_FAILED = "FIELD_READ_FAILED"
    CAMERA_UNMAPPED = "CAMERA_UNMAPPED"
    CHANNEL_REJECTED = "CHANNEL_REJECTED"
    SUMMARY_IGNORED = "SUMMARY_IGNORED"
    NON_MOTION_IGNORED = "NON_MOTION_IGNORED"


class DeliveryComparison(StrEnum):
    DISTINCT = "DISTINCT"
    DUPLICATE = "DUPLICATE"
    CONFLICT = "CONFLICT"


class Freshness(StrEnum):
    UNKNOWN = "UNKNOWN"
    RECENT = "RECENT"
    STALE = "STALE"
    CLOCK_SKEW = "CLOCK_SKEW"


class Transport(StrEnum):
    ANDROID_LISTENER = "android_notification_listener"
    WAYDROID_PRIVATE_DBUS = "waydroid_private_dbus"


class NotificationValidationError(ValueError):
    """Static error category only; never include rejected field values."""


def _label(value: object) -> str:
    if not isinstance(value, str) or not _LABEL.fullmatch(value):
        raise NotificationValidationError("invalid bounded label")
    return value


def _uuid(value: object) -> UUID:
    if not isinstance(value, str) or len(value) != 36:
        raise NotificationValidationError("invalid delivery identity")
    try:
        result = UUID(value)
    except ValueError:
        raise NotificationValidationError("invalid delivery identity") from None
    if str(result) != value or result.int == 0:
        raise NotificationValidationError("invalid delivery identity")
    return result


def _utc(value: datetime) -> datetime:
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
        raise NotificationValidationError("timezone-aware timestamp required")
    try:
        return value.astimezone(UTC)
    except (ValueError, OverflowError):
        raise NotificationValidationError("invalid timestamp") from None


def _timestamp(value: object) -> datetime:
    if not isinstance(value, str) or len(value) > 40:
        raise NotificationValidationError("invalid timestamp")
    try:
        return _utc(datetime.fromisoformat(value))
    except (ValueError, OverflowError):
        raise NotificationValidationError("invalid timestamp") from None


@dataclass(frozen=True)
class RelayRegistration:
    """Trusted configuration, never populated from a notification/request body.

    The lead must verify canonical camera ownership against the household graph
    before constructing this registration. This pure module cannot do that.
    Empty package/channel/camera configurations fail closed at intake.
    """

    household_id: UUID
    relay_id: UUID
    camera_mappings: Mapping[str, UUID] = field(repr=False)
    allowed_channels: frozenset[str]
    allowed_packages: frozenset[str] = frozenset({WANSVIEW_PACKAGE})
    stale_after_seconds: int = 300
    transport: Transport = Transport.ANDROID_LISTENER

    def __post_init__(self) -> None:
        if not isinstance(self.transport, Transport):
            raise NotificationValidationError("invalid registered transport")
        if any(not isinstance(v, UUID) or v.int == 0 for v in (self.household_id, self.relay_id)):
            raise NotificationValidationError("invalid registration identity")
        packages = frozenset(self.allowed_packages)
        if packages - {WANSVIEW_PACKAGE}:
            raise NotificationValidationError("only official Wansview Cloud package is allowed")
        if type(self.stale_after_seconds) is not int or not 1 <= self.stale_after_seconds <= 86400:
            raise NotificationValidationError("invalid freshness bound")
        if len(self.camera_mappings) > 128 or len(self.allowed_channels) > 32:
            raise NotificationValidationError("registration exceeds bounds")
        cameras = dict(self.camera_mappings)
        for alias, camera in cameras.items():
            _label(alias)
            if not isinstance(camera, UUID) or camera.int == 0:
                raise NotificationValidationError("invalid canonical camera")
        channels = frozenset(_label(channel) for channel in self.allowed_channels)
        object.__setattr__(self, "camera_mappings", MappingProxyType(cameras))
        object.__setattr__(self, "allowed_packages", packages)
        object.__setattr__(self, "allowed_channels", channels)


@dataclass(frozen=True)
class DeliveryReceipt:
    """Comparison material only, NOT a durable delivery acknowledgement."""

    event_id: str
    content_digest: str


@dataclass(frozen=True)
class NormalizationResult:
    disposition: Disposition
    event: EventEnvelope | None = None
    receipt: DeliveryReceipt | None = None


def compare_delivery(previous: DeliveryReceipt, candidate: DeliveryReceipt) -> DeliveryComparison:
    """Caller must persist/compare atomically; no in-memory exactly-once claim."""
    if previous.event_id != candidate.event_id:
        return DeliveryComparison.DISTINCT
    if previous.content_digest != candidate.content_digest:
        return DeliveryComparison.CONFLICT
    return DeliveryComparison.DUPLICATE


def _freshness(at: datetime | None, received_at: datetime, seconds: int) -> Freshness:
    if at is None:
        return Freshness.UNKNOWN
    age = (received_at - at).total_seconds()
    if age < 0:
        return Freshness.CLOCK_SKEW
    return Freshness.STALE if age > seconds else Freshness.RECENT


def normalize_notification(
    *,
    package_name: str,
    load_fields: Callable[[], object],
    registration: RelayRegistration,
    received_at: datetime,
    synthetic: bool = False,
) -> NormalizationResult:
    """Legacy fixture-only entry point; not a raw vendor notification parser."""
    return _normalize_report(
        package_name=package_name,
        load_fields=load_fields,
        registration=registration,
        received_at=received_at,
        report_format=SYNTHETIC_FORMAT,
        enabled=synthetic is True,
    )


def sanitize_relay_report(
    *,
    package_name: str,
    load_fields: Callable[[], object],
    registration: RelayRegistration,
    received_at: datetime,
) -> NormalizationResult:
    """Validate our typed report v1, not vendor text or producer qualification.

    The receiver authenticates and qualifies the registered producer before
    accepting this result into the journal. This function sets no source trust,
    identity or wake authority, even for a perfectly schema-valid report.
    """
    return _normalize_report(
        package_name=package_name,
        load_fields=load_fields,
        registration=registration,
        received_at=received_at,
        report_format=REAL_REPORT_FORMAT,
        enabled=True,
    )


def _normalize_report(
    *,
    package_name: str,
    load_fields: Callable[[], object],
    registration: RelayRegistration,
    received_at: datetime,
    report_format: str,
    enabled: bool,
) -> NormalizationResult:
    """Shared minimization; reject package before invoking the field reader."""
    if (
        type(package_name) is not str
        or package_name != WANSVIEW_PACKAGE
        or package_name not in registration.allowed_packages
    ):
        return NormalizationResult(Disposition.PACKAGE_REJECTED)
    if not enabled:
        return NormalizationResult(Disposition.LIVE_FORMAT_UNQUALIFIED)
    try:
        received_at = _utc(received_at)
    except NotificationValidationError:
        return NormalizationResult(Disposition.INVALID_FIELDS)
    try:
        fields = load_fields()
    except Exception:
        # A reader exception might contain raw private text; do not log it.
        return NormalizationResult(Disposition.FIELD_READ_FAILED)
    if type(fields) is not dict or fields.keys() != _FIELDS:
        return NormalizationResult(Disposition.INVALID_FIELDS)
    if type(fields["format"]) is not str or fields["format"] != report_format:
        return NormalizationResult(Disposition.FORMAT_REJECTED)
    try:
        delivery_id = _uuid(fields["delivery_id"])
        alias = _label(fields["camera_alias"])
        kind = _label(fields["kind"])
        if registration.transport == Transport.WAYDROID_PRIVATE_DBUS:
            # Waydroid 1.6.2 Notify does not export these Android properties.
            if any(
                fields[key] is not None
                for key in ("channel_id", "android_posted_at", "is_group_summary")
            ):
                raise NotificationValidationError("unavailable transport fields")
            channel = None
            posted_at = None
        else:
            channel = _label(fields["channel_id"])
            posted_at = _timestamp(fields["android_posted_at"])
        source_at = (
            None
            if fields["source_occurred_at"] is None
            else _timestamp(fields["source_occurred_at"])
        )
        relay_at = _timestamp(fields["relay_received_at"])
        summary = fields["is_group_summary"]
        losses = fields["reported_loss_count"]
        if registration.transport == Transport.ANDROID_LISTENER and type(summary) is not bool:
            raise NotificationValidationError("invalid summary flag")
        if losses is not None and (type(losses) is not int or not 0 <= losses <= 1_000_000):
            raise NotificationValidationError("invalid loss count")
    except NotificationValidationError:
        return NormalizationResult(Disposition.INVALID_FIELDS)
    if (
        registration.transport == Transport.ANDROID_LISTENER
        and channel not in registration.allowed_channels
    ):
        return NormalizationResult(Disposition.CHANNEL_REJECTED)
    if summary:
        return NormalizationResult(Disposition.SUMMARY_IGNORED)
    if kind != "motion_reported":
        return NormalizationResult(Disposition.NON_MOTION_IGNORED)
    camera = registration.camera_mappings.get(alias)
    if camera is None:
        return NormalizationResult(Disposition.CAMERA_UNMAPPED)

    synthetic = report_format == SYNTHETIC_FORMAT
    # Separate both journal (source, source_event_id) and envelope UUID identity.
    prefix = "android-notification" if synthetic else "android-relay-report"
    source = f"{prefix}:{registration.household_id}:{registration.relay_id}"
    event_id = str(uuid5(NAMESPACE_URL, f"{report_format}:{source}:{delivery_id}"))
    # Immutable source facts: ANIMA retry receipt time/freshness are excluded.
    facts = {
        "format": report_format,
        "camera_resource_id": str(camera),
        "source_package": WANSVIEW_PACKAGE,
        "transport": registration.transport.value,
        "channel_id": channel,
        "is_group_summary": summary,
        "event_kind": "motion_reported",
        "source_occurred_at": source_at.isoformat() if source_at else None,
        "android_posted_at": posted_at.isoformat() if posted_at else None,
        "relay_received_at": relay_at.isoformat(),
        "reported_loss_count": losses,
    }
    digest = hashlib.sha256(json.dumps(facts, sort_keys=True).encode()).hexdigest()
    clock_skew = (
        (posted_at is not None and posted_at > relay_at)
        or relay_at > received_at
        or (source_at is not None and source_at > (posted_at or relay_at))
    )
    event = EventEnvelope.create(
        event_id=event_id,
        event_type=(
            "external.android.motion_reported.synthetic"
            if synthetic
            else "external.android.motion_reported"
        ),
        source=source,
        source_event_id=str(delivery_id),
        subject_key=f"household/{registration.household_id}/camera/{camera}",
        # Observation of posting/relay receipt, NEVER promoted to camera time.
        occurred_at=posted_at or relay_at,
        recorded_at=received_at,
        evidence_kind=EvidenceKind.UNKNOWN,
        confidence=None,
        delivery_class=DeliveryClass.BEST_EFFORT,
        payload={
            **facts,
            "anima_received_at": received_at.isoformat(),
            "timestamp_basis": "ANDROID_POST_TIME" if posted_at else "RELAY_RECEIPT_TIME",
            "report_freshness": _freshness(
                posted_at, received_at, registration.stale_after_seconds
            ),
            "source_freshness": _freshness(
                source_at, received_at, registration.stale_after_seconds
            ),
            "relay_queue_freshness": _freshness(
                relay_at, received_at, registration.stale_after_seconds
            ),
            "clock_status": "CLOCK_SKEW" if clock_skew else "CONSISTENT_NOT_VERIFIED",
            "coverage": "UNKNOWN",
            "relay_loss_status": (
                "UNKNOWN" if losses is None else "REPORTED_LOSS" if losses else "NO_LOSS_REPORTED"
            ),
            "identity_status": "UNKNOWN",
            "authority": "NONE",
        },
        metadata={
            "household_id": str(registration.household_id),
            "relay_id": str(registration.relay_id),
            "external_content_trust": "EXTERNAL_UNTRUSTED",
            **(
                {"parser_qualification": "SYNTHETIC_ONLY_UNQUALIFIED"}
                if synthetic
                else {"schema_qualification": "ANIMA_OWNED_SCHEMA"}
            ),
            "synthetic": synthetic,
            "wake_eligible": False,
            "content_digest": digest,
        },
    )
    return NormalizationResult(
        Disposition.NORMALIZED_SYNTHETIC if synthetic else Disposition.NORMALIZED_REPORT,
        event,
        DeliveryReceipt(event_id, digest),
    )
