"""Opt-in dispatcher for only the saved household learning configuration's tasks.

No implicit scheduling, backlog scan, embedded cognition, provider call, or deployment.
Explicit reconcile=True reuses saved owner configuration through TaskService.
Constructing this worker starts nothing. Core explicitly calls run_once/start.
Successful dispatch means a durable SENTRY request, not a completed review.
"""

from __future__ import annotations

import threading
from datetime import datetime
from typing import Any
from uuid import UUID, uuid4

from anima_ha.attention import AttentionProfile
from anima_ha.events import EventEnvelope
from anima_ha.intelligence import IntelligenceProviderMode, SentryAttentionBridge
from anima_ha.tasks import (
    DurableTask,
    DurableTaskDispatcher,
    PostgresTaskStore,
    TaskStatus,
    TaskType,
)


class LearningReviewError(ValueError):
    """Only fixed, non-payload error categories cross the worker boundary."""


class LearningReviewRunner:
    def __init__(
        self,
        core: Any,
        learning: Any,
        household_id: UUID,
        *,
        poll_seconds: float = 30.0,
        lease_seconds: int = 60,
        reconcile: bool = False,
    ) -> None:
        if not isinstance(household_id, UUID) or not household_id.int:
            raise LearningReviewError("INVALID_HOUSEHOLD")
        if isinstance(poll_seconds, bool) or not 1 <= poll_seconds <= 60:
            raise LearningReviewError("INVALID_POLL_INTERVAL")
        if type(lease_seconds) is not int or not 10 <= lease_seconds <= 300:
            raise LearningReviewError("INVALID_LEASE_INTERVAL")
        if type(reconcile) is not bool:
            raise LearningReviewError("INVALID_RECONCILE_FLAG")
        self.core, self.learning, self.household_id = core, learning, household_id
        self.poll_seconds, self.lease_seconds = poll_seconds, lease_seconds
        self.reconcile = reconcile
        self.worker_id = f"learning-review:{household_id}:{uuid4()}"
        self._stop = threading.Event()
        self._tick_lock = threading.Lock()
        self._lifecycle_lock = threading.Lock()
        self._thread: threading.Thread | None = None
        self.last_report = self._report("NOT_STARTED")
        self._dispatch_error: str | None = None

    @staticmethod
    def _report(status: str, *, error: str | None = None) -> dict[str, Any]:
        return {
            "status": status,
            "claimed": 0,
            "dispatched": 0,
            "failed": 0,
            "error_category": error,
            "review_execution": "NOT_OBSERVED",
        }

    def _provider_ready(self) -> bool:
        return (
            self.core.intelligence_provider == IntelligenceProviderMode.SENTRY
            and self.core.intelligence_store is not None
        )

    def _tasks(self) -> tuple[PostgresTaskStore, dict[UUID, DurableTask]]:
        service = self.learning.task_service
        store = service.store if service is not None else None
        if not isinstance(store, PostgresTaskStore):
            raise LearningReviewError("POSTGRES_TASK_STORE_REQUIRED")
        # This lean server-only projection avoids loading household evidence on
        # every idle poll. It does not create defaults, tasks or config versions.
        status = self.learning.review_task_scope(self.household_id)
        version = status.get("config_version")
        if version is None:
            return store, {}
        try:
            config_version = UUID(version)
        except (ValueError, TypeError, AttributeError):
            raise LearningReviewError("INVALID_CONFIG_SCOPE") from None
        if not config_version.int:
            raise LearningReviewError("INVALID_CONFIG_SCOPE")
        config = status.get("config")
        scheduling = status.get("scheduling")
        if not isinstance(config, dict) or not isinstance(scheduling, dict):
            raise LearningReviewError("INVALID_CONFIG_SCOPE")
        items = scheduling.get("tasks")
        if not isinstance(items, list) or len(items) > 2:
            raise LearningReviewError("INVALID_TASK_SCOPE")
        tasks: dict[UUID, DurableTask] = {}
        kinds = set()
        for item in items:
            if not isinstance(item, dict) or item.get("kind") not in {"DAILY", "ROUTINE"}:
                raise LearningReviewError("INVALID_TASK_SCOPE")
            kind = item["kind"]
            enabled = config.get(
                "daily_review_enabled" if kind == "DAILY" else "routine_review_enabled"
            )
            if enabled is not True:
                raise LearningReviewError("DISABLED_TASK_IN_SCOPE")
            try:
                task_id = UUID(item["task_id"])
            except (KeyError, ValueError, TypeError, AttributeError):
                raise LearningReviewError("INVALID_TASK_SCOPE") from None
            if task_id in tasks or kind in kinds:
                raise LearningReviewError("DUPLICATE_TASK_SCOPE")
            task = store.get(task_id)
            if (
                task.household_id != self.household_id
                or task.task_type != TaskType.REASONING_DUE
                or task.status != TaskStatus.ACTIVE
                or task.creation_idempotency_key
                != f"household-learning:{self.household_id}:{config_version}:{kind}"
                or task.metadata.get("created_via") != "household_learning"
                or task.payload.get("review_kind") != kind
                or task.payload.get("config_version") != str(config_version)
                or task.provenance.get("kind") != "HOUSEHOLD_REVIEW"
                or task.provenance.get("config_version") != str(config_version)
            ):
                raise LearningReviewError("TASK_PROVENANCE_MISMATCH")
            tasks[task_id] = task
            kinds.add(kind)
        return store, tasks

    def _append_review(self, event: EventEnvelope) -> Any:
        """Journal then exact-event Attention; retry retains both stable IDs."""
        self._dispatch_error = "REVIEW_SCOPE_CHANGED"
        _, tasks = self._tasks()
        if not self._provider_ready():
            raise LearningReviewError("SENTRY_UNAVAILABLE")
        try:
            task_id = UUID(event.payload["task_id"])
        except (KeyError, ValueError, TypeError):
            raise LearningReviewError("INVALID_REVIEW_EVENT") from None
        if (
            task_id not in tasks
            or event.source != "anima:durable-task"
            or event.event_type != "scheduled_reasoning_due"
            or event.metadata.get("household_id") != str(self.household_id)
            or event.subject_key != f"task/{task_id}"
        ):
            raise LearningReviewError("REVIEW_SCOPE_CHANGED")
        self._dispatch_error = "REVIEW_JOURNAL_FAILED"
        appended = self.core.journal.append(event)
        self._dispatch_error = "REVIEW_SCOPE_CHANGED"
        # A disabled/replaced config must not consume an already-journaled event.
        _, current = self._tasks()
        if current.get(task_id) != tasks[task_id] or not self._provider_ready():
            raise LearningReviewError("REVIEW_SCOPE_CHANGED")
        self._dispatch_error = "SENTRY_ATTENTION_ENQUEUE_FAILED"
        # Event-specific profile/consumer cannot traverse prior or following
        # guaranteed events. Source-ID filtering precedes context assembly.
        profile = AttentionProfile(
            f"household.learning.review.v1:{self.household_id}:{event.event_id}", ()
        )
        consumer = f"learning-review:{self.household_id}:{event.event_id}"
        self.core.attention.prime_consumer_before(profile, consumer, appended.journal_position - 1)
        requests = SentryAttentionBridge(
            attention=self.core.attention,
            context=self.core.context,
            store=self.core.intelligence_store,
            profile=profile,
        ).run_once(
            household_id=self.household_id,
            tools=self.core.plugins.list_tools(),
            principal_id=None,
            consumer_name=consumer,
            limit=1,
            source_event_id=event.event_id,
        )
        if len(requests) != 1 or any(
            request.household_id != self.household_id
            or request.causation_id != event.event_id
            or request.provider_id != "sentry"
            for request in requests
        ):
            raise LearningReviewError("SENTRY_ATTENTION_ENQUEUE_FAILED")
        self._dispatch_error = None
        return appended

    def run_once(self, *, now: datetime | None = None) -> dict[str, Any]:
        if not self._tick_lock.acquire(blocking=False):
            return self._report("BUSY")
        try:
            if not self._provider_ready():
                report = self._report("DISABLED", error="SENTRY_UNAVAILABLE")
            else:
                if self.reconcile:
                    self.learning.ensure_review_tasks(self.household_id)
                base, tasks = self._tasks()
                if not tasks:
                    report = self._report("IDLE")
                else:
                    scoped = PostgresTaskStore(
                        base.database_url,
                        base.connect_timeout,
                        claim_household_id=self.household_id,
                        claim_task_ids=tuple(sorted(tasks)),
                    )
                    sink = _ReviewSink(self)
                    self._dispatch_error = None
                    dispatched = DurableTaskDispatcher(
                        scoped,
                        sink,
                        worker_id=self.worker_id,
                        lease_seconds=self.lease_seconds,
                    ).run_once(now=now, limit=2)
                    report = self._report(
                        "PARTIAL"
                        if dispatched.failed
                        else "DISPATCHED"
                        if dispatched.dispatched
                        else "IDLE",
                        error=(self._dispatch_error or "TASK_DISPATCH_FAILED")
                        if dispatched.failed
                        else None,
                    )
                    report.update(
                        claimed=dispatched.claimed,
                        dispatched=dispatched.dispatched,
                        failed=dispatched.failed,
                    )
            self.last_report = report
        except Exception as exc:
            # Never log DB exception strings, payloads, objectives or credentials.
            category = (
                str(exc) if isinstance(exc, LearningReviewError) else "LEARNING_REVIEW_FAILED"
            )
            self.last_report = self._report("FAILED", error=category)
        finally:
            self._tick_lock.release()
        return dict(self.last_report)

    def tick(self, *, now: datetime | None = None) -> dict[str, Any]:
        return self.run_once(now=now)

    def run(self) -> None:
        while not self._stop.is_set():
            self.run_once()
            self._stop.wait(self.poll_seconds)

    def start(self) -> None:
        with self._lifecycle_lock:
            if self._thread is not None and self._thread.is_alive():
                return
            self._stop.clear()
            self._thread = threading.Thread(
                target=self.run, name="anima-learning-review", daemon=True
            )
            self._thread.start()

    def stop(self, timeout: float = 5.0) -> bool:
        if not 0 <= timeout <= 60:
            raise LearningReviewError("INVALID_STOP_TIMEOUT")
        with self._lifecycle_lock:
            self._stop.set()
            thread = self._thread
        if thread is not None and thread is not threading.current_thread():
            thread.join(timeout)
        return thread is None or not thread.is_alive()


class _ReviewSink:
    def __init__(self, runner: LearningReviewRunner) -> None:
        self.runner = runner

    def append(self, event: EventEnvelope) -> Any:
        return self.runner._append_review(event)
