from __future__ import annotations

from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from uuid import UUID, uuid4

from anima_ha.intelligence import IntelligenceLifecycle
from anima_ha.live_results import _bounded_payload
from anima_ha.policy import Assurance, EvidenceType, IdentityEvidence
from anima_ha.ui_api import UIIdentity, UIService

HOUSEHOLD = UUID("00000000-0000-0000-0000-000000000012")
PRINCIPAL = UUID("00000000-0000-0000-0000-000000000013")


def _identity() -> UIIdentity:
    now = datetime.now(UTC)
    return UIIdentity(
        HOUSEHOLD,
        PRINCIPAL,
        "test-user",
        IdentityEvidence(
            uuid4(),
            HOUSEHOLD,
            PRINCIPAL,
            EvidenceType.AUTHENTICATED_SESSION,
            "test",
            now,
            now,
            now + timedelta(minutes=5),
            Assurance.AUTHENTICATED,
            70,
            "test",
        ),
    )


def test_live_notification_payload_is_bounded() -> None:
    payload = _bounded_payload(
        {
            "request_id": str(uuid4()),
            "household_id": str(HOUSEHOLD),
            "status": "RESPONSE",
            "response": "x" * 20_000,
            "detail": None,
        }
    )

    assert len(str(payload["response"]).encode()) < 7_500
    assert payload["status"] == "RESPONSE"


def test_ui_reads_only_live_result_for_the_request_household() -> None:
    request_id = uuid4()
    request = SimpleNamespace(
        request_id=request_id,
        household_id=HOUSEHOLD,
        lifecycle=IntelligenceLifecycle.COMPLETED,
    )

    class Store:
        def get(self, value: UUID) -> SimpleNamespace | None:
            return request if value == request_id else None

    class Bus:
        def get(self, value: UUID, household_id: UUID) -> dict[str, object] | None:
            if value == request_id and household_id == HOUSEHOLD:
                return {
                    "request_id": str(request_id),
                    "household_id": str(HOUSEHOLD),
                    "status": "RESPONSE",
                    "response": "The basement is clear.",
                    "detail": None,
                    "provider_ambiguous": False,
                }
            return None

    service = UIService(
        core_runtime=SimpleNamespace(intelligence_store=Store()),
        commands=SimpleNamespace(),
        conversation=SimpleNamespace(),
        sentry_results=Bus(),  # type: ignore[arg-type]
    )

    result = service.conversation_result(_identity(), str(request_id))

    assert result["status"] == "RESPONSE"
    assert result["response"] == "The basement is clear."
    assert result["available"] is True
