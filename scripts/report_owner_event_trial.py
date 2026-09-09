#!/usr/bin/env python3
"""Summarize SENTRY's private, content-free unattended-event trial ledger."""

from __future__ import annotations

import argparse
import json
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


def _time(value: str) -> datetime:
    parsed = datetime.fromisoformat(value)
    if parsed.tzinfo is None:
        raise ValueError("trial timestamps must include a timezone")
    return parsed.astimezone(UTC)


def load_records(path: Path, *, since: datetime | None = None) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    if not path.exists():
        return records
    for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        try:
            item = json.loads(line)
            recorded_at = _time(str(item["recorded_at"]))
        except (json.JSONDecodeError, KeyError, TypeError, ValueError) as exc:
            raise ValueError(f"invalid trial ledger line {number}") from exc
        if not isinstance(item, dict) or not isinstance(item.get("request_id"), str):
            raise ValueError(f"invalid trial ledger line {number}")
        if since is None or recorded_at >= since:
            records.append(item)
    return records


def summarize(records: list[dict[str, Any]]) -> dict[str, Any]:
    request_counts = Counter(str(item["request_id"]) for item in records)
    required = [item for item in records if item.get("notification_required") is True]
    spoken = [item for item in records if item.get("delivery_status") == "DELIVERED"]
    required_spoken = [item for item in required if item.get("delivery_status") == "DELIVERED"]
    required_unfulfilled = [
        item
        for item in required
        if item.get("delivery_status") != "DELIVERED"
        and item.get("notification_delivery_status") != "DELIVERED"
    ]
    discretionary_spoken = [
        item for item in spoken if item.get("notification_required") is not True
    ]
    return {
        "schema_version": 1,
        "records": len(records),
        "unique_requests": len(request_counts),
        "duplicate_request_records": sum(
            count - 1 for count in request_counts.values() if count > 1
        ),
        "required_notifications": len(required),
        "required_tts_delivered": len(required_spoken),
        "required_delivery_not_proven": len(required_unfulfilled),
        "tts_delivered": len(spoken),
        "discretionary_tts_delivered": len(discretionary_spoken),
        "owner_review_needed_for_unnecessary_announcements": len(discretionary_spoken),
        "delivery_statuses": dict(
            sorted(Counter(str(item.get("delivery_status", "UNKNOWN")) for item in records).items())
        ),
        "result_statuses": dict(
            sorted(Counter(str(item.get("result_status", "UNKNOWN")) for item in records).items())
        ),
        "decisions": dict(
            sorted(Counter(str(item.get("decision", "UNKNOWN")) for item in records).items())
        ),
        "initiative_reasons": dict(
            sorted(
                Counter(str(item.get("initiative_reason", "UNKNOWN")) for item in records).items()
            )
        ),
        "content_retained": False,
        "interpretation": {
            "missed_alert_proxy": "required_delivery_not_proven",
            "unnecessary_announcement_status": "OWNER_FEEDBACK_REQUIRED",
            "notification_tool_delivery": "NOT_PROVEN_UNLESS_ROUTE_RECEIPT_IS_RECORDED",
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--ledger",
        type=Path,
        default=Path.home() / ".local/state/sentry/anima-event-trial.jsonl",
    )
    parser.add_argument("--since", help="inclusive ISO-8601 trial start")
    parser.add_argument("--output", type=Path)
    arguments = parser.parse_args()
    since = _time(arguments.since) if arguments.since else None
    result = summarize(load_records(arguments.ledger, since=since))
    rendered = json.dumps(result, indent=2, sort_keys=True) + "\n"
    if arguments.output:
        arguments.output.write_text(rendered, encoding="utf-8")
    else:
        print(rendered, end="")


if __name__ == "__main__":
    main()
