from __future__ import annotations

from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from typing import Any, cast
from uuid import UUID, uuid4

from anima_ha.action import ActionStatus
from anima_ha.agent import (
    AgentRuntime,
    CodexTurnResult,
    FinalDecision,
    InMemoryEpisodeStore,
    ScriptedCodexAdapter,
    TokenUsage,
)
from anima_ha.attention import AttentionProfile, ReasoningTrigger, TriggerStatus
from anima_ha.events import DeliveryClass, EventEnvelope, EventImportance
from anima_ha.graph import NodeKind
from anima_ha.plugins import (
    DispatchState,
    ExternalContentTrust,
    Idempotency,
    InvocationOutcome,
    InvocationResult,
    NativeRuntime,
    PluginManager,
    ToolDescriptor,
)
from anima_ha.policy import Assurance, EvidenceType, IdentityEvidence, PolicyService
from anima_ha.tasks import (
    TASK_MANIFEST,
    InMemoryTaskStore,
    ScheduleKind,
    TaskNativePlugin,
    TaskService,
    TaskType,
)
from anima_ha.ui_api import UIIdentity
from anima_ha.ui_runtime import (
    CoreConversationPipeline,
    CoreUICommandGateway,
    _safe_confirmation_result,
)


class AllowEvaluator:
    def evaluate(self, document: dict[str, object]) -> dict[str, object]:
        del document
        return {"decision": "ALLOW", "reason_code": "TEST_ALLOW", "policy_version": "test"}


class CapturingEvaluator(AllowEvaluator):
    def __init__(self) -> None:
        self.documents: list[dict[str, object]] = []

    def evaluate(self, document: dict[str, object]) -> dict[str, object]:
        self.documents.append(document)
        return super().evaluate(document)


class StubAttention:
    def __init__(self, trigger: ReasoningTrigger) -> None:
        self.trigger = trigger

    def process(self, profile: AttentionProfile, **kwargs: object) -> SimpleNamespace:
        del profile, kwargs
        return SimpleNamespace(failure=None, processed=1)

    def list_triggers(self, profile_version: str) -> list[ReasoningTrigger]:
        assert profile_version == self.trigger.attention_profile_version
        return [self.trigger]


class StubContext:
    def __init__(self, packet: dict[str, object]) -> None:
        self.packet = packet

    def assemble(self, trigger: ReasoningTrigger, **kwargs: object) -> SimpleNamespace:
        del trigger, kwargs
        return SimpleNamespace(
            context_packet_id=UUID(str(self.packet["context_packet_id"])),
            to_payload=lambda: self.packet,
        )


def test_device_inventory_projects_canonical_capabilities_and_truth() -> None:
    resource_id = uuid4()
    capability_id = uuid4()
    observed_at = datetime.now(UTC)
    resource = SimpleNamespace(canonical_id=resource_id, name="Hall light", kind=NodeKind.RESOURCE)
    capability = SimpleNamespace(
        canonical_id=capability_id,
        name="Hall light power capability",
        kind=NodeKind.CAPABILITY,
        metadata={"capability_type": "power.set", "readable": True, "writable": True},
    )

    class Graph:
        def get_node(self, value: UUID) -> object | None:
            return resource if value == resource_id else None

        def resource_capabilities(self, value: UUID) -> list[object]:
            assert value == resource_id
            return [capability]

        def truth_for_node(self, value: UUID, truth: object) -> list[tuple[object, object]]:
            assert value == capability_id
            assert truth is not None
            return [
                (
                    SimpleNamespace(semantic_attribute="power.state"),
                    SimpleNamespace(
                        status=SimpleNamespace(value="CURRENT/KNOWN"),
                        value=True,
                        last_observed_at=observed_at,
                    ),
                )
            ]

    adapter = SimpleNamespace(
        graph=Graph(),
        reality=SimpleNamespace(projection=SimpleNamespace(get=lambda *_args, **_kwargs: None)),
        provider_inventory=lambda: [
            {
                "external_object_kind": "device",
                "external_id": "ha-device",
                "present": True,
                "metadata": {"canonical_target_id": str(resource_id), "name": "Hall light"},
            }
        ],
    )
    manager = SimpleNamespace(
        list_tools=lambda: [
            SimpleNamespace(
                plugin_id="anima.provider.home-assistant",
                name="refresh_inventory",
                availability=True,
            )
        ]
    )
    gateway = CoreUICommandGateway(
        cast(Any, manager),
        PolicyService(AllowEvaluator()),
        home_assistant_adapter=adapter,  # type: ignore[arg-type]
    )

    result = gateway.device_inventory(cast(Any, object()))

    item = result["items"][0]
    assert item["state"] == "ON"
    assert item["truth_status"] == "CURRENT/KNOWN"
    assert item["capabilities"] == [
        {
            "type": "power.set",
            "label": "Hall light power capability",
            "readable": True,
            "writable": True,
            "truth_status": "CURRENT/KNOWN",
            "state": "ON",
            "observed_at": observed_at.isoformat(),
        }
    ]


