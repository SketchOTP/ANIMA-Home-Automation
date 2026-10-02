"""Actual PluginManager → coordinator → owner/SENTRY result regression."""

from dataclasses import replace
from typing import Any
from uuid import uuid4

import pytest
from test_action import DenyEvaluator, request, tool
from test_plugins import AllowEvaluator, EchoNative, manifest

from anima_ha.action import (
    ActionExecutionCoordinator,
    ActionRequest,
    ActionStatus,
    InMemoryActionStore,
    InMemoryResourceLocker,
)
from anima_ha.plugins import (
    DispatchState,
    ExecutionBoundary,
    InvocationOutcome,
    NativeRuntime,
    PluginManager,
    PluginValidationError,
)
from anima_ha.policy import Assurance, IdentityContext, PolicyService
from anima_ha.sentry_boundary import CoreSentryBoundary
from anima_ha.ui_runtime import _safe_result


class Runtime(EchoNative):
    def __init__(self, value: Any) -> None:
        super().__init__()
        self.value = value
        self.calls = 0

    def list_tools(self) -> list[dict[str, Any]]:
        return [{"name": "set_power", "input_schema": {"type": "object"}}]

    def invoke(
        self, name: str, arguments: dict[str, Any], timeout: float, execution_context: Any = None
    ) -> Any:
        self.calls += 1
        if isinstance(self.value, Exception):
            raise self.value
        return self.value


def manager_for(value: Any) -> tuple[PluginManager, Runtime]:
    runtime = Runtime(value)
    descriptor = tool()
    definition = {
        **descriptor.to_payload(),
        "output_schema": {"type": "object", "required": ["outcome"]},
    }
    manager = PluginManager()
    manager.register(
        replace(manifest(), plugin_id=descriptor.plugin_id, tools=(definition,)),
        NativeRuntime(runtime),
    )
    manager.enable(descriptor.plugin_id)
    return manager, runtime


@pytest.mark.parametrize(
    ("value", "outcome"),
    [
        ({"malformed": True}, InvocationOutcome.INVALID_RESULT),
        ("not an object", InvocationOutcome.INVALID_RESULT),
        (PluginValidationError("after entry"), InvocationOutcome.INVALID_RESULT),
        (TimeoutError("after entry"), InvocationOutcome.PLUGIN_TIMEOUT),
        ({"outcome": "VERIFICATION_FAILED"}, InvocationOutcome.VERIFICATION_FAILED),
    ],
)
def test_post_entry_errors_are_possibly_dispatched(value: Any, outcome: InvocationOutcome) -> None:
    manager, runtime = manager_for(value)
    identity = IdentityContext(uuid4(), None, Assurance.AUTHENTICATED)
    invocation = manager.invoke(
        tool().tool_id,
        {},
        household_id=identity.household_id,
        identity=identity,
        policy_service=PolicyService(AllowEvaluator()),
    )
    assert runtime.calls == 1
    assert invocation.outcome == outcome
    assert invocation.dispatch_state == DispatchState.POSSIBLY_DISPATCHED


@pytest.mark.parametrize(
    ("observed", "expected"),
    [
        ("on", ActionStatus.SUCCEEDED),
        ("off", ActionStatus.VERIFICATION_FAILED),
        (None, ActionStatus.UNKNOWN_RESULT),
    ],
)
def test_malformed_result_is_verified_and_never_redispatched(
    observed: Any, expected: ActionStatus
) -> None:
    from anima_ha.action import TruthSnapshot

    manager, runtime = manager_for({"malformed": True})
    snapshots = iter(
        [
            TruthSnapshot({"power": {"state": "KNOWN", "value": "off", "version": "1"}}),
            TruthSnapshot(
                {
                    "power": {
                        "state": "UNKNOWN" if observed is None else "KNOWN",
                        "value": observed,
                        "version": "2",
                    }
                }
            ),
        ]
    )
    coordinator, action, _, store = request(manager, refresher=lambda _: next(snapshots))  # type: ignore[arg-type]
    result = coordinator.execute(action)
    assert result.record.status == expected
    assert result.record.result is not None
    assert result.record.result["connector_outcome"] == "INVALID_RESULT"
    assert result.record.result["connector_dispatch_state"] == "POSSIBLY_DISPATCHED"
    assert coordinator.execute(action).duplicate
    restarted = ActionExecutionCoordinator(manager, store, InMemoryResourceLocker())
    store.recover_incomplete()
    assert restarted.execute(action).duplicate
    assert runtime.calls == 1


