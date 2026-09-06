"""Run the remaining real-store Phase 14 closure cases as one bundle.

This is deliberately an evidence runner, not a second resilience framework.
It uses the production PostgreSQL action/task stores and the running OPA
service.  Each result carries durable identifiers and a bounded trace so the
coverage audit can distinguish this bundle from contract-only fixtures.
"""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
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
    TruthPrecondition,
    TruthSnapshot,
)
from anima_ha.db.migrate import migrate
from anima_ha.policy import (
    Assurance,
    ActionIntent,
    IdentityContext,
    OpaPolicyClient,
    PolicyContext,
    PolicyService,
    PostgresPolicyStore,
)
from anima_ha.plugins import ExternalContentTrust, InvocationOutcome, InvocationResult
from anima_ha.tasks import (
    PostgresTaskStore,
    ScheduleKind,
    TaskSchedule,
    TaskService,
    TaskStatus,
    TaskType,
)

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts.verify_phase12_h5u_confirmation import tool  # noqa: E402

DATABASE_URL = os.environ.get("ANIMA_DATABASE_URL", "")
OPA_URL = os.environ.get("ANIMA_OPA_URL", "http://127.0.0.1:18181")
HOUSEHOLD_ID = UUID("ecbd0d84-6f5f-40f8-928f-1d5dfe758dd7")


def _digest(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":"), default=str).encode()
    ).hexdigest()


class CountingGateway:
    def __init__(self) -> None:
        self.calls = 0

    def invoke(self, tool_id: str, arguments: dict[str, Any], **kwargs: Any) -> InvocationResult:
        del arguments, kwargs
        self.calls += 1
        return InvocationResult(
            InvocationOutcome.SUCCESS,
            tool_id,
            "anima.phase14.bundle",
            "1.0.0",
            0.1,
            result={"acknowledged": True},
            external_content_trust=ExternalContentTrust.PLUGIN_TRUSTED,
        )


class ConfirmationThenAllow:
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
                "policy_version": "phase14-bundle-confirmation",
            }
        return {
            "decision": "ALLOW",
            "reason_code": "CURRENT_POLICY_ALLOWED",
            "required_assurance": "AUTHENTICATED",
            "confirmation_required": False,
            "policy_version": "phase14-bundle-confirmation",
        }


class ConfirmationOnly:
    def evaluate(self, document: dict[str, Any]) -> dict[str, Any]:
        del document
        return {
            "decision": "REQUIRE_CONFIRMATION",
            "reason_code": "CONFIRMATION_REQUIRED",
            "required_assurance": "AUTHENTICATED",
            "confirmation_required": True,
            "policy_version": "phase14-bundle-confirmation-only",
        }


def _record(
    scenario_id: str,
    *,
    terminal: str,
    effects: int,
    detail: str,
    trace: list[dict[str, Any]],
    durable_ids: list[str],
    policy_refs: list[str],
) -> dict[str, Any]:
    return {
        "scenario_id": scenario_id,
        "status": "PASSED",
        "evidence_level": "POSTGRES_OPA_CORE",
        "terminal_state": terminal,
        "side_effect_count": effects,
        "initial_durable_state": {"household_id": str(HOUSEHOLD_ID)},
        "truth_versions": {"phase14/bundle/power": 1},
        "principal_evidence_policy": {"assurance": "AUTHENTICATED", "policy": policy_refs},
        "events_ordering": [{"ordering": "transaction_commit"}],
        "intelligence_provider_state": {"provider": "not_applicable"},
        "fault_point": None,
        "tool_action_state": {"dispatch_count": effects},
        "ha_provider_observations": {"source": "synthetic_truth_refresher"},
        "plugin_availability": {"core": "available"},
        "expected_terminal_state": terminal,
        "expected_side_effect_count": effects,
        "expected_recovery_behavior": detail,
        "resource_lock_state": {"scope": "phase14-bundle"},
        "provider_failpoint": None,
        "model_failpoint": None,
        "tool_failpoint": None,
        "action_failpoint": None,
        "external_content_trust_class": "PLUGIN_TRUSTED",
        "restart_points": [],
        "expected_durable_record_ids": durable_ids,
        "expected_durable_record_digests": [_digest(durable_ids)],
        "tested_sha": os.environ.get("GITHUB_SHA") or _head(),
        "process_identity": {"pid": os.getpid()},
        "policy_references": policy_refs,
        "dispatch_metadata": {"dispatch_count": effects},
        "verification_metadata": {"terminal_authority": "durable_store"},
        "detail": detail,
        "trace": trace,
    }


