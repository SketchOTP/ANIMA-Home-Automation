from __future__ import annotations

from datetime import UTC, datetime
from types import SimpleNamespace
from typing import Any
from uuid import UUID, uuid4

import httpx
import pytest

from anima_ha.action import (
    ActionExecutionCoordinator,
    ActionStatus,
    InMemoryActionStore,
    InMemoryResourceLocker,
)
from anima_ha.events import DeliveryClass, EventEnvelope, EventImportance
from anima_ha.external import external_plugin
from anima_ha.notification_routes import (
    NOTIFICATION_ROUTE_MANIFEST,
    NotificationRoute,
    NotificationRouteError,
    NotificationRouteNativePlugin,
    SenseGuardNotificationDispatcher,
)
from anima_ha.plugins import InvocationContext, NativeRuntime, PluginManager, SecretBroker
from anima_ha.policy import PolicyService, RequestOrigin


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


def test_senseguard_notification_dispatch_is_server_authored_and_idempotent() -> None:
    household_id = uuid4()
    resource_id = uuid4()
    route = NotificationRoute(uuid4(), household_id, minimum_priority=80)
    policy = SimpleNamespace(policy_id=uuid4(), priority=90)
    alert = EventEnvelope.create(
        event_id="senseguard-event-1",
        event_type="senseguard.event",
        source="anima.senseguard-policy",
        subject_key=f"senseguard/{resource_id}",
        occurred_at=datetime(2026, 9, 6, 1, 3, tzinfo=UTC),
        payload={
            "canonical_resource_id": str(resource_id),
            "occurred_at": "2026-09-06T01:03:00-04:00",
        },
        importance=EventImportance.CRITICAL,
        delivery_class=DeliveryClass.GUARANTEED,
        metadata={"household_id": str(household_id)},
    )

    class Routes:
        def list_all(self, household: UUID) -> list[NotificationRoute]:
            return [route] if household == household_id else []

    tool = SimpleNamespace(
        tool_id="anima.external.notifications.send",
        version="0.1.0",
        read_only=False,
        availability=True,
        execution_spec={"profile": "notifications.send"},
        semantic_action="notifications.send",
        risk_class="EXTERNAL_SIDE_EFFECT",
    )
    requests: list[Any] = []

    class Manager:
        def list_tools(self) -> list[Any]:
            return [tool]

    class Actions:
        def execute(self, request: Any) -> Any:
            requests.append(request)
            return SimpleNamespace(
                record=SimpleNamespace(
                    action_id=request.action_id,
                    status=ActionStatus.SUCCEEDED,
                    detail="provider accepted",
                ),
                invocation=SimpleNamespace(outcome=SimpleNamespace(value="SUCCESS")),
            )

    journal: list[Any] = []
    dispatcher = SenseGuardNotificationDispatcher(
        route_store=Routes(),
        manager=Manager(),
        policy_service=object(),
        action_executor=Actions(),
        journal=journal,
        resource_name=lambda value: "SenseGuard Basement" if value == resource_id else None,
    )
    first = dispatcher.dispatch(alert, policy)
    second = dispatcher.dispatch(alert, policy)

    assert first[0]["status"] == "SUCCEEDED"
    assert second[0]["status"] == "SUCCEEDED"
    assert requests[0].idempotency_key == requests[1].idempotency_key
    assert requests[0].arguments["title"] == "ANIMA household alert"
    assert "SenseGuard Basement" in requests[0].arguments["message"]
    assert requests[0].policy_context.graph_metadata == {
        "notification_alert_authorized": True,
        "notification_route_id": str(route.route_id),
        "alert_policy_id": str(policy.policy_id),
    }
    assert len(journal) == 2


def test_senseguard_notification_dispatch_reports_missing_route_without_provider_call() -> None:
    household_id = uuid4()
    alert = SimpleNamespace(
        event_id="senseguard-event-no-route",
        correlation_id="corr",
        payload={"canonical_resource_id": str(uuid4())},
        metadata={"household_id": str(household_id)},
    )

    class Routes:
        def list_all(self, household: UUID) -> list[NotificationRoute]:
            del household
            return []

    class Manager:
        def list_tools(self) -> list[Any]:
            raise AssertionError("provider must not be consulted without a route")

    dispatcher = SenseGuardNotificationDispatcher(
        route_store=Routes(),
        manager=Manager(),
        policy_service=object(),
        action_executor=object(),
        journal=[],
        resource_name=lambda value: None,
    )
    assert dispatcher.dispatch(alert, SimpleNamespace(policy_id=uuid4(), priority=90)) == [
        {"status": "NO_ROUTE"}
    ]


def test_senseguard_notification_uses_real_action_and_ntfy_plugin_boundaries() -> None:
    household_id = uuid4()
    resource_id = uuid4()
    route = NotificationRoute(uuid4(), household_id)
    policy = SimpleNamespace(policy_id=uuid4(), priority=90)
    alert = EventEnvelope.create(
        event_id="senseguard-provider-1",
        event_type="senseguard.event",
        source="anima.senseguard-policy",
        subject_key=f"senseguard/{resource_id}",
        occurred_at=datetime(2026, 9, 6, 1, 3, tzinfo=UTC),
        payload={"canonical_resource_id": str(resource_id)},
        importance=EventImportance.CRITICAL,
        delivery_class=DeliveryClass.GUARANTEED,
        metadata={"household_id": str(household_id)},
    )
    calls: list[httpx.Request] = []

    def transport(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        return httpx.Response(200, content=b"{}", request=request)

    manifest, runtime = external_plugin(
        "anima.external.notifications",
        transport=httpx.MockTransport(transport),
    )
    manager = PluginManager(secret_broker=SecretBroker({"NTFY_TOPIC": "anima-test"}))
    manager.register(manifest, NativeRuntime(runtime))
    assert manager.enable(manifest.plugin_id).enabled

    class AllowConfiguredAlert:
        def evaluate(self, document: dict[str, object]) -> dict[str, object]:
            action = document["action_intent"]
            assert isinstance(action, dict)
            assert action["semantic_action"] == "notifications.send"
            assert document["origin"] == "DURABLE_SYSTEM_TASK"
            graph = document["graph"]
            assert isinstance(graph, dict)
            assert graph["notification_alert_authorized"] is True
            return {
                "decision": "ALLOW",
                "reason_code": "CONFIGURED_ALERT_NOTIFICATION",
                "policy_version": "test",
            }

    action_executor = ActionExecutionCoordinator(
        manager,
        InMemoryActionStore(),
        InMemoryResourceLocker(),
    )
    dispatcher = SenseGuardNotificationDispatcher(
        route_store=SimpleNamespace(list_all=lambda household: [route]),
        manager=manager,
        policy_service=PolicyService(AllowConfiguredAlert()),
        action_executor=action_executor,
        journal=[],
        resource_name=lambda value: "Basement SenseGuard" if value == resource_id else None,
    )

    result = dispatcher.dispatch(alert, policy)

    assert result[0]["status"] == ActionStatus.SUCCEEDED.value
    assert len(calls) == 1
    assert calls[0].url.host == "ntfy.sh"
    assert calls[0].url.path == "/anima-test"
