"""PostgreSQL persistence/restart evidence for the bounded Phase 8 runtime."""

from __future__ import annotations

import hashlib
import json
import subprocess
import time
from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

import psycopg
from psycopg.rows import dict_row

from anima_ha.agent import (
    AgentRuntime,
    CodexTurnResult,
    EpisodeRequest,
    FinalDecision,
    FinalDisposition,
    PostgresEpisodeStore,
    ScriptedCodexAdapter,
    TokenUsage,
)
from anima_ha.db.migrate import migrate
from anima_ha.events import EventEnvelope
from anima_ha.journal import PostgresEventJournal
from anima_ha.plugins import ExternalContentTrust, InvocationOutcome, InvocationResult
from anima_ha.policy import Assurance, IdentityContext, PolicyContext, PolicyService

DATABASE_URL = "postgresql://anima:anima_dev_only@localhost:55432/anima"
HOUSEHOLD_ID = UUID("ecbd0d84-6f5f-40f8-928f-1d5dfe758dd7")


class AllowEvaluator:
    def evaluate(self, document: dict[str, Any]) -> dict[str, Any]:
        return {"decision": "ALLOW", "reason_code": "READ_ONLY_ALLOWED", "policy_version": "test"}


class NoToolGateway:
    def invoke(self, tool_id: str, arguments: dict[str, Any], **kwargs: Any) -> InvocationResult:
        return InvocationResult(
            InvocationOutcome.PLUGIN_UNAVAILABLE,
            tool_id,
            "",
            "",
            0,
            error_class="UNEXPECTED_TOOL",
            external_content_trust=ExternalContentTrust.LOCAL_TRUSTED,
        )


def wait_for_database(timeout: float = 60) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            with psycopg.connect(DATABASE_URL, connect_timeout=2):
                return
        except psycopg.Error:
            time.sleep(0.5)
    raise TimeoutError("PostgreSQL did not become ready")


def fixture() -> EpisodeRequest:
    run_id = str(uuid4())
    event_id = f"phase8-source-{run_id}"
    profile = f"phase8.integration.{run_id}"
    profile_digest = hashlib.sha256(profile.encode()).hexdigest()
    decision_id = uuid4()
    trigger_id = uuid4()
    context_id = uuid4()
    journal = PostgresEventJournal(DATABASE_URL)
    observed_at = datetime.now(UTC)
    appended = journal.append(
        EventEnvelope.create(
            event_id=event_id,
            event_type="user.request",
            source="phase8-integration",
            subject_key="household/synthetic",
            occurred_at=observed_at,
            recorded_at=observed_at,
            payload={"request": "Determine whether any action is needed."},
            metadata={"household_id": str(HOUSEHOLD_ID)},
        )
    )
    packet = {
        "context_packet_id": str(context_id),
        "schema_version": 1,
        "trigger_id": str(trigger_id),
        "selection_profile_version": profile,
        "digest": hashlib.sha256(run_id.encode()).hexdigest(),
        "omissions": [],
        "sections": {
            "events": {
                "status": "READY",
                "items": [
                    {
                        "kind": "event",
                        "data": {"request": "Determine whether any action is needed."},
                        "source_refs": [event_id],
                        "trust": "LOCAL_TRUSTED",
                        "egress": "CLOUD_ALLOWED",
                    }
                ],
                "error_code": None,
            }
        },
    }
    encoded = json.dumps(packet, sort_keys=True, separators=(",", ":")).encode()
    with psycopg.connect(DATABASE_URL) as connection, connection.cursor() as cursor:
        cursor.execute(
            "INSERT INTO anima_attention_profiles "
            "(profile_version, profile_digest, configuration, activated_at, active) "
            "VALUES (%s,%s,'{}'::jsonb,now(),false)",
            (profile, profile_digest),
        )
        cursor.execute(
            """INSERT INTO anima_attention_decisions (
                attention_decision_id, idempotency_key, source_event_id, journal_position,
                attention_profile_version, decision, reason_code, created_at,
                resulting_trigger_id, metadata
            ) VALUES (%s,%s,%s,%s,%s,'TRIGGER','PHASE8_INTEGRATION',now(),%s,'{}'::jsonb)""",
            (
                decision_id,
                f"phase8:{run_id}",
                event_id,
                appended.journal_position,
                profile,
                trigger_id,
            ),
        )
        cursor.execute(
            """INSERT INTO anima_reasoning_triggers (
                trigger_id, decision_id, trigger_type, source_event_ids,
                journal_position_start, journal_position_end, subject_refs,
                attention_reason, priority, created_at, attention_profile_version,
                context_status, status, metadata
            ) VALUES (%s,%s,'DIRECT',%s::jsonb,%s,%s,%s::jsonb,'PHASE8_INTEGRATION',50,
                now(),%s,'CONTEXT_READY','CONTEXT_READY','{}'::jsonb)""",
            (
                trigger_id,
                decision_id,
                json.dumps([event_id]),
                appended.journal_position,
                appended.journal_position,
                json.dumps(["household/synthetic"]),
                profile,
            ),
        )
        cursor.execute(
            """INSERT INTO anima_context_packets (
                context_packet_id, trigger_id, schema_version, selection_profile_version,
                assembled_at, packet_digest, packet, serialized_bytes
            ) VALUES (%s,%s,1,%s,now(),%s,%s::jsonb,%s)""",
            (context_id, trigger_id, profile, packet["digest"], encoded.decode(), len(encoded)),
        )
        connection.commit()
    return EpisodeRequest(
        trigger_id,
        context_id,
        HOUSEHOLD_ID,
        packet,
        (),
        IdentityContext(HOUSEHOLD_ID, None, Assurance.ANONYMOUS),
        PolicyService(AllowEvaluator()),
        PolicyContext(),
    )


