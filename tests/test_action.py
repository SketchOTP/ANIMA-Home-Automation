from __future__ import annotations

from typing import Any
from uuid import UUID, uuid4

from anima_ha.action import (
    ActionExecutionCoordinator,
    ActionRequest,
    ActionStatus,
    InMemoryActionStore,
    InMemoryResourceLocker,
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

    def invoke(self, tool_id: str, arguments: dict[str, Any], **kwargs: Any) -> InvocationResult:
        self.calls += 1
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
        provenance="test",
    )


def request(
    gateway: Gateway,
    *,
    key: str = "action-1",
    evaluator: Any = None,
    refresher: Any = None,
    preconditions: tuple[TruthPrecondition, ...] = (),
    verifier: Any = None,
) -> tuple[ActionExecutionCoordinator, ActionRequest, Gateway, InMemoryActionStore]:
    store = InMemoryActionStore()
    coordinator = ActionExecutionCoordinator(gateway, store, InMemoryResourceLocker())
    action = ActionRequest.create(
        idempotency_key=key,
        household_id=HOUSEHOLD,
        tool=tool(),
        arguments={"resource_id": str(RESOURCE), "desired_on": True},
        identity=IdentityContext(HOUSEHOLD, None, Assurance.AUTHENTICATED),
        policy_service=PolicyService(evaluator or AllowEvaluator()),
        refresher=refresher
        or (
            lambda resources: TruthSnapshot(
                {"power": {"state": "KNOWN", "value": "off", "version": "1"}}
            )
        ),
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


def test_ambiguous_connector_timeout_is_unknown_and_not_retried() -> None:
    gateway = Gateway(InvocationOutcome.PLUGIN_TIMEOUT)
    coordinator, action, gateway, store = request(gateway)
    result = coordinator.execute(action)
    assert result.record.status == ActionStatus.UNKNOWN_RESULT
    assert gateway.calls == 1
    assert store.get(action.action_id) == result.record


def test_partial_effects_are_durable_without_compensation() -> None:
    gateway = Gateway(
        result={
            "effects": [
                {"outcome": "SUCCEEDED", "observed": {"state": "on"}},
                {"outcome": "UNKNOWN", "detail": "timeout after dispatch"},
            ]
        }
    )
    coordinator, action, _, store = request(gateway)
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


def test_restart_recovery_marks_planned_and_executing_without_retry() -> None:
    gateway = Gateway()
    coordinator, action, _, store = request(gateway)
    claimed = store.claim(action)
    store.update(claimed.record.action_id, ActionStatus.EXECUTING)
    recovered = store.recover_incomplete()
    assert recovered[0].status == ActionStatus.UNKNOWN_RESULT
    assert coordinator.execute(action).duplicate is True
    assert gateway.calls == 0
