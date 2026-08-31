"""ANIMA-owned declarative durable tasks and scheduled cognition dispatch.

Tasks persist future intent, not executable work or future authority.  A due
task emits one guaranteed journal event; the existing attention, context,
policy, cognition, and action boundaries decide what happens next.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass, field, replace
from datetime import UTC, datetime, timedelta
from enum import StrEnum
from typing import Any, Protocol
from uuid import UUID, uuid4, uuid5
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

import psycopg
from croniter import croniter  # type: ignore[import-untyped]
from psycopg.rows import dict_row

from anima_ha.attention import AttentionProfile, PostgresAttentionService, ReasoningTrigger
from anima_ha.context import ContextBroker, ContextPacket
from anima_ha.events import DeliveryClass, EventEnvelope, EventImportance
from anima_ha.plugins import (
    CORE_VERSION,
    MANIFEST_VERSION,
    ExternalContentTrust,
    Idempotency,
    PluginManifest,
    PluginValidationError,
    RuntimeKind,
    TrustClass,
)

TASK_NAMESPACE = UUID("a8324d4d-74ad-47d0-87fb-5c3e6de25013")
TASK_EVENT_NAMESPACE = UUID("86f7cc5e-93cc-4b01-9b48-dbe2e6a3d89e")
TASK_SCHEMA_VERSION = 1
MAX_TASK_TITLE = 240
MAX_TASK_PAYLOAD_BYTES = 32_768
MAX_CRON_FIELDS = 5
FORBIDDEN_PAYLOAD_KEYS = {
    "arguments",
    "callable",
    "code",
    "command",
    "connector",
    "executable",
    "function",
    "import_path",
    "provider",
    "shell",
    "tool_id",
    "tool_name",
}


class TaskValidationError(ValueError):
    """Raised when declarative task data is invalid or unsafe."""


class TaskNotFound(KeyError):
    """Raised when a task or run does not exist."""


class TaskConflict(RuntimeError):
    """Raised when an idempotency key is reused for different task data."""


class TaskType(StrEnum):
    REASONING_DUE = "REASONING_DUE"
    EPISODE_CONTINUATION = "EPISODE_CONTINUATION"


class ScheduleKind(StrEnum):
    ONCE = "ONCE"
    INTERVAL = "INTERVAL"
    CRON = "CRON"


class IntervalKind(StrEnum):
    FIXED_DURATION = "FIXED_DURATION"


class MisfirePolicy(StrEnum):
    FIRE_ONCE_NOW = "FIRE_ONCE_NOW"
    SKIP = "SKIP"
    COALESCE_ONE = "COALESCE_ONE"


class TaskStatus(StrEnum):
    ACTIVE = "ACTIVE"
    PAUSED = "PAUSED"
    CANCELLED = "CANCELLED"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


class TaskRunStatus(StrEnum):
    PENDING = "PENDING"
    CLAIMED = "CLAIMED"
    DISPATCHING = "DISPATCHING"
    DISPATCHED = "DISPATCHED"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"
    MISSED = "MISSED"


def _utc(value: datetime, name: str) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise TaskValidationError(f"{name} must be timezone-aware")
    return value.astimezone(UTC)


def _json(value: Any) -> Any:
    try:
        raw = json.dumps(value, sort_keys=True, separators=(",", ":"))
    except (TypeError, ValueError) as exc:
        raise TaskValidationError("task data must be JSON-compatible") from exc
    if len(raw.encode()) > MAX_TASK_PAYLOAD_BYTES:
        raise TaskValidationError("task data exceeds ANIMA size bound")
    return value


def _reject_executable_keys(value: Any) -> None:
    if isinstance(value, dict):
        for key, child in value.items():
            if str(key).casefold() in FORBIDDEN_PAYLOAD_KEYS:
                raise TaskValidationError(f"executable task key is prohibited: {key}")
            _reject_executable_keys(child)
    elif isinstance(value, list):
        for child in value:
            _reject_executable_keys(child)


def _declarative_payload(value: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise TaskValidationError("task payload must be an object")
    _reject_executable_keys(value)
    _json(value)
    if not any(str(key) in {"objective", "summary", "question"} for key in value):
        raise TaskValidationError("task payload requires a bounded objective or summary")
    subject_refs = value.get("subject_refs", [])
    if (
        not isinstance(subject_refs, list)
        or len(subject_refs) > 32
        or not all(isinstance(item, str) and item.strip() for item in subject_refs)
    ):
        raise TaskValidationError("subject_refs must be a bounded list of non-empty strings")
    return dict(value)


class RecurrenceCalculator:
    """Small ANIMA wrapper around croniter for next-occurrence calculation."""

    dependency_version = "6.2.4"

    @staticmethod
    def validate(expression: str) -> None:
        fields = expression.split()
        if len(fields) != MAX_CRON_FIELDS or not croniter.is_valid(expression):
            raise TaskValidationError("cron must be a valid five-field expression")

    def next_after(self, expression: str, after: datetime, timezone: str) -> datetime:
        self.validate(expression)
        at = _utc(after, "after")
        zone = _zone(timezone)
        local_after = at.astimezone(zone)
        iterator = croniter(expression, local_after)
        candidate = iterator.get_next(datetime)
        if candidate.tzinfo is None:
            candidate = candidate.replace(tzinfo=zone)
        # A fall-back clock repeats one local wall time.  ANIMA emits one
        # occurrence per configured wall time, so skip the second fold.
        if candidate.astimezone(zone).replace(tzinfo=None) == local_after.replace(tzinfo=None):
            candidate = iterator.get_next(datetime)
        return _utc(candidate, "cron occurrence")


def _zone(timezone: str) -> ZoneInfo:
    if not timezone.strip():
        raise TaskValidationError("IANA timezone is required")
    try:
        return ZoneInfo(timezone)
    except ZoneInfoNotFoundError as exc:
        raise TaskValidationError(f"unknown IANA timezone: {timezone}") from exc


@dataclass(frozen=True, slots=True)
class TaskSchedule:
    kind: ScheduleKind
    timezone: str
    run_at: datetime
    interval_seconds: int | None = None
    cron_expression: str | None = None
    interval_kind: IntervalKind = IntervalKind.FIXED_DURATION
    misfire_policy: MisfirePolicy = MisfirePolicy.FIRE_ONCE_NOW
    misfire_grace_seconds: int | None = None
    expires_at: datetime | None = None
    schema_version: int = TASK_SCHEMA_VERSION

    def __post_init__(self) -> None:
        object.__setattr__(self, "kind", ScheduleKind(self.kind))
        object.__setattr__(self, "interval_kind", IntervalKind(self.interval_kind))
        object.__setattr__(self, "misfire_policy", MisfirePolicy(self.misfire_policy))
        if self.schema_version != TASK_SCHEMA_VERSION:
            raise TaskValidationError("unsupported task schedule schema")
        _zone(self.timezone)
        object.__setattr__(self, "run_at", _utc(self.run_at, "run_at"))
        if self.expires_at is not None:
            object.__setattr__(self, "expires_at", _utc(self.expires_at, "expires_at"))
        if self.misfire_grace_seconds is not None and self.misfire_grace_seconds < 0:
            raise TaskValidationError("misfire_grace_seconds must not be negative")
        if self.kind == ScheduleKind.ONCE:
            if self.interval_seconds is not None or self.cron_expression is not None:
                raise TaskValidationError("one-shot schedule cannot have recurrence fields")
        elif self.kind == ScheduleKind.INTERVAL:
            if self.interval_seconds is None or self.interval_seconds < 1:
                raise TaskValidationError("interval_seconds must be positive")
            if (
                self.cron_expression is not None
                or self.interval_kind != IntervalKind.FIXED_DURATION
            ):
                raise TaskValidationError("interval schedules must be fixed-duration intervals")
        elif self.kind == ScheduleKind.CRON:
            if not self.cron_expression or self.interval_seconds is not None:
                raise TaskValidationError("cron schedule requires only a cron expression")
            RecurrenceCalculator.validate(self.cron_expression)

    def to_payload(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "kind": self.kind.value,
            "timezone": self.timezone,
            "run_at": self.run_at.isoformat(),
            "interval_seconds": self.interval_seconds,
            "cron_expression": self.cron_expression,
            "interval_kind": self.interval_kind.value,
            "misfire_policy": self.misfire_policy.value,
            "misfire_grace_seconds": self.misfire_grace_seconds,
            "expires_at": self.expires_at.isoformat() if self.expires_at else None,
        }

    @classmethod
    def from_payload(cls, value: dict[str, Any]) -> TaskSchedule:
        return cls(
            kind=ScheduleKind(str(value["kind"])),
            timezone=str(value["timezone"]),
            run_at=datetime.fromisoformat(str(value["run_at"])),
            interval_seconds=(
                int(value["interval_seconds"])
                if value.get("interval_seconds") is not None
                else None
            ),
            cron_expression=(
                str(value["cron_expression"]) if value.get("cron_expression") else None
            ),
            interval_kind=IntervalKind(
                str(value.get("interval_kind", IntervalKind.FIXED_DURATION))
            ),
            misfire_policy=MisfirePolicy(
                str(value.get("misfire_policy", MisfirePolicy.FIRE_ONCE_NOW))
            ),
            misfire_grace_seconds=(
                int(value["misfire_grace_seconds"])
                if value.get("misfire_grace_seconds") is not None
                else None
            ),
            expires_at=(
                datetime.fromisoformat(str(value["expires_at"]))
                if value.get("expires_at")
                else None
            ),
            schema_version=int(value.get("schema_version", TASK_SCHEMA_VERSION)),
        )

    def next_after(self, after: datetime) -> datetime:
        at = _utc(after, "after")
        if self.kind == ScheduleKind.INTERVAL:
            assert self.interval_seconds is not None
            return at + timedelta(seconds=self.interval_seconds)
        if self.kind == ScheduleKind.CRON:
            assert self.cron_expression is not None
            return RecurrenceCalculator().next_after(self.cron_expression, at, self.timezone)
        raise TaskValidationError("one-shot schedule has no next occurrence")


@dataclass(frozen=True, slots=True)
class DurableTask:
    task_id: UUID
    household_id: UUID
    task_type: TaskType
    title: str
    payload: dict[str, Any]
    schedule: TaskSchedule
    creator_principal_id: UUID | None
    creator_episode_id: UUID | None
    creation_idempotency_key: str
    created_at: datetime
    updated_at: datetime
    next_run_at: datetime
    last_run_at: datetime | None = None
    recurrence_version: int = 1
    max_attempts: int = 5
    metadata: dict[str, Any] = field(default_factory=dict)
    provenance: dict[str, Any] = field(default_factory=dict)
    status: TaskStatus = TaskStatus.ACTIVE

    def __post_init__(self) -> None:
        object.__setattr__(self, "task_type", TaskType(self.task_type))
        object.__setattr__(self, "status", TaskStatus(self.status))
        if not self.title.strip() or len(self.title) > MAX_TASK_TITLE:
            raise TaskValidationError("task title is required and bounded")
        if not self.creation_idempotency_key.strip():
            raise TaskValidationError("creation_idempotency_key is required")
        if self.max_attempts < 1 or self.max_attempts > 20:
            raise TaskValidationError("max_attempts must be between 1 and 20")
        _declarative_payload(self.payload)
        _reject_executable_keys(self.metadata)
        _reject_executable_keys(self.provenance)
        _json(self.metadata)
        _json(self.provenance)
        object.__setattr__(self, "created_at", _utc(self.created_at, "created_at"))
        object.__setattr__(self, "updated_at", _utc(self.updated_at, "updated_at"))
        object.__setattr__(self, "next_run_at", _utc(self.next_run_at, "next_run_at"))
        if self.last_run_at is not None:
            object.__setattr__(self, "last_run_at", _utc(self.last_run_at, "last_run_at"))

    @property
    def fingerprint(self) -> str:
        value = {
            "household_id": str(self.household_id),
            "task_type": self.task_type.value,
            "title": self.title,
            "payload": self.payload,
            "schedule": self.schedule.to_payload(),
            "creator_principal_id": str(self.creator_principal_id)
            if self.creator_principal_id
            else None,
            "creator_episode_id": str(self.creator_episode_id) if self.creator_episode_id else None,
        }
        return hashlib.sha256(
            json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest()

    def to_payload(self) -> dict[str, Any]:
        return {
            "task_id": str(self.task_id),
            "household_id": str(self.household_id),
            "task_type": self.task_type.value,
            "title": self.title,
            "payload": self.payload,
            "schedule": self.schedule.to_payload(),
            "creator_principal_id": str(self.creator_principal_id)
            if self.creator_principal_id
            else None,
            "creator_episode_id": str(self.creator_episode_id) if self.creator_episode_id else None,
            "creation_idempotency_key": self.creation_idempotency_key,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "next_run_at": self.next_run_at.isoformat(),
            "last_run_at": self.last_run_at.isoformat() if self.last_run_at else None,
            "recurrence_version": self.recurrence_version,
            "max_attempts": self.max_attempts,
            "metadata": self.metadata,
            "provenance": self.provenance,
            "status": self.status.value,
        }


@dataclass(frozen=True, slots=True)
class DurableTaskRun:
    run_id: UUID
    task_id: UUID
    scheduled_for: datetime
    claimed_at: datetime | None
    claimed_by: str | None
    lease_expires_at: datetime | None
    attempt: int
    status: TaskRunStatus
    source_event_id: str
    started_at: datetime | None = None
    completed_at: datetime | None = None
    outcome: dict[str, Any] | None = None
    error_class: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "status", TaskRunStatus(self.status))
        object.__setattr__(self, "scheduled_for", _utc(self.scheduled_for, "scheduled_for"))
        for name in ("claimed_at", "lease_expires_at", "started_at", "completed_at"):
            value = getattr(self, name)
            if value is not None:
                object.__setattr__(self, name, _utc(value, name))
        if self.attempt < 1:
            raise TaskValidationError("run attempt must be positive")
        _json(self.outcome or {})
        _json(self.metadata)

    def to_payload(self) -> dict[str, Any]:
        return {
            "run_id": str(self.run_id),
            "task_id": str(self.task_id),
            "scheduled_for": self.scheduled_for.isoformat(),
            "claimed_at": self.claimed_at.isoformat() if self.claimed_at else None,
            "claimed_by": self.claimed_by,
            "lease_expires_at": self.lease_expires_at.isoformat()
            if self.lease_expires_at
            else None,
            "attempt": self.attempt,
            "status": self.status.value,
            "source_event_id": self.source_event_id,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "outcome": self.outcome,
            "error_class": self.error_class,
            "metadata": self.metadata,
        }


def deterministic_run_id(task_id: UUID, scheduled_for: datetime) -> UUID:
    return uuid5(
        TASK_NAMESPACE, f"run:{task_id}:{_utc(scheduled_for, 'scheduled_for').isoformat()}"
    )


def deterministic_source_event_id(task_id: UUID, run_id: UUID, scheduled_for: datetime) -> str:
    return str(
        uuid5(
            TASK_EVENT_NAMESPACE,
            f"scheduled:{task_id}:{run_id}:{_utc(scheduled_for, 'scheduled_for').isoformat()}",
        )
    )


class TaskStore(Protocol):
    def create(self, task: DurableTask) -> DurableTask: ...

    def get(self, task_id: UUID) -> DurableTask: ...

    def list_tasks(
        self, household_id: UUID, *, status: TaskStatus | None = None
    ) -> list[DurableTask]: ...

    def cancel(self, task_id: UUID, now: datetime) -> DurableTask: ...

    def pause(self, task_id: UUID, now: datetime) -> DurableTask: ...

    def resume(self, task_id: UUID, now: datetime) -> DurableTask: ...

    def claim_due(
        self, now: datetime | None, worker_id: str, lease_seconds: int, limit: int
    ) -> list[DurableTaskRun]: ...

    def get_run(self, run_id: UUID) -> DurableTaskRun: ...

    def list_runs(self, task_id: UUID) -> list[DurableTaskRun]: ...

    def task_for_run(self, run_id: UUID) -> DurableTask: ...

    def reclaim_expired(self, now: datetime | None) -> int: ...

    def begin_dispatch(
        self, run_id: UUID, worker_id: str, now: datetime | None
    ) -> DurableTaskRun: ...

    def mark_dispatched(
        self, run_id: UUID, *, source_event_id: str, outcome: dict[str, Any], now: datetime | None
    ) -> DurableTaskRun: ...

    def cancel_run(self, run_id: UUID, now: datetime | None) -> DurableTaskRun: ...


def _next_task_run(task: DurableTask, now: datetime) -> datetime | None:
    if task.schedule.kind == ScheduleKind.ONCE:
        return None
    candidate = task.schedule.next_after(now)
    if task.schedule.expires_at is not None and candidate > task.schedule.expires_at:
        return None
    return candidate


def _occurrence_status(task: DurableTask, now: datetime) -> tuple[TaskRunStatus, dict[str, Any]]:
    late = max((now - task.next_run_at).total_seconds(), 0.0)
    grace_exceeded = (
        task.schedule.misfire_grace_seconds is not None
        and late > task.schedule.misfire_grace_seconds
    )
    recurring = task.schedule.kind != ScheduleKind.ONCE
    if grace_exceeded or (
        late > 0 and recurring and task.schedule.misfire_policy == MisfirePolicy.SKIP
    ):
        return TaskRunStatus.MISSED, {
            "misfire": True,
            "misfire_policy": task.schedule.misfire_policy.value,
            "late_seconds": late,
            "reason": "MISFIRE_GRACE_EXCEEDED" if grace_exceeded else "POLICY_SKIP",
        }
    if late > 0 and recurring and task.schedule.misfire_policy == MisfirePolicy.COALESCE_ONE:
        return TaskRunStatus.CLAIMED, {"misfire": True, "coalesced": True, "late_seconds": late}
    if late > 0:
        return TaskRunStatus.CLAIMED, {"misfire": True, "late_seconds": late}
    return TaskRunStatus.CLAIMED, {}


class InMemoryTaskStore:
    """Deterministic store used by unit tests and the simulator."""

    def __init__(self) -> None:
        self.tasks: dict[UUID, DurableTask] = {}
        self.runs: dict[UUID, DurableTaskRun] = {}
        self.by_creation_key: dict[str, tuple[UUID, str]] = {}
        self._lock = threading.RLock()

    def create(self, task: DurableTask) -> DurableTask:
        with self._lock:
            existing = self.by_creation_key.get(task.creation_idempotency_key)
            if existing:
                if existing[1] != task.fingerprint:
                    raise TaskConflict("creation idempotency key has different task parameters")
                return self.tasks[existing[0]]
            self.tasks[task.task_id] = task
            self.by_creation_key[task.creation_idempotency_key] = (task.task_id, task.fingerprint)
            return task

    def get(self, task_id: UUID) -> DurableTask:
        with self._lock:
            try:
                return self.tasks[task_id]
            except KeyError as exc:
                raise TaskNotFound(task_id) from exc

    def list_tasks(
        self, household_id: UUID, *, status: TaskStatus | None = None
    ) -> list[DurableTask]:
        with self._lock:
            values = [task for task in self.tasks.values() if task.household_id == household_id]
            if status is not None:
                values = [task for task in values if task.status == status]
            return sorted(values, key=lambda task: (task.next_run_at, str(task.task_id)))

    def _replace_task(self, task: DurableTask, **changes: Any) -> DurableTask:
        replacement = replace(task, updated_at=changes.pop("now", datetime.now(UTC)), **changes)
        self.tasks[task.task_id] = replacement
        return replacement

    def cancel(self, task_id: UUID, now: datetime) -> DurableTask:
        with self._lock:
            task = self.get(task_id)
            if task.status not in {TaskStatus.COMPLETED, TaskStatus.CANCELLED}:
                return self._replace_task(task, status=TaskStatus.CANCELLED, now=_utc(now, "now"))
            return task

    def pause(self, task_id: UUID, now: datetime) -> DurableTask:
        with self._lock:
            task = self.get(task_id)
            if task.status == TaskStatus.ACTIVE:
                return self._replace_task(task, status=TaskStatus.PAUSED, now=_utc(now, "now"))
            return task

    def resume(self, task_id: UUID, now: datetime) -> DurableTask:
        with self._lock:
            task = self.get(task_id)
            at = _utc(now, "now")
            if task.status != TaskStatus.PAUSED:
                return task
            next_run = task.next_run_at
            if task.schedule.kind != ScheduleKind.ONCE and next_run <= at:
                next_run = _next_task_run(task, at) or at
            return self._replace_task(task, status=TaskStatus.ACTIVE, next_run_at=next_run, now=at)

    def claim_due(
        self, now: datetime | None, worker_id: str, lease_seconds: int, limit: int
    ) -> list[DurableTaskRun]:
        if not worker_id.strip() or lease_seconds < 1 or limit < 1:
            raise TaskValidationError("worker_id, lease_seconds, and limit are required")
        at = _utc(now or datetime.now(UTC), "now")
        claimed: list[DurableTaskRun] = []
        with self._lock:
            # A lease can expire after the task occurrence has already advanced.
            # Reclaim that deterministic run before creating a later occurrence.
            for run in sorted(
                self.runs.values(), key=lambda item: (item.scheduled_for, str(item.run_id))
            ):
                if len(claimed) >= limit:
                    break
                if run.status != TaskRunStatus.PENDING:
                    continue
                task = self.get(run.task_id)
                if task.status not in {TaskStatus.ACTIVE, TaskStatus.COMPLETED}:
                    continue
                claimed_run = replace(
                    run,
                    status=TaskRunStatus.CLAIMED,
                    claimed_at=at,
                    claimed_by=worker_id,
                    lease_expires_at=at + timedelta(seconds=lease_seconds),
                )
                self.runs[run.run_id] = claimed_run
                claimed.append(claimed_run)
            candidates = sorted(
                self.tasks.values(), key=lambda task: (task.next_run_at, str(task.task_id))
            )
            for task in candidates:
                if len(claimed) >= limit:
                    break
                if task.status != TaskStatus.ACTIVE or task.next_run_at > at:
                    continue
                if (
                    task.schedule.expires_at is not None
                    and task.next_run_at > task.schedule.expires_at
                ):
                    self._replace_task(task, status=TaskStatus.COMPLETED, now=at)
                    continue
                run_status, metadata = _occurrence_status(task, at)
                scheduled_for = task.next_run_at
                run_id = deterministic_run_id(task.task_id, scheduled_for)
                source_event_id = deterministic_source_event_id(task.task_id, run_id, scheduled_for)
                next_run = _next_task_run(task, at)
                task_status = TaskStatus.ACTIVE if next_run is not None else TaskStatus.COMPLETED
                self._replace_task(
                    task,
                    status=task_status,
                    next_run_at=next_run or task.next_run_at,
                    last_run_at=scheduled_for,
                    recurrence_version=task.recurrence_version + (1 if next_run else 0),
                    now=at,
                )
                existing = self.runs.get(run_id)
                if existing is not None:
                    continue
                if run_status == TaskRunStatus.MISSED:
                    run = DurableTaskRun(
                        run_id,
                        task.task_id,
                        scheduled_for,
                        None,
                        None,
                        None,
                        1,
                        TaskRunStatus.MISSED,
                        source_event_id,
                        completed_at=at,
                        outcome=metadata,
                        metadata=metadata,
                    )
                else:
                    run = DurableTaskRun(
                        run_id,
                        task.task_id,
                        scheduled_for,
                        at,
                        worker_id,
                        at + timedelta(seconds=lease_seconds),
                        1,
                        TaskRunStatus.CLAIMED,
                        source_event_id,
                        metadata=metadata,
                    )
                    claimed.append(run)
                self.runs[run_id] = run
        return claimed

    def get_run(self, run_id: UUID) -> DurableTaskRun:
        with self._lock:
            try:
                return self.runs[run_id]
            except KeyError as exc:
                raise TaskNotFound(run_id) from exc

    def list_runs(self, task_id: UUID) -> list[DurableTaskRun]:
        with self._lock:
            self.get(task_id)
            return sorted(
                (run for run in self.runs.values() if run.task_id == task_id),
                key=lambda item: item.scheduled_for,
            )

    def task_for_run(self, run_id: UUID) -> DurableTask:
        return self.get(self.get_run(run_id).task_id)

    def reclaim_expired(self, now: datetime | None) -> int:
        at = _utc(now or datetime.now(UTC), "now")
        count = 0
        with self._lock:
            for run in list(self.runs.values()):
                if run.status not in {TaskRunStatus.CLAIMED, TaskRunStatus.DISPATCHING}:
                    continue
                if run.lease_expires_at is None or run.lease_expires_at > at:
                    continue
                task = self.get(run.task_id)
                if run.attempt >= task.max_attempts:
                    self.runs[run.run_id] = replace(
                        run,
                        status=TaskRunStatus.FAILED,
                        completed_at=at,
                        error_class="TASK_LEASE_ATTEMPTS_EXHAUSTED",
                    )
                else:
                    self.runs[run.run_id] = replace(
                        run,
                        status=TaskRunStatus.PENDING,
                        claimed_at=None,
                        claimed_by=None,
                        lease_expires_at=None,
                        attempt=run.attempt + 1,
                        metadata={**run.metadata, "reclaimed": True},
                    )
                count += 1
        return count

    def begin_dispatch(self, run_id: UUID, worker_id: str, now: datetime | None) -> DurableTaskRun:
        at = _utc(now or datetime.now(UTC), "now")
        with self._lock:
            run = self.get_run(run_id)
            task = self.get(run.task_id)
            if run.status not in {TaskRunStatus.CLAIMED, TaskRunStatus.PENDING}:
                return run
            if run.attempt > task.max_attempts:
                raise TaskConflict("task run exceeded maximum attempts")
            updated = replace(
                run,
                status=TaskRunStatus.DISPATCHING,
                claimed_by=worker_id,
                claimed_at=run.claimed_at or at,
                lease_expires_at=run.lease_expires_at or at + timedelta(seconds=60),
                started_at=run.started_at or at,
            )
            self.runs[run_id] = updated
            return updated

    def mark_dispatched(
        self, run_id: UUID, *, source_event_id: str, outcome: dict[str, Any], now: datetime | None
    ) -> DurableTaskRun:
        at = _utc(now or datetime.now(UTC), "now")
        with self._lock:
            run = self.get_run(run_id)
            updated = replace(
                run,
                status=TaskRunStatus.COMPLETED,
                source_event_id=source_event_id,
                completed_at=at,
                outcome=outcome,
                lease_expires_at=None,
            )
            self.runs[run_id] = updated
            return updated

    def cancel_run(self, run_id: UUID, now: datetime | None) -> DurableTaskRun:
        at = _utc(now or datetime.now(UTC), "now")
        with self._lock:
            run = self.get_run(run_id)
            if run.status in {TaskRunStatus.CLAIMED, TaskRunStatus.PENDING}:
                run = replace(run, status=TaskRunStatus.CANCELLED, completed_at=at)
                self.runs[run_id] = run
            return run


def _task_from_row(row: dict[str, Any]) -> DurableTask:
    return DurableTask(
        task_id=UUID(str(row["task_id"])),
        household_id=UUID(str(row["household_id"])),
        task_type=TaskType(str(row["task_type"])),
        title=str(row["title"]),
        payload=dict(row["payload"]),
        schedule=TaskSchedule.from_payload(dict(row["schedule"])),
        creator_principal_id=UUID(str(row["creator_principal_id"]))
        if row.get("creator_principal_id")
        else None,
        creator_episode_id=UUID(str(row["creator_episode_id"]))
        if row.get("creator_episode_id")
        else None,
        creation_idempotency_key=str(row["creation_idempotency_key"]),
        created_at=row["created_at"],
        updated_at=row["updated_at"],
        next_run_at=row["next_run_at"],
        last_run_at=row.get("last_run_at"),
        recurrence_version=int(row["recurrence_version"]),
        max_attempts=int(row["max_attempts"]),
        metadata=dict(row["metadata"]),
        provenance=dict(row["provenance"]),
        status=TaskStatus(str(row["status"])),
    )


def _run_from_row(row: dict[str, Any]) -> DurableTaskRun:
    return DurableTaskRun(
        run_id=UUID(str(row["run_id"])),
        task_id=UUID(str(row["task_id"])),
        scheduled_for=row["scheduled_for"],
        claimed_at=row.get("claimed_at"),
        claimed_by=str(row["claimed_by"]) if row.get("claimed_by") else None,
        lease_expires_at=row.get("lease_expires_at"),
        attempt=int(row["attempt"]),
        status=TaskRunStatus(str(row["status"])),
        source_event_id=str(row["source_event_id"]),
        started_at=row.get("started_at"),
        completed_at=row.get("completed_at"),
        outcome=dict(row["outcome"]) if row.get("outcome") else None,
        error_class=str(row["error_class"]) if row.get("error_class") else None,
        metadata=dict(row["metadata"]),
    )


class PostgresTaskStore:
    """Persistent task/run store with short database-time claim transactions."""

    def __init__(self, database_url: str, connect_timeout: int = 5) -> None:
        self.database_url = database_url
        self.connect_timeout = connect_timeout

    def _connect(self) -> psycopg.Connection[Any]:
        return psycopg.connect(
            self.database_url, connect_timeout=self.connect_timeout, row_factory=dict_row
        )

    def create(self, task: DurableTask) -> DurableTask:
        with self._connect() as connection, connection.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO anima_durable_tasks (
                    task_id, household_id, task_type, title, payload, schedule, timezone,
                    status, creator_principal_id, creator_episode_id, creation_idempotency_key,
                    creation_fingerprint, created_at, updated_at, next_run_at, last_run_at,
                    recurrence_version, misfire_policy, max_attempts, metadata, provenance
                ) VALUES (
                    %s, %s, %s, %s, %s::jsonb, %s::jsonb, %s, %s, %s, %s, %s,
                    %s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb, %s::jsonb
                )
                ON CONFLICT (creation_idempotency_key) DO NOTHING
                RETURNING *
                """,
                (
                    task.task_id,
                    task.household_id,
                    task.task_type.value,
                    task.title,
                    json.dumps(task.payload, sort_keys=True),
                    json.dumps(task.schedule.to_payload(), sort_keys=True),
                    task.schedule.timezone,
                    task.status.value,
                    task.creator_principal_id,
                    task.creator_episode_id,
                    task.creation_idempotency_key,
                    task.fingerprint,
                    task.created_at,
                    task.updated_at,
                    task.next_run_at,
                    task.last_run_at,
                    task.recurrence_version,
                    task.schedule.misfire_policy.value,
                    task.max_attempts,
                    json.dumps(task.metadata, sort_keys=True),
                    json.dumps(task.provenance, sort_keys=True),
                ),
            )
            row = cursor.fetchone()
            if row is None:
                cursor.execute(
                    "SELECT * FROM anima_durable_tasks WHERE creation_idempotency_key = %s",
                    (task.creation_idempotency_key,),
                )
                row = cursor.fetchone()
                if row is None:
                    raise TaskConflict("task insert conflict could not be resolved")
                if str(row["creation_fingerprint"]) != task.fingerprint:
                    raise TaskConflict("creation idempotency key has different task parameters")
            connection.commit()
        return _task_from_row(dict(row))

    def get(self, task_id: UUID) -> DurableTask:
        with self._connect() as connection, connection.cursor() as cursor:
            cursor.execute("SELECT * FROM anima_durable_tasks WHERE task_id = %s", (task_id,))
            row = cursor.fetchone()
        if row is None:
            raise TaskNotFound(task_id)
        return _task_from_row(dict(row))

    def list_tasks(
        self, household_id: UUID, *, status: TaskStatus | None = None
    ) -> list[DurableTask]:
        query = "SELECT * FROM anima_durable_tasks WHERE household_id = %s"
        params: list[Any] = [household_id]
        if status is not None:
            query += " AND status = %s"
            params.append(status.value)
        query += " ORDER BY next_run_at, task_id"
        with self._connect() as connection, connection.cursor() as cursor:
            cursor.execute(query, params)
            rows = list(cursor.fetchall())
        return [_task_from_row(dict(row)) for row in rows]

    def _set_status(
        self,
        task_id: UUID,
        status: TaskStatus,
        now: datetime,
        *,
        next_run_at: datetime | None = None,
    ) -> DurableTask:
        with self._connect() as connection, connection.cursor() as cursor:
            cursor.execute(
                """
                UPDATE anima_durable_tasks SET status=%s, updated_at=%s,
                    next_run_at=COALESCE(%s, next_run_at)
                WHERE task_id=%s RETURNING *
                """,
                (status.value, _utc(now, "now"), next_run_at, task_id),
            )
            row = cursor.fetchone()
            if row is None:
                raise TaskNotFound(task_id)
            connection.commit()
        return _task_from_row(dict(row))

    def cancel(self, task_id: UUID, now: datetime) -> DurableTask:
        return self._set_status(task_id, TaskStatus.CANCELLED, now)

    def pause(self, task_id: UUID, now: datetime) -> DurableTask:
        return self._set_status(task_id, TaskStatus.PAUSED, now)

    def resume(self, task_id: UUID, now: datetime) -> DurableTask:
        task = self.get(task_id)
        at = _utc(now, "now")
        next_run = task.next_run_at
        if task.schedule.kind != ScheduleKind.ONCE and next_run <= at:
            next_run = _next_task_run(task, at) or at
        return self._set_status(task_id, TaskStatus.ACTIVE, at, next_run_at=next_run)

    def claim_due(
        self, now: datetime | None, worker_id: str, lease_seconds: int, limit: int
    ) -> list[DurableTaskRun]:
        if not worker_id.strip() or lease_seconds < 1 or limit < 1:
            raise TaskValidationError("worker_id, lease_seconds, and limit are required")
        with self._connect() as connection, connection.cursor() as cursor:
            cursor.execute("SELECT now() AS database_now")
            db_now_row = cursor.fetchone()
            assert db_now_row is not None
            at = (
                _utc(now, "now")
                if now is not None
                else _utc(db_now_row["database_now"], "database_now")
            )
            cursor.execute(
                """
                SELECT run.* FROM anima_durable_task_runs AS run
                JOIN anima_durable_tasks AS task ON task.task_id = run.task_id
                WHERE run.status='PENDING' AND task.status IN ('ACTIVE','COMPLETED')
                ORDER BY run.scheduled_for, run.run_id
                FOR UPDATE OF run SKIP LOCKED
                LIMIT %s
                """,
                (limit,),
            )
            reclaimed_rows = list(cursor.fetchall())
            claimed: list[DurableTaskRun] = []
            for raw in reclaimed_rows:
                cursor.execute(
                    """
                    UPDATE anima_durable_task_runs SET status='CLAIMED', claimed_at=%s,
                        claimed_by=%s, lease_expires_at=%s WHERE run_id=%s RETURNING *
                    """,
                    (at, worker_id, at + timedelta(seconds=lease_seconds), raw["run_id"]),
                )
                updated = cursor.fetchone()
                if updated is not None:
                    claimed.append(_run_from_row(dict(updated)))
            remaining = limit - len(claimed)
            if remaining <= 0:
                connection.commit()
                return claimed
            cursor.execute(
                """
                SELECT * FROM anima_durable_tasks
                WHERE status='ACTIVE' AND next_run_at <= %s
                ORDER BY next_run_at, task_id
                FOR UPDATE SKIP LOCKED
                LIMIT %s
                """,
                (at, remaining),
            )
            rows = list(cursor.fetchall())
            for raw in rows:
                task = _task_from_row(dict(raw))
                run_status, metadata = _occurrence_status(task, at)
                scheduled_for = task.next_run_at
                run_id = deterministic_run_id(task.task_id, scheduled_for)
                source_event_id = deterministic_source_event_id(task.task_id, run_id, scheduled_for)
                next_run = _next_task_run(task, at)
                task_status = TaskStatus.ACTIVE if next_run is not None else TaskStatus.COMPLETED
                cursor.execute(
                    """
                    UPDATE anima_durable_tasks SET status=%s, updated_at=%s,
                        next_run_at=COALESCE(%s, next_run_at), last_run_at=%s,
                        recurrence_version=recurrence_version + %s
                    WHERE task_id=%s
                    """,
                    (
                        task_status.value,
                        at,
                        next_run,
                        scheduled_for,
                        1 if next_run else 0,
                        task.task_id,
                    ),
                )
                cursor.execute(
                    """
                    INSERT INTO anima_durable_task_runs (
                        run_id, task_id, scheduled_for, claimed_at, claimed_by,
                        lease_expires_at, attempt, status, source_event_id, completed_at,
                        outcome, metadata
                    ) VALUES (%s,%s,%s,%s,%s,%s,1,%s,%s,%s,%s::jsonb,%s::jsonb)
                    ON CONFLICT (task_id, scheduled_for) DO NOTHING
                    RETURNING *
                    """,
                    (
                        run_id,
                        task.task_id,
                        scheduled_for,
                        None if run_status == TaskRunStatus.MISSED else at,
                        None if run_status == TaskRunStatus.MISSED else worker_id,
                        None
                        if run_status == TaskRunStatus.MISSED
                        else at + timedelta(seconds=lease_seconds),
                        run_status.value
                        if run_status == TaskRunStatus.MISSED
                        else TaskRunStatus.CLAIMED.value,
                        source_event_id,
                        at if run_status == TaskRunStatus.MISSED else None,
                        json.dumps(metadata, sort_keys=True),
                        json.dumps(metadata, sort_keys=True),
                    ),
                )
                inserted = cursor.fetchone()
                if inserted and run_status != TaskRunStatus.MISSED:
                    claimed.append(_run_from_row(dict(inserted)))
            connection.commit()
        return claimed

    def get_run(self, run_id: UUID) -> DurableTaskRun:
        with self._connect() as connection, connection.cursor() as cursor:
            cursor.execute("SELECT * FROM anima_durable_task_runs WHERE run_id = %s", (run_id,))
            row = cursor.fetchone()
        if row is None:
            raise TaskNotFound(run_id)
        return _run_from_row(dict(row))

    def list_runs(self, task_id: UUID) -> list[DurableTaskRun]:
        # Household ownership is checked by the caller through get(task_id).
        self.get(task_id)
        with self._connect() as connection, connection.cursor() as cursor:
            cursor.execute(
                "SELECT * FROM anima_durable_task_runs WHERE task_id=%s ORDER BY scheduled_for",
                (task_id,),
            )
            rows = list(cursor.fetchall())
        return [_run_from_row(dict(row)) for row in rows]

    def task_for_run(self, run_id: UUID) -> DurableTask:
        run = self.get_run(run_id)
        return self.get(run.task_id)

    def reclaim_expired(self, now: datetime | None) -> int:
        with self._connect() as connection, connection.cursor() as cursor:
            cursor.execute("SELECT now() AS database_now")
            row = cursor.fetchone()
            assert row is not None
            at = _utc(now, "now") if now else _utc(row["database_now"], "database_now")
            cursor.execute(
                """
                UPDATE anima_durable_task_runs AS run SET
                    status = CASE
                        WHEN run.attempt >= task.max_attempts THEN 'FAILED'
                        ELSE 'PENDING' END,
                    claimed_at = CASE
                        WHEN run.attempt >= task.max_attempts THEN run.claimed_at
                        ELSE NULL END,
                    claimed_by = CASE
                        WHEN run.attempt >= task.max_attempts THEN run.claimed_by
                        ELSE NULL END,
                    lease_expires_at = CASE
                        WHEN run.attempt >= task.max_attempts THEN run.lease_expires_at
                        ELSE NULL END,
                    attempt = CASE
                        WHEN run.attempt >= task.max_attempts THEN run.attempt
                        ELSE run.attempt + 1 END,
                    completed_at = CASE
                        WHEN run.attempt >= task.max_attempts THEN %s
                        ELSE run.completed_at END,
                    error_class = CASE
                        WHEN run.attempt >= task.max_attempts
                        THEN 'TASK_LEASE_ATTEMPTS_EXHAUSTED'
                        ELSE run.error_class END,
                    metadata = run.metadata || '{"reclaimed": true}'::jsonb
                FROM anima_durable_tasks AS task
                WHERE run.task_id = task.task_id
                  AND run.status IN ('CLAIMED','DISPATCHING')
                  AND run.lease_expires_at IS NOT NULL AND run.lease_expires_at <= %s
                """,
                (at, at),
            )
            count = cursor.rowcount
            connection.commit()
        return count

    def begin_dispatch(self, run_id: UUID, worker_id: str, now: datetime | None) -> DurableTaskRun:
        at = _utc(now or datetime.now(UTC), "now")
        with self._connect() as connection, connection.cursor() as cursor:
            cursor.execute(
                """
                UPDATE anima_durable_task_runs SET status='DISPATCHING',
                    claimed_by=COALESCE(claimed_by,%s), claimed_at=COALESCE(claimed_at,%s),
                    started_at=COALESCE(started_at,%s),
                    lease_expires_at=COALESCE(lease_expires_at,%s)
                WHERE run_id=%s AND status IN ('CLAIMED','PENDING')
                RETURNING *
                """,
                (worker_id, at, at, at + timedelta(seconds=60), run_id),
            )
            row = cursor.fetchone()
            if row is None:
                cursor.execute("SELECT * FROM anima_durable_task_runs WHERE run_id=%s", (run_id,))
                row = cursor.fetchone()
            if row is None:
                raise TaskNotFound(run_id)
            connection.commit()
        return _run_from_row(dict(row))

    def mark_dispatched(
        self, run_id: UUID, *, source_event_id: str, outcome: dict[str, Any], now: datetime | None
    ) -> DurableTaskRun:
        at = _utc(now or datetime.now(UTC), "now")
        with self._connect() as connection, connection.cursor() as cursor:
            cursor.execute(
                """
                UPDATE anima_durable_task_runs SET status='COMPLETED',
                    source_event_id=%s, completed_at=%s, outcome=%s::jsonb,
                    lease_expires_at=NULL
                WHERE run_id=%s RETURNING *
                """,
                (source_event_id, at, json.dumps(outcome, sort_keys=True), run_id),
            )
            row = cursor.fetchone()
            if row is None:
                raise TaskNotFound(run_id)
            connection.commit()
        return _run_from_row(dict(row))

    def cancel_run(self, run_id: UUID, now: datetime | None) -> DurableTaskRun:
        at = _utc(now or datetime.now(UTC), "now")
        with self._connect() as connection, connection.cursor() as cursor:
            cursor.execute(
                """
                UPDATE anima_durable_task_runs SET status='CANCELLED', completed_at=%s
                WHERE run_id=%s AND status IN ('PENDING','CLAIMED') RETURNING *
                """,
                (at, run_id),
            )
            row = cursor.fetchone()
            if row is None:
                cursor.execute("SELECT * FROM anima_durable_task_runs WHERE run_id=%s", (run_id,))
                row = cursor.fetchone()
            if row is None:
                raise TaskNotFound(run_id)
            connection.commit()
        return _run_from_row(dict(row))


