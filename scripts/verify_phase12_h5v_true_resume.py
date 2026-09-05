"""Prove same-episode approval/rejection continuation with real OPA policy."""

from __future__ import annotations

import json
import os
from typing import Any
from uuid import UUID, uuid4

import psycopg

from anima_ha.action import (
    ActionExecutionCoordinator,
    ActionStatus,
    PostgresActionStore,
    PostgresPendingApprovalStore,
    PostgresResourceLocker,
)
from anima_ha.agent import (
    AgentRuntime,
    CodexTurnResult,
    EpisodeRequest,
    EpisodeStatus,
    FinalDecision,
    PostgresEpisodeStore,
    ScriptedCodexAdapter,
    TokenUsage,
    ToolRequestDecision,
)
from anima_ha.plugins import (
    DispatchState,
    ExternalContentTrust,
    Idempotency,
    InvocationOutcome,
    InvocationResult,
    ProviderExecutionContext,
    ToolDescriptor,
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

DATABASE_URL = os.environ.get(
    "ANIMA_DATABASE_URL", "postgresql://anima:anima_dev_only@127.0.0.1:55432/anima"
)
OPA_URL = os.environ.get("ANIMA_OPA_URL", "http://127.0.0.1:18181")
HOUSEHOLD_ID = UUID("ecbd0d84-6f5f-40f8-928f-1d5dfe758dd7")


def _packet() -> dict[str, Any]:
    return {
        "context_packet_id": str(uuid4()),
        "schema_version": 1,
        "trigger_id": str(uuid4()),
        "selection_profile_version": "h5v.v1",
        "digest": "h5v-context-digest",
        "omissions": [],
        "sections": {
            "events": {"status": "READY", "items": [], "error_code": None},
            "truth": {"status": "READY", "items": [], "error_code": None},
        },
    }


def _seed_postgres_context(packet: dict[str, Any]) -> None:
    """Create the minimum real journal/attention/context chain for one test."""
    trigger_id = UUID(str(packet["trigger_id"]))
    packet_id = UUID(str(packet["context_packet_id"]))
    decision_id = uuid4()
    event_id = f"h5v:{uuid4()}"
    with psycopg.connect(DATABASE_URL) as connection, connection.cursor() as cursor:
        cursor.execute(
            """
            INSERT INTO anima_attention_profiles
                (profile_version, profile_digest, configuration, activated_at, active)
            VALUES (%s,%s,%s::jsonb,now(),false)
            ON CONFLICT (profile_version) DO NOTHING
            """,
            (f"h5v-{trigger_id}", f"h5v-{trigger_id}-digest", "{}"),
        )
        profile = f"h5v-{trigger_id}"
        cursor.execute(
            """
            INSERT INTO anima_event_journal
                (event_id,schema_version,event_type,source,subject_key,occurred_at,
                 recorded_at,evidence_kind,importance,delivery_class,payload,metadata)
            VALUES (%s,1,'user.request','h5v-verifier','h5v/continuation',now(),now(),
                    'OBSERVED','NORMAL','GUARANTEED','{}'::jsonb,'{}'::jsonb)
            """,
            (event_id,),
        )
        cursor.execute(
            "SELECT journal_position FROM anima_event_journal WHERE event_id=%s",
            (event_id,),
        )
        position_row = cursor.fetchone()
        if position_row is None:
            raise AssertionError("seed event was not persisted")
        journal_position = int(position_row[0])
        cursor.execute(
            """
            INSERT INTO anima_attention_decisions
                (attention_decision_id,idempotency_key,source_event_id,journal_position,
                 attention_profile_version,decision,reason_code,created_at,metadata)
            VALUES (%s,%s,%s,%s,%s,'TRIGGER','H5V_TEST',now(),'{}'::jsonb)
            """,
            (decision_id, f"h5v:{trigger_id}", event_id, journal_position, profile),
        )
        cursor.execute(
            """
            INSERT INTO anima_reasoning_triggers
                (trigger_id,decision_id,trigger_type,source_event_ids,journal_position_start,
                 journal_position_end,subject_refs,attention_reason,priority,created_at,
                 attention_profile_version,context_status,status,metadata)
            VALUES (%s,%s,'DIRECT_USER','[]'::jsonb,%s,%s,'[]'::jsonb,'H5V_TEST',50,now(),
                    %s,'CONTEXT_READY','CONTEXT_READY','{}'::jsonb)
            """,
            (trigger_id, decision_id, journal_position, journal_position, profile),
        )
        cursor.execute(
            """
            INSERT INTO anima_context_packets
                (context_packet_id,trigger_id,schema_version,selection_profile_version,
                 assembled_at,packet_digest,packet,serialized_bytes)
            VALUES (%s,%s,1,%s,now(),%s,%s::jsonb,%s)
            """,
            (
                packet_id,
                trigger_id,
                packet["selection_profile_version"],
                packet["digest"],
                json.dumps(packet, sort_keys=True),
                len(json.dumps(packet, sort_keys=True).encode()),
            ),
        )
        connection.commit()


def _final(text: str) -> CodexTurnResult:
    return CodexTurnResult(
        FinalDecision("ENOUGH_EVIDENCE", True, text, "h5v continuation"),
        TokenUsage(20, 0, 10, 0),
        1.0,
        ("turn.completed",),
    )


class NotificationGateway:
    def __init__(self) -> None:
        self.calls: list[ProviderExecutionContext] = []

    def invoke(
        self,
        tool_id: str,
        arguments: dict[str, Any],
        **kwargs: Any,
    ) -> InvocationResult:
        del arguments
        context = kwargs.get("execution_context")
        if not isinstance(context, ProviderExecutionContext):
            raise AssertionError("ANIMA did not provide provider execution context")
        self.calls.append(context)
        return InvocationResult(
            InvocationOutcome.SUCCESS,
            tool_id,
            "anima.external.notifications",
            "1.0.0",
            1.0,
            result={"accepted": True},
            provenance="h5v-deterministic-provider",
            external_content_trust=ExternalContentTrust.PLUGIN_TRUSTED,
            dispatch_state=DispatchState.ACKNOWLEDGED,
        )


def _tool() -> ToolDescriptor:
    return ToolDescriptor(
        tool_id="anima.external.notifications.send",
        plugin_id="anima.external.notifications",
        capability_id="notifications",
        name="send",
        description="Send a bounded synthetic notification.",
        input_schema={
            "type": "object",
            "properties": {"title": {"type": "string"}, "message": {"type": "string"}},
            "required": ["title", "message"],
            "additionalProperties": False,
        },
        output_schema={"type": "object"},
        risk_class="EXTERNAL_SIDE_EFFECT",
        semantic_action="send_message",
        read_only=False,
        idempotency=Idempotency.KEYED,
        timeout=2.0,
        verification_requirement="PROVIDER_RECEIPT",
        external_content_trust=ExternalContentTrust.PLUGIN_TRUSTED,
        availability=True,
        version="1.0.0",
        provenance="h5v-deterministic-provider",
        execution_spec={"profile": "notifications.send"},
    )


def _run(decision: str) -> dict[str, Any]:
    tool = _tool()
    principal = uuid4()
    identity = IdentityContext(HOUSEHOLD_ID, principal, Assurance.AUTHENTICATED)
    policy_store = PostgresPolicyStore(DATABASE_URL)
    policy = PolicyService(OpaPolicyClient(OPA_URL), audit_store=policy_store)
    packet = _packet()
    _seed_postgres_context(packet)
    request = EpisodeRequest(
        trigger_id=UUID(str(packet["trigger_id"])),
        context_packet_id=UUID(str(packet["context_packet_id"])),
        household_id=HOUSEHOLD_ID,
        context_packet=packet,
        tools=(tool,),
        identity=identity,
        policy_service=policy,
        policy_context=PolicyContext(principal_role="resident"),
        origin=RequestOrigin.DIRECT_USER,
    )
    provider = NotificationGateway()
    pending = PostgresPendingApprovalStore(DATABASE_URL)
    coordinator = ActionExecutionCoordinator(
        provider,
        PostgresActionStore(DATABASE_URL),
        PostgresResourceLocker(DATABASE_URL),
        pending_approvals=pending,
    )
    adapter = ScriptedCodexAdapter(
        [
            CodexTurnResult(
                ToolRequestDecision(
                    tool.tool_id,
                    {"title": "H5V", "message": "continuation approval test"},
                ),
                TokenUsage(),
                1.0,
                ("turn.completed",),
            ),
            _final(
                "The request was approved and completed."
                if decision == "APPROVE"
                else "The request was rejected and was not dispatched."
            ),
        ]
    )
    store = PostgresEpisodeStore(DATABASE_URL)
    agent = AgentRuntime(
        adapter,
        provider,
        store,
        action_executor=coordinator,
    )
    waiting = agent.run(request)
    if waiting.episode.status != EpisodeStatus.WAITING_CONFIRMATION:
        raise AssertionError(f"expected waiting confirmation, got {waiting.episode.status}")
    approval = pending.list_for(HOUSEHOLD_ID, principal)
    if len(approval) != 1:
        raise AssertionError(f"expected one approval, got {len(approval)}")
    resumed = agent.resume_confirmation(
        approval[0].approval_id,
        identity=identity,
        decision=decision,
        policy_context=request.policy_context,
        tool_resolver=lambda tool_id: tool if tool_id == tool.tool_id else None,
        tools=(tool,),
        policy_service=policy,
    )
    if resumed is None or resumed.episode.episode_id != waiting.episode.episode_id:
        raise AssertionError("continuation did not resume the original episode")
    # A completed continuation is terminal.  Replaying the same approval
    # callback must not reconstruct a second model turn or provider effect.
    resumed_again = agent.resume_confirmation(
        approval[0].approval_id,
        identity=identity,
        decision=decision,
        policy_context=request.policy_context,
        tool_resolver=lambda tool_id: tool if tool_id == tool.tool_id else None,
        tools=(tool,),
        policy_service=policy,
    )
    if resumed_again is not None:
        raise AssertionError("terminal continuation was replayed")
    if len(adapter.prompts) != 2:
        raise AssertionError(f"expected two model turns, got {len(adapter.prompts)}")
    with psycopg.connect(DATABASE_URL) as connection, connection.cursor() as cursor:
        cursor.execute(
            "SELECT count(*) FROM anima_agent_continuations WHERE episode_id=%s",
            (waiting.episode.episode_id,),
        )
        continuation_row = cursor.fetchone()
    if continuation_row is None or int(continuation_row[0]) != 1:
        raise AssertionError("continuation result was not durably appended")
    if decision == "REJECT" and provider.calls:
        raise AssertionError("rejected approval dispatched to provider")
    if decision == "APPROVE" and len(provider.calls) != 1:
        raise AssertionError("approved action did not dispatch exactly once")
    action_id = approval[0].action_id
    action = coordinator.store.get(action_id)
    expected_status = (
        ActionStatus.SUCCEEDED if decision == "APPROVE" else ActionStatus.POLICY_DENIED
    )
    if action is None or action.status != expected_status:
        raise AssertionError(f"expected {expected_status}, got {action.status if action else None}")
    transcript = store.load_transcript(waiting.episode.episode_id)
    if not any(
        item.get("tool_result", {}).get("approval_decision") == decision for item in transcript
    ):
        raise AssertionError("approval decision was not present in resumed transcript")
    return {
        "decision": decision,
        "episode_id": str(waiting.episode.episode_id),
        "same_episode": True,
        "model_turns": len(adapter.prompts),
        "continuation_records": 1,
        "action_status": action.status.value,
        "provider_calls": len(provider.calls),
        "provider_execution_context": bool(provider.calls),
        "phase13": False,
    }


def main() -> int:
    evidence = {"approve": _run("APPROVE"), "reject": _run("REJECT")}
    print(json.dumps(evidence, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
