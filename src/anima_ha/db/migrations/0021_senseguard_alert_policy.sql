-- Phase 13: one typed, ANIMA-owned SenseGuard alert policy.
CREATE TABLE IF NOT EXISTS anima_senseguard_alert_policies (
    policy_id UUID PRIMARY KEY,
    household_id UUID NOT NULL,
    resource_ids JSONB NOT NULL,
    event_type TEXT NOT NULL,
    timezone TEXT NOT NULL,
    start_local TIME NOT NULL,
    end_local TIME NOT NULL,
    priority INTEGER NOT NULL CHECK (priority BETWEEN 0 AND 100),
    guaranteed_attention BOOLEAN NOT NULL,
    delivery_mode TEXT NOT NULL CHECK (delivery_mode IN ('SENTRY_COGNITION', 'NOTIFICATION')),
    enabled BOOLEAN NOT NULL,
    creator_principal_id UUID,
    version INTEGER NOT NULL CHECK (version >= 1),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CHECK (jsonb_typeof(resource_ids) = 'array'),
    CHECK (jsonb_array_length(resource_ids) BETWEEN 1 AND 32)
);

CREATE INDEX IF NOT EXISTS anima_senseguard_alert_policies_household_idx
    ON anima_senseguard_alert_policies (household_id, enabled);
