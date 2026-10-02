"""Source-derived prospective plans, not execution or measured probability.

Only an identified resource's repeated local time bucket supports this small
forecast. Sequences without a qualified future trigger remain insufficient.
The comparator always predicts no receipt in the SAME selected opportunities;
we do not manufacture contrast trials from historical silence.
"""

from __future__ import annotations

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
    temporal = candidate["temporal_consistency"]
    if (
        candidate["observation_count"] < 5
        or candidate["distinct_day_count"] < 3
        or candidate["elapsed_hours"] < 48
        or temporal["ratio"] < 0.75
        or temporal.get("dominant_local_day_count", 0) < 3
    ):
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
