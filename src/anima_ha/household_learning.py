"""Bounded household initiative preferences and reviewable inferred suggestions.

Core supplies allowlisted, household-validated Journal projections, never a raw
vault or provider payload. This module cannot execute suggestions or notify.
MemoryService retains versions/audit; TaskService owns durable scheduling. A
scheduled task is not evidence of a completed SENTRY review.
"""

from __future__ import annotations

import hashlib
import json
import math
import re
from collections import Counter
from collections.abc import Callable, Iterable, Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import asdict, dataclass, replace
from datetime import UTC, datetime, timedelta
from typing import Any, cast
from uuid import UUID, uuid5
from zoneinfo import ZoneInfo

from psycopg.errors import UniqueViolation

from anima_ha.attention import SentryEventPath, compatible_sentry_path
from anima_ha.household_patterns import (
    ROUTINE_EVIDENCE_THRESHOLD,
    candidate_digest,
    evidence_score,
    extract_pattern_candidates,
)
from anima_ha.knowledge import KnowledgeValidationError
from anima_ha.memory import (
    MemoryProvenance,
    MemoryRecord,
    MemoryStatus,
    MemoryType,
    ProvenanceKind,
)
from anima_ha.plugins import (
    CORE_VERSION,
    MANIFEST_VERSION,
    ExternalContentTrust,
    Idempotency,
    InvocationContext,
    PluginManifest,
    PluginValidationError,
    RuntimeKind,
    TrustClass,
    validate_instance,
)
from anima_ha.policy import RequestOrigin
from anima_ha.preferences import _household, _member
from anima_ha.tasks import MisfirePolicy, ScheduleKind, TaskSchedule, TaskStatus, TaskType

NAMESPACE = UUID("d65d3386-54ae-4294-8d7b-fabcc1428438")
CONFIG_KIND = "household_initiative_config"
MODE_KIND = "household_declared_mode"
INCIDENT_KIND = "household_incident_assessment"
SUGGESTION_KIND = "household_learning_suggestion"
REVIEW_PACKET_KIND = "household_learning_review_packet"
REVIEW_COMPLETION_KIND = "household_learning_review_completion"
SHADOW_KIND = "household_learning_shadow"
MAX_EVIDENCE = 2000
EVIDENCE_WINDOW_DAYS = 28
# Knowledge notes have a deliberately small filesystem/API body limit. Keep
# the durable Memory record lossless within its existing proposal bounds, but
# make the Obsidian projection deterministic and bounded for every valid
# review explanation.
KNOWLEDGE_NOTE_RATIONALE_CHARS = 800
KNOWLEDGE_NOTE_MISSING_ITEM_CHARS = 120
EVENT_TYPES = (
    "senseguard.opened",
    "senseguard.event",
    "household.presence.connection_changed",
    "household.ring.motion",
    "household.ring.doorbell",
)
LEARNING_EVENT_TYPES = (
    *EVENT_TYPES,
    "external.android.lock_reported",
    "external.android.motion_reported",
)
DEVICE_NOTIFICATION_MODES = ("ALWAYS", "TIME_WINDOW", "NEVER", "CONTEXTUAL")
DEVICE_EVENT_KINDS = ("ANY", "UNLOCKED", "LOCKED", "OPENED", "CLOSED", "MOTION", "DOORBELL")
_REQUEST_SCOPE: ContextVar[tuple[UUID, UUID, frozenset[str], dict[str, dict[str, Any]]] | None] = (
    ContextVar("household_learning_request", default=None)
)


class HouseholdLearningError(ValueError):
    """Invalid scope, version, evidence or initiative input."""

    def safe_code(self) -> str:
        """Return only a fixed diagnostic category for provider evidence."""
        value = self.args[0] if self.args else None
        if isinstance(value, str) and re.fullmatch(r"KNOWLEDGE_SYNC_KNOWLEDGE_[A-Z0-9_]+", value):
            return value
        if isinstance(value, str) and re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9 ._-]{1,95}", value):
            return "HOUSEHOLD_LEARNING_" + re.sub(r"[^A-Za-z0-9]+", "_", value).upper().strip("_")
        return "HOUSEHOLD_LEARNING_ERROR"


def _uuid(value: Any) -> UUID:
    try:
        result = UUID(str(value))
        if result.int == 0:
            raise ValueError
        return result
    except (ValueError, TypeError, AttributeError):
        raise HouseholdLearningError("nonzero canonical UUID required") from None


def _time(value: Any) -> datetime:
    try:
        result = value if isinstance(value, datetime) else datetime.fromisoformat(value)
        if result.tzinfo is None or result.utcoffset() is None:
            raise ValueError
        return result.astimezone(UTC)
    except (ValueError, TypeError, AttributeError):
        raise HouseholdLearningError("aware timestamp required") from None


def _text(value: Any, maximum: int) -> str:
    if not isinstance(value, str) or not value.strip() or len(value) > maximum:
        raise HouseholdLearningError("text missing or exceeds bound")
    if any(ord(char) < 32 and char not in "\n\t" for char in value):
        raise HouseholdLearningError("control characters forbidden")
    return value.strip()


def _bounded_note_text(value: str, maximum: int, byte_limit: int) -> str:
    """Fit a non-empty review field into the human-readable note projection."""
    marker = "\n[bounded for Obsidian projection]"
    truncated = len(value) > maximum
    value = value[:maximum]
    if len(value.encode("utf-8")) > byte_limit:
        truncated = True
        remaining = byte_limit - len(marker.encode("utf-8"))
        while len(value.encode("utf-8")) > remaining:
            value = value[:-1]
    return value + marker if truncated else value


def _bounded_note_missing(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [
        _bounded_note_text(item, KNOWLEDGE_NOTE_MISSING_ITEM_CHARS, 120)
        for item in value[:8]
        if isinstance(item, str) and item.strip()
    ]


@contextmanager
def learning_request_scope(
    request_id: UUID,
    household_id: UUID,
    allowed_event_ids: Iterable[str],
    candidates: Iterable[dict[str, Any]] = (),
) -> Iterator[None]:
    """Core-only active/frozen request scope, never a model tool parameter.

    Core must collect allowed IDs from the qualified Journal reader and bind
    them only around the exact native proposal invocation. Scope is restored
    on exceptions and isolated between concurrent execution contexts.
    """
    allowed: set[str] = set()
    for index, value in enumerate(allowed_event_ids):
        if index >= MAX_EVIDENCE + 1:
            raise HouseholdLearningError("request evidence exceeds bound")
        allowed.add(str(_uuid(value)))
    candidate_map: dict[str, dict[str, Any]] = {}
    for index, candidate in enumerate(candidates):
        if index >= 6 or not isinstance(candidate, dict):
            raise HouseholdLearningError("request candidates exceed bound")
        candidate_id = str(_uuid(candidate.get("candidate_id")))
        refs = candidate.get("source_event_ids")
        if not isinstance(refs, list) or not refs or not set(map(str, refs)) <= allowed:
            raise HouseholdLearningError("candidate evidence scope mismatch")
        candidate_map[candidate_id] = dict(candidate)
    token = _REQUEST_SCOPE.set(
        (_uuid(request_id), _uuid(household_id), frozenset(allowed), candidate_map)
    )
    try:
        yield
    finally:
        _REQUEST_SCOPE.reset(token)


@dataclass(frozen=True, slots=True)
class DeviceNotificationRule:
    """Owner-selected notification behavior for one canonical household resource."""

    resource_id: str
    mode: str = "CONTEXTUAL"
    start_local: str = "00:00"
    end_local: str = "23:59"
    timezone: str = "America/New_York"
    event_kind: str = "ANY"
    sentry_path: SentryEventPath | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "resource_id", str(_uuid(self.resource_id)))
        if self.mode not in DEVICE_NOTIFICATION_MODES:
            raise HouseholdLearningError("unsupported device notification mode")
        if self.event_kind not in DEVICE_EVENT_KINDS:
            raise HouseholdLearningError("unsupported device notification event kind")
        if self.sentry_path is not None:
            try:
                path = SentryEventPath(self.sentry_path)
            except (TypeError, ValueError):
                raise HouseholdLearningError("unsupported SENTRY event path") from None
            if path == SentryEventPath.AGGREGATED_REASONING:
                raise HouseholdLearningError(
                    "aggregation is selected by the Attention profile, not a device rule"
                )
            object.__setattr__(
                self,
                "sentry_path",
                compatible_sentry_path(path, alert_mode=self.mode),
            )
        for value in (self.start_local, self.end_local):
            try:
                datetime.strptime(value, "%H:%M")
            except (TypeError, ValueError):
                raise HouseholdLearningError("device notification time must be HH:MM") from None
        try:
            ZoneInfo(self.timezone)
        except (KeyError, TypeError, ValueError):
            raise HouseholdLearningError("device notification timezone is invalid") from None

    @classmethod
    def from_payload(cls, value: Any) -> DeviceNotificationRule:
        required = set(cls.__dataclass_fields__) - {"event_kind", "sentry_path"}
        if (
            not isinstance(value, dict)
            or set(value) - set(cls.__dataclass_fields__)
            or not required <= set(value)
        ):
            raise HouseholdLearningError("full device notification rule required")
        if value.get("sentry_path") == SentryEventPath.AGGREGATED_REASONING.value:
            # This value was never a valid device override, but older data may
            # contain it.  Reconcile it to the safe route for the alert mode
            # instead of making the whole household configuration unreadable.
            value = {
                **value,
                "sentry_path": compatible_sentry_path(
                    SentryEventPath.AGGREGATED_REASONING,
                    alert_mode=str(value.get("mode", "")),
                ).value,
            }
        return cls(**value)

    def to_payload(self) -> dict[str, Any]:
        payload = {
            "resource_id": self.resource_id,
            "mode": self.mode,
            "start_local": self.start_local,
            "end_local": self.end_local,
            "timezone": self.timezone,
            "event_kind": self.event_kind,
        }
        if self.sentry_path is not None:
            payload["sentry_path"] = self.sentry_path.value
        return payload


@dataclass(frozen=True, slots=True)
class InitiativeConfig:
    learning_days: int = 3
    routine_review_days: int = 3
    daily_review_enabled: bool = True
    routine_review_enabled: bool = True
    proactive_enabled: bool = False
    always_notify: tuple[str, ...] = ()
    device_notifications: tuple[DeviceNotificationRule, ...] = ()

    def __post_init__(self) -> None:
        for name, minimum in (("learning_days", 3), ("routine_review_days", 2)):
            value = getattr(self, name)
            if type(value) is not int or not minimum <= value <= 14:
                raise HouseholdLearningError(f"{name} must be {minimum}..14")
        for name in ("daily_review_enabled", "routine_review_enabled", "proactive_enabled"):
            if type(getattr(self, name)) is not bool:
                raise HouseholdLearningError(f"{name} must be boolean")
        if (
            not isinstance(self.always_notify, (tuple, list))
            or len(self.always_notify) > len(EVENT_TYPES)
            or any(item not in EVENT_TYPES for item in self.always_notify)
            or len(set(self.always_notify)) != len(self.always_notify)
        ):
            raise HouseholdLearningError("always_notify must be unique registered event types")
        object.__setattr__(self, "always_notify", tuple(sorted(self.always_notify)))
        if (
            not isinstance(self.device_notifications, (tuple, list))
            or len(self.device_notifications) > 128
        ):
            raise HouseholdLearningError("device notification rules exceed bound")
        rules = tuple(
            item
            if isinstance(item, DeviceNotificationRule)
            else DeviceNotificationRule.from_payload(item)
            for item in self.device_notifications
        )
        if len({item.resource_id for item in rules}) != len(rules):
            raise HouseholdLearningError("device notification resources must be unique")
        object.__setattr__(
            self, "device_notifications", tuple(sorted(rules, key=lambda item: item.resource_id))
        )

    def to_payload(self) -> dict[str, Any]:
        return {
            **asdict(self),
            "always_notify": list(self.always_notify),
            "device_notifications": [item.to_payload() for item in self.device_notifications],
        }

    @classmethod
    def from_payload(cls, value: dict[str, Any]) -> InitiativeConfig:
        if not isinstance(value, dict) or set(value) - {"device_notifications"} != (
            set(cls.__dataclass_fields__) - {"device_notifications"}
        ):
            raise HouseholdLearningError("full exact initiative config required")
        return cls(**({"device_notifications": [], **value}))


