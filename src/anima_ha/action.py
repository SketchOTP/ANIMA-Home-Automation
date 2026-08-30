"""Deterministic action execution boundary for consequential tool requests.

The agent may propose an action, but this module owns the final safety checks:
fresh-state validation, policy reauthorization, short-lived resource
serialization, durable idempotency, connector invocation, observed
verification, and crash reconciliation.  It deliberately does not retry or
compensate an ambiguous external side effect.
"""

from __future__ import annotations

import hashlib
import json
import threading
from collections.abc import Callable, Mapping
from contextlib import AbstractContextManager
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from struct import unpack
from typing import Any, Protocol
from uuid import UUID, uuid4

import psycopg
from psycopg.rows import dict_row

from anima_ha.events import EventEnvelope
from anima_ha.plugins import (
    Idempotency,
    InvocationOutcome,
    InvocationResult,
    ToolDescriptor,
)
from anima_ha.policy import (
    ActionIntent,
    ConfirmationChallenge,
    Decision,
    IdentityContext,
    PolicyContext,
    PolicyService,
    RequestOrigin,
    TruthPolicyContext,
)


class ActionStatus(StrEnum):
    PLANNED = "PLANNED"
    EXECUTING = "EXECUTING"
    SUCCEEDED = "SUCCEEDED"
    FAILED = "FAILED"
    RESOURCE_BUSY = "RESOURCE_BUSY"
    PRECONDITION_FAILED = "PRECONDITION_FAILED"
    POLICY_DENIED = "POLICY_DENIED"
    REQUIRE_CONFIRMATION = "REQUIRE_CONFIRMATION"
    REQUIRE_STRONGER_AUTH = "REQUIRE_STRONGER_AUTH"
    VERIFICATION_FAILED = "VERIFICATION_FAILED"
    UNKNOWN_RESULT = "UNKNOWN_RESULT"
    PARTIAL = "PARTIAL"
    RECOVERY_REQUIRED = "RECOVERY_REQUIRED"


class VerificationOutcome(StrEnum):
    VERIFIED = "VERIFIED"
    FAILED = "FAILED"
    UNKNOWN = "UNKNOWN"


@dataclass(frozen=True, slots=True)
class TruthSnapshot:
    """The latest provider-backed state used for action decisions."""

    values: Mapping[str, Mapping[str, Any]] = field(default_factory=dict)

    def to_payload(self) -> dict[str, Any]:
        return {str(key): dict(value) for key, value in sorted(self.values.items())}


@dataclass(frozen=True, slots=True)
class TruthPrecondition:
    truth_key: str
    expected_state: str | None = None
    expected_value: Any = None
    expected_version: str | None = None

    def matches(self, snapshot: TruthSnapshot) -> bool:
        current = snapshot.values.get(self.truth_key)
        if current is None:
            return False
        if self.expected_state is not None and str(current.get("state")) != self.expected_state:
            return False
        if self.expected_value is not None and current.get("value") != self.expected_value:
            return False
        if (
            self.expected_version is not None
            and str(current.get("version")) != self.expected_version
        ):
            return False
        return True

    def to_payload(self) -> dict[str, Any]:
        return {
            "truth_key": self.truth_key,
            "expected_state": self.expected_state,
            "expected_value": self.expected_value,
            "expected_version": self.expected_version,
        }


@dataclass(frozen=True, slots=True)
class VerificationResult:
    outcome: VerificationOutcome
    observed: dict[str, Any] = field(default_factory=dict)
    detail: str | None = None


TruthRefresher = Callable[[tuple[UUID, ...]], TruthSnapshot]
ActionVerifier = Callable[["ActionRequest", InvocationResult, TruthSnapshot], VerificationResult]


