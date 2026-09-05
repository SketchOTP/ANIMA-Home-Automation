"""Prove approval continuation re-evaluates current policy before dispatch.

The action and approval rows are real PostgreSQL records.  The evaluator is a
test-only policy transition: it requests confirmation for the initial intent,
then denies the same intent when the approved continuation is consumed.  This
keeps the test focused on the coordinator's reauthorization boundary without
changing the repository's Phase 4 policy bundle.
"""

from __future__ import annotations

import json
import os
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import UUID, uuid4

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.verify_phase12_h5u_confirmation import HOUSEHOLD_ID, tool  # noqa: E402

from anima_ha.action import (
    ActionExecutionCoordinator,
    ActionRequest,
    ActionStatus,
    PostgresActionStore,
    PostgresPendingApprovalStore,
    PostgresResourceLocker,
    TruthSnapshot,
)
from anima_ha.db.migrate import migrate
from anima_ha.plugins import (
    ExternalContentTrust,
    InvocationOutcome,
    InvocationResult,
)
from anima_ha.policy import (
    Assurance,
    IdentityContext,
    PolicyContext,
    PolicyService,
    PostgresPolicyStore,
)

DATABASE_URL = os.environ.get("ANIMA_DATABASE_URL", "")


class PolicyChangesBeforeApproval:
    """Request approval once, then represent a current policy denial."""

    def __init__(self) -> None:
        self.calls = 0

    def evaluate(self, document: dict[str, Any]) -> dict[str, Any]:
        del document
        self.calls += 1
        if self.calls == 1:
            return {
                "decision": "REQUIRE_CONFIRMATION",
                "reason_code": "CONFIRMATION_REQUIRED",
                "required_assurance": "AUTHENTICATED",
                "confirmation_required": True,
                "policy_version": "phase14-policy-transition",
            }
        return {
            "decision": "DENY",
            "reason_code": "POLICY_CHANGED_BEFORE_REAUTHORIZATION",
            "required_assurance": "AUTHENTICATED",
            "confirmation_required": False,
            "policy_version": "phase14-policy-transition",
        }


class CountingGateway:
    def __init__(self) -> None:
        self.calls = 0

    def invoke(self, *args: Any, **kwargs: Any) -> InvocationResult:
        del args, kwargs
        self.calls += 1
        return InvocationResult(
            InvocationOutcome.SUCCESS,
            "anima.test.set_power",
            "anima.test",
            "1.0.0",
            1.0,
            result={"accepted": True},
            external_content_trust=ExternalContentTrust.PLUGIN_TRUSTED,
        )


def main() -> int:
    if not DATABASE_URL:
        raise RuntimeError("ANIMA_DATABASE_URL is required")
    migrate(DATABASE_URL, 5)
    principal = uuid4()
    evaluator = PolicyChangesBeforeApproval()
    policy = PolicyService(evaluator, audit_store=PostgresPolicyStore(DATABASE_URL))
    gateway = CountingGateway()
    pending = PostgresPendingApprovalStore(DATABASE_URL)
    coordinator = ActionExecutionCoordinator(
        gateway,
        PostgresActionStore(DATABASE_URL),
        PostgresResourceLocker(DATABASE_URL),
        pending_approvals=pending,
    )
    request = ActionRequest.create(
        action_id=uuid4(),
        action_intent_id=uuid4(),
        idempotency_key=f"phase14-policy-reauthorization-{uuid4()}",
        household_id=HOUSEHOLD_ID,
        tool=tool(),
        arguments={"resource_id": str(UUID(int=11)), "desired_on": True},
        identity=IdentityContext(HOUSEHOLD_ID, principal, Assurance.AUTHENTICATED),
        policy_service=policy,
        policy_context=PolicyContext(principal_role="resident"),
        refresher=lambda resources: TruthSnapshot(
            {"power": {"state": "KNOWN", "value": "off", "version": "1"}}
        ),
    )
    waiting = coordinator.execute(request)
    if waiting.record.status != ActionStatus.REQUIRE_CONFIRMATION:
        raise AssertionError(f"expected confirmation, got {waiting.record.status}")
    if not waiting.record.result or "approval_id" not in waiting.record.result:
        raise AssertionError("confirmation did not persist an approval reference")
    approval_id = UUID(str(waiting.record.result["approval_id"]))

    resumed = coordinator.approve_pending(
        approval_id,
        household_id=HOUSEHOLD_ID,
        principal_id=principal,
        decision="APPROVE",
        tool=tool(),
        policy_service=policy,
        policy_context=PolicyContext(principal_role="resident"),
        refresher=lambda resources: TruthSnapshot(
            {"power": {"state": "KNOWN", "value": "off", "version": "1"}}
        ),
    )
    if resumed is None or resumed.record.status != ActionStatus.POLICY_DENIED:
        raise AssertionError(
            "continuation did not apply the changed policy before dispatch: "
            f"{None if resumed is None else resumed.record.status}"
        )
    if gateway.calls != 0:
        raise AssertionError("policy change after approval caused a provider dispatch")
    stored = pending.get(approval_id)
    if stored is None or stored.status.value != "APPROVED":
        raise AssertionError("approval continuation outcome was not durably recorded")

    print(
        json.dumps(
            {
                "scenario_id": "POLICY_CHANGE_BEFORE_APPROVAL_NO_DISPATCH",
                "status": "PASS",
                "evidence_level": "POSTGRES_ACTION_POLICY",
                "policy_evaluations": evaluator.calls,
                "initial_status": waiting.record.status.value,
                "continuation_status": resumed.record.status.value,
                "policy_reason": "POLICY_CHANGED_BEFORE_REAUTHORIZATION",
                "provider_dispatches": gateway.calls,
                "approval_durable_status": stored.status.value,
                "checked_at": datetime.now(UTC).isoformat(),
                "phase15": False,
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
