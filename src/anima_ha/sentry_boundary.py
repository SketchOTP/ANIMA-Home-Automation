"""The narrow, Core-owned boundary used by the SENTRY intelligence process.

SENTRY is allowed to reason, select from the registered catalogue, and return
structured results.  It is not allowed to connect to PostgreSQL or Home
Assistant itself.  Every household read or mutation in this module is routed
through the already accepted ANIMA services, policy checks, and (for
consequential tools) the Phase 9 action coordinator.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Callable
from contextlib import nullcontext
from dataclasses import dataclass, replace
from datetime import UTC, datetime, timedelta
from typing import Any, Protocol
from uuid import UUID, uuid5

from anima_ha.action import ActionRecord, ActionRequest, PendingApproval, resolve_action_safety_spec
from anima_ha.intelligence import (
    IntelligenceLifecycle,
    IntelligenceOrigin,
    IntelligenceRequest,
    IntelligenceRequestFactory,
    IntelligenceResult,
    IntelligenceResultStatus,
    IntelligenceStore,
)
from anima_ha.plugins import (
    ExecutionBoundary,
    InvocationContext,
    InvocationResult,
    PluginManager,
    ToolDescriptor,
    public_invocation_status,
)
from anima_ha.policy import (
    ActionIntent,
    Assurance,
    Decision,
    EvidenceType,
    IdentityAggregator,
    IdentityContext,
    IdentityEvidence,
    PolicyContext,
    RequestOrigin,
)
from anima_ha.scene_application import SceneApplication

SENTRY_BOUNDARY_VERSION = "1"
_INVOCATION_NAMESPACE = UUID("8ed25308-c6a7-45ee-85ff-c6d4e572a58f")


class SentryBoundaryError(RuntimeError):
    """A request could not be served by the trusted Core boundary."""


@dataclass(frozen=True, slots=True)
class SentryIdentityEvidenceEnvelope:
    """Untrusted SENTRY observations translated into ANIMA evidence classes."""

    endpoint_id: str
    profile_state: str
    confidence: int
    observed_at: datetime
    local_proximity: bool = False
    spoken_identity_claim: str | None = None
    state: str = "recognized"

    def to_anima_evidence(self, household_id: UUID, principal_id: UUID | None) -> IdentityEvidence:
        observed = self.observed_at.astimezone(UTC)
        evidence_usable = (
            self.state.casefold() == "recognized" and self.profile_state.casefold() == "recognized"
        )
        # Recognition, proximity, and voice are never allowed to mint
        # AUTHENTICATED or STRONG_AUTHENTICATED evidence.
        return IdentityEvidence(
            evidence_id=uuid5(
                _INVOCATION_NAMESPACE,
                f"sentry-evidence:{household_id}:{self.endpoint_id}:{observed.isoformat()}",
            ),
            household_id=household_id,
            claimed_principal_id=principal_id if evidence_usable else None,
            evidence_type=(
                EvidenceType.LOCAL_PROXIMITY
                if self.local_proximity
                else EvidenceType.OTHER_PROVIDER_EVIDENCE
            ),
            issuer="sentry",
            issued_at=observed,
            observed_at=observed,
            expires_at=observed + timedelta(minutes=5),
            assurance=Assurance.RECOGNIZED,
            strength=min(max(self.confidence, 0), 50),
            provenance=f"sentry:{self.profile_state}:{self.state}",
            reference=self.endpoint_id[:256],
            metadata={
                "voice_claim_present": self.spoken_identity_claim is not None,
                "sentry_state": self.state,
                "usable_for_principal_candidate": evidence_usable,
            },
        )


@dataclass(frozen=True, slots=True)
class SentryBoundaryHealth:
    provider_id: str
    state: str
    version: str = SENTRY_BOUNDARY_VERSION
    detail: str | None = None
    journal_handoff_state: str | None = None

    def to_payload(self) -> dict[str, str | None]:
        payload = {
            "provider_id": self.provider_id,
            "state": self.state,
            "version": self.version,
            "detail": self.detail,
        }
        if self.journal_handoff_state is not None:
            payload["journal_handoff_state"] = self.journal_handoff_state
        return payload


def _origin(value: IntelligenceOrigin) -> RequestOrigin:
    return {
        IntelligenceOrigin.DIRECT_UI_USER: RequestOrigin.DIRECT_USER,
        IntelligenceOrigin.DIRECT_SENTRY_INTERACTION: RequestOrigin.DIRECT_USER,
        IntelligenceOrigin.AUTONOMOUS_ATTENTION: RequestOrigin.AUTONOMOUS_AGENT,
        IntelligenceOrigin.DURABLE_TASK: RequestOrigin.DURABLE_SYSTEM_TASK,
        IntelligenceOrigin.APPROVAL_RESOLUTION: RequestOrigin.DIRECT_USER,
        IntelligenceOrigin.TESTING: RequestOrigin.TESTING,
    }[value]


def _identity(request: IntelligenceRequest) -> IdentityContext:
    """Translate stored provenance; this never upgrades an anonymous caller."""
    assurance = (
        Assurance.AUTHENTICATED
        if request.principal_id is not None
        and request.origin
        in {IntelligenceOrigin.DIRECT_UI_USER, IntelligenceOrigin.APPROVAL_RESOLUTION}
        else Assurance.RECOGNIZED
    )
    return IdentityContext(
        request.household_id,
        request.principal_id,
        assurance,
        explanation="ANIMA-issued intelligence invocation context",
    )


@dataclass(slots=True)
class CoreSentryBoundary:
    """Typed operations exposed to SENTRY by the ANIMA composition root."""

    manager: PluginManager
    policy_service: Any
    intelligence_store: IntelligenceStore
    action_executor: Any | None = None
    action_refresher: Callable[[tuple[UUID, ...]], Any] | None = None
    action_verifier: Callable[[Any, InvocationResult, Any], Any] | None = None
    context_loader: Callable[[UUID], dict[str, Any] | None] | None = None
    notification_context_loader: Callable[[IntelligenceRequest], dict[str, Any]] | None = None
    reasoning_context_loader: Callable[[IntelligenceRequest], dict[str, Any]] | None = None
    policy_role_resolver: Callable[[UUID], str | None] | None = None
    access_level_resolver: Callable[[UUID], str] | None = None
    agent_memory_enabled: bool = False
    learning_service: Any | None = None
    sensor_status_loader: Callable[[UUID], dict[str, Any]] | None = None
    journal_handoff_status_loader: Callable[[], str] | None = None
    scene_application: SceneApplication | None = None
    owner_task_guard: Callable[[IntelligenceRequest], Any] | None = None
    approval_results: Any | None = None

    def health(self) -> SentryBoundaryHealth:
        return SentryBoundaryHealth(
            "anima-core",
            "available",
            journal_handoff_state=(
                self.journal_handoff_status_loader() if self.journal_handoff_status_loader else None
            ),
        )

    def sensor_status(self, household_id: UUID) -> dict[str, Any]:
        """Return only the bounded live-signal projection for one household."""
        if self.sensor_status_loader is None:
            raise SentryBoundaryError("SENSOR_STATUS_UNAVAILABLE")
        payload = self.sensor_status_loader(household_id)
        if not isinstance(payload, dict) or str(payload.get("status")) != "CURRENT":
            raise SentryBoundaryError("SENSOR_STATUS_UNAVAILABLE")
        return payload

    def claim_request(
        self,
        worker_id: str,
        *,
        household_id: UUID | None = None,
        excluded_origins: frozenset[IntelligenceOrigin] = frozenset(),
    ) -> IntelligenceRequest | None:
        # A SENTRY worker can claim only requests explicitly addressed to the
        # SENTRY provider; it must never consume another provider's queue.
        return self.intelligence_store.claim(
            worker_id,
            provider_id="sentry",
            household_id=household_id,
            excluded_origins=excluded_origins,
        )

    def claim_specific_request(
        self, request_id: UUID, worker_id: str, household_id: UUID
    ) -> IntelligenceRequest | None:
        return self.intelligence_store.claim_specific(
            request_id,
            worker_id,
            household_id=household_id,
            provider_id="sentry",
        )

    def start_provider(self, request: IntelligenceRequest, worker_id: str) -> bool:
        """Fence the provider boundary before any SENTRY model code runs."""
        try:
            self._assert_active(request)
        except SentryBoundaryError:
            return False
        if request.claim_owner != worker_id:
            return False
        if request.lifecycle == IntelligenceLifecycle.PROVIDER_RUNNING:
            return True
        if request.lifecycle not in {
            IntelligenceLifecycle.CLAIMED,
            IntelligenceLifecycle.DELIVERED_TO_PROVIDER,
        }:
            return False
        return self.intelligence_store.transition(
            request.request_id,
            worker_id,
            request.fencing_generation,
            IntelligenceLifecycle.PROVIDER_RUNNING,
            {"provider_invocation_started": True, "provider": "sentry"},
        )

    def renew_request(
        self, request: IntelligenceRequest, worker_id: str, model_call: dict[str, Any] | None = None
    ) -> bool:
        if request.claim_owner != worker_id:
            return False
        if request.lifecycle not in {
            IntelligenceLifecycle.CLAIMED,
            IntelligenceLifecycle.DELIVERED_TO_PROVIDER,
            IntelligenceLifecycle.PROVIDER_RUNNING,
        }:
            return False
        if model_call is not None:
            return self.intelligence_store.renew(
                request.request_id,
                worker_id,
                request.fencing_generation,
                model_call=model_call,
            )
        return self.intelligence_store.renew(
            request.request_id,
            worker_id,
            request.fencing_generation,
        )

    def request_context(self, request: IntelligenceRequest) -> dict[str, Any]:
        packet = dict(self._request_context(request))
        if self.reasoning_context_loader is not None:
            support = self.reasoning_context_loader(request)
            # Context enrichment is live, non-authoritative and not written back
            # into the original immutable packet/request or its digest.
            enriched = {**packet, "household_context": support}
            if len(json.dumps(enriched).encode()) <= 60000:
                packet["household_context"] = support
            else:
                # Initiative is a Core-owned, request-bound authorization and
                # mandatory-alert decision. It must survive context-size
                # reduction even when optional household history/preferences
                # make the full support packet too large. Dropping it here
                # turns a valid required alert into an indistinguishable
                # UNAVAILABLE result at the SENTRY boundary.
                reduced: dict[str, Any] = {"status": "CONTEXT_LIMIT_REQUIRES_SCOPED_READ"}
                if isinstance(support, dict):
                    initiative = support.get("initiative")
                    if isinstance(initiative, dict):
                        reduced["initiative"] = initiative
                packet["household_context"] = reduced
        return packet

    def request_notification(self, request: IntelligenceRequest) -> dict[str, Any]:
        """Return only Core's compact disposition for an autonomous event.

        Mandatory alerts must not depend on the larger household reasoning
        context. This response exposes no tools, memory, routine history,
        model prompt, or optional context; it contains only the fresh,
        request-bound Core decision and canonical announcement.
        """
        if request.origin not in {
            IntelligenceOrigin.AUTONOMOUS_ATTENTION,
            IntelligenceOrigin.DURABLE_TASK,
        }:
            raise SentryBoundaryError("NOTIFICATION_NOT_UNSOLICITED")
        initiative: dict[str, Any] | None
        loader = self.notification_context_loader
        if loader is not None:
            initiative = loader(request)
        elif self.reasoning_context_loader is not None:
            support = self.reasoning_context_loader(request)
            initiative = support.get("initiative") if isinstance(support, dict) else None
        else:
            raise SentryBoundaryError("NOTIFICATION_CONTEXT_UNAVAILABLE")
        if not isinstance(initiative, dict):
            raise SentryBoundaryError("NOTIFICATION_CONTEXT_INVALID")
        status = initiative.get("status")
        return {
            "household_context": {
                "status": status if isinstance(status, str) else "UNAVAILABLE",
                "initiative": {
                    "status": status if isinstance(status, str) else "UNAVAILABLE",
                    "notification": (
                        initiative.get("notification")
                        if isinstance(initiative.get("notification"), dict)
                        else {}
                    ),
                },
            }
        }

    def _request_context(self, request: IntelligenceRequest) -> dict[str, Any]:
        if self.context_loader is None:
            direct = request.request_metadata.get("direct_context")
            if isinstance(direct, dict):
                return dict(direct)
            raise SentryBoundaryError("CONTEXT_BOUNDARY_UNAVAILABLE")
        if request.trigger_id is None:
            direct = request.request_metadata.get("direct_context")
            if isinstance(direct, dict):
                return dict(direct)
            raise SentryBoundaryError("CONTEXT_TRIGGER_UNAVAILABLE")
        packet = self.context_loader(request.trigger_id)
        if packet is None:
            raise SentryBoundaryError("CONTEXT_PACKET_UNAVAILABLE")
        if str(packet.get("household_id", request.household_id)) != str(request.household_id):
            raise SentryBoundaryError("CONTEXT_HOUSEHOLD_MISMATCH")
        return packet

    def create_direct_request(
        self,
        *,
        household_id: UUID,
        sentry_request_id: str,
        source_surface: str,
        user_text: str,
        identity_evidence_refs: tuple[str, ...] = (),
        principal_id: UUID | None = None,
        service_client_id: str = "unscoped",
        identity_context: IdentityContext | None = None,
    ) -> IntelligenceRequest:
        """Create direct SENTRY work without consuming autonomous Attention."""
        request = IntelligenceRequestFactory.for_direct_sentry_interaction(
            sentry_request_id=sentry_request_id,
            household_id=household_id,
            source_surface=source_surface,
            user_text=user_text,
            tools=self.manager.list_tools(),
            principal_id=principal_id,
            identity_evidence_refs=identity_evidence_refs,
            service_client_id=service_client_id,
            identity_context=identity_context.to_payload() if identity_context else None,
        )
        return self.intelligence_store.enqueue(request)

    def persist_sentry_identity(
        self,
        household_id: UUID,
        envelope: SentryIdentityEvidenceEnvelope,
        *,
        profile_principal_id: UUID | None = None,
    ) -> tuple[IdentityEvidence, IdentityContext]:
        """Persist one bounded SENTRY observation before request creation."""
        evidence = envelope.to_anima_evidence(household_id, profile_principal_id)
        recorder = getattr(self.policy_service, "record_evidence", None)
        if callable(recorder):
            recorder(evidence)
        return evidence, IdentityAggregator().aggregate(household_id, [evidence])

    def record_sentry_identity(
        self,
        request: IntelligenceRequest,
        envelope: SentryIdentityEvidenceEnvelope,
        *,
        profile_principal_id: UUID | None = None,
    ) -> IdentityContext:
        """Persist bounded SENTRY evidence and aggregate it without escalation."""
        _evidence, context = self.persist_sentry_identity(
            request.household_id, envelope, profile_principal_id=profile_principal_id
        )
        return context

    @staticmethod
    def _schema_digest(schema: dict[str, Any]) -> str:
        return hashlib.sha256(
            json.dumps(schema, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest()

    def catalogue(self, request: IntelligenceRequest) -> list[dict[str, Any]]:
        """Return only tools frozen for this request and still compatible."""
        current = {tool.tool_id: tool for tool in self.manager.list_tools()}
        result: list[dict[str, Any]] = []
        for original in request.catalogue:
            tool_id = str(original.get("tool_id", ""))
            tool = current.get(tool_id)
            expected_schema = str(original.get("schema_digest", ""))
            compatible = (
                tool is not None
                and tool.availability
                and tool.plugin_id == original.get("plugin_id")
                and tool.version == original.get("version")
                and self._schema_digest(tool.input_schema) == expected_schema
                and tool.output_schema == original.get("output_schema")
            )
            if compatible:
                assert tool is not None
                payload = tool.to_payload()
                payload["schema_digest"] = expected_schema
                if not self.agent_memory_enabled and tool_id in {
                    "anima.knowledge.create_note",
                    "anima.knowledge.update_note",
                    "anima.knowledge.retract_note",
                    "anima.knowledge.purge_expired",
                    "anima.household-learning.propose",
                    "anima.household-learning.record_incident_assessment",
                }:
                    payload["availability"] = False
                    payload["unavailable_reason"] = "AGENT_MEMORY_NOT_ENABLED"
                result.append(payload)
            else:
                unavailable = dict(original)
                unavailable["availability"] = False
                unavailable["unavailable_reason"] = "DISABLED_OR_INCOMPATIBLE"
                result.append(unavailable)
        return result

    def _assert_active(self, request: IntelligenceRequest, *, owner_guard: bool = True) -> None:
        if owner_guard and self.owner_task_guard is not None:
            try:
                self.owner_task_guard(request)
            except Exception:
                raise SentryBoundaryError("OWNER_TASK_CURRENT_SCOPE_UNAVAILABLE") from None
        current = self.intelligence_store.get(request.request_id)
        if current is None or current.claim_owner is None:
            raise SentryBoundaryError("INTELLIGENCE_REQUEST_NOT_FOUND")
        if (
            current.claim_owner != request.claim_owner
            or current.fencing_generation != request.fencing_generation
            or current.lifecycle
            not in {
                IntelligenceLifecycle.CLAIMED,
                IntelligenceLifecycle.DELIVERED_TO_PROVIDER,
                IntelligenceLifecycle.PROVIDER_RUNNING,
            }
            or current.lease_expires_at is None
            or current.lease_expires_at <= datetime.now(UTC)
        ):
            raise SentryBoundaryError("INTELLIGENCE_CLAIM_LOST")

    def _tool(self, tool_id: str) -> ToolDescriptor:
        tool = next((item for item in self.manager.list_tools() if item.tool_id == tool_id), None)
        if tool is None or not tool.availability:
            raise SentryBoundaryError("TOOL_UNAVAILABLE")
        return tool

    def _request_tool(self, request: IntelligenceRequest, tool_id: str) -> ToolDescriptor:
        bound = next((item for item in request.catalogue if item.get("tool_id") == tool_id), None)
        if bound is None:
            raise SentryBoundaryError("TOOL_NOT_BOUND_TO_REQUEST")
        tool = self._tool(tool_id)
        if (
            tool.plugin_id != bound.get("plugin_id")
            or tool.version != bound.get("version")
            or self._schema_digest(tool.input_schema) != bound.get("schema_digest")
            or tool.output_schema != bound.get("output_schema")
        ):
            raise SentryBoundaryError("TOOL_BINDING_INCOMPATIBLE")
        return tool

    def _access_level(self, request: IntelligenceRequest) -> str:
        """Resolve the server-owned SENTRY access level for this principal.

        The value is never accepted from a SENTRY request or model argument.
        Missing identity stays LIMITED, which is the safe default for direct
        voice interactions whose evidence has not independently authenticated
        a household principal.
        """
        # Test/deterministic boundaries constructed without a commissioned
        # resolver retain their pre-existing policy behavior. The normal
        # composition root always supplies the resolver, where missing identity
        # is intentionally LIMITED.
        if self.access_level_resolver is None:
            return "UNRESTRICTED"
        if request.principal_id is None:
            return "LIMITED"
        value = str(self.access_level_resolver(request.principal_id)).strip().upper()
        if value not in {"LIMITED", "UNRESTRICTED"}:
            raise SentryBoundaryError("ACCESS_LEVEL_INVALID")
        return value

    def approval_presentation_authority(
        self,
        request: IntelligenceRequest,
        action: ActionRecord,
        pending: PendingApproval,
        *,
        instance: str,
    ) -> dict[str, Any]:
        """Authorize only presentation of this principal's verified direct result.

        The caller has locked and checked the exact Core request/action/approval
        and current membership. Reuse the configured notification policy, not
        an anonymous status probe or the action's execution permission. LIMITED
        may receive its own fixed outcome; this grants no household tools.
        """
        if (
            request.origin != IntelligenceOrigin.DIRECT_SENTRY_INTERACTION
            or request.principal_id is None
            or request.principal_id != pending.principal_id
            or request.household_id != action.household_id
            or request.household_id != pending.household_id
            or action.action_id != pending.action_id
            or self.policy_role_resolver is None
            or self.access_level_resolver is None
        ):
            return {"allowed": False, "reason": "CURRENT_ORIGINATING_SCOPE_UNAVAILABLE"}
        role = self.policy_role_resolver(request.principal_id)
        access = self._access_level(request)
        # Graph person-management calls household residents 'member'; retain
        # the actual label in OPA rather than remapping execution permissions.
        if role not in {"owner", "member", "resident"}:
            return {"allowed": False, "reason": "CURRENT_ORIGINATING_PRINCIPAL_NOT_ALLOWED"}
        identity = _identity(request)
        recorded = request.request_metadata.get("identity_context", {})
        if recorded:
            if (
                recorded.get("household_id") != str(request.household_id)
                or recorded.get("principal_id") != str(request.principal_id)
                or recorded.get("conflicting_principals") is not False
            ):
                return {"allowed": False, "reason": "ORIGINATING_IDENTITY_PROVENANCE_UNAVAILABLE"}
            identity = IdentityContext(
                request.household_id,
                request.principal_id,
                Assurance(recorded["assurance"]),
                tuple(UUID(str(value)) for value in recorded.get("evidence_ids", [])),
                explanation="Core-recorded originating identity, no approval-derived upgrade",
            )
        decision = self.policy_service.evaluate(
            ActionIntent.create(
                household_id=request.household_id,
                principal_id=request.principal_id,
                semantic_action="notifications.send",
                origin=RequestOrigin.DURABLE_SYSTEM_TASK,
                graph_metadata={"external_side_effect": True},
                correlation_id=str(request.request_id),
                causation_id=str(action.action_id),
            ),
            identity,
            PolicyContext(
                principal_role=role,
                graph_metadata={
                    # Derived only from the exact current verified Core association,
                    # never supplied by a service/model or an autonomous opt-in.
                    "notification_alert_authorized": True,
                    "notification_route_id": f"sentry-originating-result:{instance}",
                    "alert_policy_id": str(pending.approval_id),
                    "originating_request_id": str(request.request_id),
                    "verified_action_id": str(action.action_id),
                    "originating_principal_id": str(request.principal_id),
                    "sentry_access": access,
                },
            ),
        )
        return {
            "allowed": decision.decision == Decision.ALLOW,
            "reason": decision.reason_code,
            "policy": {
                "decision": decision.decision.value,
                "policy_version": decision.policy_version,
                "assurance": identity.assurance.value,
                "principal_role": role,
                "sentry_access": access,
            },
        }

    @staticmethod
    def _limited_tool_allowed(
        tool: ToolDescriptor, arguments: dict[str, Any], principal_id: UUID | None
    ) -> bool:
        """Keep limited SENTRY users inside read and personal-preference scope."""
        if getattr(tool, "read_only", False):
            return True
        if principal_id is None or tool.tool_id not in {
            "anima.household-preferences.create_preference",
            "anima.household-preferences.update_preference",
        }:
            return False
        # A limited principal may express or correct only their own personal
        # preference. Omitting person_id would otherwise write household-wide
        # guidance, so it is deliberately rejected here.
        return str(arguments.get("person_id", "")) == str(principal_id)

    def invoke_tool(
        self,
        request: IntelligenceRequest,
        tool_id: str,
        arguments: dict[str, Any],
        *,
        ordinal: int = 1,
    ) -> dict[str, Any]:
        """Invoke one registered semantic tool using ANIMA-owned identity.

        A provider/HA tool may never be called through a raw runtime here:
        consequential descriptors are converted to ActionRequest and pass the
        existing coordinator, while all other tools pass through PluginManager
        and Phase 4 policy.
        """
        if ordinal < 1:
            raise SentryBoundaryError("INVALID_TOOL_ORDINAL")
        self._assert_active(request)
        tool = self._request_tool(request, tool_id)
        knowledge_tool = tool.tool_id in {
            "anima.knowledge.create_note",
            "anima.knowledge.update_note",
            "anima.knowledge.retract_note",
            "anima.knowledge.purge_expired",
        }
        # Learning proposals are agent-maintained, source-bound memory. They
        # use the same explicit autonomy gate as knowledge notes, but belong
        # to the learning plugin and therefore need a separate source check.
        learning_proposal = tool.tool_id in {
            "anima.household-learning.propose",
            "anima.household-learning.record_incident_assessment",
        }
        agent_memory_tool = knowledge_tool or learning_proposal
        limited_allowed = self._limited_tool_allowed(tool, arguments, request.principal_id)
        # Exact agent-maintained knowledge remains non-authoritative even when
        # the speaker is unidentified. It still passes the dedicated deployment
        # gate, exact builtin-source check, and current OPA autonomy decision
        # below. This exception cannot change roles, preferences, devices or HA.
        if agent_memory_tool and self.agent_memory_enabled:
            limited_allowed = True
        if self._access_level(request) == "LIMITED" and not limited_allowed:
            return {
                "status": "DENIED",
                "operation": tool.tool_id,
                "reason": "USER_ACCESS_LIMITED",
            }
        if (
            request.origin
            in {IntelligenceOrigin.AUTONOMOUS_ATTENTION, IntelligenceOrigin.DURABLE_TASK}
            and tool.tool_id == "anima.external.notifications.send"
        ):
            # This is a delivery ceiling, not a replacement for current OPA.
            # Evaluate live owner settings; model arguments cannot supply permission.
            permission: dict[str, Any] = {}
            if self.reasoning_context_loader is not None:
                try:
                    permission = (
                        self.reasoning_context_loader(request)
                        .get("initiative", {})
                        .get("notification", {})
                    )
                except Exception:
                    pass
            if permission.get("allowed") is not True or permission.get("request_id") != str(
                request.request_id
            ):
                return {
                    "status": "DENIED",
                    "operation": tool.tool_id,
                    "reason": "UNSOLICITED_NOTIFICATION_NOT_ELIGIBLE",
                }
        identity = _identity(request)
        origin = _origin(request.origin)
        if learning_proposal:
            if not self.agent_memory_enabled or self.learning_service is None:
                return {
                    "status": "DENIED",
                    "operation": tool.tool_id,
                    "reason": "AGENT_LEARNING_NOT_ENABLED",
                }
            plugin = self.manager.plugins.get(tool.plugin_id)
            if plugin is None or plugin.manifest.source != "builtin:anima_ha.household_learning":
                raise SentryBoundaryError("AGENT_LEARNING_SOURCE_INVALID")
            origin = RequestOrigin.AUTONOMOUS_AGENT
        if knowledge_tool:
            if not self.agent_memory_enabled:
                return {
                    "status": "DENIED",
                    "operation": tool.tool_id,
                    "reason": "AGENT_MEMORY_NOT_ENABLED",
                }
            plugin = self.manager.plugins.get(tool.plugin_id)
            if plugin is None or plugin.manifest.source != "builtin:anima_ha.knowledge":
                raise SentryBoundaryError("AGENT_MEMORY_SOURCE_INVALID")
            # A note is agent-maintained data, not an authenticated user action.
            # Existing OPA explicit autonomy policy still authorizes or denies it.
            # This deployment grant cannot authorize preferences, roles or HA.
            origin = RequestOrigin.AUTONOMOUS_AGENT
        digest = hashlib.sha256(
            json.dumps(arguments, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest()
        invocation_context = InvocationContext(
            household_id=request.household_id,
            principal_id=request.principal_id,
            episode_id=None,
            tool_request_id=uuid5(
                _INVOCATION_NAMESPACE, f"{request.request_id}:{ordinal}:{digest}"
            ),
            ordinal=ordinal,
            system_idempotency_key=f"{request.idempotency_key}:tool:{ordinal}",
            origin=origin,
        )
        role = (
            self.policy_role_resolver(request.principal_id)
            if (self.policy_role_resolver is not None and request.principal_id is not None)
            else None
        )
        policy_context = PolicyContext(principal_role=role)
        if tool.tool_id == "anima.scenes.apply_scene":
            if self.scene_application is None:
                raise SentryBoundaryError("SCENE_APPLICATION_UNAVAILABLE")

            def scene_guard() -> None:
                self._assert_active(request)
                self._request_tool(request, tool.tool_id)
                self._request_tool(request, "anima.provider.home-assistant.set_power")

            scene_result = self.scene_application.apply(
                dict(arguments),
                identity=identity,
                origin=origin,
                idempotency_key=invocation_context.system_idempotency_key,
                guard=scene_guard,
            )
            if self.approval_results is not None and scene_result.get("action_id"):
                self.approval_results.associate(request, UUID(scene_result["action_id"]))
            return scene_result
        if tool.execution_boundary == ExecutionBoundary.COORDINATED_CONSEQUENTIAL:
            if self.action_executor is None:
                raise SentryBoundaryError("ACTION_COORDINATOR_UNAVAILABLE")
            safety_spec = resolve_action_safety_spec(tool)
            if safety_spec is None:
                raise SentryBoundaryError("TRUSTED_ACTION_SPEC_UNAVAILABLE")
            execution = self.action_executor.execute(
                ActionRequest.create(
                    idempotency_key=f"{request.idempotency_key}:action:{ordinal}",
                    household_id=request.household_id,
                    tool=tool,
                    arguments=dict(arguments),
                    identity=identity,
                    policy_service=self.policy_service,
                    policy_context=policy_context,
                    refresher=self.action_refresher,
                    verifier=self.action_verifier,
                    origin=origin,
                    safety_spec=safety_spec,
                )
            )
            if self.approval_results is not None:
                self.approval_results.associate(request, execution.record.action_id)
            return {
                "status": execution.record.status.value,
                "action_id": str(execution.record.action_id),
                "operation": tool.tool_id,
                "detail": execution.record.detail,
                "result": execution.record.result,
                "evidence": {
                    "connector_outcome": execution.invocation.outcome.value
                    if execution.invocation
                    else None,
                    "observed_at": datetime.now(UTC).isoformat(),
                },
            }
        scope: Any = nullcontext()
        if tool.tool_id == "anima.household-learning.propose":
            from anima_ha.household_learning import learning_request_scope

            assert self.learning_service is not None
            evidence = self.learning_service.evidence(request.household_id, limit=2000)
            packet = self.learning_service.ensure_review_packet(request)
            scope = learning_request_scope(
                request.request_id,
                request.household_id,
                (item["event_id"] for item in evidence["items"]),
                packet.get("candidates", []) if packet else [],
            )
        elif tool.tool_id == "anima.household-learning.record_incident_assessment":
            from anima_ha.household_learning import learning_request_scope

            if self.learning_service is None or self.reasoning_context_loader is None:
                raise SentryBoundaryError("INCIDENT_CONTEXT_UNAVAILABLE")
            context = self.reasoning_context_loader(request)
            evidence = context.get("initiative", {}).get("nearby_events", {}).get("items", [])
            scope = learning_request_scope(
                request.request_id,
                request.household_id,
                (item["event_id"] for item in evidence),
            )
        with scope:
            result = self.manager.invoke(
                tool.tool_id,
                dict(arguments),
                household_id=request.household_id,
                identity=identity,
                origin=origin,
                policy_service=self.policy_service,
                policy_context=policy_context,
                invocation_context=invocation_context,
            )
        return self._safe_invocation(result)

    @staticmethod
    def _safe_invocation(result: InvocationResult) -> dict[str, Any]:
        return {
            "status": public_invocation_status(result),
            "operation": result.tool_id,
            "connector_outcome": result.outcome.value,
            "dispatch_state": result.dispatch_state.value,
            "result": result.result,
            "reason": result.error_class,
            "trust": result.external_content_trust.value,
        }

    def submit_result(
        self,
        request: IntelligenceRequest,
        worker_id: str,
        result: IntelligenceResult,
    ) -> bool:
        return self.finalize_result(request, worker_id, result)[0]

    def finalize_result(
        self, request: IntelligenceRequest, worker_id: str, result: IntelligenceResult
    ) -> tuple[bool, IntelligenceResult, dict[str, Any]]:
        # A valid active provider must account for its actual outcome even if
        # the saved task expired or authority changed while it was running.
        # Current delivery eligibility below still withholds any response.
        self._assert_active(request, owner_guard=False)
        permission: dict[str, Any] = {"allowed": False, "reason": "NOT_UNSOLICITED_SPEECH"}
        if request.origin in {
            IntelligenceOrigin.AUTONOMOUS_ATTENTION,
            IntelligenceOrigin.DURABLE_TASK,
        }:
            try:
                if self.reasoning_context_loader is not None:
                    permission = (
                        self.reasoning_context_loader(request)
                        .get("initiative", {})
                        .get("notification", {})
                    )
            except Exception:
                permission = {}
            allowed = permission.get("allowed") is True and permission.get("request_id") == str(
                request.request_id
            )
            if result.status == IntelligenceResultStatus.RESPONSE and not allowed:
                # Do not turn an actual action failure/success into a speech result.
                # Only unsolicited response text is withheld; action references stay intact.
                result = replace(
                    result,
                    status=IntelligenceResultStatus.NO_ACTION,
                    response_text=None,
                    detail="UNSOLICITED_DELIVERY_WITHHELD",
                )
            elif (
                result.status == IntelligenceResultStatus.NO_ACTION
                and allowed
                and permission.get("required") is True
            ):
                result = replace(
                    result,
                    status=IntelligenceResultStatus.PARTIAL,
                    detail="REQUIRED_NOTIFICATION_NOT_PRODUCED",
                )
        if request.claim_owner != worker_id:
            return False, result, {}
        recorded = self.intelligence_store.record_result(
            request.request_id, worker_id, request.fencing_generation, result
        )
        if recorded and self.approval_results is not None:
            self.approval_results.reconcile_request(request)
        if recorded and self.learning_service is not None:
            # Terminal evidence remains authoritative if reconciliation fails.
            try:
                packet = self.learning_service.review_packet(
                    request.household_id, request.request_id
                )
                if packet is not None:
                    self.learning_service._complete_review(request.household_id, packet)
            except Exception:
                permission = {**permission, "learning_reconciliation": "PENDING"}
        return recorded, result, permission


class SentryReasoningProvider(Protocol):
    """Small host-owned provider contract implemented by the SENTRY bridge."""

    def run(
        self,
        request: IntelligenceRequest,
        context_packet: dict[str, Any],
        catalogue: list[dict[str, Any]],
        boundary: CoreSentryBoundary,
    ) -> IntelligenceResult: ...


@dataclass(slots=True)
class SentryBridgeWorker:
    """Claim and hand off one durable request without blind replay."""

    boundary: CoreSentryBoundary
    provider: SentryReasoningProvider
    worker_id: str

    def run_once(self) -> IntelligenceResult | None:
        request = self.boundary.claim_request(self.worker_id)
        if request is None:
            return None
        if not self.boundary.intelligence_store.transition(
            request.request_id,
            self.worker_id,
            request.fencing_generation,
            IntelligenceLifecycle.DELIVERED_TO_PROVIDER,
        ):
            return None
        try:
            if not self.boundary.start_provider(request, self.worker_id):
                raise SentryBoundaryError("INTELLIGENCE_CLAIM_LOST")
            result = self.provider.run(
                request,
                self.boundary.request_context(request),
                self.boundary.catalogue(request),
                self.boundary,
            )
        except Exception as exc:
            result = IntelligenceResult(
                request.request_id,
                IntelligenceResultStatus.UNAVAILABLE,
                detail=f"SENTRY provider unavailable: {type(exc).__name__}",
            )
        if not self.boundary.submit_result(request, self.worker_id, result):
            raise SentryBoundaryError("INTELLIGENCE_RESULT_CLAIM_LOST")
        return result
