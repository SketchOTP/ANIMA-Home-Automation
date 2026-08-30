"""PostgreSQL and synthetic high-volume evidence for ANIMA Phase 7."""

from __future__ import annotations

import json
import subprocess
import time
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import psycopg
from psycopg.rows import dict_row

from anima_ha.attention import (
    AttentionProfile,
    AttentionReplay,
    AttentionRule,
    PostgresAttentionService,
    RuleAction,
    default_attention_profile,
)
from anima_ha.context import ContextBroker
from anima_ha.db.migrate import migrate
from anima_ha.events import (
    DeliveryClass,
    EventEnvelope,
    EventImportance,
    ObservationState,
    TruthObservation,
)
from anima_ha.fixtures import sample_household_document
from anima_ha.graph import PostgresHouseholdGraph
from anima_ha.journal import PostgresEventJournal, PostgresRealityStore
from anima_ha.memory import (
    MemoryProvenance,
    MemoryRecord,
    MemoryService,
    MemoryType,
    ProvenanceKind,
)
from anima_ha.plugins import ExternalContentTrust, Idempotency, ToolDescriptor
from anima_ha.routines import RoutineService

DATABASE_URL = "postgresql://anima:anima_dev_only@localhost:55432/anima"


def wait_for_database(timeout: float = 60) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            with psycopg.connect(DATABASE_URL, connect_timeout=2):
                return
        except psycopg.Error:
            time.sleep(0.5)
    raise TimeoutError("PostgreSQL did not become ready")


def append_high_volume(
    journal: PostgresEventJournal,
    *,
    run_id: str,
    household_id: UUID,
    entrance_id: UUID,
    base: datetime,
) -> tuple[list[str], list[str]]:
    ordinary_ids: list[str] = []
    guaranteed_ids: list[str] = []
    with psycopg.connect(DATABASE_URL, row_factory=dict_row) as connection:
        for index in range(10_000):
            seconds = index // 100
            at = base + timedelta(seconds=seconds)
            if index % 500 == 0:
                guaranteed_id = f"phase7-{run_id}-guaranteed-{index // 500}"
                guaranteed_ids.append(guaranteed_id)
                journal.append_in_connection(
                    connection,
                    EventEnvelope.create(
                        event_id=guaranteed_id,
                        event_type="user.request" if index == 0 else "safety.leak",
                        source="phase7-volume",
                        subject_key=str(entrance_id) if index == 0 else f"safety/zone/{index % 3}",
                        occurred_at=at,
                        recorded_at=at,
                        payload=(
                            {
                                "request": "What is happening at the front door?",
                                "identity_context": {
                                    "household_id": str(household_id),
                                    "principal_id": str(uuid4()),
                                    "assurance": "AUTHENTICATED",
                                    "conflicting": False,
                                    "evidence_ids": [f"phase7-evidence-{run_id}"],
                                },
                            }
                            if index == 0
                            else {"classification": "synthetic-guaranteed"}
                        ),
                        source_event_id=guaranteed_id,
                        importance=EventImportance.CRITICAL,
                        delivery_class=DeliveryClass.GUARANTEED,
                        metadata={"household_id": str(household_id)},
                    ),
                )
            event_id = f"phase7-{run_id}-motion-{index}"
            ordinary_ids.append(event_id)
            journal.append_in_connection(
                connection,
                EventEnvelope.create(
                    event_id=event_id,
                    event_type="household.motion",
                    source="phase7-volume",
                    subject_key=f"room/{index % 2}/motion",
                    occurred_at=at,
                    recorded_at=at,
                    payload={"active": True, "sample": index},
                    source_event_id=event_id,
                    metadata={"household_id": str(household_id)},
                ),
            )
        connection.commit()
    return ordinary_ids, guaranteed_ids


