"""Deterministic, provenance-retaining household pattern candidates.

Candidates are review inputs, never Truth, identity, policy, or executable
routines.  Missing observations are reported as coverage gaps rather than
treated as evidence that an event did not happen.
"""

from __future__ import annotations

import hashlib
import json
from collections import Counter, defaultdict
from dataclasses import asdict, dataclass
from datetime import datetime
from typing import Any
from uuid import UUID, uuid5
from zoneinfo import ZoneInfo

PATTERN_NAMESPACE = UUID("bc23b402-7872-4cc7-ae67-d35f6f3cd568")
MAX_CANDIDATES = 6
MAX_SOURCE_REFS = 12


def _stamp(value: str) -> datetime:
    parsed = datetime.fromisoformat(value)
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError("pattern evidence time must be aware")
    return parsed


@dataclass(frozen=True, slots=True)
class PatternCandidate:
    candidate_id: str
    candidate_key: str
    candidate_class: str
    title: str
    factual_summary: str
    evidence_window: dict[str, str]
    source_event_ids: tuple[str, ...]
    observation_count: int
    distinct_day_count: int
    elapsed_hours: float
    temporal_consistency: dict[str, Any]
    supporting_evidence: tuple[str, ...]
    contradictory_evidence: tuple[str, ...]
    missing_information: tuple[str, ...]
    source_trust: str
    maturity: str
    canonical_ids: tuple[str, ...]

    def to_payload(self) -> dict[str, Any]:
        value = asdict(self)
        for key in (
            "source_event_ids",
            "supporting_evidence",
            "contradictory_evidence",
            "missing_information",
            "canonical_ids",
        ):
            value[key] = list(value[key])
        return value


def _event_qualifier(item: dict[str, Any]) -> str:
    for key in ("event_kind", "transition"):
        value = item.get(key)
        if isinstance(value, str) and value:
            return value.upper()
    return str(item["event_type"]).rsplit(".", 1)[-1].upper()


def _maturity(count: int, days: int, elapsed_hours: float, consistency: float) -> str:
    if count >= 5 and days >= 3 and elapsed_hours >= 48 and consistency >= 0.5:
        return "LEARNED_ROUTINE_ELIGIBLE"
    if count >= 3 and days >= 2:
        return "TENTATIVE_HYPOTHESIS"
    if count >= 2:
        return "SUPPORTED_OBSERVATION"
    return "INSUFFICIENT_EVIDENCE"


