from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import uuid4
from zoneinfo import ZoneInfo

from anima_ha.household_patterns import (
    ROUTINE_EVIDENCE_THRESHOLD,
    candidate_digest,
    evidence_score,
    extract_pattern_candidates,
)


def event(at: datetime, *, event_type: str, resource: str, qualifier: str) -> dict[str, str]:
    return {
        "event_id": str(uuid4()),
        "event_type": event_type,
        "event_kind": qualifier,
        "occurred_at": at.isoformat(),
        "recorded_at": at.isoformat(),
        "canonical_id": resource,
    }


def test_evidence_strength_is_deterministic_and_separate_from_model_confidence() -> None:
    strong = evidence_score(41, 5, 87.8, 1.0)
    weak = evidence_score(3, 2, 24.0, 0.5)
    assert strong >= ROUTINE_EVIDENCE_THRESHOLD
    assert weak < ROUTINE_EVIDENCE_THRESHOLD
    assert strong == evidence_score(41, 5, 87.8, 1.0)


def test_candidate_extraction_is_deterministic_and_exposes_maturity_inputs() -> None:
    household, resource = uuid4(), str(uuid4())
    start = datetime(2026, 9, 1, 5, tzinfo=UTC)
    rows = [
        event(
            start + timedelta(days=day, minutes=day),
            event_type="external.android.lock_reported",
            resource=resource,
            qualifier="UNLOCKED",
        )
        for day in range(4)
    ]
    first = extract_pattern_candidates(
        rows, household_id=household, timezone=ZoneInfo("America/New_York")
    )
    second = extract_pattern_candidates(
        list(reversed(rows)), household_id=household, timezone=ZoneInfo("America/New_York")
    )
    assert [item.to_payload() for item in first] == [item.to_payload() for item in second]
    assert candidate_digest(first) == candidate_digest(second)
    candidate = first[0]
    assert candidate.observation_count == 4
    assert candidate.distinct_day_count == 4
    assert candidate.source_trust == "CORE_QUALIFIED_JOURNAL_PROJECTION"
    assert candidate.maturity == "TENTATIVE_HYPOTHESIS"
    assert 0 <= candidate.evidence_score <= 1
    assert "actor" in " ".join(candidate.missing_information).lower()


def test_sequence_never_claims_identity_or_causation() -> None:
    household, first_resource, second_resource = uuid4(), str(uuid4()), str(uuid4())
    start = datetime(2026, 9, 1, 12, tzinfo=UTC)
    rows: list[dict[str, str]] = []
    for day in range(3):
        rows.extend(
            [
                event(
                    start + timedelta(days=day),
                    event_type="household.ring.motion",
                    resource=first_resource,
                    qualifier="MOTION",
                ),
                event(
                    start + timedelta(days=day, minutes=2),
                    event_type="external.android.lock_reported",
                    resource=second_resource,
                    qualifier="UNLOCKED",
                ),
            ]
        )
    candidates = extract_pattern_candidates(rows, household_id=household, timezone=ZoneInfo("UTC"))
    sequence = next(item for item in candidates if item.candidate_class == "EVENT_SEQUENCE")
    gaps = " ".join(sequence.missing_information).lower()
    assert "causation" in gaps and "actor" in gaps
    assert sequence.maturity == "TENTATIVE_HYPOTHESIS"


def test_conflicting_qualified_observations_are_reported_not_resolved() -> None:
    household, resource = uuid4(), str(uuid4())
    start = datetime(2026, 9, 1, 12, tzinfo=UTC)
    rows = [
        event(
            start + timedelta(days=day),
            event_type="external.android.lock_reported",
            resource=resource,
            qualifier="LOCKED",
        )
        for day in range(2)
    ]
    rows.append(
        event(
            start,
            event_type="external.android.lock_reported",
            resource=resource,
            qualifier="UNLOCKED",
        )
    )
    candidates = extract_pattern_candidates(rows, household_id=household, timezone=ZoneInfo("UTC"))
    locked = next(item for item in candidates if item.candidate_key.endswith(":LOCKED"))
    assert locked.contradictory_evidence == ("conflicting_qualified_observations=1",)


