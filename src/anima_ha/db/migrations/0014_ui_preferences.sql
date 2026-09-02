CREATE TABLE IF NOT EXISTS anima_ui_preferences (
    household_id UUID NOT NULL,
    principal_id UUID NOT NULL,
    preferences JSONB NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (household_id, principal_id),
    CHECK (jsonb_typeof(preferences) = 'object')
);

