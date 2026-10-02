"""Opt-in, exact fresh Core-event claims; no backlog recovery or provider execution.

ANIMA_SENTRY_AUTOWAKE_ENABLED_AT is a server-owned aware ISO timestamp. Missing
means disabled. Restart does not invent an enable epoch. Client bounds may only
tighten that epoch and the 120-second maximum age. No new persistence substrate.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from time import monotonic
from typing import Any
from uuid import UUID

import psycopg
from psycopg.rows import dict_row

from anima_ha.intelligence import (
    SENTRY_REQUEST_READY_CHANNEL,
    IntelligenceRequest,
    _request_from_row,
)


def aware_timestamp(value: str) -> datetime:
    result = datetime.fromisoformat(value)
    if result.tzinfo is None or result.utcoffset() is None:
        raise ValueError("auto-wake requires an aware timestamp")
    return result.astimezone(UTC)


@dataclass(frozen=True)
class AutoWakeWindow:
    not_before: datetime | None
    max_age_seconds: int
    owner_tasks_only: bool = False


# Join immutable, server-written journal provenance, not just request metadata.
# Context identity and the single-source trigger must agree with the request.
_ELIGIBLE = """
    r.household_id=%s AND r.provider_id=%s
    AND r.origin IN ('AUTONOMOUS_ATTENTION','DURABLE_TASK')
    AND r.lifecycle='PENDING' AND NOT r.provider_invocation_started
    AND r.attempt_count=0 AND r.fencing_generation=0
    AND r.claim_owner IS NULL AND r.lease_expires_at IS NULL
    AND r.result_status IS NULL AND r.completed_at IS NULL
    AND r.created_at <= now()
    AND (r.request_metadata->'owner_task' IS NOT NULL OR r.created_at >= %s)
    AND (r.request_metadata->'owner_task' IS NOT NULL
        OR r.created_at >= now() - (%s * interval '1 second'))
    AND EXISTS (
        SELECT 1 FROM anima_reasoning_triggers t
        JOIN anima_event_journal e ON e.event_id=r.causation_id
        JOIN anima_context_packets c ON c.trigger_id=t.trigger_id
        WHERE t.trigger_id=r.trigger_id
          AND t.source_event_ids=jsonb_build_array(e.event_id)
          AND t.journal_position_start=e.journal_position
          AND t.journal_position_end=e.journal_position
          AND t.metadata->>'household_id'=r.household_id::text
          AND e.metadata->>'household_id'=r.household_id::text
          AND c.context_packet_id=r.context_packet_id AND c.packet_digest=r.context_digest
          AND t.status IN ('PENDING','CONTEXT_READY')
          AND e.occurred_at <= now()
          AND (r.request_metadata->'owner_task' IS NOT NULL OR e.occurred_at >= %s)
          AND (r.request_metadata->'owner_task' IS NOT NULL
              OR e.occurred_at >= now() - (%s * interval '1 second'))
          AND e.delivery_class='GUARANTEED'
          AND ((r.origin='AUTONOMOUS_ATTENTION' AND r.principal_id IS NULL
                AND e.source!='anima:durable-task')
            OR (r.origin='DURABLE_TASK' AND e.source='anima:durable-task'))
          AND (
            (e.source='anima:senseguard-policy'
             AND e.event_type IN ('senseguard.opened','senseguard.event')
             AND e.metadata->>'provenance'='anima.senseguard.alert_policy'
             AND e.metadata->>'delivery_mode'='SENTRY_COGNITION')
            OR (e.source='anima.household_presence'
                AND e.event_type='household.presence.connection_changed'
                AND e.payload->>'household_id'=r.household_id::text
                AND e.payload->>'signal_kind'='ROUTER_WIFI'
                AND e.payload->>'transition' IN ('RECONNECTED','DISCONNECTED')
                AND e.payload->'is_authentication'='false'::jsonb
                AND e.payload->'door_actor_verified'='false'::jsonb)
            OR (e.source='anima.ring'
                AND e.event_type IN ('household.ring.motion','household.ring.doorbell')
                AND e.payload->>'household_id'=r.household_id::text
                AND e.payload->>'time_basis'='HA_EVENT_RECEIVED'
                AND e.payload->'physical_actor_verified'='false'::jsonb)
            OR (e.source LIKE 'android-relay-report:%%'
                AND e.event_type IN (
                    'external.android.motion_reported','external.android.lock_reported'
                )
                AND e.metadata->>'household_id'=r.household_id::text
                AND e.metadata->>'schema_qualification'='ANIMA_OWNED_SCHEMA'
                AND e.metadata->>'external_content_trust'='EXTERNAL_UNTRUSTED'
                AND e.metadata->'synthetic'='false'::jsonb
                AND e.metadata->'producer_qualified'='true'::jsonb
                AND e.metadata->'wake_eligible'='true'::jsonb
                AND e.payload->>'authority'='NONE')
            OR (e.source='anima:durable-task' AND e.event_type='scheduled_reasoning_due'
                AND (EXISTS (
                    SELECT 1 FROM anima_durable_tasks task
                    JOIN anima_durable_task_runs run ON run.task_id=task.task_id
                    JOIN anima_memory_records settings
                      ON settings.memory_id::text=task.provenance->>'config_version'
                    WHERE task.task_id::text=e.payload->>'task_id'
                      AND run.run_id::text=e.payload->>'run_id'
                      AND run.source_event_id=e.event_id
                      AND run.status IN ('DISPATCHED','COMPLETED')
                      AND run.outcome->>'event_id'=e.event_id
                      AND task.household_id=r.household_id AND task.status='ACTIVE'
                      AND r.principal_id IS NULL
                      AND task.metadata->>'created_via'='household_learning'
                      AND task.provenance->>'kind'='HOUSEHOLD_REVIEW'
                      AND settings.household_id=r.household_id AND settings.status='ACTIVE'
                      AND settings.provenance_kind='EXPLICIT_INPUT'
                      AND settings.metadata->>'record_kind'='household_initiative_config'
                      AND (settings.expires_at IS NULL OR settings.expires_at > now())
                      AND ((task.payload->>'review_kind'='DAILY'
                            AND settings.metadata->'config'->'daily_review_enabled'='true'::jsonb)
                        OR (task.payload->>'review_kind'='ROUTINE'
                            AND settings.metadata->'config'->'routine_review_enabled'
                                ='true'::jsonb))
                ) OR EXISTS (
                    SELECT 1 FROM anima_durable_tasks task
                    JOIN anima_durable_task_runs run ON run.task_id=task.task_id
                    JOIN anima_graph_nodes person ON person.canonical_id=task.creator_principal_id
                    JOIN anima_graph_relationships member ON member.source_id=person.canonical_id
                      AND member.target_id=task.household_id
                      AND member.relationship_type='MEMBER_OF'
                      AND member.retired_at IS NULL
                    JOIN anima_graph_nodes household ON household.canonical_id=task.household_id
                      AND household.kind='HOUSEHOLD' AND household.retired_at IS NULL
                    WHERE task.task_id::text=e.payload->>'task_id'
                      AND run.run_id::text=e.payload->>'run_id' AND run.source_event_id=e.event_id
                      AND run.status IN ('DISPATCHED','COMPLETED')
                      AND run.attempt BETWEEN 1 AND task.max_attempts
                      AND run.outcome->>'event_id'=e.event_id
                      AND run.claimed_at<=run.started_at AND run.started_at<=now()
                      AND task.created_at<=run.claimed_at
                      AND task.household_id=r.household_id
                      AND task.status IN ('ACTIVE','COMPLETED')
                      AND task.creator_principal_id=r.principal_id
                      AND person.retired_at IS NULL AND person.kind='PERSON'
                      AND person.metadata->>'semantic_role' IN ('owner','member','resident')
                      AND COALESCE(person.metadata->>'sentry_access','LIMITED')
                          IN ('LIMITED','UNRESTRICTED')
                      AND task.provenance->>'created_via'='tasks.schedule'
                      AND task.provenance->>'origin'='DIRECT_USER'
                      AND task.provenance->'owner_result_contract'='1'::jsonb
                      AND (task.schedule->>'run_at')::timestamptz>task.created_at
                      AND ((task.schedule->>'expires_at') IS NULL
                        OR (task.schedule->>'expires_at')::timestamptz>=now())
                      AND ((task.schedule->>'misfire_grace_seconds') IS NULL
                        OR EXTRACT(EPOCH FROM (run.started_at-run.scheduled_for))
                           <= (task.schedule->>'misfire_grace_seconds')::integer)
                      AND task.creation_fingerprint=e.payload->>'task_fingerprint'
                      AND r.request_metadata->'owner_task'->>'fingerprint'=task.creation_fingerprint
                      AND r.request_metadata->'owner_task'->>'task_id'=task.task_id::text
                      AND r.request_metadata->'owner_task'->>'run_id'=run.run_id::text
                      AND r.request_metadata->'owner_task'->>'delivery_intent'
                          ='SAVED_OWNER_TASK_RESULT'
                )))
          )
    )