class HouseholdLearningService:
    """Core-only facade; the native adapter requires authenticated invocation context.

    evidence_reader(hh, *, since, limit) must reload *only* server-allowlisted
    same-household Journal rows and return {items, truncated}. Items contain
    event_id/event_type/occurred_at/recorded_at/canonical_id and optionally
    source_event_id (for wrapper dedup). No model-provided evidence is accepted.
    request_evidence_reader(hh, request_id) returns IDs Core exposed to that
    active bound request. Missing either dependency fails closed for proposals.
    """

    def __init__(
        self,
        memory_service: Any,
        graph: Any,
        journal: Any = None,
        *,
        evidence_reader: Callable[..., dict[str, Any]] | None = None,
        evidence_read: Callable[..., dict[str, Any]] | None = None,
        request_evidence_reader: Callable[[UUID, UUID], Iterable[str]] | None = None,
        task_service: Any = None,
        knowledge_plugin: Any = None,
        timezone: str = "UTC",
        clock: Callable[[], datetime] | None = None,
        situation_reader: Callable[[UUID], dict[str, Any]] | None = None,
        request_state_reader: Callable[[UUID, UUID], dict[str, Any]] | None = None,
        coverage_reader: Callable[..., dict[str, Any]] | None = None,
    ) -> None:
        self.memory, self.graph, self.journal = memory_service, graph, journal
        if evidence_reader is not None and evidence_read is not None:
            raise HouseholdLearningError("configure only one evidence reader")
        self.evidence_reader = evidence_reader or evidence_read
        self.request_evidence_reader = request_evidence_reader
        self.task_service = task_service
        self.knowledge_plugin = knowledge_plugin
        self.zone = ZoneInfo(timezone)
        self.clock = clock or (lambda: datetime.now(UTC))
        self.situation_reader = situation_reader
        self.request_state_reader = request_state_reader
        self.coverage_reader = coverage_reader

    def _now(self) -> datetime:
        return _time(self.clock())

    def _owner(self, household_id: UUID, principal_id: UUID | None) -> None:
        if principal_id is None:
            raise HouseholdLearningError("commissioned owner required")
        person = _member(self.graph, household_id, principal_id)
        if person.metadata.get("semantic_role") != "owner":
            raise HouseholdLearningError("commissioned owner required")

    def _records(
        self, household_id: UUID, kind: str, *, limit: int, cursor: UUID | None = None
    ) -> list[MemoryRecord]:
        _household(self.graph, household_id)
        where, params = self.memory._rows_for_filters(
            household_id=household_id,
            subject_id=None,
            memory_types=None,
            graph_ref=None,
            now=self._now(),
        )
        anchor = self.memory.get(cursor) if cursor is not None else None
        if cursor is not None and (
            anchor is None
            or anchor.household_id != household_id
            or anchor.metadata.get("record_kind") != kind
        ):
            raise HouseholdLearningError("invalid household learning cursor")
        params.update(
            kind=kind, after=cursor, after_time=anchor.created_at if anchor else None, limit=limit
        )
        with self.memory._connect() as connection, connection.cursor() as sql:
            sql.execute(
                f"""SELECT m.* FROM anima_memory_records m WHERE {where}
                AND m.metadata->>'record_kind' = %(kind)s
                AND (%(after)s::uuid IS NULL OR
                    (m.created_at,m.memory_id) > (%(after_time)s::timestamptz,%(after)s::uuid))
                ORDER BY m.created_at ASC,m.memory_id ASC LIMIT %(limit)s""",
                params,
            )
            return [self.memory._memory(row) for row in sql.fetchall()]

    def _all_records(self, household_id: UUID, kind: str) -> list[MemoryRecord]:
        """Bounded keyset traversal; never silently report a first page as a total."""
        result: list[MemoryRecord] = []
        cursor = None
        for _ in range(64):
            page = self._records(household_id, kind, limit=256, cursor=cursor)
            result.extend(page)
            if len(page) < 256:
                return result
            cursor = page[-1].memory_id
        raise HouseholdLearningError("learning enumeration exceeds bound; continuation required")

    def review_state(
        self,
        household_id: UUID,
        packet: dict[str, Any],
        *,
        outcomes: list[MemoryRecord] | None = None,
        previous: MemoryRecord | None = None,
    ) -> dict[str, Any]:
        state = (
            self.request_state_reader(household_id, _uuid(packet["request_id"]))
            if self.request_state_reader
            else {}
        )
        lifecycle = state.get("lifecycle", "NOT_CONFIGURED")
        if outcomes is None:
            outcomes = [
                row
                for row in self._all_records(household_id, SUGGESTION_KIND)
                if row.metadata.get("review_id") == packet["review_id"]
            ]
        required = {item["candidate_id"] for item in packet["candidates"]}
        materialized = {row.metadata.get("candidate_id") for row in outcomes}
        if previous is None:
            previous = next(
                (
                    row
                    for row in self._all_records(household_id, REVIEW_COMPLETION_KIND)
                    if row.metadata.get("review_id") == packet["review_id"]
                ),
                None,
            )
        complete = required == materialized
        # Old completion records retain their bounded materialization receipt
        # after a later candidate version supersedes the original suggestions.
        if previous and previous.metadata.get("candidate_digest") == packet["candidate_digest"]:
            complete |= previous.metadata.get("outcome_count") == len(required)
        successful = (
            lifecycle in {"COMPLETED", "NO_ACTION"}
            and state.get("result_status") in {"RESPONSE", "NO_ACTION", "TOOL_ACTIVITY_COMPLETED"}
            and state.get("provider_invocation_started") is True
            and complete
        )
        return {
            "schema_version": 2,
            "lifecycle": lifecycle,
            "terminal_at": state.get("completed_at"),
            "provider_started": state.get("provider_invocation_started") is True,
            "candidate_materialized": complete,
            "terminal_success": successful,
            "review_status": "COMPLETED"
            if successful
            else "INCOMPLETE"
            if lifecycle in {"COMPLETED", "NO_ACTION"}
            else lifecycle,
            "projection_status": "FAILED"
            if any(row.metadata.get("projection_status") == "FAILED" for row in outcomes)
            else "PENDING"
            if any(row.metadata.get("projection_status") == "PENDING" for row in outcomes)
            else "SYNCHRONIZED"
            if outcomes and all(row.metadata.get("knowledge_note") for row in outcomes)
            else "NOT_CONFIGURED",
        }

    def reconcile_reviews(self, household_id: UUID) -> None:
        """Reconcile durable outcomes, not provider requests; never invoke/replay a model."""
        suggestions = self._all_records(household_id, SUGGESTION_KIND)
        completions = self._all_records(household_id, REVIEW_COMPLETION_KIND)
        for row in self._all_records(household_id, REVIEW_PACKET_KIND):
            packet = dict(row.metadata["packet"])
            outcomes = [
                item
                for item in suggestions
                if item.metadata.get("review_id") == packet["review_id"]
            ]
            previous = next(
                (
                    item
                    for item in completions
                    if item.metadata.get("review_id") == packet["review_id"]
                ),
                None,
            )
            self._complete_review(household_id, packet, outcomes=outcomes, previous=previous)
        # Notes are projections of already qualified Memory, never provider
        # work. Bounded retries cannot replay a model or a household action.
        attempted = 0
        for row in self._all_records(household_id, SUGGESTION_KIND):
            request_value = row.metadata.get("request_id") or (
                row.provenance.source_ref.removeprefix("anima:request:")
                if row.provenance.source_ref.startswith("anima:request:")
                else None
            )
            if row.metadata.get("knowledge_note") and request_value and self.request_state_reader:
                state = self.request_state_reader(household_id, _uuid(request_value))
                if (
                    state.get("lifecycle")
                    in {
                        "FAILED",
                        "UNKNOWN_RESULT",
                        "RECOVERY_REQUIRED",
                        "CANCELLED",
                    }
                    and not row.metadata.get("projection_quarantined")
                    and not (
                        row.provenance.kind == ProvenanceKind.EXPLICIT_INPUT
                        and row.metadata.get("conclusion") == "OWNER_CORRECTION"
                    )
                ):
                    updated = {
                        **row.metadata,
                        "projection_quarantined": True,
                        "projection_status": "PENDING",
                        "request_id": request_value,
                        "projection_retry_at": None,
                    }
                    # Historical notes retain their receipt; disabling them is a
                    # versioned projection correction, not a provider replay.
                    candidate = updated.get("projection_candidate") or {
                        "candidate_key": updated.get("candidate_key", str(row.memory_id)),
                        "title": updated.get("candidate_title", "Historical learning record"),
                        "maturity_evidence": updated.get("maturity_evidence", {}),
                    }
                    updated["projection_candidate"] = candidate
                    row = self.memory.correct(
                        row.memory_id,
                        replace(
                            row,
                            memory_id=uuid5(NAMESPACE, f"quarantine:{row.memory_id}"),
                            created_at=self._now(),
                            metadata=updated,
                            supersedes_memory_id=None,
                        ),
                    )
            retry = row.metadata.get("projection_retry_at")
            if (
                attempted < 256
                and row.metadata.get("projection_status") in {"PENDING", "FAILED"}
                and (not retry or _time(retry) <= self._now())
            ):
                synced = self._sync_projection(row)
                attempted += synced.memory_id != row.memory_id
        self.evaluate_shadows(household_id)

    def _config(self, household_id: UUID) -> tuple[InitiativeConfig, MemoryRecord | None]:
        rows = self._records(household_id, CONFIG_KIND, limit=2)
        if len(rows) > 1:
            raise HouseholdLearningError("multiple active initiative configs; reconcile required")
        if not rows:
            return InitiativeConfig(), None
        row = rows[0]
        if (
            row.memory_type != MemoryType.EXPLICIT_PREFERENCE
            or row.provenance.kind != ProvenanceKind.EXPLICIT_INPUT
            or row.subject_id is not None
        ):
            raise HouseholdLearningError(
                "initiative config is not an explicit household preference"
            )
        return InitiativeConfig.from_payload(row.metadata["config"]), row

    def declared_mode(self, household_id: UUID) -> dict[str, Any]:
        rows = self._records(household_id, MODE_KIND, limit=2)
        if len(rows) > 1:
            raise HouseholdLearningError("multiple household mode versions")
        row = rows[0] if rows else None
        if row is not None and (
            row.memory_type != MemoryType.EXPLICIT_FACT
            or row.provenance.kind != ProvenanceKind.EXPLICIT_INPUT
            or row.metadata.get("mode") not in {"HOME", "AWAY", "UNSET"}
        ):
            raise HouseholdLearningError("invalid declared household mode provenance")
        return {
            "mode": row.metadata["mode"] if row else "UNSET",
            "version": str(row.memory_id) if row else None,
            "declared_at": row.created_at.isoformat() if row else None,
            "source": row.provenance.source_ref if row else None,
            "classification": "OWNER_DECLARED_NOT_OCCUPANCY",
            "authority": "NONE",
        }

    def set_household_mode(
        self, household_id: UUID, principal_id: UUID, payload: dict[str, Any]
    ) -> dict[str, Any]:
        self._owner(household_id, principal_id)
        if set(payload) != {"mode", "expected_version"} or payload["mode"] not in {
            "HOME",
            "AWAY",
            "UNSET",
        }:
            raise HouseholdLearningError("exact declared household mode required")
        current = self.declared_mode(household_id)
        if payload["expected_version"] != current["version"]:
            raise HouseholdLearningError("household mode version changed; reload")
        if current["version"] and payload["mode"] == current["mode"]:
            return {"status": "SUCCEEDED", "declared_mode": current}
        previous = UUID(current["version"]) if current["version"] else None
        record = MemoryRecord.create(
            memory_id=uuid5(NAMESPACE, f"mode:{household_id}:{previous or 'initial'}"),
            household_id=household_id,
            memory_type=MemoryType.EXPLICIT_FACT,
            content=f"Owner-declared household mode: {payload['mode']}",
            provenance=MemoryProvenance(
                ProvenanceKind.EXPLICIT_INPUT, f"anima:principal:{principal_id}"
            ),
            created_at=self._now(),
            confidence=1.0,
            metadata={"record_kind": MODE_KIND, "mode": payload["mode"]},
        )
        try:
            if previous:
                self.memory.correct(previous, record)
            else:
                self.memory.create(record)
        except UniqueViolation:
            raise HouseholdLearningError("household mode version changed; reload") from None
        return {"status": "SUCCEEDED", "declared_mode": self.declared_mode(household_id)}

    def get_situation(self, household_id: UUID) -> dict[str, Any]:
        _household(self.graph, household_id)
        packet = (
            self.situation_reader(household_id)
            if self.situation_reader
            else {"status": "UNAVAILABLE", "coverage": "CONTEXT_READER_UNAVAILABLE"}
        )
        return {**packet, "declared_mode": self.declared_mode(household_id), "authority": "NONE"}

    def record_incident_assessment(
        self, household_id: UUID, payload: dict[str, Any], request_id: UUID
    ) -> dict[str, Any]:
        scope = _REQUEST_SCOPE.get()
        if scope is None or scope[:2] != (request_id, household_id):
            raise HouseholdLearningError("active incident request scope required")
        if set(payload) != {"event_ids", "assessment", "unknowns"}:
            raise HouseholdLearningError("exact incident assessment fields required")
        ids = payload["event_ids"]
        if (
            not isinstance(ids, list)
            or not 1 <= len(ids) <= 12
            or not all(isinstance(item, str) for item in ids)
            or len(set(ids)) != len(ids)
            or not set(ids) <= scope[2]
        ):
            raise HouseholdLearningError("incident evidence not bound to current request")
        text = _text(payload["assessment"], 1000)
        unknowns = payload["unknowns"]
        if not isinstance(unknowns, list) or len(unknowns) > 8:
            raise HouseholdLearningError("bounded incident unknowns required")
        unknowns = [_text(item, 240) for item in unknowns]
        version = uuid5(NAMESPACE, f"incident:{household_id}:{request_id}")
        existing = self.memory.get(version)
        if existing is not None:
            if (
                existing.household_id != household_id
                or existing.metadata.get("record_kind") != INCIDENT_KIND
                or existing.metadata.get("assessment") != text
                or existing.metadata.get("unknowns") != unknowns
                or {item["event_id"] for item in existing.metadata.get("source_refs", [])}
                != set(ids)
            ):
                raise HouseholdLearningError("incident already recorded; no overwrite")
            # Idempotent return is the original immutable assessment, not a
            # fresh coverage/mode claim or a second model/action execution.
            return {
                "status": "SUCCEEDED",
                "incident_id": str(version),
                **existing.metadata,
                "authority": "NONE",
            }
        current = self.get_situation(household_id)
        observations = current.get("observations", {}).get("items", [])
        refs = [item for item in observations if item["event_id"] in ids]
        if {item["event_id"] for item in refs} != set(ids):
            raise HouseholdLearningError("incident source freshness/qualification changed")
        refs = [
            {
                key: item[key]
                for key in (
                    "event_id",
                    "event_type",
                    "canonical_id",
                    "source_event_id",
                    "occurred_at",
                    "recorded_at",
                    "time_basis",
                    "physical_occurred_at",
                    "event_kind",
                    "transition",
                    "source_occurred_at",
                    "android_posted_at",
                    "relay_received_at",
                    "identity_verified",
                    "source_family",
                    "independence",
                )
                if key in item
            }
            for item in refs
        ]
        coverage = current.get("source_coverage", {})
        # Memory deliberately forbids authority/permission metadata even when
        # marked NONE. Persist only bounded source-state facts, not a copied
        # rich packet or nested grants/credentials.
        source_coverage = {
            name: {
                key: value
                for key, value in state.items()
                if key in {"status", "reason", "coverage", "subscriptions_active"}
                and (isinstance(value, bool) or isinstance(value, str) and len(value) <= 128)
            }
            for name, state in coverage.items()
            if name in {"ha_bound_consumer", "android", "presence", "handoff"}
            and isinstance(state, dict)
        }
        metadata = {
            "record_kind": INCIDENT_KIND,
            "request_id": str(request_id),
            "assessment": text,
            "unknowns": unknowns,
            "source_refs": refs,
            "declared_mode": {
                key: value
                for key, value in current["declared_mode"].items()
                if key in {"mode", "version", "declared_at", "source", "classification"}
            },
            "source_coverage": source_coverage,
            "classification": "SENTRY_INFERRED_ASSESSMENT",
            "disposition": "UNVERIFIED_NO_ACTION_AUTHORITY",
        }
        try:
            self.memory.create(
                MemoryRecord.create(
                    memory_id=version,
                    household_id=household_id,
                    memory_type=MemoryType.TEMPORARY_EPISODIC,
                    content=text,
                    provenance=MemoryProvenance(
                        ProvenanceKind.EVENT_JOURNAL, f"anima:request:{request_id}", ids[0]
                    ),
                    created_at=self._now(),
                    expires_at=self._now() + timedelta(days=7),
                    confidence=0.5,
                    metadata=metadata,
                )
            )
        except UniqueViolation:
            return self.record_incident_assessment(household_id, payload, request_id)
        return {"status": "SUCCEEDED", "incident_id": str(version), **metadata, "authority": "NONE"}

    def configure(
        self, household_id: UUID, principal_id: UUID, payload: dict[str, Any]
    ) -> dict[str, Any]:
        self._owner(household_id, principal_id)
        if "expected_version" not in payload:
            raise HouseholdLearningError("expected_version required; null for initial save")
        config = InitiativeConfig.from_payload(
            {key: value for key, value in payload.items() if key != "expected_version"}
        )
        expected = _uuid(payload["expected_version"]) if payload["expected_version"] else None
        if payload["expected_version"] is not None and expected is None:
            raise HouseholdLearningError("expected_version must be UUID or null")
        current, original = self._config(household_id)
        if (original.memory_id if original else None) != expected:
            raise HouseholdLearningError("config version changed; reload")
        if original and config == current:
            return self.status(household_id)
        config_json = json.dumps(config.to_payload(), sort_keys=True)
        # A deterministic initial PK prevents two concurrent first writers from
        # creating two active configs. Later corrections lock the old version.
        version = uuid5(NAMESPACE, f"config:{household_id}:{expected or 'initial'}")
        memory = MemoryRecord.create(
            memory_id=version,
            household_id=household_id,
            memory_type=MemoryType.EXPLICIT_PREFERENCE,
            content=config_json,
            provenance=MemoryProvenance(
                ProvenanceKind.EXPLICIT_INPUT, f"anima:principal:{principal_id}"
            ),
            created_at=self._now(),
            confidence=1.0,
            metadata={
                "record_kind": CONFIG_KIND,
                "scope": "initiative",
                "config": config.to_payload(),
            },
        )
        try:
            if original:
                self.memory.correct(original.memory_id, memory)
            else:
                self.memory.create(memory)
        except UniqueViolation:
            raise HouseholdLearningError("config version changed; reload") from None
        return self.status(household_id)

    def set_device_notification(
        self, household_id: UUID, principal_id: UUID, payload: dict[str, Any]
    ) -> dict[str, Any]:
        """Change one bounded device/event rule without replacing unrelated owner settings."""

        self._owner(household_id, principal_id)
        current, original = self._config(household_id)
        expected = str(original.memory_id) if original else None
        if payload.get("expected_version") != expected:
            raise HouseholdLearningError("config version changed; reload")
        resource_id = str(_uuid(payload.get("resource_id")))
        mode = str(payload.get("mode", ""))
        remaining = [
            item for item in current.device_notifications if item.resource_id != resource_id
        ]
        if mode != "DEFAULT":
            remaining.append(
                DeviceNotificationRule(
                    resource_id=resource_id,
                    mode=mode,
                    start_local=str(payload.get("start_local", "00:00")),
                    end_local=str(payload.get("end_local", "23:59")),
                    timezone=str(payload.get("timezone", self.zone.key)),
                    event_kind=str(payload.get("event_kind", "ANY")),
                    sentry_path=(
                        SentryEventPath(str(payload["sentry_path"]))
                        if payload.get("sentry_path") is not None
                        else None
                    ),
                )
            )
        updated = replace(current, device_notifications=tuple(remaining))
        return self.configure(
            household_id,
            principal_id,
            {**updated.to_payload(), "expected_version": expected},
        )

    def evidence(self, household_id: UUID, limit: int = 50) -> dict[str, Any]:
        _household(self.graph, household_id)
        if type(limit) is not int or not 1 <= limit <= MAX_EVIDENCE:
            raise HouseholdLearningError("evidence limit must be 1..2000")
        if self.evidence_reader is None:
            return {"status": "UNAVAILABLE", "items": [], "truncated": False, "authority": "NONE"}
        now = self._now()
        since = now - timedelta(days=EVIDENCE_WINDOW_DAYS)
        try:
            page = self.evidence_reader(household_id, since=since, limit=limit)
        except Exception:
            return {
                "status": "UNAVAILABLE",
                "items": [],
                "truncated": False,
                "reason": "EVIDENCE_READ_FAILED",
                "authority": "NONE",
            }
        if not isinstance(page, dict) or not isinstance(page.get("items"), list):
            raise HouseholdLearningError("invalid trusted evidence projection")
        if page.get("status") != "SUCCEEDED":
            return {"status": "UNAVAILABLE", "items": [], "truncated": False, "authority": "NONE"}
        items: list[dict[str, Any]] = []
        seen: set[str] = set()
        for row in page["items"][:limit]:
            # Household membership/source qualification belongs to Core's
            # reader. Re-project defensively; never return extra keys/raw data.
            occurred, recorded = _time(row["occurred_at"]), _time(row["recorded_at"])
            if not since <= occurred <= recorded <= now or not since <= recorded:
                continue
            if row["event_type"] not in LEARNING_EVENT_TYPES:
                continue
            event_id = str(_uuid(row["event_id"]))
            source_id = (
                _text(row["source_event_id"], 256) if row.get("source_event_id") else event_id
            )
            if event_id in seen or source_id in seen:
                continue
            seen.update((event_id, source_id))
            items.append(
                {
                    "event_id": event_id,
                    "event_type": row["event_type"],
                    "occurred_at": occurred.isoformat(),
                    "recorded_at": recorded.isoformat(),
                    "canonical_id": str(_uuid(row["canonical_id"])),
                    **(
                        {"event_kind": _text(row["event_kind"], 32)}
                        if row.get("event_kind")
                        else {}
                    ),
                    **(
                        {"transition": _text(row["transition"], 32)}
                        if row.get("transition")
                        else {}
                    ),
                }
            )
        return {
            "status": "SUCCEEDED",
            "items": items,
            "truncated": bool(page.get("truncated")) or len(page["items"]) > limit,
            "authority": "NONE",
        }

    def _readiness(self, config: InitiativeConfig, page: dict[str, Any]) -> dict[str, Any]:
        times = [_time(row["occurred_at"]) for row in page["items"]]
        receipts = [_time(row["recorded_at"]) for row in page["items"]]
        days = len({value.astimezone(self.zone).date() for value in times})
        received_days = len({value.astimezone(self.zone).date() for value in receipts})
        first, last = (min(times), max(times)) if times else (None, None)
        elapsed = (last - first).total_seconds() if first and last else 0.0
        received_elapsed = (max(receipts) - min(receipts)).total_seconds() if receipts else 0.0
        required = config.learning_days * 86400
        return {
            "ready": page["status"] == "SUCCEEDED"
            and days >= config.learning_days
            and elapsed >= required
            and received_days >= config.learning_days
            and received_elapsed >= required,
            "observed_local_days": days,
            "required_days": config.learning_days,
            "first_observed_at": first.isoformat() if first else None,
            "last_observed_at": last.isoformat() if last else None,
            "elapsed_seconds": elapsed,
            "received_local_days": received_days,
            "received_elapsed_seconds": received_elapsed,
            "required_elapsed_seconds": required,
            "evidence_status": page["status"],
            "truncated": page["truncated"],
            "window_days": EVIDENCE_WINDOW_DAYS,
            "coverage": "BOUNDED_OBSERVATIONS_NOT_COMPLETE_HOUSEHOLD_HISTORY",
        }

    def status(self, household_id: UUID, *, include_learning: bool = True) -> dict[str, Any]:
        config, row = self._config(household_id)
        evidence = self.evidence(household_id, MAX_EVIDENCE)
        readiness = self._readiness(config, evidence)
        candidates = extract_pattern_candidates(
            evidence["items"], household_id=household_id, timezone=self.zone
        )
        completions = (
            self._all_records(household_id, REVIEW_COMPLETION_KIND) if include_learning else []
        )
        packets = self._all_records(household_id, REVIEW_PACKET_KIND) if include_learning else []
        suggestions = self._all_records(household_id, SUGGESTION_KIND) if include_learning else []
        states = [
            self.review_state(
                household_id,
                dict(item.metadata["packet"]),
                outcomes=[
                    row
                    for row in suggestions
                    if row.metadata.get("review_id") == item.metadata["packet"]["review_id"]
                ],
                previous=next(
                    (
                        row
                        for row in completions
                        if row.metadata.get("review_id") == item.metadata["packet"]["review_id"]
                    ),
                    None,
                ),
            )
            for item in packets
        ]
        successful_ids = {
            item.metadata["packet"]["review_id"]
            for item, state in zip(packets, states, strict=True)
            if state["terminal_success"]
        }
        successful = sorted(
            (item for item in completions if item.metadata.get("review_id") in successful_ids),
            key=lambda item: (
                _time(item.metadata["terminal_at"])
                if item.metadata.get("terminal_at")
                else item.created_at,
                str(item.memory_id),
            ),
        )
        learned_routines = [
            routine for row in suggestions if (routine := self._learned_routine(row)) is not None
        ]
        return {
            "status": "SUCCEEDED",
            "config": config.to_payload(),
            "declared_mode": self.declared_mode(household_id),
            "config_version": str(row.memory_id) if row else None,
            "timezone": self.zone.key,
            "readiness": readiness,
            "proactive_eligible": config.proactive_enabled and readiness["ready"],
            "always_notify_types": list(EVENT_TYPES),
            "scheduling": self._scheduling(household_id, config, row),
            "learning": {
                "evidence_events": len(evidence["items"]),
                "candidate_count": len(candidates),
                "candidate_types": sorted({item.candidate_class for item in candidates}),
                "candidates": [item.to_payload() for item in candidates],
                "last_review": self._review_summary(successful[-1]) if successful else None,
                "last_attempt": {**dict(packets[-1].metadata["packet"]), **states[-1]}
                if packets
                else None,
                "review_count": sum(item["terminal_success"] for item in states),
                "failed_review_count": sum(
                    item["review_status"]
                    in {"FAILED", "UNKNOWN_RESULT", "RECOVERY_REQUIRED", "CANCELLED", "INCOMPLETE"}
                    for item in states
                ),
                "pending_review_count": sum(
                    not item["terminal_success"]
                    and item["review_status"]
                    not in {
                        "FAILED",
                        "UNKNOWN_RESULT",
                        "RECOVERY_REQUIRED",
                        "CANCELLED",
                        "INCOMPLETE",
                    }
                    for item in states
                ),
                "packet_count": len(packets),
                "completion_record_count": len(completions),
                "enumeration": "COMPLETE" if include_learning else "NOT_REQUESTED",
                "gaps": self._learning_gaps(evidence, candidates),
                "learned_routines": learned_routines,
                "shadow_evaluations": self.evaluations(household_id)
                if include_learning
                else {"status": "NOT_REQUESTED", "items": []},
            },
            "authority": "NONE",
        }

    @staticmethod
    def _learning_gaps(page: dict[str, Any], candidates: list[Any]) -> list[str]:
        gaps: list[str] = []
        if page.get("truncated"):
            gaps.append("The bounded evidence window is truncated.")
        if not any(item.candidate_class == "EVENT_SEQUENCE" for item in candidates):
            gaps.append("No repeated multi-day event sequence met the bounded candidate threshold.")
        if not any(
            item["event_type"] == "household.presence.connection_changed" for item in page["items"]
        ):
            gaps.append(
                "No qualified presence transitions are available; identity or occupancy "
                "is not inferred."
            )
        return gaps

    @staticmethod
    def _review_summary(row: MemoryRecord) -> dict[str, Any]:
        metadata = row.metadata
        return {
            "review_id": metadata.get("review_id"),
            "review_kind": metadata.get("review_kind"),
            "completed_at": metadata.get("terminal_at") or row.created_at.isoformat(),
            "candidate_count": metadata.get("candidate_count", 0),
            "outcome_count": metadata.get("outcome_count", 0),
            "evidence_start": metadata.get("evidence_start"),
            "evidence_end": metadata.get("evidence_end"),
            "authority": "NONE",
        }

    def create_review_packet(
        self,
        household_id: UUID,
        request_id: UUID,
        *,
        review_kind: str,
        source_event_id: str,
    ) -> dict[str, Any]:
        """Persist the exact deterministic packet bound to one SENTRY request."""
        if review_kind not in {"INITIAL_CATCH_UP", "DAILY", "ROUTINE"}:
            raise HouseholdLearningError("unsupported review kind")
        page = self.evidence(household_id, MAX_EVIDENCE)
        if page["status"] != "SUCCEEDED":
            raise HouseholdLearningError("qualified evidence unavailable")
        candidates = extract_pattern_candidates(
            page["items"], household_id=household_id, timezone=self.zone
        )
        if review_kind == "DAILY":
            completions = self._all_records(household_id, REVIEW_COMPLETION_KIND)
            incorporated: set[str] = set()
            for completion in completions:
                request_value = completion.metadata.get("request_id")
                if not request_value:
                    continue
                packet = self.review_packet(household_id, _uuid(request_value))
                if packet is None:
                    continue
                if not self.review_state(household_id, packet)["terminal_success"]:
                    continue
                incorporated.update(
                    str(event_id)
                    for candidate in packet["candidates"]
                    for event_id in candidate["source_event_ids"]
                )
            # A late-arriving observation may have an older occurred_at than
            # the previous review's newest event. Source identity, not a time
            # watermark, determines whether evidence was incorporated.
            candidates = [
                item for item in candidates if not set(item.source_event_ids) <= incorporated
            ]
        payload = [item.to_payload() for item in candidates]
        review_id = uuid5(NAMESPACE, f"review-packet:{household_id}:{request_id}")
        existing = self.memory.get(review_id)
        digest = candidate_digest(candidates)
        if existing is not None:
            if existing.metadata.get("candidate_digest") != digest:
                raise HouseholdLearningError("review request reused with different evidence")
            return dict(existing.metadata["packet"])
        times = [_time(item["occurred_at"]) for item in page["items"]]
        packet = {
            "review_id": str(review_id),
            "request_id": str(request_id),
            "review_kind": review_kind,
            "evidence_start": min(times).isoformat() if times else None,
            "evidence_end": max(times).isoformat() if times else None,
            "evidence_event_count": len(page["items"]),
            "candidate_digest": digest,
            "candidates": payload,
            "guidance": (
                "Evaluate each candidate from its source-linked evidence. Submit one bounded "
                "household-learning proposal per candidate, including explicit insufficient or "
                "rejected outcomes. Correlation is not identity, causation, policy, or Truth."
            ),
        }
        row = MemoryRecord.create(
            memory_id=review_id,
            household_id=household_id,
            memory_type=MemoryType.TEMPORARY_EPISODIC,
            content=json.dumps(packet, sort_keys=True),
            provenance=MemoryProvenance(
                ProvenanceKind.EVENT_JOURNAL,
                f"anima:request:{request_id}",
                source_event_id,
            ),
            created_at=self._now(),
            confidence=1.0,
            graph_refs=tuple(
                sorted(
                    {_uuid(value) for candidate in payload for value in candidate["canonical_ids"]},
                    key=str,
                )
            ),
            metadata={
                "record_kind": REVIEW_PACKET_KIND,
                "review_id": str(review_id),
                "request_id": str(request_id),
                "review_kind": review_kind,
                "candidate_digest": digest,
                "packet": packet,
            },
        )
        try:
            self.memory.create(row)
        except UniqueViolation:
            saved = self.memory.get(review_id)
            if saved is None or saved.metadata.get("candidate_digest") != digest:
                raise HouseholdLearningError("review packet conflict") from None
        if not candidates:
            self._complete_review(household_id, packet)
        return packet

    def review_packet(self, household_id: UUID, request_id: UUID) -> dict[str, Any] | None:
        row = self.memory.get(uuid5(NAMESPACE, f"review-packet:{household_id}:{request_id}"))
        if (
            row is None
            or row.household_id != household_id
            or row.metadata.get("record_kind") != REVIEW_PACKET_KIND
        ):
            return None
        return dict(row.metadata["packet"])

    def ensure_review_packet(self, request: Any) -> dict[str, Any] | None:
        """Lazily close the enqueue/packet crash window before provider use."""
        existing = self.review_packet(request.household_id, request.request_id)
        if existing is not None:
            return existing
        if request.origin.value not in {"DURABLE_TASK", "AUTONOMOUS_ATTENTION"}:
            return None
        source = next(
            (
                row
                for event_type in (
                    "scheduled_reasoning_due",
                    "household_learning_catch_up_requested",
                )
                for row in self.journal.list_events(event_type=event_type, limit=1000)
                if row["event_id"] == request.causation_id
                and row["metadata"].get("household_id") == str(request.household_id)
            ),
            None,
        )
        if source is None:
            return None
        review_kind = source["payload"].get("review_kind")
        if review_kind is None and source["event_type"] == "scheduled_reasoning_due":
            task_value = source["payload"].get("task_id")
            if self.task_service is None or not task_value:
                return None
            try:
                task = self.task_service.get(_uuid(task_value))
            except (HouseholdLearningError, KeyError):
                return None
            if (
                task.household_id != request.household_id
                or task.metadata.get("created_via") != "household_learning"
                or task.payload.get("config_version") is None
            ):
                return None
            review_kind = task.payload.get("review_kind")
        if review_kind not in {"INITIAL_CATCH_UP", "DAILY", "ROUTINE"}:
            return None
        return self.create_review_packet(
            request.household_id,
            request.request_id,
            review_kind=review_kind,
            source_event_id=source["event_id"],
        )

    def review_task_scope(self, household_id: UUID) -> dict[str, Any]:
        """Read-only worker projection: no observation scan or task creation."""
        config, row = self._config(household_id)
        return {
            "config": config.to_payload(),
            "config_version": str(row.memory_id) if row else None,
            "scheduling": self._scheduling(household_id, config, row),
        }

    @staticmethod
    def _evidence_score_from_metadata(metadata: dict[str, Any]) -> float | None:
        value = metadata.get("evidence_score")
        if isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value):
            return round(max(0.0, min(1.0, float(value))), 3)
        evidence = metadata.get("maturity_evidence")
        if not isinstance(evidence, dict):
            return None
        count, days, elapsed = (
            evidence.get("observation_count"),
            evidence.get("distinct_day_count"),
            evidence.get("elapsed_hours"),
        )
        if not (
            isinstance(count, (int, float))
            and not isinstance(count, bool)
            and math.isfinite(count)
            and isinstance(days, (int, float))
            and not isinstance(days, bool)
            and math.isfinite(days)
            and isinstance(elapsed, (int, float))
            and not isinstance(elapsed, bool)
            and math.isfinite(elapsed)
        ):
            return None
        consistency = 1.0 if metadata.get("candidate_class") == "EVENT_SEQUENCE" else 0.0
        temporal = evidence.get("temporal_consistency")
        if isinstance(temporal, dict) and isinstance(temporal.get("ratio"), (int, float)):
            consistency = float(temporal["ratio"])
        return evidence_score(int(count), int(days), float(elapsed), consistency)

    def _learned_routine(self, row: MemoryRecord) -> dict[str, Any] | None:
        metadata = row.metadata
        if (
            metadata.get("review_status") in {"DISMISSED", "CORRECTED", "RETRACTED"}
            or metadata.get("conclusion") != "LEARNED_ROUTINE_SUGGESTION"
        ):
            return None
        request_value = metadata.get("request_id") or (
            row.provenance.source_ref.removeprefix("anima:request:")
            if row.provenance.source_ref.startswith("anima:request:")
            else None
        )
        packet = (
            self.review_packet(row.household_id, _uuid(request_value)) if request_value else None
        )
        if packet is None or not self.review_state(row.household_id, packet)["terminal_success"]:
            return None
        score = self._evidence_score_from_metadata(metadata)
        if score is None or score < ROUTINE_EVIDENCE_THRESHOLD:
            return None
        candidate_key = metadata.get("candidate_key")
        if not isinstance(candidate_key, str) or not candidate_key:
            return None
        return {
            "routine_id": str(
                uuid5(NAMESPACE, f"learned-routine:{row.household_id}:{candidate_key}")
            ),
            "title": metadata.get("candidate_title", "Learned household pattern"),
            "summary": metadata.get("candidate_factual_summary", row.content),
            "candidate_class": metadata.get("candidate_class"),
            "maturity": metadata.get("maturity", "LEARNED_ROUTINE_ELIGIBLE"),
            "evidence_score": score,
            "evidence_threshold": ROUTINE_EVIDENCE_THRESHOLD,
            "source_suggestion_id": str(row.memory_id),
            "source_refs": metadata.get("source_refs", []),
            "created_at": row.created_at.isoformat(),
            "status": "ACTIVE",
            "classification": "INFERRED_LEARNED_ROUTINE",
            "executable": False,
            "authority": "NONE",
        }

    def _suggestion(self, row: MemoryRecord) -> dict[str, Any]:
        learned_routine = self._learned_routine(row)
        return {
            "suggestion_id": str(row.memory_id),
            "kind": row.metadata["kind"],
            "content": row.content,
            "confidence": row.confidence,
            "evidence_score": self._evidence_score_from_metadata(row.metadata),
            "classification": "OWNER_CORRECTION"
            if row.provenance.kind == ProvenanceKind.EXPLICIT_INPUT
            and row.metadata.get("conclusion") == "OWNER_CORRECTION"
            else "INFERRED",
            "review_status": row.metadata["review_status"],
            "source_refs": row.metadata["source_refs"],
            "created_at": row.created_at.isoformat(),
            "authority": "NONE",
            "evidence_status": "JOURNAL_LINKED_NOT_VERIFIED_TRUTH",
            "conclusion": row.metadata.get("conclusion", "TENTATIVE_HYPOTHESIS"),
            "candidate_id": row.metadata.get("candidate_id"),
            "candidate_class": row.metadata.get("candidate_class"),
            "maturity": row.metadata.get("maturity"),
            "maturity_evidence": row.metadata.get("maturity_evidence", {}),
            "rationale_summary": row.metadata.get("rationale_summary"),
            "missing_information": row.metadata.get("missing_information", []),
            "rejected_alternatives": row.metadata.get("rejected_alternatives", []),
            "knowledge_note": row.metadata.get("knowledge_note"),
            "projection_status": row.metadata.get("projection_status", "NOT_CONFIGURED"),
            "learned_routine": learned_routine,
        }

    def suggestions(
        self, household_id: UUID, limit: int = 20, cursor: str | None = None
    ) -> dict[str, Any]:
        if type(limit) is not int or not 1 <= limit <= 20:
            raise HouseholdLearningError("suggestion limit must be 1..20")
        rows = self._records(
            household_id,
            SUGGESTION_KIND,
            limit=limit + 1,
            cursor=_uuid(cursor) if cursor is not None else None,
        )
        return {
            "status": "SUCCEEDED",
            "items": [self._suggestion(row) for row in rows[:limit]],
            "next_cursor": str(rows[limit - 1].memory_id) if len(rows) > limit else None,
        }

    def propose(
        self,
        household_id: UUID,
        principal_id: UUID | None,
        payload: dict[str, Any],
        request_id: UUID,
        *,
        invocation_id: UUID | None = None,
        invocation_context: InvocationContext | None = None,
    ) -> dict[str, Any]:
        del principal_id  # Never convert a model suggestion into owner provenance.
        legacy_fields = {"kind", "content", "confidence", "event_ids"}
        review_fields = {
            "candidate_id",
            "conclusion",
            "rationale_summary",
            "evidence_categories",
            "missing_information",
            "rejected_alternatives",
        }
        if set(payload) - legacy_fields - review_fields or not legacy_fields <= set(payload):
            raise HouseholdLearningError("exact suggestion fields required")
        structured = "candidate_id" in payload
        if not structured and set(payload) != legacy_fields:
            raise HouseholdLearningError("candidate review fields must be complete")
        kind, confidence = payload["kind"], payload["confidence"]
        if kind not in {"PATTERN", "WORKFLOW", "LESSON"}:
            raise HouseholdLearningError("unsupported suggestion kind")
        if (
            type(confidence) not in (float, int)
            or not math.isfinite(confidence)
            or not 0 <= confidence <= 0.5
        ):
            raise HouseholdLearningError("inferred suggestion confidence must be 0..0.5")
        content = _text(payload["content"], 1000)
        ids = payload["event_ids"]
        if not isinstance(ids, list) or not 1 <= len(ids) <= 12:
            raise HouseholdLearningError("one to twelve event IDs required")
        ids = [_text(value, 256) for value in ids]
        if len(set(ids)) != len(ids):
            raise HouseholdLearningError("duplicate event IDs")
        request_id = _uuid(request_id)
        scope = _REQUEST_SCOPE.get()
        if scope is not None:
            if scope[:2] != (request_id, household_id):
                raise HouseholdLearningError("request evidence scope mismatch")
            allowed = set(scope[2])
            candidates = scope[3]
        elif self.request_evidence_reader is not None:
            allowed = set(self.request_evidence_reader(household_id, request_id))
        else:
            raise HouseholdLearningError("request evidence binding unavailable")
        candidate: dict[str, Any] | None = None
        conclusion = "TENTATIVE_HYPOTHESIS"
        candidate_id: str | None = None
        if structured:
            candidate_id = str(_uuid(payload["candidate_id"]))
            candidate = candidates.get(candidate_id) if scope is not None else None
            if candidate is None:
                raise HouseholdLearningError("candidate not bound to request")
            if set(ids) != set(candidate["source_event_ids"]):
                raise HouseholdLearningError("candidate source references changed")
            # The model may omit explanatory fields from a valid typed
            # proposal. Fill only from the deterministic candidate packet,
            # and use an explicitly conservative conclusion when the model
            # did not provide one. Missing model output must never become a
            # learned routine, identity, authority, or policy decision.
            candidate_supporting = candidate.get("supporting_evidence")
            candidate_missing = candidate.get("missing_information")
            candidate_contradictory = candidate.get("contradictory_evidence")
            defaults = {
                "conclusion": "INSUFFICIENT_EVIDENCE",
                "rationale_summary": (
                    "The provider supplied no separate rationale; ANIMA retained the bounded "
                    "candidate as unconfirmed."
                ),
                "evidence_categories": (
                    [value for value in candidate_supporting if isinstance(value, str)][:8]
                    if isinstance(candidate_supporting, list)
                    else ["qualified_journal_evidence"]
                ),
                "missing_information": (
                    [value for value in candidate_missing if isinstance(value, str)][:8]
                    if isinstance(candidate_missing, list)
                    else ["The provider supplied no additional missing-information summary."]
                ),
                "rejected_alternatives": (
                    [value for value in candidate_contradictory if isinstance(value, str)][:6]
                    if isinstance(candidate_contradictory, list)
                    else []
                ),
            }
            payload = {**defaults, **payload}
            conclusion = payload["conclusion"]
            if conclusion not in {
                "SUPPORTED_OBSERVATION",
                "TENTATIVE_HYPOTHESIS",
                "LEARNED_ROUTINE_SUGGESTION",
                "INSUFFICIENT_EVIDENCE",
                "CONTRADICTED",
                "REJECTED",
                "SUPERSEDED",
            }:
                raise HouseholdLearningError("unsupported candidate conclusion")
            _text(payload["rationale_summary"], 1200)
            for key, maximum in (
                ("evidence_categories", 8),
                ("missing_information", 8),
                ("rejected_alternatives", 6),
            ):
                values = payload[key]
                if (
                    not isinstance(values, list)
                    or len(values) > maximum
                    or any(
                        not isinstance(value, str) or not value.strip() or len(value) > 240
                        for value in values
                    )
                ):
                    raise HouseholdLearningError("invalid candidate review explanation")
        page = self.evidence(household_id, MAX_EVIDENCE)
        found = {row["event_id"]: row for row in page["items"]}
        if not set(ids) <= allowed or not set(ids) <= found.keys():
            raise HouseholdLearningError(
                "evidence not in this request and household Journal window"
            )
        refs = [found[event_id] for event_id in sorted(ids)]
        normalized = {**payload, "event_ids": sorted(ids)}
        signature = hashlib.sha256(json.dumps(normalized, sort_keys=True).encode()).hexdigest()
        current: MemoryRecord | None = None
        if candidate is not None:
            current = next(
                (
                    row
                    for row in self._all_records(household_id, SUGGESTION_KIND)
                    if row.metadata.get("candidate_key") == candidate["candidate_key"]
                ),
                None,
            )
        memory_id = uuid5(
            NAMESPACE,
            f"suggestion:{household_id}:{request_id}:{candidate['candidate_key']}:{signature}"
            if candidate is not None
            else f"suggestion:{household_id}:{invocation_id or request_id}",
        )
        existing = self.memory.get(memory_id)
        if existing is not None:
            if (
                existing.household_id != household_id
                or existing.metadata.get("signature") != signature
            ):
                raise HouseholdLearningError("request reused for different suggestion")
            return {
                "status": "SUCCEEDED",
                "suggestion": self._suggestion(self._projection_receipt(existing)),
            }
        review_packet = self.review_packet(household_id, request_id) if candidate else None
        metadata: dict[str, Any] = {
            "record_kind": SUGGESTION_KIND,
            "kind": kind,
            "review_status": "PENDING",
            "source_refs": refs,
            "signature": signature,
            "request_id": str(request_id),
            "conclusion": conclusion,
        }
        if candidate is not None and review_packet is not None:
            metadata.update(
                candidate_id=candidate_id,
                candidate_key=candidate["candidate_key"],
                candidate_class=candidate["candidate_class"],
                candidate_title=candidate["title"],
                candidate_factual_summary=candidate["factual_summary"],
                maturity=candidate["maturity"],
                evidence_score=candidate["evidence_score"],
                maturity_evidence={
                    key: candidate[key]
                    for key in (
                        "observation_count",
                        "distinct_day_count",
                        "elapsed_hours",
                        "temporal_consistency",
                        "contradictory_evidence",
                        "evidence_score",
                    )
                },
                rationale_summary=payload["rationale_summary"],
                evidence_categories=payload["evidence_categories"],
                missing_information=payload["missing_information"],
                rejected_alternatives=payload["rejected_alternatives"],
                review_id=review_packet["review_id"],
                review_kind=review_packet["review_kind"],
            )
        if self.knowledge_plugin is not None and invocation_context is not None and candidate:
            metadata.update(
                projection_status="PENDING",
                projection_candidate=candidate,
                projection_origin=invocation_context.origin.value,
            )
            if current and current.metadata.get("knowledge_note"):
                metadata["knowledge_note"] = current.metadata["knowledge_note"]
        row = MemoryRecord.create(
            memory_id=memory_id,
            household_id=household_id,
            memory_type=MemoryType.AGENT_LESSON
            if kind == "LESSON"
            else MemoryType.INFERRED_PATTERN,
            content=content,
            created_at=self._now(),
            confidence=float(confidence),
            provenance=MemoryProvenance(
                ProvenanceKind.INFERRED_FROM_HISTORY,
                f"anima:request:{request_id}",
                refs[0]["event_id"],
            ),
            graph_refs=tuple(sorted({_uuid(ref["canonical_id"]) for ref in refs}, key=str)),
            metadata=metadata,
        )
        try:
            saved = (
                self.memory.correct(current.memory_id, row) if current else self.memory.create(row)
            )
        except UniqueViolation:
            saved = self.memory.get(memory_id)
            if saved is None or saved.metadata.get("signature") != signature:
                raise HouseholdLearningError("request reused for different suggestion") from None
        if review_packet is not None:
            self._complete_review(household_id, review_packet)
        saved = self._sync_projection(saved)
        return {"status": "SUCCEEDED", "suggestion": self._suggestion(saved)}

    def _projection_receipt(self, row: MemoryRecord) -> MemoryRecord:
        """Follow only projection receipts, never attribute later owner/model edits to retry."""
        for _ in range(64):
            if row.status != MemoryStatus.SUPERSEDED or not row.superseded_by_memory_id:
                return row
            following = self.memory.get(row.superseded_by_memory_id)
            if (
                following is None
                or following.household_id != row.household_id
                or following.metadata.get("record_kind") != SUGGESTION_KIND
                or following.content != row.content
                or any(
                    following.metadata.get(key) != row.metadata.get(key)
                    for key in ("signature", "review_status", "review_request_id", "request_id")
                )
            ):
                return row
            row = following
        raise HouseholdLearningError("projection receipt chain exceeds bound")

    def _sync_projection(self, row: MemoryRecord) -> MemoryRecord:
        """Retry the exact qualified projection, never a provider request."""
        metadata = row.metadata
        candidate = metadata.get("projection_candidate")
        if self.knowledge_plugin is None or not isinstance(candidate, dict):
            return row
        if metadata.get("projection_status") == "SYNCHRONIZED":
            return row
        if (
            metadata.get("projection_retry_at")
            and _time(metadata["projection_retry_at"]) > self._now()
        ):
            return row
        request_id = _uuid(metadata["request_id"])
        packet = self.review_packet(row.household_id, request_id)
        if (
            not metadata.get("projection_quarantined")
            and not (
                row.provenance.kind == ProvenanceKind.EXPLICIT_INPUT
                and metadata.get("conclusion") == "OWNER_CORRECTION"
            )
            and metadata.get("review_status")
            not in {
                "DISMISSED",
                "CORRECTED",
                "RETRACTED",
            }
            and (
                packet is None
                or not self.review_state(row.household_id, packet)["terminal_success"]
            )
        ):
            return row
        attempt = int(metadata.get("projection_attempts", 0)) + 1
        context = InvocationContext(
            household_id=row.household_id,
            principal_id=None,
            episode_id=request_id,
            tool_request_id=row.memory_id,
            ordinal=1,
            system_idempotency_key=f"learning-projection:{row.memory_id}",
            origin=RequestOrigin(
                metadata.get("projection_origin", RequestOrigin.AUTONOMOUS_AGENT.value)
            ),
        )
        try:
            receipt = self._sync_knowledge(
                row.household_id,
                request_id,
                context,
                row,
                candidate,
                metadata["conclusion"],
                row.content,
                metadata["source_refs"],
                metadata,
                hashlib.sha256(
                    json.dumps(
                        {
                            "signature": metadata["signature"],
                            "review_status": metadata["review_status"],
                            "request_id": metadata.get("request_id"),
                            "review_request_id": metadata.get("review_request_id"),
                            "content": row.content,
                            "quarantined": metadata.get("projection_quarantined", False),
                        },
                        sort_keys=True,
                    ).encode()
                ).hexdigest(),
            )
            updated = {
                **metadata,
                "knowledge_note": receipt,
                "projection_status": "SYNCHRONIZED",
                "projection_failure": None,
                "projection_retry_at": None,
            }
        except (HouseholdLearningError, OSError, RuntimeError):
            updated = {
                **metadata,
                "projection_status": "FAILED",
                "projection_failure": "KNOWLEDGE_SYNC_FAILED",
                "projection_retry_at": (
                    self._now() + timedelta(seconds=min(3600, 30 * 2 ** min(attempt, 7)))
                ).isoformat(),
            }
        updated["projection_attempts"] = attempt
        updated["projection_updated_at"] = self._now().isoformat()
        replacement = replace(
            row,
            memory_id=uuid5(NAMESPACE, f"projection:{row.memory_id}:{attempt}"),
            created_at=self._now(),
            metadata=updated,
            supersedes_memory_id=None,
        )
        try:
            return cast(MemoryRecord, self.memory.correct(row.memory_id, replacement))
        except UniqueViolation:
            return cast(MemoryRecord, self.memory.get(replacement.memory_id) or row)

    def _sync_knowledge(
        self,
        household_id: UUID,
        request_id: UUID,
        invocation_context: InvocationContext | None,
        current: MemoryRecord | None,
        candidate: dict[str, Any] | None,
        conclusion: str,
        content: str,
        refs: list[dict[str, Any]],
        metadata: dict[str, Any],
        signature: str,
    ) -> dict[str, str] | None:
        if self.knowledge_plugin is None or invocation_context is None or candidate is None:
            return None
        note_type, classifier = {
            "SUPPORTED_OBSERVATION": ("observed_pattern", "300.2"),
            "TENTATIVE_HYPOTHESIS": ("hypothesis", "300.3"),
            "LEARNED_ROUTINE_SUGGESTION": ("learned_routine", "300.4"),
            "INSUFFICIENT_EVIDENCE": ("rejected_hypothesis", "300.5"),
            "CONTRADICTED": ("rejected_hypothesis", "300.5"),
            "REJECTED": ("rejected_hypothesis", "300.5"),
            "SUPERSEDED": ("rejected_hypothesis", "300.5"),
            "OWNER_CORRECTION": ("household_model", "300.1"),
        }[conclusion]
        source_refs = [
            {
                "kind": "request",
                "source_id": str(request_id),
                "meaning": "Bounded SENTRY learning review.",
            },
            *[
                {
                    "kind": "event",
                    "source_id": ref["event_id"],
                    "meaning": "Qualified source observation.",
                }
                for ref in refs[:11]
            ],
        ]
        if metadata.get("review_request_id"):
            source_refs = [
                {
                    "kind": "request",
                    "source_id": metadata["review_request_id"],
                    "meaning": "Explicit owner review/correction, not execution authority.",
                },
                *source_refs[:11],
            ]
        maturity = (
            candidate["maturity_evidence"]
            if "maturity_evidence" in candidate
            else {
                key: candidate[key]
                for key in (
                    "observation_count",
                    "distinct_day_count",
                    "elapsed_hours",
                    "temporal_consistency",
                )
            }
        )
        rationale = metadata.get("rationale_summary", "Not separately supplied.")
        if not isinstance(rationale, str) or not rationale.strip():
            rationale = "Not separately supplied."
        maturity_text = _bounded_note_text(json.dumps(maturity, sort_keys=True), 1200, 600)
        missing_text = _bounded_note_text(
            json.dumps(
                _bounded_note_missing(metadata.get("missing_information", [])), sort_keys=True
            ),
            2048,
            1000,
        )
        body = (
            f"Conclusion: {conclusion}\n\n{_bounded_note_text(content, 1000, 1000)}\n\n"
            "Review rationale: "
            f"{_bounded_note_text(rationale, 1200, KNOWLEDGE_NOTE_RATIONALE_CHARS)}\n\n"
            f"Observable maturity inputs: {maturity_text}\n\n"
            f"Missing information: {missing_text}\n\n"
            "This is inferred context, not Truth, identity, policy, authentication, "
            "or an executable routine."
        )
        review_status = metadata.get("review_status", "PENDING")
        body += f"\n\nOwner review: {review_status}. ACK is review, never execution approval."
        arguments: dict[str, Any] = {
            "title": candidate["title"],
            "body": body,
            "note_type": note_type,
            "classifier": classifier,
            "classification": "USER_STATED"
            if conclusion == "OWNER_CORRECTION"
            else "SENTRY_INFERENCE",
            "confidence": 0.5 if metadata.get("maturity") == "LEARNED_ROUTINE_ELIGIBLE" else 0.35,
            "source_refs": source_refs,
            "observed_at": None,
            "enabled": review_status not in {"DISMISSED", "RETRACTED"}
            and not metadata.get("projection_quarantined", False),
            "retention_days": None,
            "person_refs": [],
        }
        operation = "create_note"
        previous = current.metadata.get("knowledge_note") if current else None
        if isinstance(previous, dict) and previous.get("note_id") and previous.get("digest"):
            operation = "update_note"
            arguments.update(note_id=previous["note_id"], expected_digest=previous["digest"])
        context = InvocationContext(
            household_id=household_id,
            principal_id=None,
            episode_id=request_id,
            tool_request_id=uuid5(
                NAMESPACE, f"knowledge:{household_id}:{candidate['candidate_key']}:{signature}"
            ),
            ordinal=invocation_context.ordinal,
            system_idempotency_key=f"{invocation_context.system_idempotency_key}:knowledge",
            origin=invocation_context.origin,
        )
        try:
            result = self.knowledge_plugin.invoke_with_invocation_context(
                operation, arguments, 10, context
            )
        except KnowledgeValidationError as exc:
            # Keep the provider boundary content-free while retaining the
            # exact fixed validation category needed to repair automation.
            code = exc.args[0] if exc.args else None
            safe_code = (
                code
                if isinstance(code, str) and re.fullmatch(r"KNOWLEDGE_[A-Z0-9_]+", code)
                else "KNOWLEDGE_VALIDATION_ERROR"
            )
            raise HouseholdLearningError(f"KNOWLEDGE_SYNC_{safe_code}") from None
        note = result.get("note") if isinstance(result, dict) else None
        if not isinstance(note, dict) or not note.get("note_id") or not note.get("digest"):
            raise HouseholdLearningError("knowledge synchronization failed")
        return {"note_id": str(note["note_id"]), "digest": str(note["digest"])}

    def _complete_review(
        self,
        household_id: UUID,
        packet: dict[str, Any],
        *,
        outcomes: list[MemoryRecord] | None = None,
        previous: MemoryRecord | None = None,
    ) -> None:
        candidate_ids = {item["candidate_id"] for item in packet["candidates"]}
        if outcomes is None:
            outcomes = [
                row
                for row in self._all_records(household_id, SUGGESTION_KIND)
                if row.metadata.get("review_id") == packet["review_id"]
            ]
        if previous is None:
            previous = next(
                (
                    row
                    for row in self._all_records(household_id, REVIEW_COMPLETION_KIND)
                    if row.metadata.get("review_id") == packet["review_id"]
                ),
                None,
            )
        state = self.review_state(household_id, packet, outcomes=outcomes, previous=previous)
        if previous is not None and all(
            previous.metadata.get(key) == value for key, value in state.items()
        ):
            return
        signature = hashlib.sha256(json.dumps(state, sort_keys=True).encode()).hexdigest()
        completion_id = uuid5(NAMESPACE, f"review-disposition:{packet['review_id']}:{signature}")
        if self.memory.get(completion_id) is not None:
            return
        counts = Counter(str(row.metadata.get("conclusion")) for row in outcomes)
        completion = MemoryRecord.create(
            memory_id=completion_id,
            household_id=household_id,
            memory_type=MemoryType.OBSERVED_CONTEXT,
            content=(
                f"{packet['review_kind']} learning review {state['review_status']} for "
                f"{len(outcomes)} bounded candidate(s)."
            ),
            provenance=MemoryProvenance(
                ProvenanceKind.INFERRED_FROM_HISTORY,
                f"anima:request:{packet['request_id']}",
            ),
            created_at=self._now(),
            confidence=1.0,
            metadata={
                **state,
                "reconciles_memory_id": str(previous.memory_id) if previous else None,
                "record_kind": REVIEW_COMPLETION_KIND,
                "review_id": packet["review_id"],
                "request_id": packet["request_id"],
                "review_kind": packet["review_kind"],
                "candidate_count": len(candidate_ids),
                "outcome_count": previous.metadata["outcome_count"]
                if previous and not outcomes
                else len(outcomes),
                "outcomes": dict(counts),
                "evidence_start": packet["evidence_start"],
                "evidence_end": packet["evidence_end"],
                "candidate_digest": packet["candidate_digest"],
            },
        )
        try:
            self.memory.correct(previous.memory_id, completion) if previous else self.memory.create(
                completion
            )
        except UniqueViolation:
            pass

    def review(
        self,
        household_id: UUID,
        principal_id: UUID,
        payload: dict[str, Any],
        request_id: UUID,
    ) -> dict[str, Any]:
        self._owner(household_id, principal_id)
        if (payload.get("decision") == "CORRECTED") != ("content" in payload):
            raise HouseholdLearningError("only correction requires content")
        if (
            set(payload) - {"suggestion_id", "decision", "content"}
            or not {"suggestion_id", "decision"} <= set(payload)
            or payload["decision"]
            not in {
                "ACKNOWLEDGED",
                "DISMISSED",
                "CORRECTED",
                "RETRACTED",
            }
        ):
            raise HouseholdLearningError(
                "review requires suggestion version and supported decision"
            )
        version = uuid5(NAMESPACE, f"review:{household_id}:{_uuid(request_id)}")
        existing = self.memory.get(version)
        if existing is not None:
            if (
                existing.household_id != household_id
                or str(existing.supersedes_memory_id) != payload["suggestion_id"]
                or existing.metadata.get("review_status") != payload["decision"]
                or (
                    payload["decision"] == "CORRECTED"
                    and existing.content != _text(payload["content"], 1000)
                )
            ):
                raise HouseholdLearningError("review request reused with different arguments")
            return {
                "status": "SUCCEEDED",
                "suggestion": self._suggestion(self._projection_receipt(existing)),
            }
        row = self.memory.get(_uuid(payload["suggestion_id"]))
        if (
            row is None
            or row.household_id != household_id
            or row.metadata.get("record_kind") != SUGGESTION_KIND
        ):
            raise HouseholdLearningError("suggestion does not exist in household")
        if row.status != MemoryStatus.ACTIVE:
            raise HouseholdLearningError("suggestion version changed; reload")
        replacement = MemoryRecord.create(
            memory_id=version,
            household_id=household_id,
            memory_type=MemoryType.EXPLICIT_FACT
            if payload["decision"] == "CORRECTED"
            else row.memory_type,
            content=_text(payload.get("content"), 1000)
            if payload["decision"] == "CORRECTED"
            else row.content,
            provenance=MemoryProvenance(ProvenanceKind.EXPLICIT_INPUT, f"owner:{principal_id}")
            if payload["decision"] == "CORRECTED"
            else row.provenance,
            confidence=row.confidence,
            graph_refs=row.graph_refs,
            created_at=self._now(),
            metadata={
                **row.metadata,
                "review_status": payload["decision"],
                "conclusion": "OWNER_CORRECTION"
                if payload["decision"] == "CORRECTED"
                else row.metadata["conclusion"],
                "reviewed_by": str(principal_id),
                "reviewed_at": self._now().isoformat(),
                "review_request_id": str(request_id),
                "projection_origin": RequestOrigin.DIRECT_USER.value,
                "projection_quarantined": False
                if payload["decision"] == "CORRECTED"
                else row.metadata.get("projection_quarantined", False),
                "projection_status": "PENDING"
                if row.metadata.get("projection_candidate")
                else "NOT_CONFIGURED",
                "projection_retry_at": None,
            },
        )
        saved = self.memory.correct(row.memory_id, replacement)
        saved = self._sync_projection(saved)
        self.evaluate_shadows(household_id)
        return {"status": "SUCCEEDED", "suggestion": self._suggestion(saved)}

    def freeze_shadow(
        self, household_id: UUID, principal_id: UUID, payload: dict[str, Any], request_id: UUID
    ) -> dict[str, Any]:
        """Explicit owner-selected shadow only. Freeze before any future outcomes."""
        self._owner(household_id, principal_id)
        fields = {
            "suggestion_id",
            "canonical_id",
            "event_type",
            "predicts_occurrence",
            "starts_at",
            "window_seconds",
            "window_count",
        }
        if set(payload) != fields or type(payload["predicts_occurrence"]) is not bool:
            raise HouseholdLearningError("exact shadow fields required")
        starts = _time(payload["starts_at"])
        normalized = {**payload, "starts_at": starts.isoformat()}
        signature = hashlib.sha256(json.dumps(normalized, sort_keys=True).encode()).hexdigest()
        identifier = uuid5(NAMESPACE, f"shadow:{household_id}:{request_id}")
        existing = self.memory.get(identifier)
        if existing:
            if (
                existing.household_id != household_id
                or existing.metadata.get("input_digest") != signature
            ):
                raise HouseholdLearningError("shadow request reused")
            return {
                "status": "SUCCEEDED",
                "evaluation": self._shadow_public(self._shadow_receipt(existing)),
            }
        source = self.memory.get(_uuid(payload["suggestion_id"]))
        if (
            source is None
            or source.household_id != household_id
            or source.status != MemoryStatus.ACTIVE
            or source.metadata.get("record_kind") != SUGGESTION_KIND
            or source.metadata.get("review_status") in {"DISMISSED", "RETRACTED"}
        ):
            raise HouseholdLearningError("active household hypothesis version required")
        packet = self.review_packet(household_id, _uuid(source.metadata["request_id"]))
        if packet is None or not self.review_state(household_id, packet)["terminal_success"]:
            raise HouseholdLearningError("qualified review outcome required")
        canonical_id = str(_uuid(payload["canonical_id"]))
        current_ids = {
            str(node.canonical_id)
            for node in [
                *self.graph.resources_in_place(household_id),
                *self.graph.members_of_household(household_id),
            ]
        }
        if canonical_id not in current_ids:
            raise HouseholdLearningError(
                "prediction source is not a current household member/resource"
            )
        event_type = payload["event_type"]
        if event_type not in LEARNING_EVENT_TYPES or not any(
            ref["canonical_id"] == canonical_id and ref["event_type"] == event_type
            for ref in source.metadata["source_refs"]
        ):
            raise HouseholdLearningError("prediction must match qualified source references")
        seconds, count = payload["window_seconds"], payload["window_count"]
        if (
            type(seconds) is not int
            or not 300 <= seconds <= 86400
            or type(count) is not int
            or not 1 <= count <= 48
        ):
            raise HouseholdLearningError("shadow opportunity bounds exceeded")
        frozen_at = self._now()
        if not frozen_at < starts <= frozen_at + timedelta(days=7) or starts + timedelta(
            seconds=seconds * count
        ) > frozen_at + timedelta(days=28):
            raise HouseholdLearningError("future bounded window required")
        row = MemoryRecord.create(
            memory_id=identifier,
            household_id=household_id,
            memory_type=MemoryType.TEMPORARY_EPISODIC,
            created_at=frozen_at,
            content="Owner-selected prospective shadow evaluation; no executable authority.",
            provenance=MemoryProvenance(ProvenanceKind.EXPLICIT_INPUT, f"owner:{principal_id}"),
            metadata={
                "record_kind": SHADOW_KIND,
                "input_digest": signature,
                "evaluation_id": str(identifier),
                "frozen_at": frozen_at.isoformat(),
                "hypothesis_version": str(source.memory_id),
                "hypothesis_signature": source.metadata["signature"],
                "hypothesis_content_digest": hashlib.sha256(source.content.encode()).hexdigest(),
                "prediction": normalized,
                "baseline": "PREDICT_NO_OCCURRENCE",
                "required_coverage": "QUALIFIED_SOURCE_INTERVAL",
                "late_grace_seconds": 60,
                "disposition": "EVIDENCE_PENDING",
                "windows": [],
            },
        )
        self.memory.create(row)
        return {"status": "SUCCEEDED", "evaluation": self._shadow_public(row)}

    def _shadow_receipt(self, row: MemoryRecord) -> MemoryRecord:
        for _ in range(64):
            if row.status != MemoryStatus.SUPERSEDED or not row.superseded_by_memory_id:
                return row
            following = self.memory.get(row.superseded_by_memory_id)
            if (
                following is None
                or following.household_id != row.household_id
                or following.metadata.get("input_digest") != row.metadata.get("input_digest")
            ):
                raise HouseholdLearningError("invalid shadow receipt chain")
            row = following
        raise HouseholdLearningError("shadow receipt chain exceeds bound")

    @staticmethod
    def _shadow_public(row: MemoryRecord) -> dict[str, Any]:
        value = row.metadata
        windows = value["windows"]
        qualified = [item for item in windows if not item["unknown"]]
        return {
            key: value[key]
            for key in (
                "evaluation_id",
                "frozen_at",
                "hypothesis_version",
                "prediction",
                "baseline",
                "required_coverage",
                "disposition",
            )
        } | {
            "windows": windows,
            "planned_opportunities": value["prediction"]["window_count"],
            "closed_opportunities": len(windows),
            "covered_opportunities": sum(item["coverage"] == "QUALIFIED" for item in windows),
            "known_opportunities": len(qualified),
            "observed_positive_opportunities": sum(
                item.get("outcome_basis") == "QUALIFIED_POSITIVE_SOURCE_RECEIPT" for item in windows
            ),
            "unknown_opportunities": len(windows) - len(qualified),
            "misses": sum(item["miss"] is True for item in qualified),
            "prediction_correct": sum(item["prediction_correct"] is True for item in qualified),
            "baseline_correct": sum(item["baseline_correct"] is True for item in qualified),
            "real_future_evidence": "PENDING"
            if value["disposition"] == "EVIDENCE_PENDING"
            else "SOURCE_WINDOW_ONLY_NOT_PHYSICAL",
            "authority": "NONE",
        }

    def evaluations(
        self, household_id: UUID, limit: int = 20, cursor: str | None = None
    ) -> dict[str, Any]:
        if type(limit) is not int or not 1 <= limit <= 20:
            raise HouseholdLearningError("evaluation limit must be 1..20")
        rows = self._records(
            household_id, SHADOW_KIND, limit=limit + 1, cursor=_uuid(cursor) if cursor else None
        )
        return {
            "status": "SUCCEEDED",
            "items": [self._shadow_public(row) for row in rows[:limit]],
            "next_cursor": str(rows[limit - 1].memory_id) if len(rows) > limit else None,
        }

    def evaluate_shadows(self, household_id: UUID) -> None:
        from anima_ha.household_shadow import score_window

        for row in self._all_records(household_id, SHADOW_KIND):
            metadata = row.metadata
            if metadata["disposition"] == "SUPERSEDED_HYPOTHESIS":
                continue
            source = self.memory.get(_uuid(metadata["hypothesis_version"]))
            for _ in range(64):
                if source is None or source.status != MemoryStatus.SUPERSEDED:
                    break
                source = self.memory.get(source.superseded_by_memory_id)
            valid = bool(
                source
                and source.household_id == household_id
                and source.status == MemoryStatus.ACTIVE
                and source.metadata.get("signature") == metadata["hypothesis_signature"]
                and hashlib.sha256(source.content.encode()).hexdigest()
                == metadata["hypothesis_content_digest"]
                and source.metadata.get("review_status") not in {"DISMISSED", "RETRACTED"}
            )
            updated = dict(metadata)
            if not valid:
                updated["disposition"] = "SUPERSEDED_HYPOTHESIS"
                updated["invalidated_at"] = self._now().isoformat()
            else:
                prediction = metadata["prediction"]
                windows = list(metadata["windows"])
                page = self.evidence(household_id, MAX_EVIDENCE)
                # Closed receipts stay immutable versions. Late Journal arrivals
                # may only reduce confidence, not retroactively fill a coverage gap.
                for index, window in enumerate(windows):
                    check = score_window(
                        start=_time(window["start"]),
                        end=_time(window["end"]),
                        frozen_at=_time(metadata["frozen_at"]),
                        closed_at=_time(window["end"])
                        + timedelta(seconds=metadata["late_grace_seconds"]),
                        event_type=prediction["event_type"],
                        canonical_id=prediction["canonical_id"],
                        predicts_occurrence=prediction["predicts_occurrence"],
                        events=page["items"],
                        coverage={"status": "UNKNOWN"},
                        truncated=False,
                    )
                    if (
                        check["late_records"] > window["late_records"]
                        and window.get("outcome_basis") != "QUALIFIED_POSITIVE_SOURCE_RECEIPT"
                    ):
                        windows[index] = {
                            **window,
                            "late_records": check["late_records"],
                            "coverage": "UNKNOWN",
                            "unknown": True,
                            "observed_occurrence": None,
                            "prediction_correct": None,
                            "miss": None,
                            "baseline_correct": None,
                        }
                for index in range(len(windows), prediction["window_count"]):
                    start = _time(prediction["starts_at"]) + timedelta(
                        seconds=prediction["window_seconds"] * index
                    )
                    end = start + timedelta(seconds=prediction["window_seconds"])
                    closed = end + timedelta(seconds=metadata["late_grace_seconds"])
                    if closed > self._now():
                        break
                    coverage = (
                        self.coverage_reader(
                            household_id,
                            prediction["canonical_id"],
                            prediction["event_type"],
                            start,
                            end,
                        )
                        if self.coverage_reader
                        else {"status": "UNKNOWN"}
                    )
                    windows.append(
                        score_window(
                            start=start,
                            end=end,
                            frozen_at=_time(metadata["frozen_at"]),
                            closed_at=closed,
                            event_type=prediction["event_type"],
                            canonical_id=prediction["canonical_id"],
                            predicts_occurrence=prediction["predicts_occurrence"],
                            events=page["items"],
                            coverage=coverage,
                            truncated=bool(page["truncated"] or page["status"] != "SUCCEEDED"),
                        )
                    )
                updated["windows"] = windows
                if len(windows) == prediction["window_count"]:
                    updated["disposition"] = (
                        "WINDOW_CLOSED_UNKNOWN_COVERAGE"
                        if any(item["unknown"] for item in windows)
                        else "WINDOW_SCORED"
                    )
            if updated == metadata:
                continue
            digest = hashlib.sha256(json.dumps(updated, sort_keys=True).encode()).hexdigest()
            replacement = replace(
                row,
                memory_id=uuid5(NAMESPACE, f"shadow-result:{metadata['evaluation_id']}:{digest}"),
                created_at=self._now(),
                metadata=updated,
                supersedes_memory_id=None,
            )
            try:
                self.memory.correct(row.memory_id, replacement)
            except UniqueViolation:
                pass

    @staticmethod
    def _task_keys(
        household_id: UUID, config: InitiativeConfig, row: MemoryRecord | None
    ) -> dict[str, str]:
        version = str(row.memory_id) if row else "defaults"
        return {
            kind: f"household-learning:{household_id}:{version}:{kind}"
            for kind, enabled in (
                ("DAILY", config.daily_review_enabled),
                ("ROUTINE", config.routine_review_enabled),
            )
            if enabled
        }

    def _scheduling(
        self, household_id: UUID, config: InitiativeConfig, row: MemoryRecord | None
    ) -> dict[str, Any]:
        result: dict[str, Any] = {
            "status": "NOT_SCHEDULED",
            "tasks": [],
            "execution_status": "NOT_OBSERVED",
        }
        if self.task_service is None:
            return result
        keys = self._task_keys(household_id, config, row)
        tasks = self.task_service.list_tasks(household_id, status=TaskStatus.ACTIVE)
        result["tasks"] = [
            {
                "task_id": str(task.task_id),
                "kind": kind,
                "next_run_at": task.next_run_at.isoformat(),
            }
            for kind, key in keys.items()
            for task in tasks
            if task.creation_idempotency_key == key
        ]
        if keys and len(result["tasks"]) == len(keys):
            result["status"] = "SCHEDULED"
        elif result["tasks"]:
            result["status"] = "PARTIAL"
        return result

    def ensure_review_tasks(self, household_id: UUID) -> dict[str, Any]:
        """Explicit Core reconciliation, never called from status/configure.

        Reuses TaskService; only this household's tagged review tasks are
        cancelled/replaced. Runtime must recheck current config before consuming
        an already-dispatched old task. No automatic notification is authorized.
        """
        config, row = self._config(household_id)
        if self.task_service is None:
            return self._scheduling(household_id, config, row)
        if row is None:
            return {
                "status": "NOT_SCHEDULED",
                "tasks": [],
                "execution_status": "NOT_OBSERVED",
                "reason": "CONFIG_NOT_SAVED",
            }
        keys = self._task_keys(household_id, config, row)
        tasks = self.task_service.list_tasks(household_id)
        for task in tasks:
            if (
                task.metadata.get("created_via") == "household_learning"
                and task.creation_idempotency_key not in keys.values()
                and task.status in {TaskStatus.ACTIVE, TaskStatus.PAUSED}
            ):
                self.task_service.cancel(task.task_id, now=self._now())
        existing = {task.creation_idempotency_key for task in tasks}
        # Stable per-version anchor is necessary for concurrent retries. This
        # is scheduling metadata, never an observed-day/readiness watermark.
        anchor = row.created_at
        for kind, key in keys.items():
            if key in existing:
                continue
            days = 1 if kind == "DAILY" else config.routine_review_days
            self.task_service.create(
                household_id=household_id,
                task_type=TaskType.REASONING_DUE,
                title="Daily SENTRY self-review"
                if kind == "DAILY"
                else "Household learned routine review",
                payload={
                    "review_kind": kind,
                    "config_version": str(row.memory_id) if row else None,
                    "objective": (
                        "Read bounded household evidence; review useful lessons and propose "
                        "source-linked suggestions or none. Never invent observations or "
                        "execute suggestions."
                    ),
                },
                schedule=TaskSchedule(
                    kind=ScheduleKind.INTERVAL,
                    timezone=self.zone.key,
                    run_at=anchor + timedelta(days=days),
                    interval_seconds=days * 86400,
                    misfire_policy=MisfirePolicy.COALESCE_ONE,
                ),
                creation_idempotency_key=key,
                metadata={"created_via": "household_learning"},
                provenance={
                    "kind": "HOUSEHOLD_REVIEW",
                    "config_version": str(row.memory_id) if row else None,
                },
                now=self._now(),
            )
        return self._scheduling(household_id, config, row)


