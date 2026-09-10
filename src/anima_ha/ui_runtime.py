"""Composition adapters that connect the local interface to ANIMA Core.

This module contains wiring only.  Domain behavior remains in the accepted
journal, attention, context, agent, policy, plugin, task, calendar, and action
modules.  The UI receives these adapters; it never calls a provider or a
database service directly.
"""

from __future__ import annotations

import os
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

from anima_ha.action import (
    ActionExecutionCoordinator,
    ActionRequest,
    PostgresActionStore,
    PostgresPendingApprovalStore,
    PostgresResourceLocker,
    resolve_action_safety_spec,
)
from anima_ha.agent import (
    AgentRuntime,
    CodexCliRuntime,
    EpisodeRequest,
    EpisodeRunResult,
    PostgresEpisodeStore,
)
from anima_ha.attention import (
    AttentionProfile,
    PostgresAttentionService,
    default_attention_profile,
)
from anima_ha.automations import (
    AUTOMATIONS_MANIFEST,
    AutomationEventRouter,
    AutomationNativePlugin,
    PostgresAutomationStore,
)
from anima_ha.backup import BACKUP_MANIFEST, BackupCoordinator, BackupNativePlugin
from anima_ha.calendar import (
    CALENDAR_MANIFEST,
    CalendarNativePlugin,
    CalendarService,
    PostgresCalendarStore,
)
from anima_ha.capability_management import (
    CAPABILITY_MANAGEMENT_MANIFEST,
    CapabilityManagementNativePlugin,
)
from anima_ha.context import ContextBroker
from anima_ha.events import EventEnvelope
from anima_ha.external import ExternalAuditJournalSink, external_plugin
from anima_ha.family_routines import FAMILY_ROUTINES_MANIFEST, FamilyRoutinesNativePlugin
from anima_ha.graph import NodeKind, PostgresHouseholdGraph, ProviderReference, RelationshipType
from anima_ha.home_assistant import (
    HAInstanceConfig,
    HassClientConnection,
    HomeAssistantAdapter,
    HomeAssistantPlugin,
    PostgresHAStore,
    home_assistant_manifest,
    inventory_handle,
)
from anima_ha.household_event_context import HouseholdEventEvidence
from anima_ha.household_initiative import HouseholdInitiativeContext
from anima_ha.household_learning import (
    HOUSEHOLD_LEARNING_MANIFEST,
    HouseholdLearningNativePlugin,
    HouseholdLearningService,
)
from anima_ha.household_presence import (
    HOUSEHOLD_PRESENCE_MANIFEST,
    HouseholdPresenceNativePlugin,
    HouseholdPresenceService,
    SignalKind,
)
from anima_ha.household_presence_runtime import HouseholdPresenceEventRouter
from anima_ha.household_spaces import (
    HOUSEHOLD_SPACES_MANIFEST,
    HouseholdSpacesNativePlugin,
)
from anima_ha.intelligence import (
    IntelligenceOrigin,
    IntelligenceProviderMode,
    IntelligenceRequest,
    IntelligenceRequestFactory,
    PostgresIntelligenceStore,
    SentryAttentionBridge,
)
from anima_ha.journal import PostgresEventJournal, PostgresRealityStore
from anima_ha.knowledge import KNOWLEDGE_MANIFEST, KnowledgeConfig, KnowledgeNativePlugin
from anima_ha.notification_routes import (
    NOTIFICATION_ROUTE_MANIFEST,
    NotificationRouteNativePlugin,
    PostgresNotificationRouteStore,
    SenseGuardNotificationDispatcher,
)
from anima_ha.plugins import (
    InvocationContext,
    InvocationOutcome,
    InvocationResult,
    NativeRuntime,
    PluginManager,
    SecretBroker,
)
from anima_ha.policy import (
    Assurance,
    IdentityContext,
    OpaPolicyClient,
    PolicyContext,
    PolicyService,
    PostgresPolicyStore,
    RequestOrigin,
)
from anima_ha.preferences import PREFERENCES_MANIFEST, PreferencesNativePlugin
from anima_ha.scenes import SCENES_MANIFEST, PostgresSceneStore, SceneError, SceneNativePlugin
from anima_ha.senseguard_alerts import (
    SENSEGUARD_ALERT_MANIFEST,
    PostgresSenseGuardAlertPolicyStore,
    SenseGuardAlertNativePlugin,
    SenseGuardEventRouter,
)
from anima_ha.sentry_boundary import CoreSentryBoundary
from anima_ha.sentry_identity_profiles import (
    SentryIdentityProfileClient,
    SentryIdentityProfileError,
)
from anima_ha.sentry_voice_settings import (
    SENTRY_CONTROL_MANIFEST,
    SentryControlNativePlugin,
    SentryVoiceSettingsStore,
)
from anima_ha.tasks import TASK_MANIFEST, PostgresTaskStore, TaskNativePlugin, TaskService
from anima_ha.users import HOUSEHOLD_USERS_MANIFEST, HouseholdUsersNativePlugin, user_payload
from anima_ha.vendor_events import (
    VENDOR_EVENTS_MANIFEST,
    PostgresVendorEventStore,
    VendorEventsNativePlugin,
)


def _dispatch_senseguard_attention(
    *,
    alert: EventEnvelope,
    journal_position: int,
    household_id: UUID,
    attention: Any,
    context: Any,
    store: Any,
    tools: list[Any],
    event_path_resolver: Any | None = None,
) -> list[IntelligenceRequest]:
    """Dispatch one already-journaled policy alert, including delayed recovery."""
    if (
        alert.source != "anima:senseguard-policy"
        or str(alert.metadata.get("household_id", "")) != str(household_id)
        or journal_position < 1
    ):
        raise ValueError("SenseGuard dispatch requires a journaled same-household policy alert")
    # Fresh trigger identities cannot reuse contexts from the old broad bridge.
    profile = AttentionProfile("phase13.senseguard.event.v2", ())
    consumer = f"senseguard-alert:{household_id}:{alert.event_id}"
    attention.prime_consumer_before(profile, consumer, journal_position - 1)
    return SentryAttentionBridge(
        attention=attention,
        context=context,
        store=store,
        profile=profile,
        event_path_resolver=event_path_resolver,
    ).run_once(
        household_id=household_id,
        tools=tools,
        consumer_name=consumer,
        limit=1,
        source_event_id=alert.event_id,
    )


def _resolve_ha_event_resource(
    graph: PostgresHouseholdGraph, provider_scope: str, household_id: UUID, external_id: str
) -> UUID | None:
    """Resolve an HA entity to one active device owned only by this household."""
    nodes = graph.resolve_provider_references(
        "home_assistant", provider_scope, "entity", external_id
    )
    if len(nodes) != 1:
        return None
    node = nodes[0]
    if node.kind == NodeKind.CAPABILITY:
        capability_type = str(node.metadata.get("capability_type", ""))
        if not capability_type:
            return None
        # Candidate lookup is global: a second owner outside this household is
        # still ambiguous. resource_capabilities checks the exact, active EXPOSES
        # edge (the broader type lookup can also return retired relationships).
        owners = {
            resource.canonical_id
            for resource in graph.resources_with_capability(capability_type)
            if resource.kind in {NodeKind.RESOURCE, NodeKind.SENSOR}
            and any(
                capability.canonical_id == node.canonical_id
                for capability in graph.resource_capabilities(resource.canonical_id)
            )
        }
        if len(owners) != 1:
            return None
        resource_id = next(iter(owners))
    elif node.kind in {NodeKind.RESOURCE, NodeKind.SENSOR}:
        resource_id = node.canonical_id
    else:
        return None
    if len(graph.related(resource_id, RelationshipType.INSTALLED_IN)) != 1:
        return None
    households = {
        place.canonical_id
        for place in graph.list_places()
        if place.kind == NodeKind.HOUSEHOLD
        and any(
            resource.canonical_id == resource_id
            for resource in graph.resources_in_place(place.canonical_id)
        )
    }
    return resource_id if households == {household_id} else None


def _identity(identity: UIIdentity) -> IdentityContext:
    return IdentityContext(
        identity.household_id,
        identity.principal_id,
        Assurance.AUTHENTICATED,
        evidence_ids=(identity.evidence.evidence_id,),
        explanation="authenticated local interface session",
    )


def _safe_result(result: InvocationResult) -> dict[str, Any]:
    """Expose a stable UI outcome without leaking policy internals."""
    response: dict[str, Any] = {
        "status": {
            InvocationOutcome.SUCCESS: "SUCCEEDED",
            InvocationOutcome.POLICY_DENIED: "DENIED",
            InvocationOutcome.REQUIRE_CONFIRMATION: "REQUIRE_CONFIRMATION",
            InvocationOutcome.REQUIRE_STRONGER_AUTH: "REQUIRE_STRONGER_AUTH",
            InvocationOutcome.PLUGIN_UNAVAILABLE: "UNAVAILABLE",
            InvocationOutcome.PLUGIN_ERROR: "FAILED",
            InvocationOutcome.PLUGIN_TIMEOUT: "UNKNOWN_RESULT",
            InvocationOutcome.UNKNOWN_RESULT: "UNKNOWN_RESULT",
            InvocationOutcome.VERIFICATION_FAILED: "FAILED",
            InvocationOutcome.INVALID_ARGUMENTS: "FAILED",
            InvocationOutcome.INVALID_RESULT: "FAILED",
        }.get(result.outcome, result.outcome.value),
        "operation": result.tool_id,
    }
    if result.result is not None:
        response["result"] = result.result
    if result.error_class:
        response["reason"] = result.error_class
    if result.policy_decision is not None:
        response["policy"] = result.policy_decision.decision.value
    return response


