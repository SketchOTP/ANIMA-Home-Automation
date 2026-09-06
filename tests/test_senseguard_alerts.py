from datetime import UTC, datetime, time
from uuid import UUID, uuid4

import pytest

from anima_ha.plugins import InvocationContext
from anima_ha.policy import RequestOrigin
from anima_ha.senseguard_alerts import (
    SENSEGUARD_ALERT_MANIFEST,
    SenseGuardAlertNativePlugin,
    SenseGuardAlertPolicy,
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