class EventSink(Protocol):
    def append(self, event: EventEnvelope) -> Any: ...


@dataclass(frozen=True, slots=True)
class DispatchReport:
    claimed: int
    dispatched: int
    failed: int
    run_ids: tuple[UUID, ...]


class DurableTaskDispatcher:
    """Claims due runs, emits deterministic events, and closes dispatch records."""

    def __init__(
        self, store: TaskStore, event_sink: EventSink, *, worker_id: str, lease_seconds: int = 30
    ) -> None:
        if not worker_id.strip():
            raise TaskValidationError("worker_id is required")
        self.store = store
        self.event_sink = event_sink
        self.worker_id = worker_id
        self.lease_seconds = lease_seconds

    @staticmethod
    def event_for(task: DurableTask, run: DurableTaskRun) -> EventEnvelope:
        subject_refs = task.payload.get("subject_refs", [])
        bounded_refs = (
            [str(item) for item in subject_refs[:32]] if isinstance(subject_refs, list) else []
        )
        payload = {
            "task_id": str(task.task_id),
            "run_id": str(run.run_id),
            "task_type": task.task_type.value,
            "summary": task.title,
            "objective": task.payload.get("objective")
            or task.payload.get("question")
            or task.payload.get("summary"),
            "subject_refs": bounded_refs,
            "creator_principal_id": str(task.creator_principal_id)
            if task.creator_principal_id
            else None,
            "creator_episode_id": str(task.creator_episode_id) if task.creator_episode_id else None,
            "scheduled_for": run.scheduled_for.isoformat(),
            "run_metadata": run.metadata,
        }
        return EventEnvelope.create(
            event_id=run.source_event_id,
            source_event_id=run.source_event_id,
            event_type="scheduled_reasoning_due",
            source="anima:durable-task",
            subject_key=f"task/{task.task_id}",
            occurred_at=run.scheduled_for,
            payload=payload,
            importance=EventImportance.IMPORTANT,
            delivery_class=DeliveryClass.GUARANTEED,
            metadata={"household_id": str(task.household_id), "task_run_id": str(run.run_id)},
        )

    def run_once(self, *, now: datetime | None = None, limit: int = 100) -> DispatchReport:
        self.store.reclaim_expired(now)
        runs = self.store.claim_due(now, self.worker_id, self.lease_seconds, limit)
        dispatched = 0
        failed = 0
        for run in runs:
            try:
                current = self.store.begin_dispatch(run.run_id, self.worker_id, now)
                task = self.store.task_for_run(current.run_id)
                if task.status == TaskStatus.CANCELLED:
                    self.store.cancel_run(current.run_id, now)
                    continue
                event = self.event_for(task, current)
                self.event_sink.append(event)
                self.store.mark_dispatched(
                    current.run_id,
                    source_event_id=event.event_id,
                    outcome={"event_id": event.event_id, "event_type": event.event_type},
                    now=now,
                )
                dispatched += 1
            except Exception:
                failed += 1
        return DispatchReport(len(runs), dispatched, failed, tuple(run.run_id for run in runs))

    def diagnostics(self, *, now: datetime | None = None) -> dict[str, Any]:
        del now
        started = time.perf_counter()
        elapsed = (time.perf_counter() - started) * 1000
        return {"worker_id": self.worker_id, "poll_elapsed_ms": round(elapsed, 3)}