_CONFIG_SCHEMA = {
    "learning_days": {"type": "integer", "minimum": 3, "maximum": 14},
    "routine_review_days": {"type": "integer", "minimum": 2, "maximum": 14},
    **{
        name: {"type": "boolean"}
        for name in ("daily_review_enabled", "routine_review_enabled", "proactive_enabled")
    },
    "always_notify": {
        "type": "array",
        "items": {"type": "string", "enum": list(EVENT_TYPES)},
        "uniqueItems": True,
        "maxItems": len(EVENT_TYPES),
    },
    "device_notifications": {
        "type": "array",
        "maxItems": 128,
        "items": {
            "type": "object",
            "properties": {
                "resource_id": {"type": "string", "format": "uuid"},
                "mode": {"type": "string", "enum": list(DEVICE_NOTIFICATION_MODES)},
                "start_local": {"type": "string", "pattern": "^[0-2][0-9]:[0-5][0-9]$"},
                "end_local": {"type": "string", "pattern": "^[0-2][0-9]:[0-5][0-9]$"},
                "timezone": {"type": "string", "minLength": 1, "maxLength": 64},
                "event_kind": {"type": "string", "enum": list(DEVICE_EVENT_KINDS)},
                "sentry_path": {
                    "type": "string",
                    "enum": [
                        SentryEventPath.IMMEDIATE_ANNOUNCEMENT_ONLY.value,
                        SentryEventPath.ANNOUNCEMENT_AND_CONTEXTUAL_REASONING.value,
                        SentryEventPath.NO_SENTRY_REASONING.value,
                    ],
                },
            },
            "required": ["resource_id", "mode", "start_local", "end_local", "timezone"],
            "additionalProperties": False,
        },
    },
    "expected_version": {"type": ["string", "null"], "format": "uuid"},
}


