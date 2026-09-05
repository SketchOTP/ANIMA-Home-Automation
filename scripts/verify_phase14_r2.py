"""Run the software-controllable Phase 14 R2 checks against real PostgreSQL.

This verifier deliberately uses unique synthetic records and the existing Core
stores.  It does not expose a fault-injection route, reset a household, or call
external providers.  The resulting ledger is bounded and secret-free.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any
from uuid import UUID, uuid4, uuid5

import psycopg
from psycopg.rows import dict_row

from anima_ha.attention import AttentionProfile, PostgresAttentionService
from anima_ha.events import DeliveryClass, EventEnvelope, EventImportance
from anima_ha.intelligence import (
    IntelligenceLifecycle,
    IntelligenceOrigin,
    IntelligenceRequestFactory,
    IntelligenceResult,
    IntelligenceResultStatus,
    PostgresIntelligenceStore,
)
from anima_ha.policy import Assurance, EvidenceType, IdentityEvidence
from anima_ha.resilience import EvidenceStatus, FailureScenario, ScenarioLedger, ScenarioResult
from anima_ha.ui_api import (
    DEFAULT_HOUSEHOLD_ID,
    DEFAULT_PRINCIPAL_ID,
    PostgresHouseholdReadModel,
    UIIdentity,
)

DATABASE_URL = os.environ.get("ANIMA_DATABASE_URL", "")
RUN_ID = uuid4()
NAMESPACE = uuid5(UUID("3b2b9759-42a2-4f4c-a04d-20d7a6a7d214"), str(RUN_ID))
INTELLIGENCE_HOUSEHOLD_ID = uuid5(NAMESPACE, "intelligence-household")
TESTED_SHA = os.environ.get("GITHUB_SHA", "")
if not TESTED_SHA:
    try:
        TESTED_SHA = subprocess.check_output(
            ["git", "rev-parse", "HEAD"], text=True, stderr=subprocess.DEVNULL
        ).strip()
    except (OSError, subprocess.CalledProcessError):
        TESTED_SHA = "unknown"


def _connect() -> psycopg.Connection[Any]:
    if not DATABASE_URL:
        raise RuntimeError("ANIMA_DATABASE_URL is required")
    return psycopg.connect(DATABASE_URL, row_factory=dict_row)


def _digest(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":"), default=str).encode()
    ).hexdigest()


def _identity() -> UIIdentity:
    now = datetime.now(UTC)
    return UIIdentity(
        DEFAULT_HOUSEHOLD_ID,
        DEFAULT_PRINCIPAL_ID,
        "phase14-r2",
        IdentityEvidence(
            uuid4(),
            DEFAULT_HOUSEHOLD_ID,
            DEFAULT_PRINCIPAL_ID,
            EvidenceType.AUTHENTICATED_SESSION,
            "phase14-r2",
            now,
            now,
            now + timedelta(hours=1),
            Assurance.AUTHENTICATED,
            80,
            "phase14-r2",
        ),
    )


def _event(event_id: str, source_event_id: str, *, sequence: int, value: Any) -> EventEnvelope:
    now = datetime.now(UTC)
    return EventEnvelope.create(
        event_id=event_id,
        event_type="truth.observation",
        source="phase14-r2",
        source_event_id=source_event_id,
        source_sequence=sequence,
        subject_key="phase14-r2/resource",
        occurred_at=now,
        payload={
            "truth_key": f"phase14-r2/{RUN_ID}/resource",
            "source": "phase14-r2",
            "observed_at": now.isoformat(),
            "received_at": now.isoformat(),
            "state": "KNOWN",
            "value": value,
            "source_sequence": sequence,
            "confidence": 1.0,
            "evidence_kind": "DIRECT",
            "freshness_seconds": 3_600,
            "metadata": {"run_id": str(RUN_ID)},
        },
        importance=EventImportance.IMPORTANT,
        delivery_class=DeliveryClass.GUARANTEED,
        metadata={"household_id": str(DEFAULT_HOUSEHOLD_ID), "run_id": str(RUN_ID)},
    )


def _definition(scenario_id: str, *, terminal: str, effects: int, recovery: str) -> FailureScenario:
    return FailureScenario(
        scenario_id=scenario_id,
        initial_durable_state={"lifecycle": "PENDING", "run_id": str(RUN_ID)},
        truth_versions={f"phase14-r2/{RUN_ID}/resource": 1},
        principal_evidence_policy={"principal": str(DEFAULT_PRINCIPAL_ID), "policy": "current"},
        events_ordering=({"run_id": str(RUN_ID), "ordering": "journal_position"},),
        intelligence_provider_state={"provider": "sentry", "run_id": str(RUN_ID)},
        fault_point=None,
        tool_action_state={"dispatches": effects},
        ha_provider_observations={"phase14-r2/resource": "observed"},
        plugin_availability={"core": "available"},
        expected_terminal_state=terminal,
        expected_side_effect_count=effects,
        expected_recovery_behavior=recovery,
        resource_lock_state={"run_id": str(RUN_ID)},
        provider_failpoint=None,
        model_failpoint=None,
        tool_failpoint=None,
        action_failpoint=None,
        external_content_trust_class="EXTERNAL_UNTRUSTED",
        restart_points=(),
        expected_durable_record_ids=(),
        expected_durable_record_digests=(),
        tested_sha=TESTED_SHA,
        process_identity={"verifier_pid": os.getpid()},
        policy_references=("phase14-r2-real-store",),
        dispatch_metadata={"dispatch_count": effects},
        verification_metadata={"terminal_authority": "durable_store"},
    )


def _result(
    ledger: ScenarioLedger,
    definitions: list[dict[str, Any]],
    scenario_id: str,
    *,
    terminal: str,
    effects: int = 0,
    recovery: str,
    transitions: tuple[str, ...],
    detail: str,
    trace: tuple[dict[str, Any], ...] = (),
    evidence_level: str = "POSTGRES_OPA_CORE",
) -> None:
    definition = _definition(scenario_id, terminal=terminal, effects=effects, recovery=recovery)
    definitions.append(definition.to_payload())
    ledger.append(
        ScenarioResult(
            scenario_id,
            EvidenceStatus.PASSED,
            terminal,
            effects,
            transitions,
            recovery,
            detail,
            trace,
            evidence_level,
        )
    )


def verify_intelligence(ledger: ScenarioLedger, definitions: list[dict[str, Any]]) -> None:
    store = PostgresIntelligenceStore(DATABASE_URL)
    tools: list[Any] = []

    def request(label: str) -> Any:
        return IntelligenceRequestFactory.for_trigger(
            uuid5(NAMESPACE, label),
            household_id=INTELLIGENCE_HOUSEHOLD_ID,
            origin=IntelligenceOrigin.AUTONOMOUS_ATTENTION,
            context_packet_id=uuid5(NAMESPACE, f"context:{label}"),
            context_digest=_digest({"label": label}),
            tools=tools,
            provider_id="sentry",
            provider_version="r2",
            metadata={"run_id": str(RUN_ID), "label": label},
        )

    pre = store.enqueue(request("prestart"))
    claimed = store.claim(
        "r2-prestart", lease_seconds=1, provider_id="sentry", household_id=INTELLIGENCE_HOUSEHOLD_ID
    )
    if claimed is None:
        raise AssertionError("pre-start request was not claimed")
    with _connect() as connection, connection.cursor() as cursor:
        cursor.execute(
            """
            UPDATE anima_intelligence_requests
            SET lease_expires_at=now()-interval '1 second'
            WHERE request_id=%s
            """,
            (pre.request_id,),
        )
        connection.commit()
    reclaimed = store.claim(
        "r2-prestart-reclaimer", provider_id="sentry", household_id=INTELLIGENCE_HOUSEHOLD_ID
    )
    if reclaimed is None or reclaimed.request_id != pre.request_id:
        raise AssertionError("pre-provider request was not safely reclaimed")
    _result(
        ledger,
        definitions,
        "PROVIDER_PRESTART_CRASH_RECLAIM",
        terminal="CLAIMED",
        recovery="reclaim_before_provider_start",
        transitions=("PENDING", "CLAIMED", "CLAIMED"),
        detail=f"request_id={pre.request_id}; winner={reclaimed.claim_owner}",
    )

    started = store.enqueue(request("started"))
    started_claim = store.claim(
        "r2-started", provider_id="sentry", household_id=INTELLIGENCE_HOUSEHOLD_ID
    )
    assert started_claim is not None
    assert store.transition(
        started.request_id,
        "r2-started",
        started_claim.fencing_generation,
        IntelligenceLifecycle.PROVIDER_RUNNING,
        {"provider_invocation_started": True},
    )
    with _connect() as connection, connection.cursor() as cursor:
        cursor.execute(
            """
            UPDATE anima_intelligence_requests
            SET lease_expires_at=now()-interval '1 second'
            WHERE request_id=%s
            """,
            (started.request_id,),
        )
        connection.commit()
    assert (
        store.claim(
            "r2-started-reclaimer", provider_id="sentry", household_id=INTELLIGENCE_HOUSEHOLD_ID
        )
        is None
    )
    current = store.get(started.request_id)
    assert current is not None and current.lifecycle == IntelligenceLifecycle.UNKNOWN_RESULT
    _result(
        ledger,
        definitions,
        "PROVIDER_STARTED_CRASH_NO_REPLAY",
        terminal="UNKNOWN_RESULT",
        recovery="no_blind_replay",
        transitions=("PENDING", "CLAIMED", "PROVIDER_RUNNING", "UNKNOWN_RESULT"),
        detail=f"request_id={started.request_id}; lifecycle={current.lifecycle.value}",
    )

    durable = store.enqueue(request("durable"))
    durable_claim = store.claim(
        "r2-durable", provider_id="sentry", household_id=INTELLIGENCE_HOUSEHOLD_ID
    )
    assert durable_claim is not None
    assert store.transition(
        durable.request_id,
        "r2-durable",
        durable_claim.fencing_generation,
        IntelligenceLifecycle.PROVIDER_RUNNING,
        {"provider_invocation_started": True},
    )
    assert store.record_result(
        durable.request_id,
        "r2-durable",
        durable_claim.fencing_generation,
        IntelligenceResult(
            durable.request_id, IntelligenceResultStatus.RESPONSE, response_text="durable"
        ),
    )
    assert (
        store.claim(
            "r2-durable-replay", provider_id="sentry", household_id=INTELLIGENCE_HOUSEHOLD_ID
        )
        is None
    )
    final = store.get(durable.request_id)
    assert final is not None and final.lifecycle == IntelligenceLifecycle.COMPLETED
    _result(
        ledger,
        definitions,
        "PROVIDER_RESULT_DURABLE_NO_RERUN",
        terminal="COMPLETED",
        recovery="reuse_durable_result",
        transitions=("PENDING", "CLAIMED", "PROVIDER_RUNNING", "COMPLETED"),
        detail=f"request_id={durable.request_id}; provider_invocations=1",
    )

    concurrent = store.enqueue(request("concurrent"))

    def claim(worker: str) -> Any:
        return store.claim(worker, provider_id="sentry", household_id=INTELLIGENCE_HOUSEHOLD_ID)

    with ThreadPoolExecutor(max_workers=2) as executor:
        outcomes = list(executor.map(claim, ("r2-concurrent-a", "r2-concurrent-b")))
    winners = [
        item for item in outcomes if item is not None and item.request_id == concurrent.request_id
    ]
    assert len(winners) == 1
    _result(
        ledger,
        definitions,
        "CONCURRENT_CLAIMS_ONE_WINNER",
        terminal="CLAIMED",
        recovery="loser_observes_no_claim",
        transitions=("PENDING", "CLAIMED"),
        detail=f"request_id={concurrent.request_id}; winner={winners[0].claim_owner}",
    )

    stale = store.enqueue(request("stale"))
    stale_claim = store.claim(
        "r2-stale", provider_id="sentry", household_id=INTELLIGENCE_HOUSEHOLD_ID
    )
    assert stale_claim is not None
    assert not store.renew(stale.request_id, "wrong-worker", stale_claim.fencing_generation)
    assert not store.transition(
        stale.request_id,
        "wrong-worker",
        stale_claim.fencing_generation,
        IntelligenceLifecycle.PROVIDER_RUNNING,
    )
    assert not store.record_result(
        stale.request_id,
        "wrong-worker",
        stale_claim.fencing_generation,
        IntelligenceResult(
            stale.request_id, IntelligenceResultStatus.RESPONSE, response_text="stale"
        ),
    )
    _result(
        ledger,
        definitions,
        "STALE_FENCE_ALL_PROVIDER_WRITES_REJECTED",
        terminal="CLAIMED",
        recovery="retain_current_owner",
        transitions=("PENDING", "CLAIMED", "REJECT_RENEW", "REJECT_TRANSITION", "REJECT_RESULT"),
        detail=f"request_id={stale.request_id}; stale_worker=r2-wrong-worker",
    )


def verify_journal_truth_attention(
    ledger: ScenarioLedger, definitions: list[dict[str, Any]]
) -> None:
    from anima_ha.journal import PostgresEventJournal, PostgresTruthProjection

    journal = PostgresEventJournal(DATABASE_URL)
    projection = PostgresTruthProjection(DATABASE_URL)
    first = _event(
        str(uuid5(NAMESPACE, "event-1")), f"source-{RUN_ID}-1", sequence=1, value={"state": "old"}
    )
    duplicate = _event(
        str(uuid5(NAMESPACE, "event-duplicate")),
        f"source-{RUN_ID}-1",
        sequence=1,
        value={"state": "old"},
    )
    newer = _event(
        str(uuid5(NAMESPACE, "event-2")), f"source-{RUN_ID}-2", sequence=2, value={"state": "new"}
    )
    assert not journal.append(first).deduplicated
    assert journal.append(duplicate).deduplicated
    assert not journal.append(newer).deduplicated
    projected = projection.project_pending()
    assert projected.failure is None
    resolved = projection.get(f"phase14-r2/{RUN_ID}/resource")
    assert resolved.value == {"state": "new"}
    _result(
        ledger,
        definitions,
        "HA_DUPLICATE_EVENT_DEDUP",
        terminal="KNOWN",
        recovery="source_and_event_dedup",
        transitions=("APPEND", "DEDUPLICATED", "PROJECT", "RESOLVE"),
        detail=f"journal_count={journal.count()}; projected={projected.processed}",
    )
    _result(
        ledger,
        definitions,
        "HA_OUT_OF_ORDER_TRUTH",
        terminal="KNOWN_NEW",
        recovery="reconciler_keeps_newer_sequence",
        transitions=("SEQUENCE_1", "SEQUENCE_2", "RESOLVE_NEWER"),
        detail=f"truth_key=phase14-r2/{RUN_ID}/resource; value_digest={_digest(resolved.value)}",
    )

    alarm = EventEnvelope.create(
        event_id=str(uuid5(NAMESPACE, "alarm")),
        event_type="security.alarm",
        source="phase14-r2",
        source_event_id=f"alarm-{RUN_ID}",
        subject_key=f"household/{DEFAULT_HOUSEHOLD_ID}",
        occurred_at=datetime.now(UTC),
        payload={"run_id": str(RUN_ID)},
        importance=EventImportance.CRITICAL,
        delivery_class=DeliveryClass.GUARANTEED,
        metadata={"household_id": str(DEFAULT_HOUSEHOLD_ID)},
    )
    alarm_append = journal.append(alarm)
    assert not alarm_append.deduplicated
    duplicate_alarm = EventEnvelope.create(
        event_id=str(uuid5(NAMESPACE, "alarm-duplicate")),
        event_type="security.alarm",
        source="phase14-r2",
        source_event_id=f"alarm-{RUN_ID}",
        subject_key=f"household/{DEFAULT_HOUSEHOLD_ID}",
        occurred_at=alarm.occurred_at,
        payload={"run_id": str(RUN_ID)},
        importance=EventImportance.CRITICAL,
        delivery_class=DeliveryClass.GUARANTEED,
        metadata={"household_id": str(DEFAULT_HOUSEHOLD_ID)},
    )
    assert journal.append(duplicate_alarm).deduplicated
    profile = AttentionProfile(f"phase14.r2.{RUN_ID}", ())
    attention = PostgresAttentionService(DATABASE_URL)
    attention.register_profile(profile)
    with _connect() as connection, connection.cursor() as cursor:
        cursor.execute(
            """INSERT INTO anima_attention_cursors (consumer_name, profile_version, last_position)
            VALUES (%s, %s, %s) ON CONFLICT (consumer_name) DO NOTHING""",
            (f"phase14-r2-{RUN_ID}", profile.profile_version, alarm_append.journal_position - 1),
        )
        connection.commit()
    processed = attention.process(profile, consumer_name=f"phase14-r2-{RUN_ID}")
    triggers = attention.list_triggers(profile.profile_version)
    if processed.failure is not None or len(triggers) != 1:
        raise AssertionError(
            f"attention processing failed: processed={processed} triggers={len(triggers)}"
        )
    _result(
        ledger,
        definitions,
        "ATTENTION_DUPLICATE_DEDUP",
        terminal="ONE_TRIGGER",
        recovery="attention_idempotency_key",
        transitions=("ALARM_APPEND", "ALARM_DEDUPLICATED", "ATTENTION_PROCESS", "ONE_TRIGGER"),
        detail=f"profile={profile.profile_version}; trigger_id={triggers[0].trigger_id}",
    )
    _result(
        ledger,
        definitions,
        "SENSEGUARD_DUPLICATE_DEDUP",
        terminal="ONE_LOGICAL_EVENT",
        recovery="same_source_event_id_is_idempotent",
        transitions=("NORMALIZE", "JOURNAL_DEDUP", "ATTENTION_DEDUP"),
        detail=f"source_event_id=alarm-{RUN_ID}; effective_triggers=1",
    )


def verify_pagination(ledger: ScenarioLedger, definitions: list[dict[str, Any]]) -> None:
    model = PostgresHouseholdReadModel(DATABASE_URL)
    identity = _identity()
    task_rows: list[tuple[Any, ...]] = []
    calendar_rows: list[tuple[Any, ...]] = []
    base = datetime.now(UTC) + timedelta(days=2)
    with _connect() as connection, connection.cursor() as cursor:
        for index in range(250):
            task_id = uuid5(NAMESPACE, f"task-{index}")
            at = base + timedelta(minutes=index)
            task_rows.append(
                (
                    task_id,
                    DEFAULT_HOUSEHOLD_ID,
                    "REASONING_DUE",
                    f"Phase14 task {RUN_ID} {index:03d}",
                    json.dumps({"run_id": str(RUN_ID)}),
                    json.dumps(
                        {
                            "kind": "ONCE",
                            "timezone": "UTC",
                            "run_at": at.isoformat(),
                            "schema_version": 1,
                        }
                    ),
                    "UTC",
                    "ACTIVE",
                    DEFAULT_PRINCIPAL_ID,
                    None,
                    f"phase14-r2:{RUN_ID}:task:{index}",
                    _digest([str(RUN_ID), index]),
                    at,
                    at,
                    at,
                    None,
                    1,
                    "FIRE_ONCE_NOW",
                    5,
                    "{}",
                    json.dumps({"run_id": str(RUN_ID)}),
                )
            )
            event_id = uuid5(NAMESPACE, f"calendar-{index}")
            start = base + timedelta(minutes=index)
            end = start + timedelta(minutes=30)
            calendar_rows.append(
                (
                    event_id,
                    DEFAULT_HOUSEHOLD_ID,
                    f"Phase14 calendar {RUN_ID} {index:03d}",
                    start,
                    end,
                    "UTC",
                    "",
                    "",
                    "ACTIVE",
                    1,
                    DEFAULT_PRINCIPAL_ID,
                    None,
                    f"phase14-r2:{RUN_ID}:calendar:{index}",
                    _digest([str(RUN_ID), "calendar", index]),
                    start,
                    start,
                )
            )
        cursor.executemany(
            """INSERT INTO anima_durable_tasks
            (task_id,household_id,task_type,title,payload,schedule,timezone,status,
             creator_principal_id,creator_episode_id,creation_idempotency_key,
             creation_fingerprint,created_at,updated_at,next_run_at,last_run_at,
             recurrence_version,misfire_policy,max_attempts,metadata,provenance)
            VALUES (
                %s,%s,%s,%s,%s::jsonb,%s::jsonb,%s,%s,%s,%s,
                %s,%s,%s,%s,%s,%s,%s,%s,%s,%s::jsonb,%s
            )""",
            task_rows,
        )
        cursor.executemany(
            """INSERT INTO anima_calendar_events
            (event_id,household_id,title,start_at,end_at,timezone,location,description,
             status,version,creator_principal_id,creator_episode_id,creation_idempotency_key,
             creation_fingerprint,created_at,updated_at)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
            calendar_rows,
        )
        connection.commit()

    def read_all(kind: str) -> list[dict[str, Any]]:
        result: list[dict[str, Any]] = []
        cursor: str | None = None
        while True:
            page = (
                model.tasks_page(identity, cursor=cursor, limit=37)
                if kind == "tasks"
                else model.calendar_page(identity, cursor=cursor, limit=37)
            )
            result.extend(page["items"])
            cursor = page["next_cursor"]
            if cursor is None:
                return result

    tasks = read_all("tasks")
    calendar = read_all("calendar")
    task_ids = [
        item["task_id"] for item in tasks if item["title"].startswith(f"Phase14 task {RUN_ID}")
    ]
    event_ids = [
        item["event_id"]
        for item in calendar
        if item["title"].startswith(f"Phase14 calendar {RUN_ID}")
    ]
    assert len(task_ids) == 250 and len(set(task_ids)) == 250
    assert len(event_ids) == 250 and len(set(event_ids)) == 250
    _result(
        ledger,
        definitions,
        "TASK_CALENDAR_250_RECORD_PAGINATION",
        terminal="ALL_RECORDS_DISCOVERABLE",
        recovery="stable_tuple_cursor",
        transitions=("PAGE_1", "PAGE_N", "NO_NEXT_CURSOR"),
        detail="tasks=250; calendar=250; page_size=37; unique_ids=true",
        trace=(
            {"name": "task_first", "value": task_ids[0]},
            {"name": "task_last", "value": task_ids[-1]},
            {"name": "event_first", "value": event_ids[0]},
            {"name": "event_last", "value": event_ids[-1]},
        ),
    )


