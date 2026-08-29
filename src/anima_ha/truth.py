"""Deterministic truth observation reconciliation and query contracts."""

from __future__ import annotations

import json
from collections.abc import Iterable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any

from anima_ha.events import EvidenceKind, ObservationState, TruthObservation


class TruthStatus(StrEnum):
    CURRENT_KNOWN = "CURRENT/KNOWN"
    STALE = "STALE"
    UNKNOWN = "UNKNOWN"
    UNAVAILABLE = "UNAVAILABLE"
    CONFLICTING = "CONFLICTING"


@dataclass(frozen=True, slots=True)
class TruthResolution:
    truth_key: str
    status: TruthStatus
    value: Any = None
    observations: tuple[TruthObservation, ...] = ()
    conflict_candidates: tuple[TruthObservation, ...] = ()
    confidence: float | None = None
    evidence_kind: EvidenceKind | None = None
    last_observed_at: datetime | None = None
    last_received_at: datetime | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "truth_key": self.truth_key,
            "status": self.status.value,
            "value": self.value,
            "confidence": self.confidence,
            "evidence_kind": self.evidence_kind.value if self.evidence_kind else None,
            "last_observed_at": self.last_observed_at.isoformat()
            if self.last_observed_at
            else None,
            "last_received_at": self.last_received_at.isoformat()
            if self.last_received_at
            else None,
            "observations": [observation.to_payload() for observation in self.observations],
            "conflict_candidates": [
                observation.to_payload() for observation in self.conflict_candidates
            ],
        }


def _value_key(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)


def _precedence_key(observation: TruthObservation) -> tuple[Any, ...]:
    """Source sequence dominates arrival order when a source supplies one."""

    if observation.source_sequence is not None:
        return (1, observation.source_sequence)
    return (0, observation.observed_at)


def _ordering_key(observation: TruthObservation) -> tuple[Any, ...]:
    return (*_precedence_key(observation), observation.received_at, observation.event_id or "")


class TruthReconciler:
    """Pure deterministic reducer; it performs no I/O or external side effects."""

    def resolve(
        self,
        truth_key: str,
        observations: Iterable[TruthObservation],
        *,
        now: datetime | None = None,
    ) -> TruthResolution:
        current_time = (now or datetime.now(UTC)).astimezone(UTC)
        matching = [
            observation for observation in observations if observation.truth_key == truth_key
        ]
        by_source: dict[str, list[TruthObservation]] = {}
        for observation in matching:
            by_source.setdefault(observation.source, []).append(observation)

        latest: list[TruthObservation] = []
        for source_observations in by_source.values():
            maximum = max(_precedence_key(observation) for observation in source_observations)
            latest.extend(
                observation
                for observation in source_observations
                if _precedence_key(observation) == maximum
            )
        latest.sort(key=lambda observation: (observation.source, _ordering_key(observation)))

        known = [
            observation for observation in latest if observation.state == ObservationState.KNOWN
        ]
        last_observed = max((item.observed_at for item in latest), default=None)
        last_received = max((item.received_at for item in latest), default=None)
        if known:
            distinct = {_value_key(item.value) for item in known}
            if len(distinct) > 1:
                return TruthResolution(
                    truth_key=truth_key,
                    status=TruthStatus.CONFLICTING,
                    observations=tuple(latest),
                    conflict_candidates=tuple(known),
                    confidence=min(
                        (item.confidence for item in known if item.confidence is not None),
                        default=None,
                    ),
                    last_observed_at=last_observed,
                    last_received_at=last_received,
                )

            representative = max(
                known,
                key=lambda item: (
                    item.confidence is not None,
                    item.confidence or 0,
                    item.evidence_kind == EvidenceKind.DIRECT,
                    item.source,
                ),
            )
            expired = all(
                item.expires_at is not None and item.expires_at < current_time for item in known
            )
            return TruthResolution(
                truth_key=truth_key,
                status=TruthStatus.STALE if expired else TruthStatus.CURRENT_KNOWN,
                value=representative.value,
                observations=tuple(latest),
                confidence=representative.confidence,
                evidence_kind=(
                    EvidenceKind.DIRECT
                    if any(item.evidence_kind == EvidenceKind.DIRECT for item in known)
                    else representative.evidence_kind
                ),
                last_observed_at=last_observed,
                last_received_at=last_received,
            )

        status = (
            TruthStatus.UNAVAILABLE
            if any(item.state == ObservationState.UNAVAILABLE for item in latest)
            else TruthStatus.UNKNOWN
        )
        return TruthResolution(
            truth_key=truth_key,
            status=status,
            observations=tuple(latest),
            last_observed_at=last_observed,
            last_received_at=last_received,
        )


@dataclass(slots=True)
class InMemoryTruthState:
    """Small simulator/test store using the same reducer as PostgreSQL."""

    observations: list[TruthObservation] = field(default_factory=list)
    reconciler: TruthReconciler = field(default_factory=TruthReconciler)

    def add(self, observation: TruthObservation) -> TruthResolution:
        self.observations.append(observation)
        return self.get(observation.truth_key)

    def get(self, truth_key: str, *, now: datetime | None = None) -> TruthResolution:
        return self.reconciler.resolve(truth_key, self.observations, now=now)