@dataclass(frozen=True, slots=True)
class ActionRequest:
    action_id: UUID
    idempotency_key: str
    household_id: UUID
    tool: ToolDescriptor
    arguments: dict[str, Any]
    identity: IdentityContext
    policy_service: PolicyService
    policy_context: PolicyContext = field(default_factory=PolicyContext)
    resource_ids: tuple[UUID, ...] = ()
    preconditions: tuple[TruthPrecondition, ...] = ()
    refresher: TruthRefresher | None = None
    verifier: ActionVerifier | None = None
    confirmation: ConfirmationChallenge | None = None
    origin: RequestOrigin = RequestOrigin.AUTONOMOUS_AGENT
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    def __post_init__(self) -> None:
        if not self.idempotency_key.strip():
            raise ValueError("idempotency_key is required")
        if self.household_id != self.identity.household_id:
            raise ValueError("action household and identity household must match")
        object.__setattr__(self, "created_at", self.created_at.astimezone(UTC))

    @classmethod
    def create(
        cls,
        *,
        idempotency_key: str,
        household_id: UUID,
        tool: ToolDescriptor,
        arguments: dict[str, Any],
        identity: IdentityContext,
        policy_service: PolicyService,
        **kwargs: Any,
    ) -> ActionRequest:
        resource_values: list[UUID] = []
        raw_resource = arguments.get("resource_id")
        if raw_resource is not None:
            resource_values.append(UUID(str(raw_resource)))
        raw_resources = arguments.get("resource_ids", ())
        if isinstance(raw_resources, list | tuple):
            resource_values.extend(UUID(str(value)) for value in raw_resources)
        provided_resources = kwargs.pop("resource_ids", None)
        return cls(
            action_id=UUID(str(kwargs.pop("action_id", uuid4()))),
            idempotency_key=idempotency_key,
            household_id=household_id,
            tool=tool,
            arguments=dict(arguments),
            identity=identity,
            policy_service=policy_service,
            resource_ids=tuple(sorted(set(provided_resources or resource_values))),
            **kwargs,
        )

    @property
    def request_digest(self) -> str:
        payload = {
            "household_id": str(self.household_id),
            "tool_id": self.tool.tool_id,
            "tool_version": self.tool.version,
            "arguments": self.arguments,
            "resource_ids": [str(item) for item in self.resource_ids],
            "preconditions": [item.to_payload() for item in self.preconditions],
        }
        return hashlib.sha256(
            json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str).encode()
        ).hexdigest()


@dataclass(frozen=True, slots=True)
class ActionRecord:
    action_id: UUID
    idempotency_key: str
    request_digest: str
    household_id: UUID
    tool_id: str
    status: ActionStatus
    created_at: datetime
    updated_at: datetime
    detail: str | None = None
    result: dict[str, Any] | None = None
    latest_truth: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class ActionExecutionResult:
    record: ActionRecord
    invocation: InvocationResult | None = None
    duplicate: bool = False
    idempotency_conflict: bool = False


@dataclass(frozen=True, slots=True)
class ActionClaim:
    record: ActionRecord
    duplicate: bool = False
    idempotency_conflict: bool = False


class ActionStore(Protocol):
    def claim(self, request: ActionRequest) -> ActionClaim: ...

    def update(
        self,
        action_id: UUID,
        status: ActionStatus,
        *,
        detail: str | None = None,
        result: dict[str, Any] | None = None,
        latest_truth: dict[str, Any] | None = None,
    ) -> ActionRecord: ...

    def get(self, action_id: UUID) -> ActionRecord | None: ...

    def recover_incomplete(self) -> list[ActionRecord]: ...

    def record_effects(self, action_id: UUID, result: dict[str, Any]) -> None: ...


def _now() -> datetime:
    return datetime.now(UTC)


def _record(
    request: ActionRequest,
    *,
    status: ActionStatus,
    detail: str | None = None,
    result: dict[str, Any] | None = None,
    latest_truth: dict[str, Any] | None = None,
    updated_at: datetime | None = None,
) -> ActionRecord:
    stamp = updated_at or _now()
    return ActionRecord(
        request.action_id,
        request.idempotency_key,
        request.request_digest,
        request.household_id,
        request.tool.tool_id,
        status,
        request.created_at,
        stamp,
        detail,
        result,
        latest_truth or {},
    )


