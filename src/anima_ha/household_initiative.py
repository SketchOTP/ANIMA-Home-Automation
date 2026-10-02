"""Server-owned unsolicited-delivery eligibility, separate from model reasoning."""

from __future__ import annotations

import json
from datetime import UTC, datetime, time, timedelta
from typing import Any
from uuid import UUID
from zoneinfo import ZoneInfo

import psycopg
from psycopg.rows import dict_row

from anima_ha.attention import SentryEventPath, compatible_sentry_path
from anima_ha.household_event_context import HouseholdEventEvidence
from anima_ha.intelligence import IntelligenceOrigin, IntelligenceRequest


def device_notification_matches(
    rule: dict[str, Any], event_type: str, payload: dict[str, Any]
) -> bool:
    """Match one bounded owner-selected event selector; no executable predicates."""

    selected = str(rule.get("event_kind", "ANY")).upper()
    if selected == "ANY":
        return True
    candidates = {
        str(payload.get(key, "")).strip().upper()
        for key in ("event_kind", "reported_lock_state", "transition", "state")
    }
    candidates.add(event_type.rsplit(".", 1)[-1].upper())
    aliases = {
        "UNLOCKED": {"UNLOCKED", "UNLOCK"},
        "LOCKED": {"LOCKED", "LOCK"},
        "OPENED": {"OPENED", "OPEN"},
        "CLOSED": {"CLOSED", "CLOSE"},
        "MOTION": {"MOTION", "MOTION_REPORTED"},
        "DOORBELL": {"DOORBELL", "RING"},
    }
    return bool(candidates & aliases.get(selected, set()))


