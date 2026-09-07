"""Typed relay and fixture tests; no real Wansview sample or household data."""

from __future__ import annotations

import json
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from uuid import UUID

import pytest

from anima_ha.android_notifications import (
    REAL_REPORT_FORMAT,
    SYNTHETIC_FORMAT,
    WANSVIEW_PACKAGE,
    DeliveryComparison,
    Disposition,
    Freshness,
    NormalizationResult,
    NotificationValidationError,
    RelayRegistration,
    Transport,
    compare_delivery,
    normalize_notification,
    sanitize_relay_report,
)
from anima_ha.events import DeliveryClass, EvidenceKind

NOW = datetime(2026, 1, 1, 12, tzinfo=UTC)
HOME = UUID(int=1)
RELAY = UUID(int=2)
CAMERA = UUID(int=3)


def registration() -> RelayRegistration:
    return RelayRegistration(HOME, RELAY, {"fixture-camera": CAMERA}, frozenset({"fixture-motion"}))


def fields(**changes: object) -> dict[str, object]:
    return {
        "format": SYNTHETIC_FORMAT,
        "delivery_id": str(UUID(int=4)),
        "camera_alias": "fixture-camera",
        "channel_id": "fixture-motion",
        "kind": "motion_reported",
        "android_posted_at": (NOW - timedelta(seconds=2)).isoformat(),
        "source_occurred_at": None,
        "relay_received_at": (NOW - timedelta(seconds=1)).isoformat(),
        "is_group_summary": False,
        "reported_loss_count": None,
        **changes,
    }


def normalize(data: object, *, at: datetime = NOW) -> NormalizationResult:
    return normalize_notification(
        package_name=WANSVIEW_PACKAGE,
        load_fields=lambda: data,
        registration=registration(),
        received_at=at,
        synthetic=True,
    )


@pytest.mark.parametrize(
    "package", ["com.messages", "", WANSVIEW_PACKAGE + ".fake", "*", "WANSVIEW"]
)
def test_unrelated_packages_never_load_fields(package: str) -> None:
    calls: list[bool] = []

    def reader() -> object:
        calls.append(True)
        raise RuntimeError("private-notification-sentinel")

    result = normalize_notification(
        package_name=package,
        load_fields=reader,
        registration=registration(),
        received_at=NOW,
        synthetic=True,
    )
    assert result.disposition == Disposition.PACKAGE_REJECTED
    assert calls == []
    assert result.event is None


def test_production_default_cannot_load_or_promote_fixture() -> None:
    def reader() -> object:
        pytest.fail("production must not access an unqualified notification")

    result = normalize_notification(
        package_name=WANSVIEW_PACKAGE,
        load_fields=reader,
        registration=registration(),
        received_at=NOW,
    )
    assert result.disposition == Disposition.LIVE_FORMAT_UNQUALIFIED
    assert result.event is None and result.receipt is None


def test_empty_allowlist_fails_closed() -> None:
    result = normalize_notification(
        package_name=WANSVIEW_PACKAGE,
        load_fields=lambda: pytest.fail("read"),
        registration=replace(registration(), allowed_packages=frozenset()),
        received_at=NOW,
        synthetic=True,
    )
    assert result.disposition == Disposition.PACKAGE_REJECTED


def test_registration_is_explicit_bounded_and_defensively_copied() -> None:
    with pytest.raises(NotificationValidationError):
        replace(registration(), allowed_packages=frozenset({"*"}))
    with pytest.raises(NotificationValidationError):
        replace(registration(), stale_after_seconds=True)
    with pytest.raises(NotificationValidationError):
        replace(registration(), camera_mappings={"https://private.example": CAMERA})
    cameras = {"fixture-camera": CAMERA}
    config = replace(registration(), camera_mappings=cameras)
    cameras.clear()
    assert config.camera_mappings["fixture-camera"] == CAMERA


@pytest.mark.parametrize(
    "key", ["body", "title", "Bundle", "image", "uri", "otp", "household_id", "authority"]
)
def test_raw_or_authority_fields_rejected_without_retention(key: str) -> None:
    result = normalize(fields(**{key: "private-notification-sentinel"}))
    assert result.disposition == Disposition.INVALID_FIELDS
    assert result.event is None
    assert "private-notification-sentinel" not in repr(result)


