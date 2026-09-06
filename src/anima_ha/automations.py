"""ANIMA-owned bounded event-to-action automations.

Automations accept only canonical resource references and a boolean power
intent.  A matching HA observation is still routed through the ordinary
PluginManager, OPA, action lock, fresh observation, and Phase 9 verification
path.  This module never accepts HA service names, entity IDs, templates, or
arbitrary executable configuration.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, replace
from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

import psycopg
from psycopg.rows import dict_row

from anima_ha.action import ActionExecutionCoordinator, ActionRequest
from anima_ha.events import EventEnvelope
from anima_ha.plugins import (
    CORE_VERSION,
    MANIFEST_VERSION,
    ExternalContentTrust,
    Idempotency,
    InvocationResult,
    PluginManifest,
    PluginValidationError,
    RuntimeKind,
    TrustClass,
)
from anima_ha.policy import Assurance, IdentityContext, PolicyContext, PolicyService, RequestOrigin

AUTOMATIONS_MANIFEST_ID = "anima.automations"
MAX_AUTOMATION_NAME = 80


class AutomationError(RuntimeError):
    """Base class for bounded automation validation and persistence errors."""


class AutomationNotFound(AutomationError):
    pass


class AutomationConflict(AutomationError):
    pass


def _state(value: Any) -> str:
    clean = str(value).strip().casefold()
    if clean not in {"on", "off"}:
        raise AutomationError("automation state must be on or off")
    return clean


@dataclass(frozen=True, slots=True)
class Automation:
    automation_id: UUID
    household_id: UUID
    name: str
    trigger_resource_id: UUID
    trigger_state: str
    action_resource_id: UUID
    action_desired_on: bool
    enabled: bool
    creator_principal_id: UUID | None
    version: int
    created_at: datetime
    updated_at: datetime

    @classmethod
    def create(
        cls,
        *,
        household_id: UUID,
        name: str,
        trigger_resource_id: UUID,
        trigger_state: Any,
        action_resource_id: UUID,
        action_desired_on: bool,
        creator_principal_id: UUID | None,
        now: datetime | None = None,
        automation_id: UUID | None = None,
    ) -> Automation:
        clean_name = str(name).strip()
        if not 1 <= len(clean_name) <= MAX_AUTOMATION_NAME:
            raise AutomationError(f"name must contain 1 to {MAX_AUTOMATION_NAME} characters")
        if not isinstance(action_desired_on, bool):
            raise AutomationError("action_desired_on must be boolean")
        at = (now or datetime.now(UTC)).astimezone(UTC)
        return cls(
            automation_id or uuid4(),
            household_id,
            clean_name,
            trigger_resource_id,
            _state(trigger_state),
            action_resource_id,
            action_desired_on,
            True,
            creator_principal_id,
            1,
            at,
            at,
        )

    def to_payload(self) -> dict[str, Any]:
        return {
            "automation_id": str(self.automation_id),
            "name": self.name,
            "trigger_resource_id": str(self.trigger_resource_id),
            "trigger_state": self.trigger_state,
            "action_resource_id": str(self.action_resource_id),
            "action_desired_on": self.action_desired_on,
            "enabled": self.enabled,
            "version": self.version,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
        }


def _from_row(row: dict[str, Any]) -> Automation:
    return Automation(
        UUID(str(row["automation_id"])),
        UUID(str(row["household_id"])),
        str(row["name"]),
        UUID(str(row["trigger_resource_id"])),
        _state(row["trigger_state"]),
        UUID(str(row["action_resource_id"])),
        bool(row["action_desired_on"]),
        bool(row["enabled"]),
        UUID(str(row["creator_principal_id"])) if row.get("creator_principal_id") else None,
        int(row["version"]),
        row["created_at"],
        row["updated_at"],
    )


class PostgresAutomationStore:
    def __init__(self, database_url: str) -> None:
        self.database_url = database_url

    def _connect(self) -> psycopg.Connection[Any]:
        return psycopg.connect(self.database_url, row_factory=dict_row)

    def list(self, household_id: UUID) -> list[Automation]:
        with self._connect() as connection, connection.cursor() as cursor:
            cursor.execute(
                "SELECT * FROM anima_automations "
                "WHERE household_id=%s ORDER BY name, automation_id",
                (household_id,),
            )
            return [_from_row(dict(row)) for row in cursor.fetchall()]

    def get(self, household_id: UUID, automation_id: UUID) -> Automation:
        with self._connect() as connection, connection.cursor() as cursor:
            cursor.execute(
                "SELECT * FROM anima_automations WHERE household_id=%s AND automation_id=%s",
                (household_id, automation_id),
            )
            row = cursor.fetchone()
        if row is None:
            raise AutomationNotFound(str(automation_id))
        return _from_row(dict(row))

    def create(self, automation: Automation) -> Automation:
        with self._connect() as connection, connection.cursor() as cursor:
            cursor.execute(
                """INSERT INTO anima_automations
                (automation_id, household_id, name, trigger_resource_id, trigger_state,
                 action_resource_id, action_desired_on, enabled, creator_principal_id,
                 version, created_at, updated_at)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING *""",
                (
                    automation.automation_id,
                    automation.household_id,
                    automation.name,
                    automation.trigger_resource_id,
                    automation.trigger_state,
                    automation.action_resource_id,
                    automation.action_desired_on,
                    automation.enabled,
                    automation.creator_principal_id,
                    automation.version,
                    automation.created_at,
                    automation.updated_at,
                ),
            )
            row = cursor.fetchone()
            connection.commit()
        assert row is not None
        return _from_row(dict(row))

    def update(
        self,
        household_id: UUID,
        automation_id: UUID,
        expected_version: int,
        *,
        name: str,
        trigger_resource_id: UUID,
        trigger_state: Any,
        action_resource_id: UUID,
        action_desired_on: bool,
        enabled: bool,
        now: datetime,
    ) -> Automation:
        clean_name = str(name).strip()
        if not 1 <= len(clean_name) <= MAX_AUTOMATION_NAME:
            raise AutomationError(f"name must contain 1 to {MAX_AUTOMATION_NAME} characters")
        with self._connect() as connection, connection.cursor() as cursor:
            cursor.execute(
                """UPDATE anima_automations SET name=%s, trigger_resource_id=%s,
                   trigger_state=%s, action_resource_id=%s, action_desired_on=%s,
                   enabled=%s, version=version+1, updated_at=%s
                   WHERE household_id=%s AND automation_id=%s AND version=%s
                   RETURNING *""",
                (
                    clean_name,
                    trigger_resource_id,
                    _state(trigger_state),
                    action_resource_id,
                    action_desired_on,
                    enabled,
                    now.astimezone(UTC),
                    household_id,
                    automation_id,
                    expected_version,
                ),
            )
            row = cursor.fetchone()
            if row is None:
                connection.rollback()
                current = self.get(household_id, automation_id)
                raise AutomationConflict(
                    f"automation version is stale; current version is {current.version}"
                )
            connection.commit()
        return _from_row(dict(row))


class InMemoryAutomationStore:
    def __init__(self) -> None:
        self.automations: dict[UUID, Automation] = {}

    def list(self, household_id: UUID) -> list[Automation]:
        return sorted(
            (item for item in self.automations.values() if item.household_id == household_id),
            key=lambda item: (item.name, item.automation_id),
        )

    def get(self, household_id: UUID, automation_id: UUID) -> Automation:
        item = self.automations.get(automation_id)
        if item is None or item.household_id != household_id:
            raise AutomationNotFound(str(automation_id))
        return item

    def create(self, automation: Automation) -> Automation:
        if automation.automation_id in self.automations:
            raise AutomationConflict("automation identity already exists")
        self.automations[automation.automation_id] = automation
        return automation

    def update(
        self,
        household_id: UUID,
        automation_id: UUID,
        expected_version: int,
        *,
        name: str,
        trigger_resource_id: UUID,
        trigger_state: Any,
        action_resource_id: UUID,
        action_desired_on: bool,
        enabled: bool,
        now: datetime,
    ) -> Automation:
        current = self.get(household_id, automation_id)
        if current.version != expected_version:
            raise AutomationConflict("automation version is stale")
        updated = replace(
            current,
            name=str(name).strip(),
            trigger_resource_id=trigger_resource_id,
            trigger_state=_state(trigger_state),
            action_resource_id=action_resource_id,
            action_desired_on=action_desired_on,
            enabled=enabled,
            version=current.version + 1,
            updated_at=now.astimezone(UTC),
        )
        self.automations[automation_id] = updated
        return updated


def _schema(*, update: bool = False) -> dict[str, Any]:
    properties: dict[str, Any] = {
        "automation_id": {"type": "string", "format": "uuid"},
        "expected_version": {"type": "integer", "minimum": 1},
        "name": {"type": "string", "minLength": 1, "maxLength": MAX_AUTOMATION_NAME},
        "trigger_resource_id": {"type": "string", "format": "uuid"},
        "trigger_state": {"type": "string", "enum": ["on", "off"]},
        "action_resource_id": {"type": "string", "format": "uuid"},
        "action_desired_on": {"type": "boolean"},
        "enabled": {"type": "boolean"},
    }
    del update
    required = [
        "name",
        "trigger_resource_id",
        "trigger_state",
        "action_resource_id",
        "action_desired_on",
    ]
    return {
        "type": "object",
        "properties": properties,
        "required": required,
        "additionalProperties": False,
    }


def _tool(
    name: str, description: str, schema: dict[str, Any], *, read_only: bool
) -> dict[str, Any]:
    return {
        "name": name,
        "description": description,
        "input_schema": schema,
        "output_schema": {"type": "object"},
        "semantic_action": "read_automations" if read_only else "configure_automations",
        "risk_class": "READ_ONLY" if read_only else "LOW_RISK_HOME_CONTROL",
        "read_only": read_only,
        "idempotency": Idempotency.IDEMPOTENT.value if read_only else Idempotency.KEYED.value,
        "external_content_trust": ExternalContentTrust.LOCAL_TRUSTED.value,
    }


AUTOMATIONS_MANIFEST = PluginManifest(
    plugin_id=AUTOMATIONS_MANIFEST_ID,
    plugin_version="0.1.0",
    manifest_version=MANIFEST_VERSION,
    requires_core=CORE_VERSION,
    name="ANIMA automations",
    description="Bounded event-triggered canonical power actions",
    runtime_kind=RuntimeKind.TRUSTED_NATIVE,
    trust_class=TrustClass.TRUSTED_NATIVE,
    capabilities=("automations",),
    tools=(
        _tool(
            "list_automations",
            "List household automations",
            {"type": "object", "additionalProperties": False},
            read_only=True,
        ),
        _tool(
            "create_automation",
            "Create a bounded event-to-power automation",
            _schema(),
            read_only=False,
        ),
        _tool(
            "update_automation",
            "Update an automation with optimistic version protection",
            _schema(update=True),
            read_only=False,
        ),
    ),
    source="builtin:anima_ha.automations",
)


class AutomationNativePlugin:
    def __init__(self, store: Any, resource_validator: Callable[[UUID, UUID], bool]) -> None:
        self.store = store
        self.resource_validator = resource_validator

    def start(self, secret_env: dict[str, str]) -> None:
        if secret_env:
            raise PluginValidationError("automations accept no secrets")

    def stop(self) -> None:
        return None

    def list_tools(self) -> list[dict[str, Any]]:
        return [dict(item) for item in AUTOMATIONS_MANIFEST.tools]

    def invoke(self, name: str, arguments: dict[str, Any], timeout: float) -> Any:
        del name, arguments, timeout
        raise PluginValidationError("automations require trusted invocation context")

    def invoke_with_invocation_context(
        self, name: str, arguments: dict[str, Any], timeout: float, context: Any
    ) -> Any:
        del timeout
        if name == "list_automations":
            return {
                "automations": [item.to_payload() for item in self.store.list(context.household_id)]
            }
        if name not in {"create_automation", "update_automation"}:
            raise AutomationError(f"unknown automation operation: {name}")
        trigger_resource_id = UUID(str(arguments["trigger_resource_id"]))
        action_resource_id = UUID(str(arguments["action_resource_id"]))
        if not self.resource_validator(context.household_id, trigger_resource_id):
            raise AutomationError("AUTOMATION_TRIGGER_NOT_COMMISSIONED")
        if not self.resource_validator(context.household_id, action_resource_id):
            raise AutomationError("AUTOMATION_ACTION_NOT_COMMISSIONED")
        if name == "create_automation":
            automation = Automation.create(
                household_id=context.household_id,
                name=str(arguments["name"]),
                trigger_resource_id=trigger_resource_id,
                trigger_state=arguments["trigger_state"],
                action_resource_id=action_resource_id,
                action_desired_on=arguments["action_desired_on"],
                creator_principal_id=context.principal_id,
            )
            return {"automation": self.store.create(automation).to_payload()}
        automation = self.store.get(context.household_id, UUID(str(arguments["automation_id"])))
        if arguments.get("expected_version") is None:
            raise AutomationError("AUTOMATION_VERSION_REQUIRED")
        updated = self.store.update(
            context.household_id,
            automation.automation_id,
            int(arguments["expected_version"]),
            name=str(arguments.get("name", automation.name)),
            trigger_resource_id=trigger_resource_id,
            trigger_state=arguments.get("trigger_state", automation.trigger_state),
            action_resource_id=action_resource_id,
            action_desired_on=arguments.get("action_desired_on", automation.action_desired_on),
            enabled=bool(arguments.get("enabled", automation.enabled)),
            now=datetime.now(UTC),
        )
        return {"automation": updated.to_payload()}


class AutomationEventRouter:
    """Match one normalized observation and execute one governed power action."""

    def __init__(
        self,
        *,
        household_id: UUID,
        store: Any,
        resource_resolver: Callable[[str], UUID | None],
        manager: Any,
        action_executor: ActionExecutionCoordinator,
        policy_service: PolicyService,
        action_refresher: Callable[[tuple[UUID, ...]], Any] | None,
        action_verifier: Callable[[Any, InvocationResult, Any], Any] | None,
        role_resolver: Callable[[UUID], str | None],
        journal: Any,
    ) -> None:
        self.household_id = household_id
        self.store = store
        self.resource_resolver = resource_resolver
        self.manager = manager
        self.action_executor = action_executor
        self.policy_service = policy_service
        self.action_refresher = action_refresher
        self.action_verifier = action_verifier
        self.role_resolver = role_resolver
        self.journal = journal

    @staticmethod
    def _observed_state(event: EventEnvelope) -> str | None:
        payload = event.payload if isinstance(event.payload, dict) else {}
        value = payload.get("value")
        if isinstance(value, bool):
            return "on" if value else "off"
        clean = str(value).strip().casefold()
        return clean if clean in {"on", "off"} else None

    def handle(self, event: EventEnvelope) -> list[dict[str, Any]]:
        if event.event_type != "truth.observation":
            return []
        external_id = str(event.metadata.get("external_id", ""))
        resource_id = self.resource_resolver(external_id) if external_id else None
        state = self._observed_state(event)
        if resource_id is None or state is None:
            return []
        results: list[dict[str, Any]] = []
        for automation in self.store.list(self.household_id):
            if not automation.enabled or automation.trigger_resource_id != resource_id:
                continue
            if automation.trigger_state != state:
                continue
            tool = next(
                (
                    item
                    for item in self.manager.list_tools()
                    if item.plugin_id == "anima.provider.home-assistant"
                    and item.name == "set_power"
                ),
                None,
            )
            if tool is None or not tool.availability:
                result = {"status": "UNAVAILABLE", "automation_id": str(automation.automation_id)}
            else:
                principal = automation.creator_principal_id
                identity = IdentityContext(
                    self.household_id,
                    principal,
                    Assurance.AUTHENTICATED,
                    explanation="configured ANIMA automation",
                )
                action = ActionRequest.create(
                    idempotency_key=f"automation:{automation.automation_id}:{event.event_id}",
                    household_id=self.household_id,
                    tool=tool,
                    arguments={
                        "resource_id": str(automation.action_resource_id),
                        "desired_on": automation.action_desired_on,
                    },
                    identity=identity,
                    policy_service=self.policy_service,
                    policy_context=PolicyContext(
                        principal_role=self.role_resolver(principal) if principal else None
                    ),
                    refresher=self.action_refresher,
                    verifier=self.action_verifier,
                    origin=RequestOrigin.AUTONOMOUS_AGENT,
                    trigger_id=UUID(str(event.event_id)) if _is_uuid(event.event_id) else None,
                )
                execution = self.action_executor.execute(action)
                result = {
                    "status": execution.record.status.value,
                    "automation_id": str(automation.automation_id),
                    "action_id": str(execution.record.action_id),
                    "event_id": event.event_id,
                }
            self.journal.append(
                EventEnvelope.create(
                    event_id=str(uuid4()),
                    source_event_id=event.event_id,
                    event_type="automation.fired",
                    source="anima:automations",
                    subject_key=f"automation/{automation.automation_id}",
                    occurred_at=event.occurred_at,
                    payload=result,
                    correlation_id=event.correlation_id,
                    causation_id=event.event_id,
                    metadata={"household_id": str(self.household_id)},
                )
            )
            results.append(result)
        return results


def _is_uuid(value: str) -> bool:
    try:
        UUID(str(value))
    except ValueError:
        return False
    return True