@dataclass(frozen=True, slots=True)
class TaskMutationResult:
    task: DurableTask
    event_id: str | None


class TaskService:
    """Policy-facing task operations and append-only lifecycle audit."""

    def __init__(self, store: TaskStore, event_sink: EventSink | None = None) -> None:
        self.store = store
        self.event_sink = event_sink

    def create(
        self,
        *,
        household_id: UUID,
        task_type: TaskType,
        title: str,
        payload: dict[str, Any],
        schedule: TaskSchedule,
        creation_idempotency_key: str,
        creator_principal_id: UUID | None = None,
        creator_episode_id: UUID | None = None,
        metadata: dict[str, Any] | None = None,
        provenance: dict[str, Any] | None = None,
        now: datetime | None = None,
    ) -> DurableTask:
        at = _utc(now or datetime.now(UTC), "now")
        task = DurableTask(
            task_id=uuid4(),
            household_id=household_id,
            task_type=task_type,
            title=title,
            payload=_declarative_payload(payload),
            schedule=schedule,
            creator_principal_id=creator_principal_id,
            creator_episode_id=creator_episode_id,
            creation_idempotency_key=creation_idempotency_key,
            created_at=at,
            updated_at=at,
            next_run_at=schedule.run_at,
            metadata=metadata or {},
            provenance=provenance or {},
        )
        stored = self.store.create(task)
        if stored.task_id == task.task_id:
            self._audit(
                "task.created", stored, {"creation_idempotency_key": creation_idempotency_key}
            )
        return stored

    def get(self, task_id: UUID) -> DurableTask:
        return self.store.get(task_id)

    def list_tasks(
        self, household_id: UUID, *, status: TaskStatus | None = None
    ) -> list[DurableTask]:
        return self.store.list_tasks(household_id, status=status)

    def list_runs(self, task_id: UUID) -> list[DurableTaskRun]:
        return self.store.list_runs(task_id)

    def cancel(self, task_id: UUID, *, now: datetime | None = None) -> TaskMutationResult:
        task = self.store.cancel(task_id, _utc(now or datetime.now(UTC), "now"))
        return TaskMutationResult(task, self._audit("task.cancelled", task, {}))

    def pause(self, task_id: UUID, *, now: datetime | None = None) -> TaskMutationResult:
        task = self.store.pause(task_id, _utc(now or datetime.now(UTC), "now"))
        return TaskMutationResult(task, self._audit("task.paused", task, {}))

    def resume(self, task_id: UUID, *, now: datetime | None = None) -> TaskMutationResult:
        task = self.store.resume(task_id, _utc(now or datetime.now(UTC), "now"))
        return TaskMutationResult(task, self._audit("task.resumed", task, {}))

    def _audit(self, event_type: str, task: DurableTask, payload: dict[str, Any]) -> str | None:
        if self.event_sink is None:
            return None
        event = EventEnvelope.create(
            event_id=str(uuid4()),
            event_type=event_type,
            source="anima:durable-task",
            subject_key=f"task/{task.task_id}",
            occurred_at=datetime.now(UTC),
            payload={"task_id": str(task.task_id), **payload},
            importance=EventImportance.IMPORTANT,
            delivery_class=DeliveryClass.GUARANTEED,
            metadata={"household_id": str(task.household_id)},
        )
        self.event_sink.append(event)
        return event.event_id


