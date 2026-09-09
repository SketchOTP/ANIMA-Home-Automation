from datetime import UTC, datetime, time
from types import SimpleNamespace
from uuid import UUID, uuid4

import pytest

from anima_ha.events import DeliveryClass, EventEnvelope, EventImportance
from anima_ha.plugins import InvocationContext, NativeRuntime, PluginManager
from anima_ha.policy import RequestOrigin
from anima_ha.senseguard_alerts import (
    SENSEGUARD_ALERT_MANIFEST,
    SenseGuardAlertNativePlugin,
    SenseGuardAlertPolicy,
    SenseGuardEventRouter,
    SenseGuardPolicyError,
    new_senseguard_policy,
)


def test_overnight_senseguard_policy_uses_household_local_time() -> None:
    household_id = uuid4()
    kitchen = uuid4()
    basement = uuid4()
    policy = new_senseguard_policy(
        household_id,
        (kitchen, basement),
        start_local="00:00",
        end_local="05:00",
    )
    assert policy.matches(
        resource_id=basement,
        event_type="senseguard.event",
        occurred_at=datetime(2026, 9, 4, 4, 3, tzinfo=UTC),
    )
    assert not policy.matches(
        resource_id=basement,
        event_type="senseguard.event",
        occurred_at=datetime(2026, 9, 4, 10, 3, tzinfo=UTC),
    )
    assert not policy.matches(
        resource_id=uuid4(),
        event_type="senseguard.event",
        occurred_at=datetime(2026, 9, 4, 4, 3, tzinfo=UTC),
    )
    metadata = policy.attention_metadata(
        event_id="ha-event-1",
        resource_id=basement,
        occurred_at=datetime(2026, 9, 4, 4, 3, tzinfo=UTC),
    )
    assert metadata["guaranteed_attention"] is True
    assert metadata["provenance"] == "anima.senseguard.alert_policy"


def test_senseguard_policy_rejects_unbounded_or_invalid_configuration() -> None:
    with pytest.raises(SenseGuardPolicyError):
        new_senseguard_policy(uuid4(), (), start_local=time(0), end_local=time(1))
    with pytest.raises(SenseGuardPolicyError):
        new_senseguard_policy(uuid4(), (uuid4(),), timezone="Not/AZone")


def test_notification_policy_dispatches_notification_instead_of_sentry_attention() -> None:
    household_id = uuid4()
    resource_id = uuid4()
    policy = SenseGuardAlertPolicy(
        policy_id=uuid4(),
        household_id=household_id,
        resource_ids=(resource_id,),
        event_type="senseguard.event",
        timezone="America/New_York",
        start_local=time(0),
        end_local=time(5),
        delivery_mode="NOTIFICATION",
    )
    event = EventEnvelope.create(
        event_id="ha-senseguard-1",
        event_type="truth.observation",
        source="home-assistant",
        subject_key="binary_sensor.basement_guard",
        occurred_at=datetime(2026, 9, 6, 5, 3, tzinfo=UTC),
        payload={"state": "on"},
        importance=EventImportance.IMPORTANT,
        delivery_class=DeliveryClass.BEST_EFFORT,
        metadata={
            "external_id": "binary_sensor.basement_guard",
            "senseguard_event_type": "senseguard.event",
            "household_id": str(household_id),
        },
    )
    attention_calls: list[None] = []
    notification_calls: list[tuple[object, object]] = []

    class Store:
        def list_enabled(self, household: UUID) -> list[SenseGuardAlertPolicy]:
            return [policy] if household == household_id else []

    class Sink:
        def append(self, alert: object) -> object:
            del alert
            return SimpleNamespace(deduplicated=False)

    router = SenseGuardEventRouter(
        household_id=household_id,
        policy_store=Store(),  # type: ignore[arg-type]
        resource_resolver=lambda value: (
            resource_id if value == event.metadata["external_id"] else None
        ),
        event_sink=Sink(),
        dispatch_attention=lambda: attention_calls.append(None),
        dispatch_notification=lambda alert, matched: notification_calls.append((alert, matched)),
    )

    alerts = router.handle(event)

    assert len(alerts) == 1
    assert attention_calls == []
    assert notification_calls == [(alerts[0], policy)]


def test_typed_alert_plugin_owns_household_and_creator_provenance() -> None:
    household_id = uuid4()
    resource_id = uuid4()
    principal_id = uuid4()

    class Store:
        def __init__(self) -> None:
            self.saved: SenseGuardAlertPolicy | None = None

        def get(self, household: UUID, policy_id: UUID) -> SenseGuardAlertPolicy | None:
            del household, policy_id
            return self.saved

        def save(
            self, policy: SenseGuardAlertPolicy, *, expected_version: int | None = None
        ) -> SenseGuardAlertPolicy:
            assert expected_version is None
            self.saved = policy
            return policy

        def list_all(self, household: UUID) -> list[SenseGuardAlertPolicy]:
            return [self.saved] if self.saved and self.saved.household_id == household else []

    store = Store()
    plugin = SenseGuardAlertNativePlugin(store)  # type: ignore[arg-type]
    context = InvocationContext(
        household_id=household_id,
        principal_id=principal_id,
        episode_id=None,
        tool_request_id=uuid4(),
        ordinal=1,
        system_idempotency_key="test-alert-policy",
        origin=RequestOrigin.DIRECT_USER,
    )
    result = plugin.invoke_with_invocation_context(
        "save_policy",
        {
            "resource_ids": [str(resource_id)],
            "event_type": "senseguard.event",
            "timezone": "America/New_York",
            "start_local": "00:00",
            "end_local": "05:00",
        },
        1.0,
        context,
    )
    assert result["policy"]["household_id"] == str(household_id)
    assert result["policy"]["creator_principal_id"] == str(principal_id)
    assert SENSEGUARD_ALERT_MANIFEST.plugin_id == "anima.senseguard-alerts"