class InMemoryActionStore:
    """Deterministic test store mirroring the PostgreSQL uniqueness rules."""

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self.records: dict[UUID, ActionRecord] = {}
        self.by_key: dict[str, UUID] = {}
        self.effects: list[dict[str, Any]] = []

    def claim(self, request: ActionRequest) -> ActionClaim:
        with self._lock:
            existing_id = self.by_key.get(request.idempotency_key)
            if existing_id is not None:
                existing = self.records[existing_id]
                return ActionClaim(
                    existing,
                    duplicate=existing.request_digest == request.request_digest,
                    idempotency_conflict=existing.request_digest != request.request_digest,
                )
            record = _record(request, status=ActionStatus.PLANNED)
            self.records[request.action_id] = record
            self.by_key[request.idempotency_key] = request.action_id
            return ActionClaim(record)

    def update(
        self,
        action_id: UUID,
        status: ActionStatus,
        *,
        detail: str | None = None,
        result: dict[str, Any] | None = None,
        latest_truth: dict[str, Any] | None = None,
    ) -> ActionRecord:
        with self._lock:
            old = self.records[action_id]
            new = ActionRecord(
                old.action_id,
                old.idempotency_key,
                old.request_digest,
                old.household_id,
                old.tool_id,
                status,
                old.created_at,
                _now(),
                detail,
                result,
                old.latest_truth if latest_truth is None else latest_truth,
            )
            self.records[action_id] = new
            return new

    def get(self, action_id: UUID) -> ActionRecord | None:
        with self._lock:
            return self.records.get(action_id)

    def recover_incomplete(self) -> list[ActionRecord]:
        with self._lock:
            recovered: list[ActionRecord] = []
            for record in list(self.records.values()):
                if record.status == ActionStatus.EXECUTING:
                    recovered.append(
                        self.update(
                            record.action_id,
                            ActionStatus.UNKNOWN_RESULT,
                            detail="process restart occurred after external execution began",
                        )
                    )
                elif record.status == ActionStatus.PLANNED:
                    recovered.append(
                        self.update(
                            record.action_id,
                            ActionStatus.RECOVERY_REQUIRED,
                            detail="planned action was not resumed after process restart",
                        )
                    )
            return recovered

    def record_effects(self, action_id: UUID, result: dict[str, Any]) -> None:
        with self._lock:
            for index, raw_effect in enumerate(result.get("effects", [])):
                self.effects.append(
                    {"action_id": action_id, "effect_index": index, **dict(raw_effect)}
                )


