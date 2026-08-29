"""Bounded x86-64 PostgreSQL + local OPA Phase 4 integration evidence."""

from __future__ import annotations

import os
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import psycopg
from psycopg.rows import dict_row

from anima_ha.config import RuntimeConfig
from anima_ha.policy import (
    ActionIntent,
    Assurance,
    AutonomyPolicy,
    EvidenceType,
    IdentityAggregator,
    IdentityContext,
    IdentityEvidence,
    OpaPolicyClient,
    PolicyContext,
    PolicyService,
    PostgresPolicyStore,
    RequestOrigin,
    TruthPolicyContext,
)


def _evidence(
    household_id: UUID,
    principal_id: UUID,
    evidence_type: EvidenceType,
    now: datetime,
    *,
    expires_at: datetime | None = None,
    metadata: dict[str, object] | None = None,
    strength: int = 60,
) -> IdentityEvidence:
    return IdentityEvidence(
        uuid4(),
        household_id,
        principal_id,
        evidence_type,
        "phase4-integration",
        now,
        now,
        expires_at,
        Assurance.RECOGNIZED,
        strength,
        "synthetic-integration",
        metadata=metadata or {},
    )


def _expect(label: str, actual: str, expected: str) -> None:
    if actual != expected:
        raise AssertionError(f"{label}: expected {expected}, got {actual}")