def _tool(
    name: str,
    properties: dict[str, Any],
    required: list[str],
    *,
    read: bool = True,
    description: str | None = None,
) -> dict[str, Any]:
    return {
        "name": name,
        "description": description
        or f"Bounded household learning {name}; suggestions are not executable or verified truth",
        "input_schema": {
            "type": "object",
            "properties": properties,
            "required": required,
            "additionalProperties": False,
        },
        "output_schema": {"type": "object", "additionalProperties": True},
        "semantic_action": "capabilities.read" if read else "capabilities.configure",
        "risk_class": "READ_ONLY" if read else "SECURITY_SECURE_ACTION",
        "read_only": read,
        "idempotency": Idempotency.IDEMPOTENT.value if read else Idempotency.KEYED.value,
        "external_content_trust": ExternalContentTrust.EXTERNAL_UNTRUSTED.value,
    }


HOUSEHOLD_LEARNING_MANIFEST = PluginManifest(
    plugin_id="anima.household-learning",
    plugin_version="1.4.0",
    manifest_version=MANIFEST_VERSION,
    requires_core=CORE_VERSION,
    name="Household learning",
    description="Evidence-bounded initiative preferences and reviewable suggestions",
    runtime_kind=RuntimeKind.TRUSTED_NATIVE,
    trust_class=TrustClass.TRUSTED_NATIVE,
    capabilities=("household.learning",),
    source="builtin:anima_ha.household_learning",
    tools=(
        _tool("get_status", {}, []),
        _tool("get_situation", {}, []),
        _tool(
            "evaluations",
            {
                "limit": {"type": "integer", "minimum": 1, "maximum": 20},
                "cursor": {"type": "string", "format": "uuid"},
            },
            [],
        ),
        _tool(
            "freeze_shadow",
            {
                "suggestion_id": {"type": "string", "format": "uuid"},
                "canonical_id": {"type": "string", "format": "uuid"},
                "event_type": {"type": "string", "enum": list(LEARNING_EVENT_TYPES)},
                "predicts_occurrence": {"type": "boolean"},
                "starts_at": {"type": "string", "format": "date-time"},
                "window_seconds": {"type": "integer", "minimum": 300, "maximum": 86400},
                "window_count": {"type": "integer", "minimum": 1, "maximum": 48},
            },
            [
                "suggestion_id",
                "canonical_id",
                "event_type",
                "predicts_occurrence",
                "starts_at",
                "window_seconds",
                "window_count",
            ],
            read=False,
        ),
        _tool(
            "set_household_mode",
            {
                "mode": {"type": "string", "enum": ["HOME", "AWAY", "UNSET"]},
                "expected_version": {"type": ["string", "null"], "format": "uuid"},
            },
            ["mode", "expected_version"],
            read=False,
            description="Explicit owner declaration only; never infer Away or grant authority",
        ),
        _tool(
            "record_incident_assessment",
            {
                "event_ids": {
                    "type": "array",
                    "minItems": 1,
                    "maxItems": 12,
                    "uniqueItems": True,
                    "items": {"type": "string", "format": "uuid"},
                },
                "assessment": {"type": "string", "minLength": 1, "maxLength": 1000},
                "unknowns": {
                    "type": "array",
                    "maxItems": 8,
                    "items": {"type": "string", "minLength": 1, "maxLength": 240},
                },
            },
            ["event_ids", "assessment", "unknowns"],
            read=False,
            description="Record bounded SENTRY inference with current source references; no action",
        ),
        _tool("configure", _CONFIG_SCHEMA, list(_CONFIG_SCHEMA), read=False),
        _tool(
            "set_device_notification",
            {
                "resource_id": {"type": "string", "format": "uuid"},
                "mode": {
                    "type": "string",
                    "enum": ["DEFAULT", *DEVICE_NOTIFICATION_MODES],
                },
                "event_kind": {"type": "string", "enum": list(DEVICE_EVENT_KINDS)},
                "start_local": {"type": "string", "pattern": "^[0-2][0-9]:[0-5][0-9]$"},
                "end_local": {"type": "string", "pattern": "^[0-2][0-9]:[0-5][0-9]$"},
                "timezone": {"type": "string", "minLength": 1, "maxLength": 64},
                "expected_version": {"type": ["string", "null"], "format": "uuid"},
            },
            ["resource_id", "mode", "event_kind", "expected_version"],
            read=False,
            description=(
                "Set or remove one owner notification rule for a canonical device and bounded "
                "event kind without replacing unrelated household settings. Read get_status "
                "first and pass its exact config_version."
            ),
        ),
        _tool("evidence", {"limit": {"type": "integer", "minimum": 1, "maximum": 50}}, []),
        _tool(
            "suggestions",
            {
                "limit": {"type": "integer", "minimum": 1, "maximum": 20},
                "cursor": {"type": "string", "format": "uuid"},
            },
            [],
        ),
        _tool(
            "propose",
            {
                "kind": {"type": "string", "enum": ["PATTERN", "WORKFLOW", "LESSON"]},
                "content": {"type": "string", "minLength": 1, "maxLength": 1000},
                "confidence": {"type": "number", "minimum": 0, "maximum": 0.5},
                "event_ids": {
                    "type": "array",
                    "minItems": 1,
                    "maxItems": 12,
                    "uniqueItems": True,
                    "items": {"type": "string", "minLength": 1, "maxLength": 256},
                },
                "candidate_id": {"type": "string", "format": "uuid"},
                "conclusion": {
                    "type": "string",
                    "enum": [
                        "SUPPORTED_OBSERVATION",
                        "TENTATIVE_HYPOTHESIS",
                        "LEARNED_ROUTINE_SUGGESTION",
                        "INSUFFICIENT_EVIDENCE",
                        "CONTRADICTED",
                        "REJECTED",
                        "SUPERSEDED",
                    ],
                },
                "rationale_summary": {"type": "string", "minLength": 1, "maxLength": 1200},
                "evidence_categories": {
                    "type": "array",
                    "maxItems": 8,
                    "items": {"type": "string", "minLength": 1, "maxLength": 240},
                },
                "missing_information": {
                    "type": "array",
                    "maxItems": 8,
                    "items": {"type": "string", "minLength": 1, "maxLength": 240},
                },
                "rejected_alternatives": {
                    "type": "array",
                    "maxItems": 6,
                    "items": {"type": "string", "minLength": 1, "maxLength": 240},
                },
            },
            ["kind", "content", "confidence", "event_ids"],
            read=False,
            description=(
                "Record one source-bound learning review outcome. For a supplied learning "
                "candidate, include candidate_id, conclusion, concise rationale, evidence "
                "categories, missing information and rejected alternatives. This never creates "
                "Truth, policy, identity, permissions, routines or actions."
            ),
        ),
        _tool(
            "review",
            {
                "suggestion_id": {"type": "string", "format": "uuid"},
                "decision": {
                    "type": "string",
                    "enum": ["ACKNOWLEDGED", "DISMISSED", "CORRECTED", "RETRACTED"],
                },
                "content": {"type": "string", "minLength": 1, "maxLength": 1000},
            },
            ["suggestion_id", "decision"],
            read=False,
        ),
    ),
)


