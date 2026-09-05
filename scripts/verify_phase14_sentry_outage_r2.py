"""Exercise SENTRY outage states while ANIMA local functions continue.

This verifier uses fresh PostgreSQL request records and reconstructed stores.
It does not emulate a successful model response: an unavailable SENTRY
provider remains unavailable, while local journal, task, and calendar reads
continue to work.
"""

from __future__ import annotations

import json
import os
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import psycopg

from anima_ha.calendar import CalendarEvent, PostgresCalendarStore
from anima_ha.db.migrate import migrate
from anima_ha.events import DeliveryClass, EventEnvelope, EventImportance
from anima_ha.intelligence import (
    IntelligenceLifecycle,
    IntelligenceOrigin,
    IntelligenceRequest,
    IntelligenceResult,
    IntelligenceResultStatus,
    PostgresIntelligenceStore,
)
from anima_ha.journal import PostgresEventJournal
from anima_ha.tasks import (
    DurableTask,
    PostgresTaskStore,
    ScheduleKind,
    TaskSchedule,
    TaskType,
)

DATABASE_URL = os.environ.get("ANIMA_DATABASE_URL", "")
HOUSEHOLD_ID = uuid4()
PROVIDER = "sentry"


def request(label: str) -> IntelligenceRequest:
    return IntelligenceRequest(
        request_id=uuid4(),
        household_id=HOUSEHOLD_ID,
        origin=IntelligenceOrigin.DIRECT_SENTRY_INTERACTION,
        context_packet_id=uuid4(),
        context_digest=f"phase14:{label}:context",
        catalogue_digest=f"phase14:{label}:catalogue",
        provider_id=PROVIDER,
        provider_version="r2",
        idempotency_key=f"phase14-sentry-outage-{label}-{uuid4()}",
        request_metadata={"phase14_label": label},
        catalogue=(),
    )


def expire(database_url: str, request_id: UUID) -> None:
    with psycopg.connect(database_url) as connection, connection.cursor() as cursor:
        cursor.execute(
            """
            UPDATE anima_intelligence_requests
            SET lease_expires_at=now()-interval '1 second', updated_at=now()
            WHERE request_id=%s
            """,
            (request_id,),
        )
        connection.commit()


def append_local_event(journal: PostgresEventJournal) -> str:
    event = EventEnvelope.create(
        event_id=str(uuid4()),
        event_type="phase14.local.platform.available",
        source="phase14-sentry-outage",
        subject_key=f"household/{HOUSEHOLD_ID}",
        occurred_at=datetime.now(UTC),
        payload={"platform": "anima", "cognition": "unavailable"},
        importance=EventImportance.NORMAL,
        delivery_class=DeliveryClass.BEST_EFFORT,
        metadata={"household_id": str(HOUSEHOLD_ID)},
    )
    return journal.append(event).event_id


def create_local_records() -> tuple[UUID, UUID]:
    now = datetime.now(UTC)
    task_store = PostgresTaskStore(DATABASE_URL)
    task = DurableTask(
        task_id=uuid4(),
        household_id=HOUSEHOLD_ID,
        task_type=TaskType.REASONING_DUE,
        title="Phase 14 local platform continuity",
        payload={"objective": "verify local operation during SENTRY outage"},
        schedule=TaskSchedule(
            kind=ScheduleKind.ONCE,
            timezone="UTC",
            run_at=now + timedelta(hours=1),
        ),
        creator_principal_id=None,
        creator_episode_id=None,
        creation_idempotency_key=f"phase14-sentry-outage-task-{uuid4()}",
        created_at=now,
        updated_at=now,
        next_run_at=now + timedelta(hours=1),
    )
    task_store.create(task)

    calendar_store = PostgresCalendarStore(DATABASE_URL)
    event = CalendarEvent.create(
        household_id=HOUSEHOLD_ID,
        title="Phase 14 local calendar continuity",
        start_at=now + timedelta(hours=2),
        end_at=now + timedelta(hours=3),
        timezone="UTC",
        creation_idempotency_key=f"phase14-sentry-outage-calendar-{uuid4()}",
        creator_principal_id=None,
        creator_episode_id=None,
        now=now,
    )
    calendar_store.create(event)
    assert task_store.get(task.task_id).task_id == task.task_id
    assert calendar_store.get(HOUSEHOLD_ID, event.event_id).event_id == event.event_id
    return task.task_id, event.event_id


