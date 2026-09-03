from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID, uuid4

from anima_ha.action import (
    ActionExecutionCoordinator,
    ActionRequest,
    ActionStatus,
    InMemoryActionStore,
    InMemoryPendingApprovalStore,
    InMemoryResourceLocker,
    PendingApprovalStatus,
    TruthPrecondition,
    TruthSnapshot,
    VerificationOutcome,
    VerificationResult,
)
from anima_ha.plugins import (
    ExternalContentTrust,
    Idempotency,
    InvocationOutcome,
    InvocationResult,
    ToolDescriptor,
)
from anima_ha.policy import Assurance, IdentityContext, PolicyService

HOUSEHOLD = UUID("ecbd0d84-6f5f-40f8-928f-1d5dfe758dd7")
RESOURCE = UUID("3c2bd8c5-5d31-4d3c-87b7-59d6a4de62ce")
RESOURCE_2 = UUID("22e4e13a-040f-44c9-90a6-1f3a0ebd8b56")


class AllowEvaluator:
    def evaluate(self, document: dict[str, Any]) -> dict[str, Any]:
        return {"decision": "ALLOW", "reason_code": "ALLOWED", "policy_version": "test"}


class DenyEvaluator:
    def evaluate(self, document: dict[str, Any]) -> dict[str, Any]:
        return {"decision": "DENY", "reason_code": "DENIED", "policy_version": "test"}


class ConfirmationEvaluator:
    def evaluate(self, document: dict[str, Any]) -> dict[str, Any]:
        return {
            "decision": "REQUIRE_CONFIRMATION",
            "reason_code": "CONFIRM_REQUIRED",
            "policy_version": "test",
            "confirmation_required": True,
        }


class Gateway:
    def __init__(
        self, outcome: InvocationOutcome = InvocationOutcome.SUCCESS, result: Any = None
    ) -> None:
        self.outcome = outcome
        self.result = (
            result
            if result is not None
            else {
                "outcome": "SUCCESS",
                "observed_state": "on",
            }
        )
        self.calls = 0
        self.contexts: list[Any] = []
        self.action_intent_ids: list[UUID | None] = []

    def invoke(self, tool_id: str, arguments: dict[str, Any], **kwargs: Any) -> InvocationResult:
        self.calls += 1
        self.contexts.append(kwargs.get("execution_context"))
        self.action_intent_ids.append(kwargs.get("action_intent_id"))
        return InvocationResult(
            self.outcome,
            tool_id,
            "anima.test",
            "1.0.0",
            1.0,
            result=self.result,
            error_class="TIMEOUT" if self.outcome == InvocationOutcome.PLUGIN_TIMEOUT else None,
            external_content_trust=ExternalContentTrust.PLUGIN_TRUSTED,
        )


def tool(*, provider_idempotency_supported: bool = False) -> ToolDescriptor:
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
        provenance="test",
        execution_spec={
            "profile": "set_power",
            "provider_idempotency_supported": provider_idempotency_supported,
        },
    )


def request(
    gateway: Gateway,
    *,
    key: str = "action-1",
    evaluator: Any = None,
    refresher: Any = None,
    preconditions: tuple[TruthPrecondition, ...] = (),
    verifier: Any = None,
    provider_idempotency_supported: bool = False,
) -> tuple[ActionExecutionCoordinator, ActionRequest, Gateway, InMemoryActionStore]:
    store = InMemoryActionStore()
    coordinator = ActionExecutionCoordinator(gateway, store, InMemoryResourceLocker())
    snapshots = iter(
        [
            TruthSnapshot({"power": {"state": "KNOWN", "value": "off", "version": "1"}}),
            TruthSnapshot({"power": {"state": "KNOWN", "value": "on", "version": "2"}}),
        ]
    )
    action = ActionRequest.create(
        idempotency_key=key,
        household_id=HOUSEHOLD,
        tool=tool(provider_idempotency_supported=provider_idempotency_supported),
        arguments={"resource_id": str(RESOURCE), "desired_on": True},
        identity=IdentityContext(HOUSEHOLD, None, Assurance.AUTHENTICATED),
        policy_service=PolicyService(evaluator or AllowEvaluator()),
        refresher=refresher or (lambda resources: next(snapshots)),
        preconditions=preconditions,
        verifier=verifier,
    )
    return coordinator, action, gateway, store


