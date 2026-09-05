"""ANIMA-owned SenseGuard alert policy and event matching.

This is intentionally a typed alert policy, not a raw Home Assistant
automation editor.  It decides whether a canonical SenseGuard event should
create guaranteed SENTRY attention; it never decides what SENTRY says or what
action SENTRY may take.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, time
from typing import Any
from uuid import NAMESPACE_URL, UUID, uuid4, uuid5
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

import psycopg
from psycopg.rows import dict_row

from anima_ha.events import DeliveryClass, EventEnvelope, EventImportance


class SenseGuardPolicyError(ValueError):
    """A policy is outside the bounded alert contract."""


def _zone(value: str) -> ZoneInfo:
    if not value.strip():
        raise SenseGuardPolicyError("household timezone is required")
    try:
        return ZoneInfo(value)
    except ZoneInfoNotFoundError as exc:
        raise SenseGuardPolicyError("unknown household timezone") from exc


def _clock(value: time | str) -> time:
    if isinstance(value, time):
        parsed = value
    else:
        try:
            parsed = time.fromisoformat(value)
        except ValueError as exc:
            raise SenseGuardPolicyError("alert time must be HH:MM[:SS]") from exc
    return parsed.replace(tzinfo=None, microsecond=0)


@dataclass(frozen=True, slots=True)
class SenseGuardAlertPolicy:
    policy_id: UUID
    household_id: UUID
    resource_ids: tuple[UUID, ...]
    event_type: str
    timezone: str
    start_local: time
    end_local: time
    priority: int = 90
    guaranteed_attention: bool = True
    delivery_mode: str = "SENTRY_COGNITION"
    enabled: bool = True
    creator_principal_id: UUID | None = None
    version: int = 1

    def __post_init__(self) -> None:
        if not self.resource_ids or len(self.resource_ids) > 32:
            raise SenseGuardPolicyError("one to 32 canonical resources are required")
        if not self.event_type.strip() or len(self.event_type) > 120:
            raise SenseGuardPolicyError("event_type is invalid")
        _zone(self.timezone)
        object.__setattr__(self, "start_local", _clock(self.start_local))
        object.__setattr__(self, "end_local", _clock(self.end_local))
        if not 0 <= self.priority <= 100:
            raise SenseGuardPolicyError("priority must be between 0 and 100")
        if self.delivery_mode not in {"SENTRY_COGNITION", "NOTIFICATION"}:
            raise SenseGuardPolicyError("unsupported SenseGuard delivery mode")
        if self.version < 1:
            raise SenseGuardPolicyError("policy version must be positive")

    def matches(self, *, resource_id: UUID, event_type: str, occurred_at: datetime) -> bool:
        if (
            not self.enabled
            or resource_id not in self.resource_ids
            or event_type != self.event_type
        ):
            return False
        local = occurred_at.astimezone(_zone(self.timezone)).time().replace(microsecond=0)
        if self.start_local <= self.end_local:
            return self.start_local <= local < self.end_local
        return local >= self.start_local or local < self.end_local

    def to_payload(self) -> dict[str, Any]:
        return {
            "policy_id": str(self.policy_id),
            "household_id": str(self.household_id),
            "resource_ids": [str(value) for value in self.resource_ids],
            "event_type": self.event_type,
            "timezone": self.timezone,
            "start_local": self.start_local.isoformat(),
            "end_local": self.end_local.isoformat(),
            "priority": self.priority,
            "guaranteed_attention": self.guaranteed_attention,
            "delivery_mode": self.delivery_mode,
            "enabled": self.enabled,
            "creator_principal_id": str(self.creator_principal_id)
            if self.creator_principal_id
            else None,
            "version": self.version,
        }

    def attention_metadata(
        self, *, event_id: str, resource_id: UUID, occurred_at: datetime
    ) -> dict[str, Any]:
        if not self.matches(
            resource_id=resource_id,
            event_type=self.event_type,
            occurred_at=occurred_at,
        ):
            raise SenseGuardPolicyError("event does not match this policy")
        return {
            "alert_policy_id": str(self.policy_id),
            "alert_event_id": event_id,
            "canonical_resource_ids": [str(value) for value in self.resource_ids],
            "guaranteed_attention": self.guaranteed_attention,
            "priority": self.priority,
            "delivery_mode": self.delivery_mode,
            "provenance": "anima.senseguard.alert_policy",
        }


class PostgresSenseGuardAlertPolicyStore:
    """Small optimistic-version store for the typed SenseGuard policy."""

    def __init__(self, database_url: str, connect_timeout: int = 5) -> None:
        self.database_url = database_url
        self.connect_timeout = connect_timeout

    def _connect(self) -> psycopg.Connection[Any]:
        return psycopg.connect(
            self.database_url, connect_timeout=self.connect_timeout, row_factory=dict_row
        )

    def save(
        self, policy: SenseGuardAlertPolicy, *, expected_version: int | None = None
    ) -> SenseGuardAlertPolicy:
        if expected_version is not None and expected_version != policy.version - 1:
            raise SenseGuardPolicyError("SENSEGUARD_POLICY_VERSION_CONFLICT")
        with self._connect() as connection, connection.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO anima_senseguard_alert_policies
                    (policy_id, household_id, resource_ids, event_type, timezone,
                     start_local, end_local, priority, guaranteed_attention,
                     delivery_mode, enabled, creator_principal_id, version)
                VALUES (%s,%s,%s::jsonb,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                ON CONFLICT (policy_id) DO UPDATE SET
                    resource_ids=EXCLUDED.resource_ids, event_type=EXCLUDED.event_type,
                    timezone=EXCLUDED.timezone, start_local=EXCLUDED.start_local,
                    end_local=EXCLUDED.end_local, priority=EXCLUDED.priority,
                    guaranteed_attention=EXCLUDED.guaranteed_attention,
                    delivery_mode=EXCLUDED.delivery_mode, enabled=EXCLUDED.enabled,
                    creator_principal_id=EXCLUDED.creator_principal_id,
                    version=EXCLUDED.version, updated_at=now()
                WHERE anima_senseguard_alert_policies.version = %s
                RETURNING *
                """,
                (
                    policy.policy_id,
                    policy.household_id,
                    json.dumps([str(value) for value in policy.resource_ids]),
                    policy.event_type,
                    policy.timezone,
                    policy.start_local,
                    policy.end_local,
                    policy.priority,
                    policy.guaranteed_attention,
                    policy.delivery_mode,
                    policy.enabled,
                    policy.creator_principal_id,
                    policy.version,
                    expected_version if expected_version is not None else 0,
                ),
            )
            row = cursor.fetchone()
            if row is None:
                connection.rollback()
                raise SenseGuardPolicyError("SENSEGUARD_POLICY_VERSION_CONFLICT")
            connection.commit()
        return policy

    def list_enabled(self, household_id: UUID) -> list[SenseGuardAlertPolicy]:
        """Read the active typed policies for one household."""
        with self._connect() as connection, connection.cursor() as cursor:
            cursor.execute(
                """SELECT * FROM anima_senseguard_alert_policies
                   WHERE household_id=%s AND enabled ORDER BY policy_id""",
                (household_id,),
            )
            rows = cursor.fetchall()
        policies: list[SenseGuardAlertPolicy] = []
        for row in rows:
            resource_ids = row["resource_ids"]
            if isinstance(resource_ids, str):
                resource_ids = json.loads(resource_ids)
            policies.append(
                SenseGuardAlertPolicy(
                    policy_id=UUID(str(row["policy_id"])),
                    household_id=UUID(str(row["household_id"])),
                    resource_ids=tuple(UUID(str(item)) for item in resource_ids),
                    event_type=str(row["event_type"]),
                    timezone=str(row["timezone"]),
                    start_local=row["start_local"],
                    end_local=row["end_local"],
                    priority=int(row["priority"]),
                    guaranteed_attention=bool(row["guaranteed_attention"]),
                    delivery_mode=str(row["delivery_mode"]),
                    enabled=bool(row["enabled"]),
                    creator_principal_id=(
                        UUID(str(row["creator_principal_id"]))
                        if row.get("creator_principal_id")
                        else None
                    ),
                    version=int(row["version"]),
                )
            )
        return policies


