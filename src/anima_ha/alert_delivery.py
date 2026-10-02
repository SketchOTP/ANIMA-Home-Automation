"""Mandatory speech ledger in the existing intelligence request store.

This is not a model claim or action continuation. Only current Core initiative
policy can create/dispatch an obligation. Playback intent is durable before the
speaker is called; expired intent becomes UNKNOWN, never automatic replay.
"""

from __future__ import annotations

import hashlib
import json
import secrets
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID

import psycopg
from psycopg.rows import dict_row

from anima_ha.intelligence import IntelligenceOrigin, IntelligenceRequest, _request_from_row


def initialize_required_delivery(
    request: IntelligenceRequest, disposition: dict[str, Any]
) -> dict[str, Any] | None:
    if (
        request.origin != IntelligenceOrigin.AUTONOMOUS_ATTENTION
        or request.provider_id != "sentry"
        or request.principal_id is not None
        or disposition.get("allowed") is not True
        or disposition.get("required") is not True
        or disposition.get("reason") != "ALWAYS_NOTIFY"
        or not isinstance(disposition.get("announcement"), dict)
    ):
        return None
    return {
        "version": 1,
        "execution_kind": "SENTRY_REQUIRED_SPEECH",
        "state": "PENDING",
        "generation": 0,
        "attempts": 0,
        "event_id": disposition["announcement"]["event_id"],
        "created_at": datetime.now(UTC).isoformat(),
    }