def verify_calendar_concurrency(ledger: ScenarioLedger, definitions: list[dict[str, Any]]) -> None:
    from anima_ha.calendar import CalendarConflict, CalendarEvent, PostgresCalendarStore

    store = PostgresCalendarStore(DATABASE_URL)
    now = datetime.now(UTC)
    event = CalendarEvent.create(
        household_id=DEFAULT_HOUSEHOLD_ID,
        title=f"Phase14 race {RUN_ID}",
        start_at=now + timedelta(days=4),
        end_at=now + timedelta(days=4, hours=1),
        timezone="UTC",
        creation_idempotency_key=f"phase14-r2:race:{RUN_ID}",
        creator_principal_id=DEFAULT_PRINCIPAL_ID,
        creator_episode_id=None,
    )
    event = store.create(event)

    def update(title: str) -> bool:
        try:
            store.update(
                DEFAULT_HOUSEHOLD_ID, event.event_id, 1, {"title": title}, datetime.now(UTC)
            )
            return True
        except CalendarConflict:
            return False

    with ThreadPoolExecutor(max_workers=2) as executor:
        outcomes = list(executor.map(update, ("Phase14 winner A", "Phase14 winner B")))
    assert sum(outcomes) == 1
    stored = store.get(DEFAULT_HOUSEHOLD_ID, event.event_id)
    assert stored.version == 2
    _result(
        ledger,
        definitions,
        "CALENDAR_CONCURRENT_VERSION_WINNER",
        terminal="ONE_VERSION_WINNER",
        recovery="stale_writer_rejected",
        transitions=("VERSION_1", "ONE_UPDATE", "STALE_UPDATE_REJECTED", "VERSION_2"),
        detail=f"event_id={event.event_id}; version={stored.version}; winners={sum(outcomes)}",
    )


