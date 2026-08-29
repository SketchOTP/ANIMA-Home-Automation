"""Deterministic, low-risk routine context derived from journal history.

Routine records are probabilistic context.  They never write Truth, memory
authority, permissions, or executable automation.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid5

import psycopg
from psycopg.rows import dict_row

from anima_ha.journal import PostgresEventJournal

ROUTINE_NAMESPACE = UUID("8f2d2f0f-1d45-4c40-bc89-cf35fb0dd4c9")


@dataclass(frozen=True, slots=True)
class RoutineModel:
    routine_id: UUID
    household_id: UUID
    model_key: str
    model_version: int
    label: str
    model: dict[str, Any]
    confidence: float
    sample_count: int
    source_start: datetime | None
    source_end: datetime | None
    source_event_ids: tuple[str, ...]
    generated_at: datetime


class RoutineValidationError(ValueError):
    """Raised for invalid synthetic routine observations or model requests."""


class RoutineService:
    """Rebuildable PostgreSQL routine statistics over canonical journal events."""

    def __init__(self, database_url: str, connect_timeout: int = 5) -> None:
        self.database_url = database_url
        self.connect_timeout = connect_timeout
        self.journal = PostgresEventJournal(database_url, connect_timeout)

    def rebuild_activity_model(
        self,
        household_id: UUID,
        *,
        source: str = "simulator",
        model_version: int = 1,
        now: datetime | None = None,
    ) -> RoutineModel:
        if model_version < 1:
            raise RoutineValidationError("model_version must be positive")
        subject_key = f"routine/household/{household_id}"
        events = self.journal.list_events(
            event_type="routine.activity_observation",
            source=source,
            subject_key=subject_key,
            limit=10000,
        )
        if not events:
            raise RoutineValidationError("at least one routine observation is required")
        counts: dict[str, list[int]] = {}
        for event in events:
            payload = event["payload"]
            if isinstance(payload, str):
                payload = json.loads(payload)
            bucket = str(payload.get("bucket", "")).strip()
            if not bucket:
                occurred = event["occurred_at"].astimezone(UTC)
                bucket = f"{occurred.hour:02d}:00"
            active = payload.get("active")
            if not isinstance(active, bool):
                raise RoutineValidationError("routine observations require boolean active")
            counts.setdefault(bucket, [0, 0])
            counts[bucket][0] += int(active)
            counts[bucket][1] += 1
        probabilities = {
            bucket: round(active / samples, 6)
            for bucket, (active, samples) in sorted(counts.items())
        }
        low_activity = [
            bucket for bucket, probability in probabilities.items() if probability < 0.25
        ]
        sample_count = len(events)
        confidence = round(min(0.99, 0.5 + sample_count / (sample_count + 20)), 6)
        source_times = [event["occurred_at"] for event in events]
        generated_at = now or datetime.now(UTC)
        routine_id = uuid5(ROUTINE_NAMESPACE, f"{household_id}:activity:{model_version}")
        routine = RoutineModel(
            routine_id=routine_id,
            household_id=household_id,
            model_key="household_activity_by_bucket",
            model_version=model_version,
            label="Inferred household activity pattern",
            model={
                "classification": "INFERRED",
                "bucket_probabilities": probabilities,
                "low_activity_buckets": low_activity,
                "interpretation": (
                    "activity is usually low in these buckets; this is not proof "
                    "of sleep or absence"
                ),
            },
            confidence=confidence,
            sample_count=sample_count,
            source_start=min(source_times),
            source_end=max(source_times),
            source_event_ids=tuple(str(event["event_id"]) for event in events),
            generated_at=generated_at,
        )
        with psycopg.connect(
            self.database_url, connect_timeout=self.connect_timeout, row_factory=dict_row
        ) as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    INSERT INTO anima_routine_models (
                        routine_id, household_id, model_key, model_version, label, model,
                        confidence, sample_count, source_start, source_end, source_event_ids,
                        generated_at
                    ) VALUES (%(routine_id)s, %(household_id)s, %(model_key)s, %(model_version)s,
                              %(label)s, %(model)s::jsonb, %(confidence)s, %(sample_count)s,
                              %(source_start)s, %(source_end)s, %(source_event_ids)s::jsonb,
                              %(generated_at)s)
                    ON CONFLICT (household_id, model_key, model_version) DO UPDATE SET
                        routine_id = EXCLUDED.routine_id, label = EXCLUDED.label,
                        model = EXCLUDED.model, confidence = EXCLUDED.confidence,
                        sample_count = EXCLUDED.sample_count, source_start = EXCLUDED.source_start,
                        source_end = EXCLUDED.source_end,
                        source_event_ids = EXCLUDED.source_event_ids,
                        generated_at = EXCLUDED.generated_at
                    """,
                    {
                        "routine_id": routine.routine_id,
                        "household_id": routine.household_id,
                        "model_key": routine.model_key,
                        "model_version": routine.model_version,
                        "label": routine.label,
                        "model": json.dumps(routine.model, sort_keys=True),
                        "confidence": routine.confidence,
                        "sample_count": routine.sample_count,
                        "source_start": routine.source_start,
                        "source_end": routine.source_end,
                        "source_event_ids": json.dumps(list(routine.source_event_ids)),
                        "generated_at": routine.generated_at,
                    },
                )
            connection.commit()
        return routine

    def get(self, household_id: UUID, *, model_version: int = 1) -> RoutineModel | None:
        with psycopg.connect(
            self.database_url, connect_timeout=self.connect_timeout, row_factory=dict_row
        ) as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT * FROM anima_routine_models
                    WHERE household_id = %s AND model_key = 'household_activity_by_bucket'
                      AND model_version = %s
                    """,
                    (household_id, model_version),
                )
                row = cursor.fetchone()
        if row is None:
            return None
        return RoutineModel(
            routine_id=UUID(str(row["routine_id"])),
            household_id=UUID(str(row["household_id"])),
            model_key=str(row["model_key"]),
            model_version=int(row["model_version"]),
            label=str(row["label"]),
            model=dict(row["model"]),
            confidence=float(row["confidence"]),
            sample_count=int(row["sample_count"]),
            source_start=row["source_start"],
            source_end=row["source_end"],
            source_event_ids=tuple(str(value) for value in (row["source_event_ids"] or [])),
            generated_at=row["generated_at"],
        )
