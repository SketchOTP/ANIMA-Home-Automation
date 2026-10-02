"""Qualify the real ANIMA Attention-to-SENTRY bridge restart boundary.

This target starts the actual ``anima_ha.sentry_bridge`` process, appends one
unique user request, and starts the process again.  It verifies that the
durable Attention cursor and request idempotency prevent a duplicate request.
It does not invoke a model and therefore makes no live-SENTRY claim.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID, uuid4

import psycopg

from anima_ha.attention import PostgresAttentionService, default_attention_profile
from anima_ha.db.migrate import migrate
from anima_ha.events import DeliveryClass, EventEnvelope, EventImportance
from anima_ha.graph import CanonicalNode, CommissioningDocument, NodeKind, PostgresHouseholdGraph
from anima_ha.journal import PostgresEventJournal

DATABASE_URL = os.environ.get("ANIMA_DATABASE_URL", "")
ROOT = Path(__file__).resolve().parents[1]


def scalar(query: str, *args: object) -> int:
    with psycopg.connect(DATABASE_URL) as connection, connection.cursor() as cursor:
        cursor.execute(query, args)
        row = cursor.fetchone()
        return int(row[0]) if row else 0


def run_bridge(consumer_name: str, household_id: UUID) -> dict[str, int | float]:
    environment = {
        **os.environ,
        "ANIMA_DATABASE_URL": DATABASE_URL,
        "ANIMA_HOUSEHOLD_ID": str(household_id),
        "ANIMA_SENTRY_HOUSEHOLD_ID": str(household_id),
    }
    lifecycle_before = scalar(
        "SELECT count(*) FROM anima_event_journal "
        "WHERE event_type IN ('plugin.registered','plugin.healthy')"
    )
    triggers_before = scalar(
        "SELECT count(*) FROM anima_reasoning_triggers WHERE attention_profile_version=%s",
        "phase13.sentry.v1",
    )
    started = time.monotonic()
    subprocess.run(
        [
            sys.executable,
            "-m",
            "anima_ha.sentry_bridge",
            "--once",
            "--consumer-name",
            consumer_name,
        ],
        cwd=ROOT,
        env=environment,
        check=True,
        capture_output=True,
        text=True,
    )
    return {
        "elapsed_seconds": round(time.monotonic() - started, 3),
        "plugin_lifecycle_events_added": scalar(
            "SELECT count(*) FROM anima_event_journal "
            "WHERE event_type IN ('plugin.registered','plugin.healthy')"
        )
        - lifecycle_before,
        "trigger_count_before": triggers_before,
        "trigger_count_after": scalar(
            "SELECT count(*) FROM anima_reasoning_triggers WHERE attention_profile_version=%s",
            "phase13.sentry.v1",
        ),
    }


def main() -> int:
    if not DATABASE_URL:
        raise RuntimeError("ANIMA_DATABASE_URL is required")
    migrate(DATABASE_URL, 5)
    # Core's canonical consumer requires real commissioned Graph scope even
    # without an HA adapter. Never borrow/create a production/default household
    # to qualify a disposable restart fixture.
    household_id = uuid4()
    PostgresHouseholdGraph(DATABASE_URL).commission(
        CommissioningDocument(
            version=1,
            nodes=(CanonicalNode(household_id, NodeKind.HOUSEHOLD, "Phase14 bridge fixture"),),
        )
    )
    PostgresAttentionService(DATABASE_URL).register_profile(
        default_attention_profile("phase13.sentry.v1")
    )
    journal = PostgresEventJournal(DATABASE_URL)
    source_event_id = f"phase14-sentry-bridge-{uuid4()}"
    event = EventEnvelope.create(
        event_id=str(uuid4()),
        event_type="user.request",
        source="phase14.sentry.bridge",
        source_event_id=source_event_id,
        subject_key=f"household/{household_id}",
        occurred_at=datetime.now(UTC),
        payload={
            "request": "phase14 bridge restart read-only check",
            "run_marker": source_event_id,
        },
        importance=EventImportance.IMPORTANT,
        delivery_class=DeliveryClass.GUARANTEED,
        metadata={
            "household_id": str(household_id),
            "phase14_test": True,
        },
    )
    append = journal.append(event)
    assert append.deduplicated is False
    position = journal.position(event.event_id)
    assert position is not None
    consumer_name = f"phase14-sentry-{uuid4()}"
    with psycopg.connect(DATABASE_URL) as connection, connection.cursor() as cursor:
        cursor.execute(
            """
            INSERT INTO anima_attention_cursors (consumer_name, profile_version, last_position)
            VALUES (%s, %s, %s)
            ON CONFLICT (consumer_name) DO UPDATE SET last_position = EXCLUDED.last_position
            """,
            (consumer_name, "phase13.sentry.v1", position - 1),
        )
        connection.commit()
    first_process = run_bridge(consumer_name, household_id)
    first_count = scalar(
        "SELECT count(*) FROM anima_intelligence_requests WHERE causation_id=%s", event.event_id
    )
    assert first_count == 1, first_count
    second_process = run_bridge(consumer_name, household_id)
    second_count = scalar(
        "SELECT count(*) FROM anima_intelligence_requests WHERE causation_id=%s", event.event_id
    )
    assert second_count == 1, second_count
    print(
        json.dumps(
            {
                "scenario_id": "SENTRY_BRIDGE_RESTART_NO_DUPLICATE_REQUEST",
                "status": "PASS",
                "evidence_level": "POSTGRES_PROCESS",
                "source_event_id_present": True,
                "request_count_before_restart": first_count,
                "request_count_after_restart": second_count,
                "process_observations": [first_process, second_process],
                "embedded_agent_runtime": False,
                "phase15": False,
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
