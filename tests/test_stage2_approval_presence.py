from __future__ import annotations

import json
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace
from typing import Any, cast
from uuid import UUID, uuid4

import pytest
from test_action import AllowEvaluator, ConfirmationEvaluator, DenyEvaluator, Gateway, tool
from test_ui_runtime import _ui_control_identity

from anima_ha.action import (
    ActionExecutionCoordinator,
    ActionRequest,
    InMemoryActionStore,
    InMemoryPendingApprovalStore,
    InMemoryResourceLocker,
    TruthSnapshot,
)
from anima_ha.policy import Assurance, IdentityContext, PolicyService
from anima_ha.ui_api import UICommandError
from anima_ha.ui_runtime import CoreUICommandGateway
from anima_ha.wifi_presence import (
    WifiNeighbor,
    WifiPerson,
    WifiPresenceMonitor,
    _read_previous,
    presence_transition_event,
    project_wifi_presence,
)


@pytest.mark.parametrize("choice", ["APPROVE", "REJECT", "DENY_CURRENT"])
def test_episode_less_gateway_uses_current_authority_not_agent_fallback(choice: str) -> None:
    identity = _ui_control_identity()
    native = Gateway()
    pending = InMemoryPendingApprovalStore()
    coordinator = ActionExecutionCoordinator(
        native, InMemoryActionStore(), InMemoryResourceLocker(), pending_approvals=pending
    )
    descriptor = tool()
    action = ActionRequest.create(
        idempotency_key=str(uuid4()),
        household_id=identity.household_id,
        tool=descriptor,
        arguments={"resource_id": str(uuid4()), "desired_on": True},
        identity=IdentityContext(
            identity.household_id, identity.principal_id, Assurance.AUTHENTICATED
        ),
        policy_service=PolicyService(ConfirmationEvaluator()),
        refresher=lambda resources: TruthSnapshot({"power": {"state": "KNOWN", "value": "off"}}),
    )
    first = coordinator.execute(action)
    assert first.record.result is not None
    identifier = str(first.record.result["approval_id"])
    approval = pending.get(UUID(identifier))
    assert approval is not None and approval.episode_id is None

    def forbidden_agent_resume(*args: Any, **kwargs: Any) -> None:
        raise AssertionError("episode-less approval must not use agent resume")

    ui = CoreUICommandGateway(
        cast(Any, SimpleNamespace(list_tools=lambda: [descriptor])),
        PolicyService(DenyEvaluator() if choice == "DENY_CURRENT" else AllowEvaluator()),
        action_executor=coordinator,
        action_refresher=lambda resources: TruthSnapshot(
            {"power": {"state": "KNOWN", "value": "off"}}
        ),
        agent=cast(Any, SimpleNamespace(resume_confirmation=forbidden_agent_resume)),
    )
    with pytest.raises(UICommandError, match="APPROVAL_NOT_FOUND"):
        ui.confirmation(replace(identity, principal_id=uuid4()), identifier, "APPROVE")
    with pytest.raises(UICommandError, match="APPROVAL_NOT_FOUND"):
        ui.confirmation(replace(identity, household_id=uuid4()), identifier, "APPROVE")
    if choice == "REJECT":
        ui.manager = cast(
            Any, SimpleNamespace(list_tools=lambda: [])
        )  # Retired tool still rejectable.
    result = ui.confirmation(
        identity, identifier, "APPROVE" if choice == "DENY_CURRENT" else choice
    )
    assert result["status"] == (
        "REJECTED"
        if choice == "REJECT"
        else "POLICY_DENIED"
        if choice == "DENY_CURRENT"
        else "VERIFICATION_FAILED"
    )
    assert native.calls == (1 if choice == "APPROVE" else 0)
    with pytest.raises(UICommandError, match="APPROVAL_NOT_ACTIONABLE|CORE_TOOL_UNAVAILABLE"):
        ui.confirmation(identity, identifier, choice if choice == "REJECT" else "APPROVE")
    resumed_action = coordinator.store.get(approval.action_id)
    assert resumed_action is not None  # Same action, not a stronger-auth continuation.


def test_stale_restart_never_invents_arrival_and_same_state_timestamp_is_stable(
    tmp_path: Path,
) -> None:
    now = datetime.now(UTC)
    person = WifiPerson(str(uuid4()), str(uuid4()), ("aa:bb:cc:dd:ee:ff",))
    prior = {
        person.person_id: {
            "active": False,
            "status": "UNKNOWN",
            "last_status_changed_at": (now - timedelta(hours=1)).isoformat(),
            "absence_sweeps": 2,
        }
    }
    path = tmp_path / "status.json"
    path.write_text(
        json.dumps(
            {
                "state": "READY",
                "observed_at": (now - timedelta(seconds=121)).isoformat(),
                "households": {person.household_id: {"people": prior}},
            }
        )
    )
    path.chmod(0o600)
    baseline = _read_previous(path, now=now)
    assert baseline[person.person_id]["active"] is None
    current = project_wifi_presence(
        [person],
        [WifiNeighbor("192.0.2.1", person.macs[0], "REACHABLE")],
        now=now,
        previous=baseline,
    )
    assert (
        presence_transition_event(
            person, baseline.get(person.person_id, {}), current[person.person_id], now=now
        )
        is None
    )
    historical_changed = prior[person.person_id]["last_status_changed_at"]
    assert current[person.person_id]["last_status_changed_at"] == historical_changed
    steady = project_wifi_presence(
        [person],
        [WifiNeighbor("192.0.2.1", person.macs[0], "REACHABLE")],
        now=now + timedelta(seconds=30),
        previous=current,
    )
    assert steady[person.person_id]["last_status_changed_at"] == historical_changed
    monitor = WifiPresenceMonitor(
        "isolated-not-connected", status_path=path, runner=lambda argv, timeout: (1, "")
    )
    with pytest.raises(ValueError, match="NEIGHBOR_COVERAGE_UNAVAILABLE"):
        monitor._neighbors("isolated-interface")
    fault = monitor._write({}, state="NOT_READY", reason="NEIGHBOR_COVERAGE_UNAVAILABLE")
    lost = fault["households"][person.household_id]["people"][person.person_id]
    assert lost["active"] is None and lost["status"] == "UNKNOWN"
    assert lost["last_status_changed_at"] == historical_changed
    restarted = _read_previous(path, now=now)
    recovered = project_wifi_presence(
        [person],
        [WifiNeighbor("192.0.2.1", person.macs[0], "REACHABLE")],
        now=now,
        previous=restarted,
    )
    assert recovered[person.person_id]["last_status_changed_at"] == historical_changed
    assert (
        presence_transition_event(
            person, restarted[person.person_id], recovered[person.person_id], now=now
        )
        is None
    )
    missed = project_wifi_presence(
        [person], [], now=now + timedelta(seconds=30), previous=recovered
    )
    changed = project_wifi_presence([person], [], now=now + timedelta(seconds=60), previous=missed)
    assert (
        changed[person.person_id]["last_status_changed_at"]
        == (now + timedelta(seconds=60)).isoformat()
    )
    assert (
        presence_transition_event(
            person, missed[person.person_id], changed[person.person_id], now=now
        )
        is not None
    )
