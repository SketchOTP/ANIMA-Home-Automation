"""Pure, privacy-bounded SmartThings-via-HA observations for a commissioned DL110.

This is not a connector, lock controller, Truth projector, or identity verifier.
Core must build the binding from its graph and verified HA registry association;
never construct it from vendor payloads, model arguments, or similar names.
Stock HA exposes a state cache, not a lossless SmartThings operation stream.
"""

from __future__ import annotations

import hashlib
import json
import re
import unicodedata
from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from uuid import NAMESPACE_URL, UUID, uuid5

from anima_ha.events import EventEnvelope, EvidenceKind


class TapoEventError(ValueError):
    """Invalid trusted context or unsupported source; messages contain no input."""


class ReportedLockState(StrEnum):
    LOCKED = "locked"
    UNLOCKED = "unlocked"
    UNKNOWN = "unknown"
    UNAVAILABLE = "unavailable"


@dataclass(frozen=True, slots=True)
class TapoLockBinding:
    """Server-owned, household-validated mapping; not an ingress/API schema.

    Core must verify an active DL110 resource, its lock capability, household
    membership and the SmartThings integration owning this exact HA entity.
    This pure module cannot perform those graph/registry checks itself.
    """

    household_id: UUID
    resource_id: UUID
    capability_id: UUID
    ha_instance_id: UUID
    ha_entity_id: str = field(repr=False)
    version: int = 1

    def __post_init__(self) -> None:
        if any(
            not isinstance(value, UUID) or value.int == 0
            for value in (
                self.household_id,
                self.resource_id,
                self.capability_id,
                self.ha_instance_id,
            )
        ):
            raise TapoEventError("canonical mapping UUIDs are required")
        if (
            not isinstance(self.ha_entity_id, str)
            or len(self.ha_entity_id) > 255
            or not re.fullmatch(r"lock\.[a-z0-9_]+", self.ha_entity_id)
        ):
            raise TapoEventError("mapping must identify one HA lock entity")
        if type(self.version) is not int or self.version < 1:
            raise TapoEventError("mapping version must be a positive integer")


def _aware(value: datetime) -> datetime:
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
        raise TapoEventError("receipt time must be timezone-aware")
    return value.astimezone(UTC)


def _ha_time(value: object) -> tuple[datetime | None, str]:
    if value is None:
        return None, "MISSING"
    if not isinstance(value, str) or len(value) > 64:
        return None, "INVALID"
    try:
        parsed = datetime.fromisoformat(value)
        if parsed.tzinfo is None or parsed.utcoffset() is None:
            return None, "INVALID"
        return parsed.astimezone(UTC), "PRESENT"
    except (ValueError, OverflowError):
        return None, "INVALID"


def _reported_text(value: object, *, limit: int) -> str | None:
    # Reject rather than truncate: truncation can change a reported identity.
    if not isinstance(value, str) or not 1 <= len(value) <= limit or not value.strip():
        return None
    if any(unicodedata.category(char).startswith("C") for char in value):
        return None
    return value


