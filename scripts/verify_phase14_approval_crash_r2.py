"""Exercise approval continuation loss at a real process boundary.

The child process consumes a real PostgreSQL confirmation and enters action
execution, then exits before its provider returns.  The parent reconstructs
the Core stores and proves recovery reports uncertainty without redispatching.
The test also records the distinct durable rejection state.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path
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
    RequestOrigin,
)

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from scripts.verify_phase12_h5u_confirmation import tool  # noqa: E402

DATABASE_URL = os.environ.get("ANIMA_DATABASE_URL", "")
OPA_URL = os.environ.get("ANIMA_OPA_URL", "http://127.0.0.1:18181")
HOUSEHOLD_ID = UUID("ecbd0d84-6f5f-40f8-928f-1d5dfe758dd7")
RESOURCE_ID = UUID("3c2bd8c5-5d31-4d3c-87b7-59d6a4de62ce")
ROOT = Path(__file__).resolve().parents[1]


def success() -> InvocationResult:
    return InvocationResult(
        InvocationOutcome.SUCCESS,
        "anima.external.notifications.send",
        "anima.external.notifications",
        "1.0.0",
        1.0,
        result={"accepted": True},
        external_content_trust=ExternalContentTrust.PLUGIN_TRUSTED,
    )


class CrashGateway:
    def __init__(self, marker: Path) -> None:
        self.marker = marker

    def invoke(self, *args: Any, **kwargs: Any) -> InvocationResult:
        del args, kwargs
        self.marker.write_text("dispatch_started", encoding="utf-8")
        os._exit(71)


class CountingGateway:
    def __init__(self) -> None:
        self.calls = 0

    def invoke(self, *args: Any, **kwargs: Any) -> InvocationResult:
        del args, kwargs
        self.calls += 1
        return success()


class ConfirmationByValidity:
    def evaluate(self, document: dict[str, Any]) -> dict[str, Any]:
        if document.get("confirmation", {}).get("valid") is True:
            return {
                "decision": "ALLOW",
                "reason_code": "CONFIRMATION_VALID",
                "policy_version": "phase14-process-crash",
            }
        return {
            "decision": "REQUIRE_CONFIRMATION",
            "reason_code": "CONFIRMATION_REQUIRED",
            "policy_version": "phase14-process-crash",
            "confirmation_required": True,
        }


def policy() -> PolicyService:
    return PolicyService(
        ConfirmationByValidity(), audit_store=PostgresPolicyStore(DATABASE_URL)
    )


def build_request(principal: UUID, label: str) -> ActionRequest:
    return ActionRequest.create(
        action_id=uuid4(),
        action_intent_id=uuid4(),
        idempotency_key=f"phase14-approval-crash-{label}-{uuid4()}",
        household_id=HOUSEHOLD_ID,
        tool=tool(),
        arguments={
            "resource_id": str(RESOURCE_ID),
            "desired_on": True,
            "label": f"approval crash {label}",
        },
        identity=IdentityContext(HOUSEHOLD_ID, principal, Assurance.AUTHENTICATED),
        policy_service=policy(),
        policy_context=PolicyContext(principal_role="resident"),
        refresher=lambda resources: TruthSnapshot(
            {"power": {"state": "KNOWN", "value": "off", "version": "1"}}
        ),
        origin=RequestOrigin.DIRECT_USER,
    )


def child(approval_id: UUID, principal: UUID, marker: Path, action: ActionRequest) -> int:
    gateway = CrashGateway(marker)
    coordinator = ActionExecutionCoordinator(
        gateway,
        PostgresActionStore(DATABASE_URL),
        PostgresResourceLocker(DATABASE_URL),
        pending_approvals=PostgresPendingApprovalStore(DATABASE_URL),
    )
    coordinator.approve_pending(
        approval_id,
        household_id=HOUSEHOLD_ID,
        principal_id=principal,
        decision="APPROVE",
        tool=action.tool,
        policy_service=policy(),
        policy_context=PolicyContext(principal_role="resident"),
        refresher=lambda resources: TruthSnapshot(),
        allow_recovery=True,
    )
    raise AssertionError("crash gateway unexpectedly returned")


def main() -> int:
    if not DATABASE_URL:
        raise RuntimeError("ANIMA_DATABASE_URL is required")
    migrate(DATABASE_URL, 5)
    pending = PostgresPendingApprovalStore(DATABASE_URL)
    parent_gateway = CountingGateway()
    coordinator = ActionExecutionCoordinator(
        parent_gateway,
        PostgresActionStore(DATABASE_URL),
        PostgresResourceLocker(DATABASE_URL),
        pending_approvals=pending,
    )
    principal = uuid4()
    action = build_request(principal, "started")
    waiting = coordinator.execute(action)
    if waiting.record.status != ActionStatus.REQUIRE_CONFIRMATION or not waiting.record.result:
        raise AssertionError(f"expected confirmation, got {waiting.record.status}")
    approval_id = UUID(str(waiting.record.result["approval_id"]))
    marker = Path(f"/tmp/anima-phase14-approval-crash-{approval_id}.marker")
    result = subprocess.run(
        [
            sys.executable,
            __file__,
            "--child",
            str(approval_id),
            str(principal),
        ],
        cwd=ROOT,
        env={**os.environ, "ANIMA_DATABASE_URL": DATABASE_URL, "ANIMA_OPA_URL": OPA_URL,
             "ANIMA_CRASH_MARKER": str(marker)},
        capture_output=True,
        text=True,
    )
    if result.returncode != 71 or not marker.exists():
        raise AssertionError(f"approval child did not crash at dispatch: {result.stderr}")
    stored_pending = pending.get(approval_id)
    if stored_pending is None or stored_pending.status.value != "APPROVED":
        raise AssertionError("approval consumption was not durable before process loss")
    action_store = PostgresActionStore(DATABASE_URL)
    in_flight = action_store.get(action.action_id)
    if in_flight is None or in_flight.status != ActionStatus.EXECUTING:
        raise AssertionError("action was not durable as executing before process loss")
    recovered = [
        item
        for item in action_store.recover_incomplete()
        if item.action_id == action.action_id
    ]
    if not recovered or recovered[0].status != ActionStatus.UNKNOWN_RESULT:
        raise AssertionError("ambiguous approved action was not recovered as unknown")

    resumed = coordinator.approve_pending(
        approval_id,
        household_id=HOUSEHOLD_ID,
        principal_id=principal,
        decision="APPROVE",
        tool=action.tool,
        policy_service=policy(),
        policy_context=PolicyContext(principal_role="resident"),
        refresher=lambda resources: TruthSnapshot(),
        allow_recovery=True,
    )
    if resumed is None or resumed.record.status != ActionStatus.UNKNOWN_RESULT:
        raise AssertionError("recovery did not preserve UNKNOWN_RESULT")
    if parent_gateway.calls != 0:
        raise AssertionError("recovery redispatched an action")
    after_pending = pending.get(approval_id)
    if after_pending is None or after_pending.status.value != "APPROVED":
        raise AssertionError("approved continuation state was not retained")

    reject_gateway = CountingGateway()
    reject_coordinator = ActionExecutionCoordinator(
        reject_gateway,
        PostgresActionStore(DATABASE_URL),
        PostgresResourceLocker(DATABASE_URL),
        pending_approvals=pending,
    )
    rejected_action = build_request(principal, "rejected")
    rejected_waiting = reject_coordinator.execute(rejected_action)
    if (
        rejected_waiting.record.status != ActionStatus.REQUIRE_CONFIRMATION
        or not rejected_waiting.record.result
    ):
        raise AssertionError("rejection fixture did not reach confirmation")
    rejected_id = UUID(str(rejected_waiting.record.result["approval_id"]))
    rejected = reject_coordinator.approve_pending(
        rejected_id,
        household_id=HOUSEHOLD_ID,
        principal_id=principal,
        decision="REJECT",
        tool=rejected_action.tool,
        policy_service=policy(),
        policy_context=PolicyContext(principal_role="resident"),
        refresher=lambda resources: TruthSnapshot(),
    )
    if rejected is None or rejected.record.status != ActionStatus.POLICY_DENIED:
        raise AssertionError("rejection did not stop the action")
    rejection_row = pending.get(rejected_id)
    if rejection_row is None or rejection_row.status.value != "REJECTED":
        raise AssertionError("rejection was not durably distinct from policy denial")
    if reject_gateway.calls != 0:
        raise AssertionError("rejection dispatched an action")

    print(
        json.dumps(
            {
                "scenario_id": "APPROVAL_CONTINUATION_PROCESS_CRASH_NO_REDISPATCH",
                "evidence_level": "POSTGRES_PROCESS_DETERMINISTIC_POLICY",
                "status": "PASS",
                "child_exit_code": result.returncode,
                "approval_consumed_before_crash": True,
                "pre_recovery_status": in_flight.status.value,
                "recovered_status": recovered[0].status.value,
                "post_recovery_status": resumed.record.status.value,
                "redispatches_after_recovery": parent_gateway.calls,
                "rejection_status": rejection_row.status.value,
                "rejection_action_status": rejected.record.status.value,
                "rejection_dispatches": reject_gateway.calls,
                "checked_at": datetime.now(UTC).isoformat(),
                "phase15": False,
            },
            sort_keys=True,
        )
    )
    marker.unlink(missing_ok=True)
    return 0


if len(sys.argv) > 1 and sys.argv[1] == "--child":
    if len(sys.argv) != 4:
        raise SystemExit("child requires approval_id and principal_id")
    # The child reconstructs the exact pending action from PostgreSQL rather
    # than receiving executable arguments from a caller.
    approval = UUID(sys.argv[2])
    principal_value = UUID(sys.argv[3])
    pending_row = PostgresPendingApprovalStore(DATABASE_URL).get(approval)
    if pending_row is None:
        raise SystemExit("pending approval not found")
    reconstructed = ActionRequest.create(
        action_id=pending_row.action_id,
        action_intent_id=pending_row.action_intent_id,
        idempotency_key=pending_row.idempotency_key,
        household_id=pending_row.household_id,
        tool=tool(),
        arguments=dict(pending_row.arguments),
        identity=IdentityContext(HOUSEHOLD_ID, principal_value, Assurance.AUTHENTICATED),
        policy_service=policy(),
        policy_context=PolicyContext(principal_role="resident"),
        refresher=lambda resources: TruthSnapshot(),
        origin=RequestOrigin.DIRECT_USER,
    )
    raise SystemExit(
        child(
            approval,
            principal_value,
            Path(os.environ["ANIMA_CRASH_MARKER"]),
            reconstructed,
        )
    )


if __name__ == "__main__":
    raise SystemExit(main())
