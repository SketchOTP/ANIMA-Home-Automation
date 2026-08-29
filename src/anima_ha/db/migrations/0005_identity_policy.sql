CREATE TABLE IF NOT EXISTS anima_identity_evidence (
    evidence_id UUID PRIMARY KEY,
    household_id UUID NOT NULL,
    claimed_principal_id UUID,
    evidence_type TEXT NOT NULL,
    issuer TEXT NOT NULL,
    issued_at TIMESTAMPTZ NOT NULL,
    observed_at TIMESTAMPTZ NOT NULL,
    expires_at TIMESTAMPTZ,
    assurance TEXT NOT NULL,
    strength INTEGER NOT NULL CHECK (strength >= 0 AND strength <= 100),
    provenance TEXT NOT NULL,
    reference TEXT,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb CHECK (jsonb_typeof(metadata) = 'object'),
    CHECK (expires_at IS NULL OR expires_at > issued_at)
);

CREATE INDEX IF NOT EXISTS anima_identity_evidence_active_idx
    ON anima_identity_evidence (household_id, claimed_principal_id, expires_at);

CREATE TABLE IF NOT EXISTS anima_policy_bundles (
    bundle_version TEXT PRIMARY KEY,
    bundle_digest TEXT NOT NULL UNIQUE,
    source TEXT NOT NULL,
    activated_at TIMESTAMPTZ NOT NULL,
    validation_status TEXT NOT NULL CHECK (validation_status IN ('VALID', 'INVALID')),
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb CHECK (jsonb_typeof(metadata) = 'object')
);

CREATE TABLE IF NOT EXISTS anima_confirmation_challenges (
    challenge_id UUID PRIMARY KEY,
    action_intent_id UUID NOT NULL,
    household_id UUID NOT NULL,
    confirming_principal_id UUID NOT NULL,
    issued_at TIMESTAMPTZ NOT NULL,
    expires_at TIMESTAMPTZ NOT NULL,
    consumed_at TIMESTAMPTZ,
    CHECK (expires_at > issued_at)
);

CREATE INDEX IF NOT EXISTS anima_confirmation_lookup_idx
    ON anima_confirmation_challenges (action_intent_id, confirming_principal_id, expires_at);

CREATE TABLE IF NOT EXISTS anima_policy_decisions (
    decision_id UUID PRIMARY KEY,
    action_intent_id UUID NOT NULL,
    household_id UUID NOT NULL,
    principal_id UUID,
    decision TEXT NOT NULL CHECK (decision IN (
        'ALLOW', 'DENY', 'REQUIRE_CONFIRMATION', 'REQUIRE_STRONGER_AUTH'
    )),
    reason_code TEXT NOT NULL,
    policy_version TEXT NOT NULL,
    policy_digest TEXT NOT NULL,
    required_assurance TEXT,
    confirmation_required BOOLEAN NOT NULL DEFAULT false,
    evaluated_at TIMESTAMPTZ NOT NULL,
    input_snapshot JSONB NOT NULL CHECK (jsonb_typeof(input_snapshot) = 'object')
);

CREATE INDEX IF NOT EXISTS anima_policy_decisions_household_idx
    ON anima_policy_decisions (household_id, evaluated_at, decision);
