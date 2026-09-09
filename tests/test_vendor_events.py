from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest

from anima_ha.plugins import ContentPersistence, InvocationContext
from anima_ha.policy import RequestOrigin
from anima_ha.vendor_events import (
    VENDOR_EVENTS_MANIFEST,
    VendorEventReadError,
    VendorEventsNativePlugin,
)


class Store:
    def __init__(self) -> None:
        self.calls: list[tuple[UUID, int, int | None]] = []

    def list_recent(
        self, household_id: UUID, *, limit: int, before_position: int | None = None
    ) -> dict[str, object]:
        self.calls.append((household_id, limit, before_position))
        return {
            "schema_version": 1,
            "as_of": datetime.now(UTC).isoformat(),
            "items": [],
            "next_cursor": None,
            "external_content_trust": "EXTERNAL_UNTRUSTED",
            "identity_warning": "Reported lock identity is device-reported and unverified.",
        }


def context(household_id: UUID) -> InvocationContext:
    return InvocationContext(
        household_id=household_id,
        principal_id=uuid4(),
        episode_id=uuid4(),
        tool_request_id=uuid4(),
        ordinal=1,
        system_idempotency_key="vendor-event-read",
        origin=RequestOrigin.DIRECT_USER,
    )


def test_manifest_is_read_only_external_and_core_restricted() -> None:
    tool = VENDOR_EVENTS_MANIFEST.tools[0]
    assert tool["read_only"] is True
    assert tool["external_content_trust"] == "EXTERNAL_UNTRUSTED"
    from anima_ha.plugins import core_content_persistence

    assert (
        core_content_persistence("anima.vendor-events.list_recent_events")
        == ContentPersistence.EPHEMERAL_RESTRICTED
    )


def test_plugin_uses_only_server_owned_household_scope_and_bounded_cursor() -> None:
    store = Store()
    plugin = VendorEventsNativePlugin(store)  # type: ignore[arg-type]
    household = uuid4()
    result = plugin.invoke_with_invocation_context(
        "list_recent_events", {"limit": 7, "cursor": "123"}, 5, context(household)
    )
    assert result["items"] == []
    assert store.calls == [(household, 7, 123)]
    with pytest.raises(VendorEventReadError):
        plugin.invoke_with_invocation_context(
            "list_recent_events", {"cursor": "other-household/123"}, 5, context(household)
        )


def test_plugin_never_accepts_household_or_provider_arguments() -> None:
    plugin = VendorEventsNativePlugin(Store())  # type: ignore[arg-type]
    with pytest.raises(Exception, match="unsupported vendor-event read"):
        plugin.invoke_with_invocation_context(
            "list_recent_events", {"household_id": str(uuid4())}, 5, context(uuid4())
        )