def test_invalid_output_is_not_success_in_public_transports() -> None:
    manager, runtime = manager_for({"malformed": True})
    assert manager.tools[tool().tool_id].read_only is False
    identity = IdentityContext(uuid4(), None, Assurance.AUTHENTICATED)
    result = manager.invoke(
        tool().tool_id,
        {},
        household_id=identity.household_id,
        identity=identity,
        policy_service=PolicyService(AllowEvaluator()),
    )
    for project in (_safe_result, CoreSentryBoundary._safe_invocation):
        payload = project(result)
        assert payload["status"] != "SUCCEEDED"
        assert payload["dispatch_state"] == "POSSIBLY_DISPATCHED"
        assert payload["connector_outcome"] == "INVALID_RESULT"
    assert runtime.calls == 1


def test_read_only_invalid_output_without_verification_is_unknown_and_not_replayed() -> None:
    runtime = EchoNative()
    definition = manifest()
    manager = PluginManager()
    manager.register(
        replace(
            definition,
            tools=(
                {
                    **definition.tools[0],
                    "output_schema": {"type": "object", "required": ["status"]},
                },
            ),
        ),
        NativeRuntime(runtime),
    )
    manager.enable(definition.plugin_id)
    descriptor = manager.list_tools()[0]
    assert descriptor.read_only is True
    assert descriptor.risk_class == "READ_ONLY"
    assert descriptor.execution_boundary == ExecutionBoundary.READ_ONLY
    assert descriptor.verification_requirement == "NONE"
    identity = IdentityContext(uuid4(), None, Assurance.AUTHENTICATED)
    action = ActionRequest.create(
        idempotency_key=str(uuid4()),
        household_id=identity.household_id,
        tool=descriptor,
        arguments={"value": "synthetic"},
        identity=identity,
        policy_service=PolicyService(AllowEvaluator()),
    )
    assert action.verifier is None
    store = InMemoryActionStore()
    coordinator = ActionExecutionCoordinator(manager, store, InMemoryResourceLocker())
    result = coordinator.execute(action)
    assert result.record.status == ActionStatus.UNKNOWN_RESULT
    assert result.record.result is not None
    assert result.record.result["connector_outcome"] == "INVALID_RESULT"
    assert result.record.result["connector_dispatch_state"] == "POSSIBLY_DISPATCHED"
    assert coordinator.execute(action).duplicate
    store.recover_incomplete()
    restarted = ActionExecutionCoordinator(manager, store, InMemoryResourceLocker())
    replay = restarted.execute(action)
    assert replay.duplicate
    assert replay.record.status == ActionStatus.UNKNOWN_RESULT
    assert len(runtime.execution_contexts) == 1


def test_invalid_input_and_policy_denial_are_before_dispatch() -> None:
    manager, runtime = manager_for({"outcome": "SUCCESS"})
    descriptor = manager.tools[tool().tool_id]
    manager.tools[descriptor.tool_id] = replace(
        descriptor, input_schema={"type": "object", "required": ["required_argument"]}
    )
    identity = IdentityContext(uuid4(), None, Assurance.AUTHENTICATED)
    invalid = manager.invoke(
        descriptor.tool_id,
        {},
        household_id=identity.household_id,
        identity=identity,
        policy_service=PolicyService(AllowEvaluator()),
    )
    denied = manager.invoke(
        descriptor.tool_id,
        {"required_argument": True},
        household_id=identity.household_id,
        identity=identity,
        policy_service=PolicyService(DenyEvaluator()),
    )
    assert invalid.outcome == InvocationOutcome.INVALID_ARGUMENTS
    assert denied.outcome == InvocationOutcome.POLICY_DENIED
    assert invalid.dispatch_state == denied.dispatch_state == DispatchState.BEFORE_DISPATCH
    assert runtime.calls == 0


def test_valid_acknowledgement_still_requires_action_verification() -> None:
    manager, runtime = manager_for({"outcome": "SUCCESS"})
    coordinator, action, _, _ = request(manager)  # type: ignore[arg-type]
    result = coordinator.execute(action)
    assert result.record.status == ActionStatus.SUCCEEDED
    assert result.record.result is not None
    assert result.record.result["connector_dispatch_state"] == "ACKNOWLEDGED"
    assert coordinator.execute(action).duplicate
    assert runtime.calls == 1