def test_stale_precondition_is_rejected_before_gateway() -> None:
    gateway = Gateway()
    coordinator, action, gateway, _ = request(
        gateway,
        preconditions=(TruthPrecondition("power", expected_value="off", expected_version="old"),),
        refresher=lambda resources: TruthSnapshot(
            {"power": {"state": "KNOWN", "value": "on", "version": "new"}}
        ),
    )
    result = coordinator.execute(action)
    assert result.record.status == ActionStatus.PRECONDITION_FAILED
    assert gateway.calls == 0


def test_system_owned_precondition_is_required_even_when_request_omits_one() -> None:
    gateway = Gateway()
    coordinator, action, gateway, _ = request(
        gateway,
        refresher=lambda resources: TruthSnapshot(
            {"power": {"state": "UNKNOWN", "value": None, "version": "lost"}}
        ),
    )
    result = coordinator.execute(action)
    assert result.record.status == ActionStatus.PRECONDITION_FAILED
    assert gateway.calls == 0


def test_busy_resource_is_not_queued() -> None:
    gateway = Gateway()
    coordinator, action, _, _ = request(gateway)
    with coordinator.locker.try_acquire((RESOURCE,)) as held:
        assert held
        result = coordinator.execute(action)
    assert result.record.status == ActionStatus.RESOURCE_BUSY
    assert gateway.calls == 0


def test_distinct_resource_can_progress_while_another_resource_is_held() -> None:
    gateway = Gateway()
    coordinator, action, _, _ = request(gateway)
    distinct = ActionRequest.create(
        action_id=uuid4(),
        idempotency_key="action-distinct-resource",
        household_id=HOUSEHOLD,
        tool=tool(),
        arguments={"resource_id": str(RESOURCE_2), "desired_on": True},
        identity=action.identity,
        policy_service=action.policy_service,
        refresher=action.refresher,
    )
    with coordinator.locker.try_acquire((RESOURCE,)) as held:
        assert held
        result = coordinator.execute(distinct)
    assert result.record.status == ActionStatus.SUCCEEDED
    assert gateway.calls == 1


def test_idempotency_replays_without_second_connector_call_and_rejects_key_reuse() -> None:
    gateway = Gateway()
    coordinator, action, gateway, _ = request(gateway)
    first = coordinator.execute(action)
    second = coordinator.execute(action)
    assert first.record.status == ActionStatus.SUCCEEDED
    assert second.duplicate is True
    assert gateway.calls == 1

    changed = ActionRequest.create(
        action_id=uuid4(),
        idempotency_key=action.idempotency_key,
        household_id=HOUSEHOLD,
        tool=tool(),
        arguments={"resource_id": str(RESOURCE), "desired_on": False},
        identity=action.identity,
        policy_service=action.policy_service,
    )
    conflict = coordinator.execute(changed)
    assert conflict.idempotency_conflict is True
    assert gateway.calls == 1


def test_provider_idempotency_context_is_forwarded_without_model_arguments() -> None:
    gateway = Gateway()
    coordinator, action, gateway, _ = request(gateway, provider_idempotency_supported=True)
    result = coordinator.execute(action)
    assert result.record.status == ActionStatus.SUCCEEDED
    context = gateway.contexts[0]
    assert context.execution_id == action.action_id
    assert context.anima_idempotency_key == action.idempotency_key
    assert context.provider_idempotency_key == f"anima:{action.action_id}"
    assert gateway.action_intent_ids == [action.action_intent_id]
    assert "provider_idempotency_key" not in action.arguments


def test_connector_without_native_idempotency_remains_executable() -> None:
    gateway = Gateway()
    coordinator, action, gateway, _ = request(gateway)
    result = coordinator.execute(action)
    assert result.record.status == ActionStatus.SUCCEEDED
    assert gateway.contexts[0].provider_idempotency_key is None