class TaskNativePlugin:
    """Bounded Phase 5 native capability facade for declarative task operations."""

    def __init__(self, service: TaskService) -> None:
        self.service = service

    def start(self, secret_env: dict[str, str]) -> None:
        if secret_env:
            raise PluginValidationError("durable task plugin accepts no secrets")

    def stop(self) -> None:
        return None

    def list_tools(self) -> list[dict[str, Any]]:
        return [dict(item) for item in TASK_MANIFEST.tools]

    def invoke(self, name: str, arguments: dict[str, Any], timeout: float) -> Any:
        raise PluginValidationError("task plugin requires trusted household invocation context")

    def invoke_for_household(
        self, name: str, arguments: dict[str, Any], timeout: float, household_id: UUID
    ) -> Any:
        del timeout
        if name == "schedule":
            schedule = TaskSchedule.from_payload(dict(arguments["schedule"]))
            task = self.service.create(
                household_id=household_id,
                task_type=TaskType(str(arguments["task_type"])),
                title=str(arguments["title"]),
                payload=dict(arguments["payload"]),
                schedule=schedule,
                creation_idempotency_key=str(arguments["creation_idempotency_key"]),
                creator_principal_id=UUID(str(arguments["creator_principal_id"]))
                if arguments.get("creator_principal_id")
                else None,
                creator_episode_id=UUID(str(arguments["creator_episode_id"]))
                if arguments.get("creator_episode_id")
                else None,
                provenance={"created_via": "tasks.schedule"},
            )
            return {"task": task.to_payload()}
        if name == "list":
            status = TaskStatus(str(arguments["status"])) if arguments.get("status") else None
            return {
                "tasks": [
                    task.to_payload()
                    for task in self.service.list_tasks(household_id, status=status)
                ]
            }
        if name == "get":
            task = self.service.get(UUID(str(arguments["task_id"])))
            if task.household_id != household_id:
                raise TaskNotFound(arguments["task_id"])
            return {"task": task.to_payload()}
        task_id = UUID(str(arguments["task_id"]))
        task = self.service.get(task_id)
        if task.household_id != household_id:
            raise TaskNotFound(arguments["task_id"])
        mutation = {
            "cancel": self.service.cancel,
            "pause": self.service.pause,
            "resume": self.service.resume,
        }.get(name)
        if mutation is None:
            raise PluginValidationError(f"unknown durable task tool: {name}")
        return {"task": mutation(task_id).task.to_payload()}


