"""Server-owned unsolicited-delivery eligibility, separate from model reasoning."""

from __future__ import annotations

from datetime import UTC, datetime, time, timedelta
from typing import Any
from uuid import UUID
from zoneinfo import ZoneInfo

import psycopg
from psycopg.rows import dict_row

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
    return {
        "allowed": allowed,
        "required": required,
        "reason": reason,
        "request_id": str(request_id),
        "evaluated_at": at.isoformat(),
        "delivery": "SELECT_CONFIGURED_CHANNEL_USING_PREFERENCES; NOT_A_DELIVERY_RECEIPT",
    }


class HouseholdInitiativeContext:
    def __init__(self, database_url: str, learning: Any, evidence: HouseholdEventEvidence) -> None:
        self.database_url, self.learning, self.evidence = database_url, learning, evidence

    def __call__(self, request: IntelligenceRequest) -> dict[str, Any]:
        at = datetime.now(UTC)
        closed = notification_disposition(
            request_id=request.request_id, event_type=None, config={}, ready=False, now=at
        )
        try:
            status = self.learning.status(request.household_id)
            result: dict[str, Any] = {"status": "AVAILABLE", **status, "notification": closed}
            result["status"] = "AVAILABLE"
            result["nearby_events"] = self.evidence.recent_household_evidence(
                request.household_id, limit=24, now=at
            )
            if request.origin not in {
                IntelligenceOrigin.AUTONOMOUS_ATTENTION,
                IntelligenceOrigin.DURABLE_TASK,
            }:
                result["notification"] = {**closed, "reason": "DIRECT_REQUEST_NOT_UNSOLICITED"}
                return result
            with psycopg.connect(
                self.database_url,
                row_factory=dict_row,
                connect_timeout=5,
                options="-c statement_timeout=5000",
            ) as connection:
                source = connection.execute(
                    "SELECT event_type,source,metadata,payload,occurred_at "
                    "FROM anima_event_journal "
                    "WHERE event_id=%s AND metadata->>'household_id'=%s",
                    (request.causation_id, str(request.household_id)),
                ).fetchone()
                if source is None:
                    return result
                review = (
                    source["event_type"] == "scheduled_reasoning_due"
                    and source["source"] == "anima:durable-task"
                )
                explicit_alert = False
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
                        explicit_alert = bool(
                            connection.execute(
                                "SELECT 1 FROM anima_senseguard_alert_policies "
                                "WHERE policy_id=%s AND household_id=%s AND enabled "
                                "AND guaranteed_attention AND delivery_mode='SENTRY_COGNITION' "
                                "AND event_type=%s AND resource_ids ? %s",
                                (
                                    policy_uuid,
                                    request.household_id,
                                    source["event_type"],
                                    str(source["payload"].get("canonical_resource_id", "")),
                                ),
                            ).fetchone()
                        )
            valid_source = any(
                item["event_id"] == request.causation_id
                for item in result["nearby_events"]["items"]
            )
            # Delay/absence never authorizes a stale greeting. Reviews remain silent.
            fresh = at - timedelta(seconds=120) <= source["occurred_at"] <= at
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
                now=at,
            )
            return result
        except Exception:
            return {"status": "UNAVAILABLE", "notification": closed, "authority": "NONE"}