def test_ambiguous_connector_timeout_is_unknown_and_not_retried() -> None:
    gateway = Gateway(InvocationOutcome.PLUGIN_TIMEOUT)
    snapshots = iter(
        [
            TruthSnapshot({"power": {"state": "KNOWN", "value": "off", "version": "1"}}),
            TruthSnapshot({"power": {"state": "UNKNOWN", "value": None, "version": "lost"}}),
        ]
    )
    coordinator, action, gateway, store = request(
        gateway,
        refresher=lambda resources: next(snapshots),
    )
    result = coordinator.execute(action)
    assert result.record.status == ActionStatus.UNKNOWN_RESULT
    assert gateway.calls == 1
    assert store.get(action.action_id) == result.record


def test_ambiguous_timeout_is_success_when_fresh_observation_proves_effect() -> None:
    gateway = Gateway(InvocationOutcome.PLUGIN_TIMEOUT)
    snapshots = iter(
        [
            TruthSnapshot({"power": {"state": "KNOWN", "value": "off", "version": "1"}}),
            TruthSnapshot({"power": {"state": "KNOWN", "value": "on", "version": "2"}}),
        ]
    )
    coordinator, action, gateway, _ = request(gateway, refresher=lambda resources: next(snapshots))
    result = coordinator.execute(action)
    assert result.record.status == ActionStatus.SUCCEEDED
    assert result.record.result is not None
    assert result.record.result["connector_ambiguity"] is True
    assert gateway.calls == 1


def test_ambiguous_timeout_with_definitive_non_matching_observation_fails() -> None:
    gateway = Gateway(InvocationOutcome.PLUGIN_TIMEOUT)
    snapshots = iter(
        [
            TruthSnapshot({"power": {"state": "KNOWN", "value": "off", "version": "1"}}),
            TruthSnapshot({"power": {"state": "KNOWN", "value": "off", "version": "2"}}),
        ]
    )
    coordinator, action, gateway, _ = request(gateway, refresher=lambda resources: next(snapshots))
    result = coordinator.execute(action)
    assert result.record.status == ActionStatus.VERIFICATION_FAILED
    assert gateway.calls == 1


def test_connector_effect_claim_cannot_create_success_without_observation() -> None:
    gateway = Gateway(result={"effects": [{"outcome": "SUCCEEDED", "observed": {"state": "on"}}]})
    snapshots = iter(
        [
            TruthSnapshot({"power": {"state": "KNOWN", "value": "off", "version": "1"}}),
            TruthSnapshot({"power": {"state": "KNOWN", "value": "off", "version": "2"}}),
        ]
    )
    coordinator, action, gateway, _ = request(gateway, refresher=lambda resources: next(snapshots))
    result = coordinator.execute(action)
    assert result.record.status == ActionStatus.VERIFICATION_FAILED
    assert result.record.result is not None
    assert result.record.result["connector_evidence"]["effects"][0]["outcome"] == "SUCCEEDED"


def test_already_satisfied_action_does_not_dispatch() -> None:
    gateway = Gateway()
    coordinator, action, gateway, _ = request(
        gateway,
        refresher=lambda resources: TruthSnapshot(
            {"power": {"state": "KNOWN", "value": "on", "version": "1"}}
        ),
    )
    result = coordinator.execute(action)
    assert result.record.status == ActionStatus.SUCCEEDED
    assert result.record.result == {
        "executed": False,
        "effects": [
            {
                "effect_id": "set_power:power",
                "truth_key": "power",
                "expected_state": "KNOWN",
                "expected_value": "on",
                "outcome": "VERIFIED",
                "observed": {"state": "KNOWN", "value": "on", "version": "1"},
                "source": "FRESH_TRUTH",
                "detail": None,
            }
        ],
        "observed": {"power": {"state": "KNOWN", "value": "on", "version": "1"}},
    }
    assert gateway.calls == 0


