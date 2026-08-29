"""ANIMA-owned immutable event and observation contracts.

These contracts deliberately contain no Home Assistant or provider-specific
fields.  They are the boundary between sources and the canonical journal.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from enum import StrEnum
from typing import Any

SUPPORTED_EVENT_SCHEMA_VERSION = 1


class UnsupportedEventSchema(ValueError):
    """Raised when an event schema cannot be interpreted safely."""


class EventImportance(StrEnum):
    LOW = "LOW"
    NORMAL = "NORMAL"
    IMPORTANT = "IMPORTANT"
    CRITICAL = "CRITICAL"


class DeliveryClass(StrEnum):
    BEST_EFFORT = "BEST_EFFORT"
    GUARANTEED = "GUARANTEED"


class EvidenceKind(StrEnum):
    DIRECT = "DIRECT"
    INFERRED = "INFERRED"
    UNKNOWN = "UNKNOWN"
    UNAVAILABLE = "UNAVAILABLE"


class ObservationState(StrEnum):
    KNOWN = "KNOWN"
    UNKNOWN = "UNKNOWN"
    UNAVAILABLE = "UNAVAILABLE"


def _utc(value: datetime, field_name: str) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{field_name} must be timezone-aware")
    return value.astimezone(UTC)


def _json_value(value: Any) -> Any:
    """Validate that a value can cross the JSON/PostgreSQL boundary."""

    json.dumps(value, sort_keys=True, separators=(",", ":"))
    return value


@dataclass(frozen=True, slots=True)
class EventEnvelope:
    """Normalized, immutable event envelope retained by the event journal."""

    event_id: str
    schema_version: int
    event_type: str
    source: str
    subject_key: str
    occurred_at: datetime
    recorded_at: datetime
    payload: dict[str, Any]
    source_event_id: str | None = None
    source_sequence: int | None = None
    correlation_id: str | None = None
    causation_id: str | None = None
    confidence: float | None = None
    evidence_kind: EvidenceKind = EvidenceKind.DIRECT
    importance: EventImportance = EventImportance.NORMAL
    delivery_class: DeliveryClass = DeliveryClass.BEST_EFFORT
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        for name in ("event_id", "event_type", "source", "subject_key"):
            if not getattr(self, name).strip():
                raise ValueError(f"{name} must not be empty")
        if self.schema_version < 1:
            raise ValueError("schema_version must be positive")
        if self.schema_version > SUPPORTED_EVENT_SCHEMA_VERSION:
            raise UnsupportedEventSchema(
                f"event schema {self.schema_version} is unsupported; "
                f"supported={SUPPORTED_EVENT_SCHEMA_VERSION}"
            )
        if self.source_sequence is not None and self.source_sequence < 0:
            raise ValueError("source_sequence must not be negative")
        if self.confidence is not None and not 0 <= self.confidence <= 1:
            raise ValueError("confidence must be between 0 and 1")
        object.__setattr__(self, "occurred_at", _utc(self.occurred_at, "occurred_at"))
        object.__setattr__(self, "recorded_at", _utc(self.recorded_at, "recorded_at"))
        _json_value(self.payload)
        _json_value(self.metadata)

    @classmethod
    def create(
        cls,
        *,
        event_id: str,
        event_type: str,
        source: str,
        subject_key: str,
        occurred_at: datetime,
        payload: dict[str, Any],
        recorded_at: datetime | None = None,
        **kwargs: Any,
    ) -> EventEnvelope:
        return cls(
            event_id=event_id,
            schema_version=SUPPORTED_EVENT_SCHEMA_VERSION,
            event_type=event_type,
            source=source,
            subject_key=subject_key,
            occurred_at=occurred_at,
            recorded_at=recorded_at or datetime.now(UTC),
            payload=payload,
            **kwargs,
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "event_id": self.event_id,
            "schema_version": self.schema_version,
            "event_type": self.event_type,
            "source": self.source,
            "source_event_id": self.source_event_id,
            "subject_key": self.subject_key,
            "occurred_at": self.occurred_at.isoformat(),
            "recorded_at": self.recorded_at.isoformat(),
            "source_sequence": self.source_sequence,
            "correlation_id": self.correlation_id,
            "causation_id": self.causation_id,
            "confidence": self.confidence,
            "evidence_kind": self.evidence_kind.value,
            "importance": self.importance.value,
            "delivery_class": self.delivery_class.value,
            "payload": self.payload,
            "metadata": self.metadata,
        }


@dataclass(frozen=True, slots=True)
class TruthObservation:
    """A provenance-bearing observation of a generic truth key."""

    truth_key: str
    source: str
    observed_at: datetime
    received_at: datetime
    state: ObservationState = ObservationState.KNOWN
    value: Any = None
    source_sequence: int | None = None
    confidence: float | None = None
    evidence_kind: EvidenceKind = EvidenceKind.DIRECT
    freshness_seconds: int | None = None
    event_id: str | None = None
    journal_position: int | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.truth_key.strip() or not self.source.strip():
            raise ValueError("truth_key and source must not be empty")
        state = ObservationState(self.state)
        evidence_kind = EvidenceKind(self.evidence_kind)
        object.__setattr__(self, "state", state)
        object.__setattr__(self, "evidence_kind", evidence_kind)
        if state != ObservationState.KNOWN and self.value is not None:
            raise ValueError("unknown and unavailable observations cannot have a value")
        if self.source_sequence is not None and self.source_sequence < 0:
            raise ValueError("source_sequence must not be negative")
        if self.confidence is not None and not 0 <= self.confidence <= 1:
            raise ValueError("confidence must be between 0 and 1")
        if self.freshness_seconds is not None and self.freshness_seconds < 0:
            raise ValueError("freshness_seconds must not be negative")
        object.__setattr__(self, "observed_at", _utc(self.observed_at, "observed_at"))
        object.__setattr__(self, "received_at", _utc(self.received_at, "received_at"))
        _json_value(self.value)
        _json_value(self.metadata)

    @property
    def expires_at(self) -> datetime | None:
        if self.freshness_seconds is None:
            return None
        return self.observed_at + timedelta(seconds=self.freshness_seconds)

    def to_payload(self) -> dict[str, Any]:
        return {
            "truth_key": self.truth_key,
            "source": self.source,
            "observed_at": self.observed_at.isoformat(),
            "received_at": self.received_at.isoformat(),
            "state": self.state.value,
            "value": self.value,
            "source_sequence": self.source_sequence,
            "confidence": self.confidence,
            "evidence_kind": self.evidence_kind.value,
            "freshness_seconds": self.freshness_seconds,
            "metadata": self.metadata,
        }

    @classmethod
    def from_payload(
        cls,
        payload: dict[str, Any],
        *,
        event_id: str | None = None,
        journal_position: int | None = None,
    ) -> TruthObservation:
        return cls(
            truth_key=str(payload["truth_key"]),
            source=str(payload["source"]),
            observed_at=datetime.fromisoformat(str(payload["observed_at"])),
            received_at=datetime.fromisoformat(str(payload["received_at"])),
            state=ObservationState(str(payload.get("state", ObservationState.KNOWN))),
            value=payload.get("value"),
            source_sequence=payload.get("source_sequence"),
            confidence=payload.get("confidence"),
            evidence_kind=EvidenceKind(str(payload.get("evidence_kind", EvidenceKind.DIRECT))),
            freshness_seconds=payload.get("freshness_seconds"),
            event_id=event_id,
            journal_position=journal_position,
            metadata=dict(payload.get("metadata", {})),
        )