def _task_input_schema(name: str) -> dict[str, Any]:
    if name == "schedule":
        return {
            "type": "object",
            "required": ["task_type", "title", "payload", "schedule", "creation_idempotency_key"],
            "properties": {
                "task_type": {"type": "string", "enum": [item.value for item in TaskType]},
                "title": {"type": "string", "minLength": 1, "maxLength": MAX_TASK_TITLE},
                "payload": {"type": "object"},
                "schedule": {"type": "object"},
                "creation_idempotency_key": {"type": "string", "minLength": 1, "maxLength": 200},
                "creator_principal_id": {"type": ["string", "null"]},
                "creator_episode_id": {"type": ["string", "null"]},
            },
            "additionalProperties": False,
        }
    if name == "list":
        return {
            "type": "object",
            "properties": {"status": {"type": ["string", "null"]}},
            "additionalProperties": False,
        }
    return {
        "type": "object",
        "required": ["task_id"],
        "properties": {"task_id": {"type": "string", "format": "uuid"}},
        "additionalProperties": False,
    }


TASK_MANIFEST = PluginManifest(
    plugin_id="anima.durable-tasks",
    plugin_version="0.1.0",
    manifest_version=MANIFEST_VERSION,
    requires_core=CORE_VERSION,
    name="ANIMA durable tasks",
    description="Declarative future cognition opportunities on the ANIMA PostgreSQL substrate",
    runtime_kind=RuntimeKind.TRUSTED_NATIVE,
    trust_class=TrustClass.TRUSTED_NATIVE,
    capabilities=("durable_tasks",),
    tools=tuple(
        {
            "name": name,
            "description": description,
            "input_schema": _task_input_schema(name),
            "output_schema": {"type": "object"},
            "semantic_action": semantic_action,
            "risk_class": risk_class,
            "read_only": read_only,
            "idempotency": Idempotency.KEYED.value
            if not read_only
            else Idempotency.IDEMPOTENT.value,
            "external_content_trust": ExternalContentTrust.LOCAL_TRUSTED.value,
        }
        for name, description, semantic_action, risk_class, read_only in (
            (
                "schedule",
                "Schedule a future cognition opportunity",
                "schedule_task",
                "EXTERNAL_SIDE_EFFECT",
                False,
            ),
            ("list", "List household durable tasks", "list_tasks", "READ_ONLY", True),
            ("get", "Get one household durable task", "get_task", "READ_ONLY", True),
            (
                "cancel",
                "Cancel a household durable task",
                "cancel_task",
                "EXTERNAL_SIDE_EFFECT",
                False,
            ),
            (
                "pause",
                "Pause a household durable task",
                "pause_task",
                "EXTERNAL_SIDE_EFFECT",
                False,
            ),
            (
                "resume",
                "Resume a household durable task",
                "resume_task",
                "EXTERNAL_SIDE_EFFECT",
                False,
            ),
        )
    ),
    source="builtin:anima_ha.tasks",
)


