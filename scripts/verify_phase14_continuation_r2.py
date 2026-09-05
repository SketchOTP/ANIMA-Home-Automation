"""Exercise real PostgreSQL continuation fencing and terminal replay safety."""

from __future__ import annotations

import json
import sys
from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID, uuid4

import psycopg

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.verify_phase12_h5v_true_resume import (
    DATABASE_URL,
    HOUSEHOLD_ID,
    OPA_URL,
    _packet,
    _seed_postgres_context,
    _tool,
)

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
    PostgresEpisodeStore,
    ScriptedCodexAdapter,
    TokenUsage,
    ToolRequestDecision,
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


def waiting_run() -> tuple[AgentRuntime, EpisodeRequest, UUID, UUID, int]:
    tool = _tool()
    principal = uuid4()
    identity = IdentityContext(HOUSEHOLD_ID, principal, Assurance.AUTHENTICATED)
    packet = _packet()
    _seed_postgres_context(packet)
    request = EpisodeRequest(
        trigger_id=UUID(str(packet["trigger_id"])),
        context_packet_id=UUID(str(packet["context_packet_id"])),
        household_id=HOUSEHOLD_ID,
        context_packet=packet,
        tools=(tool,),
        identity=identity,
        policy_service=PolicyService(
            OpaPolicyClient(OPA_URL), audit_store=PostgresPolicyStore(DATABASE_URL)
        ),
        policy_context=PolicyContext(principal_role="resident"),
        origin=RequestOrigin.DIRECT_USER,
    )
    pending = PostgresPendingApprovalStore(DATABASE_URL)
    coordinator = ActionExecutionCoordinator(
        _NoopGateway(),
        PostgresActionStore(DATABASE_URL),
        PostgresResourceLocker(DATABASE_URL),
        pending_approvals=pending,
    )
    adapter = ScriptedCodexAdapter(
        [
            CodexTurnResult(
                ToolRequestDecision(
                    tool.tool_id, {"title": "Phase 14", "message": "continuation fence"}
                ),
                TokenUsage(),
                1.0,
                ("turn.completed",),
            )
        ]
    )
    agent = AgentRuntime(
        adapter, _NoopGateway(), PostgresEpisodeStore(DATABASE_URL), action_executor=coordinator
    )
    result = agent.run(request)
    assert result.episode.status == EpisodeStatus.WAITING_CONFIRMATION
    approvals = pending.list_for(HOUSEHOLD_ID, principal)
    assert len(approvals) == 1
    return (
        agent,
        request,
        approvals[0].approval_id,
        result.episode.episode_id,
        approvals[0].action_id,
    )


class _NoopGateway:
    def invoke(self, *args: object, **kwargs: object) -> object:
        del args, kwargs
        raise AssertionError("continuation fence test must not dispatch")


def main() -> int:
    if not DATABASE_URL:
        raise RuntimeError("ANIMA_DATABASE_URL is required")
    agent, request, approval_id, episode_id, action_id = waiting_run()
    store = PostgresEpisodeStore(DATABASE_URL)
    owner_a = "phase14-continuation-a"
    owner_b = "phase14-continuation-b"
    assert store.claim_continuation(episode_id, approval_id, owner_a, lease_seconds=1)
    with psycopg.connect(DATABASE_URL) as connection, connection.cursor() as cursor:
        cursor.execute(
            "UPDATE anima_agent_continuations SET claim_expires_at=now()-interval '1 second' "
            "WHERE episode_id=%s AND approval_id=%s",
            (episode_id, approval_id),
        )
        connection.commit()
    assert store.claim_continuation(episode_id, approval_id, owner_b, lease_seconds=30)
    assert not store.transition_continuation(
        episode_id, approval_id, owner_a, "MODEL_RESUMING", "RUNNING"
    )
    stale_rejected = False
    try:
        store.record_continuation_result(
            episode_id,
            approval_id,
            1,
            {"action_status": ActionStatus.RECOVERY_REQUIRED.value},
            "stale",
            owner_a,
        )
    except RuntimeError:
        stale_rejected = True
    assert stale_rejected
    assert store.transition_continuation(
        episode_id, approval_id, owner_b, "RECOVERY_REQUIRED", "FAILED"
    )
    current = store.get_continuation(episode_id, approval_id)
    assert current is not None and current["continuation_status"] == "RECOVERY_REQUIRED"
    action = PostgresActionStore(DATABASE_URL).get(action_id)
    assert action is not None and action.status == ActionStatus.REQUIRE_CONFIRMATION
    assert not request.context_packet.get("missing")
    print(
        json.dumps(
            {
                "scenario_id": "CONTINUATION_STALE_FENCE_AND_PRECLAIM_CRASH",
                "status": "PASS",
                "evidence_level": "POSTGRES_OPA_CORE",
                "pre_claim_reclaimable": True,
                "stale_transition_rejected": True,
                "stale_result_rejected": True,
                "action_dispatches": 0,
                "continuation_status": current["continuation_status"],
                "checked_at": datetime.now(UTC).isoformat(),
                "phase15": False,
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