def notification_disposition(
    *,
    request_id: UUID,
    event_type: str | None,
    config: dict[str, Any],
    ready: bool,
    explicit_alert: bool = False,
    device_rule: dict[str, Any] | None = None,
    event_occurred_at: datetime | None = None,
    review: bool = False,
    sentry_event_path: str | SentryEventPath | None = None,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Permission to consider delivery is not proof of delivery or identity."""
    at = now or datetime.now(UTC)
    required = False
    if review:
        allowed, reason = False, "REVIEW_SILENT"
    elif event_type is None:
        allowed, reason = False, "UNAVAILABLE"
    elif device_rule and device_rule.get("mode") == "NEVER":
        allowed, reason = False, "PROACTIVE_DISABLED"
    elif device_rule and device_rule.get("mode") == "ALWAYS":
        allowed, required, reason = True, True, "ALWAYS_NOTIFY"
    elif device_rule and device_rule.get("mode") == "TIME_WINDOW":
        try:
            zone = ZoneInfo(str(device_rule["timezone"]))
            local = (event_occurred_at or at).astimezone(zone).time().replace(microsecond=0)
            start = time.fromisoformat(str(device_rule["start_local"]))
            end = time.fromisoformat(str(device_rule["end_local"]))
            in_window = start <= local < end if start <= end else local >= start or local < end
        except (KeyError, TypeError, ValueError):
            in_window = False
        if in_window:
            allowed, required, reason = True, True, "ALWAYS_NOTIFY"
        else:
            allowed, reason = False, "PROACTIVE_DISABLED"
    elif device_rule and device_rule.get("mode") == "CONTEXTUAL":
        if ready:
            allowed, reason = True, "LEARNED_PROACTIVE"
        else:
            allowed, reason = False, "LEARNING_REQUIRED"
    elif explicit_alert or event_type in config.get("always_notify", []):
        allowed, required, reason = True, True, "ALWAYS_NOTIFY"
    elif not ready:
        allowed, reason = False, "LEARNING_REQUIRED"
    elif config.get("proactive_enabled") is not True:
        allowed, reason = False, "PROACTIVE_DISABLED"
    else:
        allowed, reason = True, "LEARNED_PROACTIVE"
    configured_path = sentry_event_path
    if configured_path is None and device_rule:
        configured_path = device_rule.get("sentry_path")
    path = compatible_sentry_path(
        configured_path,
        alert_mode=str(device_rule.get("mode")) if device_rule else None,
        required=required,
    )
    return {
        "allowed": allowed,
        "required": required,
        "reason": reason,
        "request_id": str(request_id),
        "evaluated_at": at.isoformat(),
        "sentry_event_path": path.value,
        "delivery": "SELECT_CONFIGURED_CHANNEL_USING_PREFERENCES; NOT_A_DELIVERY_RECEIPT",
    }


class HouseholdInitiativeContext:
    def __init__(
        self,
        database_url: str,
        learning: Any,
        evidence: HouseholdEventEvidence,
        owner_tasks: Any | None = None,
    ) -> None:
        self.database_url, self.learning, self.evidence = database_url, learning, evidence
        self.owner_tasks = owner_tasks

    def resolve_event_path(self, household_id: UUID, trigger: Any) -> SentryEventPath | None:
        """Resolve the owner-selected cognition route before request creation.

        The Attention profile supplies the safe default and aggregate/ignore
        semantics.  A matching device rule may refine a normal trigger, but it
        can never turn an aggregate trigger into an immediate one or override
        a route that already disables SENTRY reasoning.
        """
        try:
            raw = trigger.metadata.get(
                "sentry_event_path",
                SentryEventPath.ANNOUNCEMENT_AND_CONTEXTUAL_REASONING.value,
            )
            path = SentryEventPath(str(raw))
            if path in {
                SentryEventPath.AGGREGATED_REASONING,
                SentryEventPath.NO_SENTRY_REASONING,
            }:
                return path
            source_event_id = trigger.source_event_ids[0]
            with psycopg.connect(
                self.database_url,
                row_factory=dict_row,
                connect_timeout=5,
                options="-c statement_timeout=5000",
            ) as connection:
                source = connection.execute(
                    "SELECT event_type,payload FROM anima_event_journal "
                    "WHERE event_id=%s AND metadata->>'household_id'=%s",
                    (source_event_id, str(household_id)),
                ).fetchone()
            if source is None:
                return path
            resource_id = str(
                source["payload"].get("canonical_resource_id")
                or source["payload"].get("resource_id")
                or ""
            )
            status = self.learning.status(household_id, include_learning=False)
            if source["event_type"] in status.get("config", {}).get("always_notify", []):
                # A server-owned always-notify event has already made its
                # alert decision. Keep the first factual announcement off the
                # model path; optional contextual work may not gate speech.
                return SentryEventPath.IMMEDIATE_ANNOUNCEMENT_ONLY
            rule = next(
                (
                    item
                    for item in status.get("config", {}).get("device_notifications", [])
                    if item.get("resource_id") == resource_id
                    and device_notification_matches(item, source["event_type"], source["payload"])
                ),
                None,
            )
            if rule is None:
                return path
            if rule.get("mode") == "NEVER":
                return SentryEventPath.NO_SENTRY_REASONING
            configured = rule.get("sentry_path")
            return SentryEventPath(str(configured)) if configured else path
        except (AttributeError, KeyError, TypeError, ValueError, psycopg.Error):
            # Route lookup is an optimization layer.  A failure must retain
            # the profile's safe contextual default and never invent a
            # suppression or bypass.
            return None

    def __call__(self, request: IntelligenceRequest) -> dict[str, Any]:
        at = datetime.now(UTC)
        closed = notification_disposition(
            request_id=request.request_id, event_type=None, config={}, ready=False, now=at
        )
        try:
            if self.owner_tasks is not None:
                owner = self.owner_tasks.notification(request)
                if owner is not None:
                    return dict(owner)
            status = self.learning.status(request.household_id, include_learning=False)
            result: dict[str, Any] = {"status": "AVAILABLE", **status, "notification": closed}
            result["status"] = "AVAILABLE"
            packet = self.learning.ensure_review_packet(request)
            if packet is not None:
                result["learning_review"] = packet
            if request.origin not in {
                IntelligenceOrigin.AUTONOMOUS_ATTENTION,
                IntelligenceOrigin.DURABLE_TASK,
            }:
                result["notification"] = {
                    **closed,
                    "reason": "DIRECT_REQUEST_NOT_UNSOLICITED",
                }
                return result
            with psycopg.connect(
                self.database_url,
                row_factory=dict_row,
                connect_timeout=5,
                options="-c statement_timeout=5000",
            ) as connection:
                source = connection.execute(
                    "SELECT event_id,event_type,source,metadata,payload,occurred_at "
                    "FROM anima_event_journal "
                    "WHERE event_id=%s AND metadata->>'household_id'=%s",
                    (request.causation_id, str(request.household_id)),
                ).fetchone()
                if source is None:
                    return result
                review = (
                    source["event_type"] == "scheduled_reasoning_due"
                    and source["source"] == "anima:durable-task"
                    and packet is not None
                )
                explicit_alert = False
                explicit_revoked = False
                if (
                    source["source"] == "anima:senseguard-policy"
                    and source["metadata"].get("provenance") == "anima.senseguard.alert_policy"
                ):
                    policy_id = source["metadata"].get("alert_policy_id")
                    try:
                        policy_uuid = UUID(str(policy_id))
                    except (TypeError, ValueError):
                        policy_uuid = None
                    if policy_uuid:
                        current_policy = connection.execute(
                            "SELECT enabled,guaranteed_attention,delivery_mode,"
                            "event_type,resource_ids "
                            "FROM anima_senseguard_alert_policies "
                            "WHERE policy_id=%s AND household_id=%s",
                            (
                                policy_uuid,
                                request.household_id,
                            ),
                        ).fetchone()
                        explicit_alert = bool(
                            current_policy
                            and current_policy["enabled"]
                            and current_policy["guaranteed_attention"]
                            and current_policy["delivery_mode"] == "SENTRY_COGNITION"
                            and current_policy["event_type"] == source["event_type"]
                            and str(source["payload"].get("canonical_resource_id", ""))
                            in current_policy["resource_ids"]
                        )
                        explicit_revoked = current_policy is not None and not explicit_alert
            # Current source qualification is exact, not membership in an
            # optional, truncated correlation window. This uses the existing
            # household/source/trust/clock projection, never raw vendor prose.
            exact = self.evidence.recent_household_evidence(
                request.household_id, event_ids=(str(request.causation_id),), limit=1, now=at
            )
            valid_source = any(item["event_id"] == request.causation_id for item in exact["items"])
            # Delay/absence never authorizes a stale greeting. Reviews remain silent.
            managed = request.request_metadata.get("required_delivery", {})
            freshness_seconds = 600 if managed.get("version") == 1 else 120
            fresh = at - timedelta(seconds=freshness_seconds) <= source["occurred_at"] <= at
            resource_id = str(
                source["payload"].get("canonical_resource_id")
                or source["payload"].get("resource_id")
                or ""
            )
            device_rule = next(
                (
                    item
                    for item in status["config"].get("device_notifications", [])
                    if item.get("resource_id") == resource_id
                ),
                None,
            )
            if device_rule is not None and not device_notification_matches(
                device_rule, source["event_type"], source["payload"]
            ):
                device_rule = None
            result["notification"] = notification_disposition(
                request_id=request.request_id,
                event_type=source["event_type"] if valid_source and fresh else None,
                config=status["config"],
                ready=status["readiness"]["ready"],
                explicit_alert=explicit_alert and valid_source and fresh,
                device_rule=device_rule,
                event_occurred_at=source["occurred_at"],
                review=review,
                sentry_event_path=request.request_metadata.get("sentry_event_path"),
                now=at,
            )
            result["notification"]["revocation_confirmed"] = bool(
                valid_source
                and fresh
                and (explicit_revoked or (device_rule and device_rule.get("mode") == "NEVER"))
            )
            if (
                result["notification"]["allowed"] is True
                and result["notification"]["required"] is True
                and result["notification"]["reason"] == "ALWAYS_NOTIFY"
                and valid_source
                and fresh
            ):
                announcement = self._canonical_announcement(source, resource_id)
                if announcement is not None:
                    result["notification"]["announcement"] = announcement
            return result
        except Exception:
            return {"status": "UNAVAILABLE", "notification": closed, "authority": "NONE"}

    def correlation_context(self, request: IntelligenceRequest) -> dict[str, Any]:
        """Optional rich history; not canonical first-speech authority."""
        try:
            return self.evidence.recent_household_evidence(request.household_id, limit=24)
        except Exception:
            return {"status": "UNAVAILABLE", "items": [], "authority": "NONE"}

    def prospective_feedback_context(self, request: IntelligenceRequest) -> dict[str, Any]:
        """Optional rich reasoning history, never a compact notification dependency."""
        unavailable: dict[str, Any] = {
            "status": "UNAVAILABLE",
            "items": [],
            "authority": "NONE",
        }
        try:
            items = self.learning.prospective_feedback(request.household_id)[-6:]
            if len(json.dumps(items).encode()) > 12000:
                return {**unavailable, "status": "CONTEXT_LIMIT_REQUIRES_SCOPED_READ"}
            return {**unavailable, "status": "AVAILABLE", "items": items}
        except Exception:
            # No raw private exception/content, permission fallback or speech
            # authority. Empty items mean unavailable, not measured absence.
            return unavailable

    def _canonical_announcement(
        self, source: dict[str, Any], resource_id: str
    ) -> dict[str, Any] | None:
        """Build a factual Core-authored first alert from trusted graph identity."""
        if not resource_id:
            return None
        try:
            resource = self.evidence.graph.get_node(UUID(resource_id))
        except (AttributeError, TypeError, ValueError):
            return None
        name = str(getattr(resource, "name", "")).strip()
        if not name or len(name) > 160:
            return None
        event_type = str(source["event_type"])
        payload = source["payload"]
        event_kind = (
            str(
                payload.get("event_kind")
                or payload.get("reported_lock_state")
                or payload.get("transition")
                or event_type.rsplit(".", 1)[-1]
            )
            .strip()
            .lower()
        )
        phrases = {
            "unlocked": f"{name} was unlocked.",
            "opened": f"{name} was opened.",
            "motion": f"Motion was detected by {name}.",
            "motion_reported": f"Motion was detected by {name}.",
            "doorbell": f"{name} was pressed.",
        }
        if event_type == "household.presence.connection_changed":
            text = {
                "reconnected": f"{name}'s associated device is visible on Wi-Fi.",
                "disconnected": f"{name}'s Wi-Fi presence is now uncertain.",
            }.get(event_kind)
        else:
            text = phrases.get(event_kind)
        if text is None:
            return None
        return {
            "schema_version": 1,
            "text": text,
            "event_id": str(source.get("event_id", "")),
            "event_type": event_type,
            "occurred_at": source["occurred_at"].isoformat(),
            "canonical_resource_id": resource_id,
            "canonical_resource_name": name,
            "authority": "ANIMA_CANONICAL_EVENT",
        }