"""


class PostgresAutoWakeClaims:
    def __init__(self, database_url: str, *, enabled_at: datetime | None) -> None:
        self.database_url = database_url
        self.enabled_at = aware_timestamp(enabled_at.isoformat()) if enabled_at else None

    def window(
        self, body: dict[str, Any], *, deterministic_delivery: bool = False
    ) -> AutoWakeWindow:
        if body.get("origin") == "DURABLE_TASK":
            # Saved task consent/freshness is in the exact immutable SQL join.
            # This cannot commission autonomous events or learning reviews.
            if set(body) & {"not_before", "max_age_seconds"}:
                raise ValueError("owner task scope has no autonomous enable epoch")
            return AutoWakeWindow(None, 120, owner_tasks_only=True)
        if body.get("origin") != "AUTONOMOUS_ATTENTION":
            raise ValueError("auto-wake origin must be AUTONOMOUS_ATTENTION")
        age = body.get("max_age_seconds", 120)
        if type(age) is not int or not 1 <= age <= 120:
            raise ValueError("max_age_seconds must be an integer from 1 to 120")
        epoch = aware_timestamp(str(body.get("not_before", "")))
        if self.enabled_at is None and not deterministic_delivery:
            raise ValueError("autonomous reasoning is not commissioned")
        return AutoWakeWindow(max(epoch, self.enabled_at) if self.enabled_at else epoch, age)

    @staticmethod
    def _scope(window: AutoWakeWindow) -> str:
        return _ELIGIBLE + (
            " AND r.origin='DURABLE_TASK' AND r.request_metadata->'owner_task' IS NOT NULL "
            if window.owner_tasks_only
            else ""
        )

    @staticmethod
    def _parameters(
        household_id: UUID, provider_id: str, window: AutoWakeWindow
    ) -> tuple[Any, ...]:
        return (
            household_id,
            provider_id,
            window.not_before,
            window.max_age_seconds,
            window.not_before,
            window.max_age_seconds,
        )

    def _eligible(
        self,
        connection: psycopg.Connection[Any],
        household_id: UUID,
        provider_id: str,
        window: AutoWakeWindow,
        *,
        limit: int,
    ) -> list[dict[str, Any]]:
        if type(limit) is not int or not 1 <= limit <= 10:
            raise ValueError("limit must be an integer from 1 to 10")
        rows = connection.execute(
            "SELECT r.request_id,r.household_id,r.provider_id,r.origin,r.created_at,"
            "r.request_metadata->>'sentry_event_path' AS sentry_event_path "
            "FROM anima_intelligence_requests r WHERE "
            + self._scope(window)
            + " ORDER BY CASE WHEN (r.request_metadata->>'priority') ~ '^-?[0-9]+$' "
            "THEN (r.request_metadata->>'priority')::integer ELSE 0 END DESC,"
            "r.created_at,r.request_id LIMIT %s",
            (*self._parameters(household_id, provider_id, window), limit),
        ).fetchall()
        return [
            {
                key: value.isoformat() if isinstance(value, datetime) else str(value)
                for key, value in row.items()
            }
            for row in rows
        ]

    def eligible(
        self, household_id: UUID, provider_id: str, window: AutoWakeWindow, *, limit: int
    ) -> list[dict[str, Any]]:
        with psycopg.connect(
            self.database_url,
            row_factory=dict_row,
            connect_timeout=5,
            options="-c statement_timeout=5000",
        ) as connection:
            return self._eligible(connection, household_id, provider_id, window, limit=limit)

    def wait(
        self,
        household_id: UUID,
        provider_id: str,
        window: AutoWakeWindow,
        *,
        limit: int,
        wait_seconds: int,
    ) -> list[dict[str, Any]]:
        """Wait for durable eligible work without polling the model or database."""
        if type(wait_seconds) is not int or not 1 <= wait_seconds <= 30:
            raise ValueError("wait_seconds must be an integer from 1 to 30")
        with psycopg.connect(
            self.database_url,
            autocommit=True,
            row_factory=dict_row,
            connect_timeout=5,
            options="-c statement_timeout=35000",
        ) as connection:
            connection.execute(f"LISTEN {SENTRY_REQUEST_READY_CHANNEL}")
            # LISTEN first, then query, so a commit cannot be lost between the
            # initial read and entering the wait.
            items = self._eligible(connection, household_id, provider_id, window, limit=limit)
            if items:
                return items
            deadline = monotonic() + wait_seconds
            while True:
                remaining = deadline - monotonic()
                if remaining <= 0:
                    return []
                notified = next(connection.notifies(timeout=remaining, stop_after=1), None)
                if notified is None:
                    return []
                items = self._eligible(connection, household_id, provider_id, window, limit=limit)
                if items:
                    return items

    def claim(
        self,
        request_id: UUID,
        household_id: UUID,
        provider_id: str,
        worker_id: str,
        window: AutoWakeWindow,
    ) -> tuple[IntelligenceRequest, datetime] | None:
        if not worker_id.strip() or len(worker_id) > 256:
            raise ValueError("invalid auto-wake worker")
        with psycopg.connect(
            self.database_url,
            row_factory=dict_row,
            connect_timeout=5,
            options="-c statement_timeout=5000",
        ) as connection:
            # A locked candidate and rechecked predicates prevent list/claim races.
            # There is intentionally no existing-active-request fallback.
            row = connection.execute(
                "WITH candidate AS (SELECT r.request_id FROM anima_intelligence_requests r "
                "WHERE "
                + self._scope(window)
                + " AND r.request_id=%s FOR UPDATE OF r SKIP LOCKED) "
                "UPDATE anima_intelligence_requests r SET lifecycle='CLAIMED',claim_owner=%s,"
                "fencing_generation=r.fencing_generation+1,attempt_count=r.attempt_count+1,"
                "lease_expires_at=now()+interval '120 seconds',updated_at=now() "
                "FROM candidate WHERE r.request_id=candidate.request_id RETURNING r.*",
                (*self._parameters(household_id, provider_id, window), request_id, worker_id),
            ).fetchone()
            if row is None:
                return None
            connection.execute(
                "INSERT INTO anima_intelligence_transitions "
                "(request_id,from_lifecycle,to_lifecycle,fencing_generation,actor) "
                "VALUES (%s,'PENDING','CLAIMED',%s,%s)",
                (request_id, row["fencing_generation"], worker_id),
            )
        return _request_from_row(row), row["created_at"]
