ALTER TABLE anima_sentry_voice_settings
    ADD COLUMN IF NOT EXISTS active_instance_id TEXT NOT NULL DEFAULT 'living_room'
    CHECK (active_instance_id IN ('living_room', 'office'));