class PostgresActionStore:
    def __init__(self, database_url: str, connect_timeout: int = 5) -> None:
        self.database_url = database_url
        self.connect_timeout = connect_timeout

    def _connect(self) -> psycopg.Connection[Any]:
        return psycopg.connect(
            self.database_url, connect_timeout=self.connect_timeout, row_factory=dict_row
        )

    @staticmethod
    def _record(row: Mapping[str, Any]) -> ActionRecord:
        return ActionRecord(
            UUID(str(row["action_id"])),
            str(row["idempotency_key"]),
            str(row["request_digest"]),
            UUID(str(row["household_id"])),
            str(row["tool_id"]),
            ActionStatus(str(row["status"])),
            row["created_at"],
            row["updated_at"],
            str(row["detail"]) if row["detail"] else None,
            dict(row["result"]) if isinstance(row["result"], dict) else None,
            dict(row["latest_truth"]) if isinstance(row["latest_truth"], dict) else {},
        )

    def claim(self, request: ActionRequest) -> ActionClaim:
        with self._connect() as connection, connection.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO anima_actions (
                    action_id, idempotency_key, request_digest, household_id, tool_id,
                    arguments, resource_ids, preconditions, status, created_at, updated_at
                ) VALUES (%s,%s,%s,%s,%s,%s::jsonb,%s::jsonb,%s::jsonb,'PLANNED',%s,%s)
                ON CONFLICT (idempotency_key) DO NOTHING
                """,
                (
                    request.action_id,
                    request.idempotency_key,
                    request.request_digest,
                    request.household_id,
                    request.tool.tool_id,
                    json.dumps(request.arguments, sort_keys=True, default=str),
                    json.dumps([str(item) for item in request.resource_ids]),
                    json.dumps([item.to_payload() for item in request.preconditions], default=str),
                    request.created_at,
                    request.created_at,
                ),
            )
            inserted = cursor.rowcount == 1
            cursor.execute(
                "SELECT * FROM anima_actions WHERE idempotency_key=%s", (request.idempotency_key,)
            )
            row = cursor.fetchone()
            connection.commit()
        if row is None:
            raise RuntimeError("action claim disappeared")
        existing = self._record(row)
        return ActionClaim(
            existing,
            duplicate=not inserted and existing.request_digest == request.request_digest,
            idempotency_conflict=existing.request_digest != request.request_digest,
        )

    def update(
        self,
        action_id: UUID,
        status: ActionStatus,
        *,
        detail: str | None = None,
        result: dict[str, Any] | None = None,
        latest_truth: dict[str, Any] | None = None,
    ) -> ActionRecord:
        with self._connect() as connection, connection.cursor() as cursor:
            cursor.execute(
                """
                UPDATE anima_actions SET status=%s, detail=%s, result=%s::jsonb,
                    latest_truth=COALESCE(%s::jsonb, latest_truth), updated_at=now()
                WHERE action_id=%s RETURNING *
                """,
                (
                    status.value,
                    detail,
                    json.dumps(result, sort_keys=True, default=str),
                    json.dumps(latest_truth, sort_keys=True, default=str)
                    if latest_truth is not None
                    else None,
                    action_id,
                ),
            )
            row = cursor.fetchone()
            connection.commit()
        if row is None:
            raise KeyError(action_id)
        return self._record(row)

    def get(self, action_id: UUID) -> ActionRecord | None:
        with self._connect() as connection, connection.cursor() as cursor:
            cursor.execute("SELECT * FROM anima_actions WHERE action_id=%s", (action_id,))
            row = cursor.fetchone()
        return self._record(row) if row else None

    def recover_incomplete(self) -> list[ActionRecord]:
        with self._connect() as connection, connection.cursor() as cursor:
            cursor.execute(
                """
                UPDATE anima_actions
                SET status=CASE WHEN status='EXECUTING' THEN 'UNKNOWN_RESULT'
                                ELSE 'RECOVERY_REQUIRED' END,
                    detail=CASE WHEN status='EXECUTING'
                                THEN 'process restart occurred after external execution began'
                                ELSE 'planned action was not resumed after process restart' END,
                    updated_at=now()
                WHERE status IN ('PLANNED','EXECUTING')
                RETURNING *
                """
            )
            rows = list(cursor.fetchall())
            connection.commit()
        return [self._record(row) for row in rows]

    def record_effects(self, action_id: UUID, result: dict[str, Any]) -> None:
        with self._connect() as connection, connection.cursor() as cursor:
            for index, raw_effect in enumerate(result.get("effects", [])):
                effect = dict(raw_effect)
                cursor.execute(
                    """
                    INSERT INTO anima_action_effects
                        (effect_id, action_id, effect_index, outcome, observed, detail)
                    VALUES (%s,%s,%s,%s,%s::jsonb,%s)
                    ON CONFLICT (action_id, effect_index) DO UPDATE SET
                        outcome=EXCLUDED.outcome, observed=EXCLUDED.observed, detail=EXCLUDED.detail
                    """,
                    (
                        uuid4(),
                        action_id,
                        index,
                        str(effect.get("outcome", "UNKNOWN")),
                        json.dumps(effect.get("observed"), sort_keys=True, default=str),
                        str(effect.get("detail")) if effect.get("detail") is not None else None,
                    ),
                )
            connection.commit()


class ResourceLock(AbstractContextManager[bool]):
    def __init__(
        self, connection: psycopg.Connection[Any] | None, keys: list[tuple[int, int]]
    ) -> None:
        self.connection = connection
        self.keys = keys
        self.acquired = False

    def __enter__(self) -> bool:
        if self.connection is None:
            return False
        with self.connection.cursor() as cursor:
            for key in self.keys:
                cursor.execute("SELECT pg_try_advisory_lock(%s,%s)", key)
                row = cursor.fetchone()
                if row is None or not bool(row[0]):
                    for held_key in reversed(self.keys[: self.keys.index(key)]):
                        cursor.execute("SELECT pg_advisory_unlock(%s,%s)", held_key)
                    self.connection.close()
                    self.connection = None
                    return False
        self.acquired = True
        return True

    def __exit__(self, exc_type: Any, exc: Any, traceback: Any) -> None:
        if self.connection is not None and self.acquired:
            with self.connection.cursor() as cursor:
                for key in reversed(self.keys):
                    cursor.execute("SELECT pg_advisory_unlock(%s,%s)", key)
        if self.connection is not None:
            self.connection.close()
        self.connection = None
        self.acquired = False


def _lock_key(resource_id: UUID) -> tuple[int, int]:
    digest = hashlib.sha256(f"anima.action.resource:{resource_id}".encode()).digest()
    return unpack(">ii", digest[:8])


class PostgresResourceLocker:
    """Non-blocking session locks; the session remains open only for the call."""

    def __init__(self, database_url: str, connect_timeout: int = 5) -> None:
        self.database_url = database_url
        self.connect_timeout = connect_timeout

    def try_acquire(self, resources: tuple[UUID, ...]) -> ResourceLock:
        connection = psycopg.connect(self.database_url, connect_timeout=self.connect_timeout)
        connection.autocommit = True
        return ResourceLock(connection, [_lock_key(item) for item in sorted(set(resources))])


class InMemoryResourceLock(AbstractContextManager[bool]):
    def __init__(self, locks: dict[UUID, threading.Lock], resources: tuple[UUID, ...]) -> None:
        self.locks = locks
        self.resources = tuple(sorted(set(resources)))
        self.held: list[threading.Lock] = []

    def __enter__(self) -> bool:
        for resource in self.resources:
            lock = self.locks.setdefault(resource, threading.Lock())
            if not lock.acquire(blocking=False):
                for held in reversed(self.held):
                    held.release()
                self.held = []
                return False
            self.held.append(lock)
        return True

    def __exit__(self, exc_type: Any, exc: Any, traceback: Any) -> None:
        for lock in reversed(self.held):
            lock.release()
        self.held = []


class InMemoryResourceLocker:
    def __init__(self) -> None:
        self._locks: dict[UUID, threading.Lock] = {}
        self._guard = threading.Lock()

    def try_acquire(self, resources: tuple[UUID, ...]) -> InMemoryResourceLock:
        with self._guard:
            return InMemoryResourceLock(self._locks, resources)


class ActionGateway(Protocol):
    def invoke(
        self,
        tool_id: str,
        arguments: dict[str, Any],
        *,
        household_id: UUID,
        identity: IdentityContext,
        origin: RequestOrigin,
        resource_id: UUID | None = None,
        capability_id: UUID | None = None,
        policy_service: PolicyService,
        policy_context: PolicyContext,
        confirmation: ConfirmationChallenge | None = None,
    ) -> InvocationResult: ...


class ActionExecutionCoordinator:
    def __init__(
        self,
        gateway: ActionGateway,
        store: ActionStore,
        locker: PostgresResourceLocker | InMemoryResourceLocker,
        *,
        journal: Any | None = None,
    ) -> None:
        self.gateway = gateway
        self.store = store
        self.locker = locker
        self.journal = journal

    def _audit(self, request: ActionRequest, event_type: str, payload: dict[str, Any]) -> None:
        if self.journal is None:
            return
        self.journal.append(
            EventEnvelope.create(
                event_id=str(uuid4()),
                event_type=event_type,
                source="anima:action-execution",
                subject_key=f"action/{request.action_id}",
                occurred_at=_now(),
                payload=payload,
                correlation_id=str(request.action_id),
                metadata={"household_id": str(request.household_id)},
            )
        )

    @staticmethod
    def _context(request: ActionRequest, snapshot: TruthSnapshot) -> PolicyContext:
        values = tuple(
            TruthPolicyContext(
                truth_key=key,
                status=str(value.get("state", "UNKNOWN")),
                value=value.get("value"),
                source_event_ids=tuple(str(item) for item in value.get("source_event_ids", ())),
            )
            for key, value in sorted(snapshot.values.items())
        )
        return PolicyContext(
            principal_role=request.policy_context.principal_role,
            graph_metadata=dict(request.policy_context.graph_metadata),
            truth=values,
        )

    @staticmethod
    def _intent(request: ActionRequest, context: PolicyContext) -> ActionIntent:
        resource_id = request.resource_ids[0] if request.resource_ids else None
        capability_id = None
        if request.arguments.get("capability_id") is not None:
            capability_id = UUID(str(request.arguments["capability_id"]))
        return ActionIntent.create(
            household_id=request.household_id,
            semantic_action=request.tool.semantic_action,
            resource_id=resource_id,
            capability_id=capability_id,
            principal_id=request.identity.principal_id,
            origin=request.origin,
            truth=context.truth,
            graph_metadata={
                **context.graph_metadata,
                "plugin_id": request.tool.plugin_id,
                "security_sensitive": request.tool.risk_class.startswith("SECURITY"),
                "read_only": request.tool.read_only,
                "writable": not request.tool.read_only,
                "external_side_effect": request.tool.risk_class == "EXTERNAL_SIDE_EFFECT",
                "financial": request.tool.risk_class == "FINANCIAL_PURCHASE",
            },
        )

    def _terminal(
        self,
        request: ActionRequest,
        status: ActionStatus,
        *,
        detail: str,
        snapshot: TruthSnapshot | None = None,
        invocation: InvocationResult | None = None,
        result: dict[str, Any] | None = None,
    ) -> ActionExecutionResult:
        record = self.store.update(
            request.action_id,
            status,
            detail=detail,
            result=result,
            latest_truth=snapshot.to_payload() if snapshot else None,
        )
        if result is not None and isinstance(result.get("effects"), list):
            self.store.record_effects(request.action_id, result)
        self._audit(request, "action.completed", {"status": status.value, "detail": detail})
        return ActionExecutionResult(record, invocation)

    def _refresh(self, request: ActionRequest) -> TruthSnapshot:
        if request.refresher is None:
            return TruthSnapshot()
        return request.refresher(request.resource_ids)

    def _verify(
        self,
        request: ActionRequest,
        invocation: InvocationResult,
        snapshot: TruthSnapshot,
    ) -> VerificationResult:
        if request.verifier is not None:
            return request.verifier(request, invocation, snapshot)
        if isinstance(invocation.result, dict):
            outcome = invocation.result.get("outcome")
            if outcome == "SUCCESS" and invocation.result.get("observed_state") is not None:
                return VerificationResult(VerificationOutcome.VERIFIED, dict(invocation.result))
        return VerificationResult(
            VerificationOutcome.UNKNOWN,
            detail="consequential action has no observed post-action verification",
        )

    @staticmethod
    def _effects(result: Any) -> tuple[ActionStatus, str] | None:
        if not isinstance(result, dict) or not isinstance(result.get("effects"), list):
            return None
        outcomes = [str(item.get("outcome", "UNKNOWN")).upper() for item in result["effects"]]
        if not outcomes:
            return ActionStatus.FAILED, "empty effect set"
        known = {"SUCCESS", "SUCCEEDED", "VERIFIED"}
        failed = {"FAILED", "FAILURE", "ERROR"}
        unknown = {"UNKNOWN", "TIMEOUT", "TIMED_OUT", "AMBIGUOUS"}
        if any(item in unknown for item in outcomes) and any(
            item in known | failed for item in outcomes
        ):
            return (
                ActionStatus.PARTIAL,
                "multi-effect execution produced mixed known and unknown results",
            )
        if any(item in failed for item in outcomes) and any(item in known for item in outcomes):
            return (
                ActionStatus.PARTIAL,
                "multi-effect execution produced mixed success and failure",
            )
        if any(item in unknown for item in outcomes):
            return (
                ActionStatus.UNKNOWN_RESULT,
                "multi-effect execution contains an ambiguous effect",
            )
        if all(item in known for item in outcomes):
            return ActionStatus.SUCCEEDED, "all effects verified by connector result"
        return ActionStatus.FAILED, "connector returned an unrecognized effect outcome"

    def execute(self, request: ActionRequest) -> ActionExecutionResult:
        claim = self.store.claim(request)
        if claim.idempotency_conflict:
            return ActionExecutionResult(
                claim.record,
                duplicate=True,
                idempotency_conflict=True,
            )
        if claim.duplicate:
            return ActionExecutionResult(claim.record, duplicate=True)

        self._audit(request, "action.started", {"tool_id": request.tool.tool_id})
        with self.locker.try_acquire(request.resource_ids) as acquired:
            if not acquired:
                return self._terminal(
                    request,
                    ActionStatus.RESOURCE_BUSY,
                    detail="canonical resource is already being acted on; request was not queued",
                )
            try:
                snapshot = self._refresh(request)
            except Exception as exc:
                return self._terminal(
                    request,
                    ActionStatus.UNKNOWN_RESULT,
                    detail=f"latest-state refresh failed: {type(exc).__name__}",
                )
            if not request.tool.read_only and request.refresher is None:
                return self._terminal(
                    request,
                    ActionStatus.UNKNOWN_RESULT,
                    detail="consequential action requires a provider-backed latest-state refresher",
                    snapshot=snapshot,
                )
            if not request.tool.read_only and request.tool.idempotency == Idempotency.NONE:
                return self._terminal(
                    request,
                    ActionStatus.FAILED,
                    detail="consequential connector does not declare idempotent execution",
                    snapshot=snapshot,
                )
            failed = [
                item.truth_key for item in request.preconditions if not item.matches(snapshot)
            ]
            if failed:
                return self._terminal(
                    request,
                    ActionStatus.PRECONDITION_FAILED,
                    detail=f"latest state no longer satisfies preconditions: {','.join(failed)}",
                    snapshot=snapshot,
                )
            context = self._context(request, snapshot)
            intent = self._intent(request, context)
            if intent.risk_class.value != request.tool.risk_class:
                return self._terminal(
                    request,
                    ActionStatus.POLICY_DENIED,
                    detail="tool risk metadata does not match the semantic action risk",
                    snapshot=snapshot,
                )
            decision = request.policy_service.evaluate(
                intent, request.identity, context, request.confirmation
            )
            decision_map = {
                Decision.DENY: ActionStatus.POLICY_DENIED,
                Decision.REQUIRE_CONFIRMATION: ActionStatus.REQUIRE_CONFIRMATION,
                Decision.REQUIRE_STRONGER_AUTH: ActionStatus.REQUIRE_STRONGER_AUTH,
            }
            if decision.decision in decision_map:
                return self._terminal(
                    request,
                    decision_map[decision.decision],
                    detail=decision.reason_code,
                    snapshot=snapshot,
                )
            self.store.update(
                request.action_id,
                ActionStatus.EXECUTING,
                detail="final policy authorized execution",
                latest_truth=snapshot.to_payload(),
            )
            self._audit(
                request,
                "action.executing",
                {"policy_decision_id": str(decision.decision_id)},
            )
            try:
                invocation = self.gateway.invoke(
                    request.tool.tool_id,
                    request.arguments,
                    household_id=request.household_id,
                    identity=request.identity,
                    origin=request.origin,
                    resource_id=request.resource_ids[0] if request.resource_ids else None,
                    capability_id=(
                        UUID(str(request.arguments["capability_id"]))
                        if request.arguments.get("capability_id") is not None
                        else None
                    ),
                    policy_service=request.policy_service,
                    policy_context=context,
                    confirmation=request.confirmation,
                )
            except Exception as exc:
                return self._terminal(
                    request,
                    ActionStatus.UNKNOWN_RESULT,
                    detail=f"connector failed after execution began: {type(exc).__name__}",
                    snapshot=snapshot,
                )
            effect_status = self._effects(invocation.result)
            if effect_status is not None:
                status, detail = effect_status
                return self._terminal(
                    request,
                    status,
                    detail=detail,
                    snapshot=snapshot,
                    invocation=invocation,
                    result=invocation.result if isinstance(invocation.result, dict) else None,
                )
            if invocation.outcome in {
                InvocationOutcome.REQUIRE_CONFIRMATION,
                InvocationOutcome.REQUIRE_STRONGER_AUTH,
                InvocationOutcome.POLICY_DENIED,
            }:
                status = {
                    InvocationOutcome.REQUIRE_CONFIRMATION: ActionStatus.REQUIRE_CONFIRMATION,
                    InvocationOutcome.REQUIRE_STRONGER_AUTH: ActionStatus.REQUIRE_STRONGER_AUTH,
                    InvocationOutcome.POLICY_DENIED: ActionStatus.POLICY_DENIED,
                }[invocation.outcome]
                return self._terminal(
                    request,
                    status,
                    detail=invocation.error_class or status.value,
                    snapshot=snapshot,
                    invocation=invocation,
                )
            if invocation.outcome == InvocationOutcome.VERIFICATION_FAILED:
                return self._terminal(
                    request,
                    ActionStatus.VERIFICATION_FAILED,
                    detail="provider verification failed",
                    snapshot=snapshot,
                    invocation=invocation,
                )
            if (
                invocation.outcome
                in {
                    InvocationOutcome.UNKNOWN_RESULT,
                    InvocationOutcome.PLUGIN_TIMEOUT,
                    InvocationOutcome.PLUGIN_ERROR,
                }
                and not request.tool.read_only
            ):
                return self._terminal(
                    request,
                    ActionStatus.UNKNOWN_RESULT,
                    detail=invocation.error_class or "ambiguous connector result",
                    snapshot=snapshot,
                    invocation=invocation,
                )
            if invocation.outcome != InvocationOutcome.SUCCESS:
                return self._terminal(
                    request,
                    ActionStatus.FAILED,
                    detail=invocation.error_class or invocation.outcome.value,
                    snapshot=snapshot,
                    invocation=invocation,
                )
            if not request.tool.read_only or request.tool.verification_requirement != "NONE":
                verification_snapshot = snapshot
                if not request.tool.read_only:
                    try:
                        verification_snapshot = self._refresh(request)
                    except Exception as exc:
                        return self._terminal(
                            request,
                            ActionStatus.UNKNOWN_RESULT,
                            detail=f"post-action state refresh failed: {type(exc).__name__}",
                            snapshot=snapshot,
                            invocation=invocation,
                        )
                verification = self._verify(request, invocation, verification_snapshot)
                if verification.outcome == VerificationOutcome.FAILED:
                    return self._terminal(
                        request,
                        ActionStatus.VERIFICATION_FAILED,
                        detail=verification.detail or "observed state did not match",
                        snapshot=verification_snapshot,
                        invocation=invocation,
                        result=verification.observed,
                    )
                if verification.outcome == VerificationOutcome.UNKNOWN:
                    return self._terminal(
                        request,
                        ActionStatus.UNKNOWN_RESULT,
                        detail=verification.detail or "verification was inconclusive",
                        snapshot=verification_snapshot,
                        invocation=invocation,
                        result=verification.observed,
                    )
            return self._terminal(
                request,
                ActionStatus.SUCCEEDED,
                detail="action executed and verified",
                snapshot=verification_snapshot if not request.tool.read_only else snapshot,
                invocation=invocation,
                result=invocation.result if isinstance(invocation.result, dict) else None,
            )


ActionCoordinator = ActionExecutionCoordinator
