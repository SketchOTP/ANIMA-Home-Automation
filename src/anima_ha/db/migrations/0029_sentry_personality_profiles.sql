CREATE TABLE anima_sentry_personality_profiles (
    profile_id UUID PRIMARY KEY,
    household_id UUID NOT NULL,
    name TEXT NOT NULL CHECK (char_length(name) BETWEEN 1 AND 80),
    profile_text TEXT NOT NULL CHECK (char_length(profile_text) BETWEEN 1 AND 4000),
    version UUID NOT NULL,
    active BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE UNIQUE INDEX anima_sentry_personality_household_name_uq
    ON anima_sentry_personality_profiles (household_id, lower(name));

CREATE UNIQUE INDEX anima_sentry_personality_one_active_uq
    ON anima_sentry_personality_profiles (household_id)
    WHERE active;

CREATE INDEX anima_sentry_personality_household_idx
    ON anima_sentry_personality_profiles (household_id, updated_at DESC, profile_id);