@dataclass(frozen=True, slots=True)
class ScheduledCognitionResult:
    dispatch: DispatchReport
    attention: Any
    episodes: tuple[Any, ...]


class ScheduledCognitionBridge:
    """Connect due task events to fresh Phase 7/8 cognition inputs."""

    def __init__(
        self,
        dispatcher: DurableTaskDispatcher,
        attention: PostgresAttentionService,
        context: ContextBroker,
        agent_runtime: Any,
    ) -> None:
        self.dispatcher = dispatcher
        self.attention = attention
        self.context = context
        self.agent_runtime = agent_runtime

    def run_once(
        self,
        *,
        profile: AttentionProfile,
        household_id: UUID,
        request_factory: Callable[[ReasoningTrigger, ContextPacket], Any],
        tools: list[Any] | None = None,
        now: datetime | None = None,
        limit: int = 100,
    ) -> ScheduledCognitionResult:
        dispatch = self.dispatcher.run_once(now=now, limit=limit)
        attention_result = self.attention.process(profile, limit=limit)
        episodes: list[Any] = []
        for trigger in self.attention.list_triggers(profile.profile_version):
            if trigger.status.value != "PENDING":
                continue
            if str(trigger.metadata.get("household_id", household_id)) != str(household_id):
                continue
            packet = self.context.assemble(
                trigger,
                household_id=household_id,
                tools=tools,
                assembled_at=now,
                persist=True,
            )
            episodes.append(self.agent_runtime.run(request_factory(trigger, packet)))
        return ScheduledCognitionResult(dispatch, attention_result, tuple(episodes))


