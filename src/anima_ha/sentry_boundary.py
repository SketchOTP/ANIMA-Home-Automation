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
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any, Protocol
from uuid import UUID, uuid5

from anima_ha.action import ActionRequest, resolve_action_safety_spec
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
    InvocationOutcome,
    InvocationResult,
    PluginManager,
    ToolDescriptor,
)
from anima_ha.policy import (
    Assurance,
    EvidenceType,
    IdentityAggregator,
    IdentityContext,
    IdentityEvidence,
    PolicyContext,
    RequestOrigin,
)

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
                _INVOCATION_NAMESPACE, f"sentry-evidence:{self.endpoint_id}:{observed.isoformat()}"
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

    def to_payload(self) -> dict[str, str | None]:
        return {
            "provider_id": self.provider_id,
            "state": self.state,
            "version": self.version,
            "detail": self.detail,
        }


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

    def health(self) -> SentryBoundaryHealth:
        return SentryBoundaryHealth("anima-core", "available")

    def claim_request(
        self, worker_id: str, *, household_id: UUID | None = None
    ) -> IntelligenceRequest | None:
        # A SENTRY worker can claim only requests explicitly addressed to the
        # SENTRY provider; it must never consume another provider's queue.
        return self.intelligence_store.claim(
            worker_id, provider_id="sentry", household_id=household_id
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

    def renew_request(self, request: IntelligenceRequest, worker_id: str) -> bool:
        if request.claim_owner != worker_id:
            return False
        if request.lifecycle not in {
            IntelligenceLifecycle.CLAIMED,
            IntelligenceLifecycle.DELIVERED_TO_PROVIDER,
            IntelligenceLifecycle.PROVIDER_RUNNING,
        }:
            return False
        return self.intelligence_store.renew(
            request.request_id, worker_id, request.fencing_generation
        )

    def request_context(self, request: IntelligenceRequest) -> dict[str, Any]:
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
    ) -> IntelligenceRequest:
        """Create direct SENTRY work without consuming autonomous Attention."""
        request = IntelligenceRequestFactory.for_direct_sentry_interaction(
            sentry_request_id=sentry_request_id,
            household_id=household_id,
            source_surface=source_surface,
            user_text=user_text,
            tools=self.manager.list_tools(),
            identity_evidence_refs=identity_evidence_refs,
        )
        return self.intelligence_store.enqueue(request)

    def record_sentry_identity(
        self,
        request: IntelligenceRequest,
        envelope: SentryIdentityEvidenceEnvelope,
        *,
        profile_principal_id: UUID | None = None,
    ) -> IdentityContext:
        """Persist bounded SENTRY evidence and aggregate it without escalation."""
        evidence = envelope.to_anima_evidence(request.household_id, profile_principal_id)
        recorder = getattr(self.policy_service, "record_evidence", None)
        if callable(recorder):
            recorder(evidence)
        return IdentityAggregator().aggregate(request.household_id, [evidence])

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
            )
            if compatible:
                assert tool is not None
                payload = tool.to_payload()
                payload["schema_digest"] = expected_schema
                result.append(payload)
            else:
                unavailable = dict(original)
                unavailable["availability"] = False
                unavailable["unavailable_reason"] = "DISABLED_OR_INCOMPATIBLE"
                result.append(unavailable)
        return result

    def _assert_active(self, request: IntelligenceRequest) -> None:
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
        ):
            raise SentryBoundaryError("TOOL_BINDING_INCOMPATIBLE")
        return tool

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
        identity = _identity(request)
        origin = _origin(request.origin)
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
        policy_context = PolicyContext()
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
            return {
                "status": execution.record.status.value,
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
        status = {
            InvocationOutcome.SUCCESS: "SUCCEEDED",
            InvocationOutcome.POLICY_DENIED: "DENIED",
            InvocationOutcome.REQUIRE_CONFIRMATION: "REQUIRE_CONFIRMATION",
            InvocationOutcome.REQUIRE_STRONGER_AUTH: "REQUIRE_STRONGER_AUTH",
            InvocationOutcome.PLUGIN_UNAVAILABLE: "UNAVAILABLE",
            InvocationOutcome.PLUGIN_TIMEOUT: "UNKNOWN_RESULT",
            InvocationOutcome.UNKNOWN_RESULT: "UNKNOWN_RESULT",
        }.get(result.outcome, "FAILED")
        return {
            "status": status,
            "operation": result.tool_id,
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
        self._assert_active(request)
        if request.claim_owner != worker_id:
            return False
        return self.intelligence_store.record_result(
            request.request_id, worker_id, request.fencing_generation, result
        )


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
