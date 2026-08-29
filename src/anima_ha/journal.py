"""PostgreSQL event journal and reality-substrate orchestration boundary."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from typing import Any

import psycopg
from psycopg.rows import dict_row

from anima_ha.events import (
    SUPPORTED_EVENT_SCHEMA_VERSION,
    EventEnvelope,
    TruthObservation,
    UnsupportedEventSchema,
)
from anima_ha.truth import TruthReconciler, TruthResolution


class ProjectionError(RuntimeError):
    """Raised when a journal event cannot be projected safely."""


@dataclass(frozen=True, slots=True)
class AppendResult:
    event_id: str
    journal_position: int
    deduplicated: bool
    deduplication_key: str | None = None


@dataclass(frozen=True, slots=True)
class ProjectionResult:
    processed: int
    last_position: int | None
    failed_position: int | None = None
    failure: str | None = None


@dataclass(frozen=True, slots=True)
class RebuildResult:
    replayed: int
    last_position: int | None
    state_count: int


class PostgresEventJournal:
    """Append-only PostgreSQL journal with event and source deduplication."""

    def __init__(self, database_url: str, connect_timeout: int = 5) -> None:
        self.database_url = database_url
        self.connect_timeout = connect_timeout

    def append(self, event: EventEnvelope) -> AppendResult:
        if event.schema_version != SUPPORTED_EVENT_SCHEMA_VERSION:
            raise UnsupportedEventSchema(
                f"event schema {event.schema_version} is unsupported; "
                f"supported={SUPPORTED_EVENT_SCHEMA_VERSION}"
            )
        with psycopg.connect(
            self.database_url, connect_timeout=self.connect_timeout, row_factory=dict_row
        ) as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    INSERT INTO anima_event_journal (
                        event_id, schema_version, event_type, source, source_event_id,
                        subject_key, occurred_at, recorded_at, source_sequence,
                        correlation_id, causation_id, confidence, evidence_kind,
                        importance, delivery_class, payload, metadata
                    ) VALUES (
                        %(event_id)s, %(schema_version)s, %(event_type)s, %(source)s,
                        %(source_event_id)s, %(subject_key)s, %(occurred_at)s,
                        %(recorded_at)s, %(source_sequence)s, %(correlation_id)s,
                        %(causation_id)s, %(confidence)s, %(evidence_kind)s,
                        %(importance)s, %(delivery_class)s, %(payload)s::jsonb,
                        %(metadata)s::jsonb
                    )
                    ON CONFLICT DO NOTHING
                    RETURNING journal_position
                    """,
                    {
                        "event_id": event.event_id,
                        "schema_version": event.schema_version,
                        "event_type": event.event_type,
                        "source": event.source,
                        "source_event_id": event.source_event_id,
                        "subject_key": event.subject_key,
                        "occurred_at": event.occurred_at,
                        "recorded_at": event.recorded_at,
                        "source_sequence": event.source_sequence,
                        "correlation_id": event.correlation_id,
                        "causation_id": event.causation_id,
                        "confidence": event.confidence,
                        "evidence_kind": event.evidence_kind.value,
                        "importance": event.importance.value,
                        "delivery_class": event.delivery_class.value,
                        "payload": json.dumps(event.payload, sort_keys=True),
                        "metadata": json.dumps(event.metadata, sort_keys=True),
                    },
                )
                inserted = cursor.fetchone()
                if inserted:
                    connection.commit()
                    return AppendResult(event.event_id, int(inserted["journal_position"]), False)
                cursor.execute(
                    """
                    SELECT journal_position, event_id, source_event_id
                    FROM anima_event_journal
                    WHERE event_id = %(event_id)s
                       OR (%(source_event_id)s::text IS NOT NULL AND source = %(source)s
                           AND source_event_id = %(source_event_id)s)
                    ORDER BY journal_position
                    LIMIT 1
                    """,
                    {
                        "event_id": event.event_id,
                        "source": event.source,
                        "source_event_id": event.source_event_id,
                    },
                )
                existing = cursor.fetchone()
                if existing is None:
                    raise ProjectionError("event insert was ignored but no duplicate was found")
                connection.commit()
                key = "event_id" if existing["event_id"] == event.event_id else "source_event_id"
                return AppendResult(
                    str(existing["event_id"]), int(existing["journal_position"]), True, key
                )

    def list_events(
        self,
        *,
        after_position: int = 0,
        event_type: str | None = None,
        source: str | None = None,
        subject_key: str | None = None,
        correlation_id: str | None = None,
        occurred_after: datetime | None = None,
        occurred_before: datetime | None = None,
        limit: int = 1000,
    ) -> list[dict[str, Any]]:
        clauses = ["journal_position > %(after_position)s"]
        params: dict[str, Any] = {"after_position": after_position, "limit": limit}
        for name, value in (
            ("event_type", event_type),
            ("source", source),
            ("subject_key", subject_key),
            ("correlation_id", correlation_id),
        ):
            if value is not None:
                clauses.append(f"{name} = %({name})s")
                params[name] = value
        if occurred_after is not None:
            clauses.append("occurred_at >= %(occurred_after)s")
            params["occurred_after"] = occurred_after
        if occurred_before is not None:
            clauses.append("occurred_at <= %(occurred_before)s")
            params["occurred_before"] = occurred_before
        query = f"""
            SELECT journal_position, event_id, schema_version, event_type, source,
                   source_event_id, subject_key, occurred_at, recorded_at,
                   source_sequence, correlation_id, causation_id, confidence,
                   evidence_kind, importance, delivery_class, payload, metadata
            FROM anima_event_journal
            WHERE {" AND ".join(clauses)}
            ORDER BY journal_position ASC
            LIMIT %(limit)s
        """
        with psycopg.connect(
            self.database_url, connect_timeout=self.connect_timeout, row_factory=dict_row
        ) as connection:
            with connection.cursor() as cursor:
                cursor.execute(query, params)
                return list(cursor.fetchall())

    def count(self) -> int:
        with psycopg.connect(
            self.database_url, connect_timeout=self.connect_timeout, row_factory=dict_row
        ) as connection:
            with connection.cursor() as cursor:
                cursor.execute("SELECT count(*) AS count FROM anima_event_journal")
                row = cursor.fetchone()
                assert row is not None
                return int(row["count"])


