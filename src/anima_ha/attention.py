"""Deterministic, journal-backed attention and durable reasoning triggers.

Attention selects when future cognition should run.  It never prescribes an
action and it never consumes provider-native events directly.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from enum import StrEnum
from typing import Any
from uuid import UUID, uuid5

import psycopg
from psycopg.rows import dict_row

from anima_ha.events import DeliveryClass, EventImportance

ATTENTION_NAMESPACE = UUID("f8ae3131-5885-4ee6-a4bd-d38c31c938a2")
ATTENTION_PROFILE_SCHEMA_VERSION = 1


class AttentionValidationError(ValueError):
    """Raised when a profile or event cannot be classified safely."""


class AttentionProcessingError(RuntimeError):
    """Raised when ordinary attention processing cannot advance safely."""


class AttentionDecisionClass(StrEnum):
    TRIGGER = "TRIGGER"
    SUPPRESS = "SUPPRESS"
    AGGREGATE_PENDING = "AGGREGATE_PENDING"
    AGGREGATE_TRIGGER = "AGGREGATE_TRIGGER"


class SuppressionReason(StrEnum):
    DUPLICATE = "DUPLICATE"
    COOLDOWN = "COOLDOWN"
    RATE_LIMIT = "RATE_LIMIT"
    LOW_SIGNIFICANCE = "LOW_SIGNIFICANCE"
    AGGREGATED = "AGGREGATED"
    CONFIGURED_IGNORE = "CONFIGURED_IGNORE"


class RuleAction(StrEnum):
    TRIGGER = "TRIGGER"
    AGGREGATE = "AGGREGATE"
    IGNORE = "IGNORE"


class TriggerStatus(StrEnum):
    PENDING = "PENDING"
    CONTEXT_READY = "CONTEXT_READY"
    FAILED_CONTEXT = "FAILED_CONTEXT"


@dataclass(frozen=True, slots=True)
class AttentionRule:
    rule_id: str
    action: RuleAction
    event_types: tuple[str, ...] = ()
    sources: tuple[str, ...] = ()
    subject_prefixes: tuple[str, ...] = ()
    importance: tuple[EventImportance, ...] = ()
    truth_states: tuple[str, ...] = ()
    cooldown_seconds: int = 0
    rate_limit_count: int = 0
    rate_limit_window_seconds: int = 0
    aggregation_window_seconds: int = 0
    priority: int = 50

    def __post_init__(self) -> None:
        object.__setattr__(self, "action", RuleAction(self.action))
        object.__setattr__(
            self, "importance", tuple(EventImportance(value) for value in self.importance)
        )
        if not self.rule_id.strip():
            raise AttentionValidationError("rule_id is required")
        if any(value < 0 for value in (self.cooldown_seconds, self.rate_limit_count)):
            raise AttentionValidationError("cooldown and rate limit must not be negative")
        if self.rate_limit_count and self.rate_limit_window_seconds < 1:
            raise AttentionValidationError("rate limit requires a positive window")
        if self.action == RuleAction.AGGREGATE and self.aggregation_window_seconds < 1:
            raise AttentionValidationError("aggregation requires a positive window")
        if not 0 <= self.priority <= 100:
            raise AttentionValidationError("priority must be between 0 and 100")

    def matches(self, event: dict[str, Any]) -> bool:
        payload = _mapping(event.get("payload"))
        return (
            (not self.event_types or str(event["event_type"]) in self.event_types)
            and (not self.sources or str(event["source"]) in self.sources)
            and (
                not self.subject_prefixes
                or any(
                    str(event["subject_key"]).startswith(value) for value in self.subject_prefixes
                )
            )
            and (
                not self.importance or EventImportance(str(event["importance"])) in self.importance
            )
            and (not self.truth_states or str(payload.get("state", "")) in self.truth_states)
        )

    def to_payload(self) -> dict[str, Any]:
        return {
            "rule_id": self.rule_id,
            "action": self.action.value,
            "event_types": list(self.event_types),
            "sources": list(self.sources),
            "subject_prefixes": list(self.subject_prefixes),
            "importance": [value.value for value in self.importance],
            "truth_states": list(self.truth_states),
            "cooldown_seconds": self.cooldown_seconds,
            "rate_limit_count": self.rate_limit_count,
            "rate_limit_window_seconds": self.rate_limit_window_seconds,
            "aggregation_window_seconds": self.aggregation_window_seconds,
            "priority": self.priority,
        }

    @classmethod
    def from_payload(cls, value: dict[str, Any]) -> AttentionRule:
        return cls(
            rule_id=str(value["rule_id"]),
            action=RuleAction(str(value["action"])),
            event_types=tuple(str(item) for item in value.get("event_types", [])),
            sources=tuple(str(item) for item in value.get("sources", [])),
            subject_prefixes=tuple(str(item) for item in value.get("subject_prefixes", [])),
            importance=tuple(EventImportance(str(item)) for item in value.get("importance", [])),
            truth_states=tuple(str(item) for item in value.get("truth_states", [])),
            cooldown_seconds=int(value.get("cooldown_seconds", 0)),
            rate_limit_count=int(value.get("rate_limit_count", 0)),
            rate_limit_window_seconds=int(value.get("rate_limit_window_seconds", 0)),
            aggregation_window_seconds=int(value.get("aggregation_window_seconds", 0)),
            priority=int(value.get("priority", 50)),
        )


@dataclass(frozen=True, slots=True)
class AttentionProfile:
    profile_version: str
    rules: tuple[AttentionRule, ...]
    schema_version: int = ATTENTION_PROFILE_SCHEMA_VERSION
    guaranteed_event_types: tuple[str, ...] = (
        "user.request",
        "security.alarm",
        "safety.leak",
        "system.health.critical",
        "scheduled_reasoning_due",
    )

    def __post_init__(self) -> None:
        if self.schema_version != ATTENTION_PROFILE_SCHEMA_VERSION:
            raise AttentionValidationError("unsupported attention profile schema version")
        if not self.profile_version.strip():
            raise AttentionValidationError("profile_version is required")
        identifiers = [rule.rule_id for rule in self.rules]
        if len(identifiers) != len(set(identifiers)):
            raise AttentionValidationError("attention rule IDs must be unique")

    def to_payload(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "profile_version": self.profile_version,
            "guaranteed_event_types": list(self.guaranteed_event_types),
            "rules": [rule.to_payload() for rule in self.rules],
        }

    @property
    def digest(self) -> str:
        return _digest(self.to_payload())

    @classmethod
    def from_payload(cls, value: dict[str, Any]) -> AttentionProfile:
        return cls(
            profile_version=str(value["profile_version"]),
            schema_version=int(value.get("schema_version", 0)),
            guaranteed_event_types=tuple(
                str(item) for item in value.get("guaranteed_event_types", [])
            ),
            rules=tuple(AttentionRule.from_payload(dict(item)) for item in value.get("rules", [])),
        )


@dataclass(frozen=True, slots=True)
class AttentionDecision:
    attention_decision_id: UUID
    source_event_id: str
    journal_position: int
    attention_profile_version: str
    decision: AttentionDecisionClass
    reason_code: str
    created_at: datetime
    correlation_key: str | None = None
    aggregation_key: str | None = None
    resulting_trigger_id: UUID | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_payload(self) -> dict[str, Any]:
        return {
            "attention_decision_id": str(self.attention_decision_id),
            "source_event_id": self.source_event_id,
            "journal_position": self.journal_position,
            "attention_profile_version": self.attention_profile_version,
            "decision": self.decision.value,
            "reason_code": self.reason_code,
            "correlation_key": self.correlation_key,
            "aggregation_key": self.aggregation_key,
            "created_at": self.created_at.isoformat(),
            "resulting_trigger_id": str(self.resulting_trigger_id)
            if self.resulting_trigger_id
            else None,
            "metadata": self.metadata,
        }


@dataclass(frozen=True, slots=True)
class ReasoningTrigger:
    trigger_id: UUID
    trigger_type: str
    source_event_ids: tuple[str, ...]
    journal_position_range: tuple[int, int]
    subject_refs: tuple[str, ...]
    attention_reason: str
    priority: int
    created_at: datetime
    attention_profile_version: str
    correlation_id: str | None = None
    context_status: TriggerStatus = TriggerStatus.PENDING
    status: TriggerStatus = TriggerStatus.PENDING
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_payload(self) -> dict[str, Any]:
        return {
            "trigger_id": str(self.trigger_id),
            "trigger_type": self.trigger_type,
            "source_event_ids": list(self.source_event_ids),
            "journal_position_range": list(self.journal_position_range),
            "subject_refs": list(self.subject_refs),
            "correlation_id": self.correlation_id,
            "attention_reason": self.attention_reason,
            "priority": self.priority,
            "created_at": self.created_at.isoformat(),
            "attention_profile_version": self.attention_profile_version,
            "context_status": self.context_status.value,
            "status": self.status.value,
            "metadata": self.metadata,
        }


@dataclass(frozen=True, slots=True)
class AttentionProcessResult:
    processed: int
    decisions: int
    triggers: int
    last_position: int
    failed_position: int | None = None
    failure: str | None = None


def default_attention_profile(version: str = "phase7.v1") -> AttentionProfile:
    """A provider-independent prototype profile with no behavioral actions."""

    return AttentionProfile(
        version,
        (
            AttentionRule(
                "user_request",
                RuleAction.TRIGGER,
                event_types=("user.request",),
                priority=90,
            ),
            AttentionRule(
                "critical_uncertainty",
                RuleAction.TRIGGER,
                event_types=("truth.observation",),
                truth_states=("UNKNOWN", "UNAVAILABLE"),
                importance=(EventImportance.IMPORTANT, EventImportance.CRITICAL),
                priority=85,
            ),
            AttentionRule(
                "ordinary_motion",
                RuleAction.AGGREGATE,
                event_types=("household.motion",),
                aggregation_window_seconds=60,
                priority=35,
            ),
            AttentionRule(
                "material_state_change",
                RuleAction.TRIGGER,
                event_types=("truth.observation",),
                cooldown_seconds=30,
                rate_limit_count=10,
                rate_limit_window_seconds=60,
                priority=50,
            ),
            AttentionRule(
                "ignore_lifecycle_noise",
                RuleAction.IGNORE,
                event_types=("plugin.health.sample",),
                priority=0,
            ),
        ),
    )


def _mapping(value: Any) -> dict[str, Any]:
    if isinstance(value, str):
        parsed = json.loads(value)
        return dict(parsed) if isinstance(parsed, dict) else {}
    return dict(value) if isinstance(value, dict) else {}


def _sequence(value: Any) -> list[Any]:
    if isinstance(value, str):
        parsed = json.loads(value)
        return list(parsed) if isinstance(parsed, list) else []
    return list(value) if isinstance(value, list) else []


def _digest(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":"), default=str).encode()
    ).hexdigest()


def _uuid(key: str) -> UUID:
    return uuid5(ATTENTION_NAMESPACE, key)


def _is_guaranteed(profile: AttentionProfile, event: dict[str, Any]) -> bool:
    metadata = _mapping(event.get("metadata"))
    return (
        DeliveryClass(str(event["delivery_class"])) == DeliveryClass.GUARANTEED
        or str(event["event_type"]) in profile.guaranteed_event_types
        or metadata.get("guaranteed_attention") is True
    )


def _is_high_importance(event: dict[str, Any]) -> bool:
    return EventImportance(str(event["importance"])) in {
        EventImportance.IMPORTANT,
        EventImportance.CRITICAL,
    }


def _is_duplicate_or_unchanged(event: dict[str, Any]) -> bool:
    metadata = _mapping(event.get("metadata"))
    payload = _mapping(event.get("payload"))
    if metadata.get("duplicate_of") or metadata.get("unchanged") is True:
        return True
    if "previous_value" in payload and "value" in payload:
        return bool(payload["previous_value"] == payload["value"])
    return False


def _matched_rule(profile: AttentionProfile, event: dict[str, Any]) -> AttentionRule | None:
    return next((rule for rule in profile.rules if rule.matches(event)), None)


class PostgresAttentionService:
    """Restart-safe attention processor over canonical journal positions."""

    def __init__(self, database_url: str, connect_timeout: int = 5) -> None:
        self.database_url = database_url
        self.connect_timeout = connect_timeout

    def _connect(self) -> psycopg.Connection[Any]:
        return psycopg.connect(
            self.database_url, connect_timeout=self.connect_timeout, row_factory=dict_row
        )

    def register_profile(
        self, profile: AttentionProfile, *, active: bool = True, now: datetime | None = None
    ) -> None:
        now = now or datetime.now(UTC)
        with self._connect() as connection, connection.cursor() as cursor:
            if active:
                cursor.execute("UPDATE anima_attention_profiles SET active = FALSE WHERE active")
            cursor.execute(
                """
                INSERT INTO anima_attention_profiles
                    (profile_version, profile_digest, configuration, activated_at, active)
                VALUES (%s, %s, %s::jsonb, %s, %s)
                ON CONFLICT (profile_version) DO UPDATE SET
                    active = EXCLUDED.active
                WHERE anima_attention_profiles.profile_digest = EXCLUDED.profile_digest
                RETURNING profile_digest
                """,
                (
                    profile.profile_version,
                    profile.digest,
                    json.dumps(profile.to_payload(), sort_keys=True),
                    now,
                    active,
                ),
            )
            row = cursor.fetchone()
            if row is None or str(row["profile_digest"]) != profile.digest:
                raise AttentionValidationError("profile version cannot be reused with new content")
            connection.commit()

    def prime_consumer_before(
        self, profile: AttentionProfile, consumer_name: str, journal_position: int
    ) -> None:
        """Create an isolated cursor immediately before a known event."""
        if journal_position < 0:
            raise AttentionValidationError("journal position must not be negative")
        self.register_profile(profile, active=False)
        with self._connect() as connection, connection.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO anima_attention_cursors (consumer_name, profile_version, last_position)
                VALUES (%s, %s, %s)
                ON CONFLICT (consumer_name) DO NOTHING
                """,
                (consumer_name, profile.profile_version, journal_position),
            )
            connection.commit()

    def load_profile(self, profile_version: str) -> AttentionProfile:
        with self._connect() as connection, connection.cursor() as cursor:
            cursor.execute(
                "SELECT configuration FROM anima_attention_profiles WHERE profile_version = %s",
                (profile_version,),
            )
            row = cursor.fetchone()
        if row is None:
            raise AttentionValidationError("attention profile is not registered")
        return AttentionProfile.from_payload(_mapping(row["configuration"]))

    @staticmethod
    def _event_time(event: dict[str, Any]) -> datetime:
        value = event["recorded_at"]
        if not isinstance(value, datetime):
            value = datetime.fromisoformat(str(value))
        return value.astimezone(UTC)

    @staticmethod
    def _correlation_key(event: dict[str, Any]) -> str:
        return str(event.get("correlation_id") or event.get("causation_id") or event["subject_key"])

    @staticmethod
    def _household_scope(event: dict[str, Any]) -> str:
        metadata = _mapping(event.get("metadata"))
        return str(metadata.get("household_id") or "default")

    @staticmethod
    def _insert_metric(
        cursor: psycopg.Cursor[Any], profile_version: str, metric: str, amount: int = 1
    ) -> None:
        cursor.execute(
            """
            INSERT INTO anima_attention_metrics (profile_version, metric_name, metric_value)
            VALUES (%s, %s, %s)
            ON CONFLICT (profile_version, metric_name) DO UPDATE SET
                metric_value = anima_attention_metrics.metric_value + EXCLUDED.metric_value,
                updated_at = now()
            """,
            (profile_version, metric, amount),
        )

    def _persist_decision(
        self,
        cursor: psycopg.Cursor[Any],
        *,
        event: dict[str, Any],
        profile: AttentionProfile,
        decision_class: AttentionDecisionClass,
        reason_code: str,
        idempotency_key: str,
        aggregation_key: str | None = None,
        trigger: ReasoningTrigger | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> AttentionDecision:
        decision_id = _uuid(f"decision:{idempotency_key}")
        created_at = self._event_time(event)
        decision = AttentionDecision(
            decision_id,
            str(event["event_id"]),
            int(event["journal_position"]),
            profile.profile_version,
            decision_class,
            reason_code,
            created_at,
            self._correlation_key(event),
            aggregation_key,
            trigger.trigger_id if trigger else None,
            metadata or {},
        )
        cursor.execute(
            """
            INSERT INTO anima_attention_decisions (
                attention_decision_id, idempotency_key, source_event_id, journal_position,
                attention_profile_version, decision, reason_code, correlation_key,
                aggregation_key, created_at, resulting_trigger_id, metadata
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb)
            ON CONFLICT (idempotency_key) DO NOTHING
            """,
            (
                decision.attention_decision_id,
                idempotency_key,
                decision.source_event_id,
                decision.journal_position,
                decision.attention_profile_version,
                decision.decision.value,
                decision.reason_code,
                decision.correlation_key,
                decision.aggregation_key,
                decision.created_at,
                decision.resulting_trigger_id,
                json.dumps(decision.metadata, sort_keys=True),
            ),
        )
        if trigger is not None:
            cursor.execute(
                """
                INSERT INTO anima_reasoning_triggers (
                    trigger_id, decision_id, trigger_type, source_event_ids,
                    journal_position_start, journal_position_end, subject_refs,
                    correlation_id, attention_reason, priority, created_at,
                    attention_profile_version, context_status, status, metadata
                ) VALUES (%s, %s, %s, %s::jsonb, %s, %s, %s::jsonb, %s, %s,
                          %s, %s, %s, %s, %s, %s::jsonb)
                ON CONFLICT (trigger_id) DO NOTHING
                """,
                (
                    trigger.trigger_id,
                    decision.attention_decision_id,
                    trigger.trigger_type,
                    json.dumps(list(trigger.source_event_ids)),
                    trigger.journal_position_range[0],
                    trigger.journal_position_range[1],
                    json.dumps(list(trigger.subject_refs)),
                    trigger.correlation_id,
                    trigger.attention_reason,
                    trigger.priority,
                    trigger.created_at,
                    trigger.attention_profile_version,
                    trigger.context_status.value,
                    trigger.status.value,
                    json.dumps(trigger.metadata, sort_keys=True),
                ),
            )
            self._insert_metric(cursor, profile.profile_version, "triggers_emitted")
        self._insert_metric(cursor, profile.profile_version, "decisions_recorded")
        if decision_class == AttentionDecisionClass.SUPPRESS:
            self._insert_metric(
                cursor, profile.profile_version, f"suppressed_{reason_code.lower()}"
            )
        return decision

    def _trigger_for_event(
        self,
        profile: AttentionProfile,
        event: dict[str, Any],
        reason: str,
        priority: int,
        idempotency_key: str,
    ) -> ReasoningTrigger:
        return ReasoningTrigger(
            _uuid(f"trigger:{idempotency_key}"),
            "EVENT",
            (str(event["event_id"]),),
            (int(event["journal_position"]), int(event["journal_position"])),
            (str(event["subject_key"]),),
            reason,
            priority,
            self._event_time(event),
            profile.profile_version,
            str(event["correlation_id"]) if event.get("correlation_id") else None,
            metadata={"household_id": self._household_scope(event)},
        )

    def _cooldown_active(
        self,
        cursor: psycopg.Cursor[Any],
        profile: AttentionProfile,
        rule: AttentionRule,
        event: dict[str, Any],
    ) -> bool:
        if not rule.cooldown_seconds:
            return False
        cursor.execute(
            """
            SELECT last_trigger_at FROM anima_attention_cooldowns
            WHERE profile_version = %s AND household_scope = %s
              AND rule_id = %s AND subject_key = %s
            """,
            (
                profile.profile_version,
                self._household_scope(event),
                rule.rule_id,
                str(event["subject_key"]),
            ),
        )
        row = cursor.fetchone()
        return bool(
            row
            and self._event_time(event)
            < row["last_trigger_at"] + timedelta(seconds=rule.cooldown_seconds)
        )

    def _rate_limited(
        self,
        cursor: psycopg.Cursor[Any],
        profile: AttentionProfile,
        rule: AttentionRule,
        event: dict[str, Any],
    ) -> bool:
        if not rule.rate_limit_count:
            return False
        at = self._event_time(event)
        epoch = int(at.timestamp())
        start = datetime.fromtimestamp(epoch - epoch % rule.rate_limit_window_seconds, tz=UTC)
        cursor.execute(
            """
            SELECT trigger_count FROM anima_attention_rate_windows
            WHERE profile_version = %s AND household_scope = %s
              AND rule_id = %s AND window_start = %s
            """,
            (profile.profile_version, self._household_scope(event), rule.rule_id, start),
        )
        row = cursor.fetchone()
        return bool(row and int(row["trigger_count"]) >= rule.rate_limit_count)

    def _mark_trigger_state(
        self,
        cursor: psycopg.Cursor[Any],
        profile: AttentionProfile,
        rule: AttentionRule,
        event: dict[str, Any],
    ) -> None:
        at = self._event_time(event)
        if rule.cooldown_seconds:
            cursor.execute(
                """
                INSERT INTO anima_attention_cooldowns
                    (profile_version, household_scope, rule_id, subject_key, last_trigger_at)
                VALUES (%s, %s, %s, %s, %s)
                ON CONFLICT (profile_version, household_scope, rule_id, subject_key)
                DO UPDATE SET last_trigger_at = GREATEST(
                    anima_attention_cooldowns.last_trigger_at, EXCLUDED.last_trigger_at
                )
                """,
                (
                    profile.profile_version,
                    self._household_scope(event),
                    rule.rule_id,
                    str(event["subject_key"]),
                    at,
                ),
            )
        if rule.rate_limit_count:
            epoch = int(at.timestamp())
            start = datetime.fromtimestamp(epoch - epoch % rule.rate_limit_window_seconds, tz=UTC)
            cursor.execute(
                """
                INSERT INTO anima_attention_rate_windows
                    (profile_version, household_scope, rule_id, window_start, trigger_count)
                VALUES (%s, %s, %s, %s, 1)
                ON CONFLICT (profile_version, household_scope, rule_id, window_start)
                DO UPDATE SET trigger_count = anima_attention_rate_windows.trigger_count + 1
                """,
                (profile.profile_version, self._household_scope(event), rule.rule_id, start),
            )

    def _aggregate(
        self,
        cursor: psycopg.Cursor[Any],
        profile: AttentionProfile,
        rule: AttentionRule,
        event: dict[str, Any],
    ) -> None:
        at = self._event_time(event)
        seconds = rule.aggregation_window_seconds
        epoch = int(at.timestamp())
        start = datetime.fromtimestamp(epoch - epoch % seconds, tz=UTC)
        end = start + timedelta(seconds=seconds)
        key = f"{event['event_type']}:{event['subject_key']}"
        idempotency_key = f"{profile.profile_version}:{rule.rule_id}:{key}:{start.isoformat()}"
        aggregate_id = _uuid(f"aggregate:{idempotency_key}")
        cursor.execute(
            """
            INSERT INTO anima_attention_aggregates (
                aggregate_id, idempotency_key, profile_version, household_scope, rule_id,
                aggregation_key, event_type, subject_key, window_start, window_end,
                event_count, first_seen, last_seen, source_event_ids, journal_positions
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, 1, %s, %s,
                      %s::jsonb, %s::jsonb)
            ON CONFLICT (idempotency_key) DO UPDATE SET
                event_count = anima_attention_aggregates.event_count + 1,
                first_seen = LEAST(anima_attention_aggregates.first_seen, EXCLUDED.first_seen),
                last_seen = GREATEST(anima_attention_aggregates.last_seen, EXCLUDED.last_seen),
                source_event_ids = anima_attention_aggregates.source_event_ids
                    || EXCLUDED.source_event_ids,
                journal_positions = anima_attention_aggregates.journal_positions
                    || EXCLUDED.journal_positions
            """,
            (
                aggregate_id,
                idempotency_key,
                profile.profile_version,
                self._household_scope(event),
                rule.rule_id,
                key,
                str(event["event_type"]),
                str(event["subject_key"]),
                start,
                end,
                at,
                at,
                json.dumps([str(event["event_id"])]),
                json.dumps([int(event["journal_position"])]),
            ),
        )
        self._persist_decision(
            cursor,
            event=event,
            profile=profile,
            decision_class=AttentionDecisionClass.AGGREGATE_PENDING,
            reason_code=SuppressionReason.AGGREGATED.value,
            idempotency_key=f"source:{profile.profile_version}:{event['event_id']}",
            aggregation_key=key,
            metadata={"rule_id": rule.rule_id, "window_start": start.isoformat()},
        )

    def _flush_due(
        self,
        cursor: psycopg.Cursor[Any],
        profile: AttentionProfile,
        due_at: datetime,
    ) -> int:
        cursor.execute(
            """
            SELECT * FROM anima_attention_aggregates
            WHERE profile_version = %s AND closed_at IS NULL AND window_end <= %s
            ORDER BY window_end, aggregate_id FOR UPDATE
            """,
            (profile.profile_version, due_at),
        )
        rows = list(cursor.fetchall())
        rules = {rule.rule_id: rule for rule in profile.rules}
        for row in rows:
            source_ids = tuple(str(value) for value in _sequence(row["source_event_ids"]))
            positions = tuple(int(value) for value in _sequence(row["journal_positions"]))
            representative = {
                "event_id": source_ids[0],
                "journal_position": positions[0],
                "event_type": str(row["event_type"]),
                "source": "anima.attention.aggregate",
                "subject_key": str(row["subject_key"]),
                "recorded_at": row["window_end"],
                "occurred_at": row["first_seen"],
                "importance": EventImportance.NORMAL.value,
                "delivery_class": DeliveryClass.BEST_EFFORT.value,
                "payload": {},
                "metadata": {"household_id": str(row["household_scope"])},
                "correlation_id": None,
                "causation_id": None,
            }
            close_key = f"aggregate-close:{row['idempotency_key']}"
            rule = rules[str(row["rule_id"])]
            trigger = ReasoningTrigger(
                _uuid(f"trigger:{close_key}"),
                "AGGREGATE",
                source_ids,
                (min(positions), max(positions)),
                (str(row["subject_key"]),),
                "AGGREGATION_WINDOW_COMPLETE",
                rule.priority,
                row["window_end"],
                profile.profile_version,
                metadata={
                    "event_type": str(row["event_type"]),
                    "count": int(row["event_count"]),
                    "first_seen": row["first_seen"].isoformat(),
                    "last_seen": row["last_seen"].isoformat(),
                    "aggregation_key": str(row["aggregation_key"]),
                },
            )
            self._persist_decision(
                cursor,
                event=representative,
                profile=profile,
                decision_class=AttentionDecisionClass.AGGREGATE_TRIGGER,
                reason_code="AGGREGATION_WINDOW_COMPLETE",
                idempotency_key=close_key,
                aggregation_key=str(row["aggregation_key"]),
                trigger=trigger,
                metadata={"rule_id": str(row["rule_id"]), "source_count": len(source_ids)},
            )
            cursor.execute(
                """
                UPDATE anima_attention_aggregates
                SET closed_at = %s, resulting_trigger_id = %s
                WHERE aggregate_id = %s AND closed_at IS NULL
                """,
                (due_at, trigger.trigger_id, row["aggregate_id"]),
            )
            self._insert_metric(cursor, profile.profile_version, "aggregates_flushed")
        return len(rows)

    def _process_event(
        self,
        cursor: psycopg.Cursor[Any],
        profile: AttentionProfile,
        event: dict[str, Any],
    ) -> int:
        source_key = f"source:{profile.profile_version}:{event['event_id']}"
        if _is_guaranteed(profile, event):
            trigger = self._trigger_for_event(profile, event, "GUARANTEED_CLASS", 100, source_key)
            self._persist_decision(
                cursor,
                event=event,
                profile=profile,
                decision_class=AttentionDecisionClass.TRIGGER,
                reason_code="GUARANTEED_CLASS",
                idempotency_key=source_key,
                trigger=trigger,
                metadata={"guaranteed": True},
            )
            self._insert_metric(cursor, profile.profile_version, "guaranteed_triggers")
            return 1
        if _is_duplicate_or_unchanged(event):
            self._persist_decision(
                cursor,
                event=event,
                profile=profile,
                decision_class=AttentionDecisionClass.SUPPRESS,
                reason_code=SuppressionReason.DUPLICATE.value,
                idempotency_key=source_key,
            )
            return 0
        rule = _matched_rule(profile, event)
        if rule is None:
            if _is_high_importance(event):
                trigger = self._trigger_for_event(
                    profile, event, "UNCLASSIFIED_HIGH_IMPORTANCE", 90, source_key
                )
                self._persist_decision(
                    cursor,
                    event=event,
                    profile=profile,
                    decision_class=AttentionDecisionClass.TRIGGER,
                    reason_code="UNCLASSIFIED_HIGH_IMPORTANCE",
                    idempotency_key=source_key,
                    trigger=trigger,
                )
                return 1
            self._persist_decision(
                cursor,
                event=event,
                profile=profile,
                decision_class=AttentionDecisionClass.SUPPRESS,
                reason_code=SuppressionReason.LOW_SIGNIFICANCE.value,
                idempotency_key=source_key,
            )
            return 0
        if rule.action == RuleAction.IGNORE:
            self._persist_decision(
                cursor,
                event=event,
                profile=profile,
                decision_class=AttentionDecisionClass.SUPPRESS,
                reason_code=SuppressionReason.CONFIGURED_IGNORE.value,
                idempotency_key=source_key,
                metadata={"rule_id": rule.rule_id},
            )
            return 0
        if rule.action == RuleAction.AGGREGATE:
            self._aggregate(cursor, profile, rule, event)
            return 0
        if self._cooldown_active(cursor, profile, rule, event):
            self._persist_decision(
                cursor,
                event=event,
                profile=profile,
                decision_class=AttentionDecisionClass.SUPPRESS,
                reason_code=SuppressionReason.COOLDOWN.value,
                idempotency_key=source_key,
                metadata={"rule_id": rule.rule_id},
            )
            return 0
        if self._rate_limited(cursor, profile, rule, event):
            self._persist_decision(
                cursor,
                event=event,
                profile=profile,
                decision_class=AttentionDecisionClass.SUPPRESS,
                reason_code=SuppressionReason.RATE_LIMIT.value,
                idempotency_key=source_key,
                metadata={"rule_id": rule.rule_id},
            )
            return 0
        trigger = self._trigger_for_event(
            profile, event, f"RULE:{rule.rule_id}", rule.priority, source_key
        )
        self._persist_decision(
            cursor,
            event=event,
            profile=profile,
            decision_class=AttentionDecisionClass.TRIGGER,
            reason_code=f"RULE:{rule.rule_id}",
            idempotency_key=source_key,
            trigger=trigger,
            metadata={"rule_id": rule.rule_id},
        )
        self._mark_trigger_state(cursor, profile, rule, event)
        return 1

    def process(
        self,
        profile: AttentionProfile,
        *,
        consumer_name: str = "attention-live",
        limit: int = 1000,
        flush_due_at: datetime | None = None,
    ) -> AttentionProcessResult:
        if limit < 1:
            raise AttentionValidationError("limit must be positive")
        self.register_profile(profile)
        failed_event: dict[str, Any] | None = None
        last_position = 0
        try:
            with self._connect() as connection, connection.cursor() as cursor:
                cursor.execute(
                    "SELECT pg_advisory_xact_lock(hashtext(%s))",
                    (f"anima.attention:{consumer_name}",),
                )
                cursor.execute(
                    """
                    INSERT INTO anima_attention_cursors (consumer_name, profile_version)
                    VALUES (%s, %s) ON CONFLICT (consumer_name) DO NOTHING
                    """,
                    (consumer_name, profile.profile_version),
                )
                cursor.execute(
                    "SELECT * FROM anima_attention_cursors WHERE consumer_name = %s FOR UPDATE",
                    (consumer_name,),
                )
                checkpoint = cursor.fetchone()
                assert checkpoint is not None
                if str(checkpoint["profile_version"]) != profile.profile_version:
                    raise AttentionValidationError(
                        "a live cursor cannot silently switch attention profile"
                    )
                last_position = int(checkpoint["last_position"])
                cursor.execute(
                    """
                    SELECT journal_position, event_id, schema_version, event_type, source,
                           source_event_id, subject_key, occurred_at, recorded_at,
                           source_sequence, correlation_id, causation_id, confidence,
                           evidence_kind, importance, delivery_class, payload, metadata
                    FROM anima_event_journal WHERE journal_position > %s
                    ORDER BY journal_position ASC LIMIT %s
                    """,
                    (last_position, limit),
                )
                events = list(cursor.fetchall())
                decisions = 0
                triggers = 0
                for event in events:
                    failed_event = event
                    self._flush_due(cursor, profile, self._event_time(event))
                    triggers += self._process_event(cursor, profile, event)
                    decisions += 1
                    last_position = int(event["journal_position"])
                    cursor.execute(
                        """
                        UPDATE anima_attention_cursors SET last_position = %s,
                            updated_at = now(), last_error = NULL
                        WHERE consumer_name = %s
                        """,
                        (last_position, consumer_name),
                    )
                    self._insert_metric(cursor, profile.profile_version, "journal_events_processed")
                if flush_due_at is not None:
                    triggers += self._flush_due(cursor, profile, flush_due_at)
                connection.commit()
                return AttentionProcessResult(len(events), decisions, triggers, last_position)
        except Exception as exc:
            if failed_event is not None:
                with self._connect() as failure_connection, failure_connection.cursor() as cursor:
                    cursor.execute(
                        """
                        INSERT INTO anima_attention_failures (
                            consumer_name, journal_position, source_event_id,
                            error_class, error_message
                        ) VALUES (%s, %s, %s, %s, %s)
                        ON CONFLICT (consumer_name, journal_position) DO UPDATE SET
                            error_class = EXCLUDED.error_class,
                            error_message = EXCLUDED.error_message,
                            failed_at = now(),
                            retry_count = anima_attention_failures.retry_count + 1
                        """,
                        (
                            consumer_name,
                            int(failed_event["journal_position"]),
                            str(failed_event["event_id"]),
                            type(exc).__name__,
                            str(exc),
                        ),
                    )
                    cursor.execute(
                        """UPDATE anima_attention_cursors SET last_error = %s
                           WHERE consumer_name = %s""",
                        (str(exc), consumer_name),
                    )
                    failure_connection.commit()
                return AttentionProcessResult(
                    0,
                    0,
                    0,
                    last_position,
                    int(failed_event["journal_position"]),
                    str(exc),
                )
            raise

    def cursor(self, consumer_name: str = "attention-live") -> int:
        with self._connect() as connection, connection.cursor() as cursor:
            cursor.execute(
                "SELECT last_position FROM anima_attention_cursors WHERE consumer_name = %s",
                (consumer_name,),
            )
            row = cursor.fetchone()
        return int(row["last_position"]) if row else 0

    def list_decisions(self, profile_version: str) -> list[dict[str, Any]]:
        with self._connect() as connection, connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT * FROM anima_attention_decisions
                WHERE attention_profile_version = %s
                ORDER BY journal_position, created_at, attention_decision_id
                """,
                (profile_version,),
            )
            return list(cursor.fetchall())

    def list_triggers(self, profile_version: str) -> list[ReasoningTrigger]:
        with self._connect() as connection, connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT * FROM anima_reasoning_triggers
                WHERE attention_profile_version = %s
                ORDER BY journal_position_start, created_at, trigger_id
                """,
                (profile_version,),
            )
            rows = list(cursor.fetchall())
        return [
            ReasoningTrigger(
                UUID(str(row["trigger_id"])),
                str(row["trigger_type"]),
                tuple(str(value) for value in _sequence(row["source_event_ids"])),
                (int(row["journal_position_start"]), int(row["journal_position_end"])),
                tuple(str(value) for value in _sequence(row["subject_refs"])),
                str(row["attention_reason"]),
                int(row["priority"]),
                row["created_at"],
                str(row["attention_profile_version"]),
                str(row["correlation_id"]) if row["correlation_id"] else None,
                TriggerStatus(str(row["context_status"])),
                TriggerStatus(str(row["status"])),
                _mapping(row["metadata"]),
            )
            for row in rows
        ]

    def metrics(self, profile_version: str) -> dict[str, int]:
        with self._connect() as connection, connection.cursor() as cursor:
            cursor.execute(
                """SELECT metric_name, metric_value FROM anima_attention_metrics
                   WHERE profile_version = %s""",
                (profile_version,),
            )
            return {str(row["metric_name"]): int(row["metric_value"]) for row in cursor.fetchall()}