def extract_pattern_candidates(
    items: list[dict[str, Any]],
    *,
    household_id: UUID,
    timezone: ZoneInfo,
    max_candidates: int = MAX_CANDIDATES,
) -> list[PatternCandidate]:
    """Extract bounded recurrence and sequence candidates from qualified rows."""
    if not 1 <= max_candidates <= MAX_CANDIDATES:
        raise ValueError("candidate bound must be 1..6")
    unique = {str(row["event_id"]): row for row in items}
    ordered = sorted(unique.values(), key=lambda row: (_stamp(row["occurred_at"]), row["event_id"]))
    if not ordered:
        return []
    all_days = {
        _stamp(item["occurred_at"]).astimezone(timezone).date().isoformat() for item in ordered
    }
    candidates: list[PatternCandidate] = []
    groups: dict[tuple[str, str, str], list[dict[str, Any]]] = defaultdict(list)
    observations_at: dict[tuple[str, str, str], set[str]] = defaultdict(set)
    for item in ordered:
        qualifier = _event_qualifier(item)
        groups[(item["event_type"], item["canonical_id"], qualifier)].append(item)
        observations_at[(item["event_type"], item["canonical_id"], item["occurred_at"])].add(
            qualifier
        )
    for (event_type, canonical_id, qualifier), rows in groups.items():
        if len(rows) < 2:
            continue
        times = [_stamp(row["occurred_at"]).astimezone(timezone) for row in rows]
        days = {value.date().isoformat() for value in times}
        buckets = Counter((value.hour // 4) * 4 for value in times)
        dominant_start, dominant_count = buckets.most_common(1)[0]
        consistency = dominant_count / len(times)
        elapsed = (max(times) - min(times)).total_seconds() / 3600
        key = f"recurrence:{event_type}:{canonical_id}:{qualifier}"
        candidate_id = str(uuid5(PATTERN_NAMESPACE, f"{household_id}:{key}"))
        missing = (
            [
                f"No qualified observations on {len(all_days - days)} covered local day(s); "
                "absence is not negative evidence."
            ]
            if all_days - days
            else []
        )
        maturity = _maturity(len(rows), len(days), elapsed, consistency)
        conflicting_slots = sum(
            1
            for row in rows
            if len(observations_at[(event_type, canonical_id, row["occurred_at"])]) > 1
        )
        candidates.append(
            PatternCandidate(
                candidate_id=candidate_id,
                candidate_key=key,
                candidate_class="RESOURCE_RECURRENCE",
                title=f"Repeated {qualifier.lower()} observations",
                factual_summary=(
                    f"{len(rows)} qualified {qualifier.lower()} observations were recorded for "
                    f"one canonical resource across {len(days)} local day(s)."
                ),
                evidence_window={
                    "start": min(times).isoformat(),
                    "end": max(times).isoformat(),
                    "timezone": timezone.key,
                },
                source_event_ids=tuple(row["event_id"] for row in rows[-MAX_SOURCE_REFS:]),
                observation_count=len(rows),
                distinct_day_count=len(days),
                elapsed_hours=round(elapsed, 3),
                temporal_consistency={
                    "dominant_local_window": (
                        f"{dominant_start:02d}:00-{(dominant_start + 4) % 24:02d}:00"
                    ),
                    "observations_in_window": dominant_count,
                    "total_observations": len(rows),
                    "ratio": round(consistency, 3),
                },
                supporting_evidence=(
                    f"count={len(rows)}",
                    f"distinct_local_days={len(days)}",
                    f"elapsed_hours={round(elapsed, 3)}",
                ),
                contradictory_evidence=(
                    (f"conflicting_qualified_observations={conflicting_slots}",)
                    if conflicting_slots
                    else ()
                ),
                missing_information=tuple(missing + ["The observations do not identify an actor."]),
                source_trust="CORE_QUALIFIED_JOURNAL_PROJECTION",
                maturity=maturity,
                canonical_ids=(canonical_id,),
            )
        )

    sequence_groups: dict[tuple[str, str], list[tuple[dict[str, Any], dict[str, Any]]]] = (
        defaultdict(list)
    )
    for first, second in zip(ordered, ordered[1:], strict=False):
        gap = (_stamp(second["occurred_at"]) - _stamp(first["occurred_at"])).total_seconds()
        if 0 <= gap <= 600 and first["event_id"] != second["event_id"]:
            sequence_groups[(first["event_type"], second["event_type"])].append((first, second))
    for (first_type, second_type), pairs in sequence_groups.items():
        days = {
            _stamp(first["occurred_at"]).astimezone(timezone).date().isoformat()
            for first, _ in pairs
        }
        if len(pairs) < 2 or len(days) < 2:
            continue
        event_ids = list(dict.fromkeys(event["event_id"] for pair in pairs for event in pair))[
            -MAX_SOURCE_REFS:
        ]
        starts = [_stamp(first["occurred_at"]).astimezone(timezone) for first, _ in pairs]
        ends = [_stamp(second["occurred_at"]).astimezone(timezone) for _, second in pairs]
        elapsed = (max(ends) - min(starts)).total_seconds() / 3600
        key = f"sequence:{first_type}:{second_type}"
        candidates.append(
            PatternCandidate(
                candidate_id=str(uuid5(PATTERN_NAMESPACE, f"{household_id}:{key}")),
                candidate_key=key,
                candidate_class="EVENT_SEQUENCE",
                title="Repeated nearby event sequence",
                factual_summary=(
                    f"{first_type} was followed within ten minutes by {second_type} "
                    f"{len(pairs)} times across {len(days)} local day(s)."
                ),
                evidence_window={
                    "start": min(starts).isoformat(),
                    "end": max(ends).isoformat(),
                    "timezone": timezone.key,
                },
                source_event_ids=tuple(event_ids),
                observation_count=len(pairs),
                distinct_day_count=len(days),
                elapsed_hours=round(elapsed, 3),
                temporal_consistency={
                    "maximum_sequence_gap_seconds": 600,
                    "pair_count": len(pairs),
                },
                supporting_evidence=(
                    f"pair_count={len(pairs)}",
                    f"distinct_local_days={len(days)}",
                ),
                contradictory_evidence=(),
                missing_information=(
                    "Temporal proximity does not establish causation or a shared actor.",
                    "Missing events are not evidence that the sequence did not occur.",
                ),
                source_trust="CORE_QUALIFIED_JOURNAL_PROJECTION",
                maturity=_maturity(len(pairs), len(days), elapsed, 1.0),
                canonical_ids=tuple(
                    sorted({event["canonical_id"] for pair in pairs for event in pair})
                ),
            )
        )
    candidates.sort(
        key=lambda item: (
            -item.distinct_day_count,
            -item.observation_count,
            item.candidate_class,
            item.candidate_key,
        )
    )
    return candidates[:max_candidates]


def candidate_digest(candidates: list[PatternCandidate]) -> str:
    payload = [item.to_payload() for item in candidates]
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
