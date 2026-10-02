"""Saved owner tasks composed with current Journal/Attention/frozen SENTRY.

This is a scoped EventSink for the existing dispatcher, not another scheduler
or executor. Learning review claims retain their independent saved-consent scope.
Only future, explicitly saved current-member cognition/reminder work is eligible;
dispatch completion is never a result or a delivery receipt.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from anima_ha.attention import AttentionProfile, SentryEventPath
from anima_ha.events import EventEnvelope
from anima_ha.intelligence import IntelligenceOrigin, IntelligenceRequest, SentryAttentionBridge
from anima_ha.policy import (
    ActionIntent,
    Assurance,
    Decision,
    IdentityContext,
    PolicyContext,
    RequestOrigin,
)
from anima_ha.tasks import (
    DurableTask,
    DurableTaskDispatcher,
    PostgresTaskStore,
    TaskRunStatus,
    TaskStatus,
)


class OwnerTaskError(ValueError):
    """Content-free scope failure; no task objective/credentials in diagnostics."""


class OwnerTaskResults:
    def __init__(self, core: Any, tasks: PostgresTaskStore, household_id: UUID) -> None:
        self.core, self.tasks, self.household_id = core, tasks, household_id

    def _saved(self, task: DurableTask) -> bool:
        return bool(
            task.household_id == self.household_id
            and task.creator_principal_id is not None
            and task.provenance.get("created_via") == "tasks.schedule"
            and task.provenance.get("origin") == "DIRECT_USER"
            and task.provenance.get("owner_result_contract") == 1
            and task.provenance.get("tool_request_id")
            and task.provenance.get("invocation_ordinal")
            and task.schedule.run_at > task.created_at
            and task.status in {TaskStatus.ACTIVE, TaskStatus.COMPLETED}
        )

    def _creator(self, task: DurableTask) -> bool:
        principal = task.creator_principal_id
        return bool(
            self._saved(task)
            and any(
                node.canonical_id == principal
                for node in self.core.graph.members_of_household(self.household_id)
            )
            and any(
                node.canonical_id == self.household_id
                for node in self.core.graph.households_for_member(principal)
            )
            and self.core.identity_resolver.resolve_role(principal)
            in {"owner", "member", "resident"}
            and self.core.identity_resolver.resolve_access_level(principal)
            in {"LIMITED", "UNRESTRICTED"}
        )

    def validate_event(self, event: EventEnvelope, *, now: datetime | None = None) -> DurableTask:
        at = now or datetime.now(UTC)
        try:
            task = self.tasks.get(UUID(event.payload["task_id"]))
            run = self.tasks.get_run(UUID(event.payload["run_id"]))
            qualified = (
                self._creator(task)
                and run.task_id == task.task_id
                and run.status
                in {TaskRunStatus.DISPATCHING, TaskRunStatus.DISPATCHED, TaskRunStatus.COMPLETED}
                and 1 <= run.attempt <= task.max_attempts
                and run.source_event_id == event.event_id
                and event.source_event_id == event.event_id
                and event.source == "anima:durable-task"
                and event.event_type == "scheduled_reasoning_due"
                and event.metadata.get("household_id") == str(self.household_id)
                and event.subject_key == f"task/{task.task_id}"
                and event.payload == DurableTaskDispatcher.event_for(task, run).payload
                and event.occurred_at == run.scheduled_for
                and task.created_at < run.scheduled_for <= at
                and (task.schedule.expires_at is None or at <= task.schedule.expires_at)
                and (
                    task.schedule.misfire_grace_seconds is None
                    or (
                        run.started_at is not None
                        and (run.started_at - run.scheduled_for).total_seconds()
                        <= task.schedule.misfire_grace_seconds
                    )
                )
                and run.claimed_at is not None
                and run.started_at is not None
                and task.created_at <= run.claimed_at <= run.started_at <= at
            )
        except (KeyError, TypeError, ValueError):
            qualified = False
        if not qualified:
            raise OwnerTaskError("OWNER_TASK_CURRENT_SCOPE_UNAVAILABLE")
        return task

    def validate_request(self, request: IntelligenceRequest) -> DurableTask | None:
        scope = request.request_metadata.get("owner_task")
        if scope is None:
            return None
        event = self.core.journal.get(request.causation_id)
        if event is None:
            raise OwnerTaskError("OWNER_TASK_SOURCE_UNAVAILABLE")
        task = self.validate_event(event)
        if (
            request.origin != IntelligenceOrigin.DURABLE_TASK
            or request.household_id != task.household_id
            or request.principal_id != task.creator_principal_id
            or scope != self.scope(event, task)
        ):
            raise OwnerTaskError("OWNER_TASK_REQUEST_SCOPE_CHANGED")
        return task

    @staticmethod
    def scope(event: EventEnvelope, task: DurableTask) -> dict[str, Any]:
        return {
            "task_id": str(task.task_id),
            "run_id": event.payload["run_id"],
            "fingerprint": task.fingerprint,
            "creator_principal_id": str(task.creator_principal_id),
            "delivery_intent": "SAVED_OWNER_TASK_RESULT",
        }

    def notification(self, request: IntelligenceRequest) -> dict[str, Any] | None:
        if "owner_task" not in request.request_metadata:
            return None
        task = self.validate_request(request)
        assert task is not None
        decision = self.core.policy_service.evaluate(
            ActionIntent.create(
                household_id=request.household_id,
                principal_id=request.principal_id,
                semantic_action="notifications.send",
                origin=RequestOrigin.DURABLE_SYSTEM_TASK,
                graph_metadata={"external_side_effect": True},
                correlation_id=str(request.request_id),
                causation_id=request.causation_id,
            ),
            IdentityContext(
                request.household_id,
                request.principal_id,
                Assurance.RECOGNIZED,
                explanation="Saved task principal, no authenticated execution upgrade",
            ),
            PolicyContext(
                principal_role=self.core.identity_resolver.resolve_role(request.principal_id),
                graph_metadata={
                    "notification_alert_authorized": True,
                    "notification_route_id": "sentry-owner-task-result",
                    "alert_policy_id": str(task.task_id),
                    "owner_task_run_id": request.request_metadata["owner_task"]["run_id"],
                    "originating_request_id": str(request.request_id),
                },
            ),
        )
        allowed = decision.decision == Decision.ALLOW
        return {
            "status": "AVAILABLE",
            "owner_task": {
                **request.request_metadata["owner_task"],
                "task_type": task.task_type.value,
            },
            "notification": {
                "request_id": str(request.request_id),
                "allowed": allowed,
                "required": False,
                "reason": "EXPLICIT_OWNER_TASK" if allowed else "UNAVAILABLE",
                "policy_reason": decision.reason_code,
                "evaluated_at": datetime.now(UTC).isoformat(),
                "sentry_event_path": SentryEventPath.AGGREGATED_REASONING.value,
                "delivery": (
                    "CURRENT_CONFIGURED_CHANNEL_OR_OWNER_RESULT_SURFACE; NOT_DELIVERY_PROOF"
                ),
            },
        }

    def handoff(self, event: EventEnvelope, position: int) -> None:
        task = self.validate_event(event)
        with self.core.intelligence_store._connect() as connection:
            existing = connection.execute(
                "SELECT request_metadata->'owner_task' AS scope "
                "FROM anima_intelligence_requests WHERE household_id=%s AND causation_id=%s "
                "AND origin='DURABLE_TASK' AND principal_id=%s",
                (self.household_id, event.event_id, task.creator_principal_id),
            ).fetchall()
        if existing:
            if len(existing) == 1 and existing[0]["scope"] == self.scope(event, task):
                return
            raise OwnerTaskError("OWNER_TASK_HANDOFF_SCOPE_CONFLICT")
        profile = AttentionProfile(f"owner.task.v1:{self.household_id}:{event.event_id}", ())
        consumer = f"owner-task:{self.household_id}:{event.event_id}"
        self.core.attention.prime_consumer_before(profile, consumer, position - 1)
        # Future cognition is not unattended consequential household execution.
        # Existing typed read-only/external fetch and scoped notification tools
        # still require their current policies; no saved identity upgrade.
        tools = [
            tool
            for tool in self.core.plugins.list_tools()
            if tool.read_only or tool.semantic_action == "notifications.send"
        ]
        requests = SentryAttentionBridge(
            attention=self.core.attention,
            context=self.core.context,
            store=self.core.intelligence_store,
            profile=profile,
            origin=IntelligenceOrigin.DURABLE_TASK,
            event_path_resolver=lambda *_: SentryEventPath.AGGREGATED_REASONING,
        ).run_once(
            household_id=self.household_id,
            principal_id=task.creator_principal_id,
            tools=tools,
            consumer_name=consumer,
            limit=1,
            source_event_id=event.event_id,
            request_metadata={"owner_task": self.scope(event, task)},
        )
        if len(requests) != 1:
            raise OwnerTaskError("OWNER_TASK_HANDOFF_UNAVAILABLE")

    def append(self, event: EventEnvelope) -> Any:
        try:
            self.validate_event(event)
        except OwnerTaskError:
            # A known pre-Journal scope rejection has not executed a provider
            # or external operation. Close only this exact commissioned run;
            # transport/append ambiguities still use the dispatch lease.
            run = self.tasks.get_run(UUID(event.payload["run_id"]))
            task = self.tasks.get(run.task_id)
            expected = DurableTaskDispatcher.event_for(task, run)
            if (
                self._saved(task)
                and event.event_id == expected.event_id
                and event.payload == expected.payload
                and event.metadata == expected.metadata
            ):
                with self.tasks._connect() as connection:
                    changed = connection.execute(
                        "UPDATE anima_durable_task_runs SET status='FAILED',completed_at=now(),"
                        "error_class='OWNER_TASK_CURRENT_SCOPE_UNAVAILABLE',lease_expires_at=NULL "
                        "WHERE run_id=%s AND source_event_id=%s AND status='DISPATCHING' "
                        "RETURNING run_id",
                        (run.run_id, event.event_id),
                    ).fetchone()
                    if changed is not None:
                        connection.execute(
                            "UPDATE anima_durable_tasks SET status='FAILED',updated_at=now() "
                            "WHERE task_id=%s",
                            (task.task_id,),
                        )
            raise
        appended = self.core.journal.append(event)
        self.handoff(event, appended.journal_position)
        return appended

    def run_once(self, *, now: datetime | None = None) -> dict[str, Any]:
        tasks = [
            task.task_id for task in self.tasks.list_tasks(self.household_id) if self._saved(task)
        ]
        if not tasks:
            return {"status": "IDLE", "claimed": 0, "dispatched": 0, "failed": 0}
        scoped = PostgresTaskStore(
            self.tasks.database_url,
            self.tasks.connect_timeout,
            claim_household_id=self.household_id,
            claim_task_ids=tuple(tasks),
        )
        report = DurableTaskDispatcher(
            scoped, self, worker_id=f"owner-task:{self.household_id}", lease_seconds=60
        ).run_once(now=now, limit=10)
        return {
            "status": "PARTIAL" if report.failed else "DISPATCHED" if report.dispatched else "IDLE",
            "claimed": report.claimed,
            "dispatched": report.dispatched,
            "failed": report.failed,
        }
