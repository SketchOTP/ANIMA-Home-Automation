from __future__ import annotations

from datetime import UTC, datetime
from types import SimpleNamespace
from typing import Any, cast
from uuid import UUID, uuid4

import pytest

from anima_ha.action import ActionStatus
from anima_ha.automations import (
    AUTOMATIONS_MANIFEST,
    Automation,
    AutomationConflict,
    AutomationError,
    AutomationNativePlugin,
    InMemoryAutomationStore,
)
from anima_ha.events import EventEnvelope
from anima_ha.plugins import InvocationContext
from anima_ha.policy import RequestOrigin


def _context(household_id: UUID) -> InvocationContext:
    return InvocationContext(
        household_id=household_id,
        principal_id=uuid4(),
        episode_id=None,
        tool_request_id=uuid4(),
        ordinal=1,
        system_idempotency_key="automation-test",
        origin=RequestOrigin.DIRECT_USER,
    )


def test_automation_plugin_is_typed_household_scoped_and_versioned() -> None:
    household_id = uuid4()
    trigger_id, action_id = uuid4(), uuid4()
    store = InMemoryAutomationStore()
    plugin = AutomationNativePlugin(
        store,
        lambda household, resource: (
            household == household_id and resource in {trigger_id, action_id}
        ),
    )
    context = _context(household_id)
    created = plugin.invoke_with_invocation_context(
        "create_automation",
        {
            "name": "Porch light",
            "trigger_resource_id": str(trigger_id),
            "trigger_state": "on",
            "action_resource_id": str(action_id),
            "action_desired_on": True,
        },
        1.0,
        context,
    )
    automation = created["automation"]
    assert automation["version"] == 1
    assert AUTOMATIONS_MANIFEST.plugin_id == "anima.automations"
    assert plugin.invoke_with_invocation_context("list_automations", {}, 1.0, context)[
        "automations"
    ] == [automation]

    updated = plugin.invoke_with_invocation_context(
        "update_automation",
        {
            **automation,
            "expected_version": 1,
            "trigger_state": "off",
            "action_desired_on": False,
        },
        1.0,
        context,
    )
    assert updated["automation"]["version"] == 2
    assert updated["automation"]["trigger_state"] == "off"
    with pytest.raises(AutomationConflict):
        plugin.invoke_with_invocation_context(
            "update_automation",
            {**updated["automation"], "expected_version": 1},
            1.0,
            context,
        )


def test_automation_rejects_uncommissioned_resources_and_invalid_states() -> None:
    household_id = uuid4()
    plugin = AutomationNativePlugin(InMemoryAutomationStore(), lambda household, resource: False)
    with pytest.raises(AutomationError, match="AUTOMATION_TRIGGER_NOT_COMMISSIONED"):
        plugin.invoke_with_invocation_context(
            "create_automation",
            {
                "name": "Unsafe",
                "trigger_resource_id": str(uuid4()),
                "trigger_state": "sideways",
                "action_resource_id": str(uuid4()),
                "action_desired_on": True,
            },
            1.0,
            _context(household_id),
        )


def test_automation_payload_is_json_stable() -> None:
    household_id = uuid4()
    plugin = AutomationNativePlugin(InMemoryAutomationStore(), lambda _h, _r: True)
    value = plugin.invoke_with_invocation_context(
        "create_automation",
        {
            "name": "Stable",
            "trigger_resource_id": str(uuid4()),
            "trigger_state": "on",
            "action_resource_id": str(uuid4()),
            "action_desired_on": False,
        },
        1.0,
        _context(household_id),
    )["automation"]
    assert datetime.fromisoformat(value["updated_at"]).tzinfo == UTC


def test_matching_observation_builds_one_autonomous_verified_action_request() -> None:
    household_id = uuid4()
    trigger_id, action_id = uuid4(), uuid4()
    automation = Automation.create(
        household_id=household_id,
        name="Turn on the lamp",
        trigger_resource_id=trigger_id,
        trigger_state="on",
        action_resource_id=action_id,
        action_desired_on=True,
        creator_principal_id=uuid4(),
    )

    class Store(InMemoryAutomationStore):
        def __init__(self) -> None:
            super().__init__()
            self.create(automation)

    class Executor:
        def __init__(self) -> None:
            self.requests: list[Any] = []

        def execute(self, request: Any) -> Any:
            self.requests.append(request)
            return SimpleNamespace(
                record=SimpleNamespace(action_id=uuid4(), status=ActionStatus.SUCCEEDED),
            )

    from anima_ha.automations import AutomationEventRouter

    tool = SimpleNamespace(
        tool_id="anima.provider.home-assistant.set_power",
        plugin_id="anima.provider.home-assistant",
        name="set_power",
        version="1",
        availability=True,
        read_only=False,
        risk_class="LOW_RISK_HOME_CONTROL",
        semantic_action="set_power",
        execution_spec={"profile": "home_assistant.set_power"},
    )
    executor = Executor()
    journal = SimpleNamespace(append=lambda event: event)
    router = AutomationEventRouter(
        household_id=household_id,
        store=Store(),
        resource_resolver=lambda external_id: (
            trigger_id if external_id == "sensor.trigger" else None
        ),
        manager=SimpleNamespace(list_tools=lambda: [tool]),
        action_executor=cast(Any, executor),
        policy_service=cast(Any, SimpleNamespace()),
        action_refresher=None,
        action_verifier=None,
        role_resolver=lambda principal_id: "owner" if principal_id else None,
        journal=journal,
    )
    event = EventEnvelope.create(
        event_id=str(uuid4()),
        event_type="truth.observation",
        source="provider:home_assistant",
        subject_key="entity/sensor.trigger",
        occurred_at=datetime.now(UTC),
        payload={"value": "on"},
        metadata={"external_id": "sensor.trigger"},
    )
    result = router.handle(event)
    assert result[0]["status"] == "SUCCEEDED"
    request = cast(Any, executor.requests[0])
    assert request.origin is RequestOrigin.AUTONOMOUS_AGENT
    assert request.arguments == {"resource_id": str(action_id), "desired_on": True}
    assert request.idempotency_key == f"automation:{automation.automation_id}:{event.event_id}"