def _safe_action_result(execution: Any, operation: str) -> dict[str, Any]:
    """Project the coordinator's terminal record into the UI contract.

    Connector acknowledgement is retained as bounded evidence only.  The
    coordinator record is authoritative because it includes fresh prechecks,
    policy reauthorization, and post-action verification.
    """
    status = execution.record.status
    response: dict[str, Any] = {
        "status": status.value,
        "operation": operation,
        "detail": execution.record.detail,
    }
    if execution.record.result is not None:
        response["result"] = execution.record.result
    if execution.invocation is not None:
        response["evidence"] = {
            "connector_outcome": execution.invocation.outcome.value,
            "dispatch_state": execution.invocation.dispatch_state.value,
        }
    return response


def _safe_confirmation_result(
    result: dict[str, Any], *, decision: str, approval_status: str, action_status: str
) -> dict[str, Any]:
    """Keep an authenticated rejection distinct from a policy decision.

    The action store retains ``POLICY_DENIED`` as the terminal action status
    for a rejected confirmation because no provider dispatch was authorized.
    The UI also needs to tell the user what happened: the principal rejected
    the confirmation.  Preserve both facts without exposing policy internals.
    """
    result = dict(result)
    result["approval_decision"] = decision
    result["approval_status"] = approval_status
    result["action_status"] = action_status
    if decision == "REJECT" and approval_status == "REJECTED":
        result["status"] = "REJECTED"
    return result


