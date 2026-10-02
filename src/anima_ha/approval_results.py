"""Core-only verified outcome association, not a provider/action continuation.

Reuse request metadata, transition history and the ephemeral result publisher.
No private conversation text is retained. A scene child's approval never starts
another scene step or changes its aggregate into a fictitious completed scene.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import secrets
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID

from anima_ha.action import ActionRecord, ActionStatus, PendingApproval
from anima_ha.alert_delivery import playback_evidence, playback_not_started
from anima_ha.intelligence import (
    IntelligenceRequest,
    PostgresIntelligenceStore,
    _request_from_row,
)
from anima_ha.live_results import PostgresSentryLivePublisher


def originating_playback_evidence(evidence: Any) -> dict[str, Any]:
    """Typed content-free callback evidence, not arbitrary whitelisted prose."""
    return playback_evidence(evidence, invalid="INVALID_ORIGINATING_REPLY_RECEIPT")


def approval_presentation(outcome: dict[str, Any]) -> dict[str, Any]:
    """Fixed truthful prose from verified Core metadata, never stored transcript."""
    status = outcome["action_status"]
    decision = outcome["decision"]
    response = (
        "You rejected the action. It was not dispatched."
        if decision == "REJECT"
        else {
            "SUCCEEDED": "The approved action succeeded and its result was verified.",
            "POLICY_DENIED": "Current policy denied the approved action. It was not dispatched.",
            "REQUIRE_STRONGER_AUTH": "The action still requires stronger authentication.",
            "REQUIRE_CONFIRMATION": "The action still requires confirmation.",
            "UNKNOWN_RESULT": "The approved action's outcome is unknown. It will not be replayed.",
            "RECOVERY_REQUIRED": "The action needs recovery review. It will not be replayed.",
            "PARTIAL": "The approved action has a partial result. It will not be replayed.",
            "VERIFICATION_FAILED": "The approved action could not be verified.",
        }.get(
            status,
            "The approved action did not complete successfully. See its verified Activity record.",
        )
    )
    if outcome.get("scene_stopped"):
        response += " The saved scene remains incomplete; no remaining steps were started."
    return {
        "status": outcome["result_status"],
        "response": response,
        "detail": "CORE_VERIFIED_APPROVAL_OUTCOME",
        "provider_ambiguous": False,
    }


class ApprovalResults:
    def __init__(self, store: PostgresIntelligenceStore, actions: Any, pending: Any) -> None:
        self.store, self.actions, self.core_pending = store, actions, pending

    def associate(self, request: IntelligenceRequest, action_id: UUID) -> None:
        root = self.actions.get(action_id)
        if (
            root is None
            or root.household_id != request.household_id
            or request.principal_id is None
        ):
            return
        children = [str(action_id)]
        if root.tool_id == "anima.scenes.apply_scene":
            children += [str(step["action_id"]) for step in (root.result or {}).get("steps", [])]
        with self.store._connect() as connection:
            # Both records are Core-owned; model-supplied action references are
            # not association authority. Persist only pending exact children.
            rows = connection.execute(
                "SELECT action_id FROM anima_pending_approvals WHERE action_id=ANY(%s::uuid[]) "
                "AND household_id=%s AND principal_id=%s AND episode_id IS NULL",
                (children, request.household_id, request.principal_id),
            ).fetchall()
            for row in rows:
                association = {
                    "action_id": str(row["action_id"]),
                    "root_action_id": str(action_id),
                    "scene_stopped": root.tool_id == "anima.scenes.apply_scene",
                }
                connection.execute(
                    "UPDATE anima_intelligence_requests SET request_metadata="
                    "jsonb_set(request_metadata,'{approval_actions}',"
                    "COALESCE(request_metadata->'approval_actions','[]'::jsonb) || %s::jsonb) "
                    "WHERE request_id=%s AND household_id=%s AND principal_id=%s "
                    "AND claim_owner=%s AND fencing_generation=%s AND lease_expires_at>now() "
                    "AND lifecycle IN ('CLAIMED','DELIVERED_TO_PROVIDER','PROVIDER_RUNNING') "
                    "AND jsonb_array_length("
                    "COALESCE(request_metadata->'approval_actions','[]'))<32 "
                    "AND NOT COALESCE(request_metadata->'approval_actions','[]') @> %s::jsonb",
                    (
                        json.dumps([association]),
                        request.request_id,
                        request.household_id,
                        request.principal_id,
                        request.claim_owner,
                        request.fencing_generation,
                        json.dumps([association]),
                    ),
                )

    def resolve(
        self, pending: PendingApproval, action: ActionRecord, decision: str
    ) -> dict[str, Any] | None:
        if (
            pending.episode_id is not None
            or action.action_id != pending.action_id
            or (action.household_id != pending.household_id)
        ):
            return None
        with self.store._connect() as connection:
            rows = connection.execute(
                "SELECT * FROM anima_intelligence_requests WHERE household_id=%s AND "
                "principal_id=%s "
                "AND request_metadata->'approval_actions' @> %s::jsonb FOR UPDATE",
                (
                    pending.household_id,
                    pending.principal_id,
                    json.dumps([{"action_id": str(pending.action_id)}]),
                ),
            ).fetchall()
            if len(rows) != 1:
                return None
            row = rows[0]
            association = next(
                item
                for item in row["request_metadata"]["approval_actions"]
                if item["action_id"] == str(pending.action_id)
            )
            existing = row["result_metadata"].get("approval_outcome")
            if existing is not None:
                return {"request_id": str(row["request_id"]), **existing}
            if row["lifecycle"] not in {"WAITING_CONFIRMATION", "WAITING_STRONGER_AUTH"}:
                return None
            if action.status in {ActionStatus.PLANNED, ActionStatus.EXECUTING}:
                return None
            result, lifecycle = {
                ActionStatus.SUCCEEDED: ("TOOL_ACTIVITY_COMPLETED", "COMPLETED"),
                ActionStatus.REQUIRE_CONFIRMATION: ("WAITING_CONFIRMATION", "WAITING_CONFIRMATION"),
                ActionStatus.REQUIRE_STRONGER_AUTH: (
                    "WAITING_STRONGER_AUTH",
                    "WAITING_STRONGER_AUTH",
                ),
                ActionStatus.UNKNOWN_RESULT: ("UNKNOWN_RESULT", "UNKNOWN_RESULT"),
                ActionStatus.RECOVERY_REQUIRED: ("UNAVAILABLE", "RECOVERY_REQUIRED"),
                ActionStatus.PARTIAL: ("PARTIAL", "FAILED"),
            }.get(action.status, ("FAILED", "FAILED"))
            if association["scene_stopped"] and action.status == ActionStatus.SUCCEEDED:
                result, lifecycle = "PARTIAL", "FAILED"
            outcome = {
                **association,
                "approval_id": str(pending.approval_id),
                "decision": decision,
                "action_status": action.status.value,
                "result_status": result,
                "delivery": "PENDING"
                if (
                    row["origin"] == "DIRECT_SENTRY_INTERACTION"
                    and row["request_metadata"].get("direct_context", {}).get("source_surface")
                    == "always_on_voice"
                )
                else "LIVE_PRESENTATION_NOT_OBSERVED",
                "source": "CORE_VERIFIED_ACTION_RECORD",
                "resolved_at": datetime.now(UTC).isoformat(),
            }
            connection.execute(
                "UPDATE anima_intelligence_requests SET lifecycle=%s,result_status=%s,"
                "result_metadata=jsonb_set(result_metadata,'{approval_outcome}',%s::jsonb),"
                "updated_at=now(),completed_at=CASE WHEN %s IN "
                "('WAITING_CONFIRMATION','WAITING_STRONGER_AUTH') THEN NULL ELSE now() END "
                "WHERE request_id=%s",
                (lifecycle, result, json.dumps(outcome), lifecycle, row["request_id"]),
            )
            connection.execute(
                "INSERT INTO anima_intelligence_transitions "
                "(request_id,from_lifecycle,to_lifecycle,fencing_generation,actor,metadata) "
                "VALUES(%s,%s,%s,%s,'core:approval-result',%s::jsonb)",
                (
                    row["request_id"],
                    row["lifecycle"],
                    lifecycle,
                    row["fencing_generation"],
                    json.dumps(outcome),
                ),
            )
        payload = {
            "request_id": str(row["request_id"]),
            "household_id": str(pending.household_id),
            **approval_presentation(outcome),
        }
        try:
            PostgresSentryLivePublisher(self.store.database_url).publish(payload)
        except Exception:
            # Result is durable; transient listener failure must not replay an
            # approved action or a provider to manufacture another response.
            pass
        return {"request_id": str(row["request_id"]), **outcome}

    def outcome(
        self, request_id: UUID, household_id: UUID, principal_id: UUID
    ) -> dict[str, Any] | None:
        with self.store._connect() as connection:
            row = connection.execute(
                "SELECT result_metadata->'approval_outcome' AS outcome FROM "
                "anima_intelligence_requests "
                "WHERE request_id=%s AND household_id=%s AND principal_id=%s",
                (request_id, household_id, principal_id),
            ).fetchone()
        return row["outcome"] if row else None

    @staticmethod
    def _save_delivery(connection: Any, request_id: UUID, outcome: dict[str, Any]) -> None:
        connection.execute(
            "UPDATE anima_intelligence_requests SET result_metadata="
            "jsonb_set(result_metadata,'{approval_outcome}',%s::jsonb) WHERE request_id=%s",
            (json.dumps(outcome), request_id),
        )

    def delivery(
        self,
        household_id: UUID,
        client_id: str,
        credential_generation: int,
        instance: str,
        body: dict[str, Any],
        *,
        operation: str,
        authorize: Callable[[IntelligenceRequest, ActionRecord, PendingApproval], dict[str, Any]],
    ) -> dict[str, Any]:
        """Present only this client's verified direct voice outcome, no continuation.

        Reuse the request's existing outcome metadata and the resident playback
        receipt vocabulary. Never expose provider text, tools or an execution
        binding here. A possibly-started receipt cannot be adopted/replayed.
        """
        if operation == "receipt":
            body = {**body, "evidence": originating_playback_evidence(body["evidence"])}
        at = datetime.now(UTC)
        with self.store._connect() as connection:
            rows = connection.execute(
                "SELECT r.*,r.result_metadata->'approval_outcome' AS outcome, EXISTS ("
                "SELECT 1 FROM anima_graph_nodes person JOIN anima_graph_relationships member "
                "ON member.source_id=person.canonical_id AND member.target_id=r.household_id "
                "AND member.relationship_type='MEMBER_OF' AND member.retired_at IS NULL "
                "JOIN anima_graph_nodes household ON household.canonical_id=member.target_id "
                "WHERE person.canonical_id=r.principal_id AND person.kind='PERSON' "
                "AND person.retired_at IS NULL AND household.kind='HOUSEHOLD' "
                "AND household.retired_at IS NULL) AS current_member "
                "FROM anima_intelligence_requests r "
                "WHERE r.household_id=%s AND r.origin='DIRECT_SENTRY_INTERACTION' "
                "AND r.request_metadata->'direct_context'->>'source_surface'="
                "'always_on_voice' "
                "AND r.request_metadata->'direct_context'->>'service_client_id'=%s "
                "AND r.result_metadata->'approval_outcome'->>'source'="
                "'CORE_VERIFIED_ACTION_RECORD' "
                "AND (%s='receipt' OR r.result_metadata->'approval_outcome'->>'delivery' "
                "IN ('PENDING','CLAIMED','PLAYBACK_INTENT')) "
                "AND (%s::uuid IS NULL OR r.request_id=%s::uuid) "
                "ORDER BY r.updated_at,r.request_id LIMIT 10 FOR UPDATE OF r SKIP LOCKED",
                (
                    household_id,
                    client_id,
                    operation,
                    body.get("request_id"),
                    body.get("request_id"),
                ),
            ).fetchall()
            for row in rows:
                value = dict(row["outcome"])
                state = value["delivery"]
                action = self.actions.get(UUID(value["action_id"]))
                pending = self.core_pending.get(UUID(value["approval_id"]))
                # Recheck the exact durable source, not a model's action ID.
                if (
                    action is None
                    or pending is None
                    or action.household_id != household_id
                    or pending.household_id != household_id
                    or pending.principal_id != row["principal_id"]
                    or action.action_id != pending.action_id
                    or action.status.value != value["action_status"]
                ):
                    value.update(
                        delivery="UNKNOWN", delivery_reason="CURRENT_SOURCE_SCOPE_UNAVAILABLE"
                    )
                    self._save_delivery(connection, row["request_id"], value)
                    continue
                lease = value.get("delivery_lease_until")
                if (
                    state in {"CLAIMED", "PLAYBACK_INTENT"}
                    and lease
                    and datetime.fromisoformat(lease) <= at
                ):
                    value["delivery"] = "UNKNOWN" if state == "PLAYBACK_INTENT" else "PENDING"
                    self._save_delivery(connection, row["request_id"], value)
                    state = value["delivery"]
                if operation == "next":
                    if state != "PENDING":
                        continue
                    resolved_at = datetime.fromisoformat(value["resolved_at"])
                    if resolved_at > at:
                        continue
                    if at - resolved_at > timedelta(seconds=300):
                        value.update(
                            delivery="ESCALATED", delivery_reason="LIVE_REPLY_WINDOW_EXPIRED"
                        )
                        self._save_delivery(connection, row["request_id"], value)
                        continue
                    if not row["current_member"]:
                        permission = {"allowed": False, "reason": "CURRENT_MEMBERSHIP_UNAVAILABLE"}
                    else:
                        try:
                            permission = authorize(_request_from_row(row), action, pending)
                        except Exception:
                            permission = {
                                "allowed": False,
                                "reason": "CURRENT_PRESENTATION_UNAVAILABLE",
                            }
                    value["delivery_policy"] = permission.get("policy", {})
                    if permission.get("allowed") is not True:
                        value["delivery_reason"] = permission["reason"]
                        self._save_delivery(connection, row["request_id"], value)
                        return {
                            "status": "UNAVAILABLE",
                            "delivery_status": "NOT_ATTEMPTED",
                            "reason": permission["reason"],
                        }
                    token = secrets.token_urlsafe(32)
                    generation = int(value.get("delivery_generation", 0)) + 1
                    value.update(
                        delivery="CLAIMED",
                        delivery_generation=generation,
                        delivery_token_digest=hashlib.sha256(token.encode()).hexdigest(),
                        delivery_credential_generation=credential_generation,
                        delivery_instance=instance,
                        delivery_lease_until=(at + timedelta(seconds=60)).isoformat(),
                    )
                    self._save_delivery(connection, row["request_id"], value)
                    return {
                        "status": "CLAIMED",
                        "request_id": str(row["request_id"]),
                        "generation": generation,
                        "delivery_token": token,
                        "active_instance_id": instance,
                        "phase": "APPROVAL",
                        "announcement": {"text": approval_presentation(value)["response"]},
                    }
                if (
                    value.get("delivery_generation") != body["generation"]
                    or value.get("delivery_credential_generation") != credential_generation
                    or value.get("delivery_instance") != instance
                    or not hmac.compare_digest(
                        value.get("delivery_token_digest", ""),
                        hashlib.sha256(body["delivery_token"].encode()).hexdigest(),
                    )
                ):
                    return {"status": "UNAVAILABLE", "delivery_status": "NOT_ATTEMPTED"}
                outcome = body["outcome"]
                if outcome == "PLAYBACK_INTENT":
                    if not row["current_member"]:
                        permission = {"allowed": False, "reason": "CURRENT_MEMBERSHIP_UNAVAILABLE"}
                    else:
                        try:
                            permission = authorize(_request_from_row(row), action, pending)
                        except Exception:
                            permission = {
                                "allowed": False,
                                "reason": "CURRENT_PRESENTATION_UNAVAILABLE",
                            }
                    value["delivery_policy"] = permission.get("policy", {})
                    if permission.get("allowed") is not True:
                        value["delivery_reason"] = permission["reason"]
                        self._save_delivery(connection, row["request_id"], value)
                        return {
                            "status": "UNAVAILABLE",
                            "delivery_status": state,
                            "reason": permission["reason"],
                        }
                allowed = {
                    "CLAIMED": {"PLAYBACK_INTENT": "PLAYBACK_INTENT", "UNSTARTED": "PENDING"},
                    "PLAYBACK_INTENT": {
                        "DELIVERED": "DELIVERED",
                        "UNKNOWN": "UNKNOWN",
                        "UNSTARTED": "PENDING",
                    },
                }
                target = allowed.get(state, {}).get(outcome)
                if target is None:
                    return {"status": "UNAVAILABLE", "delivery_status": state}
                # A pre-intent busy receipt proves no speaker was invoked.
                # After intent only an explicit consistent playback-owner
                # receipt may reopen delivery; silence is not proof of no start.
                evidence = body["evidence"]
                if (
                    state == "PLAYBACK_INTENT"
                    and outcome == "UNSTARTED"
                    and not playback_not_started(evidence)
                ):
                    target = "UNKNOWN"
                    value["delivery_reason"] = "POST_INTENT_NO_START_NOT_ESTABLISHED"
                value.update(
                    delivery=target,
                    delivery_observed_at=at.isoformat(),
                    delivery_evidence=body["evidence"],
                )
                self._save_delivery(connection, row["request_id"], value)
                return {
                    "status": "RECORDED",
                    "delivery_status": target,
                    "delivery_scope": "PLAYBACK_CALLBACK_NOT_HUMAN_OR_PHYSICAL_VERIFICATION",
                }
        return {"status": "EMPTY"}

    def reconcile_request(self, request: IntelligenceRequest) -> None:
        """Approval can precede the provider's initial gate result; never replay."""
        current = self.store.get(request.request_id)
        if current is None:
            return
        for association in current.request_metadata.get("approval_actions", []):
            with self.store._connect() as connection:
                row = connection.execute(
                    "SELECT approval_id FROM anima_pending_approvals WHERE action_id=%s "
                    "AND household_id=%s AND principal_id=%s AND status IN ('APPROVED','REJECTED')",
                    (association["action_id"], request.household_id, request.principal_id),
                ).fetchone()
            if row is not None:
                pending = self.core_pending.get(row["approval_id"])
                action = self.actions.get(UUID(association["action_id"]))
                if pending is not None and action is not None:
                    self.resolve(pending, action, pending.decision or "APPROVE")
