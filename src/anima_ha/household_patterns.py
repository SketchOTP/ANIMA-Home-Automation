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
from statistics import median
from typing import Any
from uuid import UUID, uuid5
from zoneinfo import ZoneInfo

PATTERN_NAMESPACE = UUID("bc23b402-7872-4cc7-ae67-d35f6f3cd568")
MAX_CANDIDATES = 6
MAX_SOURCE_REFS = 12
ROUTINE_EVIDENCE_THRESHOLD = 0.65


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
    evidence_score: float
    canonical_ids: tuple[str, ...]
    semantic_evidence: dict[str, Any] | None = None

    def to_payload(self) -> dict[str, Any]:
        value = asdict(self)
        if value["semantic_evidence"] is None:
            value.pop("semantic_evidence")
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


def _signal_family(item: dict[str, Any]) -> str:
    """Group normalized events by the independent household signal that emitted them."""
    known = {
        "household.presence.connection_changed": "MEMBER_ASSOCIATED_PRESENCE",
        "household.ring.motion": "RING_MOTION",
        "household.ring.doorbell": "RING_DOORBELL",
        "external.android.motion_reported": "ANDROID_CAMERA_MOTION",
        "external.android.lock_reported": "ANDROID_LOCK_REPORT",
        "senseguard.opened": "CONTACT_SENSOR",
        "senseguard.event": "CONTACT_SENSOR",
    }
    event_type = str(item["event_type"])
    return str(item.get("source_family") or known.get(event_type, event_type))


def _episode_signature(rows: list[dict[str, Any]]) -> tuple[tuple[str, str, str], ...]:
    return tuple(
        (str(row["event_type"]), str(row["canonical_id"]), _event_qualifier(row)) for row in rows
    )


def _episode_label(row: dict[str, Any]) -> str:
    role = (
        "member-associated device presence"
        if row["event_type"] == "household.presence.connection_changed"
        else "household sensor"
    )
    transition = _event_qualifier(row).lower()
    return f"{role} {transition} ({row['event_type']})"


