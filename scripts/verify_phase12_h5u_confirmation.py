"""Verify durable exact-intent confirmation continuation with PostgreSQL stores."""

from __future__ import annotations

import json
import os
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
from anima_ha.plugins import (
    ExternalContentTrust,
    Idempotency,
    InvocationOutcome,
    InvocationResult,
    ToolDescriptor,
)
from anima_ha.policy import Assurance, IdentityContext, PolicyService, PostgresPolicyStore

DATABASE_URL = os.environ.get(
    "ANIMA_DATABASE_URL", "postgresql://anima:anima_dev_only@127.0.0.1:55432/anima"
)
HOUSEHOLD_ID = UUID("ecbd0d84-6f5f-40f8-928f-1d5dfe758dd7")
RESOURCE_ID = UUID("3c2bd8c5-5d31-4d3c-87b7-59d6a4de62ce")


class ConfirmationByValidity:
    def evaluate(self, document: dict[str, Any]) -> dict[str, Any]:
        if document.get("confirmation", {}).get("valid") is True:
            return {
                "decision": "ALLOW",
                "reason_code": "CONFIRMATION_VALID",
                "policy_version": "test",
            }
        return {
            "decision": "REQUIRE_CONFIRMATION",
            "reason_code": "CONFIRMATION_REQUIRED",
            "policy_version": "test",
            "confirmation_required": True,
        }


class Gateway:
    def __init__(self) -> None:
        self.calls = 0

    def invoke(self, tool_id: str, arguments: dict[str, Any], **kwargs: Any) -> InvocationResult:
        self.calls += 1
        return InvocationResult(
            InvocationOutcome.SUCCESS,
            tool_id,
            "anima.test",
            "1.0.0",
            1.0,
            result={"acknowledged": True},
            external_content_trust=ExternalContentTrust.PLUGIN_TRUSTED,
        )


def tool() -> ToolDescriptor:
    return ToolDescriptor(
        tool_id="anima.test.set_power",
        plugin_id="anima.test",
        capability_id="home.control",
        name="set_power",
        description="Set synthetic power.",
        input_schema={"type": "object"},
        output_schema={"type": "object"},
        risk_class="LOW_RISK_HOME_CONTROL",
        semantic_action="set_power",
        read_only=False,
        idempotency=Idempotency.KEYED,
        timeout=2.0,
        verification_requirement="PROVIDER_STATE_MATCH",
        external_content_trust=ExternalContentTrust.PLUGIN_TRUSTED,
        availability=True,
        version="1.0.0",
        provenance="h5u-postgres-confirmation",
        execution_spec={"profile": "set_power"},
    )


def main() -> int:
    audit = PostgresPolicyStore(DATABASE_URL)
    pending = PostgresPendingApprovalStore(DATABASE_URL)
    gateway = Gateway()
    coordinator = ActionExecutionCoordinator(
        gateway,
        PostgresActionStore(DATABASE_URL),
        PostgresResourceLocker(DATABASE_URL),
        pending_approvals=pending,
    )
    principal = uuid4()
    snapshots = iter(
        [
            TruthSnapshot({"power": {"state": "KNOWN", "value": "off", "version": "1"}}),
            TruthSnapshot({"power": {"state": "KNOWN", "value": "off", "version": "2"}}),
            TruthSnapshot({"power": {"state": "KNOWN", "value": "on", "version": "2"}}),
        ]
    )
    policy = PolicyService(ConfirmationByValidity(), audit_store=audit)
    request = ActionRequest.create(
        action_id=uuid4(),
        action_intent_id=uuid4(),
        idempotency_key=f"h5u-postgres-confirmation-{uuid4()}",
        household_id=HOUSEHOLD_ID,
        tool=tool(),
        arguments={"resource_id": str(RESOURCE_ID), "desired_on": True},
        identity=IdentityContext(HOUSEHOLD_ID, principal, Assurance.AUTHENTICATED),
        policy_service=policy,
        refresher=lambda resources: next(snapshots),
    )
    first = coordinator.execute(request)
    assert first.record.status == ActionStatus.REQUIRE_CONFIRMATION
    assert first.record.result is not None
    approval_id = UUID(str(first.record.result["approval_id"]))
    stored = pending.get(approval_id)
    assert stored is not None and stored.action_intent_id == request.action_intent_id
    assert "arguments" not in stored.to_payload()
    assert (
        coordinator.approve_pending(
            approval_id,
            household_id=HOUSEHOLD_ID,
            principal_id=uuid4(),
            decision="APPROVE",
            tool=request.tool,
            policy_service=policy,
            refresher=lambda resources: next(snapshots),
        )
        is None
    )
    still_pending = pending.get(approval_id)
    assert still_pending is not None and still_pending.status.value == "PENDING"
    approved = coordinator.approve_pending(
        approval_id,
        household_id=HOUSEHOLD_ID,
        principal_id=principal,
        decision="APPROVE",
        tool=request.tool,
        policy_service=policy,
        refresher=lambda resources: next(snapshots),
    )
    assert approved is not None and approved.record.status == ActionStatus.SUCCEEDED
    assert gateway.calls == 1
    assert (
        coordinator.approve_pending(
            approval_id,
            household_id=HOUSEHOLD_ID,
            principal_id=principal,
            decision="APPROVE",
            tool=request.tool,
            policy_service=policy,
        )
        is None
    )
    print(
        json.dumps(
            {
                "durable_store": "postgresql",
                "exact_intent_preserved": True,
                "pending_arguments_omitted_from_payload": True,
                "wrong_principal_rejected": True,
                "approval_status": approved.record.status.value,
                "provider_calls": gateway.calls,
                "single_use_replay_rejected": True,
                "phase13": False,
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