def counts(episode_id: UUID) -> dict[str, int]:
    with psycopg.connect(DATABASE_URL, row_factory=dict_row) as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """SELECT
                    (SELECT count(*) FROM anima_agent_turns WHERE episode_id=%s) AS turns,
                    (SELECT count(*) FROM anima_agent_tool_requests WHERE episode_id=%s) AS tools,
                    (SELECT count(*) FROM anima_event_journal
                     WHERE correlation_id=%s AND event_type LIKE 'agent.episode.%%') AS audits""",
                (episode_id, episode_id, str(episode_id)),
            )
            row = cursor.fetchone()
            assert row is not None
            return {key: int(row[key]) for key in ("turns", "tools", "audits")}


def main() -> int:
    wait_for_database()
    applied = migrate(DATABASE_URL, 5)
    episode_request = fixture()
    adapter = ScriptedCodexAdapter(
        [
            CodexTurnResult(
                FinalDecision("NO_INTERVENTION", False, "", "No action is necessary."),
                TokenUsage(120, 20, 30, 8),
                10.0,
                ("thread.started", "turn.started", "item.completed", "turn.completed"),
            )
        ]
    )
    store = PostgresEpisodeStore(DATABASE_URL)
    runtime = AgentRuntime(
        adapter,
        NoToolGateway(),
        store,
        journal=PostgresEventJournal(DATABASE_URL),
    )
    first = runtime.run(episode_request)
    duplicate = runtime.run(episode_request)
    assert first.episode.final_disposition == FinalDisposition.NO_ACTION
    assert duplicate.duplicate_claim
    assert duplicate.episode.episode_id == first.episode.episode_id
    before = counts(first.episode.episode_id)
    assert before == {"turns": 1, "tools": 0, "audits": 2}

    subprocess.run(["docker", "compose", "restart", "db"], check=True, timeout=60)
    wait_for_database()
    restored = PostgresEpisodeStore(DATABASE_URL).get_by_trigger(episode_request.trigger_id)
    assert restored is not None
    assert restored.episode_id == first.episode.episode_id
    assert restored.final_disposition == FinalDisposition.NO_ACTION
    assert restored.usage == TokenUsage(120, 20, 30, 8)
    repeat = migrate(DATABASE_URL, 5)
    output = {
        "migration_applied": applied,
        "migration_repeat": repeat,
        "episode_id": str(restored.episode_id),
        "duplicate_claim_prevented": True,
        "restart_persistence": True,
        "counts": before,
        "usage": restored.usage.to_payload(),
        "api_dollar_cost_applied": False,
        "phase9_behavior": False,
    }
    print(json.dumps(output, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
