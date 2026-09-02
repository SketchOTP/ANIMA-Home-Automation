"""Composition adapters that connect the local interface to ANIMA Core.

This module contains wiring only.  Domain behavior remains in the accepted
journal, attention, context, agent, policy, plugin, task, calendar, and action
modules.  The UI receives these adapters; it never calls a provider or a
database service directly.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any
from uuid import UUID, uuid4

from anima_ha.action import (
    ActionExecutionCoordinator,
    ActionRequest,
    PostgresActionStore,
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
from anima_ha.journal import PostgresEventJournal
from anima_ha.plugins import (
    InvocationContext,
    InvocationOutcome,
    InvocationResult,
    NativeRuntime,
    PluginManager,
)
from anima_ha.policy import (
    Assurance,
    IdentityContext,
    OpaPolicyClient,
    PolicyContext,
    PolicyService,
    RequestOrigin,
)
from anima_ha.tasks import TASK_MANIFEST, PostgresTaskStore, TaskNativePlugin, TaskService
from anima_ha.ui_api import UICommandError, UIEventBroadcaster, UIIdentity


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


@dataclass(slots=True)
class CoreUICommandGateway:
    """Route UI mutations through the existing PluginManager and coordinator."""

    manager: PluginManager
    policy_service: PolicyService
    events: UIEventBroadcaster | None = None
    action_executor: ActionExecutionCoordinator | None = None
    action_refresher: Callable[[tuple[UUID, ...]], Any] | None = None
    action_verifier: Callable[[Any, InvocationResult, Any], Any] | None = None

    def _tool(self, plugin_prefix: str, name: str) -> Any:
        return next(
            (
                item
                for item in self.manager.list_tools()
                if item.plugin_id == plugin_prefix and item.name == name
            ),
            None,
        )

    def _invoke(
        self, identity: UIIdentity, plugin_prefix: str, name: str, payload: dict[str, Any]
    ) -> dict[str, Any]:
        tool = self._tool(plugin_prefix, name)
        if tool is None or not tool.availability:
            raise UICommandError(f"CORE_TOOL_UNAVAILABLE:{plugin_prefix}.{name}")
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
            policy_context=PolicyContext(principal_role="resident"),
            invocation_context=invocation_context,
        )
        if self.events:
            self.events.publish(
                "tasks.changed" if plugin_prefix == "anima.durable-tasks" else "calendar.changed"
            )
        return _safe_result(result)

    def task_mutation(
        self, identity: UIIdentity, operation: str, payload: dict[str, Any]
    ) -> dict[str, Any]:
        return self._invoke(identity, "anima.durable-tasks", operation, payload)

    def calendar_mutation(
        self, identity: UIIdentity, operation: str, payload: dict[str, Any]
    ) -> dict[str, Any]:
        return self._invoke(identity, "anima.calendar", operation, payload)

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
        arguments = {"resource_id": str(resource_id), **payload}
        request = ActionRequest.create(
            idempotency_key=f"ui-control:{identity.household_id}:{uuid4()}",
            household_id=identity.household_id,
            tool=tool,
            arguments=arguments,
            identity=_identity(identity),
            policy_service=self.policy_service,
            policy_context=PolicyContext(principal_role="resident"),
            refresher=self.action_refresher,
            verifier=self.action_verifier,
            origin=RequestOrigin.DIRECT_USER,
            safety_spec=resolve_action_safety_spec(tool),
        )
        execution = self.action_executor.execute(request)
        if self.events:
            self.events.publish("home.invalidated")
        if execution.invocation is not None:
            return _safe_result(execution.invocation)
        return {
            "status": {
                "POLICY_DENIED": "DENIED",
                "REQUIRE_CONFIRMATION": "REQUIRE_CONFIRMATION",
                "REQUIRE_STRONGER_AUTH": "REQUIRE_STRONGER_AUTH",
                "SUCCEEDED": "SUCCEEDED",
                "VERIFICATION_FAILED": "FAILED",
                "UNKNOWN_RESULT": "UNKNOWN_RESULT",
            }.get(execution.record.status.value, execution.record.status.value),
            "operation": tool.tool_id,
            "detail": execution.record.detail,
        }


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
    ) -> None:
        self.attention = attention
        self.context = context
        self.agent = agent
        self.policy_service = policy_service
        self.tools = tools
        self.journal = journal
        self.profile = profile or default_attention_profile("phase12.ui.v1")
        self.consumer_name = consumer_name

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
                policy_context=PolicyContext(principal_role="resident"),
                origin=RequestOrigin.DIRECT_USER,
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

    def conversation(self, events: UIEventBroadcaster) -> CoreConversationPipeline:
        return CoreConversationPipeline(
            attention=self.attention,
            context=self.context,
            agent=self.agent,
            policy_service=self.policy_service,
            tools=self.plugins.list_tools,
            journal=self.journal,
        )

    def commands(self, events: UIEventBroadcaster) -> CoreUICommandGateway:
        return CoreUICommandGateway(
            self.plugins,
            self.policy_service,
            events=events,
            action_executor=self.action_executor,
        )


def build_postgres_core(
    database_url: str,
    *,
    opa_url: str = "http://127.0.0.1:8181",
    codex: Any | None = None,
) -> CoreRuntime:
    """Compose the normal local runtime from accepted Core implementations.

    Provider plugins such as Home Assistant are commissioned separately and
    can be registered on the returned manager before the service starts.  The
    built-in task and local-calendar capabilities are always registered here;
    neither path is a UI-specific direct service call.
    """
    journal = PostgresEventJournal(database_url)
    plugins = PluginManager(journal=journal)
    task_service = TaskService(PostgresTaskStore(database_url), journal)
    calendar_service = CalendarService(PostgresCalendarStore(database_url), journal)
    plugins.register(TASK_MANIFEST, NativeRuntime(TaskNativePlugin(task_service)))
    plugins.register(CALENDAR_MANIFEST, NativeRuntime(CalendarNativePlugin(calendar_service)))
    plugins.enable(TASK_MANIFEST.plugin_id)
    plugins.enable(CALENDAR_MANIFEST.plugin_id)
    policy_service = PolicyService(OpaPolicyClient(opa_url))
    action_executor = ActionExecutionCoordinator(
        plugins,
        PostgresActionStore(database_url),
        PostgresResourceLocker(database_url),
        journal=journal,
    )
    agent = AgentRuntime(
        codex or CodexCliRuntime(),
        plugins,
        PostgresEpisodeStore(database_url),
        journal=journal,
        action_executor=action_executor,
    )
    return CoreRuntime(
        journal,
        PostgresAttentionService(database_url),
        ContextBroker(database_url),
        policy_service,
        agent,
        plugins,
        action_executor,
    )
