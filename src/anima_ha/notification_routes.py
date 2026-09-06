"""Typed notification-route metadata owned by ANIMA.

The route destination is deliberately not user supplied.  Prototype delivery
uses the server-configured ntfy provider, while the browser may manage only
the household label, priority threshold, and enabled state.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

import psycopg
from psycopg.rows import dict_row

from anima_ha.action import ActionRequest, resolve_action_safety_spec
from anima_ha.events import DeliveryClass, EventEnvelope, EventImportance
from anima_ha.plugins import (
    CORE_VERSION,
    MANIFEST_VERSION,
    ExternalContentTrust,
    Idempotency,
    InvocationContext,
    PluginManifest,
    PluginValidationError,
    RuntimeKind,
    TrustClass,
)
from anima_ha.policy import Assurance, IdentityContext, PolicyContext, RequestOrigin


class NotificationRouteError(ValueError):
    """A route is outside the bounded notification contract."""


@dataclass(frozen=True, slots=True)
class NotificationRoute:
    route_id: UUID
    household_id: UUID
    label: str = "Household notifications"
    enabled: bool = True
    minimum_priority: int = 0
    creator_principal_id: UUID | None = None
    version: int = 1
    provider_id: str = "anima.external.notifications"
    destination_ref: str = "configured_ntfy"

    def __post_init__(self) -> None:
        if not 1 <= len(self.label.strip()) <= 80:
            raise NotificationRouteError("notification route label is invalid")
        if not 0 <= self.minimum_priority <= 100:
            raise NotificationRouteError("notification priority must be between 0 and 100")
        if self.version < 1:
            raise NotificationRouteError("notification route version must be positive")
        if self.provider_id != "anima.external.notifications":
            raise NotificationRouteError("unsupported notification provider")
        if self.destination_ref != "configured_ntfy":
            raise NotificationRouteError("unsupported notification destination")

    def to_payload(self) -> dict[str, Any]:
        return {
            "route_id": str(self.route_id),
            "household_id": str(self.household_id),
            "label": self.label,
            "enabled": self.enabled,
            "minimum_priority": self.minimum_priority,
            "creator_principal_id": (
                str(self.creator_principal_id) if self.creator_principal_id else None
            ),
            "version": self.version,
            "provider": "ntfy",
            "destination": "server_configured",
        }


class PostgresNotificationRouteStore:
    """Household-scoped optimistic-version route metadata store."""

    def __init__(self, database_url: str, connect_timeout: int = 5) -> None:
        self.database_url = database_url
        self.connect_timeout = connect_timeout

    def _connect(self) -> psycopg.Connection[Any]:
        return psycopg.connect(
            self.database_url, connect_timeout=self.connect_timeout, row_factory=dict_row
        )

    @staticmethod
    def _from_row(row: dict[str, Any]) -> NotificationRoute:
        return NotificationRoute(
            route_id=UUID(str(row["route_id"])),
            household_id=UUID(str(row["household_id"])),
            label=str(row["label"]),
            enabled=bool(row["enabled"]),
            minimum_priority=int(row["minimum_priority"]),
            creator_principal_id=(
                UUID(str(row["creator_principal_id"])) if row.get("creator_principal_id") else None
            ),
            version=int(row["version"]),
            provider_id=str(row["provider_id"]),
            destination_ref=str(row["destination_ref"]),
        )

    def get(self, household_id: UUID, route_id: UUID) -> NotificationRoute | None:
        with self._connect() as connection, connection.cursor() as cursor:
            cursor.execute(
                "SELECT * FROM anima_notification_routes WHERE household_id=%s AND route_id=%s",
                (household_id, route_id),
            )
            row = cursor.fetchone()
        return self._from_row(dict(row)) if row is not None else None

    def list_all(self, household_id: UUID) -> list[NotificationRoute]:
        with self._connect() as connection, connection.cursor() as cursor:
            cursor.execute(
                "SELECT * FROM anima_notification_routes WHERE household_id=%s ORDER BY route_id",
                (household_id,),
            )
            rows = cursor.fetchall()
        return [self._from_row(dict(row)) for row in rows]

    def save(
        self, route: NotificationRoute, *, expected_version: int | None = None
    ) -> NotificationRoute:
        if expected_version is not None and expected_version != route.version - 1:
            raise NotificationRouteError("NOTIFICATION_ROUTE_VERSION_CONFLICT")
        with self._connect() as connection, connection.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO anima_notification_routes
                    (route_id, household_id, provider_id, destination_ref, label,
                     enabled, minimum_priority, creator_principal_id, version)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)
                ON CONFLICT (route_id) DO UPDATE SET
                    label=EXCLUDED.label, enabled=EXCLUDED.enabled,
                    minimum_priority=EXCLUDED.minimum_priority,
                    version=EXCLUDED.version, updated_at=now()
                WHERE anima_notification_routes.household_id=EXCLUDED.household_id
                  AND anima_notification_routes.version=%s
                RETURNING *
                """,
                (
                    route.route_id,
                    route.household_id,
                    route.provider_id,
                    route.destination_ref,
                    route.label,
                    route.enabled,
                    route.minimum_priority,
                    route.creator_principal_id,
                    route.version,
                    expected_version if expected_version is not None else 0,
                ),
            )
            row = cursor.fetchone()
            if row is None:
                connection.rollback()
                raise NotificationRouteError("NOTIFICATION_ROUTE_VERSION_CONFLICT")
            connection.commit()
        return self._from_row(dict(row))