def main() -> int:
    config = RuntimeConfig.from_environment()
    opa_url = os.environ.get("ANIMA_OPA_URL", "http://127.0.0.1:18181")
    household_id = uuid4()
    principal_id = uuid4()
    now = datetime.now(UTC).replace(microsecond=0)
    store = PostgresPolicyStore(config.database_url, config.database_connect_timeout)
    service = PolicyService(
        OpaPolicyClient(opa_url),
        autonomy=AutonomyPolicy(low_risk_home_control=True, security_secure_action=True),
        audit_store=store,
    )

    voice = _evidence(household_id, principal_id, EvidenceType.VOICE_CLAIM, now)
    strong = _evidence(
        household_id,
        principal_id,
        EvidenceType.AUTHENTICATED_SESSION,
        now,
        metadata={"mfa": True},
        strength=100,
    )
    proximity = _evidence(household_id, principal_id, EvidenceType.LOCAL_PROXIMITY, now)
    for item in (voice, strong, proximity):
        service.record_evidence(item)
    aggregator = IdentityAggregator()
    recognized = aggregator.aggregate(household_id, [voice], now=now)
    strong_identity = aggregator.aggregate(household_id, [strong], now=now)
    proximity_identity = aggregator.aggregate(household_id, [proximity], now=now)

    read = ActionIntent.create(household_id=household_id, semantic_action="query_room_temperature")
    _expect(
        "unauthenticated read",
        service.evaluate(
            read, IdentityContext(household_id, None, Assurance.ANONYMOUS)
        ).decision.value,
        "ALLOW",
    )
    low = ActionIntent.create(
        household_id=household_id,
        semantic_action="turn_off",
        graph_metadata={"writable": True},
    )
    _expect(
        "low-risk resident",
        service.evaluate(low, recognized, PolicyContext("resident")).decision.value,
        "ALLOW",
    )
    secure = ActionIntent.create(
        household_id=household_id,
        semantic_action="lock",
        graph_metadata={"security_sensitive": True},
        origin=RequestOrigin.AUTONOMOUS_AGENT,
    )
    _expect(
        "autonomous secure",
        service.evaluate(
            secure,
            IdentityContext(household_id, None, Assurance.ANONYMOUS),
            PolicyContext(),
            now=now,
        ).decision.value,
        "ALLOW",
    )
    autonomous_low = ActionIntent.create(
        household_id=household_id,
        semantic_action="turn_off",
        graph_metadata={"writable": True},
        origin=RequestOrigin.AUTONOMOUS_AGENT,
    )
    _expect(
        "autonomous low-risk",
        service.evaluate(
            autonomous_low,
            IdentityContext(household_id, None, Assurance.ANONYMOUS),
        ).decision.value,
        "ALLOW",
    )
    unlock = ActionIntent.create(
        household_id=household_id,
        semantic_action="unlock",
        graph_metadata={"security_sensitive": True},
    )
    _expect(
        "voice unlock",
        service.evaluate(unlock, recognized, PolicyContext("resident")).decision.value,
        "REQUIRE_STRONGER_AUTH",
    )
    _expect(
        "strong unlock",
        service.evaluate(unlock, strong_identity, PolicyContext("resident")).decision.value,
        "ALLOW",
    )
    _expect(
        "geofence-only unlock",
        service.evaluate(unlock, proximity_identity, PolicyContext("resident")).decision.value,
        "REQUIRE_STRONGER_AUTH",
    )
    external = ActionIntent.create(household_id=household_id, semantic_action="send_message")
    _expect(
        "external confirmation",
        service.evaluate(external, strong_identity).decision.value,
        "REQUIRE_CONFIRMATION",
    )
    challenge = store.issue_confirmation(
        action_intent_id=external.action_intent_id,
        household_id=household_id,
        confirming_principal_id=principal_id,
        issued_at=now,
    )
    _expect(
        "confirmed external",
        service.evaluate(external, strong_identity, confirmation=challenge).decision.value,
        "ALLOW",
    )
    assert store.consume_confirmation(
        challenge.challenge_id,
        action_intent_id=external.action_intent_id,
        confirming_principal_id=principal_id,
        now=now + timedelta(seconds=1),
    )
    _expect(
        "replayed confirmation",
        service.evaluate(
            external,
            strong_identity,
            confirmation=replace(challenge, consumed_at=now + timedelta(seconds=1)),
        ).decision.value,
        "REQUIRE_CONFIRMATION",
    )
    purchase = ActionIntent.create(household_id=household_id, semantic_action="complete_purchase")
    _expect(
        "purchase approval",
        service.evaluate(purchase, strong_identity).decision.value,
        "REQUIRE_CONFIRMATION",
    )
    prohibited = ActionIntent.create(household_id=household_id, semantic_action="install_package")
    _expect(
        "admin prohibited", service.evaluate(prohibited, strong_identity).decision.value, "DENY"
    )
    unknown = ActionIntent.create(
        household_id=household_id, semantic_action="unknown_consequential_operation"
    )
    _expect("unknown risk", service.evaluate(unknown, strong_identity).decision.value, "DENY")
    stale_secure = ActionIntent.create(
        household_id=household_id,
        semantic_action="lock",
        graph_metadata={"security_sensitive": True},
        truth=(TruthPolicyContext("door/front/state", "STALE", "closed", ("truth-event",)),),
    )
    _expect(
        "stale critical truth",
        service.evaluate(stale_secure, strong_identity, PolicyContext("resident")).decision.value,
        "DENY",
    )
    conflicting = _evidence(
        household_id,
        uuid4(),
        EvidenceType.AUTHENTICATED_SESSION,
        now,
        metadata={"mfa": True},
        strength=100,
    )
    conflict_identity = aggregator.aggregate(household_id, [strong, conflicting], now=now)
    _expect(
        "conflicting identity",
        service.evaluate(low, conflict_identity, PolicyContext("resident")).decision.value,
        "DENY",
    )

    with psycopg.connect(
        config.database_url, connect_timeout=config.database_connect_timeout, row_factory=dict_row
    ) as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT count(*) AS count FROM anima_policy_decisions WHERE household_id = %s",
                (household_id,),
            )
            decision_row = cursor.fetchone()
            assert decision_row is not None
            decisions = int(decision_row["count"])
            cursor.execute(
                """
                SELECT count(*) AS count FROM anima_event_journal
                WHERE event_type = 'policy.decision' AND subject_key = %s
                """,
                (f"household/{household_id}",),
            )
            audit_row = cursor.fetchone()
            assert audit_row is not None
            audits = int(audit_row["count"])
    print("PHASE4_POLICY_INTEGRATION_PASS")
    print(f"household_id={household_id}")
    print("decisions=PASS all_required_decisions_and_boundaries")
    print(f"decision_records={decisions} audit_events={audits}")
    print(f"opa_url={opa_url}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
