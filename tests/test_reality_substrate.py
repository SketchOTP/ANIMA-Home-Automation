from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime, timedelta

import pytest

from anima_ha.events import (
    EventEnvelope,
    EvidenceKind,
    ObservationState,
    TruthObservation,
    UnsupportedEventSchema,
)
from anima_ha.truth import InMemoryTruthState, TruthReconciler, TruthStatus

BASE = datetime(2026, 8, 29, 12, 0, tzinfo=UTC)


def observation(
    source: str,
    value: object = None,
    *,
    observed_at: datetime = BASE,
    sequence: int | None = None,
    state: ObservationState = ObservationState.KNOWN,
    freshness: int | None = None,
    event_id: str | None = None,
) -> TruthObservation:
    return TruthObservation(
        truth_key="home/lab/temperature",
        source=source,
        value=value,
        state=state,
        observed_at=observed_at,
        received_at=observed_at + timedelta(seconds=1),
        source_sequence=sequence,
        freshness_seconds=freshness,
        event_id=event_id,
    )


def event(event_id: str = "e-1", *, schema_version: int = 1) -> EventEnvelope:
    return EventEnvelope(
        event_id=event_id,
        schema_version=schema_version,
        event_type="truth.observation",
        source="simulator",
        subject_key="home/lab/temperature",
        occurred_at=BASE,
        recorded_at=BASE + timedelta(seconds=2),
        payload=observation("simulator", 21, event_id=event_id).to_payload(),
    )


def test_event_envelope_separates_occurrence_and_record_time() -> None:
    assert event().occurred_at < event().recorded_at
    assert event().to_dict()["schema_version"] == 1


def test_duplicate_values_from_multiple_sources_are_corrobation_not_conflict() -> None:
    result = TruthReconciler().resolve(
        "home/lab/temperature",
        [observation("sensor-a", 21), observation("sensor-b", 21)],
        now=BASE + timedelta(seconds=10),
    )
    assert result.status == TruthStatus.CURRENT_KNOWN
    assert result.value == 21
    assert not result.conflict_candidates


def test_contradictory_sources_remain_visible_as_conflict() -> None:
    result = TruthReconciler().resolve(
        "home/lab/temperature",
        [observation("sensor-a", 21), observation("sensor-b", 22)],
        now=BASE + timedelta(seconds=10),
    )
    assert result.status == TruthStatus.CONFLICTING
    assert result.value is None
    assert {item.value for item in result.conflict_candidates} == {21, 22}


def test_out_of_order_observation_does_not_replace_newer_sequence() -> None:
    state = InMemoryTruthState()
    state.add(observation("sensor-a", 22, sequence=2, event_id="new"))
    result = state.add(observation("sensor-a", 20, sequence=1, event_id="old"))
    assert result.status == TruthStatus.CURRENT_KNOWN
    assert result.value == 22


def test_unknown_unavailable_and_stale_are_explicit() -> None:
    reconciler = TruthReconciler()
    unknown = reconciler.resolve(
        "home/lab/temperature", [observation("sensor", state=ObservationState.UNKNOWN)], now=BASE
    )
    unavailable = reconciler.resolve(
        "home/lab/temperature",
        [observation("sensor", state=ObservationState.UNAVAILABLE)],
        now=BASE,
    )
    stale = reconciler.resolve(
        "home/lab/temperature",
        [observation("sensor", 21, freshness=1)],
        now=BASE + timedelta(seconds=2),
    )
    assert unknown.status == TruthStatus.UNKNOWN
    assert unavailable.status == TruthStatus.UNAVAILABLE
    assert stale.status == TruthStatus.STALE
    assert stale.value == 21


def test_inferred_evidence_is_preserved_but_direct_correspondence_wins() -> None:
    inferred = observation("model", 21)
    direct = observation("sensor", 21)
    inferred = replace(inferred, evidence_kind=EvidenceKind.INFERRED)
    result = TruthReconciler().resolve("home/lab/temperature", [inferred, direct], now=BASE)
    assert result.evidence_kind == EvidenceKind.DIRECT


def test_unsupported_event_schema_fails_explicitly() -> None:
    with pytest.raises(UnsupportedEventSchema):
        EventEnvelope(
            event_id="bad",
            schema_version=99,
            event_type="truth.observation",
            source="simulator",
            subject_key="home/lab/temperature",
            occurred_at=BASE,
            recorded_at=BASE,
            payload={},
        )
