"""ANIMA-owned identity, intent, and deterministic policy boundary.

This module deliberately stops before action execution.  OPA evaluates a
small, explicit input document; ANIMA owns the domain contracts, risk classes,
identity aggregation, policy version/digest, audit, and fail-closed behavior.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from enum import StrEnum
from pathlib import Path
from typing import Any, Protocol
from urllib.error import URLError
from urllib.request import Request, urlopen
from uuid import UUID, uuid4

import psycopg
from psycopg.rows import dict_row

from anima_ha.events import DeliveryClass, EventEnvelope, EventImportance
from anima_ha.journal import PostgresEventJournal


class PolicyUnavailable(RuntimeError):
    """Raised when the local policy evaluator cannot produce a decision."""


class PolicyValidationError(ValueError):
    """Raised when identity, intent, or policy data violates its contract."""


class Assurance(StrEnum):
    ANONYMOUS = "ANONYMOUS"
    CLAIMED = "CLAIMED"
    RECOGNIZED = "RECOGNIZED"
    AUTHENTICATED = "AUTHENTICATED"
    STRONG_AUTHENTICATED = "STRONG_AUTHENTICATED"


class EvidenceType(StrEnum):
    UNAUTHENTICATED_CLAIM = "UNAUTHENTICATED_CLAIM"
    AUTHENTICATED_SESSION = "AUTHENTICATED_SESSION"
    TRUSTED_DEVICE = "TRUSTED_DEVICE"
    LOCAL_PROXIMITY = "LOCAL_PROXIMITY"
    EXPLICIT_CONFIRMATION = "EXPLICIT_CONFIRMATION"
    VOICE_CLAIM = "VOICE_CLAIM"
    BIOMETRIC_CLAIM_PLACEHOLDER = "BIOMETRIC_CLAIM_PLACEHOLDER"
    OTHER_PROVIDER_EVIDENCE = "OTHER_PROVIDER_EVIDENCE"


class RequestOrigin(StrEnum):
    DIRECT_USER = "DIRECT_USER"
    AUTONOMOUS_AGENT = "AUTONOMOUS_AGENT"
    DURABLE_SYSTEM_TASK = "DURABLE_SYSTEM_TASK"
    ADMIN_COMMISSIONING = "ADMIN_COMMISSIONING"
    TESTING = "TESTING"


class Decision(StrEnum):
    ALLOW = "ALLOW"
    DENY = "DENY"
    REQUIRE_CONFIRMATION = "REQUIRE_CONFIRMATION"
    REQUIRE_STRONGER_AUTH = "REQUIRE_STRONGER_AUTH"


class RiskClass(StrEnum):
    READ_ONLY = "READ_ONLY"
    LOW_RISK_HOME_CONTROL = "LOW_RISK_HOME_CONTROL"
    SECURITY_SECURE_ACTION = "SECURITY_SECURE_ACTION"
    SECURITY_ACCESS_ACTION = "SECURITY_ACCESS_ACTION"
    EXTERNAL_SIDE_EFFECT = "EXTERNAL_SIDE_EFFECT"
    FINANCIAL_PURCHASE = "FINANCIAL_PURCHASE"
    ADMIN_SYSTEM_PROHIBITED = "ADMIN_SYSTEM_PROHIBITED"
    UNKNOWN = "UNKNOWN"


ASSURANCE_RANK = {
    Assurance.ANONYMOUS: 0,
    Assurance.CLAIMED: 1,
    Assurance.RECOGNIZED: 2,
    Assurance.AUTHENTICATED: 3,
    Assurance.STRONG_AUTHENTICATED: 4,
}


def _json_object(value: dict[str, Any]) -> dict[str, Any]:
    json.dumps(value, sort_keys=True, separators=(",", ":"))
    return value


def _timestamp(value: datetime, name: str) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise PolicyValidationError(f"{name} must be timezone-aware")
    return value.astimezone(UTC)


@dataclass(frozen=True, slots=True)
class IdentityEvidence:
    evidence_id: UUID
    household_id: UUID
    claimed_principal_id: UUID | None
    evidence_type: EvidenceType
    issuer: str
    issued_at: datetime
    observed_at: datetime
    expires_at: datetime | None
    assurance: Assurance
    strength: int
    provenance: str
    reference: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "evidence_type", EvidenceType(self.evidence_type))
        object.__setattr__(self, "assurance", Assurance(self.assurance))
        if not self.issuer.strip() or not self.provenance.strip():
            raise PolicyValidationError("issuer and provenance are required")
        if not 0 <= self.strength <= 100:
            raise PolicyValidationError("strength must be between 0 and 100")
        issued = _timestamp(self.issued_at, "issued_at")
        observed = _timestamp(self.observed_at, "observed_at")
        object.__setattr__(self, "issued_at", issued)
        object.__setattr__(self, "observed_at", observed)
        if self.expires_at is not None:
            expiry = _timestamp(self.expires_at, "expires_at")
            if expiry <= issued:
                raise PolicyValidationError("expires_at must be after issued_at")
            object.__setattr__(self, "expires_at", expiry)
        _json_object(self.metadata)


@dataclass(frozen=True, slots=True)
class IdentityContext:
    household_id: UUID
    principal_id: UUID | None
    assurance: Assurance
    evidence_ids: tuple[UUID, ...] = ()
    conflicting_principals: bool = False
    explanation: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(self, "assurance", Assurance(self.assurance))

    def to_payload(self) -> dict[str, Any]:
        return {
            "household_id": str(self.household_id),
            "principal_id": str(self.principal_id) if self.principal_id else None,
            "assurance": self.assurance.value,
            "evidence_ids": [str(value) for value in self.evidence_ids],
            "conflicting_principals": self.conflicting_principals,
            "explanation": self.explanation,
        }


class IdentityAggregator:
    """Aggregate non-expired evidence without turning proximity or voice into strong auth."""

    @staticmethod
    def _effective_assurance(evidence: IdentityEvidence) -> Assurance:
        if evidence.evidence_type == EvidenceType.UNAUTHENTICATED_CLAIM:
            return Assurance.CLAIMED
        if evidence.evidence_type in {
            EvidenceType.LOCAL_PROXIMITY,
            EvidenceType.TRUSTED_DEVICE,
            EvidenceType.VOICE_CLAIM,
            EvidenceType.BIOMETRIC_CLAIM_PLACEHOLDER,
            EvidenceType.OTHER_PROVIDER_EVIDENCE,
        }:
            return Assurance.RECOGNIZED
        if evidence.evidence_type == EvidenceType.AUTHENTICATED_SESSION:
            return (
                Assurance.STRONG_AUTHENTICATED
                if evidence.metadata.get("mfa") is True and evidence.strength >= 80
                else Assurance.AUTHENTICATED
            )
        if evidence.evidence_type == EvidenceType.EXPLICIT_CONFIRMATION:
            return Assurance.AUTHENTICATED
        return Assurance.CLAIMED

    def aggregate(
        self, household_id: UUID, evidence: list[IdentityEvidence], *, now: datetime | None = None
    ) -> IdentityContext:
        at = _timestamp(now or datetime.now(UTC), "now")
        active = [item for item in evidence if item.household_id == household_id]
        active = [item for item in active if item.expires_at is None or item.expires_at > at]
        principals = {item.claimed_principal_id for item in active if item.claimed_principal_id}
        if len(principals) > 1:
            return IdentityContext(
                household_id,
                None,
                Assurance.ANONYMOUS,
                tuple(item.evidence_id for item in active),
                True,
                "conflicting principal evidence does not strengthen identity",
            )
        principal = next(iter(principals), None)
        if principal is None:
            return IdentityContext(
                household_id,
                None,
                Assurance.ANONYMOUS,
                tuple(item.evidence_id for item in active),
                False,
                "no active principal evidence",
            )
        assurance = max(
            (self._effective_assurance(item) for item in active if item.claimed_principal_id),
            key=lambda value: ASSURANCE_RANK[value],
            default=Assurance.CLAIMED,
        )
        return IdentityContext(
            household_id,
            principal,
            assurance,
            tuple(item.evidence_id for item in active if item.claimed_principal_id == principal),
            False,
            "highest active evidence assurance for one principal",
        )


@dataclass(frozen=True, slots=True)
class TruthPolicyContext:
    truth_key: str
    status: str
    value: Any = None
    source_event_ids: tuple[str, ...] = ()

    def to_payload(self) -> dict[str, Any]:
        return {
            "truth_key": self.truth_key,
            "status": self.status,
            "value": self.value,
            "source_event_ids": list(self.source_event_ids),
        }


@dataclass(frozen=True, slots=True)
class PolicyContext:
    principal_role: str | None = None
    graph_metadata: dict[str, Any] = field(default_factory=dict)
    truth: tuple[TruthPolicyContext, ...] = ()

    @property
    def critical_truth_uncertain(self) -> bool:
        return any(
            item.status in {"STALE", "UNKNOWN", "UNAVAILABLE", "CONFLICTING"} for item in self.truth
        )


@dataclass(frozen=True, slots=True)
class AutonomyPolicy:
    low_risk_home_control: bool = True
    security_secure_action: bool = True


class ActionRiskClassifier:
    """Classify semantic actions, never arbitrary model prose or provider domains."""

    _admin = {"install_package", "edit_policy", "modify_permissions", "shell", "self_update"}
    _financial = {"purchase", "complete_purchase", "pay", "checkout"}
    _external = {"send_message", "send_email", "create_external_record", "change_calendar"}
    _access = {"unlock", "open", "disarm", "grant_access"}
    _secure = {
        "lock",
        "close",
        "arm",
        "secure",
        "capabilities.configure",
        "backup.create",
        "backup.restore",
    }
    _read_prefixes = ("get_", "read_", "query_", "list_", "inspect_", "status_")

    def classify(
        self, semantic_action: str, target_metadata: dict[str, Any] | None = None
    ) -> RiskClass:
        action = semantic_action.strip().casefold().replace(" ", "_")
        metadata = target_metadata or {}
        if action in self._admin or any(term in action for term in ("shell", "package", "policy")):
            return RiskClass.ADMIN_SYSTEM_PROHIBITED
        if action in self._financial or metadata.get("financial") is True:
            return RiskClass.FINANCIAL_PURCHASE
        if action in self._external or metadata.get("external_side_effect") is True:
            return RiskClass.EXTERNAL_SIDE_EFFECT
        if action in self._access:
            return RiskClass.SECURITY_ACCESS_ACTION
        if action in self._secure:
            return RiskClass.SECURITY_SECURE_ACTION
        if action.startswith(self._read_prefixes) or metadata.get("read_only") is True:
            return RiskClass.READ_ONLY
        if metadata.get("writable") is True or action in {
            "turn_on",
            "turn_off",
            "set_temperature",
            "set_brightness",
        }:
            return RiskClass.LOW_RISK_HOME_CONTROL
        return RiskClass.UNKNOWN


@dataclass(frozen=True, slots=True)
class ActionIntent:
    action_intent_id: UUID
    household_id: UUID
    semantic_action: str
    risk_class: RiskClass
    resource_id: UUID | None
    capability_id: UUID | None
    principal_id: UUID | None
    on_behalf_of: UUID | None
    origin: RequestOrigin
    truth: tuple[TruthPolicyContext, ...]
    graph_metadata: dict[str, Any]
    created_at: datetime
    correlation_id: str | None = None
    causation_id: str | None = None
    financially_consequential: bool = False
    externally_consequential: bool = False
    security_sensitive: bool = False
    verification_required: bool = False

    def __post_init__(self) -> None:
        object.__setattr__(self, "risk_class", RiskClass(self.risk_class))
        object.__setattr__(self, "origin", RequestOrigin(self.origin))
        if not self.semantic_action.strip():
            raise PolicyValidationError("semantic_action is required")
        object.__setattr__(self, "created_at", _timestamp(self.created_at, "created_at"))
        _json_object(self.graph_metadata)

    @classmethod
    def create(
        cls,
        *,
        household_id: UUID,
        semantic_action: str,
        resource_id: UUID | None = None,
        capability_id: UUID | None = None,
        principal_id: UUID | None = None,
        on_behalf_of: UUID | None = None,
        origin: RequestOrigin = RequestOrigin.DIRECT_USER,
        truth: tuple[TruthPolicyContext, ...] = (),
        graph_metadata: dict[str, Any] | None = None,
        created_at: datetime | None = None,
        **kwargs: Any,
    ) -> ActionIntent:
        metadata = graph_metadata or {}
        risk = ActionRiskClassifier().classify(semantic_action, metadata)
        return cls(
            action_intent_id=UUID(str(kwargs.pop("action_intent_id", uuid4()))),
            household_id=household_id,
            semantic_action=semantic_action,
            risk_class=risk,
            resource_id=resource_id,
            capability_id=capability_id,
            principal_id=principal_id,
            on_behalf_of=on_behalf_of,
            origin=origin,
            truth=truth,
            graph_metadata=metadata,
            created_at=created_at or datetime.now(UTC),
            financially_consequential=risk == RiskClass.FINANCIAL_PURCHASE,
            externally_consequential=risk == RiskClass.EXTERNAL_SIDE_EFFECT,
            security_sensitive=bool(metadata.get("security_sensitive", False)),
            verification_required=risk
            in {
                RiskClass.SECURITY_SECURE_ACTION,
                RiskClass.SECURITY_ACCESS_ACTION,
                RiskClass.FINANCIAL_PURCHASE,
            },
            **kwargs,
        )

    def to_payload(self) -> dict[str, Any]:
        return {
            "action_intent_id": str(self.action_intent_id),
            "household_id": str(self.household_id),
            "semantic_action": self.semantic_action,
            "risk_class": self.risk_class.value,
            "resource_id": str(self.resource_id) if self.resource_id else None,
            "capability_id": str(self.capability_id) if self.capability_id else None,
            "principal_id": str(self.principal_id) if self.principal_id else None,
            "on_behalf_of": str(self.on_behalf_of) if self.on_behalf_of else None,
            "origin": self.origin.value,
            "truth": [item.to_payload() for item in self.truth],
            "graph_metadata": self.graph_metadata,
            "created_at": self.created_at.isoformat(),
            "correlation_id": self.correlation_id,
            "causation_id": self.causation_id,
            "financially_consequential": self.financially_consequential,
            "externally_consequential": self.externally_consequential,
            "security_sensitive": self.security_sensitive,
            "verification_required": self.verification_required,
        }


@dataclass(frozen=True, slots=True)
class ConfirmationChallenge:
    challenge_id: UUID
    action_intent_id: UUID
    household_id: UUID
    confirming_principal_id: UUID
    issued_at: datetime
    expires_at: datetime
    consumed_at: datetime | None = None

    def is_valid(
        self, *, now: datetime | None = None, action_intent_id: UUID | None = None
    ) -> bool:
        at = _timestamp(now or datetime.now(UTC), "now")
        return (
            (action_intent_id is None or action_intent_id == self.action_intent_id)
            and self.consumed_at is None
            and self.expires_at > at
        )


@dataclass(frozen=True, slots=True)
class PolicyBundle:
    version: str
    digest: str
    source: str = "repository:policy/phase4"

    @classmethod
    def from_repository(cls, root: Path | None = None) -> PolicyBundle:
        policy_root = root or Path(__file__).resolve().parents[2] / "policy" / "phase4"
        contents = (
            b"".join(path.read_bytes() for path in sorted(policy_root.glob("*.rego")))
            + (policy_root / "data.json").read_bytes()
        )
        return cls("phase4-baseline-v1", hashlib.sha256(contents).hexdigest())


class OpaEvaluator(Protocol):
    def evaluate(self, document: dict[str, Any]) -> dict[str, Any]: ...


class OpaPolicyClient:
    """Small HTTP adapter; OPA remains replaceable behind this interface."""

    def __init__(self, base_url: str, timeout: float = 2.0) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    def evaluate(self, document: dict[str, Any]) -> dict[str, Any]:
        request = Request(
            f"{self.base_url}/v1/data/anima/authorization/decision",
            data=json.dumps({"input": document}, sort_keys=True).encode(),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urlopen(request, timeout=self.timeout) as response:
                body = json.loads(response.read().decode("utf-8"))
        except (OSError, URLError, TimeoutError, json.JSONDecodeError) as exc:
            raise PolicyUnavailable(str(exc)) from exc
        result = body.get("result")
        if not isinstance(result, dict):
            raise PolicyUnavailable("OPA returned no structured decision")
        return result


@dataclass(frozen=True, slots=True)
class PolicyDecision:
    decision_id: UUID
    action_intent_id: UUID
    household_id: UUID
    principal_id: UUID | None
    decision: Decision
    reason_code: str
    policy_version: str
    policy_digest: str
    current_assurance: Assurance
    required_assurance: Assurance | None
    confirmation_required: bool
    evaluated_at: datetime

    def to_payload(self) -> dict[str, Any]:
        return {
            "decision_id": str(self.decision_id),
            "action_intent_id": str(self.action_intent_id),
            "household_id": str(self.household_id),
            "principal_id": str(self.principal_id) if self.principal_id else None,
            "decision": self.decision.value,
            "reason_code": self.reason_code,
            "policy_version": self.policy_version,
            "policy_digest": self.policy_digest,
            "current_assurance": self.current_assurance.value,
            "required_assurance": (
                self.required_assurance.value if self.required_assurance else None
            ),
            "confirmation_required": self.confirmation_required,
            "evaluated_at": self.evaluated_at.isoformat(),
        }


class PolicyAuditStore(Protocol):
    def record_bundle(self, bundle: PolicyBundle, *, activated_at: datetime) -> None: ...

    def record_evidence(self, evidence: IdentityEvidence) -> None: ...

    def record_decision(self, decision: PolicyDecision, snapshot: dict[str, Any]) -> None: ...


class PostgresPolicyStore:
    """Persistence and journal audit boundary for policy evidence and decisions."""

    def __init__(self, database_url: str, connect_timeout: int = 5) -> None:
        self.database_url = database_url
        self.connect_timeout = connect_timeout
        self.journal = PostgresEventJournal(database_url, connect_timeout)

    def _connect(self) -> psycopg.Connection[Any]:
        return psycopg.connect(
            self.database_url, connect_timeout=self.connect_timeout, row_factory=dict_row
        )

    def record_bundle(self, bundle: PolicyBundle, *, activated_at: datetime) -> None:
        with self._connect() as connection, connection.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO anima_policy_bundles
                    (bundle_version, bundle_digest, source, activated_at, validation_status)
                VALUES (%s, %s, %s, %s, 'VALID')
                ON CONFLICT (bundle_version) DO NOTHING
                """,
                (bundle.version, bundle.digest, bundle.source, activated_at),
            )
            connection.commit()

    def record_evidence(self, evidence: IdentityEvidence) -> None:
        with self._connect() as connection, connection.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO anima_identity_evidence (
                    evidence_id, household_id, claimed_principal_id, evidence_type, issuer,
                    issued_at, observed_at, expires_at, assurance, strength, provenance,
                    reference, metadata
                ) VALUES (%(evidence_id)s, %(household_id)s, %(claimed_principal_id)s,
                    %(evidence_type)s, %(issuer)s, %(issued_at)s, %(observed_at)s,
                    %(expires_at)s, %(assurance)s, %(strength)s, %(provenance)s,
                    %(reference)s, %(metadata)s::jsonb)
                ON CONFLICT (evidence_id) DO NOTHING
                """,
                {
                    "evidence_id": evidence.evidence_id,
                    "household_id": evidence.household_id,
                    "claimed_principal_id": evidence.claimed_principal_id,
                    "evidence_type": evidence.evidence_type.value,
                    "issuer": evidence.issuer,
                    "issued_at": evidence.issued_at,
                    "observed_at": evidence.observed_at,
                    "expires_at": evidence.expires_at,
                    "assurance": evidence.assurance.value,
                    "strength": evidence.strength,
                    "provenance": evidence.provenance,
                    "reference": evidence.reference,
                    "metadata": json.dumps(evidence.metadata, sort_keys=True),
                },
            )
            connection.commit()

    def issue_confirmation(
        self,
        *,
        action_intent_id: UUID,
        household_id: UUID,
        confirming_principal_id: UUID,
        issued_at: datetime,
        ttl: timedelta = timedelta(minutes=2),
    ) -> ConfirmationChallenge:
        challenge = ConfirmationChallenge(
            challenge_id=uuid4(),
            action_intent_id=action_intent_id,
            household_id=household_id,
            confirming_principal_id=confirming_principal_id,
            issued_at=_timestamp(issued_at, "issued_at"),
            expires_at=_timestamp(issued_at, "issued_at") + ttl,
        )
        with self._connect() as connection, connection.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO anima_confirmation_challenges (
                    challenge_id, action_intent_id, household_id, confirming_principal_id,
                    issued_at, expires_at
                ) VALUES (%s, %s, %s, %s, %s, %s)
                """,
                (
                    challenge.challenge_id,
                    challenge.action_intent_id,
                    challenge.household_id,
                    challenge.confirming_principal_id,
                    challenge.issued_at,
                    challenge.expires_at,
                ),
            )
            connection.commit()
        return challenge

    def consume_confirmation(
        self,
        challenge_id: UUID,
        *,
        action_intent_id: UUID,
        confirming_principal_id: UUID,
        now: datetime,
    ) -> bool:
        with self._connect() as connection, connection.cursor() as cursor:
            cursor.execute(
                """
                UPDATE anima_confirmation_challenges
                SET consumed_at = %s
                WHERE challenge_id = %s AND action_intent_id = %s
                  AND confirming_principal_id = %s AND consumed_at IS NULL
                  AND expires_at > %s
                """,
                (
                    _timestamp(now, "now"),
                    challenge_id,
                    action_intent_id,
                    confirming_principal_id,
                    _timestamp(now, "now"),
                ),
            )
            consumed = cursor.rowcount == 1
            connection.commit()
            return consumed

    def record_decision(self, decision: PolicyDecision, snapshot: dict[str, Any]) -> None:
        audit = EventEnvelope.create(
            event_id=str(uuid4()),
            event_type="policy.decision",
            source="anima.policy",
            subject_key=f"household/{decision.household_id}",
            occurred_at=decision.evaluated_at,
            payload={"decision": decision.to_payload(), "input_digest": _digest(snapshot)},
            importance=EventImportance.IMPORTANT,
            delivery_class=DeliveryClass.GUARANTEED,
            metadata={"audit": True},
        )
        with self._connect() as connection:
            try:
                with connection.cursor() as cursor:
                    cursor.execute(
                        """
                        INSERT INTO anima_policy_decisions (
                            decision_id, action_intent_id, household_id, principal_id, decision,
                            reason_code, policy_version, policy_digest, required_assurance,
                            confirmation_required, evaluated_at, input_snapshot
                        ) VALUES (%(decision_id)s, %(action_intent_id)s, %(household_id)s,
                            %(principal_id)s, %(decision)s, %(reason_code)s, %(policy_version)s,
                            %(policy_digest)s, %(required_assurance)s, %(confirmation_required)s,
                            %(evaluated_at)s, %(input_snapshot)s::jsonb)
                        ON CONFLICT (decision_id) DO NOTHING
                        """,
                        {
                            "decision_id": decision.decision_id,
                            "action_intent_id": decision.action_intent_id,
                            "household_id": decision.household_id,
                            "principal_id": decision.principal_id,
                            "decision": decision.decision.value,
                            "reason_code": decision.reason_code,
                            "policy_version": decision.policy_version,
                            "policy_digest": decision.policy_digest,
                            "required_assurance": (
                                decision.required_assurance.value
                                if decision.required_assurance
                                else None
                            ),
                            "confirmation_required": decision.confirmation_required,
                            "evaluated_at": decision.evaluated_at,
                            "input_snapshot": json.dumps(snapshot, sort_keys=True),
                        },
                    )
                    self.journal.append_in_connection(connection, audit)
                connection.commit()
            except Exception:
                connection.rollback()
                raise