def test_core_pipeline_runs_real_agent_from_journal_trigger() -> None:
    household_id = UUID("00000000-0000-0000-0000-000000000012")
    principal_id = UUID("00000000-0000-0000-0000-000000000013")
    event_id = str(uuid4())
    trigger_id = uuid4()
    context_id = uuid4()
    profile = AttentionProfile("phase12.test.v1", ())
    now = datetime.now(UTC)
    trigger = ReasoningTrigger(
        trigger_id,
        "EVENT",
        (event_id,),
        (1, 1),
        (f"household/{household_id}",),
        "GUARANTEED_CLASS",
        100,
        now + timedelta(hours=1),
        profile.profile_version,
        str(trigger_id),
        TriggerStatus.CONTEXT_READY,
        TriggerStatus.CONTEXT_READY,
        {"household_id": str(household_id)},
    )
    packet = {
        "context_packet_id": str(context_id),
        "schema_version": 1,
        "trigger_id": str(trigger_id),
        "selection_profile_version": profile.profile_version,
        "digest": "test-digest",
        "omissions": [],
        "sections": {"events": {"status": "READY", "items": []}},
    }
    evidence = IdentityEvidence(
        uuid4(),
        household_id,
        principal_id,
        EvidenceType.AUTHENTICATED_SESSION,
        "test",
        now,
        now,
        now + timedelta(hours=1),
        Assurance.AUTHENTICATED,
        70,
        "ui-test",
    )
    identity = UIIdentity(household_id, principal_id, "test-ha-user", evidence)
    event = EventEnvelope.create(
        event_id=event_id,
        event_type="user.request",
        source="anima.ui",
        subject_key=f"household/{household_id}",
        occurred_at=now,
        payload={"text": "What is the status?"},
        importance=EventImportance.IMPORTANT,
        delivery_class=DeliveryClass.GUARANTEED,
        correlation_id=event_id,
        metadata={"household_id": str(household_id)},
    )
    agent = AgentRuntime(
        ScriptedCodexAdapter(
            [
                CodexTurnResult(
                    FinalDecision("READY", True, "Anima is ready.", "DONE"),
                    TokenUsage(),
                    1.0,
                    (),
                )
            ]
        ),
        gateway=SimpleNamespace(),
        store=InMemoryEpisodeStore(),
    )
    pipeline = CoreConversationPipeline(
        attention=StubAttention(trigger),
        context=StubContext(packet),
        agent=agent,
        policy_service=PolicyService(AllowEvaluator()),
        tools=lambda: [],
        profile=profile,
    )

    result = pipeline.run(identity, event)

    assert result["response"] == "Anima is ready."
    assert result["trace"]["event_id"] == event_id
    assert result["trace"]["trigger_id"] == str(trigger_id)
    assert result["trace"]["context_packet_id"] == str(context_id)


def test_ui_task_mutation_uses_core_plugin_and_policy_gateway() -> None:
    household_id = UUID("00000000-0000-0000-0000-000000000012")
    principal_id = UUID("00000000-0000-0000-0000-000000000013")
    now = datetime.now(UTC)
    evidence = IdentityEvidence(
        uuid4(),
        household_id,
        principal_id,
        EvidenceType.AUTHENTICATED_SESSION,
        "test",
        now,
        now,
        now + timedelta(hours=1),
        Assurance.AUTHENTICATED,
        70,
        "ui-test",
    )
    identity = UIIdentity(household_id, principal_id, "test-ha-user", evidence)
    task_service = TaskService(InMemoryTaskStore())
    manager = PluginManager()
    manager.register(TASK_MANIFEST, NativeRuntime(TaskNativePlugin(task_service)))
    manager.enable(TASK_MANIFEST.plugin_id)
    gateway = CoreUICommandGateway(manager, PolicyService(AllowEvaluator()))

    result = gateway.task_mutation(
        identity,
        "schedule",
        {
            "task_type": TaskType.REASONING_DUE.value,
            "title": "UI-created reminder",
            "payload": {"objective": "recheck"},
            "schedule": {
                "kind": ScheduleKind.ONCE.value,
                "timezone": "UTC",
                "run_at": (now + timedelta(hours=1)).isoformat(),
            },
        },
    )

    assert result["status"] == "SUCCEEDED"
    assert len(task_service.list_tasks(household_id)) == 1


def test_ui_mutation_policy_role_is_resolved_from_trusted_runtime_context() -> None:
    household_id = UUID("00000000-0000-0000-0000-000000000012")
    principal_id = UUID("00000000-0000-0000-0000-000000000013")
    now = datetime.now(UTC)
    evidence = IdentityEvidence(
        uuid4(),
        household_id,
        principal_id,
        EvidenceType.AUTHENTICATED_SESSION,
        "test",
        now,
        now,
        now + timedelta(hours=1),
        Assurance.AUTHENTICATED,
        70,
        "ui-test",
    )
    identity = UIIdentity(household_id, principal_id, "test-ha-user", evidence)
    evaluator = CapturingEvaluator()
    task_service = TaskService(InMemoryTaskStore())
    manager = PluginManager()
    manager.register(TASK_MANIFEST, NativeRuntime(TaskNativePlugin(task_service)))
    manager.enable(TASK_MANIFEST.plugin_id)
    gateway = CoreUICommandGateway(
        manager,
        PolicyService(evaluator),
        policy_role_resolver=lambda principal: "guest" if principal == principal_id else None,
    )
    result = gateway.task_mutation(
        identity,
        "schedule",
        {
            "task_type": TaskType.REASONING_DUE.value,
            "title": "trusted role",
            "payload": {"objective": "test"},
            "schedule": {
                "kind": ScheduleKind.ONCE.value,
                "timezone": "UTC",
                "run_at": (now + timedelta(hours=1)).isoformat(),
            },
        },
    )
    assert result["status"] == "SUCCEEDED"
    assert evaluator.documents[-1]["policy"]["role"] == "guest"  # type: ignore[index]