@dataclass(slots=True)
class CoreUICommandGateway:
    """Route UI mutations through the existing PluginManager and coordinator."""

    manager: PluginManager
    policy_service: PolicyService
    events: UIEventBroadcaster | None = None
    action_executor: ActionExecutionCoordinator | None = None
    action_refresher: Callable[[tuple[UUID, ...]], Any] | None = None
    action_verifier: Callable[[Any, InvocationResult, Any], Any] | None = None
    policy_role_resolver: Callable[[UUID], str | None] | None = None
    control_capability_resolver: Callable[[UUID], UUID | None] | None = None
    agent: AgentRuntime | None = None
    home_assistant_adapter: HomeAssistantAdapter | None = None
    scene_store: PostgresSceneStore | None = None
    automation_store: PostgresAutomationStore | None = None
    household_graph: PostgresHouseholdGraph | None = None
    sentry_identity_profiles: SentryIdentityProfileClient | None = None

    def _policy_context(self, identity: UIIdentity) -> PolicyContext:
        role = (
            self.policy_role_resolver(identity.principal_id)
            if self.policy_role_resolver is not None
            else None
        )
        return PolicyContext(principal_role=role)

    def _tool(self, plugin_prefix: str, name: str) -> Any:
        return next(
            (
                item
                for item in self.manager.list_tools()
                if item.plugin_id == plugin_prefix and item.name == name
            ),
            None,
        )

    def _tool_by_id(self, tool_id: str) -> Any:
        return next((item for item in self.manager.list_tools() if item.tool_id == tool_id), None)

    def _invoke(
        self, identity: UIIdentity, plugin_prefix: str, name: str, payload: dict[str, Any]
    ) -> dict[str, Any]:
        tool = self._tool(plugin_prefix, name)
        if tool is None or not tool.availability:
            raise UICommandError(f"CORE_TOOL_UNAVAILABLE:{plugin_prefix}.{name}")
        payload = self._normalize_ui_payload(plugin_prefix, name, payload)
        policy_identity = _identity(identity)
        invocation_context = InvocationContext(
            household_id=identity.household_id,
            principal_id=identity.principal_id,
            episode_id=None,
            tool_request_id=uuid4(),
            ordinal=1,
            system_idempotency_key=f"ui:{identity.household_id}:{tool.tool_id}:{uuid4()}",
            origin=RequestOrigin.DIRECT_USER,
        )
        result = self.manager.invoke(
            tool.tool_id,
            dict(payload),
            household_id=identity.household_id,
            identity=policy_identity,
            origin=RequestOrigin.DIRECT_USER,
            policy_service=self.policy_service,
            policy_context=self._policy_context(identity),
            invocation_context=invocation_context,
        )
        if self.events and not (plugin_prefix == KNOWLEDGE_MANIFEST.plugin_id and tool.read_only):
            event_name = {
                "anima.durable-tasks": "tasks.changed",
                "anima.calendar": "calendar.changed",
                "anima.senseguard-alerts": "alerts.changed",
                "anima.provider.home-assistant": "home.invalidated",
                "anima.scenes": "home.invalidated",
                "anima.household-preferences": "preferences.changed",
                "anima.household-users": "household.changed",
            }.get(plugin_prefix, "capabilities.changed")
            self.events.publish(event_name)
        return _safe_result(result)

    @staticmethod
    def _normalize_ui_payload(
        plugin_prefix: str, name: str, payload: dict[str, Any]
    ) -> dict[str, Any]:
        if plugin_prefix == "anima.durable-tasks" and name == "schedule":
            if "when" in payload:
                when = str(payload["when"])
                if not when.endswith(("Z", "+00:00")):
                    when = when + "Z"
                return {
                    "task_type": "REASONING_DUE",
                    "title": str(payload.get("title", "Anima reminder")),
                    "payload": {
                        "objective": str(payload.get("note") or payload.get("title", "")),
                        "subject_refs": [],
                    },
                    "schedule": {"kind": "ONCE", "timezone": "UTC", "run_at": when},
                }
        return dict(payload)

    def task_mutation(
        self, identity: UIIdentity, operation: str, payload: dict[str, Any]
    ) -> dict[str, Any]:
        return self._invoke(identity, "anima.durable-tasks", operation, payload)

    def calendar_mutation(
        self, identity: UIIdentity, operation: str, payload: dict[str, Any]
    ) -> dict[str, Any]:
        return self._invoke(identity, "anima.calendar", operation, payload)

    def alert_policy_mutation(
        self, identity: UIIdentity, operation: str, payload: dict[str, Any]
    ) -> dict[str, Any]:
        return self._invoke(identity, "anima.senseguard-alerts", operation, payload)

    def notification_route_mutation(
        self, identity: UIIdentity, operation: str, payload: dict[str, Any]
    ) -> dict[str, Any]:
        return self._invoke(identity, "anima.notification-routes", operation, payload)

    def integration_mutation(
        self, identity: UIIdentity, operation: str, payload: dict[str, Any]
    ) -> dict[str, Any]:
        if operation == "reconnect" and payload.get("plugin_id") == "anima.provider.home-assistant":
            return self._invoke(identity, "anima.provider.home-assistant", "reconnect", {})
        if operation == "setup-zha":
            return self._invoke(identity, "anima.provider.home-assistant", "start_zha_setup", {})
        if operation == "continue-zha":
            return self._invoke(
                identity,
                "anima.provider.home-assistant",
                "continue_zha_setup",
                payload,
            )
        operation_map = {"set-enabled": "set_integration_enabled"}
        name = operation_map.get(operation)
        if name is None:
            raise UICommandError("UNKNOWN_INTEGRATION_OPERATION")
        return self._invoke(identity, CAPABILITY_MANAGEMENT_MANIFEST.plugin_id, name, payload)

    def space_mutation(
        self, identity: UIIdentity, operation: str, payload: dict[str, Any]
    ) -> dict[str, Any]:
        operation_map = {
            "create": "create_space",
            "rename": "rename_space",
            "move": "move_space",
            "remove": "remove_space",
        }
        name = operation_map.get(operation)
        if name is None:
            raise UICommandError("UNKNOWN_SPACE_OPERATION")
        return self._invoke(identity, HOUSEHOLD_SPACES_MANIFEST.plugin_id, name, payload)

    def backup_mutation(
        self, identity: UIIdentity, operation: str, payload: dict[str, Any]
    ) -> dict[str, Any]:
        operation_map = {
            "create": "create_backup",
            "inspect": "inspect_backup",
            "restore": "restore_backup",
        }
        name = operation_map.get(operation)
        if name is None:
            raise UICommandError("UNKNOWN_BACKUP_OPERATION")
        # Household scope is carried in the trusted InvocationContext.  The
        # browser may identify a backup to inspect, but never its household.
        return self._invoke(identity, BACKUP_MANIFEST.plugin_id, name, payload)

    def scene_mutation(
        self, identity: UIIdentity, operation: str, payload: dict[str, Any]
    ) -> dict[str, Any]:
        operation_map = {"create": "create_scene", "update": "update_scene"}
        name = operation_map.get(operation)
        if name is None:
            raise UICommandError("UNKNOWN_SCENE_OPERATION")
        return self._invoke(identity, SCENES_MANIFEST.plugin_id, name, payload)

    def automation_mutation(
        self, identity: UIIdentity, operation: str, payload: dict[str, Any]
    ) -> dict[str, Any]:
        operation_map = {"create": "create_automation", "update": "update_automation"}
        name = operation_map.get(operation)
        if name is None:
            raise UICommandError("UNKNOWN_AUTOMATION_OPERATION")
        return self._invoke(identity, AUTOMATIONS_MANIFEST.plugin_id, name, payload)

    def family_routine_mutation(
        self, identity: UIIdentity, operation: str, payload: dict[str, Any]
    ) -> dict[str, Any]:
        if operation not in {"create", "update", "disable", "retract", "add-member"}:
            raise UICommandError("UNKNOWN_ROUTINE_OPERATION")
        return self._invoke(
            identity,
            FAMILY_ROUTINES_MANIFEST.plugin_id,
            "add_member" if operation == "add-member" else f"{operation}_routine",
            payload,
        )

    def knowledge_operation(
        self, identity: UIIdentity, name: str, payload: dict[str, Any]
    ) -> dict[str, Any]:
        if name not in {tool["name"] for tool in KNOWLEDGE_MANIFEST.tools}:
            raise UICommandError("UNKNOWN_KNOWLEDGE_OPERATION")
        return self._invoke(identity, KNOWLEDGE_MANIFEST.plugin_id, name, payload)

    def learning_operation(
        self, identity: UIIdentity, name: str, payload: dict[str, Any]
    ) -> dict[str, Any]:
        if name not in {"configure", "review"}:
            raise UICommandError("UNKNOWN_LEARNING_OPERATION")
        return self._invoke(identity, HOUSEHOLD_LEARNING_MANIFEST.plugin_id, name, payload)

    def presence_operation(
        self, identity: UIIdentity, name: str, payload: dict[str, Any]
    ) -> dict[str, Any]:
        if name not in {"snapshot", "list_sources", "bind_source"}:
            raise UICommandError("UNKNOWN_PRESENCE_OPERATION")
        return self._invoke(identity, HOUSEHOLD_PRESENCE_MANIFEST.plugin_id, name, payload)

    def presence_candidates(self, identity: UIIdentity) -> dict[str, Any]:
        """Read owner-only setup candidates without exposing provider identifiers."""
        role = self._policy_context(identity).principal_role
        if role != "owner":
            return {"status": "DENIED", "items": []}
        if self.home_assistant_adapter is None:
            return {"status": "UNAVAILABLE", "items": []}
        return {
            "status": "AVAILABLE",
            "items": self.home_assistant_adapter.public_presence_candidates(),
        }

    def commission_presence(self, identity: UIIdentity, payload: dict[str, Any]) -> dict[str, Any]:
        return self._invoke(
            identity,
            "anima.provider.home-assistant",
            "commission_presence_source",
            payload,
        )

    def preference_mutation(
        self, identity: UIIdentity, operation: str, payload: dict[str, Any]
    ) -> dict[str, Any]:
        if operation not in {"create", "update", "retract"}:
            raise UICommandError("UNKNOWN_PREFERENCE_OPERATION")
        return self._invoke(
            identity,
            PREFERENCES_MANIFEST.plugin_id,
            f"{operation}_preference",
            payload,
        )

    def user_mutation(
        self, identity: UIIdentity, operation: str, payload: dict[str, Any]
    ) -> dict[str, Any]:
        name = {"create": "create_user", "update": "update_user"}.get(operation)
        if name is not None:
            return self._invoke(identity, HOUSEHOLD_USERS_MANIFEST.plugin_id, name, payload)
        face_actions = {
            "face-start": "start",
            "face-capture": "capture",
            "face-remove-sample": "remove_sample",
            "face-commit": "commit",
            "face-cancel": "cancel",
            "face-delete": "delete",
        }
        action = face_actions.get(operation)
        if action is None:
            raise UICommandError("UNKNOWN_USER_OPERATION")
        if self.household_graph is None or self.sentry_identity_profiles is None:
            raise UICommandError("SENTRY_FACE_ENROLLMENT_UNAVAILABLE")
        try:
            person_id = UUID(str(payload.get("person_id", "")))
        except ValueError as exc:
            raise UICommandError("INVALID_USER") from exc
        people = {
            item.canonical_id: item
            for item in self.household_graph.members_of_household(identity.household_id)
        }
        person = people.get(person_id)
        if person is None:
            raise UICommandError("HOUSEHOLD_USER_NOT_FOUND")
        authorized = self._invoke(
            identity,
            HOUSEHOLD_USERS_MANIFEST.plugin_id,
            "authorize_face_profile",
            {"person_id": str(person_id), "action": action},
        )
        if authorized.get("status") != "SUCCEEDED":
            return authorized
        try:
            if action == "start":
                result = self.sentry_identity_profiles.start(str(person_id), person.name)
            elif action == "capture":
                result = self.sentry_identity_profiles.capture(
                    str(person_id), str(payload.get("session_id", "")), str(payload.get("pose", ""))
                )
            elif action == "remove_sample":
                result = self.sentry_identity_profiles.remove_sample(
                    str(person_id),
                    str(payload.get("session_id", "")),
                    str(payload.get("sample_id", "")),
                )
            elif action == "commit":
                result = self.sentry_identity_profiles.commit(
                    str(person_id), str(payload.get("session_id", ""))
                )
                person = self.household_graph.update_person_profile(
                    identity.household_id,
                    person_id,
                    sentry_profile_id=str(result["person_id"]),
                    sentry_profile_sample_count=int(result["accepted_samples"]),
                    onboarding_state="ACTIVE",
                )
                result["user"] = user_payload(person)
            elif action == "cancel":
                result = self.sentry_identity_profiles.cancel(
                    str(person_id), str(payload.get("session_id", ""))
                )
            else:
                result = self.sentry_identity_profiles.delete(str(person_id))
                person = self.household_graph.update_person_profile(
                    identity.household_id,
                    person_id,
                    onboarding_state="REVOKED",
                    clear_sentry_profile=True,
                )
                result["user"] = user_payload(person)
        except (KeyError, TypeError, ValueError, SentryIdentityProfileError) as exc:
            raise UICommandError(str(exc) or "SENTRY_FACE_ENROLLMENT_FAILED") from exc
        if self.events and action in {"commit", "delete"}:
            self.events.publish("household.changed")
        return {
            "status": "SUCCEEDED",
            "operation": f"household-user.face-{action.replace('_', '-')}",
            "result": result,
        }

    def apply_scene(self, identity: UIIdentity, scene_id: str) -> dict[str, Any]:
        """Apply a preset through the existing verified single-device action path.

        Scenes are deliberately not a raw HA batch service.  Each step is an
        ordinary Core control with its own policy, lock, fresh observation, and
        terminal result.  A later non-success therefore stops the sequence and
        is surfaced as PARTIAL/that governed outcome rather than hidden.
        """
        if self.scene_store is None:
            raise UICommandError("CORE_SCENE_STORE_UNAVAILABLE")
        try:
            scene = self.scene_store.get(identity.household_id, UUID(scene_id))
        except (ValueError, SceneError) as exc:
            raise UICommandError("SCENE_NOT_FOUND") from exc
        if not scene.enabled:
            return {"status": "FAILED", "operation": "scene.apply", "detail": "scene is disabled"}
        results: list[dict[str, Any]] = []
        for index, step in enumerate(scene.steps, start=1):
            result = self.control(
                identity,
                str(step.resource_id),
                {"desired_on": step.desired_on},
            )
            results.append({"step": index, "resource_id": str(step.resource_id), **result})
            if result.get("status") != "SUCCEEDED":
                status = result.get("status", "UNKNOWN_RESULT")
                return {
                    "status": "PARTIAL" if index > 1 else status,
                    "operation": "scene.apply",
                    "detail": f"scene stopped at step {index}",
                    "result": {"scene_id": str(scene.scene_id), "steps": results},
                }
        return {
            "status": "SUCCEEDED",
            "operation": "scene.apply",
            "detail": f"applied {len(results)} verified scene step(s)",
            "result": {"scene_id": str(scene.scene_id), "steps": results},
        }

    def device_inventory(self, identity: UIIdentity) -> dict[str, Any]:
        """Return the bounded, already-discovered HA registry for this household."""
        plugin = self._tool("anima.provider.home-assistant", "refresh_inventory")
        if self.home_assistant_adapter is None or plugin is None or not plugin.availability:
            return {
                "status": "UNAVAILABLE",
                "items": [],
                "reason": "HOME_ASSISTANT_NOT_COMMISSIONED",
            }
        items: list[dict[str, Any]] = []
        graph = self.home_assistant_adapter.graph
        truth = getattr(self.home_assistant_adapter.reality, "projection", None)
        if not callable(getattr(truth, "get", None)):
            truth = None

        provider_inventory = self.home_assistant_adapter.provider_inventory()
        devices_with_entities = {
            str(dict(item.get("metadata") or {}).get("device_id"))
            for item in provider_inventory
            if item.get("external_object_kind") == "entity"
            and bool(item.get("present"))
            and dict(item.get("metadata") or {}).get("device_id")
        }
        for item in provider_inventory:
            if item.get("external_object_kind") != "device":
                continue
            metadata = dict(item.get("metadata") or {})
            external_id = str(item.get("external_id", ""))
            # HA's device registry also contains software services such as Sun,
            # Forecast, Google Translate TTS and Backup.  They remain available
            # to their integrations but are not owner-facing household devices.
            if str(metadata.get("entry_type", "")).casefold() == "service":
                continue
            canonical_target = None
            canonical_value = metadata.get("canonical_target_id")
            connection_types = {
                str(value).casefold()
                for value in metadata.get("connection_types", [])
                if isinstance(value, str)
            }
            # A host Bluetooth controller with no entities is integration
            # infrastructure even if an older commissioning pass mapped it.
            # Preserve that mapping internally, but keep it off the household
            # device page. Real Bluetooth devices expose at least one entity;
            # other coordinators such as the Zigbee Hub remain visible.
            if external_id not in devices_with_entities and "bluetooth" in connection_types:
                continue
            if canonical_value:
                try:
                    canonical_target = graph.get_node(UUID(str(canonical_value)))
                except (TypeError, ValueError):
                    canonical_target = None
            mapped = canonical_target is not None and item.get("present") is True
            mapped_metadata: dict[str, Any]
            if mapped and canonical_target is not None:
                mapped_metadata = {
                    "name": canonical_target.name,
                    "mapping_status": "MAPPED",
                    "canonical_target_id": str(canonical_target.canonical_id),
                }
            else:
                mapped_metadata = {
                    "mapping_status": "UNMAPPED",
                    "canonical_target_id": None,
                }
            capabilities: list[dict[str, Any]] = []
            device_state = {"truth_status": "UNKNOWN", "state": "UNKNOWN", "observed_at": None}
            if mapped and canonical_target is not None:
                capabilities, device_state = device_capability_projection(
                    graph,
                    truth,
                    canonical_target.canonical_id,
                )
            items.append(
                {
                    "external_object_kind": str(item.get("external_object_kind", "")),
                    "device_handle": inventory_handle(
                        self.home_assistant_adapter.config.instance_id,
                        str(item.get("external_object_kind", "")),
                        str(item.get("external_id", "")),
                    ),
                    "present": bool(item.get("present")),
                    "metadata": {
                        key: metadata[key]
                        for key in (
                            "name_by_user",
                            "name",
                            "manufacturer",
                            "model",
                            "is_child_device",
                        )
                        if key in metadata
                    }
                    | mapped_metadata,
                    **device_state,
                    "capabilities": capabilities,
                }
            )
        # Some supported household devices are event-only integrations rather
        # than HA registry devices (for example the private Tapo and Wansview
        # notification bridges).  They are still canonical ANIMA resources and
        # belong in the owner's device catalogue.  Add only commissioned graph
        # resources that were not already projected from HA; provider details
        # remain bounded metadata and never expose credentials or raw events.
        represented = {
            str(item["metadata"].get("canonical_target_id"))
            for item in items
            if item["metadata"].get("canonical_target_id")
        }
        list_resources = getattr(graph, "resources_in_place", None)
        household_id = getattr(identity, "household_id", None)
        canonical_resources = (
            list_resources(household_id)
            if callable(list_resources) and household_id is not None
            else []
        )
        for resource in canonical_resources:
            resource_id = str(resource.canonical_id)
            if resource_id in represented:
                continue
            references_for = getattr(graph, "provider_references_for", None)
            references = [
                item
                for item in (
                    references_for(resource.canonical_id) if callable(references_for) else []
                )
                if item.provider in {"android_notification", "owner-waydroid"}
            ]
            if not references:
                continue
            reference = references[0]
            capabilities, device_state = device_capability_projection(
                graph, truth, resource.canonical_id
            )
            provider_label = {
                "android_notification": "Private Android relay",
                "owner-waydroid": "Private Android relay",
                "home-assistant": "Home Assistant",
            }.get(reference.provider, reference.provider.replace("-", " ").title())
            items.append(
                {
                    "external_object_kind": "device",
                    "device_handle": f"canonical:{resource_id}",
                    "canonical_name": resource.name,
                    "present": True,
                    "metadata": {
                        "name": resource.name,
                        "manufacturer": resource.metadata.get("manufacturer") or provider_label,
                        "model": resource.metadata.get("model"),
                        "mapping_status": "MAPPED",
                        "canonical_target_id": resource_id,
                        "integration": reference.provider,
                        "source_kind": reference.external_object_kind,
                    },
                    **device_state,
                    "capabilities": capabilities,
                }
            )
        return {"status": "AVAILABLE", "items": items}

    def device_mutation(
        self, identity: UIIdentity, operation: str, payload: dict[str, Any]
    ) -> dict[str, Any]:
        operation_map = {
            "refresh": "refresh_inventory",
            "permit-pairing": "permit_zigbee_join",
            "commission": "commission_device",
            "rename": "rename_device",
            "reassign": "reassign_device",
            "retire": "retire_device",
        }
        name = operation_map.get(operation)
        if name is None:
            raise UICommandError("UNKNOWN_DEVICE_OPERATION")
        if operation == "commission":
            handle = str(payload.get("device_handle", ""))
            if not handle or self.home_assistant_adapter is None:
                raise UICommandError("DEVICE_HANDLE_REQUIRED")
            if self.home_assistant_adapter.resolve_device_handle(handle) is None:
                raise UICommandError("UNKNOWN_DEVICE_HANDLE")
        return self._invoke(identity, "anima.provider.home-assistant", name, payload)

    def control(
        self, identity: UIIdentity, control_id: str, payload: dict[str, Any]
    ) -> dict[str, Any]:
        if self.action_executor is None:
            raise UICommandError("CORE_ACTION_EXECUTOR_UNAVAILABLE")
        try:
            resource_id = UUID(control_id)
        except ValueError as exc:
            raise UICommandError("CONTROL_RESOURCE_REFERENCE_REQUIRED") from exc
        tool = self._tool("anima.provider.home-assistant", "set_power")
        if tool is None or not tool.availability:
            raise UICommandError("CORE_TOOL_UNAVAILABLE:anima.provider.home-assistant.set_power")
        # The canonical resource is server-owned; the browser supplies only
        # the semantic desired state required by the commissioned tool.
        arguments = {**payload, "resource_id": str(resource_id)}
        if self.control_capability_resolver is not None:
            capability_id = self.control_capability_resolver(resource_id)
            if capability_id is not None:
                arguments["capability_id"] = str(capability_id)
        request = ActionRequest.create(
            idempotency_key=f"ui-control:{identity.household_id}:{uuid4()}",
            household_id=identity.household_id,
            tool=tool,
            arguments=arguments,
            identity=_identity(identity),
            policy_service=self.policy_service,
            policy_context=self._policy_context(identity),
            refresher=self.action_refresher,
            verifier=self.action_verifier,
            origin=RequestOrigin.DIRECT_USER,
            safety_spec=resolve_action_safety_spec(tool),
        )
        execution = self.action_executor.execute(request)
        if self.events:
            self.events.publish("home.invalidated")
        return _safe_action_result(execution, tool.tool_id)

    def confirmation(self, identity: UIIdentity, approval_id: str, decision: str) -> dict[str, Any]:
        if self.action_executor is None or self.action_executor.pending_approvals is None:
            raise UICommandError("CORE_CONFIRMATION_UNAVAILABLE")
        try:
            approval_uuid = UUID(approval_id)
        except ValueError as exc:
            raise UICommandError("INVALID_APPROVAL_ID") from exc
        pending = self.action_executor.pending_approvals.get(approval_uuid)
        if pending is None or pending.household_id != identity.household_id:
            raise UICommandError("APPROVAL_NOT_FOUND")
        tool = self._tool_by_id(pending.tool_id)
        if tool is None or not tool.availability:
            raise UICommandError(f"CORE_TOOL_UNAVAILABLE:{pending.tool_id}")
        choice = decision.upper()
        if self.agent is not None:
            resumed = self.agent.resume_confirmation(
                approval_uuid,
                identity=_identity(identity),
                decision=choice,
                policy_context=self._policy_context(identity),
                tool_resolver=self._tool_by_id,
                tools=tuple(self.manager.list_tools()),
                policy_service=self.policy_service,
                action_refresher=self.action_refresher,
                action_verifier=self.action_verifier,
            )
            if resumed is None:
                raise UICommandError("APPROVAL_NOT_ACTIONABLE")
            action = self.action_executor.store.get(pending.action_id)
            result = {
                "status": action.status.value if action is not None else "UNKNOWN_RESULT",
                "operation": pending.tool_id,
                "episode_id": str(resumed.episode.episode_id),
                "detail": resumed.episode.failure_class or resumed.episode.response_text,
                "response": resumed.live_response_text or resumed.episode.response_text,
                "episode_status": resumed.episode.status.value,
                "episode_disposition": (
                    resumed.episode.final_disposition.value
                    if resumed.episode.final_disposition
                    else "UNKNOWN"
                ),
            }
        else:
            execution = self.action_executor.approve_pending(
                approval_uuid,
                household_id=identity.household_id,
                principal_id=identity.principal_id,
                decision=choice,
                tool=tool,
                policy_service=self.policy_service,
                policy_context=self._policy_context(identity),
                refresher=self.action_refresher,
                verifier=self.action_verifier,
                origin=RequestOrigin.DIRECT_USER,
            )
            if execution is None:
                raise UICommandError("APPROVAL_NOT_ACTIONABLE")
            result = _safe_action_result(execution, pending.tool_id)
        action = self.action_executor.store.get(pending.action_id)
        result = _safe_confirmation_result(
            result,
            decision=choice,
            approval_status="REJECTED" if choice == "REJECT" else "APPROVED",
            action_status=action.status.value if action is not None else "UNKNOWN_RESULT",
        )
        if self.events:
            self.events.publish("home.invalidated")
        return result