def evidence_score(count: int, days: int, elapsed_hours: float, consistency: float) -> float:
    """Calculate deterministic evidence strength, not probability or authority."""
    bounded_consistency = max(0.0, min(1.0, consistency))
    score = (
        0.30 * min(count / 10.0, 1.0)
        + 0.30 * min(days / 7.0, 1.0)
        + 0.20 * min(elapsed_hours / (7.0 * 24.0), 1.0)
        + 0.20 * bounded_consistency
    )
    return round(score, 3)


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
    evidence_truncated: bool = False,
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
        dominant_days = len(
            {value.date() for value in times if (value.hour // 4) * 4 == dominant_start}
        )
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
        score = evidence_score(len(rows), len(days), elapsed, consistency)
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
                    "dominant_local_day_count": dominant_days,
                    "dominant_local_window": (
                        f"{dominant_start:02d}:00-{(dominant_start + 4) % 24:02d}:00"
                    ),
                    "observations_in_window": dominant_count,
                    "total_observations": len(rows),
                    "ratio": round(consistency, 3),
                    # Conditional support on days with qualified receipts for
                    # this source/qualifier, not covered days or probability.
                    # Preserve event concentration for maturity and ranking.
                    "observed_day_support": {
                        "numerator": dominant_days,
                        "denominator": len(days),
                        "ratio": dominant_days / len(days),
                        "support_basis": "OBSERVED_DAY_SUPPORT_NOT_PROBABILITY",
                    },
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
                evidence_score=score,
                canonical_ids=(canonical_id,),
            )
        )

    # Build a recurring episode from the ordered combination of unlike signal
    # families. The candidate records the observations and their timing; SENTRY
    # supplies the human interpretation. One day is not a learned routine, and
    # an associated phone event never authenticates the person at a sensor.
    episode_groups: dict[tuple[tuple[str, str, str], ...], list[list[dict[str, Any]]]] = (
        defaultdict(list)
    )
    index = 0
    while index < len(ordered):
        first_at = _stamp(ordered[index]["occurred_at"])
        end = index + 1
        while end < len(ordered):
            gap = (_stamp(ordered[end]["occurred_at"]) - first_at).total_seconds()
            if gap > 900:
                break
            end += 1
        cluster = ordered[index:end]
        families = {_signal_family(row) for row in cluster}
        event_types = {str(row["event_type"]) for row in cluster}
        if len(event_types) >= 2 and len(families) >= 2:
            episode_groups[_episode_signature(cluster)].append(cluster)
        index = end

    for signature, episodes in episode_groups.items():
        # Use one episode per local day so duplicate notification bursts do
        # not create artificial multi-day support.
        per_day: dict[str, list[dict[str, Any]]] = {}
        for episode in episodes:
            day = _stamp(episode[0]["occurred_at"]).astimezone(timezone).date().isoformat()
            per_day.setdefault(day, episode)
        if len(per_day) < 2:
            continue
        selected = sorted(
            per_day.values(),
            key=lambda episode: (_stamp(episode[0]["occurred_at"]), episode[0]["event_id"]),
        )
        sequence = selected[0]
        starts = [_stamp(episode[0]["occurred_at"]).astimezone(timezone) for episode in selected]
        ends = [_stamp(episode[-1]["occurred_at"]).astimezone(timezone) for episode in selected]
        intervals = [
            max(0.0, (_stamp(right["occurred_at"]) - _stamp(left["occurred_at"])).total_seconds())
            for episode in selected
            for left, right in zip(episode, episode[1:], strict=False)
        ]
        start_buckets = Counter((value.hour // 4) * 4 for value in starts)
        dominant_start, dominant_count = start_buckets.most_common(1)[0]
        consistency = dominant_count / len(starts)
        elapsed = (max(ends) - min(starts)).total_seconds() / 3600
        day_values = {value.date().isoformat() for value in starts}
        signal_families = sorted({_signal_family(row) for row in sequence})
        signal_ids = [row["event_id"] for episode in selected for row in episode]
        source_ids = tuple(dict.fromkeys(signal_ids))[-MAX_SOURCE_REFS:]
        signature_text = json.dumps(signature, separators=(",", ":"))
        signature_hash = hashlib.sha256(signature_text.encode()).hexdigest()[:24]
        key = f"multi_signal_episode:{signature_hash}"
        labels = [_episode_label(row) for row in sequence]
        presence = [
            row for row in sequence if row["event_type"] == "household.presence.connection_changed"
        ]
        missing = [
            "A member-associated phone event is device presence, not proof that the person acted.",
            "Cross-source timing supports a possible situation; it does not prove "
            "identity or causation.",
            "No event outside this qualified candidate window is treated as absent.",
        ]
        if evidence_truncated:
            missing.append(
                "The qualified evidence window was truncated; this pattern may be incomplete."
            )
        candidates.append(
            PatternCandidate(
                candidate_id=str(uuid5(PATTERN_NAMESPACE, f"{household_id}:{key}")),
                candidate_key=key,
                candidate_class="MULTI_SIGNAL_EPISODE",
                title="Recurring multi-signal household episode",
                factual_summary=(
                    f"An ordered {len(signal_families)}-family signal episode recurred on "
                    f"{len(day_values)} distinct local day(s) within a 15-minute window: "
                    + " then ".join(labels)
                    + ". This is a repeated co-occurrence, not a verified person, "
                    "arrival, departure, or cause."
                ),
                evidence_window={
                    "start": min(starts).isoformat(),
                    "end": max(ends).isoformat(),
                    "timezone": timezone.key,
                },
                source_event_ids=source_ids,
                observation_count=len(selected),
                distinct_day_count=len(day_values),
                elapsed_hours=round(elapsed, 3),
                temporal_consistency={
                    "dominant_local_window": (
                        f"{dominant_start:02d}:00-{(dominant_start + 4) % 24:02d}:00"
                    ),
                    "episodes_in_window": dominant_count,
                    "episode_count": len(selected),
                    "ratio": round(consistency, 3),
                    "maximum_episode_window_seconds": 900,
                    "median_inter_event_seconds": round(median(intervals), 3) if intervals else 0.0,
                },
                supporting_evidence=(
                    f"repeated_episode_days={len(day_values)}",
                    f"independent_signal_families={len(signal_families)}",
                    "ordered_signals=" + " -> ".join(labels),
                ),
                contradictory_evidence=(),
                missing_information=tuple(missing),
                source_trust="CORE_QUALIFIED_JOURNAL_PROJECTION",
                maturity=_maturity(len(selected), len(day_values), elapsed, consistency),
                evidence_score=evidence_score(len(selected), len(day_values), elapsed, consistency),
                canonical_ids=tuple(sorted({row["canonical_id"] for row in sequence})),
                semantic_evidence={
                    "ordered_signals": [
                        {
                            "event_type": row["event_type"],
                            "canonical_id": row["canonical_id"],
                            "qualifier": _event_qualifier(row),
                            "signal_family": _signal_family(row),
                            "member_association": (
                                "DEVICE_ASSOCIATED_WITH_MEMBER_NOT_AUTHENTICATED"
                                if row in presence
                                else "HOUSEHOLD_RESOURCE"
                            ),
                        }
                        for row in sequence
                    ],
                    "distinct_local_days": sorted(day_values),
                    "interpretation_required": True,
                    "authority": "NONE",
                },
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
                evidence_score=evidence_score(len(pairs), len(days), elapsed, 1.0),
                canonical_ids=tuple(
                    sorted({event["canonical_id"] for pair in pairs for event in pair})
                ),
            )
        )
    candidates.sort(
        key=lambda item: (
            0 if item.candidate_class == "MULTI_SIGNAL_EPISODE" else 1,
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