class TaskWorker:
    """Small local worker loop; it owns no cognition or provider authority."""

    def __init__(self, dispatcher: DurableTaskDispatcher, poll_seconds: float = 1.0) -> None:
        if poll_seconds <= 0 or poll_seconds > 60:
            raise TaskValidationError("poll_seconds must be between 0 and 60")
        self.dispatcher = dispatcher
        self.poll_seconds = poll_seconds

    def run_once(self, *, limit: int = 100) -> DispatchReport:
        return self.dispatcher.run_once(limit=limit)

    def run_forever(self, *, limit: int = 100, stop: threading.Event | None = None) -> None:
        stopper = stop or threading.Event()
        while not stopper.is_set():
            self.run_once(limit=limit)
            stopper.wait(self.poll_seconds)


def main() -> int:
    """Dispatch due declarative task events once, or run the bounded worker loop."""
    parser = argparse.ArgumentParser(description="Dispatch ANIMA durable task events")
    parser.add_argument("--worker-id", default="anima-task-worker")
    parser.add_argument("--limit", type=int, default=100)
    parser.add_argument("--poll-seconds", type=float, default=1.0)
    parser.add_argument("--forever", action="store_true")
    args = parser.parse_args()
    import os

    database_url = os.environ.get("ANIMA_DATABASE_URL", "").strip()
    if not database_url:
        parser.error("ANIMA_DATABASE_URL is required")
    from anima_ha.journal import PostgresEventJournal

    dispatcher = DurableTaskDispatcher(
        PostgresTaskStore(database_url),
        PostgresEventJournal(database_url),
        worker_id=args.worker_id,
    )
    worker = TaskWorker(dispatcher, args.poll_seconds)
    if args.forever:
        worker.run_forever(limit=args.limit)
    else:
        report = worker.run_once(limit=args.limit)
        print(
            json.dumps(
                {
                    "claimed": report.claimed,
                    "dispatched": report.dispatched,
                    "failed": report.failed,
                }
            )
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
