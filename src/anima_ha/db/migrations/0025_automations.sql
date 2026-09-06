-- Goal-wide, declarative household automations.  This is a deliberately
-- narrow event-to-power contract, not a raw Home Assistant automation editor.
CREATE TABLE IF NOT EXISTS anima_automations (
    automation_id UUID PRIMARY KEY,
    household_id UUID NOT NULL,
    name TEXT NOT NULL CHECK (char_length(name) BETWEEN 1 AND 80),
    trigger_resource_id UUID NOT NULL,
    trigger_state TEXT NOT NULL CHECK (trigger_state IN ('on', 'off')),
    action_resource_id UUID NOT NULL,
    action_desired_on BOOLEAN NOT NULL,
    enabled BOOLEAN NOT NULL DEFAULT TRUE,
    creator_principal_id UUID,
    version INTEGER NOT NULL DEFAULT 1 CHECK (version >= 1),
    created_at TIMESTAMPTZ NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL
);

CREATE INDEX IF NOT EXISTS anima_automations_household_idx
    ON anima_automations(household_id, enabled, name, automation_id);