@pytest.mark.parametrize("data", [None, b"private", ["private"], {"format": SYNTHETIC_FORMAT}])
def test_rejects_non_schema_objects(data: object) -> None:
    assert normalize(data).disposition == Disposition.INVALID_FIELDS


@pytest.mark.parametrize(
    ("changes", "expected"),
    [
        ({"format": "wansview-live-v1"}, Disposition.FORMAT_REJECTED),
        ({"camera_alias": "unconfigured"}, Disposition.CAMERA_UNMAPPED),
        ({"channel_id": "account-notices"}, Disposition.CHANNEL_REJECTED),
        ({"kind": "account_notice"}, Disposition.NON_MOTION_IGNORED),
        ({"kind": "removed"}, Disposition.NON_MOTION_IGNORED),
        ({"is_group_summary": True}, Disposition.SUMMARY_IGNORED),
        ({"is_group_summary": "false"}, Disposition.INVALID_FIELDS),
        ({"reported_loss_count": True}, Disposition.INVALID_FIELDS),
        ({"reported_loss_count": -1}, Disposition.INVALID_FIELDS),
        ({"reported_loss_count": 1_000_001}, Disposition.INVALID_FIELDS),
        ({"delivery_id": "not-a-uuid"}, Disposition.INVALID_FIELDS),
        ({"camera_alias": "x" * 65}, Disposition.INVALID_FIELDS),
        ({"android_posted_at": "2026-01-01T12:00:00"}, Disposition.INVALID_FIELDS),
        ({"source_occurred_at": "not-a-time"}, Disposition.INVALID_FIELDS),
        ({"relay_received_at": 123}, Disposition.INVALID_FIELDS),
    ],
)
def test_rejections_are_explicit(changes: dict[str, object], expected: Disposition) -> None:
    result = normalize(fields(**changes))
    assert result.disposition == expected
    assert result.event is None and result.receipt is None


def test_reader_failure_does_not_expose_private_exception() -> None:
    def reader() -> object:
        raise RuntimeError("private-notification-sentinel")

    result = normalize_notification(
        package_name=WANSVIEW_PACKAGE,
        load_fields=reader,
        registration=registration(),
        received_at=NOW,
        synthetic=True,
    )
    assert result.disposition == Disposition.FIELD_READ_FAILED
    assert "private-notification-sentinel" not in repr(result)


def test_normalized_fixture_is_not_physical_truth_or_action_authority() -> None:
    result = normalize(fields())
    assert result.disposition == Disposition.NORMALIZED_SYNTHETIC
    event = result.event
    assert event is not None
    assert event.event_type.endswith(".synthetic")
    assert event.metadata["external_content_trust"] == "EXTERNAL_UNTRUSTED"
    assert event.metadata["parser_qualification"] == "SYNTHETIC_ONLY_UNQUALIFIED"
    assert event.metadata["wake_eligible"] is False
    assert event.payload["identity_status"] == "UNKNOWN"
    assert event.payload["authority"] == "NONE"
    assert event.evidence_kind == EvidenceKind.UNKNOWN
    assert event.confidence is None and event.delivery_class == DeliveryClass.BEST_EFFORT
    assert event.payload["source_occurred_at"] is None
    assert event.payload["source_freshness"] == Freshness.UNKNOWN
    assert event.payload["camera_resource_id"] == str(CAMERA)
    assert "camera_alias" not in event.payload
    json.dumps(event.to_dict())


def test_source_post_and_both_receipt_times_are_distinct() -> None:
    source = NOW - timedelta(seconds=10)
    event = normalize(fields(source_occurred_at=source.isoformat())).event
    assert event is not None
    assert event.payload["source_occurred_at"] == source.isoformat()
    assert event.occurred_at == NOW - timedelta(seconds=2)
    assert event.payload["relay_received_at"] == (NOW - timedelta(seconds=1)).isoformat()
    assert event.recorded_at == NOW
    assert event.payload["timestamp_basis"] == "ANDROID_POST_TIME"


