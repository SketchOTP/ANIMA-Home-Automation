from __future__ import annotations

from uuid import UUID, uuid4

import pytest

from anima_ha.notification_routes import (
    NOTIFICATION_ROUTE_MANIFEST,
    NotificationRoute,
    NotificationRouteError,
    NotificationRouteNativePlugin,
)
from anima_ha.plugins import InvocationContext
from anima_ha.policy import RequestOrigin


def _context(household_id: UUID, principal_id: UUID) -> InvocationContext:
    return InvocationContext(
        household_id=household_id,
        principal_id=principal_id,
        episode_id=None,
        tool_request_id=uuid4(),
        ordinal=1,
        system_idempotency_key="test-notification-route",
        origin=RequestOrigin.DIRECT_USER,
    )


def test_notification_route_plugin_owns_destination_and_creator() -> None:
    household_id = uuid4()
    principal_id = uuid4()

    class Store:
        def __init__(self) -> None:
            self.routes: dict[UUID, NotificationRoute] = {}

        def get(self, household: UUID, route_id: UUID) -> NotificationRoute | None:
            route = self.routes.get(route_id)
            return route if route and route.household_id == household else None

        def save(
            self, route: NotificationRoute, *, expected_version: int | None = None
        ) -> NotificationRoute:
            if expected_version is not None:
                assert self.routes[route.route_id].version == expected_version
            self.routes[route.route_id] = route
            return route

        def list_all(self, household: UUID) -> list[NotificationRoute]:
            return [route for route in self.routes.values() if route.household_id == household]

    store = Store()
    plugin = NotificationRouteNativePlugin(store)  # type: ignore[arg-type]
    context = _context(household_id, principal_id)
    result = plugin.invoke_with_invocation_context(
        "save_route",
        {"label": "Overnight alerts", "minimum_priority": 80},
        1.0,
        context,
    )

    payload = result["route"]
    assert payload["household_id"] == str(household_id)
    assert payload["creator_principal_id"] == str(principal_id)
    assert payload["provider"] == "ntfy"
    assert payload["destination"] == "server_configured"
    assert "topic" not in payload
    assert "token" not in payload
    assert NOTIFICATION_ROUTE_MANIFEST.plugin_id == "anima.notification-routes"


def test_notification_route_update_requires_version_and_rejects_arbitrary_destination() -> None:
    route = NotificationRoute(route_id=uuid4(), household_id=uuid4())
    with pytest.raises(NotificationRouteError, match="unsupported notification destination"):
        NotificationRoute(
            route_id=route.route_id,
            household_id=route.household_id,
            destination_ref="https://example.invalid/topic",
        )

    class EmptyStore:
        def get(self, household: UUID, route_id: UUID) -> NotificationRoute | None:
            del household, route_id
            return route

    plugin = NotificationRouteNativePlugin(EmptyStore())  # type: ignore[arg-type]
    with pytest.raises(NotificationRouteError, match="VERSION_REQUIRED"):
        plugin.invoke_with_invocation_context(
            "save_route",
            {"route_id": str(route.route_id), "label": "Changed"},
            1.0,
            _context(route.household_id, uuid4()),
        )