def test_partial_effects_are_durable_without_compensation() -> None:
    gateway = Gateway(
        result={
            "effects": [
                {"outcome": "SUCCEEDED", "observed": {"state": "on"}},
                {"outcome": "UNKNOWN", "detail": "timeout after dispatch"},
            ]
        }
    )
    snapshots = iter(
        [
            TruthSnapshot(
                {
                    "power": {"state": "KNOWN", "value": "off", "version": "1"},
                    "backup": {"state": "KNOWN", "value": "off", "version": "1"},
                }
            ),
            TruthSnapshot(
                {
                    "power": {"state": "KNOWN", "value": "on", "version": "2"},
                    "backup": {"state": "UNKNOWN", "value": None, "version": "2"},
                }
            ),
        ]
    )
    coordinator, action, _, store = request(gateway, refresher=lambda resources: next(snapshots))
    result = coordinator.execute(action)
    assert result.record.status == ActionStatus.PARTIAL
    assert len(store.effects) == 2


def test_verification_failure_is_not_success() -> None:
    gateway = Gateway()
    coordinator, action, _, _ = request(
        gateway,
        verifier=lambda request, invocation, snapshot: VerificationResult(
            VerificationOutcome.FAILED, detail="state remained off"
        ),
    )
    result = coordinator.execute(action)
    assert result.record.status == ActionStatus.VERIFICATION_FAILED


def test_verifier_receives_post_action_refresh() -> None:
    gateway = Gateway()
    snapshots = iter(
        [
            TruthSnapshot({"power": {"state": "KNOWN", "value": "off", "version": "1"}}),
            TruthSnapshot({"power": {"state": "KNOWN", "value": "on", "version": "2"}}),
        ]
    )
    seen: list[str] = []

    def verify(request: Any, invocation: Any, snapshot: TruthSnapshot) -> VerificationResult:
        seen.append(str(snapshot.values["power"]["version"]))
        return VerificationResult(VerificationOutcome.VERIFIED, dict(snapshot.values["power"]))

    coordinator, action, _, _ = request(
        gateway,
        refresher=lambda resources: next(snapshots),
        verifier=verify,
    )
    result = coordinator.execute(action)
    assert result.record.status == ActionStatus.SUCCEEDED
    assert seen == ["2"]


def test_policy_denial_never_marks_execution_or_calls_gateway() -> None:
    gateway = Gateway()
    coordinator, action, gateway, _ = request(gateway, evaluator=DenyEvaluator())
    result = coordinator.execute(action)
    assert result.record.status == ActionStatus.POLICY_DENIED
    assert gateway.calls == 0


def test_confirmation_is_durable_exact_intent_and_resumes_once() -> None:
    gateway = Gateway()
    pending = InMemoryPendingApprovalStore()
    store = InMemoryActionStore()
    coordinator = ActionExecutionCoordinator(
        gateway, store, InMemoryResourceLocker(), pending_approvals=pending
    )
    principal = uuid4()
    snapshots = iter(
        [
            TruthSnapshot({"power": {"state": "KNOWN", "value": "off", "version": "1"}}),
            TruthSnapshot({"power": {"state": "KNOWN", "value": "off", "version": "2"}}),
            TruthSnapshot({"power": {"state": "KNOWN", "value": "on", "version": "2"}}),
        ]
    )
    action = ActionRequest.create(
        idempotency_key="confirmation-action",
        household_id=HOUSEHOLD,
        tool=tool(),
        arguments={"resource_id": str(RESOURCE), "desired_on": True},
        identity=IdentityContext(HOUSEHOLD, principal, Assurance.AUTHENTICATED),
        policy_service=PolicyService(ConfirmationEvaluator()),
        refresher=lambda resources: next(snapshots),
    )
    first = coordinator.execute(action)
    assert first.record.status == ActionStatus.REQUIRE_CONFIRMATION
    assert first.record.result is not None
    approval_id = UUID(str(first.record.result["approval_id"]))
    approval = pending.get(approval_id)
    assert approval is not None
    assert approval.action_intent_id == action.action_intent_id
    assert gateway.calls == 0

    approved = coordinator.approve_pending(
        approval_id,
        household_id=HOUSEHOLD,
        principal_id=principal,
        decision="APPROVE",
        tool=action.tool,
        policy_service=PolicyService(AllowEvaluator()),
        refresher=lambda resources: next(snapshots),
    )
    assert approved is not None
    assert approved.record.status == ActionStatus.SUCCEEDED
    assert gateway.calls == 1
    assert (
        coordinator.approve_pending(
            approval_id,
            household_id=HOUSEHOLD,
            principal_id=principal,
            decision="APPROVE",
            tool=action.tool,
            policy_service=PolicyService(AllowEvaluator()),
            refresher=lambda resources: next(snapshots),
        )
        is None
    )


