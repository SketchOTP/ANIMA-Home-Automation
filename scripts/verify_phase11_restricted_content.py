"""Real-PostgreSQL evidence for restricted external-content persistence."""

from __future__ import annotations

import hashlib
import json
import os
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
    PostgresEpisodeStore,
    ScriptedCodexAdapter,
    TokenUsage,
    ToolRequestDecision,
)
from anima_ha.db.migrate import migrate
from anima_ha.events import EventEnvelope
from anima_ha.external import external_manifests
from anima_ha.journal import PostgresEventJournal
from anima_ha.plugins import (
    ExternalContentTrust,
    InvocationOutcome,
    InvocationResult,
    ToolDescriptor,
)
from anima_ha.policy import Assurance, IdentityContext, PolicyService

DATABASE_URL = os.environ.get(
    "ANIMA_DATABASE_URL", "postgresql://anima:anima_dev_only@localhost:55432/anima"
)
HOUSEHOLD_ID = UUID("ecbd0d84-6f5f-40f8-928f-1d5dfe758dd7")
SENTINEL = "BB_RESTRICTED_SENTINEL_PRODUCT_9F31"
PRICE_SENTINEL = "BB_RESTRICTED_SENTINEL_PRICE_2719"


class AllowEvaluator:
    def evaluate(self, document: dict[str, Any]) -> dict[str, Any]:
        del document
        return {"decision": "ALLOW", "reason_code": "READ_ONLY_ALLOWED", "policy_version": "test"}


class RestrictedGateway:
    def invoke(self, tool_id: str, arguments: dict[str, Any], **kwargs: Any) -> InvocationResult:
        del arguments, kwargs
        return InvocationResult(
            InvocationOutcome.SUCCESS,
            tool_id,
            "anima.external.shopping.bestbuy",
            "0.1.0",
            1.0,
            result={"products": [{"name": SENTINEL, "price": PRICE_SENTINEL}]},
            provenance="best_buy",
            external_content_trust=ExternalContentTrust.EXTERNAL_UNTRUSTED,
        )


def _fixture() -> EpisodeRequest:
    run_id = uuid4()
    event_id = f"phase11-restricted-{run_id}"
    profile = f"phase11.restricted.{run_id}"
    trigger_id = uuid4()
    context_id = uuid4()
    decision_id = uuid4()
    journal = PostgresEventJournal(DATABASE_URL)
    now = datetime.now(UTC)
    appended = journal.append(
        EventEnvelope.create(
            event_id=event_id,
            event_type="user.request",
            source="phase11-restricted-test",
            subject_key="household/synthetic",
            occurred_at=now,
            recorded_at=now,
            payload={"request": "Compare current synthetic products."},
            metadata={"household_id": str(HOUSEHOLD_ID)},
        )
    )
    packet = {
        "context_packet_id": str(context_id),
        "schema_version": 1,
        "trigger_id": str(trigger_id),
        "selection_profile_version": profile,
        "digest": hashlib.sha256(str(run_id).encode()).hexdigest(),
        "omissions": [],
        "sections": {
            "events": {
                "status": "READY",
                "items": [
                    {
                        "kind": "event",
                        "data": {"request": "Compare current synthetic products."},
                        "source_refs": [event_id],
                        "trust": "LOCAL_TRUSTED",
                        "egress": "CLOUD_ALLOWED",
                    }
                ],
                "error_code": None,
            },
            "truth": {"status": "READY", "items": []},
        },
    }
    encoded = json.dumps(packet, sort_keys=True, separators=(",", ":")).encode()
    with psycopg.connect(DATABASE_URL) as connection, connection.cursor() as cursor:
        cursor.execute(
            """INSERT INTO anima_attention_profiles
                (profile_version, profile_digest, configuration, activated_at, active)
                VALUES (%s,%s,'{}'::jsonb,%s,false)""",
            (profile, hashlib.sha256(profile.encode()).hexdigest(), now),
        )
        cursor.execute(
            """INSERT INTO anima_attention_decisions
                (attention_decision_id, idempotency_key, source_event_id, journal_position,
                 attention_profile_version, decision, reason_code, created_at, resulting_trigger_id)
                VALUES (%s,%s,%s,%s,%s,'TRIGGER','PHASE11_RESTRICTED',%s,%s)""",
            (
                decision_id,
                f"phase11-restricted:{run_id}",
                event_id,
                appended.journal_position,
                profile,
                now,
                trigger_id,
            ),
        )
        cursor.execute(
            """INSERT INTO anima_reasoning_triggers
                (trigger_id, decision_id, trigger_type, source_event_ids,
                 journal_position_start, journal_position_end, subject_refs, attention_reason,
                 priority, created_at, attention_profile_version, context_status, status)
                VALUES (%s,%s,'DIRECT',%s::jsonb,%s,%s,%s::jsonb,'PHASE11_RESTRICTED',50,%s,%s,
                        'CONTEXT_READY','CONTEXT_READY')""",
            (
                trigger_id,
                decision_id,
                json.dumps([event_id]),
                appended.journal_position,
                appended.journal_position,
                json.dumps(["household/synthetic"]),
                now,
                profile,
            ),
        )
        cursor.execute(
            """INSERT INTO anima_context_packets
                (context_packet_id, trigger_id, schema_version, selection_profile_version,
                 assembled_at, packet_digest, packet, serialized_bytes)
                VALUES (%s,%s,1,%s,%s,%s,%s::jsonb,%s)""",
            (
                context_id,
                trigger_id,
                profile,
                now,
                packet["digest"],
                encoded.decode(),
                len(encoded),
            ),
        )
        connection.commit()
    manifest = next(
        item for item in external_manifests() if item.plugin_id == "anima.external.shopping.bestbuy"
    )
    descriptor = ToolDescriptor.from_manifest(manifest, manifest.tools[0], available=True)
    return EpisodeRequest(
        trigger_id,
        context_id,
        HOUSEHOLD_ID,
        packet,
        (descriptor,),
        IdentityContext(HOUSEHOLD_ID, None, Assurance.ANONYMOUS),
        PolicyService(AllowEvaluator()),
    )


