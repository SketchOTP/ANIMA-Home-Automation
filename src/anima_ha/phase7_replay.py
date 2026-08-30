"""Read-only Phase 7 journal replay and attention-profile comparison CLI."""

from __future__ import annotations

import argparse
import json
from datetime import UTC, timedelta
from pathlib import Path
from typing import Any
from uuid import UUID

import psycopg
from psycopg.rows import dict_row

from anima_ha.attention import AttentionProfile, AttentionReplay, default_attention_profile
from anima_ha.config import RuntimeConfig
from anima_ha.context import ContextBroker


def _profile(path: str | None, fallback_version: str) -> AttentionProfile:
    if path is None:
        return default_attention_profile(fallback_version)
    value = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError("attention profile must be a JSON object")
    return AttentionProfile.from_payload(value)


def _events(database_url: str, start: int, end: int | None) -> list[dict[str, Any]]:
    with psycopg.connect(database_url, row_factory=dict_row) as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT journal_position, event_id, schema_version, event_type, source,
                       source_event_id, subject_key, occurred_at, recorded_at,
                       source_sequence, correlation_id, causation_id, confidence,
                       evidence_kind, importance, delivery_class, payload, metadata
                FROM anima_event_journal
                WHERE journal_position >= %s AND (%s::bigint IS NULL OR journal_position <= %s)
                ORDER BY journal_position
                """,
                (start, end, end),
            )
            return list(cursor.fetchall())


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Read-only ANIMA Phase 7 attention/context replay")
    parser.add_argument("--start", type=int, default=1, help="first journal position")
    parser.add_argument("--end", type=int, help="last journal position")
    parser.add_argument("--profile", help="versioned attention profile JSON")
    parser.add_argument("--compare-profile", help="second profile JSON for comparison")
    parser.add_argument("--household-id", required=True, help="canonical household UUID")
    parser.add_argument(
        "--flush-seconds", type=int, default=300, help="seconds after final event to flush"
    )
    return parser


def main() -> int:
    args = build_parser().parse_args()
    config = RuntimeConfig.from_environment()
    events = _events(config.database_url, args.start, args.end)
    if not events:
        raise SystemExit("journal range contains no events")
    profile = _profile(args.profile, "phase7.replay.default")
    final_time = max(event["recorded_at"] for event in events) + timedelta(
        seconds=args.flush_seconds
    )
    replay = AttentionReplay()
    journal_count_before = len(events)
    result = replay.evaluate(profile, events, flush_at=final_time)
    broker = ContextBroker(config.database_url, config.database_connect_timeout)
    household_id = UUID(args.household_id)
    packets = [
        broker.assemble(
            trigger,
            household_id=household_id,
            assembled_at=final_time.astimezone(UTC),
            persist=False,
        )
        for trigger in result.triggers
    ]
    output: dict[str, Any] = {
        "side_effects": "NONE",
        "journal_range": [int(events[0]["journal_position"]), int(events[-1]["journal_position"])],
        "profile_version": profile.profile_version,
        "profile_digest": profile.digest,
        "event_count": journal_count_before,
        "decision_count": len(result.decisions),
        "trigger_count": len(result.triggers),
        "context_packet_count": len(packets),
        "context_packet_bytes": sum(packet.serialized_bytes for packet in packets),
        "packet_digests": [packet.digest for packet in packets],
    }
    if args.compare_profile:
        other = _profile(args.compare_profile, "phase7.replay.compare")
        comparison = replay.compare(profile, other, events, flush_at=final_time)
        other_result = replay.evaluate(other, events, flush_at=final_time)
        other_packets = [
            broker.assemble(
                trigger,
                household_id=household_id,
                assembled_at=final_time.astimezone(UTC),
                persist=False,
            )
            for trigger in other_result.triggers
        ]
        bytes_a = sum(packet.serialized_bytes for packet in packets)
        bytes_b = sum(packet.serialized_bytes for packet in other_packets)
        comparison.update(
            {
                "context_packet_bytes_a": bytes_a,
                "context_packet_bytes_b": bytes_b,
                "context_packet_bytes_change": bytes_b - bytes_a,
            }
        )
        output["comparison"] = comparison
    print(json.dumps(output, sort_keys=True, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