def test_confirmation_wrong_principal_reject_and_expiry_are_fail_closed() -> None:
    pending = InMemoryPendingApprovalStore()
    gateway = Gateway()
    store = InMemoryActionStore()
    coordinator = ActionExecutionCoordinator(
        gateway, store, InMemoryResourceLocker(), pending_approvals=pending
    )
    principal = uuid4()
    action = ActionRequest.create(
        idempotency_key="confirmation-boundary",
        household_id=HOUSEHOLD,
        tool=tool(),
        arguments={"resource_id": str(RESOURCE), "desired_on": True},
        identity=IdentityContext(HOUSEHOLD, principal, Assurance.AUTHENTICATED),
        policy_service=PolicyService(ConfirmationEvaluator()),
        refresher=lambda resources: TruthSnapshot(
            {"power": {"state": "KNOWN", "value": "off", "version": "1"}}
        ),
    )
    first = coordinator.execute(action)
    assert first.record.result is not None
    approval_id = UUID(str(first.record.result["approval_id"]))
    assert (
        coordinator.approve_pending(
            approval_id,
            household_id=HOUSEHOLD,
            principal_id=uuid4(),
            decision="APPROVE",
            tool=action.tool,
            policy_service=PolicyService(AllowEvaluator()),
        )
        is None
    )
    current = pending.get(approval_id)
    assert current is not None
    assert current.status == PendingApprovalStatus.PENDING
    rejected = coordinator.approve_pending(
        approval_id,
        household_id=HOUSEHOLD,
        principal_id=principal,
        decision="REJECT",
        tool=action.tool,
        policy_service=PolicyService(AllowEvaluator()),
    )
    assert rejected is not None
    assert rejected.record.status == ActionStatus.POLICY_DENIED
    assert gateway.calls == 0
    assert (
        coordinator.approve_pending(
            approval_id,
            household_id=HOUSEHOLD,
            principal_id=principal,
            decision="APPROVE",
            tool=action.tool,
            policy_service=PolicyService(AllowEvaluator()),
        )
        is None
    )

    expiring = ActionRequest.create(
        idempotency_key="confirmation-expiry",
        household_id=HOUSEHOLD,
        tool=tool(),
        arguments={"resource_id": str(RESOURCE), "desired_on": True},
        identity=IdentityContext(HOUSEHOLD, principal, Assurance.AUTHENTICATED),
        policy_service=PolicyService(ConfirmationEvaluator()),
        refresher=lambda resources: TruthSnapshot(
            {"power": {"state": "KNOWN", "value": "off", "version": "1"}}
        ),
    )
    expired_result = coordinator.execute(expiring)
    assert expired_result.record.result is not None
    expired_id = UUID(str(expired_result.record.result["approval_id"]))
    assert (
        coordinator.approve_pending(
            expired_id,
            household_id=HOUSEHOLD,
            principal_id=principal,
            decision="APPROVE",
            tool=expiring.tool,
            policy_service=PolicyService(AllowEvaluator()),
            now=datetime.now(UTC) + timedelta(minutes=3),
        )
        is None
    )
    expired = pending.get(expired_id)
    assert expired is not None
    assert expired.status == PendingApprovalStatus.EXPIRED


def test_restart_recovery_marks_planned_and_executing_without_retry() -> None:
    gateway = Gateway()
    coordinator, action, _, store = request(gateway)
    claimed = store.claim(action)
    store.update(claimed.record.action_id, ActionStatus.EXECUTING)
    recovered = store.recover_incomplete()
    assert recovered[0].status == ActionStatus.UNKNOWN_RESULT
    assert coordinator.execute(action).duplicate is True
    assert gateway.calls == 0
