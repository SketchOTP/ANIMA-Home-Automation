"""Run the bounded PostgreSQL evidence harness for Phase 1.

The harness uses a unique synthetic prefix and never deletes or updates journal
events. It exercises persistence and replay only; it does not contact HA or
external systems.
"""

from __future__ import annotations

import os
import uuid
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from datetime import UTC, datetime, timedelta

import psycopg

from anima_ha.events import EventEnvelope, ObservationState, TruthObservation
from anima_ha.journal import PostgresRealityStore
from anima_ha.truth import TruthStatus


def main() -> int:
    url = os.environ["ANIMA_DATABASE_URL"]
    prefix = "phase1-" + uuid.uuid4().hex[:12]
    now = datetime.now(UTC).replace(microsecond=0)
    store = PostgresRealityStore(url)

    def make(
        suffix: str,
        key: str,
        source: str,
        value: object = None,
        *,
        sequence: int | None = None,
        observed: datetime | None = None,
        freshness: int | None = None,
        state: ObservationState = ObservationState.KNOWN,
    ) -> EventEnvelope:
        observed = observed or now
        observation = TruthObservation(
            truth_key=f"{prefix}/{key}",
            source=source,
            value=value,
            state=state,
            observed_at=observed,
            received_at=observed + timedelta(seconds=1),
            source_sequence=sequence,
            freshness_seconds=freshness,
        )
        event_id = f"{prefix}-{suffix}"
        return EventEnvelope.create(
            event_id=event_id,
            event_type="truth.observation",
            source=source,
            source_event_id=event_id,
            subject_key=observation.truth_key,
            occurred_at=observed,
            recorded_at=observation.received_at,
            source_sequence=sequence,
            payload=observation.to_payload(),
        )

    normal = make("normal", "normal/value", "sim-a", 10)
    with ThreadPoolExecutor(max_workers=8) as pool:
        duplicate_results = list(pool.map(lambda _: store.journal.append(normal), range(8)))
    assert sum(not result.deduplicated for result in duplicate_results) == 1
    store.projection.project_pending()
    assert store.projection.get(f"{prefix}/normal/value", now=now).value == 10
    assert store.journal.append(replace(normal, event_id=f"{prefix}-source-duplicate")).deduplicated

    try:
        with psycopg.connect(url) as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    "UPDATE anima_event_journal SET metadata='{}' WHERE event_id=%s",
                    (normal.event_id,),
                )
            connection.commit()
    except psycopg.Error:
        pass
    else:
        raise AssertionError("append-only trigger did not reject UPDATE")

    for event in (
        make("ooo-new", "ooo/value", "sim-seq", 22, sequence=2),
        make(
            "ooo-old", "ooo/value", "sim-seq", 20, sequence=1, observed=now - timedelta(minutes=1)
        ),
        make("stale", "stale/value", "sim-stale", 7, freshness=1),
        make("unknown", "unknown/value", "sim-unknown", state=ObservationState.UNKNOWN),
        make(
            "unavailable",
            "unavailable/value",
            "sim-unavailable",
            state=ObservationState.UNAVAILABLE,
        ),
        make("conflict-a", "conflict/value", "sim-a", 1),
        make("conflict-b", "conflict/value", "sim-b", 2),
    ):
        store.ingest(event)
    assert store.projection.get(f"{prefix}/ooo/value", now=now).value == 22
    assert (
        store.projection.get(f"{prefix}/stale/value", now=now + timedelta(seconds=2)).status
        == TruthStatus.STALE
    )
    assert store.projection.get(f"{prefix}/unknown/value", now=now).status == TruthStatus.UNKNOWN
    assert (
        store.projection.get(f"{prefix}/unavailable/value", now=now).status
        == TruthStatus.UNAVAILABLE
    )
    assert (
        store.projection.get(f"{prefix}/conflict/value", now=now).status == TruthStatus.CONFLICTING
    )

    retry_event = make("retry", "retry/value", "sim-retry", 99)
    store.journal.append(retry_event)
    original_project_one = store.projection._project_one
    failed_once = True

    def fail_once(connection: psycopg.Connection[object], row: dict[str, object]) -> None:
        nonlocal failed_once
        if failed_once:
            failed_once = False
            raise RuntimeError("injected projection failure")
        original_project_one(connection, row)

    store.projection._project_one = fail_once
    failure = store.projection.project_pending()
    assert failure.failed_position is not None
    assert store.projection.get(f"{prefix}/retry/value", now=now).status == TruthStatus.UNKNOWN
    store.projection._project_one = original_project_one
    assert store.projection.project_pending().failed_position is None
    assert store.projection.get(f"{prefix}/retry/value", now=now).value == 99

    keys = (
        "normal/value",
        "ooo/value",
        "stale/value",
        "unknown/value",
        "unavailable/value",
        "conflict/value",
        "retry/value",
    )
    before = {key: store.projection.get(f"{prefix}/{key}", now=now).to_dict() for key in keys}
    rebuilt = store.projection.rebuild()
    after = {key: store.projection.get(f"{prefix}/{key}", now=now).to_dict() for key in keys}
    assert before == after
    assert rebuilt.replayed == store.journal.count()
    print("phase1_postgres_integration=PASS")
    print(f"synthetic_prefix={prefix}")
    print("concurrent_duplicate_logical_inserts=1")
    print("append_only_trigger=PASS")
    print("projection_failure_retry=PASS")
    print(f"rebuild_replayed={rebuilt.replayed} state_count={rebuilt.state_count}")
    print("statuses=" + str({key: after[key]["status"] for key in keys}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