class CoreConversationPipeline:
    """Drive a direct UI event through Attention, Context, and AgentRuntime."""

    def __init__(
        self,
        *,
        attention: Any,
        context: Any,
        agent: AgentRuntime,
        policy_service: PolicyService,
        tools: Callable[[], list[Any]],
        journal: PostgresEventJournal | None = None,
        profile: AttentionProfile | None = None,
        consumer_name: str = "ui-conversation",
        action_refresher: Callable[[tuple[UUID, ...]], Any] | None = None,
        action_verifier: Callable[[Any, InvocationResult, Any], Any] | None = None,
        policy_role_resolver: Callable[[UUID], str | None] | None = None,
    ) -> None:
        self.attention = attention
        self.context = context
        self.agent = agent
        self.policy_service = policy_service
        self.tools = tools
        self.journal = journal
        self.profile = profile or default_attention_profile("phase12.ui.v1")
        self.consumer_name = consumer_name
        self.action_refresher = action_refresher
        self.action_verifier = action_verifier
        self.policy_role_resolver = policy_role_resolver

    def _trigger(self, event: EventEnvelope) -> Any:
        candidates = [
            item
            for item in self.attention.list_triggers(self.profile.profile_version)
            if event.event_id in item.source_event_ids
        ]
        if not candidates:
            raise UICommandError("CONVERSATION_TRIGGER_UNAVAILABLE")
        return max(candidates, key=lambda item: item.created_at)

    def run(self, identity: UIIdentity, event: EventEnvelope) -> dict[str, Any]:
        consumer_name = self.consumer_name
        if self.journal is not None and callable(
            getattr(self.attention, "prime_consumer_before", None)
        ):
            position = self.journal.position(event.event_id)
            if position is not None:
                consumer_name = f"{self.consumer_name}:{event.event_id}"
                self.attention.prime_consumer_before(self.profile, consumer_name, position - 1)
        result = self.attention.process(self.profile, consumer_name=consumer_name)
        if result.failure:
            raise UICommandError("CONVERSATION_ATTENTION_UNAVAILABLE")
        trigger = self._trigger(event)
        packet = self.context.assemble(
            trigger,
            household_id=identity.household_id,
            tools=self.tools(),
            persist=True,
        )
        run: EpisodeRunResult = self.agent.run(
            EpisodeRequest(
                trigger_id=trigger.trigger_id,
                context_packet_id=packet.context_packet_id,
                household_id=identity.household_id,
                context_packet=packet.to_payload(),
                tools=tuple(self.tools()),
                identity=_identity(identity),
                policy_service=self.policy_service,
                policy_context=PolicyContext(
                    principal_role=(
                        self.policy_role_resolver(identity.principal_id)
                        if self.policy_role_resolver is not None
                        else None
                    )
                ),
                origin=RequestOrigin.DIRECT_USER,
                action_refresher=self.action_refresher,
                action_verifier=self.action_verifier,
            )
        )
        response = run.live_response_text or run.episode.response_text
        if response.startswith("[CONTENT_NOT_DURABLY_RETAINED]"):
            response = "Anima completed the request; the response was not retained durably."
        return {
            "response": response,
            "disposition": run.episode.final_disposition.value
            if run.episode.final_disposition
            else "UNKNOWN",
            "episode_id": str(run.episode.episode_id),
            "trace": {
                "pipeline": "journal_attention_context_agent",
                "event_id": event.event_id,
                "trigger_id": str(trigger.trigger_id),
                "context_packet_id": str(packet.context_packet_id),
                "correlation_id": event.correlation_id,
                "causation_id": event.causation_id,
                "attention_processed": result.processed,
            },
        }