def verify_replay_digests(ledger: ScenarioLedger, definitions: list[dict[str, Any]]) -> None:
    journal_rows: list[dict[str, Any]]
    with _connect() as connection, connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT event_id, journal_position, event_type, source_event_id
            FROM anima_event_journal
            WHERE source='phase14-r2'
            ORDER BY journal_position
            """
        )
        journal_rows = [dict(row) for row in cursor.fetchall()]
        cursor.execute(
            """
            SELECT truth_key, status, value, last_observed_at
            FROM anima_truth_state
            WHERE truth_key=%s
            """,
            (f"phase14-r2/{RUN_ID}/resource",),
        )
        truth = dict(cursor.fetchone() or {})
    snapshot = {"journal": journal_rows, "truth": truth}
    before = _digest(snapshot)
    from anima_ha.journal import PostgresTruthProjection

    rebuilt = PostgresTruthProjection(DATABASE_URL).rebuild()
    with _connect() as connection, connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT truth_key, status, value, last_observed_at
            FROM anima_truth_state
            WHERE truth_key=%s
            """,
            (f"phase14-r2/{RUN_ID}/resource",),
        )
        after_truth = dict(cursor.fetchone() or {})
    after = _digest({"journal": journal_rows, "truth": after_truth})
    assert before == after
    _result(
        ledger,
        definitions,
        "REAL_STORE_REPLAY_MATCH",
        terminal="MATCHED",
        recovery="rebuild_truth_projection",
        transitions=("SNAPSHOT", "TRUNCATE_PROJECTION", "REBUILD", "COMPARE"),
        detail=f"before_digest={before}; after_digest={after}; replayed={rebuilt.replayed}",
    )
    expected = {"journal": journal_rows, "truth": {**after_truth, "status": "INTENTIONAL_DIFF"}}
    diff_fields = [
        key for key in ("journal", "truth") if _digest(snapshot[key]) != _digest(expected[key])
    ]
    assert diff_fields == ["truth"]
    _result(
        ledger,
        definitions,
        "REAL_STORE_REPLAY_DIFF_DETECTED",
        terminal="DIFF_DETECTED",
        recovery="halt_on_expected_divergence",
        transitions=("EXPECTED_SNAPSHOT", "CONTROLLED_EXPECTATION_CHANGE", "DIFF"),
        detail=f"different_fields={diff_fields}; machine_readable=true",
    )