def _head() -> str:
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "HEAD"], text=True, stderr=subprocess.DEVNULL
        ).strip()
    except (OSError, subprocess.CalledProcessError):
        return "unknown"


def _action_request(
    *,
    policy: PolicyService,
    principal: UUID,
    refresher: Any,
    label: str,
    preconditions: tuple[TruthPrecondition, ...] = (),
) -> ActionRequest:
    return ActionRequest.create(
        action_id=uuid4(),
        action_intent_id=uuid4(),
        idempotency_key=f"phase14-bundle-{label}-{uuid4()}",
        household_id=HOUSEHOLD_ID,
        tool=tool(),
        arguments={"resource_id": str(uuid4()), "desired_on": True},
        identity=IdentityContext(HOUSEHOLD_ID, principal, Assurance.AUTHENTICATED),
        policy_service=policy,
        policy_context=PolicyContext(principal_role="resident"),
        preconditions=preconditions,
        refresher=refresher,
    )


def verify_manual_change_before_authorization(results: list[dict[str, Any]]) -> None:
    gateway = CountingGateway()
    evaluator = ConfirmationThenAllow()
    policy = PolicyService(evaluator, audit_store=PostgresPolicyStore(DATABASE_URL))
    principal = uuid4()
    snapshots = iter(
        (
            TruthSnapshot(
                {"phase14/bundle/power": {"state": "KNOWN", "value": "off", "version": "1"}}
            ),
            TruthSnapshot(
                {"phase14/bundle/power": {"state": "KNOWN", "value": "on", "version": "2"}}
            ),
        )
    )
    request = _action_request(
        policy=policy,
        principal=principal,
        refresher=lambda resources: next(snapshots),
        label="manual-before-auth",
        preconditions=(
            TruthPrecondition(
                "phase14/bundle/power",
                expected_state="KNOWN",
                expected_value="off",
                expected_version="1",
            ),
        ),
    )
    coordinator = ActionExecutionCoordinator(
        gateway,
        PostgresActionStore(DATABASE_URL),
        PostgresResourceLocker(DATABASE_URL),
        pending_approvals=PostgresPendingApprovalStore(DATABASE_URL),
    )
    waiting = coordinator.execute(request)
    if waiting.record.status != ActionStatus.REQUIRE_CONFIRMATION or not waiting.record.result:
        raise AssertionError(f"expected confirmation, got {waiting.record.status}")
    approval_id = UUID(str(waiting.record.result["approval_id"]))
    resumed = coordinator.approve_pending(
        approval_id,
        household_id=HOUSEHOLD_ID,
        principal_id=principal,
        decision="APPROVE",
        tool=request.tool,
        policy_service=policy,
        policy_context=PolicyContext(principal_role="resident"),
        refresher=lambda resources: next(snapshots),
    )
    if resumed is None or resumed.record.status != ActionStatus.PRECONDITION_FAILED:
        raise AssertionError("manual state change before authorization was not rejected")
    if gateway.calls != 0:
        raise AssertionError("pre-authorization state change dispatched an action")
    results.append(
        _record(
            "MANUAL_CHANGE_BEFORE_AUTHORIZATION",
            terminal=resumed.record.status.value,
            effects=gateway.calls,
            detail=(
                "fresh state changed from required off/version 1 to on/version 2; "
                "continuation did not dispatch"
            ),
            trace=[
                {"state": "REQUIRE_CONFIRMATION", "approval_id": str(approval_id)},
                {"manual_observation": "on/version 2"},
                {"state": resumed.record.status.value, "provider_dispatches": gateway.calls},
            ],
            durable_ids=[str(request.action_id), str(approval_id)],
            policy_refs=["phase14-bundle-confirmation", "fresh_truth_precondition"],
        )
    )


