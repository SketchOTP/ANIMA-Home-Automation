"""Observed-day receipt support is not event concentration or source coverage."""

from __future__ import annotations

from copy import deepcopy
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID, uuid4
from zoneinfo import ZoneInfo

import pytest

from anima_ha.household_forecasts import recurrence_plan
from anima_ha.household_patterns import extract_pattern_candidates

NOW = datetime(2026, 10, 3, tzinfo=UTC)
ZONE = ZoneInfo("UTC")
BASIS = "OBSERVED_DAY_SUPPORT_NOT_PROBABILITY"


def candidate(*, dense: bool = True, bucket_days: int = 8) -> dict[str, Any]:
    rows = []
    for day in range(1, 9):
        # Noon remains the same event-count-selected bucket, even when its
        # repeated receipts are concentrated on only a few observed days.
        hours = [1, 5, 9, 17, 21] if dense else [1]
        for hour in hours + ([12, 13, 14, 15] if day <= bucket_days else []):
            stamp = (NOW - timedelta(days=day)).replace(hour=hour)
            rows.append(
                {
                    "event_id": str(uuid4()),
                    "event_type": "household.ring.motion",
                    "canonical_id": "00000000-0000-0000-0000-000000000002",
                    "occurred_at": stamp.isoformat(),
                    "recorded_at": stamp.isoformat(),
                }
            )
    values = extract_pattern_candidates(rows, household_id=UUID(int=1), timezone=ZONE)
    return next(
        value.to_payload() for value in values if value.candidate_class == "RESOURCE_RECURRENCE"
    )


def test_daily_bucket_receipts_qualify_despite_dense_all_day_events() -> None:
    value = candidate()
    temporal = value["temporal_consistency"]
    assert temporal["ratio"] < 0.75 and temporal["dominant_local_window"] == "12:00-16:00"
    # Existing event concentration continues to determine maturity/score.
    assert value["maturity"] == "TENTATIVE_HYPOTHESIS"
    plan, reason = recurrence_plan(value, now=NOW, zone=ZONE)
    assert reason == "SUPPORTED_TEMPORAL_FORECAST" and plan is not None
    assert plan["temporal_features"]["observed_day_support"] == {
        "numerator": 8,
        "denominator": 8,
        "ratio": 1.0,
        "support_basis": BASIS,
    }
    assert plan["window_count"] == 3 and plan["predicts_occurrence"] is True


@pytest.mark.parametrize("bucket_days, supported", [(3, False), (5, False), (6, True)])
def test_event_dense_but_inconsistent_days_keep_same_threshold(
    bucket_days: int, supported: bool
) -> None:
    value = candidate(bucket_days=bucket_days)
    assert value["temporal_consistency"]["dominant_local_day_count"] == bucket_days
    plan, reason = recurrence_plan(value, now=NOW, zone=ZONE)
    assert (plan is not None) is supported
    assert reason == (
        "SUPPORTED_TEMPORAL_FORECAST" if supported else "INSUFFICIENT_MULTI_DAY_TEMPORAL_SUPPORT"
    )


def test_legacy_event_share_only_is_not_reinterpreted_as_day_support() -> None:
    value = candidate(dense=False)
    value["temporal_consistency"].pop("observed_day_support", None)
    assert value["temporal_consistency"]["ratio"] >= 0.75
    assert recurrence_plan(value, now=NOW, zone=ZONE)[0] is None


@pytest.mark.parametrize(
    "fields",
    [
        {"numerator": True},
        {"numerator": 8.0},
        {"numerator": -1},
        {"numerator": 9},
        {"numerator": 7},
        {"denominator": False},
        {"denominator": 0},
        {"denominator": "8"},
        {"denominator": 9},
        {"ratio": True},
        {"ratio": "1"},
        {"ratio": float("nan")},
        {"ratio": float("inf")},
        {"ratio": 0.75},
        {"support_basis": "PROBABILITY"},
    ],
)
def test_malformed_or_inconsistent_day_support_fails_closed(fields: dict[str, Any]) -> None:
    value = candidate()
    value["temporal_consistency"]["observed_day_support"].update(fields)
    assert recurrence_plan(value, now=NOW, zone=ZONE)[0] is None


@pytest.mark.parametrize(
    "key, malformed",
    [
        ("observation_count", True),
        ("distinct_day_count", 8.0),
        ("observation_count", 999),
        ("elapsed_hours", float("nan")),
        ("elapsed_hours", float("inf")),
    ],
)
def test_candidate_count_and_span_invariants_fail_closed(key: str, malformed: Any) -> None:
    value = candidate()
    value[key] = malformed
    assert recurrence_plan(value, now=NOW, zone=ZONE)[0] is None


@pytest.mark.parametrize(
    "key, malformed",
    [
        ("dominant_local_day_count", True),
        ("total_observations", 999),
        ("observations_in_window", 1),
    ],
)
def test_receipt_and_day_counts_must_be_consistent(key: str, malformed: Any) -> None:
    value = candidate()
    value["temporal_consistency"][key] = malformed
    assert recurrence_plan(value, now=NOW, zone=ZONE)[0] is None


def test_absent_or_non_mapping_support_fails_closed() -> None:
    value = candidate()
    malformed_supports: tuple[Any, ...] = (None, [], True, {})
    for support in malformed_supports:
        altered = deepcopy(value)
        altered["temporal_consistency"]["observed_day_support"] = support
        assert recurrence_plan(altered, now=NOW, zone=ZONE)[0] is None
