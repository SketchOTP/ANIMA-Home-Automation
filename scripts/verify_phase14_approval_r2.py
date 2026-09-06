"""Run the Phase 14 approval ownership race on real PostgreSQL."""

from __future__ import annotations

import json
import os
import sys
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

from anima_ha.action import (
    ActionExecutionCoordinator,
    ActionRequest,
    ActionStatus,
    PostgresActionStore,
    PostgresPendingApprovalStore,
    PostgresResourceLocker,
    TruthSnapshot,
)
from anima_ha.policy import (
    Assurance,
    IdentityContext,
    PolicyContext,
    PolicyService,
    PostgresPolicyStore,
)

# Keep direct `python scripts/<target>.py` execution equivalent to module
# execution in CI, where the repository root is the import base.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from scripts.verify_phase12_h5u_confirmation import ConfirmationByValidity, Gateway, tool

DATABASE_URL = os.environ.get("ANIMA_DATABASE_URL", "")
HOUSEHOLD_ID = UUID("ecbd0d84-6f5f-40f8-928f-1d5dfe758dd7")


def main() -> int:
    if not DATABASE_URL:
        raise RuntimeError("ANIMA_DATABASE_URL is required")
    principal = uuid4()
    audit = PostgresPolicyStore(DATABASE_URL)
    pending = PostgresPendingApprovalStore(DATABASE_URL)
    gateway = Gateway()
    coordinator = ActionExecutionCoordinator(
        gateway,
        PostgresActionStore(DATABASE_URL),
        PostgresResourceLocker(DATABASE_URL),
        pending_approvals=pending,
    )
    identity = IdentityContext(HOUSEHOLD_ID, principal, Assurance.AUTHENTICATED)
    snapshot = TruthSnapshot({"power": {"state": "KNOWN", "value": "off", "version": "1"}})
    request = ActionRequest.create(
        action_id=uuid4(),
        action_intent_id=uuid4(),
        idempotency_key=f"phase14-r2-approval-race-{uuid4()}",
        household_id=HOUSEHOLD_ID,
        tool=tool(),
        arguments={"resource_id": str(uuid4()), "desired_on": True},
        identity=identity,
        policy_service=PolicyService(ConfirmationByValidity(), audit_store=audit),
        policy_context=PolicyContext(principal_role="resident"),
        refresher=lambda resources: snapshot,
    )
    first = coordinator.execute(request)
    if first.record.status != ActionStatus.REQUIRE_CONFIRMATION or not first.record.result:
        raise AssertionError(f"expected confirmation, got {first.record.status}")
    approval_id = UUID(str(first.record.result["approval_id"]))
    now = datetime.now(UTC)

    def claim(decision: str) -> Any:
        return pending.claim(
            approval_id,
            household_id=HOUSEHOLD_ID,
            principal_id=principal,
            decision=decision,
            now=now,
        )

    with ThreadPoolExecutor(max_workers=2) as executor:
        outcomes = list(executor.map(claim, ("APPROVE", "REJECT")))
    winners = [item for item in outcomes if item is not None]
    if len(winners) != 1:
        raise AssertionError(f"expected one approval winner, got {len(winners)}")
    stored = pending.get(approval_id)
    if stored is None or stored.decision != winners[0].decision:
        raise AssertionError("durable approval winner does not match stored decision")
    if gateway.calls != 0:
        raise AssertionError("claim race dispatched an action")
    print(
        json.dumps(
            {
                "scenario_id": "APPROVAL_CONCURRENT_ONE_WINNER",
                "evidence_level": "POSTGRES_OPA_CORE",
                "status": "PASS",
                "approval_id": str(approval_id),
                "winner_count": len(winners),
                "winner_decision": winners[0].decision,
                "durable_status": stored.status.value,
                "provider_dispatches": gateway.calls,
                "terminal_action_status": first.record.status.value,
                "phase15": False,
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