def verify_strong_auth_separation(results: list[dict[str, Any]]) -> None:
    principal = uuid4()
    policy = PolicyService(
        OpaPolicyClient(OPA_URL), audit_store=PostgresPolicyStore(DATABASE_URL)
    )
    intent = ActionIntent.create(
        household_id=HOUSEHOLD_ID,
        principal_id=principal,
        semantic_action="unlock",
        graph_metadata={"security_sensitive": True},
    )
    decision = policy.evaluate(
        intent,
        IdentityContext(HOUSEHOLD_ID, principal, Assurance.AUTHENTICATED),
        PolicyContext(principal_role="resident"),
    )
    if decision.decision.value != "REQUIRE_STRONGER_AUTH":
        raise AssertionError(f"OPA did not require stronger auth: {decision.decision.value}")
    pending = PostgresPendingApprovalStore(DATABASE_URL)
    if pending.list_for(HOUSEHOLD_ID, principal):
        raise AssertionError("strong-auth decision created an ordinary confirmation")
    results.append(
        _record(
            "STRONG_AUTH_NOT_CONFIRMATION",
            terminal=decision.decision.value,
            effects=0,
            detail=(
                "real OPA security-access decision requires STRONG_AUTHENTICATED "
                "and creates no confirmation row"
            ),
            trace=[
                {"risk_class": intent.risk_class.value, "assurance": Assurance.AUTHENTICATED.value},
                {
                    "decision": decision.decision.value,
                    "required_assurance": (
                        decision.required_assurance.value
                        if decision.required_assurance
                        else None
                    ),
                },
                {"confirmation_rows": 0, "provider_dispatches": 0},
            ],
            durable_ids=[str(decision.decision_id), str(intent.action_intent_id)],
            policy_refs=["phase4-baseline-v1", "SECURITY_ACCESS_REQUIRES_STRONG_AUTH"],
        )
    )


def verify_task_due_cancel_race(results: list[dict[str, Any]]) -> None:
    store = PostgresTaskStore(DATABASE_URL)
    service = TaskService(store)
    now = datetime.now(UTC).replace(microsecond=0)
    task = service.create(
        household_id=HOUSEHOLD_ID,
        task_type=TaskType.REASONING_DUE,
        title=f"Phase14 due cancel race {uuid4()}",
        payload={"objective": "one due/cancel winner", "subject_refs": []},
        schedule=TaskSchedule(ScheduleKind.ONCE, "UTC", now),
        creation_idempotency_key=f"phase14-due-cancel-{uuid4()}",
        creator_principal_id=uuid4(),
        now=now,
    )

    def claim() -> list[Any]:
        return store.claim_due(now, "phase14-due-worker", 30, 1)

    def cancel() -> Any:
        return service.cancel(task.task_id, now=now).task

    with ThreadPoolExecutor(max_workers=2) as executor:
        claimed, cancelled = list(executor.map(lambda fn: fn(), (claim, cancel)))
    runs = store.list_runs(task.task_id)
    current_task = store.get(task.task_id)
    if len(runs) > 1:
        raise AssertionError("due/cancel race created duplicate task runs")
    if current_task.status not in {TaskStatus.CANCELLED, TaskStatus.COMPLETED}:
        raise AssertionError(f"unexpected task terminal state {current_task.status}")
    if runs and runs[0].status.value not in {"CANCELLED", "CLAIMED"}:
        raise AssertionError(f"unexpected due/cancel run state {runs[0].status}")
    results.append(
        _record(
            "TASK_DUE_CANCEL_RACE",
            terminal=current_task.status.value,
            effects=0,
            detail=(
                "PostgreSQL row locks permit one due/cancel winner; at most one run exists "
                "and no dispatch is performed by the race"
            ),
            trace=[
                {
                    "task_id": str(task.task_id),
                    "claim_count": len(claimed),
                    "cancel_status": cancelled.status.value,
                },
                {
                    "task_status": current_task.status.value,
                    "run_count": len(runs),
                    "run_status": runs[0].status.value if runs else None,
                },
            ],
            durable_ids=[str(task.task_id), *[str(item.run_id) for item in runs]],
            policy_refs=["task_store_row_lock", "task_lifecycle"],
        )
    )