class PostgresRequiredDelivery:
    def __init__(self, database_url: str) -> None:
        self.database_url = database_url

    @staticmethod
    def _save(cursor: psycopg.Cursor[Any], request_id: UUID, value: dict[str, Any]) -> None:
        cursor.execute(
            """UPDATE anima_intelligence_requests SET request_metadata=jsonb_set(
                request_metadata, '{required_delivery}', %s::jsonb), updated_at=now()
                WHERE request_id=%s""",
            (json.dumps(value, sort_keys=True), request_id),
        )

    def state(self, request_id: UUID) -> dict[str, Any]:
        with psycopg.connect(self.database_url, row_factory=dict_row) as conn:
            row = conn.execute(
                "SELECT request_metadata->'required_delivery' AS delivery "
                "FROM anima_intelligence_requests WHERE request_id=%s",
                (request_id,),
            ).fetchone()
        return dict(row["delivery"] or {}) if row else {}

    def queue_followup(
        self, request_id: UUID, response: str, disposition: Callable[[Any], dict[str, Any]]
    ) -> bool:
        """Retain a bounded obligation/digest, never durable generated prose.

        Content remains in the existing provider's RAM. After restart it cannot
        be recovered by model replay: missing content escalates explicitly.
        """
        with psycopg.connect(self.database_url, row_factory=dict_row) as conn:
            row = conn.execute(
                "SELECT * FROM anima_intelligence_requests WHERE request_id=%s FOR UPDATE",
                (request_id,),
            ).fetchone()
            if row is None:
                return False
            saved = dict(row["request_metadata"].get("required_delivery") or {})
            policy = disposition(_request_from_row(row))
            canonical = policy.get("announcement", {}).get("text", "")
            if (
                not saved
                or saved.get("state") in {"UNKNOWN", "ESCALATED", "CANCELLED"}
                or "followup" in saved
                or not policy.get("allowed")
                or row["request_metadata"].get("sentry_event_path")
                != "ANNOUNCEMENT_AND_CONTEXTUAL_REASONING"
                or not response.strip()
                or len(response.encode()) > 4000
                or " ".join(response.lower().split()) == " ".join(canonical.lower().split())
            ):
                return False
            saved["followup"] = {
                "state": "PENDING",
                "content_ready": False,
                "response_digest": hashlib.sha256(response.encode()).hexdigest(),
                "generation": 0,
                "attempts": 0,
            }
            with conn.cursor() as cursor:
                self._save(cursor, request_id, saved)
        return True

    def ready_followup(self, request_id: UUID, household_id: UUID, response_digest: str) -> bool:
        with psycopg.connect(self.database_url, row_factory=dict_row) as conn:
            row = conn.execute(
                "SELECT request_metadata FROM anima_intelligence_requests "
                "WHERE request_id=%s AND household_id=%s FOR UPDATE",
                (request_id, household_id),
            ).fetchone()
            saved = dict(row["request_metadata"].get("required_delivery") or {}) if row else {}
            following = saved.get("followup", {})
            if (
                following.get("state") != "PENDING"
                or following.get("response_digest") != response_digest
            ):
                return False
            following["content_ready"] = True
            with conn.cursor() as cursor:
                self._save(cursor, request_id, saved)
        return True

    def next(
        self,
        *,
        household_id: UUID,
        client_id: str,
        not_before: datetime,
        active_instance_id: str = "office",
        credential_generation: int = 1,
        max_age_seconds: int = 120,
        disposition: Callable[[Any], dict[str, Any]],
        now: datetime | None = None,
    ) -> dict[str, Any]:
        at = now or datetime.now(UTC)
        # These fields qualify the consumer's current enable epoch and initial
        # model-queue freshness, NOT a new cutoff for existing managed speech.
        # Only Core-created versioned obligations are scanned; pre-epoch ones
        # remain accountable until their original bounded expiry. No historical
        # request is adopted merely because a new consumer enabled itself.
        if (
            not_before.tzinfo is None
            or not_before > at
            or type(max_age_seconds) is not int
            or not 1 <= max_age_seconds <= 120
        ):
            raise ValueError("INVALID_ALERT_ENABLE_EPOCH")
        with psycopg.connect(self.database_url, row_factory=dict_row) as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    """SELECT r.*,d.value AS active_delivery FROM anima_intelligence_requests r
                       CROSS JOIN LATERAL (SELECT CASE
                         WHEN request_metadata->'required_delivery'->>'state'='DELIVERED'
                         THEN request_metadata->'required_delivery'->'followup'
                         ELSE request_metadata->'required_delivery' END AS value) d
                       WHERE household_id=%s AND provider_id='sentry'
                       AND origin='AUTONOMOUS_ATTENTION' AND principal_id IS NULL
                       AND created_at <= %s
                       AND request_metadata->'required_delivery'->'version'='1'::jsonb
                       AND d.value->>'state' IN ('PENDING','CLAIMED','PLAYBACK_INTENT')
                       AND (d.value->>'state'='PENDING'
                            OR (d.value->>'lease_until')::timestamptz<=%s)
                       AND COALESCE((d.value->>'retry_at')::timestamptz,
                                    '-infinity'::timestamptz)<=%s
                       AND (NOT (d.value ? 'content_ready') OR
                            d.value->'content_ready'='true'::jsonb OR created_at<=%s)
                       AND request_metadata->>'sentry_event_path' IN
                         ('IMMEDIATE_ANNOUNCEMENT_ONLY','ANNOUNCEMENT_AND_CONTEXTUAL_REASONING')
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
                             AND c.context_packet_id=r.context_packet_id
                             AND c.packet_digest=r.context_digest
                             AND e.delivery_class='GUARANTEED'
                             AND (e.source IN ('anima:senseguard-policy','anima.household_presence',
                                               'anima.ring','anima:durable-task')
                                  OR (e.source LIKE 'android-relay-report:%%'
                                      AND e.metadata->'synthetic'='false'::jsonb
                                      AND e.metadata->'producer_qualified'='true'::jsonb
                                      AND e.metadata->'wake_eligible'='true'::jsonb
                                      AND e.metadata->>'schema_qualification'='ANIMA_OWNED_SCHEMA'))
                       )
                       ORDER BY CASE WHEN (request_metadata->>'priority') ~ '^-?[0-9]+$'
                         THEN (request_metadata->>'priority')::integer ELSE 0 END DESC, created_at
                       FOR UPDATE SKIP LOCKED LIMIT 32""",
                    (household_id, at, at, at, at - timedelta(seconds=600)),
                )
                for row in cursor.fetchall():
                    request = _request_from_row(row)
                    root = dict(request.request_metadata.get("required_delivery") or {})
                    phase = "FOLLOWUP" if root.get("state") == "DELIVERED" else "CANONICAL"
                    saved = root["followup"] if phase == "FOLLOWUP" else root
                    state = saved.get("state", "PENDING")
                    if state in {"DELIVERED", "UNKNOWN", "ESCALATED", "CANCELLED"}:
                        continue
                    if state in {"CLAIMED", "PLAYBACK_INTENT"}:
                        if datetime.fromisoformat(saved["lease_until"]) > at:
                            continue
                        if state == "PLAYBACK_INTENT":
                            saved["state"] = "UNKNOWN"
                            saved["reason"] = "PLAYBACK_RECEIPT_LOST"
                            if "followup" in root:
                                root["followup"].update(
                                    state="ESCALATED", reason="CANONICAL_DELIVERY_UNKNOWN"
                                )
                            self._save(cursor, request.request_id, root)
                            continue
                    if at - row["created_at"] > timedelta(seconds=600):
                        saved.update(state="ESCALATED", reason="DELIVERY_EXPIRED")
                        if "followup" in root:
                            root["followup"].update(state="ESCALATED", reason="CANONICAL_EXPIRED")
                        self._save(cursor, request.request_id, root)
                        continue
                    if row["lifecycle"] == "CANCELLED":
                        # Context cancellation is not owner speech revocation.
                        # Retain explicit unresolved delivery escalation, not a
                        # silent SQL omission or permission inferred from a rule.
                        saved.update(state="ESCALATED", reason="CONTEXT_REQUEST_CANCELLED")
                        self._save(cursor, request.request_id, root)
                        continue
                    if saved.get("retry_at") and datetime.fromisoformat(saved["retry_at"]) > at:
                        continue
                    policy = disposition(request)
                    announcement = policy.get("announcement")
                    if not (
                        policy.get("allowed") is True
                        and policy.get("required") is True
                        and policy.get("reason") == "ALWAYS_NOTIFY"
                        and isinstance(announcement, dict)
                        and isinstance(announcement.get("text"), str)
                    ):
                        # A revoked/changed policy cannot acquire delivery authority.
                        if saved:
                            saved.update(state="CANCELLED", reason="CURRENT_POLICY_NOT_REQUIRED")
                            self._save(cursor, request.request_id, root)
                        continue
                    occurred = datetime.fromisoformat(str(announcement["occurred_at"]))
                    if occurred.tzinfo is None or not timedelta(0) <= at - occurred <= timedelta(
                        seconds=600
                    ):
                        saved.update(state="ESCALATED", reason="SOURCE_EVENT_STALE_OR_SKEWED")
                        self._save(cursor, request.request_id, root)
                        continue
                    token = secrets.token_urlsafe(32)
                    generation = int(saved.get("generation", 0)) + 1
                    saved.update(
                        state="CLAIMED",
                        generation=generation,
                        client_id=client_id,
                        active_instance_id=active_instance_id,
                        credential_generation=credential_generation,
                        token_digest=hashlib.sha256(token.encode()).hexdigest(),
                        lease_until=(at + timedelta(seconds=60)).isoformat(),
                        attempts=int(saved.get("attempts", 0)) + 1,
                        consumer_enable_epoch=not_before.isoformat(),
                        predates_enable_epoch=row["created_at"] < not_before,
                        initial_freshness_seconds=max_age_seconds,
                    )
                    self._save(cursor, request.request_id, root)
                    text = announcement["text"]
                    if at - occurred > timedelta(seconds=120):
                        text = "Delayed notification: " + text
                    return {
                        "status": "CLAIMED",
                        "request_id": str(request.request_id),
                        "generation": generation,
                        "delivery_token": token,
                        "active_instance_id": active_instance_id,
                        "phase": phase,
                        "eligibility_basis": "RETAINED_MANAGED_OBLIGATION",
                        "predates_enable_epoch": row["created_at"] < not_before,
                        "announcement": (
                            {"response_digest": saved["response_digest"]}
                            if phase == "FOLLOWUP"
                            else {**announcement, "text": text}
                        ),
                    }
        return {"status": "EMPTY"}

    def transition(
        self,
        request_id: UUID,
        *,
        household_id: UUID,
        client_id: str,
        token: str,
        generation: int,
        outcome: str,
        disposition: Callable[[Any], dict[str, Any]],
        now: datetime | None = None,
        active_instance_id: str = "office",
        credential_generation: int = 1,
        evidence: dict[str, Any] | None = None,
        phase: str = "CANONICAL",
    ) -> dict[str, Any]:
        at = now or datetime.now(UTC)
        if outcome not in {
            "PLAYBACK_INTENT",
            "DELIVERED",
            "UNSTARTED",
            "UNKNOWN",
            "CONTENT_UNAVAILABLE",
        }:
            raise ValueError("INVALID_ALERT_OUTCOME")
        with psycopg.connect(self.database_url, row_factory=dict_row) as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    "SELECT * FROM anima_intelligence_requests WHERE request_id=%s "
                    "AND household_id=%s FOR UPDATE",
                    (request_id, household_id),
                )
                row = cursor.fetchone()
                if row is None:
                    raise ValueError("ALERT_BINDING_LOST")
                root = dict(row["request_metadata"].get("required_delivery") or {})
                if phase not in {"CANONICAL", "FOLLOWUP"}:
                    raise ValueError("INVALID_DELIVERY_PHASE")
                if phase == "FOLLOWUP" and root.get("state") != "DELIVERED":
                    raise ValueError("CANONICAL_NOT_DELIVERED")
                saved = root.get("followup", {}) if phase == "FOLLOWUP" else root
                if (
                    saved.get("client_id") != client_id
                    or saved.get("generation") != generation
                    or saved.get("active_instance_id") != active_instance_id
                    or saved.get("credential_generation") != credential_generation
                    or not secrets.compare_digest(
                        str(saved.get("token_digest", "")),
                        hashlib.sha256(token.encode()).hexdigest(),
                    )
                    or datetime.fromisoformat(saved["lease_until"]) <= at
                ):
                    raise ValueError("ALERT_BINDING_LOST")
                state = saved.get("state")
                if outcome == "CONTENT_UNAVAILABLE" and state == "CLAIMED" and phase == "FOLLOWUP":
                    saved.update(state="ESCALATED", reason="FOLLOWUP_CONTENT_UNAVAILABLE")
                elif outcome == "PLAYBACK_INTENT":
                    policy = disposition(_request_from_row(row))
                    if state != "CLAIMED" or not (policy.get("allowed") and policy.get("required")):
                        raise ValueError("ALERT_AUTHORITY_CHANGED")
                    saved["state"] = outcome
                elif outcome == "UNSTARTED" and state in {"CLAIMED", "PLAYBACK_INTENT"}:
                    saved.update(
                        state="PENDING",
                        retry_at=(
                            at + timedelta(seconds=min(60, 2 ** min(int(saved["attempts"]), 6)))
                        ).isoformat(),
                    )
                elif state == "PLAYBACK_INTENT" and outcome in {"DELIVERED", "UNKNOWN"}:
                    if outcome == "DELIVERED" and not (
                        evidence
                        and evidence.get("playback_state") == "DELIVERED"
                        and evidence.get("timing_source")
                        in {"LOCAL_PLAYBACK_PROCESS", "PROJECTION_PLAYBACK_PROCESS"}
                        and isinstance(evidence.get("playback_completed_at"), str)
                    ):
                        raise ValueError("PLAYBACK_COMPLETION_EVIDENCE_REQUIRED")
                    saved.update(state=outcome, receipt_at=at.isoformat(), evidence=evidence or {})
                    if outcome == "UNKNOWN" and "followup" in root:
                        root["followup"].update(
                            state="ESCALATED", reason="CANONICAL_DELIVERY_UNKNOWN"
                        )
                else:
                    raise ValueError("ALERT_TRANSITION_CONFLICT")
                self._save(cursor, request_id, root)
        return {"status": "RECORDED", "delivery_status": saved["state"]}
