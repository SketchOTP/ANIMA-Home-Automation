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
from anima_ha.calendar import (
    CALENDAR_MANIFEST,
    CalendarNativePlugin,
    CalendarService,
    PostgresCalendarStore,
)
from anima_ha.context import ContextBroker
from anima_ha.events import EventEnvelope
from anima_ha.external import ExternalAuditJournalSink, external_plugin
from anima_ha.graph import NodeKind, PostgresHouseholdGraph
from anima_ha.home_assistant import (
    HAInstanceConfig,
    HassClientConnection,
    HomeAssistantAdapter,
    HomeAssistantPlugin,
    PostgresHAStore,
    home_assistant_manifest,
)
from anima_ha.intelligence import (
    IntelligenceOrigin,
    IntelligenceProviderMode,
    IntelligenceRequestFactory,
    PostgresIntelligenceStore,
    SentryAttentionBridge,
)
from anima_ha.journal import PostgresEventJournal, PostgresRealityStore
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
from anima_ha.senseguard_alerts import (
    SENSEGUARD_ALERT_MANIFEST,
    PostgresSenseGuardAlertPolicyStore,
    SenseGuardAlertNativePlugin,
    SenseGuardEventRouter,
)
from anima_ha.sentry_boundary import CoreSentryBoundary
from anima_ha.tasks import TASK_MANIFEST, PostgresTaskStore, TaskNativePlugin, TaskService


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
        if self.events:
            event_name = {
                "anima.durable-tasks": "tasks.changed",
                "anima.calendar": "calendar.changed",
                "anima.senseguard-alerts": "alerts.changed",
                "anima.provider.home-assistant": "home.invalidated",
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

    def device_inventory(self, identity: UIIdentity) -> dict[str, Any]:
        """Return the bounded, already-discovered HA registry for this household."""
        del identity
        plugin = self._tool("anima.provider.home-assistant", "refresh_inventory")
        if self.home_assistant_adapter is None or plugin is None or not plugin.availability:
            return {
                "status": "UNAVAILABLE",
                "items": [],
                "reason": "HOME_ASSISTANT_NOT_COMMISSIONED",
            }
        items = []
        for item in self.home_assistant_adapter.provider_inventory():
            metadata = dict(item.get("metadata") or {})
            canonical_target = None
            canonical_value = metadata.get("canonical_target_id")
            if canonical_value and self.graph is not None:
                try:
                    canonical_target = self.graph.get_node(UUID(str(canonical_value)))
                except (TypeError, ValueError):
                    canonical_target = None
            mapped = canonical_target is not None and item.get("present") is True
            items.append(
                {
                    "external_object_kind": str(item.get("external_object_kind", "")),
                    "external_id": str(item.get("external_id", "")),
                    "present": bool(item.get("present")),
                    "metadata": {
                        key: metadata[key]
                        for key in (
                            "name_by_user",
                            "name",
                            "area_id",
                            "device_id",
                            "platform",
                            "disabled_by",
                        )
                        if key in metadata
                    }
                    | ({
                        "name": canonical_target.name,
                        "mapping_status": "MAPPED",
                        "canonical_target_id": str(canonical_target.canonical_id),
                    } if mapped else {
                        "mapping_status": "UNMAPPED",
                        "canonical_target_id": None,
                    }),
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
        )

    def sentry_boundary(self) -> CoreSentryBoundary:
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
    return {name: os.environ[name] for name in names if os.environ.get(name)}


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
    plugins = PluginManager(journal=journal, secret_broker=SecretBroker(secrets))
    alert_policy_store = PostgresSenseGuardAlertPolicyStore(database_url)

    def alert_resource_is_commissioned(household_id: UUID, resource_id: UUID) -> bool:
        node = graph.get_node(resource_id)
        if node is None or node.kind not in {NodeKind.RESOURCE, NodeKind.SENSOR}:
            return False
        return any(
            resource_id == resource.canonical_id
            for place in graph.places_in_household(household_id)
            for resource in graph.resources_in_place(place.canonical_id)
        )

    plugins.register(
        SENSEGUARD_ALERT_MANIFEST,
        NativeRuntime(
            SenseGuardAlertNativePlugin(
                alert_policy_store,
                resource_validator=alert_resource_is_commissioned,
            )
        ),
    )
    plugins.enable(SENSEGUARD_ALERT_MANIFEST.plugin_id)
    task_service = TaskService(PostgresTaskStore(database_url), journal)
    calendar_service = CalendarService(PostgresCalendarStore(database_url), journal)
    plugins.register(TASK_MANIFEST, NativeRuntime(TaskNativePlugin(task_service)))
    plugins.register(CALENDAR_MANIFEST, NativeRuntime(CalendarNativePlugin(calendar_service)))
    plugins.enable(TASK_MANIFEST.plugin_id)
    plugins.enable(CALENDAR_MANIFEST.plugin_id)

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
        plugins.register(manifest, NativeRuntime(plugin_runtime))
        plugins.enable(plugin_id)
    if secrets.get("NTFY_TOPIC"):
        manifest, plugin_runtime = external_plugin(
            "anima.external.notifications",
            audit_sink=ExternalAuditJournalSink(journal),
            transport=external_transport,
        )
        plugins.register(manifest, NativeRuntime(plugin_runtime))
        plugins.enable(manifest.plugin_id)

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
        plugins.register(
            manifest,
            NativeRuntime(ha_runtime),
            configuration={"instance_id": str(instance_id), "websocket_url": websocket_url},
        )
        plugins.enable(manifest.plugin_id)

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
    )
    household_value = (
        os.environ.get("ANIMA_HOUSEHOLD_ID", "").strip()
        or os.environ.get("ANIMA_SENTRY_HOUSEHOLD_ID", "").strip()
    )
    if ha_adapter is not None and household_value and intelligence_store is not None:
        household_id = UUID(household_value)

        def resolve_resource(external_id: str) -> UUID | None:
            node = graph.resolve_provider_reference(
                "home_assistant", provider_scope, "entity", external_id
            )
            if node is None or node.kind not in {NodeKind.RESOURCE, NodeKind.SENSOR}:
                return None
            return node.canonical_id

        def dispatch_attention() -> None:
            SentryAttentionBridge(
                attention=attention,
                context=context,
                store=intelligence_store,
                # SenseGuard alerts are already classified as guaranteed
                # attention.  Do not apply the broad SENTRY profile here or
                # every ordinary HA state observation would trigger cognition.
                profile=AttentionProfile("phase13.senseguard.v1", ()),
            ).run_once(household_id=household_id, tools=plugins.list_tools())

        router = SenseGuardEventRouter(
            household_id=household_id,
            policy_store=alert_policy_store,
            resource_resolver=resolve_resource,
            event_sink=journal,
            dispatch_attention=dispatch_attention,
        )
        ha_adapter.set_normalized_event_callback(router.handle)
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
)