def _digest(document: dict[str, Any]) -> str:
    return hashlib.sha256(
        json.dumps(document, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


class PolicyService:
    """Build policy input, call OPA, and persist every decision."""

    def __init__(
        self,
        evaluator: OpaEvaluator,
        *,
        bundle: PolicyBundle | None = None,
        autonomy: AutonomyPolicy | None = None,
        audit_store: PolicyAuditStore | None = None,
    ) -> None:
        self.evaluator = evaluator
        self.bundle = bundle or PolicyBundle.from_repository()
        self.autonomy = autonomy or AutonomyPolicy()
        self.audit_store = audit_store

    def _input(
        self,
        intent: ActionIntent,
        identity: IdentityContext,
        context: PolicyContext,
        confirmation: ConfirmationChallenge | None,
        *,
        now: datetime,
    ) -> dict[str, Any]:
        truth_items = context.truth + intent.truth
        confirmation_valid = bool(
            confirmation
            and confirmation.confirming_principal_id == identity.principal_id
            and confirmation.is_valid(now=now, action_intent_id=intent.action_intent_id)
        )
        return {
            "action_intent": intent.to_payload(),
            "identity": identity.to_payload(),
            "origin": intent.origin.value,
            "policy": {
                "role": context.principal_role,
                "autonomy": {
                    "low_risk_home_control": self.autonomy.low_risk_home_control,
                    "security_secure_action": self.autonomy.security_secure_action,
                },
            },
            "truth": {
                "critical_uncertain": any(
                    item.status in {"STALE", "UNKNOWN", "UNAVAILABLE", "CONFLICTING"}
                    for item in truth_items
                ),
                "items": [item.to_payload() for item in truth_items],
            },
            "graph": context.graph_metadata,
            "confirmation": {"valid": confirmation_valid},
        }

    def evaluate(
        self,
        intent: ActionIntent,
        identity: IdentityContext,
        context: PolicyContext | None = None,
        confirmation: ConfirmationChallenge | None = None,
        *,
        now: datetime | None = None,
    ) -> PolicyDecision:
        evaluated_at = _timestamp(now or datetime.now(UTC), "now")
        document = self._input(
            intent, identity, context or PolicyContext(), confirmation, now=evaluated_at
        )
        if self.audit_store:
            self.audit_store.record_bundle(self.bundle, activated_at=evaluated_at)
        try:
            result = self.evaluator.evaluate(document)
            decision = Decision(str(result["decision"]))
            reason = str(result["reason_code"])
            required_raw = result.get("required_assurance")
            required = Assurance(str(required_raw)) if required_raw else None
            confirmation_required = bool(result.get("confirmation_required", False))
            version = str(result.get("policy_version", self.bundle.version))
        except Exception as exc:
            decision = Decision.DENY
            reason = "POLICY_UNAVAILABLE"
            required = Assurance.AUTHENTICATED
            confirmation_required = False
            version = self.bundle.version
            if not isinstance(exc, (PolicyUnavailable, KeyError, ValueError, TypeError)):
                reason = "POLICY_INVALID_RESULT"
        outcome = PolicyDecision(
            decision_id=uuid4(),
            action_intent_id=intent.action_intent_id,
            household_id=intent.household_id,
            principal_id=identity.principal_id,
            decision=decision,
            reason_code=reason,
            policy_version=version,
            policy_digest=self.bundle.digest,
            current_assurance=identity.assurance,
            required_assurance=required,
            confirmation_required=confirmation_required,
            evaluated_at=evaluated_at,
        )
        if self.audit_store:
            self.audit_store.record_decision(outcome, document)
        return outcome

    def record_evidence(self, evidence: IdentityEvidence) -> None:
        if self.audit_store:
            self.audit_store.record_evidence(evidence)
