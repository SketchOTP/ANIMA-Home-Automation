"""Canonical alert qualification is exact-source, not optional correlation."""

from pathlib import Path
from typing import Any
from unittest.mock import Mock

import pytest
from test_stage7_alert_context import composition


@pytest.mark.parametrize("mode", ["unavailable", "large"])
def test_exact_source_not_nearby_history(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, mode: str
) -> None:
    request, boundary, feedback = composition(tmp_path, monkeypatch, mode)
    initiative: Any = boundary.notification_context_loader
    reads = Mock(return_value={"items": [{"event_id": request.causation_id}]})
    initiative.evidence.recent_household_evidence = reads
    packet = boundary.request_notification(request)
    notification = packet["household_context"]["initiative"]["notification"]
    assert notification["allowed"] and notification["required"]
    assert notification["revocation_confirmed"] is False
    assert reads.call_count == 1
    assert reads.call_args.kwargs["event_ids"] == (request.causation_id,)
    assert reads.call_args.kwargs["limit"] == 1
    assert feedback.call_count == 0


def test_unqualified_source_cannot_grant_or_revoke(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    request, boundary, _ = composition(tmp_path, monkeypatch, "unavailable")
    initiative: Any = boundary.notification_context_loader
    initiative.evidence.recent_household_evidence = Mock(return_value={"items": []})
    notification = boundary.request_notification(request)["household_context"]["initiative"][
        "notification"
    ]
    assert not notification["allowed"] and not notification["required"]
    assert not notification["revocation_confirmed"]


def test_optional_correlation_failure_is_rich_only(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    request, boundary, _ = composition(tmp_path, monkeypatch, "available")
    initiative: Any = boundary.notification_context_loader

    def evidence(*args: Any, **kwargs: Any) -> dict[str, Any]:
        if "event_ids" in kwargs:
            return {"items": [{"event_id": request.causation_id}]}
        raise RuntimeError("private correlation failure")

    initiative.evidence.recent_household_evidence = evidence
    compact = boundary.request_notification(request)
    rich = boundary.request_context(request)
    assert compact["household_context"]["initiative"]["notification"]["required"]
    context = rich["household_context"]["initiative"]
    assert context["notification"]["required"]
    assert context["nearby_events"] == {"status": "UNAVAILABLE", "items": [], "authority": "NONE"}
    assert "private correlation failure" not in str(rich)
