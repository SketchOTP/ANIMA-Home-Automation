"""ANIMA-owned intelligence-provider and SENTRY handoff contracts.

SENTRY supplies reasoning and interaction. This module deliberately keeps the
provider boundary narrower than the household Core: durable records contain
identifiers, digests, lifecycle state, and bounded result metadata, while the
actual sparse ContextPacket is retrieved through an authenticated Core call.
No provider result can grant authority or manufacture an action outcome.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any, Protocol
from uuid import UUID, uuid4, uuid5

import psycopg
from psycopg.rows import dict_row

from anima_ha.events import DeliveryClass, EventEnvelope, EventImportance
from anima_ha.plugins import ToolDescriptor

INTELLIGENCE_NAMESPACE = UUID("0bd7a7d8-7300-4f96-a770-5e6f4ed7ef1a")
INTELLIGENCE_SCHEMA_VERSION = 1
MAX_RESPONSE_BYTES = 16_384
MAX_METADATA_BYTES = 8_192


class IntelligenceProviderMode(StrEnum):
    SENTRY = "sentry"
    EMBEDDED_REFERENCE = "embedded_reference"
    UNAVAILABLE = "unavailable"


class IntelligenceOrigin(StrEnum):
    DIRECT_UI_USER = "DIRECT_UI_USER"
    AUTONOMOUS_ATTENTION = "AUTONOMOUS_ATTENTION"
    DURABLE_TASK = "DURABLE_TASK"
    APPROVAL_RESOLUTION = "APPROVAL_RESOLUTION"
    TESTING = "TESTING"


class IntelligenceLifecycle(StrEnum):
    PENDING = "PENDING"
    CLAIMED = "CLAIMED"
    DELIVERED_TO_PROVIDER = "DELIVERED_TO_PROVIDER"
    PROVIDER_RUNNING = "PROVIDER_RUNNING"
    WAITING_CONFIRMATION = "WAITING_CONFIRMATION"
    WAITING_STRONGER_AUTH = "WAITING_STRONGER_AUTH"
    RESULT_RECEIVED = "RESULT_RECEIVED"
    COMPLETED = "COMPLETED"
    NO_ACTION = "NO_ACTION"
    FAILED = "FAILED"
    UNKNOWN_RESULT = "UNKNOWN_RESULT"
    RECOVERY_REQUIRED = "RECOVERY_REQUIRED"
    CANCELLED = "CANCELLED"


class IntelligenceResultStatus(StrEnum):
    RESPONSE = "RESPONSE"
    NO_ACTION = "NO_ACTION"
    TOOL_ACTIVITY_COMPLETED = "TOOL_ACTIVITY_COMPLETED"
    WAITING_CONFIRMATION = "WAITING_CONFIRMATION"
    WAITING_STRONGER_AUTH = "WAITING_STRONGER_AUTH"
    PARTIAL = "PARTIAL"
    FAILED = "FAILED"
    UNAVAILABLE = "UNAVAILABLE"
    UNKNOWN_RESULT = "UNKNOWN_RESULT"


_RESULT_LIFECYCLE: dict[IntelligenceResultStatus, IntelligenceLifecycle] = {
    IntelligenceResultStatus.RESPONSE: IntelligenceLifecycle.COMPLETED,
    IntelligenceResultStatus.NO_ACTION: IntelligenceLifecycle.NO_ACTION,
    IntelligenceResultStatus.TOOL_ACTIVITY_COMPLETED: IntelligenceLifecycle.COMPLETED,
    IntelligenceResultStatus.WAITING_CONFIRMATION: IntelligenceLifecycle.WAITING_CONFIRMATION,
    IntelligenceResultStatus.WAITING_STRONGER_AUTH: IntelligenceLifecycle.WAITING_STRONGER_AUTH,
    IntelligenceResultStatus.PARTIAL: IntelligenceLifecycle.FAILED,
    IntelligenceResultStatus.FAILED: IntelligenceLifecycle.FAILED,
    IntelligenceResultStatus.UNAVAILABLE: IntelligenceLifecycle.RECOVERY_REQUIRED,
    IntelligenceResultStatus.UNKNOWN_RESULT: IntelligenceLifecycle.UNKNOWN_RESULT,
}


@dataclass(frozen=True, slots=True)
class IntelligenceRequest:
    request_id: UUID
    household_id: UUID
    origin: IntelligenceOrigin
    context_packet_id: UUID
    context_digest: str
    catalogue_digest: str
    provider_id: str
    provider_version: str
    idempotency_key: str
    trigger_id: UUID | None = None
    principal_id: UUID | None = None
    correlation_id: str | None = None
    causation_id: str | None = None
    lifecycle: IntelligenceLifecycle = IntelligenceLifecycle.PENDING
    claim_owner: str | None = None
    fencing_generation: int = 0
    lease_expires_at: datetime | None = None
    attempt_count: int = 0
    request_metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.provider_id.strip() or not self.provider_version.strip():
            raise ValueError("provider identity is required")
        if not self.idempotency_key.strip() or not self.context_digest.strip():
            raise ValueError("request identity and context digest are required")
        if self.fencing_generation < 0 or self.attempt_count < 0:
            raise ValueError("request counters cannot be negative")
        raw = json.dumps(self.request_metadata, sort_keys=True, separators=(",", ":"))
        if len(raw.encode()) > MAX_METADATA_BYTES:
            raise ValueError("request metadata exceeds bounded size")


@dataclass(frozen=True, slots=True)
class IntelligenceResult:
    request_id: UUID
    status: IntelligenceResultStatus
    response_text: str | None = None
    action_references: tuple[str, ...] = ()
    detail: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
    provider_ambiguous: bool = False

    def __post_init__(self) -> None:
        if self.response_text is not None and len(self.response_text.encode()) > MAX_RESPONSE_BYTES:
            raise ValueError("intelligence response exceeds bounded size")
        raw = json.dumps(self.metadata, sort_keys=True, separators=(",", ":"))
        if len(raw.encode()) > MAX_METADATA_BYTES:
            raise ValueError("result metadata exceeds bounded size")

    @property
    def response_digest(self) -> str | None:
        if self.response_text is None:
            return None
        return hashlib.sha256(self.response_text.encode()).hexdigest()

    def to_live_payload(self) -> dict[str, Any]:
        return {
            "request_id": str(self.request_id),
            "status": self.status.value,
            "response": self.response_text,
            "action_references": list(self.action_references),
            "detail": self.detail,
            "metadata": self.metadata,
            "provider_ambiguous": self.provider_ambiguous,
        }


@dataclass(frozen=True, slots=True)
class ProviderHealth:
    provider_id: str
    provider_version: str
    state: str
    detail: str | None = None
    last_success_at: datetime | None = None

    def to_payload(self) -> dict[str, Any]:
        return {
            "provider_id": self.provider_id,
            "provider_version": self.provider_version,
            "state": self.state,
            "detail": self.detail,
            "last_success_at": self.last_success_at.isoformat() if self.last_success_at else None,
        }


class IntelligenceStore(Protocol):
    def enqueue(self, request: IntelligenceRequest) -> IntelligenceRequest: ...

    def claim(self, worker_id: str, *, lease_seconds: int = 120) -> IntelligenceRequest | None: ...

    def renew(
        self, request_id: UUID, worker_id: str, generation: int, *, lease_seconds: int = 120
    ) -> bool: ...

    def transition(
        self,
        request_id: UUID,
        worker_id: str,
        generation: int,
        lifecycle: IntelligenceLifecycle,
        metadata: dict[str, Any] | None = None,
    ) -> bool: ...

    def record_result(
        self, request_id: UUID, worker_id: str, generation: int, result: IntelligenceResult
    ) -> bool: ...

    def get(self, request_id: UUID) -> IntelligenceRequest | None: ...


def _digest(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":"), default=str).encode()
    ).hexdigest()


def _request_from_row(row: dict[str, Any]) -> IntelligenceRequest:
    metadata = row.get("request_metadata") or {}
    if isinstance(metadata, str):
        metadata = json.loads(metadata)
    return IntelligenceRequest(
        request_id=UUID(str(row["request_id"])),
        household_id=UUID(str(row["household_id"])),
        origin=IntelligenceOrigin(str(row["origin"])),
        context_packet_id=UUID(str(row["context_packet_id"])),
        context_digest=str(row["context_digest"]),
        catalogue_digest=str(row["catalogue_digest"]),
        provider_id=str(row["provider_id"]),
        provider_version=str(row["provider_version"]),
        idempotency_key=str(row["idempotency_key"]),
        trigger_id=UUID(str(row["trigger_id"])) if row.get("trigger_id") else None,
        principal_id=UUID(str(row["principal_id"])) if row.get("principal_id") else None,
        correlation_id=str(row["correlation_id"]) if row.get("correlation_id") else None,
        causation_id=str(row["causation_id"]) if row.get("causation_id") else None,
        lifecycle=IntelligenceLifecycle(str(row["lifecycle"])),
        claim_owner=str(row["claim_owner"]) if row.get("claim_owner") else None,
        fencing_generation=int(row["fencing_generation"]),
        lease_expires_at=row.get("lease_expires_at"),
        attempt_count=int(row["attempt_count"]),
        request_metadata=dict(metadata),
    )


class PostgresIntelligenceStore:
    """PostgreSQL request queue with lease and fencing enforcement."""

    def __init__(self, database_url: str, connect_timeout: int = 5) -> None:
        self.database_url = database_url
        self.connect_timeout = connect_timeout

    def _connect(self) -> psycopg.Connection[Any]:
        return psycopg.connect(
            self.database_url, connect_timeout=self.connect_timeout, row_factory=dict_row
        )

    def enqueue(self, request: IntelligenceRequest) -> IntelligenceRequest:
        with self._connect() as connection, connection.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO anima_intelligence_requests (
                    request_id, trigger_id, household_id, principal_id, origin,
                    correlation_id, causation_id, context_packet_id, context_digest,
                    catalogue_digest, provider_id, provider_version, idempotency_key,
                    request_metadata
                ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s::jsonb)
                ON CONFLICT (idempotency_key) DO NOTHING
                """,
                (
                    request.request_id,
                    request.trigger_id,
                    request.household_id,
                    request.principal_id,
                    request.origin.value,
                    request.correlation_id,
                    request.causation_id,
                    request.context_packet_id,
                    request.context_digest,
                    request.catalogue_digest,
                    request.provider_id,
                    request.provider_version,
                    request.idempotency_key,
                    json.dumps(request.request_metadata, sort_keys=True),
                ),
            )
            cursor.execute(
                "SELECT * FROM anima_intelligence_requests WHERE idempotency_key=%s",
                (request.idempotency_key,),
            )
            row = cursor.fetchone()
            if row is None:
                raise RuntimeError("intelligence request disappeared after enqueue")
            connection.commit()
        return _request_from_row(row)

    def claim(self, worker_id: str, *, lease_seconds: int = 120) -> IntelligenceRequest | None:
        if not worker_id.strip() or lease_seconds < 1 or lease_seconds > 900:
            raise ValueError("invalid intelligence claim parameters")
        with self._connect() as connection, connection.cursor() as cursor:
            cursor.execute(
                """
                WITH candidate AS (
                    SELECT request_id, lifecycle AS previous_lifecycle
                    FROM anima_intelligence_requests
                    WHERE (lifecycle = 'PENDING'
                           OR (lifecycle IN ('CLAIMED','DELIVERED_TO_PROVIDER','PROVIDER_RUNNING')
                               AND lease_expires_at <= now()))
                    ORDER BY created_at, request_id
                    FOR UPDATE SKIP LOCKED
                    LIMIT 1
                )
                UPDATE anima_intelligence_requests AS request
                SET lifecycle='CLAIMED', claim_owner=%s,
                    fencing_generation=request.fencing_generation + 1,
                    lease_expires_at=now() + (%s * interval '1 second'),
                    attempt_count=request.attempt_count + 1, updated_at=now()
                FROM candidate
                WHERE request.request_id=candidate.request_id
                RETURNING request.*, candidate.previous_lifecycle
                """,
                (worker_id, lease_seconds),
            )
            row = cursor.fetchone()
            if row is None:
                connection.commit()
                return None
            cursor.execute(
                """
                INSERT INTO anima_intelligence_transitions
                    (request_id, from_lifecycle, to_lifecycle, fencing_generation, actor)
                VALUES (%s, %s, 'CLAIMED', %s, %s)
                """,
                (
                    row["request_id"],
                    row["previous_lifecycle"],
                    row["fencing_generation"],
                    worker_id,
                ),
            )
            connection.commit()
        return _request_from_row(row)

    def renew(
        self, request_id: UUID, worker_id: str, generation: int, *, lease_seconds: int = 120
    ) -> bool:
        if not worker_id.strip() or generation < 1 or lease_seconds < 1 or lease_seconds > 900:
            raise ValueError("invalid intelligence renewal parameters")
        with self._connect() as connection, connection.cursor() as cursor:
            cursor.execute(
                """
                UPDATE anima_intelligence_requests
                SET lease_expires_at=now() + (%s * interval '1 second'), updated_at=now()
                WHERE request_id=%s AND claim_owner=%s AND fencing_generation=%s
                  AND lifecycle IN ('CLAIMED','DELIVERED_TO_PROVIDER','PROVIDER_RUNNING')
                  AND lease_expires_at > now()
                """,
                (lease_seconds, request_id, worker_id, generation),
            )
            changed = cursor.rowcount == 1
            connection.commit()
        return changed

    def transition(
        self,
        request_id: UUID,
        worker_id: str,
        generation: int,
        lifecycle: IntelligenceLifecycle,
        metadata: dict[str, Any] | None = None,
    ) -> bool:
        metadata = metadata or {}
        with self._connect() as connection, connection.cursor() as cursor:
            cursor.execute(
                "SELECT lifecycle FROM anima_intelligence_requests WHERE request_id=%s FOR UPDATE",
                (request_id,),
            )
            current = cursor.fetchone()
            if current is None:
                return False
            current_lifecycle = IntelligenceLifecycle(str(current["lifecycle"]))
            allowed: dict[IntelligenceLifecycle, set[IntelligenceLifecycle]] = {
                IntelligenceLifecycle.CLAIMED: {
                    IntelligenceLifecycle.DELIVERED_TO_PROVIDER,
                    IntelligenceLifecycle.PROVIDER_RUNNING,
                    IntelligenceLifecycle.CANCELLED,
                },
                IntelligenceLifecycle.DELIVERED_TO_PROVIDER: {
                    IntelligenceLifecycle.PROVIDER_RUNNING,
                    IntelligenceLifecycle.CANCELLED,
                },
                IntelligenceLifecycle.PROVIDER_RUNNING: {
                    IntelligenceLifecycle.RESULT_RECEIVED,
                    IntelligenceLifecycle.WAITING_CONFIRMATION,
                    IntelligenceLifecycle.WAITING_STRONGER_AUTH,
                    IntelligenceLifecycle.COMPLETED,
                    IntelligenceLifecycle.NO_ACTION,
                    IntelligenceLifecycle.FAILED,
                    IntelligenceLifecycle.UNKNOWN_RESULT,
                    IntelligenceLifecycle.RECOVERY_REQUIRED,
                },
            }
            if lifecycle != IntelligenceLifecycle.CANCELLED and lifecycle not in allowed.get(
                current_lifecycle, set()
            ):
                connection.rollback()
                return False
            cursor.execute(
                """
                UPDATE anima_intelligence_requests
                SET lifecycle=%s, updated_at=now(),
                    completed_at=CASE WHEN %s IN (
                        'COMPLETED','NO_ACTION','FAILED','UNKNOWN_RESULT',
                        'RECOVERY_REQUIRED','CANCELLED'
                    ) THEN now() ELSE completed_at END
                WHERE request_id=%s AND claim_owner=%s AND fencing_generation=%s
                  AND lease_expires_at > now()
                """,
                (lifecycle.value, lifecycle.value, request_id, worker_id, generation),
            )
            if cursor.rowcount != 1:
                connection.rollback()
                return False
            cursor.execute(
                """
                INSERT INTO anima_intelligence_transitions
                    (request_id, from_lifecycle, to_lifecycle, fencing_generation, actor, metadata)
                VALUES (%s,%s,%s,%s,%s,%s::jsonb)
                """,
                (
                    request_id,
                    str(current["lifecycle"]),
                    lifecycle.value,
                    generation,
                    worker_id,
                    json.dumps(metadata, sort_keys=True),
                ),
            )
            connection.commit()
        return True

    def record_result(
        self, request_id: UUID, worker_id: str, generation: int, result: IntelligenceResult
    ) -> bool:
        metadata = dict(result.metadata)
        metadata.update(
            {
                "action_references": list(result.action_references),
                "detail": result.detail,
                "provider_ambiguous": result.provider_ambiguous,
            }
        )
        with self._connect() as connection, connection.cursor() as cursor:
            cursor.execute(
                "SELECT lifecycle FROM anima_intelligence_requests WHERE request_id=%s FOR UPDATE",
                (request_id,),
            )
            current = cursor.fetchone()
            if current is None or str(current["lifecycle"]) not in {
                "DELIVERED_TO_PROVIDER",
                "PROVIDER_RUNNING",
            }:
                connection.rollback()
                return False
            terminal_lifecycle = _RESULT_LIFECYCLE[result.status]
            cursor.execute(
                """
                UPDATE anima_intelligence_requests
                SET lifecycle=%s, result_status=%s, response_digest=%s,
                    result_metadata=%s::jsonb,
                    completed_at=CASE WHEN %s IN (
                        'COMPLETED','NO_ACTION','FAILED','UNKNOWN_RESULT',
                        'RECOVERY_REQUIRED','CANCELLED'
                    ) THEN now() ELSE NULL END,
                    updated_at=now()
                WHERE request_id=%s AND claim_owner=%s AND fencing_generation=%s
                  AND lease_expires_at > now()
                """,
                (
                    terminal_lifecycle,
                    result.status.value,
                    result.response_digest,
                    json.dumps(metadata, sort_keys=True),
                    terminal_lifecycle.value,
                    request_id,
                    worker_id,
                    generation,
                ),
            )
            if cursor.rowcount != 1:
                connection.rollback()
                return False
            cursor.execute(
                """
                INSERT INTO anima_intelligence_transitions
                    (request_id, from_lifecycle, to_lifecycle, fencing_generation, actor, metadata)
                VALUES (%s, %s, %s, %s, %s, %s::jsonb)
                """,
                (
                    request_id,
                    str(current["lifecycle"]),
                    terminal_lifecycle.value,
                    generation,
                    worker_id,
                    json.dumps(metadata, sort_keys=True),
                ),
            )
            connection.commit()
        return True

    def get(self, request_id: UUID) -> IntelligenceRequest | None:
        with self._connect() as connection, connection.cursor() as cursor:
            cursor.execute(
                "SELECT * FROM anima_intelligence_requests WHERE request_id=%s", (request_id,)
            )
            row = cursor.fetchone()
        return _request_from_row(row) if row else None


