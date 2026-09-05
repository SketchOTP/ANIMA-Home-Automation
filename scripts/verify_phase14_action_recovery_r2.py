"""Exercise real action-store recovery and terminal verification semantics."""

from __future__ import annotations

import json
import os
import sys
from typing import Any
from uuid import UUID, uuid4

from anima_ha.action import (
    ActionExecutionCoordinator,
    ActionRequest,
    ActionStatus,
    PostgresActionStore,
    PostgresResourceLocker,
    TruthSnapshot,
)
from anima_ha.plugins import (
    DispatchState,
    ExternalContentTrust,
    InvocationOutcome,
    InvocationResult,
)
from anima_ha.policy import (
    Assurance,
    IdentityContext,
    OpaPolicyClient,
    PolicyContext,
    PolicyService,
    RequestOrigin,
)

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from scripts.verify_phase12_h5u_confirmation import tool  # noqa: E402

DATABASE_URL = os.environ.get("ANIMA_DATABASE_URL", "")
OPA_URL = os.environ.get("ANIMA_OPA_URL", "http://127.0.0.1:18181")
HOUSEHOLD_ID = UUID("ecbd0d84-6f5f-40f8-928f-1d5dfe758dd7")


class Gateway:
    def __init__(self, response: InvocationResult) -> None:
        self.response = response
        self.calls = 0

    def invoke(self, tool_id: str, arguments: dict[str, Any], **kwargs: Any) -> InvocationResult:
        del arguments, kwargs
        self.calls += 1
        return self.response


def request(
    key: str, *, gateway: Gateway, refresher: Any
) -> tuple[ActionExecutionCoordinator, ActionRequest]:
    identity = IdentityContext(HOUSEHOLD_ID, uuid4(), Assurance.RECOGNIZED)
    policy = PolicyService(OpaPolicyClient(OPA_URL))
    coordinator = ActionExecutionCoordinator(
        gateway,
        PostgresActionStore(DATABASE_URL),
        PostgresResourceLocker(DATABASE_URL),
    )
    action = ActionRequest.create(
        action_id=uuid4(),
        action_intent_id=uuid4(),
        idempotency_key=f"phase14-r2-action-{key}-{uuid4()}",
        household_id=HOUSEHOLD_ID,
        tool=tool(),
        arguments={"resource_id": str(uuid4()), "desired_on": True},
        identity=identity,
        policy_service=policy,
        policy_context=PolicyContext(principal_role="resident"),
        refresher=refresher,
        origin=RequestOrigin.DIRECT_USER,
    )
    return coordinator, action


def success_result() -> InvocationResult:
    return InvocationResult(
        InvocationOutcome.SUCCESS,
        "anima.test.set_power",
        "anima.test",
        "1.0.0",
        1.0,
        result={"acknowledged": True},
        external_content_trust=ExternalContentTrust.PLUGIN_TRUSTED,
    )


def main() -> int:
    if not DATABASE_URL:
        raise RuntimeError("ANIMA_DATABASE_URL is required")
    results: list[dict[str, Any]] = []

    pre_gateway = Gateway(success_result())
    pre_coordinator, pre_request = request(
        "prestart", gateway=pre_gateway, refresher=lambda resources: TruthSnapshot()
    )
    pre_coordinator.store.claim(pre_request)
    pre_coordinator.store.update(pre_request.action_id, ActionStatus.PLANNED)
    recovered = pre_coordinator.store.recover_incomplete()
    assert recovered and recovered[0].status == ActionStatus.RECOVERY_REQUIRED
    assert pre_gateway.calls == 0
    results.append({"scenario_id": "ACTION_PRE_DISPATCH_CRASH_RECLAIM", "status": "PASS"})

    started_gateway = Gateway(success_result())
    started_coordinator, started_request = request(
        "started", gateway=started_gateway, refresher=lambda resources: TruthSnapshot()
    )
    started_coordinator.store.claim(started_request)
    started_coordinator.store.update(started_request.action_id, ActionStatus.EXECUTING)
    recovered = started_coordinator.store.recover_incomplete()
    assert recovered and recovered[0].status == ActionStatus.UNKNOWN_RESULT
    assert started_gateway.calls == 0
    results.append({"scenario_id": "ACTION_STARTED_CRASH_NO_REPLAY", "status": "PASS"})

    mismatch_gateway = Gateway(success_result())
    mismatch_coordinator, mismatch_request = request(
        "mismatch",
        gateway=mismatch_gateway,
        refresher=lambda resources: TruthSnapshot(
            {"power": {"state": "KNOWN", "value": "off", "version": "1"}}
        ),
    )
    mismatch = mismatch_coordinator.execute(mismatch_request)
    assert mismatch.record.status == ActionStatus.VERIFICATION_FAILED
    assert mismatch_gateway.calls == 1
    results.append(
        {
            "scenario_id": "ACTION_ACK_BEFORE_VERIFICATION_FAILURE",
            "status": "PASS",
            "terminal_status": mismatch.record.status.value,
        }
    )

    ambiguous_gateway = Gateway(
        InvocationResult(
            InvocationOutcome.PLUGIN_ERROR,
            "anima.test.set_power",
            "anima.test",
            "1.0.0",
            1.0,
            error_class="SyntheticProviderFailure",
            dispatch_state=DispatchState.POSSIBLY_DISPATCHED,
        )
    )
    ambiguous_coordinator, ambiguous_request = request(
        "ambiguous", gateway=ambiguous_gateway, refresher=lambda resources: TruthSnapshot()
    )
    ambiguous = ambiguous_coordinator.execute(ambiguous_request)
    assert ambiguous.record.status == ActionStatus.UNKNOWN_RESULT
    assert ambiguous_gateway.calls == 1
    results.append(
        {
            "scenario_id": "ACTION_POSSIBLE_DISPATCH_UNKNOWN_NO_RETRY",
            "status": "PASS",
            "terminal_status": ambiguous.record.status.value,
        }
    )

    turns = {"refreshes": 0}

    def fresh_state(resources: Any) -> TruthSnapshot:
        del resources
        turns["refreshes"] += 1
        value = "off" if turns["refreshes"] == 1 else "on"
        return TruthSnapshot({"power": {"state": "KNOWN", "value": value, "version": "1"}})

    durable_gateway = Gateway(success_result())
    durable_coordinator, durable_request = request(
        "durable", gateway=durable_gateway, refresher=fresh_state
    )
    first = durable_coordinator.execute(durable_request)
    second = durable_coordinator.execute(durable_request)
    assert first.record.status == ActionStatus.SUCCEEDED
    assert second.duplicate is True and second.record.status == ActionStatus.SUCCEEDED
    assert durable_gateway.calls == 1
    results.append(
        {
            "scenario_id": "ACTION_RESULT_DURABLE_NO_RERUN",
            "status": "PASS",
            "provider_dispatches": durable_gateway.calls,
        }
    )

    print(json.dumps({"evidence_level": "POSTGRES_OPA_CORE", "results": results}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