class SentryConversationPipeline:
    """Queue direct UI cognition for the configured SENTRY provider.

    The browser request still creates the canonical journal event and the
    normal Phase 7 ContextPacket.  SENTRY receives the packet only after a
    durable, idempotent ANIMA request is created; there is no embedded-agent
    fallback in this mode.
    """

    def __init__(
        self,
        *,
        attention: Any,
        context: Any,
        journal: Any,
        intelligence: Any,
        tools: Callable[[], list[Any]],
        profile: AttentionProfile | None = None,
        consumer_name: str = "ui-sentry-conversation",
    ) -> None:
        self.attention = attention
        self.context = context
        self.journal = journal
        self.intelligence = intelligence
        self.tools = tools
        self.profile = profile or default_attention_profile("phase13.sentry.v1")
        self.consumer_name = consumer_name

    def run(self, identity: UIIdentity, event: EventEnvelope) -> dict[str, Any]:
        position = self.journal.position(event.event_id)
        if position is None:
            raise UICommandError("CONVERSATION_EVENT_UNAVAILABLE")
        consumer = f"{self.consumer_name}:{event.event_id}"
        self.attention.prime_consumer_before(self.profile, consumer, position - 1)
        processed = self.attention.process(self.profile, consumer_name=consumer)
        if processed.failure:
            raise UICommandError("CONVERSATION_ATTENTION_UNAVAILABLE")
        triggers = [
            item
            for item in self.attention.list_triggers(self.profile.profile_version)
            if event.event_id in item.source_event_ids
        ]
        if not triggers:
            raise UICommandError("CONVERSATION_TRIGGER_UNAVAILABLE")
        trigger = max(triggers, key=lambda item: item.created_at)
        packet = self.context.assemble(
            trigger,
            household_id=identity.household_id,
            tools=self.tools(),
            persist=True,
        )
        request = IntelligenceRequestFactory.for_trigger(
            trigger.trigger_id,
            household_id=identity.household_id,
            origin=IntelligenceOrigin.DIRECT_UI_USER,
            context_packet_id=packet.context_packet_id,
            context_digest=packet.digest,
            tools=self.tools(),
            provider_id="sentry",
            provider_version="1",
            principal_id=identity.principal_id,
            correlation_id=event.correlation_id,
            causation_id=event.event_id,
            metadata={"ui_request_id": event.event_id},
        )
        stored = self.intelligence.enqueue(request)
        return {
            "response": "SENTRY received the request and is reasoning through ANIMA.",
            "disposition": "QUEUED_FOR_SENTRY",
            "request_id": str(stored.request_id),
            "trace": {
                "pipeline": "journal_attention_context_sentry_queue",
                "event_id": event.event_id,
                "trigger_id": str(trigger.trigger_id),
                "context_packet_id": str(packet.context_packet_id),
                "correlation_id": event.correlation_id,
                "causation_id": event.causation_id,
                "attention_processed": processed.processed,
            },
        }