def normalize_smartthings_ha_lock(
    state: Mapping[str, object],
    *,
    binding: TapoLockBinding,
    household_id: UUID,
    ha_instance_id: UUID,
    received_at: datetime,
    snapshot: bool,
) -> EventEnvelope:
    """Project a raw HA state in memory into a bounded journal-compatible event.

    ``household_id`` and ``ha_instance_id`` come from trusted Core ingress, not
    the state. ``received_at`` is captured once at ingress and reused on retry.
    ``snapshot`` is explicit for startup/reconnect reads. No input is logged or
    copied wholesale, including on rejection. Only official HA lock attributes
    are inspected; no notification prose or biometric/PIN fields are parsed.

    Physical operation time and the association of cached attribution with an
    operation remain unknown. This event must not authenticate a person, assert
    arrival/door opening, trigger an unlock, or directly project physical Truth.
    """
    if household_id != binding.household_id or ha_instance_id != binding.ha_instance_id:
        raise TapoEventError("source is outside the commissioned mapping scope")
    if state.get("entity_id") != binding.ha_entity_id:
        raise TapoEventError("source does not match the commissioned lock")
    if type(snapshot) is not bool:
        raise TapoEventError("snapshot provenance must be explicit")
    receipt = _aware(received_at)
    updated, time_status = _ha_time(state.get("last_updated"))
    attributes = state.get("attributes")
    if not isinstance(attributes, Mapping):
        attributes = {}

    ha_state = state.get("state")
    raw_lock_state = attributes.get("lock_state")
    reported = ReportedLockState.UNKNOWN
    quality = "UNSUPPORTED_OR_MISSING_LOCK_STATE"
    if ha_state == "unavailable":
        reported, quality = ReportedLockState.UNAVAILABLE, "HA_UNAVAILABLE"
    elif ha_state == "unknown":
        quality = "HA_UNKNOWN"
    elif isinstance(raw_lock_state, str) and raw_lock_state in ("locked", "unlocked"):
        # HA's SmartThings is_locked() collapses every other source value to
        # False. Never infer unlocked from the HA entity's boolean/state alone.
        if ha_state == raw_lock_state:
            reported, quality = ReportedLockState(raw_lock_state), "REPORTED_STATE"
        else:
            quality = "CONFLICTING_HA_STATE"

    label = _reported_text(attributes.get("code_name"), limit=120)
    method = _reported_text(attributes.get("method"), limit=64)
    if reported != ReportedLockState.UNLOCKED or snapshot:
        label = method = None

    # HA last_updated identifies a cache revision, NOT a vendor operation.
    # Names/code slots/raw state are excluded from this public unkeyed digest.
    # No timestamp means receipt-only identity, not restart/cross-phone dedup.
    identity = {
        "contract": "tapo.smartthings_ha.v1",
        "household": str(binding.household_id),
        "instance": str(binding.ha_instance_id),
        "resource": str(binding.resource_id),
        "capability": str(binding.capability_id),
        "mapping_version": binding.version,
        "ha_updated_at": updated.isoformat() if updated else None,
        "receipt_fallback": receipt.isoformat() if updated is None else None,
    }
    digest = hashlib.sha256(
        json.dumps(identity, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    payload = {
        "schema_version": 1,
        "household_id": str(binding.household_id),
        "resource_id": str(binding.resource_id),
        "capability_id": str(binding.capability_id),
        "mapping_version": binding.version,
        "source_route": "smartthings_ha_state",
        "reported_lock_state": reported.value,
        "state_quality": quality,
        "source_occurred_at": None,
        "source_time_status": "NOT_EXPOSED_BY_HA",
        "ha_updated_at": updated.isoformat() if updated else None,
        "ha_time_status": time_status,
        "anima_received_at": receipt.isoformat(),
        "time_basis": "HA_STATE_UPDATED" if updated else "ANIMA_RECEIPT",
        "ha_clock_ahead": updated > receipt if updated else False,
        "reported_profile_label": label,
        "reported_method": method,
        "identity_status": "REPORTED_UNVERIFIED" if label else "UNKNOWN",
        "identity_event_association": "UNVERIFIED_HA_CACHED_ATTRIBUTE",
        "identity_is_authentication": False,
        "canonical_person_id": None,
        "snapshot": snapshot,
        "dedup_basis": "HA_STATE_REVISION" if updated else "RECEIPT_ONLY",
    }
    return EventEnvelope.create(
        event_id=str(uuid5(NAMESPACE_URL, f"anima:tapo:observation:{digest}")),
        event_type="tapo.lock_observed",
        source=f"provider:smartthings_ha:{binding.ha_instance_id}",
        subject_key=f"resource/{binding.resource_id}",
        occurred_at=updated or receipt,
        recorded_at=receipt,
        source_event_id=f"ha-state-revision:{digest}" if updated else None,
        payload=payload,
        evidence_kind=EvidenceKind.DIRECT,
        confidence=None,
        metadata={
            "external_content_trust": "EXTERNAL_UNTRUSTED",
            "household_id": str(binding.household_id),
            "canonical_resource_ids": [str(binding.resource_id)],
            "snapshot": snapshot,
            "physical_operation_verified": False,
            "normalizer": "tapo.smartthings_ha.v1",
        },
    )