def test_typed_alert_plugin_rejects_resource_outside_commissioned_household() -> None:
    household_id = uuid4()
    principal_id = uuid4()
    permitted = uuid4()
    rejected = uuid4()

    class Store:
        def get(self, household: UUID, policy_id: UUID) -> SenseGuardAlertPolicy | None:
            del household, policy_id
            return None

        def save(
            self, policy: SenseGuardAlertPolicy, *, expected_version: int | None = None
        ) -> SenseGuardAlertPolicy:
            del expected_version
            return policy

    def resource_validator(household: UUID, resource: UUID) -> bool:
        return household == household_id and resource == permitted

    plugin = SenseGuardAlertNativePlugin(Store(), resource_validator=resource_validator)  # type: ignore[arg-type]
    context = InvocationContext(
        household_id=household_id,
        principal_id=principal_id,
        episode_id=None,
        tool_request_id=uuid4(),
        ordinal=1,
        system_idempotency_key="test-alert-resource-scope",
        origin=RequestOrigin.DIRECT_USER,
    )
    with pytest.raises(SenseGuardPolicyError, match="SENSEGUARD_RESOURCE_NOT_COMMISSIONED"):
        plugin.invoke_with_invocation_context(
            "save_policy",
            {
                "resource_ids": [str(permitted), str(rejected)],
                "event_type": "senseguard.event",
                "timezone": "America/New_York",
                "start_local": "00:00",
                "end_local": "05:00",
            },
            1.0,
            context,
        )


def test_spoken_presence_policy_is_fixed_to_presence_detection_and_sentry() -> None:
    household_id = uuid4()
    resource_id = uuid4()
    principal_id = uuid4()

    class Store:
        def __init__(self) -> None:
            self.saved: SenseGuardAlertPolicy | None = None

        def get(self, household: UUID, policy_id: UUID) -> SenseGuardAlertPolicy | None:
            del household, policy_id
            return self.saved

        def save(
            self, policy: SenseGuardAlertPolicy, *, expected_version: int | None = None
        ) -> SenseGuardAlertPolicy:
            del expected_version
            self.saved = policy
            return policy

    store = Store()
    plugin = SenseGuardAlertNativePlugin(store)  # type: ignore[arg-type]
    context = InvocationContext(
        household_id,
        principal_id,
        None,
        uuid4(),
        1,
        "spoken-presence-policy",
        RequestOrigin.DIRECT_USER,
    )
    result = plugin.invoke_with_invocation_context(
        "save_spoken_presence_policy",
        {
            "resource_id": str(resource_id),
            "timezone": "America/New_York",
            "start_local": "00:00",
            "end_local": "02:00",
        },
        1.0,
        context,
    )
    policy = store.saved
    assert policy is not None
    assert result["policy"]["event_type"] == "presence.detected"
    assert policy.delivery_mode == "SENTRY_COGNITION"
    assert policy.guaranteed_attention is True
    assert policy.start_local == time(0)
    assert policy.end_local == time(2)

    manager = PluginManager()
    manager.register(SENSEGUARD_ALERT_MANIFEST, NativeRuntime(plugin))
    manager.enable(SENSEGUARD_ALERT_MANIFEST.plugin_id)
    descriptor = next(
        tool
        for tool in manager.list_tools()
        if tool.tool_id == "anima.senseguard-alerts.save_spoken_presence_policy"
    )
    assert descriptor.execution_boundary is not None
    assert descriptor.execution_boundary.value == "POLICY_GATED_INTERNAL"


def test_presence_detection_routes_only_live_direct_on_transition_to_spoken_sentry() -> None:
    household_id = uuid4()
    resource_id = uuid4()
    occurred_at = datetime(2026, 9, 7, 5, 30, tzinfo=UTC)
    external_id = "binary_sensor.hall_presence"
    policy = SenseGuardAlertPolicy(
        uuid4(),
        household_id,
        (resource_id,),
        "presence.detected",
        "America/New_York",
        time(0),
        time(2),
    )

    class PolicyStore:
        def list_enabled(self, household: UUID) -> list[SenseGuardAlertPolicy]:
            return [policy] if household == household_id else []

    class Sink:
        def append(self, alert: object) -> object:
            del alert
            return SimpleNamespace(deduplicated=False)

    def make_event(value: str, *, snapshot: bool = False) -> EventEnvelope:
        stamp = occurred_at.isoformat()
        metadata = {
            "external_id": external_id,
            "last_changed": stamp,
            "last_updated": stamp,
            "snapshot": snapshot,
            "attributes": {"device_class": "presence"},
        }
        return EventEnvelope.create(
            event_id=str(uuid4()),
            event_type="truth.observation",
            source="provider:home_assistant:test",
            subject_key=external_id,
            occurred_at=occurred_at,
            payload={
                "state": "KNOWN",
                "value": value,
                "evidence_kind": "DIRECT",
                "metadata": metadata,
            },
            importance=EventImportance.IMPORTANT,
            delivery_class=DeliveryClass.BEST_EFFORT,
            metadata={
                "provider": "home_assistant",
                "external_id": external_id,
                "snapshot": snapshot,
            },
        )

    router = SenseGuardEventRouter(
        household_id=household_id,
        policy_store=PolicyStore(),  # type: ignore[arg-type]
        resource_resolver=lambda value: resource_id if value == external_id else None,
        event_sink=Sink(),
    )
    alerts = router.handle(make_event("on"))
    assert len(alerts) == 1
    assert alerts[0].payload["spoken_notice"] is True
    assert router.handle(make_event("off")) == []
    assert router.handle(make_event("on", snapshot=True)) == []