class HouseholdLearningNativePlugin:
    def __init__(self, service: HouseholdLearningService) -> None:
        self.service = service

    def start(self, secret_env: dict[str, str]) -> None:
        del secret_env

    def stop(self) -> None:
        return None

    def list_tools(self) -> list[dict[str, Any]]:
        return [dict(item) for item in HOUSEHOLD_LEARNING_MANIFEST.tools]

    def invoke(self, name: str, arguments: dict[str, Any], timeout: float) -> Any:
        raise PluginValidationError("household-learning requires trusted invocation context")

    def invoke_with_invocation_context(
        self, name: str, arguments: dict[str, Any], timeout: float, context: InvocationContext
    ) -> Any:
        del timeout
        tool = next(
            (item for item in HOUSEHOLD_LEARNING_MANIFEST.tools if item["name"] == name), None
        )
        if tool is None:
            raise PluginValidationError("unknown household-learning tool")
        validate_instance(tool["input_schema"], arguments)
        if name == "get_status":
            return self.service.status(context.household_id)
        if name == "get_situation":
            return self.service.get_situation(context.household_id)
        if name == "record_incident_assessment":
            scope = _REQUEST_SCOPE.get()
            if scope is None or scope[1] != context.household_id:
                raise HouseholdLearningError("active incident request scope required")
            return self.service.record_incident_assessment(
                context.household_id, arguments, scope[0]
            )
        if name == "set_household_mode":
            if context.origin != RequestOrigin.DIRECT_USER or context.principal_id is None:
                raise HouseholdLearningError("direct commissioned owner declaration required")
            return self.service.set_household_mode(
                context.household_id, context.principal_id, arguments
            )
        if name in {"evidence", "suggestions", "evaluations"}:
            return getattr(self.service, name)(context.household_id, **arguments)
        if name in {"configure", "set_device_notification", "review", "freeze_shadow"} and (
            context.origin != RequestOrigin.DIRECT_USER or context.principal_id is None
        ):
            raise HouseholdLearningError("direct commissioned owner request required")
        if name == "configure":
            assert context.principal_id is not None
            return self.service.configure(context.household_id, context.principal_id, arguments)
        if name == "set_device_notification":
            assert context.principal_id is not None
            return self.service.set_device_notification(
                context.household_id, context.principal_id, arguments
            )
        if name == "propose":
            scope = _REQUEST_SCOPE.get()
            if scope is None or scope[1] != context.household_id:
                raise HouseholdLearningError("active Core learning request scope required")
            return self.service.propose(
                context.household_id,
                context.principal_id,
                arguments,
                scope[0],
                invocation_id=context.tool_request_id,
                invocation_context=context,
            )
        return getattr(self.service, name)(
            context.household_id, context.principal_id, arguments, context.tool_request_id
        )