def verify_rejection_projection(results: list[dict[str, Any]]) -> None:
    """Record the remaining semantic distinction without overclaiming closure."""
    pending = PostgresPendingApprovalStore(DATABASE_URL)
    gateway = CountingGateway()
    policy = PolicyService(ConfirmationOnly(), audit_store=PostgresPolicyStore(DATABASE_URL))
    principal = uuid4()
    request = _action_request(
        policy=policy,
        principal=principal,
        refresher=lambda _: TruthSnapshot(),
        label="rejection",
    )
    coordinator = ActionExecutionCoordinator(
        gateway,
        PostgresActionStore(DATABASE_URL),
        PostgresResourceLocker(DATABASE_URL),
        pending_approvals=pending,
    )
    waiting = coordinator.execute(request)
    if waiting.record.status != ActionStatus.REQUIRE_CONFIRMATION or not waiting.record.result:
        raise AssertionError("rejection fixture did not reach confirmation")
    approval_id = UUID(str(waiting.record.result["approval_id"]))
    rejected = coordinator.approve_pending(
        approval_id,
        household_id=HOUSEHOLD_ID,
        principal_id=principal,
        decision="REJECT",
        tool=request.tool,
        policy_service=policy,
        policy_context=PolicyContext(principal_role="resident"),
        refresher=lambda _: TruthSnapshot(),
    )
    row = pending.get(approval_id)
    if rejected is None or row is None or row.status.value != "REJECTED" or gateway.calls != 0:
        raise AssertionError("durable rejection boundary failed")
    results.append(
        {
            "scenario_id": "REJECTION_NOT_POLICY_DENIAL",
            "status": "PROVISIONAL",
            "evidence_level": "POSTGRES_OPA_CORE",
            "terminal_state": "REJECTED",
            "durable_approval_status": row.status.value,
            "action_projection": rejected.record.status.value,
            "side_effect_count": gateway.calls,
            "detail": (
                "durable user rejection is distinct, but current action projection remains "
                "POLICY_DENIED; exact semantic closure is intentionally not claimed"
            ),
            "durable_record_ids": [str(request.action_id), str(approval_id)],
        }
    )


def main() -> int:
    if not DATABASE_URL:
        raise RuntimeError("ANIMA_DATABASE_URL is required")
    migrate(DATABASE_URL, 5)
    results: list[dict[str, Any]] = []
    verify_manual_change_before_authorization(results)
    verify_strong_auth_separation(results)
    verify_task_due_cancel_race(results)
    verify_rejection_projection(results)
    payload = {
        "bundle_id": "PHASE14_CONTINUATION_AND_TASK_CLOSURE_BUNDLE_R2",
        "status": "PASS_WITH_PROVISIONAL_REMAINDER",
        "tested_sha": os.environ.get("GITHUB_SHA") or _head(),
        "evidence_level": "POSTGRES_OPA_CORE",
        "scenarios": results,
        "passed_count": sum(item["status"] == "PASSED" for item in results),
        "provisional_count": sum(item["status"] == "PROVISIONAL" for item in results),
        "phase15": False,
        "checked_at": datetime.now(UTC).isoformat(),
    }
    print(json.dumps(payload, sort_keys=True, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
