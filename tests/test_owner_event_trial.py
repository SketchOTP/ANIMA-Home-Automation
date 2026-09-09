from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

from scripts.report_owner_event_trial import load_records, summarize


def test_trial_summary_separates_required_and_discretionary_speech(tmp_path: Path) -> None:
    ledger = tmp_path / "trial.jsonl"
    rows = [
        {
            "recorded_at": "2026-09-08T10:00:00+00:00",
            "request_id": "required-delivered",
            "notification_required": True,
            "delivery_status": "DELIVERED",
            "result_status": "RESPONSE",
            "decision": "speak",
        },
        {
            "recorded_at": "2026-09-08T10:01:00+00:00",
            "request_id": "required-missed",
            "notification_required": True,
            "delivery_status": "NOT_ATTEMPTED",
            "result_status": "PARTIAL",
            "decision": "silent",
        },
        {
            "recorded_at": "2026-09-08T10:02:00+00:00",
            "request_id": "optional-spoken",
            "notification_required": False,
            "delivery_status": "DELIVERED",
            "result_status": "RESPONSE",
            "decision": "speak",
        },
    ]
    ledger.write_text("".join(json.dumps(item) + "\n" for item in rows), encoding="utf-8")
    records = load_records(ledger, since=datetime(2026, 9, 8, 10, 1, tzinfo=UTC))
    result = summarize(records)
    assert result["records"] == 2
    assert result["required_notifications"] == 1
    assert result["required_delivery_not_proven"] == 1
    assert result["discretionary_tts_delivered"] == 1
    assert result["content_retained"] is False


def test_missing_trial_ledger_is_an_empty_not_fabricated_result(tmp_path: Path) -> None:
    assert summarize(load_records(tmp_path / "missing.jsonl"))["records"] == 0