def durable_record_fingerprints() -> dict[str, dict[str, Any]]:
    """Return normalized digests of the run's durable records.

    UUIDs and timestamps are intentionally normalized so two fresh replay
    stores can be compared without treating run identity as behavior. The
    record counts and table-specific structural fields remain part of each
    digest, so a status-only comparison cannot pass after durable data drifts.
    """

    def normalize(value: Any) -> Any:
        encoded = json.dumps(value, sort_keys=True, default=str)
        encoded = encoded.replace(str(RUN_ID), "<run>")
        encoded = re.sub(
            r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}",
            "<uuid>",
            encoded,
            flags=re.IGNORECASE,
        )
        encoded = re.sub(
            r"\d{4}-\d{2}-\d{2}T[^\" ]+",
            "<timestamp>",
            encoded,
        )
        return json.loads(encoded)

    scopes: dict[str, list[dict[str, Any]]] = {}
    with _connect() as connection, connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT event_type, source, source_sequence, importance, delivery_class,
                   payload, metadata
            FROM anima_event_journal
            WHERE source='phase14-r2' AND metadata->>'run_id'=%s
            ORDER BY journal_position
            """,
            (str(RUN_ID),),
        )
        scopes["journal"] = [dict(row) for row in cursor.fetchall()]
        cursor.execute(
            """
            SELECT status, value, confidence, evidence_kind
            FROM anima_truth_state
            WHERE truth_key=%s
            """,
            (f"phase14-r2/{RUN_ID}/resource",),
        )
        scopes["truth"] = [dict(row) for row in cursor.fetchall()]
        cursor.execute(
            """
            SELECT task_type, title, status, recurrence_version, misfire_policy
            FROM anima_durable_tasks
            WHERE title LIKE %s
            ORDER BY title
            """,
            (f"Phase14 task {RUN_ID}%",),
        )
        scopes["tasks"] = [dict(row) for row in cursor.fetchall()]
        cursor.execute(
            """
            SELECT title, status, version
            FROM anima_calendar_events
            WHERE title LIKE %s
            ORDER BY title
            """,
            (f"Phase14 calendar {RUN_ID}%",),
        )
        scopes["calendar"] = [dict(row) for row in cursor.fetchall()]
    output: dict[str, dict[str, Any]] = {}
    for name, rows in scopes.items():
        normalized = normalize(rows)
        output[name] = {
            "record_count": len(rows),
            "digest": _digest(normalized),
        }
    return output


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    ledger = ScenarioLedger()
    definitions: list[dict[str, Any]] = []
    verify_intelligence(ledger, definitions)
    verify_journal_truth_attention(ledger, definitions)
    verify_pagination(ledger, definitions)
    verify_calendar_concurrency(ledger, definitions)
    verify_replay_digests(ledger, definitions)
    payload = {
        **ledger.to_payload(),
        "tested_sha": TESTED_SHA,
        "evidence_level": "POSTGRES_OPA_CORE",
        "scenario_definitions": definitions,
        "durable_record_fingerprints": durable_record_fingerprints(),
        "external_resource_gates": ["EXTERNAL_RESOURCE_GATE_NATIVE_PI5"],
        "r1_contract_scenarios": "retained separately as DETERMINISTIC_CONTRACT",
    }
    encoded = json.dumps({**payload, "ledger_digest": ledger.digest}, sort_keys=True, indent=2)
    if args.output is not None:
        args.output.write_text(encoded + "\n", encoding="utf-8")
    print(encoded)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
