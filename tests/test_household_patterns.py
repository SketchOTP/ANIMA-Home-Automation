from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import uuid4
from zoneinfo import ZoneInfo

from anima_ha.household_patterns import candidate_digest, extract_pattern_candidates


def event(at: datetime, *, event_type: str, resource: str, qualifier: str) -> dict[str, str]:
    return {
        "event_id": str(uuid4()),
        "event_type": event_type,
        "event_kind": qualifier,
        "occurred_at": at.isoformat(),
        "recorded_at": at.isoformat(),
        "canonical_id": resource,
    }


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
