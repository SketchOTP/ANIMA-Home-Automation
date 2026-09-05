"""Prove durable approved-action results survive a continuation crash.

The child executes a real PostgreSQL approval continuation, then exits after
the action store has durably recorded success but before continuation
completion. The parent proves wrong-principal rejection and no redispatch.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any
from uuid import UUID, uuid4

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.verify_phase12_h5u_confirmation import (  # noqa: E402
    HOUSEHOLD_ID,
    ConfirmationByValidity,
    tool,
)

from anima_ha.action import (  # noqa: E402
    ActionExecutionCoordinator,
    ActionRequest,
    ActionStatus,
    PostgresActionStore,
    PostgresPendingApprovalStore,
    PostgresResourceLocker,
    TruthSnapshot,
)
from anima_ha.db.migrate import migrate  # noqa: E402
from anima_ha.plugins import (  # noqa: E402
    ExternalContentTrust,
    InvocationOutcome,
    InvocationResult,
)
from anima_ha.policy import (  # noqa: E402
    Assurance,
    IdentityContext,
    PolicyContext,
    PolicyService,
    PostgresPolicyStore,
)

DATABASE_URL = os.environ.get("ANIMA_DATABASE_URL", "")
ROOT = Path(__file__).resolve().parents[1]


class CountingGateway:
    def __init__(self, marker: Path | None = None) -> None:
        self.calls = 0
        self.marker = marker

    def invoke(self, tool_id: str, arguments: dict[str, Any], **kwargs: Any) -> InvocationResult:
        del arguments, kwargs
        self.calls += 1
        if self.marker is not None:
            with self.marker.open("a", encoding="utf-8") as stream:
                stream.write("dispatch\n")
        return InvocationResult(
            InvocationOutcome.SUCCESS,
            tool_id,
            "anima.test",
            "1.0.0",
            1.0,
            result={"accepted": True},
            external_content_trust=ExternalContentTrust.PLUGIN_TRUSTED,
        )


class CrashAfterDurableComplete(PostgresPendingApprovalStore):
    """Crash after action success, before continuation completion."""

    def __init__(self, database_url: str, marker: Path) -> None:
        super().__init__(database_url)
        self.marker = marker

    def complete(self, approval_id: UUID, *, status: Any, outcome_refs: dict[str, Any]) -> None:
        del approval_id, status, outcome_refs
        self.marker.write_text("action_result_durable", encoding="utf-8")
        os._exit(72)


class FreshPower:
    def __init__(self) -> None:
        self.values = iter(("off", "on"))

    def __call__(self, resources: Any) -> TruthSnapshot:
        del resources
        return TruthSnapshot(
            {"power": {"state": "KNOWN", "value": next(self.values), "version": "1"}}
        )


def build_request(principal: UUID) -> ActionRequest:
    return ActionRequest.create(
        action_id=uuid4(),
        action_intent_id=uuid4(),
        idempotency_key=f"phase14-approval-durable-{uuid4()}",
        household_id=HOUSEHOLD_ID,
        tool=tool(),
        arguments={"resource_id": str(uuid4()), "desired_on": True},
        identity=IdentityContext(HOUSEHOLD_ID, principal, Assurance.AUTHENTICATED),
        policy_service=PolicyService(
            ConfirmationByValidity(), audit_store=PostgresPolicyStore(DATABASE_URL)
        ),
        policy_context=PolicyContext(principal_role="resident"),
        refresher=lambda resources: TruthSnapshot(
            {"power": {"state": "KNOWN", "value": "off", "version": "1"}}
        ),
    )


def run_child(approval_id: UUID, principal: UUID, marker: Path, dispatches: Path) -> int:
    pending = CrashAfterDurableComplete(DATABASE_URL, marker)
    coordinator = ActionExecutionCoordinator(
        CountingGateway(dispatches),
        PostgresActionStore(DATABASE_URL),
        PostgresResourceLocker(DATABASE_URL),
        pending_approvals=pending,
    )
    coordinator.approve_pending(
        approval_id,
        household_id=HOUSEHOLD_ID,
        principal_id=principal,
        decision="APPROVE",
        tool=tool(),
        policy_service=PolicyService(
            ConfirmationByValidity(), audit_store=PostgresPolicyStore(DATABASE_URL)
        ),
        policy_context=PolicyContext(principal_role="resident"),
        refresher=FreshPower(),
        allow_recovery=True,
    )
    raise AssertionError("continuation unexpectedly returned after crash hook")


def main() -> int:
    if not DATABASE_URL:
        raise RuntimeError("ANIMA_DATABASE_URL is required")
    migrate(DATABASE_URL, 5)
    principal = uuid4()
    pending = PostgresPendingApprovalStore(DATABASE_URL)
    initial = ActionExecutionCoordinator(
        CountingGateway(),
        PostgresActionStore(DATABASE_URL),
        PostgresResourceLocker(DATABASE_URL),
        pending_approvals=pending,
    )
    waiting = initial.execute(build_request(principal))
    if waiting.record.status != ActionStatus.REQUIRE_CONFIRMATION or not waiting.record.result:
        raise AssertionError(f"expected confirmation, got {waiting.record.status}")
    approval_id = UUID(str(waiting.record.result["approval_id"]))
    marker = Path(f"/tmp/anima-phase14-durable-{approval_id}.marker")
    dispatches = Path(f"/tmp/anima-phase14-durable-{approval_id}.dispatches")
    marker.unlink(missing_ok=True)
    dispatches.unlink(missing_ok=True)
    child_result = subprocess.run(
        [sys.executable, __file__, "--child", str(approval_id), str(principal)],
        cwd=ROOT,
        env={**os.environ, "ANIMA_DATABASE_URL": DATABASE_URL},
        capture_output=True,
        text=True,
    )
    if child_result.returncode != 72 or not marker.exists():
        raise AssertionError(f"durable-result child missed crash hook: {child_result.stderr}")
    action = PostgresActionStore(DATABASE_URL).get(waiting.record.action_id)
    if action is None or action.status != ActionStatus.SUCCEEDED or not action.result:
        raise AssertionError("terminal action result was not durable before continuation loss")
    stored = pending.get(approval_id)
    if stored is None or stored.status.value != "APPROVED":
        raise AssertionError("approved continuation state disappeared")

    wrong = initial.approve_pending(
        approval_id,
        household_id=HOUSEHOLD_ID,
        principal_id=uuid4(),
        decision="APPROVE",
        tool=tool(),
        policy_service=PolicyService(
            ConfirmationByValidity(), audit_store=PostgresPolicyStore(DATABASE_URL)
        ),
        policy_context=PolicyContext(principal_role="resident"),
        refresher=FreshPower(),
        allow_recovery=True,
    )
    if wrong is not None:
        raise AssertionError("wrong principal resumed approved continuation")

    recovery_gateway = CountingGateway()
    recovered = ActionExecutionCoordinator(
        recovery_gateway,
        PostgresActionStore(DATABASE_URL),
        PostgresResourceLocker(DATABASE_URL),
        pending_approvals=pending,
    ).approve_pending(
        approval_id,
        household_id=HOUSEHOLD_ID,
        principal_id=principal,
        decision="APPROVE",
        tool=tool(),
        policy_service=PolicyService(
            ConfirmationByValidity(), audit_store=PostgresPolicyStore(DATABASE_URL)
        ),
        policy_context=PolicyContext(principal_role="resident"),
        refresher=FreshPower(),
        allow_recovery=True,
    )
    if recovered is None or recovered.record.status != ActionStatus.SUCCEEDED:
        raise AssertionError("recovery did not reuse the durable terminal result")
    if recovery_gateway.calls != 0:
        raise AssertionError("recovery redispatched a durable action")
    if dispatches.read_text(encoding="utf-8").splitlines() != ["dispatch"]:
        raise AssertionError("expected exactly one child dispatch")
    print(
        json.dumps(
            {
                "scenario_id": "CONTINUATION_POST_ACTION_DURABLE_NO_DUPLICATE_RESULT",
                "status": "PASS",
                "evidence_level": "POSTGRES_PROCESS_OPA",
                "child_exit_code": child_result.returncode,
                "action_status_after_crash": action.status.value,
                "recovered_status": recovered.record.status.value,
                "wrong_principal_rejected": True,
                "dispatches_total": 1,
                "recovery_dispatches": recovery_gateway.calls,
                "phase15": False,
            },
            sort_keys=True,
        )
    )
    marker.unlink(missing_ok=True)
    dispatches.unlink(missing_ok=True)
    return 0


if len(sys.argv) > 1 and sys.argv[1] == "--child":
    if len(sys.argv) != 4:
        raise SystemExit("child requires approval_id and principal_id")
    child_approval = UUID(sys.argv[2])
    child_marker = Path(f"/tmp/anima-phase14-durable-{child_approval}.marker")
    child_dispatches = Path(f"/tmp/anima-phase14-durable-{child_approval}.dispatches")
    raise SystemExit(run_child(child_approval, UUID(sys.argv[3]), child_marker, child_dispatches))


if __name__ == "__main__":
    raise SystemExit(main())