def _sentinel_hits(episode_id: UUID) -> tuple[list[tuple[str, str]], int]:
    hits: list[tuple[str, str]] = []
    export_bytes = bytearray()
    with psycopg.connect(DATABASE_URL, row_factory=dict_row) as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """SELECT table_name, column_name
                   FROM information_schema.columns
                   WHERE table_schema='public' AND table_name LIKE 'anima_%'
                     AND data_type IN ('text','character varying','json','jsonb')"""
            )
            columns = cursor.fetchall()
            for column in columns:
                table = str(column["table_name"])
                name = str(column["column_name"])
                cursor.execute(
                    f'SELECT count(*) AS count FROM "{table}" WHERE "{name}"::text LIKE %s',
                    (f"%{SENTINEL}%",),
                )
                count_row = cursor.fetchone()
                assert count_row is not None
                if int(count_row["count"]):
                    hits.append((table, name))
            cursor.execute(
                """SELECT table_name
                   FROM information_schema.tables
                   WHERE table_schema='public' AND table_name LIKE 'anima_%'
                     AND table_type='BASE TABLE'"""
            )
            for table_row in cursor.fetchall():
                table = str(table_row["table_name"])
                cursor.execute(
                    f"SELECT COALESCE(jsonb_agg(to_jsonb(t)), '[]'::jsonb) "
                    f'FROM (SELECT * FROM "{table}") AS t'
                )
                export_row = cursor.fetchone()
                assert export_row is not None
                export_bytes.extend(canonical_export(export_row["coalesce"]))
            cursor.execute(
                "SELECT metadata, response_text FROM anima_agent_episodes WHERE episode_id=%s",
                (episode_id,),
            )
            row = cursor.fetchone()
            assert row is not None
            assert row["metadata"]["restricted_content_seen"] is True
            assert "CONTENT_NOT_DURABLY_RETAINED" in (row["response_text"] or "")
    return hits, export_bytes.count(SENTINEL.encode()) + export_bytes.count(PRICE_SENTINEL.encode())


def _durable_examples(episode_id: UUID) -> dict[str, Any]:
    with psycopg.connect(DATABASE_URL, row_factory=dict_row) as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """SELECT tool_id, outcome, sanitized_result, arguments
                   FROM anima_agent_tool_requests
                   WHERE episode_id=%s ORDER BY request_number""",
                (episode_id,),
            )
            tool_row = cursor.fetchone()
            cursor.execute(
                """SELECT decision, error_class FROM anima_agent_turns
                   WHERE episode_id=%s ORDER BY turn_number DESC LIMIT 1""",
                (episode_id,),
            )
            turn_row = cursor.fetchone()
            cursor.execute(
                """SELECT response_text, metadata FROM anima_agent_episodes
                   WHERE episode_id=%s""",
                (episode_id,),
            )
            episode_row = cursor.fetchone()
            assert tool_row is not None and turn_row is not None and episode_row is not None
            return {
                "tool_request": {
                    "tool_id": tool_row["tool_id"],
                    "outcome": tool_row["outcome"],
                    "arguments": tool_row["arguments"],
                    "sanitized_result": tool_row["sanitized_result"],
                },
                "turn": {
                    "decision": turn_row["decision"],
                    "error_class": turn_row["error_class"],
                },
                "episode": {
                    "response_text": episode_row["response_text"],
                    "metadata": episode_row["metadata"],
                },
            }


def canonical_export(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, default=str).encode()


def main() -> int:
    migrate(DATABASE_URL, 5)
    request = _fixture()
    live_text = f"Live answer includes {SENTINEL} and {PRICE_SENTINEL}."
    result = AgentRuntime(
        ScriptedCodexAdapter(
            [
                CodexTurnResult(
                    ToolRequestDecision(request.tools[0].tool_id, {"query": "headphones"}),
                    TokenUsage(),
                    1.0,
                    (),
                ),
                CodexTurnResult(
                    FinalDecision("DONE", True, live_text, "comparison complete"),
                    TokenUsage(),
                    1.0,
                    (),
                ),
            ]
        ),
        RestrictedGateway(),
        PostgresEpisodeStore(DATABASE_URL),
    ).run(request)
    assert result.live_response_text == live_text
    assert result.episode.restricted_content_seen
    duplicate = AgentRuntime(
        ScriptedCodexAdapter([]),
        RestrictedGateway(),
        PostgresEpisodeStore(DATABASE_URL),
    ).run(request)
    assert duplicate.duplicate_claim
    assert duplicate.live_response_text is None
    hits, export_occurrences = _sentinel_hits(result.episode.episode_id)
    assert export_occurrences == 0
    examples = _durable_examples(result.episode.episode_id)
    print(
        json.dumps(
            {
                "episode_id": str(result.episode.episode_id),
                "live_response_contains_sentinel": SENTINEL in (result.live_response_text or ""),
                "restricted_content_seen": result.episode.restricted_content_seen,
                "database_sentinel_hits": hits,
                "durable_export_sentinel_occurrences": export_occurrences,
                "durable_response_marker": result.episode.response_text.split()[0],
                "durable_examples": examples,
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
