"""A declared coverage/clock fault cannot manufacture a negative trial."""

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest

from anima_ha.household_shadow import score_window

NOW = datetime(2026, 10, 2, tzinfo=UTC)


@pytest.mark.parametrize("flag", ["stale", "clock_uncertain", "lost_coverage", "truncated"])
def test_declared_interval_fault_cannot_create_negative_accuracy(flag: str) -> None:
    start, end = NOW + timedelta(days=1), NOW + timedelta(days=1, hours=4)
    result = score_window(
        start=start,
        end=end,
        frozen_at=NOW,
        closed_at=end + timedelta(minutes=1),
        event_type="senseguard.opened",
        canonical_id=str(uuid4()),
        predicts_occurrence=True,
        events=[],
        truncated=False,
        coverage={
            "status": "COMPLETE",
            "basis": "QUALIFIED_SOURCE_INTERVAL",
            "start": start.isoformat(),
            "end": end.isoformat(),
            flag: True,
        },
    )
    assert result["unknown"] and result["miss"] is None and result["baseline_correct"] is None


@pytest.mark.parametrize("naive", [False, True])
def test_source_clock_fault_is_not_a_qualified_future_receipt(naive: bool) -> None:
    start, end = NOW + timedelta(days=1), NOW + timedelta(days=1, hours=4)
    canonical = str(uuid4())
    stamp = start.replace(tzinfo=None).isoformat() if naive else start.isoformat()
    result = score_window(
        start=start,
        end=end,
        frozen_at=NOW,
        closed_at=end + timedelta(minutes=1),
        event_type="senseguard.opened",
        canonical_id=canonical,
        predicts_occurrence=True,
        events=[
            {
                "event_id": str(uuid4()),
                "event_type": "senseguard.opened",
                "canonical_id": canonical,
                "occurred_at": stamp,
                "recorded_at": stamp,
                "clock_uncertain": True,
            }
        ],
        truncated=False,
        coverage={"status": "UNKNOWN"},
    )
    assert result["unknown"] and result["prediction_correct"] is None