def rows_for_run(run_id: str) -> list[dict[str, object]]:
    with psycopg.connect(DATABASE_URL, row_factory=dict_row) as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT journal_position, event_id, schema_version, event_type, source,
                       source_event_id, subject_key, occurred_at, recorded_at,
                       source_sequence, correlation_id, causation_id, confidence,
                       evidence_kind, importance, delivery_class, payload, metadata
                FROM anima_event_journal WHERE event_id LIKE %s
                ORDER BY journal_position
                """,
                (f"phase7-{run_id}-%",),
            )
            return list(cursor.fetchall())


def count_run_events(run_id: str) -> int:
    with psycopg.connect(DATABASE_URL, row_factory=dict_row) as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT count(*) AS count FROM anima_event_journal WHERE event_id LIKE %s",
                (f"phase7-{run_id}-%",),
            )
            row = cursor.fetchone()
            assert row is not None
            return int(row["count"])


def max_position() -> int:
    with psycopg.connect(DATABASE_URL, row_factory=dict_row) as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT COALESCE(max(journal_position), 0) AS position FROM anima_event_journal"
            )
            row = cursor.fetchone()
            assert row is not None
            return int(row["position"])


def main() -> int:
    wait_for_database()
    migrate(DATABASE_URL, 5)
    run_id = str(uuid4())[:8]
    base = datetime(2026, 8, 29, 22, 0, tzinfo=UTC)
    document = sample_household_document()
    household_id = next(
        node.canonical_id for node in document.nodes if node.name == "Sample Household"
    )
    entrance_id = next(node.canonical_id for node in document.nodes if node.name == "Front Door")
    graph = PostgresHouseholdGraph(DATABASE_URL)
    graph.commission(document)

    reality = PostgresRealityStore(DATABASE_URL)
    observation = TruthObservation(
        truth_key="opening/front-entrance/contact",
        source="phase7-context",
        observed_at=base - timedelta(minutes=1),
        received_at=base - timedelta(minutes=1),
        state=ObservationState.KNOWN,
        value="OPEN",
        confidence=0.99,
        freshness_seconds=600,
    )
    truth_event_id = f"phase7-context-truth-{run_id}"
    reality.ingest(
        EventEnvelope.create(
            event_id=truth_event_id,
            event_type="truth.observation",
            source="phase7-context",
            subject_key=observation.truth_key,
            occurred_at=observation.observed_at,
            recorded_at=observation.received_at,
            payload=observation.to_payload(),
            source_event_id=truth_event_id,
        )
    )
    memory = MemoryService(DATABASE_URL)
    memory.create(
        MemoryRecord.create(
            household_id=household_id,
            memory_type=MemoryType.EXPLICIT_PREFERENCE,
            content="Notify me about unusual front door activity.",
            provenance=MemoryProvenance(
                ProvenanceKind.EXPLICIT_INPUT, f"phase7-interaction-{run_id}"
            ),
            created_at=base - timedelta(hours=1),
            graph_refs=(entrance_id,),
        )
    )
    routine = RoutineService(DATABASE_URL)
    for index in range(4):
        event_id = f"phase7-routine-{run_id}-{index}"
        at = base - timedelta(days=index + 1)
        routine.journal.append(
            EventEnvelope.create(
                event_id=event_id,
                event_type="routine.activity_observation",
                source=f"phase7-routine-{run_id}",
                subject_key=f"routine/household/{household_id}",
                occurred_at=at,
                recorded_at=at,
                payload={"active": False, "bucket": "22:00"},
                source_event_id=event_id,
            )
        )
    routine.rebuild_activity_model(household_id, source=f"phase7-routine-{run_id}", now=base)

    start_position = max_position()
    profile = default_attention_profile(f"phase7.integration.{run_id}")
    consumer = f"phase7-integration-{run_id}"
    attention = PostgresAttentionService(DATABASE_URL)
    attention.register_profile(profile)
    with psycopg.connect(DATABASE_URL) as connection, connection.cursor() as cursor:
        cursor.execute(
            """
            INSERT INTO anima_attention_cursors
                (consumer_name, profile_version, last_position)
            VALUES (%s, %s, %s)
            """,
            (consumer, profile.profile_version, start_position),
        )
        connection.commit()

    journal = PostgresEventJournal(DATABASE_URL)
    ordinary_ids, guaranteed_ids = append_high_volume(
        journal,
        run_id=run_id,
        household_id=household_id,
        entrance_id=entrance_id,
        base=base,
    )
    first = attention.process(profile, consumer_name=consumer, limit=5_000)
    assert first.processed == 5_000 and first.failed_position is None
    halfway_cursor = attention.cursor(consumer)
    assert halfway_cursor > start_position

    restarted = PostgresAttentionService(DATABASE_URL)
    second = restarted.process(
        profile,
        consumer_name=consumer,
        limit=20_000,
        flush_due_at=base + timedelta(minutes=5),
    )
    assert second.processed == 5_020 and second.failed_position is None
    triggers = restarted.list_triggers(profile.profile_version)
    aggregate_triggers = [trigger for trigger in triggers if trigger.trigger_type == "AGGREGATE"]
    guaranteed_triggers = [
        trigger
        for trigger in triggers
        if set(trigger.source_event_ids).intersection(guaranteed_ids)
    ]
    assert len(aggregate_triggers) == 4
    assert len(guaranteed_triggers) == 20
    assert len(triggers) == 24
    assert sum(len(trigger.source_event_ids) for trigger in aggregate_triggers) == 10_000
    assert {
        event_id for trigger in guaranteed_triggers for event_id in trigger.source_event_ids
    } == set(guaranteed_ids)
    assert count_run_events(run_id) == 10_020

    rows = rows_for_run(run_id)
    journal_before_replay = count_run_events(run_id)
    replay = AttentionReplay().evaluate(profile, rows, flush_at=base + timedelta(minutes=5))
    assert {trigger.trigger_id for trigger in replay.triggers} == {
        trigger.trigger_id for trigger in triggers
    }
    assert count_run_events(run_id) == journal_before_replay

    user_event_id = guaranteed_ids[0]
    user_trigger = next(
        trigger for trigger in triggers if user_event_id in trigger.source_event_ids
    )
    tool = ToolDescriptor(
        "anima.synthetic.home.read_front_door",
        "anima.synthetic.home",
        "home.synthetic",
        "read_front_door",
        "Read synthetic front-door state",
        {"type": "object", "additionalProperties": False},
        {"type": "object"},
        "READ_ONLY",
        "query_state",
        True,
        Idempotency.IDEMPOTENT,
        2.0,
        "NONE",
        ExternalContentTrust.LOCAL_TRUSTED,
        True,
        "1.0.0",
        "phase7-synthetic",
        ("ENTRANCE",),
        (),
        ("front-door",),
    )
    broker = ContextBroker(DATABASE_URL)
    assembled_at = base + timedelta(minutes=5)
    packet = broker.assemble(
        user_trigger,
        household_id=household_id,
        tools=[tool],
        assembled_at=assembled_at,
    )
    persisted = broker.load(user_trigger.trigger_id)
    assert persisted is not None and persisted["digest"] == packet.digest
    replayed_packet = broker.assemble(
        user_trigger,
        household_id=household_id,
        tools=[tool],
        assembled_at=assembled_at,
        persist=False,
    )
    assert replayed_packet.digest == packet.digest
    packet_text = json.dumps(packet.to_payload(), sort_keys=True)
    assert "Front Door" in packet_text and "Front Door Contact" in packet_text
    assert "Notify me about unusual front door activity" in packet_text
    assert "probabilistic" in packet_text and "INFERRED" in packet_text
    assert "Bedroom" not in packet_text
    assert "read_front_door" in packet_text
    assert "NOT_EVALUATED" in packet_text
    assert "password" not in packet_text.casefold() and "api_key" not in packet_text.casefold()
    assert packet.cloud_safe_projection()

    profile_b = AttentionProfile(
        f"phase7.integration.compare.{run_id}",
        (
            AttentionRule(
                "ordinary_motion_30s",
                RuleAction.AGGREGATE,
                event_types=("household.motion",),
                aggregation_window_seconds=30,
                priority=35,
            ),
        ),
    )
    comparison = AttentionReplay().compare(
        profile, profile_b, rows, flush_at=base + timedelta(minutes=5)
    )
    assert comparison["guaranteed_lost_a"] == []
    assert comparison["guaranteed_lost_b"] == []
    assert comparison["trigger_count_a"] == 24
    assert comparison["trigger_count_b"] == 28
    replay_b = AttentionReplay().evaluate(profile_b, rows, flush_at=base + timedelta(minutes=5))
    bytes_a = sum(
        broker.assemble(
            trigger,
            household_id=household_id,
            assembled_at=assembled_at,
            persist=False,
        ).serialized_bytes
        for trigger in replay.triggers
    )
    bytes_b = sum(
        broker.assemble(
            trigger,
            household_id=household_id,
            assembled_at=assembled_at,
            persist=False,
        ).serialized_bytes
        for trigger in replay_b.triggers
    )

    subprocess.run(["docker", "compose", "restart", "db"], check=True)
    wait_for_database()
    after_restart = PostgresAttentionService(DATABASE_URL)
    assert after_restart.cursor(consumer) == second.last_position
    assert ContextBroker(DATABASE_URL).load(user_trigger.trigger_id)["digest"] == packet.digest  # type: ignore[index]

    metrics = after_restart.metrics(profile.profile_version)
    print("PHASE7_POSTGRES_INTEGRATION_PASS")
    print(f"run_id={run_id}")
    print(f"journal_events=10020 ordinary={len(ordinary_ids)} guaranteed={len(guaranteed_ids)}")
    print("restart_midstream=PASS cursor_preserved=PASS")
    print("expected_aggregate_triggers=4 actual_aggregate_triggers=4")
    print("expected_guaranteed_triggers=20 actual_guaranteed_triggers=20")
    print("expected_total_triggers=24 actual_total_triggers=24")
    print(f"replay_equivalence=PASS trigger_count={len(replay.triggers)}")
    print(f"context_digest={packet.digest} serialized_bytes={packet.serialized_bytes}")
    print("context_relevance=PASS unrelated_bedroom_excluded=PASS")
    print("truth_memory_routine_identity_tool_context=PASS")
    print("secret_egress_boundary=PASS")
    print(
        f"profile_comparison=PASS triggers_a=24 triggers_b=28 "
        f"context_bytes_a={bytes_a} context_bytes_b={bytes_b}"
    )
    print(f"metrics={json.dumps(metrics, sort_keys=True)}")
    print("postgres_restart_persistence=PASS")
    print("evidence=POSTGRESQL_INTEGRATION_SYNTHETIC_NO_LUNA_NO_ACTIONS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