class SenseGuardEventRouter:
    """Turn normalized HA SenseGuard events into durable attention events."""

    def __init__(
        self,
        *,
        household_id: UUID,
        policy_store: PostgresSenseGuardAlertPolicyStore,
        resource_resolver: Any,
        event_sink: Any,
        dispatch_attention: Any | None = None,
    ) -> None:
        self.household_id = household_id
        self.policy_store = policy_store
        self.resource_resolver = resource_resolver
        self.event_sink = event_sink
        self.dispatch_attention = dispatch_attention

    def handle(self, event: EventEnvelope) -> list[EventEnvelope]:
        external_id = str(event.metadata.get("external_id", ""))
        if not external_id:
            return []
        resource_id = self.resource_resolver(external_id)
        if resource_id is None:
            return []
        normalized_event_type = str(
            event.metadata.get(
                "senseguard_event_type",
                "senseguard.event" if event.event_type == "truth.observation" else event.event_type,
            )
        )
        alerts: list[EventEnvelope] = []
        for policy in self.policy_store.list_enabled(self.household_id):
            if not policy.matches(
                resource_id=resource_id,
                event_type=normalized_event_type,
                occurred_at=event.occurred_at,
            ):
                continue
            metadata = policy.attention_metadata(
                event_id=event.event_id,
                resource_id=resource_id,
                occurred_at=event.occurred_at,
            )
            alert = EventEnvelope.create(
                event_id=str(
                    uuid5(
                        NAMESPACE_URL,
                        f"anima:senseguard-alert:{policy.policy_id}:{event.event_id}",
                    )
                ),
                source_event_id=event.event_id,
                event_type=policy.event_type,
                source="anima:senseguard-policy",
                subject_key=f"senseguard/{resource_id}",
                occurred_at=event.occurred_at,
                correlation_id=event.correlation_id,
                causation_id=event.event_id,
                payload={
                    "canonical_resource_id": str(resource_id),
                    "source_event_id": event.event_id,
                    "occurred_at": event.occurred_at.isoformat(),
                    "event_type": policy.event_type,
                },
                importance=(
                    EventImportance.CRITICAL if policy.priority >= 90 else EventImportance.IMPORTANT
                ),
                delivery_class=(
                    DeliveryClass.GUARANTEED
                    if policy.guaranteed_attention
                    else DeliveryClass.BEST_EFFORT
                ),
                metadata={"household_id": str(self.household_id), **metadata},
            )
            appended = self.event_sink.append(alert)
            if not appended.deduplicated and self.dispatch_attention is not None:
                self.dispatch_attention()
            alerts.append(alert)
        return alerts


def new_senseguard_policy(
    household_id: UUID,
    resource_ids: tuple[UUID, ...],
    *,
    event_type: str = "senseguard.event",
    timezone: str = "America/New_York",
    start_local: time | str = "00:00",
    end_local: time | str = "05:00",
    creator_principal_id: UUID | None = None,
) -> SenseGuardAlertPolicy:
    return SenseGuardAlertPolicy(
        uuid4(),
        household_id,
        resource_ids,
        event_type,
        timezone,
        _clock(start_local),
        _clock(end_local),
        creator_principal_id=creator_principal_id,
    )