@dataclass(slots=True)
class CoreRuntime:
    """Already-constructed accepted Core dependencies for UI composition."""

    journal: PostgresEventJournal
    attention: PostgresAttentionService
    context: ContextBroker
    policy_service: PolicyService
    agent: AgentRuntime
    plugins: PluginManager
    action_executor: ActionExecutionCoordinator
    graph: PostgresHouseholdGraph
    truth: PostgresRealityStore
    identity_resolver: CommissionedIdentityResolver
    action_refresher: Callable[[tuple[UUID, ...]], Any] | None = None
    action_verifier: Callable[[Any, InvocationResult, Any], Any] | None = None
    intelligence_store: PostgresIntelligenceStore | None = None
    intelligence_provider: IntelligenceProviderMode = IntelligenceProviderMode.EMBEDDED_REFERENCE
    home_assistant_adapter: HomeAssistantAdapter | None = None
    alert_policy_store: PostgresSenseGuardAlertPolicyStore | None = None
    notification_route_store: PostgresNotificationRouteStore | None = None
    backup_coordinator: BackupCoordinator | None = None
    scene_store: PostgresSceneStore | None = None
    automation_store: PostgresAutomationStore | None = None
    memory_service: Any | None = None
    learning_service: Any | None = None
    initiative_context: Any | None = None

    def conversation(self, events: UIEventBroadcaster) -> CoreConversationPipeline:
        if self.intelligence_provider == IntelligenceProviderMode.SENTRY:
            if self.intelligence_store is None:
                raise UICommandError("SENTRY_INTELLIGENCE_STORE_UNAVAILABLE")
            return SentryConversationPipeline(
                attention=self.attention,
                context=self.context,
                journal=self.journal,
                intelligence=self.intelligence_store,
                tools=self.plugins.list_tools,
            )  # type: ignore[return-value]
        return CoreConversationPipeline(
            attention=self.attention,
            context=self.context,
            agent=self.agent,
            policy_service=self.policy_service,
            tools=self.plugins.list_tools,
            journal=self.journal,
            action_refresher=self.action_refresher,
            action_verifier=self.action_verifier,
            policy_role_resolver=self.identity_resolver.resolve_role,
        )

    def commands(self, events: UIEventBroadcaster) -> CoreUICommandGateway:
        def resolve_power_capability(resource_id: UUID) -> UUID | None:
            for capability in self.graph.resource_capabilities(resource_id):
                capability_type = str(capability.metadata.get("capability_type", ""))
                if capability_type.startswith("power."):
                    return capability.canonical_id
            return None

        return CoreUICommandGateway(
            self.plugins,
            self.policy_service,
            events=events,
            action_executor=self.action_executor,
            action_refresher=self.action_refresher,
            action_verifier=self.action_verifier,
            policy_role_resolver=self.identity_resolver.resolve_role,
            control_capability_resolver=resolve_power_capability,
            agent=self.agent,
            home_assistant_adapter=self.home_assistant_adapter,
            scene_store=self.scene_store,
            automation_store=self.automation_store,
            household_graph=self.graph,
            sentry_identity_profiles=SentryIdentityProfileClient.from_environment(),
        )

    def sentry_boundary(self) -> CoreSentryBoundary:
        from anima_ha.household_reasoning import household_reasoning_context

        if self.intelligence_store is None:
            raise UICommandError("SENTRY_INTELLIGENCE_STORE_UNAVAILABLE")
        return CoreSentryBoundary(
            manager=self.plugins,
            policy_service=self.policy_service,
            intelligence_store=self.intelligence_store,
            action_executor=self.action_executor,
            action_refresher=self.action_refresher,
            action_verifier=self.action_verifier,
            context_loader=lambda trigger_id: self.context.load(trigger_id),
            reasoning_context_loader=lambda request: household_reasoning_context(
                request, self.memory_service, self.graph, initiative=self.initiative_context
            ),
            policy_role_resolver=self.identity_resolver.resolve_role,
            access_level_resolver=self.identity_resolver.resolve_access_level,
            agent_memory_enabled=os.environ.get("ANIMA_SENTRY_AGENT_MEMORY", "").lower() == "true",
            learning_service=self.learning_service,
        )


class PostgresCommissionedIdentityResolver:
    """Resolve HA identities through commissioned graph provider references."""

    def __init__(self, graph: Any, provider_scope: str) -> None:
        self.graph = graph
        self.provider_scope = provider_scope

    def _resolve_person(self, ha_user_id: str) -> tuple[UUID, UUID]:
        targets = self.graph.resolve_provider_references(
            "home_assistant", self.provider_scope, "user", ha_user_id
        )
        if not targets:
            raise PrincipalMappingRequired("PRINCIPAL_MAPPING_REQUIRED")
        if len(targets) != 1 or targets[0].kind != NodeKind.PERSON:
            raise PrincipalMappingConflict("PRINCIPAL_MAPPING_CONFLICT")
        households = self.graph.households_for_member(targets[0].canonical_id)
        if not households:
            raise PrincipalMappingRequired("PRINCIPAL_MAPPING_REQUIRED")
        if len(households) != 1:
            raise PrincipalMappingConflict("PRINCIPAL_MAPPING_CONFLICT")
        return households[0].canonical_id, targets[0].canonical_id

    def resolve_ha_user(self, ha_user_id: str) -> tuple[UUID, UUID]:
        return self._resolve_person(ha_user_id)

    def resolve_principal(self, principal_id: UUID) -> tuple[UUID, UUID, str | None]:
        person = self.graph.get_node(principal_id)
        if person is None or person.kind != NodeKind.PERSON:
            raise PrincipalMappingRequired("PRINCIPAL_MAPPING_REQUIRED")
        households = self.graph.households_for_member(principal_id)
        if not households:
            raise PrincipalMappingRequired("PRINCIPAL_MAPPING_REQUIRED")
        if len(households) != 1:
            raise PrincipalMappingConflict("PRINCIPAL_MAPPING_CONFLICT")
        references = [
            reference
            for reference in self.graph.provider_references_for(principal_id)
            if reference.provider == "home_assistant"
            and reference.provider_scope == self.provider_scope
            and reference.external_object_kind == "user"
        ]
        if len(references) > 1:
            raise PrincipalMappingConflict("PRINCIPAL_MAPPING_CONFLICT")
        return (
            households[0].canonical_id,
            principal_id,
            references[0].external_id if references else None,
        )

    def resolve_role(self, principal_id: UUID) -> str | None:
        person = self.graph.get_node(principal_id)
        if person is None or person.kind != NodeKind.PERSON:
            raise PrincipalMappingRequired("PRINCIPAL_MAPPING_REQUIRED")
        role = person.metadata.get("semantic_role")
        return role.strip() if isinstance(role, str) and role.strip() else None

    def resolve_access_level(self, principal_id: UUID) -> str:
        person = self.graph.get_node(principal_id)
        if person is None or person.kind != NodeKind.PERSON:
            raise PrincipalMappingRequired("PRINCIPAL_MAPPING_REQUIRED")
        value = str(person.metadata.get("sentry_access", "LIMITED")).strip().upper()
        if value not in {"LIMITED", "UNRESTRICTED"}:
            raise PrincipalMappingRequired("ACCESS_LEVEL_MAPPING_REQUIRED")
        return value


def owner_ha_version() -> str:
    """Explicit deployment pin; discovery still rejects any other version."""
    version = os.environ.get("ANIMA_HA_EXPECTED_VERSION", "2026.8.2").strip()
    if version not in {"2026.8.2", "2026.9.0"}:
        raise ValueError("ANIMA_HA_EXPECTED_VERSION is not a qualified target")
    return version


def _environment_secrets() -> dict[str, str]:
    """Read declared secret references into the in-process broker only."""
    names = (
        "HA_ACCESS_TOKEN",
        "ANIMA_HA_ACCESS_TOKEN",
        "NTFY_TOPIC",
        "NTFY_TOKEN",
        "WALMART_CONSUMER_ID",
        "WALMART_KEY_VERSION",
        "WALMART_PRIVATE_KEY_PATH",
        "BEST_BUY_API_KEY",
    )
    values = {name: os.environ[name] for name in names if os.environ.get(name)}
    from anima_ha.ha_connection_setup import HASetupError, configured_connection

    connection = configured_connection()
    if connection is not None:
        if connection["instance_id"] != os.environ.get("ANIMA_HA_INSTANCE_ID", "") or connection[
            "base_url"
        ] != os.environ.get("ANIMA_HA_BASE_URL", "").rstrip("/"):
            raise HASetupError("HA_CONNECTION_CONFIGURATION_MISMATCH")
        values[os.environ.get("ANIMA_HA_TOKEN_SECRET_NAME", "HA_ACCESS_TOKEN")] = connection[
            "token"
        ]
    return values