def test_late_push_does_not_make_old_source_recent() -> None:
    event = normalize(fields(source_occurred_at=(NOW - timedelta(hours=1)).isoformat())).event
    assert event is not None
    assert event.payload["report_freshness"] == Freshness.RECENT
    assert event.payload["source_freshness"] == Freshness.STALE


def test_stale_receipt_and_clock_order_are_honest() -> None:
    event = normalize(fields(), at=NOW + timedelta(minutes=10)).event
    assert event is not None and event.payload["report_freshness"] == Freshness.STALE
    future = normalize(fields(android_posted_at=(NOW + timedelta(seconds=2)).isoformat())).event
    assert future is not None
    assert future.payload["clock_status"] == "CLOCK_SKEW"
    assert future.payload["report_freshness"] == Freshness.CLOCK_SKEW
    wrong_order = normalize(fields(source_occurred_at=NOW.isoformat())).event
    assert wrong_order is not None and wrong_order.payload["clock_status"] == "CLOCK_SKEW"


@pytest.mark.parametrize(
    "count,status", [(None, "UNKNOWN"), (0, "NO_LOSS_REPORTED"), (2, "REPORTED_LOSS")]
)
def test_reported_loss_never_establishes_complete_coverage(count: int | None, status: str) -> None:
    event = normalize(fields(reported_loss_count=count)).event
    assert event is not None
    assert event.payload["reported_loss_count"] == count
    assert event.payload["relay_loss_status"] == status
    assert event.payload["coverage"] == "UNKNOWN"


def test_delivery_identity_retries_conflicts_and_reconstruction() -> None:
    first = normalize(fields())
    retry = normalize(fields(), at=NOW + timedelta(minutes=10))
    assert first.receipt and retry.receipt
    assert compare_delivery(first.receipt, retry.receipt) == DeliveryComparison.DUPLICATE
    assert first.event and retry.event
    assert first.event.recorded_at != retry.event.recorded_at
    changed = normalize(fields(source_occurred_at=NOW.isoformat()))
    assert changed.receipt
    assert compare_delivery(first.receipt, changed.receipt) == DeliveryComparison.CONFLICT
    distinct = normalize(fields(delivery_id=str(UUID(int=5))))
    assert distinct.receipt
    assert compare_delivery(first.receipt, distinct.receipt) == DeliveryComparison.DISTINCT
    # No process-local cache: a new normalizer call reconstructs the same key.
    reconstructed = normalize(fields())
    assert reconstructed.receipt == first.receipt


@pytest.mark.parametrize(
    "config",
    [
        replace(registration(), household_id=UUID(int=8)),
        replace(registration(), relay_id=UUID(int=9)),
    ],
)
def test_delivery_identity_is_household_and_relay_scoped(config: RelayRegistration) -> None:
    first = normalize(fields())
    other = normalize_notification(
        package_name=WANSVIEW_PACKAGE,
        load_fields=fields,
        registration=config,
        received_at=NOW,
        synthetic=True,
    )
    assert first.receipt and other.receipt
    assert compare_delivery(first.receipt, other.receipt) == DeliveryComparison.DISTINCT


def test_configured_camera_remapping_is_not_a_silent_retry() -> None:
    first = normalize(fields())
    other = normalize_notification(
        package_name=WANSVIEW_PACKAGE,
        load_fields=fields,
        registration=replace(registration(), camera_mappings={"fixture-camera": UUID(int=7)}),
        received_at=NOW,
        synthetic=True,
    )
    assert first.receipt and other.receipt
    assert compare_delivery(first.receipt, other.receipt) == DeliveryComparison.CONFLICT


@pytest.mark.parametrize("stamp", ["0001-01-01T00:00:00+01:00", "9999-12-31T23:59:59-01:00"])
def test_out_of_range_utc_conversion_fails_closed(stamp: str) -> None:
    assert normalize(fields(android_posted_at=stamp)).disposition == Disposition.INVALID_FIELDS
    assert (
        normalize(fields(), at=datetime.fromisoformat(stamp)).disposition
        == Disposition.INVALID_FIELDS
    )