def test_repeated_composite_episode_preserves_member_signal_and_event_order() -> None:
    household = uuid4()
    driveway, entry, logan = str(uuid4()), str(uuid4()), str(uuid4())
    unrelated_resources = [str(uuid4()) for _ in range(8)]
    start = datetime(2026, 9, 1, 5, 28, tzinfo=UTC)
    rows: list[dict[str, str]] = []
    for day in range(4):
        rows.extend(
            [
                {
                    **event(
                        start + timedelta(days=day),
                        event_type="external.android.motion_reported",
                        resource=driveway,
                        qualifier="MOTION_REPORTED",
                    ),
                    "source_family": "ANDROID_NOTIFICATION",
                },
                {
                    **event(
                        start + timedelta(days=day, minutes=1),
                        event_type="household.ring.motion",
                        resource=entry,
                        qualifier="MOTION",
                    ),
                    "source_family": "anima.ring",
                },
                {
                    **event(
                        start + timedelta(days=day, minutes=2),
                        event_type="household.presence.connection_changed",
                        resource=logan,
                        qualifier="RECONNECTED",
                    ),
                    "transition": "RECONNECTED",
                    "source_family": "anima.household_presence",
                },
            ]
        )
        rows.extend(
            event(
                start + timedelta(days=day, minutes=30),
                event_type="senseguard.opened",
                resource=resource,
                qualifier="OPENED",
            )
            for resource in unrelated_resources
        )

    candidates = extract_pattern_candidates(rows, household_id=household, timezone=ZoneInfo("UTC"))
    composite = next(item for item in candidates if item.candidate_class == "MULTI_SIGNAL_EPISODE")

    assert len(candidates) == 6
    assert composite.distinct_day_count == 4
    assert composite.observation_count == 4
    assert len(composite.source_event_ids) == 12
    assert composite.canonical_ids == tuple(sorted((driveway, entry, logan)))
    assert "not a verified person, arrival, departure, or cause" in composite.factual_summary
    assert composite.semantic_evidence is not None
    assert [item["event_type"] for item in composite.semantic_evidence["ordered_signals"]] == [
        "external.android.motion_reported",
        "household.ring.motion",
        "household.presence.connection_changed",
    ]
    presence = composite.semantic_evidence["ordered_signals"][-1]
    assert presence["member_association"] == "DEVICE_ASSOCIATED_WITH_MEMBER_NOT_AUTHENTICATED"
    assert composite.source_event_ids == tuple(
        row["event_id"]
        for row in rows
        if row["event_type"]
        in {
            "external.android.motion_reported",
            "household.ring.motion",
            "household.presence.connection_changed",
        }
    )


def test_departure_episode_uses_disconnected_direction_without_claiming_work_intent() -> None:
    household = uuid4()
    driveway, ring, member = str(uuid4()), str(uuid4()), str(uuid4())
    start = datetime(2026, 9, 1, 5, 25, tzinfo=UTC)
    rows: list[dict[str, str]] = []
    for day in range(3):
        rows.extend(
            [
                {
                    **event(
                        start + timedelta(days=day),
                        event_type="household.ring.motion",
                        resource=ring,
                        qualifier="MOTION",
                    ),
                    "source_family": "anima.ring",
                },
                {
                    **event(
                        start + timedelta(days=day, minutes=2),
                        event_type="external.android.motion_reported",
                        resource=driveway,
                        qualifier="MOTION_REPORTED",
                    ),
                    "source_family": "ANDROID_NOTIFICATION",
                },
                {
                    **event(
                        start + timedelta(days=day, minutes=4),
                        event_type="household.presence.connection_changed",
                        resource=member,
                        qualifier="DISCONNECTED",
                    ),
                    "transition": "DISCONNECTED",
                    "source_family": "anima.household_presence",
                },
            ]
        )
    composite = next(
        item
        for item in extract_pattern_candidates(
            rows, household_id=household, timezone=ZoneInfo("UTC")
        )
        if item.candidate_class == "MULTI_SIGNAL_EPISODE"
    )
    assert "disconnected" in composite.factual_summary
    assert "preparation for work" not in composite.factual_summary
    assert "not proof that the person acted" in " ".join(composite.missing_information)


def test_composite_episode_requires_cross_family_recurrence_and_marks_truncation() -> None:
    household, camera, window = uuid4(), str(uuid4()), str(uuid4())
    start = datetime(2026, 9, 1, 3, tzinfo=UTC)
    rows: list[dict[str, str]] = []
    for day in range(3):
        rows.extend(
            [
                {
                    **event(
                        start + timedelta(days=day),
                        event_type="external.android.motion_reported",
                        resource=str(camera),
                        qualifier="MOTION_REPORTED",
                    ),
                    "source_family": "ANDROID_NOTIFICATION",
                },
                {
                    **event(
                        start + timedelta(days=day, minutes=3),
                        event_type="senseguard.opened",
                        resource=str(window),
                        qualifier="OPENED",
                    ),
                    "source_family": "anima:senseguard-policy",
                },
            ]
        )
    candidate = next(
        item
        for item in extract_pattern_candidates(
            rows,
            household_id=household,
            timezone=ZoneInfo("UTC"),
            evidence_truncated=True,
        )
        if item.candidate_class == "MULTI_SIGNAL_EPISODE"
    )
    assert candidate.distinct_day_count == 3
    assert any("truncated" in item for item in candidate.missing_information)

    one_day = [item for item in rows if datetime.fromisoformat(item["occurred_at"]).date().day == 1]
    assert all(
        item.candidate_class != "MULTI_SIGNAL_EPISODE"
        for item in extract_pattern_candidates(
            one_day, household_id=household, timezone=ZoneInfo("UTC")
        )
    )
