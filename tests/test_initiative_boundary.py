from __future__ import annotations

from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace
from typing import Any, cast

import pytest
from test_household_reasoning import request_for
from test_knowledge_api import setup

from anima_ha.intelligence import IntelligenceOrigin, IntelligenceResult, IntelligenceResultStatus
from anima_ha.policy import PolicyService
from anima_ha.sentry_boundary import CoreSentryBoundary


@pytest.mark.parametrize("allowed", [False, True])
def test_core_submission_rechecks_delivery_without_rewriting_action_evidence(
    tmp_path: Path, allowed: bool
) -> None:
    _, _, manager, evaluator = setup(tmp_path)
    request = replace(request_for(manager), origin=IntelligenceOrigin.AUTONOMOUS_ATTENTION)
    recorded: list[IntelligenceResult] = []

    def store_result(*args: Any) -> bool:
        recorded.append(args[-1])
        return True

    boundary = CoreSentryBoundary(
        manager,
        PolicyService(evaluator),
        cast(Any, SimpleNamespace(get=lambda _: request, record_result=store_result)),
        reasoning_context_loader=lambda _: {
            "initiative": {
                "notification": {"allowed": allowed, "request_id": str(request.request_id)}
            }
        },
    )
    outcome = IntelligenceResult(
        request.request_id,
        IntelligenceResultStatus.RESPONSE,
        response_text="Do not speak unless Core permits",
        action_references=("verified-action",),
    )
    okay, effective, permission = boundary.finalize_result(
        request, request.claim_owner or "", outcome
    )
    assert okay and permission["allowed"] == allowed
    assert effective.status == (
        IntelligenceResultStatus.RESPONSE if allowed else IntelligenceResultStatus.NO_ACTION
    )
    assert effective.action_references == ("verified-action",)
    assert recorded == [effective]
    assert effective.response_text is None if not allowed else effective.response_text is not None


def test_notification_tool_cannot_bypass_unsolicited_gate_before_model_final(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _, _, manager, evaluator = setup(tmp_path)
    request = replace(request_for(manager), origin=IntelligenceOrigin.AUTONOMOUS_ATTENTION)
    boundary = CoreSentryBoundary(
        manager, PolicyService(evaluator), cast(Any, SimpleNamespace(get=lambda _: request))
    )
    monkeypatch.setattr(
        CoreSentryBoundary,
        "_request_tool",
        lambda *_: SimpleNamespace(tool_id="anima.external.notifications.send"),
    )
    result = boundary.invoke_tool(
        request, "anima.external.notifications.send", {"message": "pretend permission granted"}
    )
    assert result["status"] == "DENIED"
    assert evaluator.documents == []


def test_manual_request_response_not_suppressed(tmp_path: Path) -> None:
    _, _, manager, evaluator = setup(tmp_path)
    request = request_for(manager)
    boundary = CoreSentryBoundary(
        manager,
        PolicyService(evaluator),
        cast(Any, SimpleNamespace(get=lambda _: request, record_result=lambda *args: True)),
    )
    outcome = IntelligenceResult(
        request.request_id, IntelligenceResultStatus.RESPONSE, response_text="Direct reply"
    )
    okay, effective, _ = boundary.finalize_result(request, request.claim_owner or "", outcome)
    assert okay and effective == outcome


def test_new_required_notification_at_submission_cannot_record_silence_as_complete(
    tmp_path: Path,
) -> None:
    _, _, manager, evaluator = setup(tmp_path)
    request = replace(request_for(manager), origin=IntelligenceOrigin.AUTONOMOUS_ATTENTION)
    boundary = CoreSentryBoundary(
        manager,
        PolicyService(evaluator),
        cast(Any, SimpleNamespace(get=lambda _: request, record_result=lambda *args: True)),
        reasoning_context_loader=lambda _: {
            "initiative": {
                "notification": {
                    "allowed": True,
                    "required": True,
                    "request_id": str(request.request_id),
                }
            }
        },
    )
    outcome = IntelligenceResult(request.request_id, IntelligenceResultStatus.NO_ACTION)
    okay, effective, _ = boundary.finalize_result(request, request.claim_owner or "", outcome)
    assert okay and effective.status == IntelligenceResultStatus.PARTIAL
    assert effective.detail == "REQUIRED_NOTIFICATION_NOT_PRODUCED"
    assert effective.response_text is None