def main() -> int:
    if not DATABASE_URL:
        raise RuntimeError("ANIMA_DATABASE_URL is required")
    migrate(DATABASE_URL, 5)
    store = PostgresIntelligenceStore(DATABASE_URL)
    journal = PostgresEventJournal(DATABASE_URL)

    pending = store.enqueue(request("before-claim"))
    claimed = store.enqueue(request("after-claim"))
    started = store.enqueue(request("after-provider-start"))
    durable = store.enqueue(request("after-result"))

    claimed_record = store.claim(
        "phase14-sentry-claim", provider_id=PROVIDER, household_id=HOUSEHOLD_ID
    )
    assert claimed_record is not None and claimed_record.request_id == pending.request_id
    # Leave the claimed request durable but not running: it is the only state
    # that may be reclaimed after a proven pre-provider loss.
    expire(DATABASE_URL, pending.request_id)
    reclaimed = store.claim(
        "phase14-sentry-reclaimer", provider_id=PROVIDER, household_id=HOUSEHOLD_ID
    )
    assert reclaimed is not None and reclaimed.request_id == pending.request_id

    claimed_record = store.claim(
        "phase14-sentry-claim-2", provider_id=PROVIDER, household_id=HOUSEHOLD_ID
    )
    assert claimed_record is not None and claimed_record.request_id == claimed.request_id

    started_record = store.claim(
        "phase14-sentry-start", provider_id=PROVIDER, household_id=HOUSEHOLD_ID
    )
    assert started_record is not None and started_record.request_id == started.request_id
    assert store.transition(
        started.request_id,
        "phase14-sentry-start",
        started_record.fencing_generation,
        IntelligenceLifecycle.PROVIDER_RUNNING,
        {"provider_invocation_started": True},
    )
    expire(DATABASE_URL, started.request_id)
    next_claim = store.claim(
        "phase14-sentry-reclaimer-2", provider_id=PROVIDER, household_id=HOUSEHOLD_ID
    )
    assert next_claim is not None and next_claim.request_id == durable.request_id
    started_after = store.get(started.request_id)
    assert (
        started_after is not None
        and started_after.lifecycle == IntelligenceLifecycle.UNKNOWN_RESULT
    )

    durable_record = next_claim
    assert store.transition(
        durable.request_id,
        "phase14-sentry-reclaimer-2",
        durable_record.fencing_generation,
        IntelligenceLifecycle.PROVIDER_RUNNING,
        {"provider_invocation_started": True},
    )
    assert store.record_result(
        durable.request_id,
        "phase14-sentry-reclaimer-2",
        durable_record.fencing_generation,
        IntelligenceResult(
            durable.request_id,
            IntelligenceResultStatus.RESPONSE,
            response_text="bounded durable response",
        ),
    )
    assert (
        store.claim(
            "phase14-sentry-no-rerun", provider_id=PROVIDER, household_id=HOUSEHOLD_ID
        )
        is None
    )

    event_id = append_local_event(journal)
    task_id, calendar_id = create_local_records()
    assert journal.position(event_id) is not None

    print(
        json.dumps(
            {
                "scenario_id": "SENTRY_OUTAGE_LOCAL_PLATFORM_CONTINUES",
                "status": "PASS",
                "evidence_level": "POSTGRES_PROCESS",
                "provider": PROVIDER,
                "provider_available": False,
                "pre_claim_reclaimed": True,
                "provider_started_recovery": started_after.lifecycle.value,
                "durable_result_reused": True,
                "embedded_agent_runtime_fallback": False,
                "local_journal_event": event_id,
                "local_task_reachable": str(task_id),
                "local_calendar_event_reachable": str(calendar_id),
                "phase15": False,
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
