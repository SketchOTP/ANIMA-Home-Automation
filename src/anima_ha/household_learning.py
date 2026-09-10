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
from collections import Counter
from collections.abc import Callable, Iterable, Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import asdict, dataclass, replace
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID, uuid5
from zoneinfo import ZoneInfo

from psycopg.errors import UniqueViolation

from anima_ha.attention import SentryEventPath, compatible_sentry_path
from anima_ha.household_patterns import candidate_digest, extract_pattern_candidates
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
SUGGESTION_KIND = "household_learning_suggestion"
REVIEW_PACKET_KIND = "household_learning_review_packet"
REVIEW_COMPLETION_KIND = "household_learning_review_completion"
MAX_EVIDENCE = 2000
EVIDENCE_WINDOW_DAYS = 28
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
        params.update(kind=kind, after=cursor, limit=limit)
        with self.memory._connect() as connection, connection.cursor() as sql:
            sql.execute(
                f"""SELECT m.* FROM anima_memory_records m WHERE {where}
                AND m.metadata->>'record_kind' = %(kind)s
                AND (%(after)s::uuid IS NULL OR m.memory_id > %(after)s::uuid)
                ORDER BY m.memory_id ASC LIMIT %(limit)s""",
                params,
            )
            return [self.memory._memory(row) for row in sql.fetchall()]

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

    def status(self, household_id: UUID) -> dict[str, Any]:
        config, row = self._config(household_id)
        evidence = self.evidence(household_id, MAX_EVIDENCE)
        readiness = self._readiness(config, evidence)
        candidates = extract_pattern_candidates(
            evidence["items"], household_id=household_id, timezone=self.zone
        )
        completions = self._records(household_id, REVIEW_COMPLETION_KIND, limit=50)
        packets = self._records(household_id, REVIEW_PACKET_KIND, limit=50)
        return {
            "status": "SUCCEEDED",
            "config": config.to_payload(),
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
                "last_review": self._review_summary(completions[-1]) if completions else None,
                "review_count": len(completions),
                "pending_review_count": max(0, len(packets) - len(completions)),
                "gaps": self._learning_gaps(evidence, candidates),
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
            "completed_at": row.created_at.isoformat(),
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
            completions = self._records(household_id, REVIEW_COMPLETION_KIND, limit=50)
            incorporated: set[str] = set()
            for completion in completions:
                request_value = completion.metadata.get("request_id")
                if not request_value:
                    continue
                packet = self.review_packet(household_id, _uuid(request_value))
                if packet is None:
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
    def _suggestion(row: MemoryRecord) -> dict[str, Any]:
        return {
            "suggestion_id": str(row.memory_id),
            "kind": row.metadata["kind"],
            "content": row.content,
            "confidence": row.confidence,
            "classification": "INFERRED",
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
        if structured and not review_fields <= set(payload):
            raise HouseholdLearningError("complete candidate review fields required")
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
                    for row in self._records(household_id, SUGGESTION_KIND, limit=MAX_EVIDENCE)
                    if row.metadata.get("candidate_key") == candidate["candidate_key"]
                ),
                None,
            )
        memory_id = uuid5(
            NAMESPACE,
            f"suggestion:{household_id}:{candidate['candidate_key']}:{signature}"
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
            return {"status": "SUCCEEDED", "suggestion": self._suggestion(existing)}
        review_packet = self.review_packet(household_id, request_id) if candidate else None
        metadata: dict[str, Any] = {
            "record_kind": SUGGESTION_KIND,
            "kind": kind,
            "review_status": "PENDING",
            "source_refs": refs,
            "signature": signature,
            "conclusion": conclusion,
        }
        if candidate is not None and review_packet is not None:
            metadata.update(
                candidate_id=candidate_id,
                candidate_key=candidate["candidate_key"],
                candidate_class=candidate["candidate_class"],
                maturity=candidate["maturity"],
                maturity_evidence={
                    key: candidate[key]
                    for key in (
                        "observation_count",
                        "distinct_day_count",
                        "elapsed_hours",
                        "temporal_consistency",
                        "contradictory_evidence",
                    )
                },
                rationale_summary=payload["rationale_summary"],
                evidence_categories=payload["evidence_categories"],
                missing_information=payload["missing_information"],
                rejected_alternatives=payload["rejected_alternatives"],
                review_id=review_packet["review_id"],
                review_kind=review_packet["review_kind"],
            )
        note_receipt = self._sync_knowledge(
            household_id,
            request_id,
            invocation_context,
            current,
            candidate,
            conclusion,
            content,
            refs,
            metadata,
            signature,
        )
        if note_receipt:
            metadata["knowledge_note"] = note_receipt
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
        return {"status": "SUCCEEDED", "suggestion": self._suggestion(saved)}

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
        body = (
            f"Conclusion: {conclusion}\n\n{content}\n\n"
            f"Review rationale: {metadata.get('rationale_summary', 'Not separately supplied.')}\n\n"
            f"Observable maturity inputs: {json.dumps(maturity, sort_keys=True)}\n\n"
            "Missing information: "
            f"{json.dumps(metadata.get('missing_information', []), sort_keys=True)}\n\n"
            "This is inferred context, not Truth, identity, policy, authentication, "
            "or an executable routine."
        )
        arguments: dict[str, Any] = {
            "title": candidate["title"],
            "body": body,
            "note_type": note_type,
            "classifier": classifier,
            "classification": "SENTRY_INFERENCE",
            "confidence": 0.5 if metadata.get("maturity") == "LEARNED_ROUTINE_ELIGIBLE" else 0.35,
            "source_refs": source_refs,
            "observed_at": None,
            "enabled": True,
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
        result = self.knowledge_plugin.invoke_with_invocation_context(
            operation, arguments, 10, context
        )
        note = result.get("note") if isinstance(result, dict) else None
        if not isinstance(note, dict) or not note.get("note_id") or not note.get("digest"):
            raise HouseholdLearningError("knowledge synchronization failed")
        return {"note_id": str(note["note_id"]), "digest": str(note["digest"])}

    def _complete_review(self, household_id: UUID, packet: dict[str, Any]) -> None:
        candidate_ids = {item["candidate_id"] for item in packet["candidates"]}
        outcomes = [
            row
            for row in self._records(household_id, SUGGESTION_KIND, limit=MAX_EVIDENCE)
            if row.metadata.get("review_id") == packet["review_id"]
        ]
        if (
            candidate_ids
            and {row.metadata.get("candidate_id") for row in outcomes} != candidate_ids
        ):
            return
        completion_id = uuid5(NAMESPACE, f"review-complete:{packet['review_id']}")
        if self.memory.get(completion_id) is not None:
            return
        counts = Counter(str(row.metadata.get("conclusion")) for row in outcomes)
        completion = MemoryRecord.create(
            memory_id=completion_id,
            household_id=household_id,
            memory_type=MemoryType.OBSERVED_CONTEXT,
            content=(
                f"{packet['review_kind']} learning review completed for "
                f"{len(outcomes)} bounded candidate(s)."
            ),
            provenance=MemoryProvenance(
                ProvenanceKind.INFERRED_FROM_HISTORY,
                f"anima:request:{packet['request_id']}",
            ),
            created_at=self._now(),
            confidence=1.0,
            metadata={
                "record_kind": REVIEW_COMPLETION_KIND,
                "review_id": packet["review_id"],
                "request_id": packet["request_id"],
                "review_kind": packet["review_kind"],
                "candidate_count": len(candidate_ids),
                "outcome_count": len(outcomes),
                "outcomes": dict(counts),
                "evidence_start": packet["evidence_start"],
                "evidence_end": packet["evidence_end"],
                "candidate_digest": packet["candidate_digest"],
            },
        )
        try:
            self.memory.create(completion)
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
        if set(payload) != {"suggestion_id", "decision"} or payload["decision"] not in {
            "ACKNOWLEDGED",
            "DISMISSED",
        }:
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
            ):
                raise HouseholdLearningError("review request reused with different arguments")
            return {"status": "SUCCEEDED", "suggestion": self._suggestion(existing)}
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
            memory_type=row.memory_type,
            content=row.content,
            provenance=row.provenance,
            confidence=row.confidence,
            graph_refs=row.graph_refs,
            created_at=self._now(),
            metadata={
                **row.metadata,
                "review_status": payload["decision"],
                "reviewed_by": str(principal_id),
                "reviewed_at": self._now().isoformat(),
            },
        )
        saved = self.memory.correct(row.memory_id, replacement)
        return {"status": "SUCCEEDED", "suggestion": self._suggestion(saved)}

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
    plugin_version="1.3.0",
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
                "decision": {"type": "string", "enum": ["ACKNOWLEDGED", "DISMISSED"]},
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
        if name in {"evidence", "suggestions"}:
            return getattr(self.service, name)(context.household_id, **arguments)
        if name in {"configure", "set_device_notification", "review"} and (
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