class IntelligenceRequestFactory:
    """Create stable, provider-bound request identities from ANIMA state."""

    @staticmethod
    def for_trigger(
        trigger_id: UUID,
        *,
        household_id: UUID,
        origin: IntelligenceOrigin,
        context_packet_id: UUID,
        context_digest: str,
        tools: list[ToolDescriptor],
        provider_id: str,
        provider_version: str,
        principal_id: UUID | None = None,
        correlation_id: str | None = None,
        causation_id: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> IntelligenceRequest:
        catalogue = [tool.to_payload() for tool in tools]
        catalogue_digest = _digest(catalogue)
        idempotency_key = f"intelligence:{provider_id}:{trigger_id}"
        request_id = uuid5(INTELLIGENCE_NAMESPACE, idempotency_key)
        return IntelligenceRequest(
            request_id=request_id,
            trigger_id=trigger_id,
            household_id=household_id,
            principal_id=principal_id,
            origin=origin,
            correlation_id=correlation_id,
            causation_id=causation_id,
            context_packet_id=context_packet_id,
            context_digest=context_digest,
            catalogue_digest=catalogue_digest,
            provider_id=provider_id,
            provider_version=provider_version,
            idempotency_key=idempotency_key,
            request_metadata=metadata or {},
        )


class SentryAttentionBridge:
    """Deliver Attention triggers to the durable SENTRY queue exactly once."""

    def __init__(
        self,
        *,
        attention: Any,
        context: Any,
        store: IntelligenceStore,
        profile: Any,
        provider_id: str = "sentry",
        provider_version: str = "1",
    ) -> None:
        self.attention = attention
        self.context = context
        self.store = store
        self.profile = profile
        self.provider_id = provider_id
        self.provider_version = provider_version

    def run_once(
        self,
        *,
        household_id: UUID,
        tools: list[ToolDescriptor],
        principal_id: UUID | None = None,
        consumer_name: str = "sentry-attention",
        limit: int = 100,
    ) -> list[IntelligenceRequest]:
        attention_result = self.attention.process(
            self.profile, consumer_name=consumer_name, limit=limit
        )
        if attention_result.failure:
            raise RuntimeError(f"attention processing failed: {attention_result.failure}")
        requests: list[IntelligenceRequest] = []
        for trigger in self.attention.list_triggers(self.profile.profile_version):
            if trigger.status.value not in {"PENDING", "CONTEXT_READY"}:
                continue
            packet = self.context.load(trigger.trigger_id)
            if packet is None:
                packet = self.context.assemble(
                    trigger, household_id=household_id, tools=tools, persist=True
                ).to_payload()
            request = IntelligenceRequestFactory.for_trigger(
                trigger.trigger_id,
                household_id=household_id,
                origin=IntelligenceOrigin.AUTONOMOUS_ATTENTION,
                context_packet_id=UUID(str(packet["context_packet_id"])),
                context_digest=str(packet.get("digest", _digest(packet))),
                tools=tools,
                provider_id=self.provider_id,
                provider_version=self.provider_version,
                principal_id=principal_id,
                correlation_id=trigger.correlation_id,
                causation_id=trigger.source_event_ids[0] if trigger.source_event_ids else None,
                metadata={"trigger_type": trigger.trigger_type, "priority": trigger.priority},
            )
            requests.append(self.store.enqueue(request))
        return requests


class IntelligenceHealthSink(Protocol):
    def append(self, event: EventEnvelope) -> Any: ...


def intelligence_health_event(
    provider: ProviderHealth, *, household_id: UUID | None = None
) -> EventEnvelope:
    now = datetime.now(UTC)
    return EventEnvelope.create(
        event_id=str(uuid4()),
        event_type="intelligence.provider.health",
        source="anima:intelligence",
        subject_key=f"intelligence/{provider.provider_id}",
        occurred_at=now,
        payload=provider.to_payload(),
        importance=EventImportance.IMPORTANT,
        delivery_class=DeliveryClass.GUARANTEED,
        metadata={"household_id": str(household_id)} if household_id else {},
    )
