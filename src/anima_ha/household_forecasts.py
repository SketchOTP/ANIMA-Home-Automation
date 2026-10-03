"""Source-derived prospective plans, not execution or measured probability.

Only an identified resource's repeated local time bucket supports this small
forecast. Sequences without a qualified future trigger remain insufficient.
The comparator always predicts no receipt in the SAME selected opportunities;
we do not manufacture contrast trials from historical silence.
"""

from __future__ import annotations

import math
from datetime import UTC, datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo


def recurrence_plan(
    candidate: dict[str, Any], *, now: datetime, zone: ZoneInfo
) -> tuple[dict[str, Any] | None, str]:
    if candidate.get("candidate_class") != "RESOURCE_RECURRENCE":
        return None, "NO_QUALIFIED_FUTURE_SEQUENCE_TRIGGER"
    if candidate.get("source_trust") != "CORE_QUALIFIED_JOURNAL_PROJECTION":
        return None, "UNQUALIFIED_CANDIDATE"
    if candidate.get("contradictory_evidence"):
        return None, "CONTRADICTORY_SOURCE_EVIDENCE"
    temporal = candidate.get("temporal_consistency")
    if not isinstance(temporal, dict):
        return None, "INVALID_OBSERVED_DAY_SUPPORT"
    observations: Any = candidate.get("observation_count")
    days: Any = candidate.get("distinct_day_count")
    elapsed: Any = candidate.get("elapsed_hours")
    if (
        type(observations) is not int
        or type(days) is not int
        or type(elapsed) not in (int, float)
        or not math.isfinite(elapsed)
    ):
        return None, "INVALID_OBSERVED_DAY_SUPPORT"
    if observations < 5 or days < 3 or elapsed < 48:
        return None, "INSUFFICIENT_MULTI_DAY_TEMPORAL_SUPPORT"
    support = temporal.get("observed_day_support")
    if not isinstance(support, dict):
        # Historical event-share-only packets cannot acquire new day support.
        return None, "INVALID_OBSERVED_DAY_SUPPORT"
    numerator: Any = support.get("numerator")
    denominator: Any = support.get("denominator")
    ratio: Any = support.get("ratio")
    bucket_days: Any = temporal.get("dominant_local_day_count")
    bucket_receipts: Any = temporal.get("observations_in_window")
    total_receipts: Any = temporal.get("total_observations")
    if (
        support.get("support_basis") != "OBSERVED_DAY_SUPPORT_NOT_PROBABILITY"
        or any(
            type(value) is not int
            for value in (numerator, denominator, bucket_days, bucket_receipts, total_receipts)
        )
        or not 0 <= numerator <= denominator == days <= observations
        or numerator != bucket_days
        or not numerator <= bucket_receipts <= total_receipts == observations
        or type(ratio) not in (int, float)
        or not math.isfinite(ratio)
        or not math.isclose(ratio, numerator / denominator, rel_tol=0, abs_tol=1e-12)
    ):
        return None, "INVALID_OBSERVED_DAY_SUPPORT"
    # The forecast predicts >=1 receipt per daily window, not the fraction of
    # all individual receipts concentrated there. Do not round at the gate.
    if numerator < 3 or 4 * numerator < 3 * denominator:
        return None, "INSUFFICIENT_MULTI_DAY_TEMPORAL_SUPPORT"
    end = datetime.fromisoformat(candidate["evidence_window"]["end"])
    if end > now or now - end > timedelta(days=2):
        return None, "STALE_OR_FUTURE_SOURCE_CLOCK"
    _, event_type, canonical_id, qualifier = candidate["candidate_key"].split(":", 3)
    hour = int(temporal["dominant_local_window"][:2])
    windows = []
    for offset in range(1, 4):
        local = datetime.combine(
            now.astimezone(zone).date() + timedelta(days=offset),
            datetime.min.time(),
            tzinfo=zone,
        ) + timedelta(hours=hour)
        finish = local + timedelta(hours=4)
        # DST wall-clock buckets are converted individually, never shifted by
        # an assumed 24h interval. Each opportunity is frozen explicitly.
        windows.append(
            {"start": local.astimezone(UTC).isoformat(), "end": finish.astimezone(UTC).isoformat()}
        )
    return {
        "canonical_id": canonical_id,
        "event_type": event_type,
        "event_qualifier": qualifier,
        "predicts_occurrence": True,
        "starts_at": windows[0]["start"],
        "window_seconds": 14400,
        "window_count": len(windows),
        "opportunities": windows,
        "timezone": zone.key,
        "temporal_features": temporal,
        "basis": "REPEATED_LOCAL_SOURCE_RECEIPT_BUCKET",
        "uncertainty": "Tentative recurrence, not daily certainty, occupancy or physical time. "
        "Missing interval coverage cannot prove a missed prediction.",
    }, "SUPPORTED_TEMPORAL_FORECAST"