def build_postgres_core(
    database_url: str,
    *,
    opa_url: str = "http://127.0.0.1:8181",
    codex: Any | None = None,
    external_transport: Any | None = None,
) -> CoreRuntime:
    """Compose the normal local runtime from accepted Core implementations."""
    journal = PostgresEventJournal(database_url)
    graph = PostgresHouseholdGraph(database_url)
    truth = PostgresRealityStore(database_url)
    secrets = _environment_secrets()
    from anima_ha.plugins import PostgresPluginStore

    plugin_store = PostgresPluginStore(database_url)
    plugins = PluginManager(
        journal=journal, store=plugin_store, secret_broker=SecretBroker(secrets)
    )

    def register_and_enable(
        manifest: Any,
        runtime: Any,
        *,
        configuration: dict[str, Any] | None = None,
        persist_choice: bool = True,
    ) -> None:
        # Persisted enablement is an operator preference for optional
        # integrations.  Required Core capabilities and commissioned HA must
        # be reconstructed from the current composition, not disabled by a
        # stale row left by a previous test or runtime.
        persisted = plugin_store.enabled(manifest.plugin_id) if persist_choice else None
        plugins.register(manifest, runtime, configuration=configuration)
        if persisted is not False:
            plugins.enable(manifest.plugin_id)

    alert_policy_store = PostgresSenseGuardAlertPolicyStore(database_url)
    notification_route_store = PostgresNotificationRouteStore(database_url)
    sentry_voice_settings_store = SentryVoiceSettingsStore(database_url)
    from anima_ha.memory import MemoryService

    memory_service = MemoryService(database_url)
    backup_coordinator = BackupCoordinator(
        database_url,
        os.environ.get("ANIMA_BACKUP_DIR", "/var/lib/anima/backups"),
    )
    scene_store = PostgresSceneStore(database_url)
    automation_store = PostgresAutomationStore(database_url)

    def alert_resource_is_commissioned(household_id: UUID, resource_id: UUID) -> bool:
        node = graph.get_node(resource_id)
        if node is None or node.kind not in {NodeKind.RESOURCE, NodeKind.SENSOR}:
            return False
        return any(
            resource_id == resource.canonical_id
            for place in graph.places_in_household(household_id)
            for resource in graph.resources_in_place(place.canonical_id)
        )

    register_and_enable(
        SENSEGUARD_ALERT_MANIFEST,
        NativeRuntime(
            SenseGuardAlertNativePlugin(
                alert_policy_store,
                resource_validator=alert_resource_is_commissioned,
            )
        ),
        persist_choice=False,
    )
    register_and_enable(
        NOTIFICATION_ROUTE_MANIFEST,
        NativeRuntime(NotificationRouteNativePlugin(notification_route_store)),
        persist_choice=False,
    )
    register_and_enable(
        SENTRY_CONTROL_MANIFEST,
        NativeRuntime(SentryControlNativePlugin(sentry_voice_settings_store)),
        persist_choice=False,
    )
    register_and_enable(
        PREFERENCES_MANIFEST,
        NativeRuntime(PreferencesNativePlugin(memory_service, graph)),
        persist_choice=False,
    )
    register_and_enable(
        FAMILY_ROUTINES_MANIFEST,
        NativeRuntime(FamilyRoutinesNativePlugin(memory_service, graph)),
        persist_choice=False,
    )
    register_and_enable(
        HOUSEHOLD_USERS_MANIFEST,
        NativeRuntime(HouseholdUsersNativePlugin(graph)),
        persist_choice=False,
    )
    register_and_enable(
        VENDOR_EVENTS_MANIFEST,
        NativeRuntime(VendorEventsNativePlugin(PostgresVendorEventStore(database_url, graph))),
        persist_choice=False,
    )
    knowledge_root = os.environ.get("ANIMA_KNOWLEDGE_ROOT", "").strip()
    knowledge_plugin: KnowledgeNativePlugin | None = None
    if knowledge_root:
        knowledge_plugin = KnowledgeNativePlugin(
            KnowledgeConfig.from_environment(),
            person_validator=lambda household, person: any(
                item.canonical_id == person
                and item.kind == NodeKind.PERSON
                and item.retired_at is None
                for item in graph.members_of_household(household)
            ),
        )
        register_and_enable(
            KNOWLEDGE_MANIFEST,
            NativeRuntime(knowledge_plugin),
        )
    task_service = TaskService(PostgresTaskStore(database_url), journal)
    household_evidence = HouseholdEventEvidence(database_url, graph)
    learning_service = HouseholdLearningService(
        memory_service,
        graph,
        journal,
        evidence_reader=household_evidence.recent_household_evidence,
        task_service=task_service,
        knowledge_plugin=knowledge_plugin,
        timezone=os.environ.get("ANIMA_HOUSEHOLD_TIMEZONE", "UTC"),
    )
    register_and_enable(
        HOUSEHOLD_LEARNING_MANIFEST,
        NativeRuntime(HouseholdLearningNativePlugin(learning_service)),
        persist_choice=False,
    )
    calendar_service = CalendarService(PostgresCalendarStore(database_url), journal)
    register_and_enable(
        TASK_MANIFEST, NativeRuntime(TaskNativePlugin(task_service)), persist_choice=False
    )
    register_and_enable(
        CALENDAR_MANIFEST,
        NativeRuntime(CalendarNativePlugin(calendar_service)),
        persist_choice=False,
    )
    register_and_enable(
        HOUSEHOLD_SPACES_MANIFEST,
        NativeRuntime(HouseholdSpacesNativePlugin(graph)),
        persist_choice=False,
    )
    register_and_enable(
        BACKUP_MANIFEST,
        NativeRuntime(BackupNativePlugin(backup_coordinator)),
        persist_choice=False,
    )

    def scene_resource_is_commissioned(household_id: UUID, resource_id: UUID) -> bool:
        node = graph.get_node(resource_id)
        if node is None or node.kind not in {NodeKind.RESOURCE, NodeKind.SENSOR}:
            return False
        if not any(
            resource_id == resource.canonical_id
            for place in graph.places_in_household(household_id)
            for resource in graph.resources_in_place(place.canonical_id)
        ):
            return False
        return any(
            str(capability.metadata.get("capability_type", "")).startswith("power.")
            for capability in graph.resource_capabilities(resource_id)
        )

    register_and_enable(
        SCENES_MANIFEST,
        NativeRuntime(SceneNativePlugin(scene_store, scene_resource_is_commissioned)),
        persist_choice=False,
    )

    def automation_resource_is_commissioned(household_id: UUID, resource_id: UUID) -> bool:
        node = graph.get_node(resource_id)
        if node is None or node.kind != NodeKind.RESOURCE:
            return False
        if not any(
            resource_id == resource.canonical_id
            for place in graph.places_in_household(household_id)
            for resource in graph.resources_in_place(place.canonical_id)
        ):
            return False
        return any(
            str(capability.metadata.get("capability_type", "")).startswith("power.")
            for capability in graph.resource_capabilities(resource_id)
        )

    register_and_enable(
        AUTOMATIONS_MANIFEST,
        NativeRuntime(
            AutomationNativePlugin(automation_store, automation_resource_is_commissioned)
        ),
        persist_choice=False,
    )

    # These are the qualified Phase 11 portfolio providers. Provider identity
    # is composition-owned; no model argument can select a host or credential.
    for plugin_id in (
        "anima.external.weather",
        "anima.external.discovery",
        "anima.external.shopping.upcitemdb",
        "anima.external.recipes",
    ):
        manifest, plugin_runtime = external_plugin(
            plugin_id,
            audit_sink=ExternalAuditJournalSink(journal),
            transport=external_transport,
            searxng_url=os.environ.get("ANIMA_SEARXNG_URL", "http://searxng:8080"),
            searxng_host=os.environ.get("ANIMA_SEARXNG_HOST", "searxng"),
            overpass_url=os.environ.get("ANIMA_OVERPASS_URL", "https://overpass-api.de"),
        )
        register_and_enable(manifest, NativeRuntime(plugin_runtime))
    if secrets.get("NTFY_TOPIC"):
        manifest, plugin_runtime = external_plugin(
            "anima.external.notifications",
            audit_sink=ExternalAuditJournalSink(journal),
            transport=external_transport,
        )
        register_and_enable(manifest, NativeRuntime(plugin_runtime))

    # HA is commissioned only when the operator has supplied the instance
    # identity, websocket endpoint, and the already-established secret ref.
    # Otherwise the capability remains unavailable and authentication maps no
    # user to a synthetic household.
    websocket_url = os.environ.get("ANIMA_HA_WEBSOCKET_URL", "").strip()
    instance_value = os.environ.get("ANIMA_HA_INSTANCE_ID", "").strip()
    provider_scope = os.environ.get("ANIMA_HA_PROVIDER_SCOPE", instance_value).strip()
    token_secret_name = os.environ.get("ANIMA_HA_TOKEN_SECRET_NAME", "HA_ACCESS_TOKEN").strip()
    ha_adapter: HomeAssistantAdapter | None = None
    if provider_scope and websocket_url and instance_value and secrets.get(token_secret_name):
        instance_id = UUID(instance_value)
        if provider_scope != str(instance_id):
            raise ValueError("ANIMA_HA_PROVIDER_SCOPE must equal ANIMA_HA_INSTANCE_ID")
        ha_config = HAInstanceConfig(
            instance_id,
            websocket_url,
            token_secret_name,
            expected_version=owner_ha_version(),
            ssl=websocket_url.lower().startswith("wss://"),
        )
        ha_adapter = HomeAssistantAdapter(ha_config, truth, graph, PostgresHAStore(database_url))
        manifest = home_assistant_manifest(ha_config)
        ha_runtime = HomeAssistantPlugin(
            ha_adapter,
            lambda token: HassClientConnection(
                ha_config,
                token,
                event_callback=ha_adapter.receive_provider_event,
                disconnect_callback=ha_adapter.disconnected,
            ),
        )
        register_and_enable(
            manifest,
            NativeRuntime(ha_runtime),
            configuration={"instance_id": str(instance_id), "websocket_url": websocket_url},
            persist_choice=False,
        )

    register_and_enable(
        CAPABILITY_MANAGEMENT_MANIFEST,
        NativeRuntime(CapabilityManagementNativePlugin(plugins)),
        persist_choice=False,
    )

    policy_service = PolicyService(
        OpaPolicyClient(opa_url), audit_store=PostgresPolicyStore(database_url)
    )
    action_executor = ActionExecutionCoordinator(
        plugins,
        PostgresActionStore(database_url),
        PostgresResourceLocker(database_url),
        journal=journal,
        pending_approvals=PostgresPendingApprovalStore(database_url),
    )
    agent = AgentRuntime(
        codex or CodexCliRuntime(),
        plugins,
        PostgresEpisodeStore(database_url),
        journal=journal,
        action_executor=action_executor,
    )
    identity_resolver = PostgresCommissionedIdentityResolver(graph, provider_scope)
    intelligence_provider = IntelligenceProviderMode(
        os.environ.get("ANIMA_INTELLIGENCE_PROVIDER", "embedded_reference").strip()
    )
    intelligence_store = PostgresIntelligenceStore(database_url)

    def refresh(resources: tuple[UUID, ...]) -> Any:
        from anima_ha.action import TruthSnapshot

        if ha_adapter is None:
            return TruthSnapshot()
        values: dict[str, dict[str, Any]] = {}
        for resource_id in resources:
            capability_id = next(
                (
                    capability.canonical_id
                    for capability in graph.resource_capabilities(resource_id)
                    if str(capability.metadata.get("capability_type", "")).startswith("power.")
                ),
                None,
            )
            state = ha_adapter.read_state(resource_id, capability_id)
            values[str(state["truth_key"])] = {
                "state": "KNOWN",
                "value": state.get("state"),
                "observed_at": state.get("observed_at"),
            }
        return TruthSnapshot(values)

    action_refresher = refresh if ha_adapter is not None else None
    attention = PostgresAttentionService(database_url)
    context = ContextBroker(database_url)
    runtime = CoreRuntime(
        journal,
        attention,
        context,
        policy_service,
        agent,
        plugins,
        action_executor,
        graph,
        truth,
        identity_resolver,
        action_refresher,
        None,
        intelligence_store,
        intelligence_provider,
        ha_adapter,
        alert_policy_store,
        notification_route_store,
        backup_coordinator,
        scene_store,
        automation_store,
        memory_service,
    )
    household_value = (
        os.environ.get("ANIMA_HOUSEHOLD_ID", "").strip()
        or os.environ.get("ANIMA_SENTRY_HOUSEHOLD_ID", "").strip()
    )
    if not household_value:
        from anima_ha.ha_connection_setup import configured_connection

        owner_connection = configured_connection()
        if owner_connection is not None:
            household_value = str(owner_connection["household_id"])
    runtime.learning_service = learning_service
    initiative_context = HouseholdInitiativeContext(
        database_url, learning_service, household_evidence
    )
    runtime.initiative_context = initiative_context
    if ha_adapter is not None and household_value and intelligence_store is not None:
        household_id = UUID(household_value)

        def classify_presence_source(reference: ProviderReference) -> SignalKind | None:
            # HA's configured home zone and router association belong to this
            # commissioned household instance. Nothing is supplied by SENTRY.
            if reference.provider_scope != provider_scope or ha_adapter is None:
                return None
            connection = ha_adapter.connection
            if connection is None or not connection.connected:
                return None
            if reference.external_id.startswith("person."):
                return (
                    SignalKind.HA_PERSON
                    if isinstance(connection.get_state(reference.external_id), dict)
                    else None
                )
            if not reference.external_id.startswith("device_tracker."):
                return None
            read_kind = getattr(connection, "presence_source_kind", None)
            if not callable(read_kind):
                return None
            kind = read_kind(reference.external_id)
            return (
                {"gps": SignalKind.GEOFENCE, "router": SignalKind.ROUTER_WIFI}.get(kind)
                if isinstance(kind, str)
                else None
            )

        presence_service = HouseholdPresenceService(
            graph, truth.projection, classify_source=classify_presence_source
        )
        register_and_enable(
            HOUSEHOLD_PRESENCE_MANIFEST,
            NativeRuntime(
                HouseholdPresenceNativePlugin(presence_service, ha_adapter.config.instance_id)
            ),
        )

        def resolve_resource(external_id: str) -> UUID | None:
            return _resolve_ha_event_resource(graph, provider_scope, household_id, external_id)

        def dispatch_attention_event(alert: EventEnvelope, journal_position: int) -> None:
            _dispatch_senseguard_attention(
                alert=alert,
                journal_position=journal_position,
                household_id=household_id,
                attention=attention,
                context=context,
                store=intelligence_store,
                tools=plugins.list_tools(),
                event_path_resolver=initiative_context.resolve_event_path,
            )

        def resource_name(resource_id: UUID) -> str | None:
            resource = graph.get_node(resource_id)
            return resource.name if resource is not None else None

        notification_dispatcher = SenseGuardNotificationDispatcher(
            route_store=notification_route_store,
            manager=plugins,
            policy_service=policy_service,
            action_executor=action_executor,
            journal=journal,
            resource_name=resource_name,
        )

        router = SenseGuardEventRouter(
            household_id=household_id,
            policy_store=alert_policy_store,
            resource_resolver=resolve_resource,
            event_sink=journal,
            dispatch_attention_event=dispatch_attention_event,
            dispatch_notification=notification_dispatcher.dispatch,
        )
        automation_router = AutomationEventRouter(
            household_id=household_id,
            store=automation_store,
            resource_resolver=resolve_resource,
            manager=plugins,
            action_executor=action_executor,
            policy_service=policy_service,
            action_refresher=action_refresher,
            action_verifier=None,
            role_resolver=identity_resolver.resolve_role,
            journal=journal,
        )

        def presence_continuity() -> tuple[bool, Any]:
            if ha_adapter is None:
                return False, None
            connection = ha_adapter.connection
            return (
                connection is not None
                and connection.connected
                and ha_adapter.status.last_error_category is None,
                (id(connection), ha_adapter.status.last_successful_state_sync),
            )

        def dispatch_presence_event(event: EventEnvelope, position: int) -> None:
            if event.source != "anima.household_presence" or event.metadata.get(
                "household_id"
            ) != str(household_id):
                raise ValueError("Presence attention requires same-household Core event")
            profile = AttentionProfile("household.presence.event.v1", ())
            consumer = f"household-presence:{household_id}:{event.event_id}"
            attention.prime_consumer_before(profile, consumer, position - 1)
            SentryAttentionBridge(
                attention=attention,
                context=context,
                store=intelligence_store,
                profile=profile,
                event_path_resolver=initiative_context.resolve_event_path,
            ).run_once(
                household_id=household_id,
                tools=plugins.list_tools(),
                consumer_name=consumer,
                limit=1,
                source_event_id=event.event_id,
            )

        presence_router = HouseholdPresenceEventRouter(
            presence_service,
            household_id,
            ha_adapter.config.instance_id,
            continuity=presence_continuity,
            journal=journal,
            dispatch=dispatch_presence_event,
        )

        from anima_ha.ring_events import RingEventRouter

        def dispatch_ring_event(event: EventEnvelope, position: int) -> None:
            if event.source != "anima.ring" or event.metadata.get("household_id") != str(
                household_id
            ):
                raise ValueError("Ring attention requires same-household Core event")
            profile = AttentionProfile("household.ring.event.v1", ())
            consumer = f"household-ring:{household_id}:{event.event_id}"
            attention.prime_consumer_before(profile, consumer, position - 1)
            SentryAttentionBridge(
                attention=attention,
                context=context,
                store=intelligence_store,
                profile=profile,
                event_path_resolver=initiative_context.resolve_event_path,
            ).run_once(
                household_id=household_id,
                tools=plugins.list_tools(),
                consumer_name=consumer,
                limit=1,
                source_event_id=event.event_id,
            )

        def ring_continuity() -> tuple[bool, Any, datetime]:
            online, epoch = presence_continuity()
            ready = ha_adapter.status.last_successful_state_sync if ha_adapter is not None else None
            return online and ready is not None, epoch, ready or datetime.now(UTC)

        ring_router = RingEventRouter(
            ha_adapter,
            household_id,
            journal,
            continuity=ring_continuity,
            dispatch=dispatch_ring_event,
        )

        def handle_normalized_event(event: EventEnvelope) -> None:
            router.handle(event)
            automation_router.handle(event)
            presence_router.handle(event)
            ring_router.handle(event)

        ha_adapter.set_normalized_event_callback(handle_normalized_event)
    return runtime


# Keep the standalone runtime importable by loading the FastAPI module only
# after this composition module has defined its builders.  This matters for
# the separate ANIMA↔SENTRY MCP process, which is not itself a web server.
from anima_ha.ui_api import (  # noqa: E402  # isort: skip
    CommissionedIdentityResolver,
    PrincipalMappingConflict,
    PrincipalMappingRequired,
    UICommandError,
    UIEventBroadcaster,
    UIIdentity,
    device_capability_projection,
)