class _ActionManager:
    def __init__(self, tool: ToolDescriptor) -> None:
        self.tool = tool
        self.arguments: dict[str, object] | None = None

    def list_tools(self) -> list[ToolDescriptor]:
        return [self.tool]


class _ActionExecutor:
    def __init__(self, status: ActionStatus) -> None:
        self.status = status
        self.request: Any = None

    def execute(self, request: Any) -> SimpleNamespace:
        self.request = request
        invocation = InvocationResult(
            InvocationOutcome.SUCCESS,
            "anima.provider.home-assistant.set_power",
            "anima.provider.home-assistant",
            "1.0.0",
            0.1,
            result={"acknowledged": True},
            dispatch_state=DispatchState.ACKNOWLEDGED,
            external_content_trust=ExternalContentTrust.PLUGIN_TRUSTED,
        )
        record = SimpleNamespace(
            status=self.status,
            detail="post-action observation did not match",
            result={"executed": True},
        )
        return SimpleNamespace(record=record, invocation=invocation)


def _ui_control_identity() -> UIIdentity:
    household_id = UUID("00000000-0000-0000-0000-000000000012")
    principal_id = UUID("00000000-0000-0000-0000-000000000013")
    now = datetime.now(UTC)
    return UIIdentity(
        household_id,
        principal_id,
        "test-ha-user",
        IdentityEvidence(
            uuid4(),
            household_id,
            principal_id,
            EvidenceType.AUTHENTICATED_SESSION,
            "test",
            now,
            now,
            now + timedelta(hours=1),
            Assurance.AUTHENTICATED,
            70,
            "ui-test",
        ),
    )


def _home_tool() -> ToolDescriptor:
    return ToolDescriptor(
        tool_id="anima.provider.home-assistant.set_power",
        plugin_id="anima.provider.home-assistant",
        capability_id="home.control",
        name="set_power",
        description="set power",
        input_schema={"type": "object", "required": ["resource_id", "desired_on"]},
        output_schema={"type": "object"},
        risk_class="LOW_RISK_HOME_CONTROL",
        semantic_action="set_power",
        read_only=False,
        idempotency=Idempotency.KEYED,
        timeout=2.0,
        verification_requirement="PROVIDER_STATE_MATCH",
        external_content_trust=ExternalContentTrust.PLUGIN_TRUSTED,
        availability=True,
        version="1.0.0",
        provenance="test",
        execution_spec={"profile": "set_power"},
    )


def test_ui_control_projects_phase9_verification_status_and_canonical_arguments() -> None:
    manager = _ActionManager(_home_tool())
    executor = _ActionExecutor(ActionStatus.VERIFICATION_FAILED)
    gateway = CoreUICommandGateway(
        cast(PluginManager, manager),
        PolicyService(AllowEvaluator()),
        action_executor=cast(Any, executor),
    )

    result = gateway.control(_ui_control_identity(), str(uuid4()), {"desired_on": True})

    assert result["status"] == "VERIFICATION_FAILED"
    assert result["status"] != "SUCCEEDED"
    assert result["evidence"] == {"connector_outcome": "SUCCESS", "dispatch_state": "ACKNOWLEDGED"}
    assert executor.request is not None
    assert executor.request.arguments["desired_on"] is True
    assert "state" not in executor.request.arguments


def test_ui_control_projects_unknown_post_dispatch_state() -> None:
    manager = _ActionManager(_home_tool())
    executor = _ActionExecutor(ActionStatus.UNKNOWN_RESULT)
    gateway = CoreUICommandGateway(
        cast(PluginManager, manager),
        PolicyService(AllowEvaluator()),
        action_executor=cast(Any, executor),
    )

    result = gateway.control(_ui_control_identity(), str(uuid4()), {"desired_on": False})

    assert result["status"] == "UNKNOWN_RESULT"


def test_ui_confirmation_rejection_is_distinct_from_policy_denial() -> None:
    result = _safe_confirmation_result(
        {"status": "POLICY_DENIED", "operation": "anima.test.set_power"},
        decision="REJECT",
        approval_status="REJECTED",
        action_status="POLICY_DENIED",
    )

    assert result["status"] == "REJECTED"
    assert result["approval_status"] == "REJECTED"
    assert result["action_status"] == "POLICY_DENIED"