class SenseGuardNotificationDispatcher:
    """Deliver only server-authored matched alert facts to configured ntfy.

    The route and alert policy are both pre-authorized household configuration.
    The dispatcher never accepts a model-authored destination or message. The
    actual provider call still passes through ActionExecutionCoordinator and
    the normal OPA/PluginManager boundary.
    """

    def __init__(
        self,
        *,
        route_store: Any,
        manager: Any,
        policy_service: Any,
        action_executor: Any,
        journal: Any,
        resource_name: Any,
    ) -> None:
        self.route_store = route_store
        self.manager = manager
        self.policy_service = policy_service
        self.action_executor = action_executor
        self.journal = journal
        self.resource_name = resource_name

    @staticmethod
    def _tool(manager: Any) -> Any | None:
        return next(
            (
                item
                for item in manager.list_tools()
                if item.tool_id == "anima.external.notifications.send"
            ),
            None,
        )

    def _record(
        self,
        *,
        alert: Any,
        policy_id: UUID,
        route_id: UUID | None,
        status: str,
        detail: str,
        action_id: UUID | None = None,
        provider_outcome: str | None = None,
    ) -> None:
        self.journal.append(
            EventEnvelope.create(
                event_id=str(uuid4()),
                event_type="notification.delivery",
                source="anima.notification-delivery",
                subject_key=f"senseguard/{alert.payload.get('canonical_resource_id', 'unknown')}",
                occurred_at=datetime.now(UTC),
                correlation_id=alert.correlation_id,
                causation_id=alert.event_id,
                payload={
                    "alert_event_id": alert.event_id,
                    "alert_policy_id": str(policy_id),
                    "route_id": str(route_id) if route_id else None,
                    "status": status,
                    "detail": detail[:240],
                    "action_id": str(action_id) if action_id else None,
                    "provider_outcome": provider_outcome,
                },
                importance=EventImportance.IMPORTANT,
                delivery_class=DeliveryClass.GUARANTEED,
                metadata={"household_id": str(alert.metadata.get("household_id", ""))},
            )
        )

    def dispatch(self, alert: Any, policy: Any) -> list[dict[str, Any]]:
        household_id = UUID(str(alert.metadata["household_id"]))
        routes = [
            route
            for route in self.route_store.list_all(household_id)
            if route.enabled and policy.priority >= route.minimum_priority
        ]
        if not routes:
            self._record(
                alert=alert,
                policy_id=policy.policy_id,
                route_id=None,
                status="NO_ROUTE",
                detail="no enabled configured route met the alert priority threshold",
            )
            return [{"status": "NO_ROUTE"}]
        tool = self._tool(self.manager)
        if tool is None or not tool.availability:
            results = []
            for route in routes:
                self._record(
                    alert=alert,
                    policy_id=policy.policy_id,
                    route_id=route.route_id,
                    status="UNAVAILABLE",
                    detail="configured ntfy provider is unavailable",
                )
                results.append({"status": "UNAVAILABLE", "route_id": str(route.route_id)})
            return results

        resource_id = str(alert.payload.get("canonical_resource_id", "unknown"))
        name = str(self.resource_name(UUID(resource_id)) or f"SenseGuard {resource_id[:8]}")
        occurred_at = str(alert.payload.get("occurred_at", alert.occurred_at.isoformat()))
        message = (
            f"{name} detected an event at {occurred_at}. "
            "ANIMA recorded it; ask SENTRY for the current state."
        )[:4000]
        results = []
        for route in routes:
            action_idempotency = f"senseguard-notification:{alert.event_id}:{route.route_id}"
            request = ActionRequest.create(
                idempotency_key=action_idempotency,
                household_id=household_id,
                tool=tool,
                arguments={"title": "ANIMA household alert", "message": message},
                identity=IdentityContext(
                    household_id,
                    None,
                    Assurance.ANONYMOUS,
                    explanation="server-generated notification from matched owner policy",
                ),
                policy_service=self.policy_service,
                policy_context=PolicyContext(
                    graph_metadata={
                        "notification_alert_authorized": True,
                        "notification_route_id": str(route.route_id),
                        "alert_policy_id": str(policy.policy_id),
                    }
                ),
                origin=RequestOrigin.DURABLE_SYSTEM_TASK,
                safety_spec=resolve_action_safety_spec(tool),
            )
            execution = self.action_executor.execute(request)
            status = execution.record.status.value
            provider_outcome = (
                execution.invocation.outcome.value if execution.invocation is not None else None
            )
            self._record(
                alert=alert,
                policy_id=policy.policy_id,
                route_id=route.route_id,
                status=status,
                detail=execution.record.detail or "notification action completed",
                action_id=execution.record.action_id,
                provider_outcome=provider_outcome,
            )
            results.append(
                {
                    "status": status,
                    "route_id": str(route.route_id),
                    "action_id": str(execution.record.action_id),
                }
            )
        return results