def test_naive_core_receipt_does_not_load_fields() -> None:
    result = normalize_notification(
        package_name=WANSVIEW_PACKAGE,
        load_fields=lambda: pytest.fail("must reject timestamp before fields"),
        registration=registration(),
        received_at=NOW.replace(tzinfo=None),
        synthetic=True,
    )
    assert result.disposition == Disposition.INVALID_FIELDS


def dbus_normalize(**changes: object) -> NormalizationResult:
    return normalize_notification(
        package_name=WANSVIEW_PACKAGE,
        load_fields=lambda: fields(
            **{
                "android_posted_at": None,
                "channel_id": None,
                "is_group_summary": None,
                **changes,
            }
        ),
        registration=replace(
            registration(), transport=Transport.WAYDROID_PRIVATE_DBUS, allowed_channels=frozenset()
        ),
        received_at=NOW,
        synthetic=True,
    )


def test_private_dbus_receipt_does_not_invent_android_metadata() -> None:
    event = dbus_normalize().event
    assert event is not None
    assert event.occurred_at == NOW - timedelta(seconds=1)
    assert event.recorded_at == NOW
    assert event.payload["timestamp_basis"] == "RELAY_RECEIPT_TIME"
    assert event.payload["report_freshness"] == Freshness.UNKNOWN
    assert event.payload["source_freshness"] == Freshness.UNKNOWN
    assert event.payload["relay_queue_freshness"] == Freshness.RECENT
    assert event.payload["transport"] == "waydroid_private_dbus"
    for key in ("channel_id", "is_group_summary", "android_posted_at", "source_occurred_at"):
        assert event.payload[key] is None
    assert event.metadata["wake_eligible"] is False


@pytest.mark.parametrize(
    "key,value",
    [
        ("android_posted_at", NOW.isoformat()),
        ("channel_id", "fixture-motion"),
        ("is_group_summary", False),
    ],
)
def test_private_dbus_rejects_fabricated_android_properties(key: str, value: object) -> None:
    assert dbus_normalize(**{key: value}).disposition == Disposition.INVALID_FIELDS


def test_private_dbus_still_requires_camera_mapping_and_has_unknown_coverage() -> None:
    assert dbus_normalize(camera_alias="other").disposition == Disposition.CAMERA_UNMAPPED
    result = dbus_normalize(relay_received_at=(NOW - timedelta(hours=1)).isoformat())
    assert result.event is not None
    assert result.event.payload["relay_queue_freshness"] == Freshness.STALE
    assert result.event.payload["report_freshness"] == Freshness.UNKNOWN
    assert result.event.payload["coverage"] == "UNKNOWN"
    assert (
        result.receipt
        == dbus_normalize(relay_received_at=(NOW - timedelta(hours=1)).isoformat()).receipt
    )


def sanitize(data: object, *, at: datetime = NOW) -> NormalizationResult:
    return sanitize_relay_report(
        package_name=WANSVIEW_PACKAGE,
        load_fields=lambda: data,
        registration=registration(),
        received_at=at,
    )


def test_real_protocol_validates_schema_without_qualifying_vendor_or_wake() -> None:
    result = sanitize(fields(format=REAL_REPORT_FORMAT))
    assert result.disposition == Disposition.NORMALIZED_REPORT
    event = result.event
    assert event is not None and result.receipt is not None
    assert event.event_type == "external.android.motion_reported"
    assert event.metadata["schema_qualification"] == "ANIMA_OWNED_SCHEMA"
    assert "parser_qualification" not in event.metadata
    assert "producer_qualified" not in event.metadata
    assert event.metadata["synthetic"] is False
    assert event.metadata["wake_eligible"] is False
    assert event.metadata["external_content_trust"] == "EXTERNAL_UNTRUSTED"
    assert event.evidence_kind == EvidenceKind.UNKNOWN and event.confidence is None
    assert event.payload["identity_status"] == "UNKNOWN"
    assert event.payload["authority"] == "NONE"