@dataclass(slots=True)
class _ReplayAggregate:
    rule: AttentionRule
    key: str
    start: datetime
    end: datetime
    events: list[dict[str, Any]] = field(default_factory=list)


@dataclass(frozen=True, slots=True)
class ReplayResult:
    profile_version: str
    decisions: tuple[dict[str, Any], ...]
    triggers: tuple[ReasoningTrigger, ...]


class AttentionReplay:
    """Pure, side-effect-free evaluator used for replay and profile comparison."""

    def evaluate(
        self,
        profile: AttentionProfile,
        events: list[dict[str, Any]],
        *,
        flush_at: datetime | None = None,
    ) -> ReplayResult:
        decisions: list[dict[str, Any]] = []
        triggers: list[ReasoningTrigger] = []
        cooldowns: dict[tuple[str, str], datetime] = {}
        rates: dict[tuple[str, datetime], int] = {}
        aggregates: dict[tuple[str, str, datetime], _ReplayAggregate] = {}

        def close(due_at: datetime) -> None:
            due = sorted(
                [item for item in aggregates.values() if item.end <= due_at],
                key=lambda item: (item.end, item.rule.rule_id, item.key),
            )
            for item in due:
                aggregate_events = item.events
                source_ids = tuple(str(event["event_id"]) for event in aggregate_events)
                positions = tuple(int(event["journal_position"]) for event in aggregate_events)
                key = (
                    f"aggregate-close:{profile.profile_version}:{item.rule.rule_id}:"
                    f"{item.key}:{item.start.isoformat()}"
                )
                trigger = ReasoningTrigger(
                    _uuid(f"trigger:{key}"),
                    "AGGREGATE",
                    source_ids,
                    (min(positions), max(positions)),
                    (str(aggregate_events[0]["subject_key"]),),
                    "AGGREGATION_WINDOW_COMPLETE",
                    item.rule.priority,
                    item.end,
                    profile.profile_version,
                    metadata={"count": len(source_ids), "aggregation_key": item.key},
                )
                triggers.append(trigger)
                decisions.append(
                    {
                        "event_id": source_ids[0],
                        "decision": AttentionDecisionClass.AGGREGATE_TRIGGER.value,
                        "reason_code": "AGGREGATION_WINDOW_COMPLETE",
                        "trigger_id": str(trigger.trigger_id),
                    }
                )
                aggregates.pop((item.rule.rule_id, item.key, item.start))

        for event in sorted(events, key=lambda item: int(item["journal_position"])):
            at = PostgresAttentionService._event_time(event)
            close(at)
            source_key = f"source:{profile.profile_version}:{event['event_id']}"
            if _is_guaranteed(profile, event):
                trigger = ReasoningTrigger(
                    _uuid(f"trigger:{source_key}"),
                    "EVENT",
                    (str(event["event_id"]),),
                    (int(event["journal_position"]), int(event["journal_position"])),
                    (str(event["subject_key"]),),
                    "GUARANTEED_CLASS",
                    100,
                    at,
                    profile.profile_version,
                )
                triggers.append(trigger)
                decisions.append(
                    {
                        "event_id": event["event_id"],
                        "decision": "TRIGGER",
                        "reason_code": "GUARANTEED_CLASS",
                    }
                )
                continue
            if _is_duplicate_or_unchanged(event):
                decisions.append(
                    {
                        "event_id": event["event_id"],
                        "decision": "SUPPRESS",
                        "reason_code": "DUPLICATE",
                    }
                )
                continue
            rule = _matched_rule(profile, event)
            if rule is None:
                if _is_high_importance(event):
                    trigger = ReasoningTrigger(
                        _uuid(f"trigger:{source_key}"),
                        "EVENT",
                        (str(event["event_id"]),),
                        (int(event["journal_position"]), int(event["journal_position"])),
                        (str(event["subject_key"]),),
                        "UNCLASSIFIED_HIGH_IMPORTANCE",
                        90,
                        at,
                        profile.profile_version,
                    )
                    triggers.append(trigger)
                    decisions.append(
                        {
                            "event_id": event["event_id"],
                            "decision": "TRIGGER",
                            "reason_code": "UNCLASSIFIED_HIGH_IMPORTANCE",
                        }
                    )
                else:
                    decisions.append(
                        {
                            "event_id": event["event_id"],
                            "decision": "SUPPRESS",
                            "reason_code": "LOW_SIGNIFICANCE",
                        }
                    )
                continue
            if rule.action == RuleAction.IGNORE:
                decisions.append(
                    {
                        "event_id": event["event_id"],
                        "decision": "SUPPRESS",
                        "reason_code": "CONFIGURED_IGNORE",
                    }
                )
                continue
            if rule.action == RuleAction.AGGREGATE:
                seconds = rule.aggregation_window_seconds
                epoch = int(at.timestamp())
                start = datetime.fromtimestamp(epoch - epoch % seconds, tz=UTC)
                key = f"{event['event_type']}:{event['subject_key']}"
                aggregate = aggregates.setdefault(
                    (rule.rule_id, key, start),
                    _ReplayAggregate(rule, key, start, start + timedelta(seconds=seconds)),
                )
                aggregate.events.append(event)
                decisions.append(
                    {
                        "event_id": event["event_id"],
                        "decision": "AGGREGATE_PENDING",
                        "reason_code": "AGGREGATED",
                    }
                )
                continue
            cooldown_key = (rule.rule_id, str(event["subject_key"]))
            last = cooldowns.get(cooldown_key)
            if last and at < last + timedelta(seconds=rule.cooldown_seconds):
                decisions.append(
                    {
                        "event_id": event["event_id"],
                        "decision": "SUPPRESS",
                        "reason_code": "COOLDOWN",
                    }
                )
                continue
            if rule.rate_limit_count:
                epoch = int(at.timestamp())
                window = datetime.fromtimestamp(
                    epoch - epoch % rule.rate_limit_window_seconds, tz=UTC
                )
                rate_key = (rule.rule_id, window)
                if rates.get(rate_key, 0) >= rule.rate_limit_count:
                    decisions.append(
                        {
                            "event_id": event["event_id"],
                            "decision": "SUPPRESS",
                            "reason_code": "RATE_LIMIT",
                        }
                    )
                    continue
                rates[rate_key] = rates.get(rate_key, 0) + 1
            cooldowns[cooldown_key] = at
            trigger = ReasoningTrigger(
                _uuid(f"trigger:{source_key}"),
                "EVENT",
                (str(event["event_id"]),),
                (int(event["journal_position"]), int(event["journal_position"])),
                (str(event["subject_key"]),),
                f"RULE:{rule.rule_id}",
                rule.priority,
                at,
                profile.profile_version,
            )
            triggers.append(trigger)
            decisions.append(
                {
                    "event_id": event["event_id"],
                    "decision": "TRIGGER",
                    "reason_code": f"RULE:{rule.rule_id}",
                }
            )
        if flush_at is not None:
            close(flush_at)
        return ReplayResult(profile.profile_version, tuple(decisions), tuple(triggers))

    def compare(
        self,
        profile_a: AttentionProfile,
        profile_b: AttentionProfile,
        events: list[dict[str, Any]],
        *,
        flush_at: datetime,
    ) -> dict[str, Any]:
        result_a = self.evaluate(profile_a, events, flush_at=flush_at)
        result_b = self.evaluate(profile_b, events, flush_at=flush_at)
        guaranteed = {
            str(event["event_id"]) for event in events if _is_guaranteed(profile_a, event)
        }
        guaranteed_a = {
            event_id
            for trigger in result_a.triggers
            for event_id in trigger.source_event_ids
            if event_id in guaranteed
        }
        guaranteed_b = {
            event_id
            for trigger in result_b.triggers
            for event_id in trigger.source_event_ids
            if event_id in guaranteed
        }
        reasons_a: dict[str, int] = {}
        reasons_b: dict[str, int] = {}
        for decision in result_a.decisions:
            reasons_a[str(decision["reason_code"])] = (
                reasons_a.get(str(decision["reason_code"]), 0) + 1
            )
        for decision in result_b.decisions:
            reasons_b[str(decision["reason_code"])] = (
                reasons_b.get(str(decision["reason_code"]), 0) + 1
            )
        return {
            "profile_a": profile_a.profile_version,
            "profile_b": profile_b.profile_version,
            "trigger_count_a": len(result_a.triggers),
            "trigger_count_b": len(result_b.triggers),
            "trigger_count_change": len(result_b.triggers) - len(result_a.triggers),
            "guaranteed_lost_a": sorted(guaranteed - guaranteed_a),
            "guaranteed_lost_b": sorted(guaranteed - guaranteed_b),
            "suppression_reasons_a": reasons_a,
            "suppression_reasons_b": reasons_b,
        }
