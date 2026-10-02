"""Pure, bounded shadow scoring; source coverage is evidence, not an assumption.

Fixed timer windows include negative opportunities. Correlated/retried receipt
records are not independent trials. No output here authorizes execution.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any


def score_window(
    *,
    start: datetime,
    end: datetime,
    frozen_at: datetime,
    closed_at: datetime,
    event_type: str,
    canonical_id: str,
    predicts_occurrence: bool,
    events: list[dict[str, Any]],
    coverage: dict[str, Any],
    truncated: bool,
    event_qualifier: str | None = None,
) -> dict[str, Any]:
    observed: dict[str, dict[str, Any]] = {}
    late = 0
    uncertain = 0
    for event in events:
        if event.get("event_type") != event_type or event.get("canonical_id") != canonical_id:
            continue
        if (
            event_qualifier
            and str(
                event.get("event_kind") or event.get("transition") or event_type.rsplit(".", 1)[-1]
            ).upper()
            != event_qualifier
        ):
            continue
        occurred = datetime.fromisoformat(event["occurred_at"])
        recorded = datetime.fromisoformat(event["recorded_at"])
        if occurred.tzinfo is None or recorded.tzinfo is None or event.get("clock_uncertain"):
            uncertain += 1
            continue
        if not start <= occurred < end:
            continue
        if recorded < occurred or recorded > closed_at or recorded < frozen_at:
            late += 1
            continue
        # Qualified source identity, not text/time similarity. Multiple receipts
        # can establish occurrence, never an independent corroboration count.
        observed[event["event_id"]] = event
    complete_coverage = (
        coverage.get("status") == "COMPLETE"
        and coverage.get("basis") == "QUALIFIED_SOURCE_INTERVAL"
        and coverage.get("start") == start.isoformat()
        and coverage.get("end") == end.isoformat()
        and not truncated
        and not late
        and not uncertain
        and not any(
            coverage.get(flag)
            for flag in ("stale", "clock_uncertain", "lost_coverage", "truncated")
        )
    )
    # A canonical qualified receipt proves an observed positive, not physical
    # identity/time or complete coverage. Missing events require a proven
    # interval; heartbeat, process health and silence never supply that proof.
    positive = bool(observed)
    qualified = positive or complete_coverage
    actual = positive if qualified else None
    return {
        "start": start.isoformat(),
        "end": end.isoformat(),
        "eligible_opportunities": 1,
        "coverage": "QUALIFIED" if complete_coverage else "UNKNOWN",
        "observed_receipt_ids": sorted(observed)[:12],
        "observed_receipt_count": len(observed),
        "physical_occurrence_at": None,
        "predicts_occurrence": predicts_occurrence,
        "outcome_basis": "QUALIFIED_POSITIVE_SOURCE_RECEIPT"
        if positive
        else "QUALIFIED_SOURCE_INTERVAL_NO_RECEIPT"
        if complete_coverage
        else "INSUFFICIENT_SOURCE_COVERAGE",
        "unknown": not qualified,
        "late_records": late,
        "clock_uncertain_records": uncertain,
        "coverage_faults": [
            flag
            for flag in ("stale", "clock_uncertain", "lost_coverage", "truncated")
            if coverage.get(flag)
        ],
        "truncated": truncated,
        "observed_occurrence": actual,
        "prediction_correct": predicts_occurrence == actual if qualified else None,
        "miss": predicts_occurrence != actual if qualified else None,
        "miss_kind": "UNPREDICTED_SOURCE_RECEIPT"
        if positive and not predicts_occurrence
        else "PREDICTED_RECEIPT_NOT_OBSERVED"
        if complete_coverage and not positive and predicts_occurrence
        else None,
        "baseline_correct": not actual if qualified else None,
    }
