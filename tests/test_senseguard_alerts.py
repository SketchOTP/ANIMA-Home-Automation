from datetime import UTC, datetime, time
from uuid import uuid4

import pytest

from anima_ha.senseguard_alerts import (
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
