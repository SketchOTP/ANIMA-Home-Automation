from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID, uuid4

from anima_ha.policy import (
    ASSURANCE_RANK,
    ActionIntent,
    ActionRiskClassifier,
    Assurance,
    ConfirmationChallenge,
    EvidenceType,
    IdentityAggregator,
    IdentityContext,
    IdentityEvidence,
    PolicyService,
    PolicyUnavailable,
    RequestOrigin,
    RiskClass,
)


def evidence(
    household_id: UUID,
    principal_id: UUID,
    evidence_type: EvidenceType,
    *,
    issued_at: datetime | None = None,
    expires_at: datetime | None = None,
    metadata: dict[str, object] | None = None,
    strength: int = 50,
) -> IdentityEvidence:
    now = datetime(2026, 8, 29, tzinfo=UTC)
    issued = issued_at or now
    return IdentityEvidence(
        uuid4(),
        household_id,
        principal_id,
        evidence_type,
        "test-issuer",
        issued,
        issued,
        expires_at,
        Assurance.RECOGNIZED,
        strength,
        "test-provenance",
        metadata=metadata or {},
    )


def test_identity_expiry_voice_and_conflict_are_not_strong_auth() -> None:
    household_id = uuid4()
    principal = uuid4()
    now = datetime(2026, 8, 29, tzinfo=UTC)
    voice = evidence(household_id, principal, EvidenceType.VOICE_CLAIM)
    expired = evidence(
        household_id,
        principal,
        EvidenceType.AUTHENTICATED_SESSION,
        issued_at=now - timedelta(minutes=2),
        expires_at=now - timedelta(seconds=1),
        metadata={"mfa": True},
        strength=100,
    )
    identity = IdentityAggregator().aggregate(household_id, [voice, expired], now=now)
    assert identity.assurance == Assurance.RECOGNIZED
    assert ASSURANCE_RANK[identity.assurance] < ASSURANCE_RANK[Assurance.STRONG_AUTHENTICATED]

    conflicting = evidence(household_id, uuid4(), EvidenceType.AUTHENTICATED_SESSION)
    result = IdentityAggregator().aggregate(household_id, [voice, conflicting], now=now)
    assert result.conflicting_principals
    assert result.assurance == Assurance.ANONYMOUS
    assert result.principal_id is None


def test_risk_classifier_is_semantic_and_unknown_fails_closed() -> None:
    classifier = ActionRiskClassifier()
    assert classifier.classify("query_room_temperature") == RiskClass.READ_ONLY
    assert classifier.classify("turn_off", {"writable": True}) == RiskClass.LOW_RISK_HOME_CONTROL
    assert (
        classifier.classify("lock", {"security_sensitive": True})
        == RiskClass.SECURITY_SECURE_ACTION
    )
    assert classifier.classify("backup.restore") == RiskClass.SECURITY_SECURE_ACTION
    assert (
        classifier.classify("unlock", {"security_sensitive": True})
        == RiskClass.SECURITY_ACCESS_ACTION
    )
    assert classifier.classify("install_package") == RiskClass.ADMIN_SYSTEM_PROHIBITED
    assert classifier.classify("novel_consequential_operation") == RiskClass.UNKNOWN


def test_action_intent_does_not_accept_provider_or_memory_authority() -> None:
    intent = ActionIntent.create(
        household_id=uuid4(),
        semantic_action="unlock",
        graph_metadata={"security_sensitive": True, "provider": "homeassistant"},
        origin=RequestOrigin.DIRECT_USER,
    )
    assert intent.risk_class == RiskClass.SECURITY_ACCESS_ACTION
    assert intent.verification_required
    assert "permission" not in intent.to_payload()
    assert ASSURANCE_RANK[Assurance.RECOGNIZED] < ASSURANCE_RANK[Assurance.STRONG_AUTHENTICATED]


def test_confirmation_is_exactly_bound_and_single_use_in_contract() -> None:
    now = datetime(2026, 8, 29, tzinfo=UTC)
    challenge = ConfirmationChallenge(
        uuid4(), uuid4(), uuid4(), uuid4(), now, now + timedelta(minutes=1)
    )
    assert challenge.is_valid(now=now, action_intent_id=challenge.action_intent_id)
    assert not challenge.is_valid(now=now, action_intent_id=uuid4())
    consumed = ConfirmationChallenge(
        challenge.challenge_id,
        challenge.action_intent_id,
        challenge.household_id,
        challenge.confirming_principal_id,
        challenge.issued_at,
        challenge.expires_at,
        now,
    )
    assert not consumed.is_valid(now=now, action_intent_id=challenge.action_intent_id)


class FailingEvaluator:
    def evaluate(self, document: dict[str, Any]) -> dict[str, Any]:
        raise PolicyUnavailable("test outage")


def test_policy_evaluator_failure_is_deny() -> None:
    household_id = uuid4()
    identity = IdentityContext(household_id, None, Assurance.ANONYMOUS)
    intent = ActionIntent.create(household_id=household_id, semantic_action="unlock")
    decision = PolicyService(FailingEvaluator()).evaluate(intent, identity)
    assert decision.decision.value == "DENY"
    assert decision.reason_code == "POLICY_UNAVAILABLE"