def _schema(name: str) -> dict[str, Any]:
    if name == "list_routes":
        return {"type": "object", "additionalProperties": False}
    return {
        "type": "object",
        "properties": {
            "route_id": {"type": "string", "format": "uuid"},
            "expected_version": {"type": "integer", "minimum": 1},
            "label": {"type": "string", "minLength": 1, "maxLength": 80},
            "enabled": {"type": "boolean"},
            "minimum_priority": {"type": "integer", "minimum": 0, "maximum": 100},
        },
        "required": ["label"],
        "additionalProperties": False,
    }


NOTIFICATION_ROUTE_MANIFEST = PluginManifest(
    plugin_id="anima.notification-routes",
    plugin_version="0.1.0",
    manifest_version=MANIFEST_VERSION,
    requires_core=CORE_VERSION,
    name="ANIMA notification routes",
    description="Household-scoped metadata for the server-configured notification provider",
    runtime_kind=RuntimeKind.TRUSTED_NATIVE,
    trust_class=TrustClass.TRUSTED_NATIVE,
    capabilities=("notification_routes",),
    tools=(
        {
            "name": "list_routes",
            "description": "List notification routes for the current household",
            "input_schema": _schema("list_routes"),
            "output_schema": {"type": "object"},
            "semantic_action": "read_notification_routes",
            "risk_class": "READ_ONLY",
            "read_only": True,
            "idempotency": Idempotency.IDEMPOTENT.value,
            "external_content_trust": ExternalContentTrust.LOCAL_TRUSTED.value,
        },
        {
            "name": "save_route",
            "description": "Create or update bounded notification route metadata",
            "input_schema": _schema("save_route"),
            "output_schema": {"type": "object"},
            "semantic_action": "configure_notifications",
            "risk_class": "LOW_RISK_HOME_CONTROL",
            "read_only": False,
            "idempotency": Idempotency.KEYED.value,
            "external_content_trust": ExternalContentTrust.LOCAL_TRUSTED.value,
        },
    ),
    source="builtin:anima_ha.notification_routes",
)


class NotificationRouteNativePlugin:
    def __init__(self, store: PostgresNotificationRouteStore) -> None:
        self.store = store

    def start(self, secret_env: dict[str, str]) -> None:
        if secret_env:
            raise PluginValidationError("notification route metadata accepts no secrets")

    def stop(self) -> None:
        return None

    def list_tools(self) -> list[dict[str, Any]]:
        return [dict(item) for item in NOTIFICATION_ROUTE_MANIFEST.tools]

    def invoke(self, name: str, arguments: dict[str, Any], timeout: float) -> Any:
        raise PluginValidationError("notification routes require trusted invocation context")

    def invoke_with_invocation_context(
        self, name: str, arguments: dict[str, Any], timeout: float, context: InvocationContext
    ) -> Any:
        del timeout
        if name == "list_routes":
            return {
                "routes": [item.to_payload() for item in self.store.list_all(context.household_id)]
            }
        if name != "save_route":
            raise PluginValidationError("unknown notification route operation")
        route_id = UUID(str(arguments["route_id"])) if arguments.get("route_id") else uuid4()
        current = self.store.get(context.household_id, route_id)
        if current is not None and arguments.get("expected_version") is None:
            raise NotificationRouteError("NOTIFICATION_ROUTE_VERSION_REQUIRED")
        route = NotificationRoute(
            route_id=route_id,
            household_id=context.household_id,
            label=str(arguments["label"]),
            enabled=bool(arguments.get("enabled", True)),
            minimum_priority=int(arguments.get("minimum_priority", 0)),
            creator_principal_id=(
                current.creator_principal_id if current else context.principal_id
            ),
            version=current.version + 1 if current else 1,
        )
        saved = self.store.save(route, expected_version=arguments.get("expected_version"))
        return {"route": saved.to_payload()}