def test_protocol_namespaces_do_not_collide_even_in_journal_source_identity() -> None:
    real = sanitize(fields(format=REAL_REPORT_FORMAT))
    fixture = normalize(fields())
    assert real.event and fixture.event and real.receipt and fixture.receipt
    assert real.event.source_event_id == fixture.event.source_event_id
    assert real.event.source != fixture.event.source
    assert compare_delivery(real.receipt, fixture.receipt) == DeliveryComparison.DISTINCT
    assert sanitize(fields()).disposition == Disposition.FORMAT_REJECTED
    assert normalize(fields(format=REAL_REPORT_FORMAT)).disposition == Disposition.FORMAT_REJECTED


@pytest.mark.parametrize(
    "field_name",
    [
        "body",
        "Bundle",
        "image",
        "authority",
        "producer_qualified",
        "producer_adapter",
        "wake_enabled",
        "wake_eligible",
        "schema_qualification",
        "household_id",
    ],
)
def test_real_report_rejects_raw_or_self_qualifying_fields(field_name: str) -> None:
    result = sanitize(fields(format=REAL_REPORT_FORMAT, **{field_name: "private-sentinel"}))
    assert result.disposition == Disposition.INVALID_FIELDS
    assert result.event is None and result.receipt is None
    assert "private-sentinel" not in repr(result)


@pytest.mark.parametrize(
    "changes,expected",
    [
        ({"camera_alias": "unmapped"}, Disposition.CAMERA_UNMAPPED),
        ({"channel_id": "unregistered"}, Disposition.CHANNEL_REJECTED),
        ({"kind": "marketing"}, Disposition.NON_MOTION_IGNORED),
        ({"is_group_summary": True}, Disposition.SUMMARY_IGNORED),
        ({"reported_loss_count": True}, Disposition.INVALID_FIELDS),
        ({"android_posted_at": "2026-01-01"}, Disposition.INVALID_FIELDS),
    ],
)
def test_real_protocol_reuses_strict_validation(
    changes: dict[str, object], expected: Disposition
) -> None:
    result = sanitize(fields(format=REAL_REPORT_FORMAT, **changes))
    assert result.disposition == expected and result.event is None


def test_real_protocol_checks_package_before_reader() -> None:
    result = sanitize_relay_report(
        package_name="unrelated.application",
        load_fields=lambda: pytest.fail("unrelated fields must not be loaded"),
        registration=registration(),
        received_at=NOW,
    )
    assert result.disposition == Disposition.PACKAGE_REJECTED


def test_real_protocol_retry_conflict_and_unknown_time() -> None:
    data = fields(format=REAL_REPORT_FORMAT)
    first = sanitize(data)
    retry = sanitize(data, at=NOW + timedelta(hours=1))
    changed = sanitize(fields(format=REAL_REPORT_FORMAT, reported_loss_count=1))
    assert first.receipt and retry.receipt and changed.receipt
    assert compare_delivery(first.receipt, retry.receipt) == DeliveryComparison.DUPLICATE
    assert compare_delivery(first.receipt, changed.receipt) == DeliveryComparison.CONFLICT
    assert retry.event and retry.event.payload["report_freshness"] == Freshness.STALE
    assert retry.event.payload["source_freshness"] == Freshness.UNKNOWN
    assert retry.event.payload["coverage"] == "UNKNOWN"


def test_real_dbus_report_preserves_receipt_only_provenance() -> None:
    result = sanitize_relay_report(
        package_name=WANSVIEW_PACKAGE,
        load_fields=lambda: fields(
            format=REAL_REPORT_FORMAT,
            android_posted_at=None,
            channel_id=None,
            is_group_summary=None,
        ),
        registration=replace(
            registration(), transport=Transport.WAYDROID_PRIVATE_DBUS, allowed_channels=frozenset()
        ),
        received_at=NOW,
    )
    assert result.disposition == Disposition.NORMALIZED_REPORT
    assert result.event is not None
    assert result.event.payload["timestamp_basis"] == "RELAY_RECEIPT_TIME"
    assert result.event.occurred_at == NOW - timedelta(seconds=1)
    assert result.event.payload["android_posted_at"] is None
    assert result.event.payload["report_freshness"] == Freshness.UNKNOWN
    assert result.event.metadata["wake_eligible"] is False
