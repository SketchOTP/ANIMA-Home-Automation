-- Goal-wide, declarative household scenes.  A scene is a named preset of
-- canonical power intents; it is not an executable Home Assistant payload.
CREATE TABLE IF NOT EXISTS anima_scenes (
    scene_id UUID PRIMARY KEY,
    household_id UUID NOT NULL,
    name TEXT NOT NULL CHECK (char_length(name) BETWEEN 1 AND 80),
    steps JSONB NOT NULL CHECK (jsonb_typeof(steps) = 'array'),
    enabled BOOLEAN NOT NULL DEFAULT TRUE,
    creator_principal_id UUID,
    version INTEGER NOT NULL DEFAULT 1 CHECK (version >= 1),
    created_at TIMESTAMPTZ NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL
);

CREATE INDEX IF NOT EXISTS anima_scenes_household_idx
    ON anima_scenes(household_id, enabled, name, scene_id);