class PostgresTruthProjection:
    """Project truth observations while retaining the journal as authority."""

    def __init__(self, database_url: str, connect_timeout: int = 5) -> None:
        self.database_url = database_url
        self.connect_timeout = connect_timeout
        self.reconciler = TruthReconciler()

    @staticmethod
    def _observation(row: dict[str, Any]) -> TruthObservation:
        payload = row["payload"]
        if isinstance(payload, str):
            payload = json.loads(payload)
        return TruthObservation.from_payload(
            dict(payload),
            event_id=str(row["event_id"]),
            journal_position=int(row["journal_position"]),
        )

    def _project_one(self, connection: psycopg.Connection[Any], row: dict[str, Any]) -> None:
        if int(row["schema_version"]) != SUPPORTED_EVENT_SCHEMA_VERSION:
            raise UnsupportedEventSchema(
                f"journal position {row['journal_position']} has unsupported schema"
            )
        if row["event_type"] != "truth.observation":
            return
        observation = self._observation(row)
        with connection.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO anima_truth_observations (
                    event_id, journal_position, truth_key, source, state, value,
                    observed_at, received_at, source_sequence, confidence,
                    evidence_kind, freshness_seconds, metadata
                ) VALUES (
                    %(event_id)s, %(journal_position)s, %(truth_key)s, %(source)s,
                    %(state)s, %(value)s::jsonb, %(observed_at)s, %(received_at)s,
                    %(source_sequence)s, %(confidence)s, %(evidence_kind)s,
                    %(freshness_seconds)s, %(metadata)s::jsonb
                ) ON CONFLICT (event_id) DO NOTHING
                """,
                {
                    "event_id": observation.event_id,
                    "journal_position": observation.journal_position,
                    "truth_key": observation.truth_key,
                    "source": observation.source,
                    "state": observation.state.value,
                    "value": (
                        json.dumps(observation.value, sort_keys=True)
                        if observation.value is not None
                        else None
                    ),
                    "observed_at": observation.observed_at,
                    "received_at": observation.received_at,
                    "source_sequence": observation.source_sequence,
                    "confidence": observation.confidence,
                    "evidence_kind": observation.evidence_kind.value,
                    "freshness_seconds": observation.freshness_seconds,
                    "metadata": json.dumps(observation.metadata, sort_keys=True),
                },
            )
            cursor.execute(
                """
                SELECT event_id, journal_position, truth_key, source, state, value,
                       observed_at, received_at, source_sequence, confidence,
                       evidence_kind, freshness_seconds, metadata
                FROM anima_truth_observations WHERE truth_key = %s
                """,
                (observation.truth_key,),
            )
            all_observations = [
                TruthObservation(
                    truth_key=str(item["truth_key"]),
                    source=str(item["source"]),
                    state=item["state"],
                    value=item["value"],
                    observed_at=item["observed_at"],
                    received_at=item["received_at"],
                    source_sequence=item["source_sequence"],
                    confidence=item["confidence"],
                    evidence_kind=item["evidence_kind"],
                    freshness_seconds=item["freshness_seconds"],
                    event_id=str(item["event_id"]),
                    journal_position=int(item["journal_position"]),
                    metadata=item["metadata"],
                )
                for item in cursor.fetchall()
            ]
            resolution = self.reconciler.resolve(observation.truth_key, all_observations)
            cursor.execute(
                """
                INSERT INTO anima_truth_state (
                    truth_key, status, value, confidence, evidence_kind,
                    last_observed_at, last_received_at, resolution
                ) VALUES (%(truth_key)s, %(status)s, %(value)s::jsonb,
                          %(confidence)s, %(evidence_kind)s, %(last_observed_at)s,
                          %(last_received_at)s, %(resolution)s::jsonb)
                ON CONFLICT (truth_key) DO UPDATE SET
                    status = EXCLUDED.status, value = EXCLUDED.value,
                    confidence = EXCLUDED.confidence, evidence_kind = EXCLUDED.evidence_kind,
                    last_observed_at = EXCLUDED.last_observed_at,
                    last_received_at = EXCLUDED.last_received_at,
                    resolution = EXCLUDED.resolution, updated_at = now()
                """,
                {
                    "truth_key": resolution.truth_key,
                    "status": resolution.status.value,
                    "value": (
                        json.dumps(resolution.value, sort_keys=True)
                        if resolution.value is not None
                        else None
                    ),
                    "confidence": resolution.confidence,
                    "evidence_kind": resolution.evidence_kind.value
                    if resolution.evidence_kind
                    else None,
                    "last_observed_at": resolution.last_observed_at,
                    "last_received_at": resolution.last_received_at,
                    "resolution": json.dumps(resolution.to_dict(), sort_keys=True),
                },
            )

    def project_pending(self) -> ProjectionResult:
        with psycopg.connect(
            self.database_url, connect_timeout=self.connect_timeout, row_factory=dict_row
        ) as connection:
            with connection.cursor() as cursor:
                cursor.execute("SELECT pg_advisory_xact_lock(hashtext('anima.truth_projection'))")
                cursor.execute(
                    """
                    SELECT last_position FROM anima_projection_checkpoints
                    WHERE projection_name = 'truth'
                    """
                )
                checkpoint = cursor.fetchone()
                last_position = int(checkpoint["last_position"]) if checkpoint else 0
                cursor.execute(
                    """
                    SELECT journal_position, event_id, schema_version, event_type, source,
                           payload FROM anima_event_journal
                    WHERE journal_position > %s ORDER BY journal_position ASC
                    """,
                    (last_position,),
                )
                rows = list(cursor.fetchall())
                processed = 0
                try:
                    for row in rows:
                        self._project_one(connection, row)
                        last_position = int(row["journal_position"])
                        processed += 1
                        cursor.execute(
                            """
                            INSERT INTO anima_projection_checkpoints
                                (projection_name, last_position, updated_at, last_error)
                            VALUES ('truth', %s, now(), NULL)
                            ON CONFLICT (projection_name) DO UPDATE SET
                                last_position = EXCLUDED.last_position,
                                updated_at = EXCLUDED.updated_at, last_error = NULL
                            """,
                            (last_position,),
                        )
                    connection.commit()
                    return ProjectionResult(processed, last_position or None)
                except Exception as exc:
                    connection.rollback()
                    with connection.cursor() as failure_cursor:
                        failure_cursor.execute(
                            """
                            INSERT INTO anima_projection_failures
                                (projection_name, journal_position, error, failed_at)
                            VALUES ('truth', %s, %s, now())
                            ON CONFLICT (projection_name, journal_position) DO UPDATE SET
                                error = EXCLUDED.error, failed_at = EXCLUDED.failed_at,
                                retry_count = anima_projection_failures.retry_count + 1
                            """,
                            (last_position + 1, str(exc)),
                        )
                        failure_cursor.execute(
                            """
                            INSERT INTO anima_projection_checkpoints
                                (projection_name, last_position, updated_at, last_error)
                            VALUES ('truth', %s, now(), %s)
                            ON CONFLICT (projection_name) DO UPDATE SET
                                updated_at = EXCLUDED.updated_at, last_error = EXCLUDED.last_error
                            """,
                            (last_position, str(exc)),
                        )
                    connection.commit()
                    return ProjectionResult(
                        processed, last_position or None, last_position + 1, str(exc)
                    )

    def get(self, truth_key: str, *, now: datetime | None = None) -> TruthResolution:
        with psycopg.connect(
            self.database_url, connect_timeout=self.connect_timeout, row_factory=dict_row
        ) as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT event_id, journal_position, truth_key, source, state, value,
                           observed_at, received_at, source_sequence, confidence,
                           evidence_kind, freshness_seconds, metadata
                    FROM anima_truth_observations WHERE truth_key = %s
                    ORDER BY journal_position ASC
                    """,
                    (truth_key,),
                )
                observations = [
                    TruthObservation(
                        truth_key=str(row["truth_key"]),
                        source=str(row["source"]),
                        state=row["state"],
                        value=row["value"],
                        observed_at=row["observed_at"],
                        received_at=row["received_at"],
                        source_sequence=row["source_sequence"],
                        confidence=row["confidence"],
                        evidence_kind=row["evidence_kind"],
                        freshness_seconds=row["freshness_seconds"],
                        event_id=str(row["event_id"]),
                        journal_position=int(row["journal_position"]),
                        metadata=row["metadata"],
                    )
                    for row in cursor.fetchall()
                ]
        return self.reconciler.resolve(truth_key, observations, now=now)

    def rebuild(self) -> RebuildResult:
        with psycopg.connect(
            self.database_url, connect_timeout=self.connect_timeout, row_factory=dict_row
        ) as connection:
            with connection.cursor() as cursor:
                cursor.execute("TRUNCATE anima_truth_state, anima_truth_observations")
                cursor.execute(
                    """
                    INSERT INTO anima_projection_checkpoints
                        (projection_name, last_position, updated_at, last_error)
                    VALUES ('truth', 0, now(), NULL)
                    ON CONFLICT (projection_name) DO UPDATE SET
                        last_position = 0, updated_at = now(), last_error = NULL
                    """
                )
            connection.commit()
        result = self.project_pending()
        if result.failed_position is not None:
            raise ProjectionError(result.failure or "truth rebuild failed")
        return RebuildResult(result.processed, result.last_position, self.state_count())

    def state_count(self) -> int:
        with psycopg.connect(
            self.database_url, connect_timeout=self.connect_timeout, row_factory=dict_row
        ) as connection:
            with connection.cursor() as cursor:
                cursor.execute("SELECT count(*) AS count FROM anima_truth_state")
                row = cursor.fetchone()
                assert row is not None
                return int(row["count"])


class PostgresRealityStore:
    """Journal-first ingestion facade used by the simulator and future adapters."""

    def __init__(self, database_url: str, connect_timeout: int = 5) -> None:
        self.journal = PostgresEventJournal(database_url, connect_timeout)
        self.projection = PostgresTruthProjection(database_url, connect_timeout)

    def ingest(
        self, event: EventEnvelope, *, project: bool = True
    ) -> tuple[AppendResult, ProjectionResult | None]:
        appended = self.journal.append(event)
        projection = self.projection.project_pending() if project else None
        return appended, projection
