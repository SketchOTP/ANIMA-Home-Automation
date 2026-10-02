"""Optional measured history must not gate canonical zero-model alerts."""

from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace
from typing import cast
from unittest.mock import Mock
from uuid import uuid4

import pytest
from test_household_reasoning import request_for
from test_knowledge_api import setup

from anima_ha.alert_delivery import initialize_required_delivery
from anima_ha.household_event_context import HouseholdEventEvidence
from anima_ha.household_initiative import HouseholdInitiativeContext
from anima_ha.household_reasoning import household_reasoning_context
from anima_ha.intelligence import IntelligenceOrigin, IntelligenceRequest
from anima_ha.policy import PolicyService
from anima_ha.sentry_boundary import CoreSentryBoundary


def composition(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, mode: str
) -> tuple[IntelligenceRequest, CoreSentryBoundary, Mock]:
    _, _, manager, evaluator = setup(tmp_path)
    resource = uuid4()
    event_id = str(uuid4())
    request = replace(
        request_for(manager),
        origin=IntelligenceOrigin.AUTONOMOUS_ATTENTION,
        principal_id=None,
        causation_id=event_id,
        request_metadata={
            **request_for(manager).request_metadata,
            "sentry_event_path": "IMMEDIATE_ANNOUNCEMENT_ONLY",
        },
    )
    source = {
        "event_id": event_id,
        "event_type": "external.android.lock_reported",
        "source": "android-relay-report:isolated",
        "metadata": {},
        "payload": {"canonical_resource_id": str(resource), "event_kind": "unlocked"},
        "occurred_at": datetime.now(UTC),
    }
    feedback = Mock(
        side_effect=RuntimeError("private error sentinel") if mode == "unavailable" else None,
        return_value=[{"windows": [], "sentinel": "x" * 70000}]
        if mode == "large"
        else [{"windows": [], "disposition": "UNKNOWN"}] * 8,
    )
    learning = SimpleNamespace(
        status=lambda *args, **kwargs: {
            "config": {"always_notify": [source["event_type"]]},
            "readiness": {"ready": False},
        },
        ensure_review_packet=lambda _: None,
        prospective_feedback=feedback,
    )
    evidence = SimpleNamespace(
        recent_household_evidence=lambda *args, **kwargs: {"items": [{"event_id": event_id}]},
        graph=SimpleNamespace(get_node=lambda _: SimpleNamespace(name="Isolated Lock")),
    )
    connection = Mock()
    connection.__enter__ = Mock(return_value=connection)
    connection.__exit__ = Mock(return_value=False)
    connection.execute.return_value.fetchone.return_value = source
    monkeypatch.setattr("anima_ha.household_initiative.psycopg.connect", lambda *a, **k: connection)
    initiative = HouseholdInitiativeContext(
        "postgresql://unused", learning, cast(HouseholdEventEvidence, evidence)
    )
    boundary = CoreSentryBoundary(
        manager,
        PolicyService(evaluator),
        SimpleNamespace(get=lambda _: request),
        notification_context_loader=initiative,
        reasoning_context_loader=lambda item: household_reasoning_context(
            item, None, None, initiative=initiative
        ),
    )
    return request, boundary, feedback


@pytest.mark.parametrize("mode", ["unavailable", "large"])
def test_optional_feedback_cannot_change_compact_required_alert(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, mode: str
) -> None:
    request, boundary, feedback = composition(tmp_path, monkeypatch, mode)
    # Fail loudly if the actual compact transport takes a tool/provider path.
    invoke = Mock(side_effect=AssertionError("no tool/model path"))
    provider = Mock(side_effect=AssertionError("no provider start"))
    monkeypatch.setattr(CoreSentryBoundary, "invoke_tool", invoke)
    monkeypatch.setattr(CoreSentryBoundary, "start_provider", provider)
    packet = boundary.request_notification(request)
    disposition = packet["household_context"]["initiative"]["notification"]
    assert disposition["allowed"] is True and disposition["required"] is True
    assert disposition["reason"] == "ALWAYS_NOTIFY"
    assert disposition["sentry_event_path"] == "IMMEDIATE_ANNOUNCEMENT_ONLY"
    assert disposition["announcement"]["text"] == "Isolated Lock was unlocked."
    obligation = initialize_required_delivery(request, disposition)
    assert obligation is not None and obligation["state"] == "PENDING"
    assert obligation["attempts"] == 0 and obligation["event_id"] == request.causation_id
    assert "prospective_feedback" not in str(packet)
    assert feedback.call_count == invoke.call_count == provider.call_count == 0


@pytest.mark.parametrize("mode", ["unavailable", "large", "available"])
def test_rich_reasoning_feedback_is_bounded_and_missing_data_is_explicit(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, mode: str
) -> None:
    request, boundary, feedback = composition(tmp_path, monkeypatch, mode)
    packet = boundary.request_context(request)["household_context"]
    measured = packet["prospective_feedback"]
    assert feedback.call_count == 1 and measured["authority"] == "NONE"
    assert (
        measured["status"]
        == {
            "unavailable": "UNAVAILABLE",
            "large": "CONTEXT_LIMIT_REQUIRES_SCOPED_READ",
            "available": "AVAILABLE",
        }[mode]
    )
    assert len(measured["items"]) == (6 if mode == "available" else 0)
    assert "private error sentinel" not in str(packet)
    assert packet["initiative"]["notification"]["required"] is True
