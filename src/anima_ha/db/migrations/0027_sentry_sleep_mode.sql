ALTER TABLE anima_sentry_voice_settings
    ADD COLUMN IF NOT EXISTS sleep_enabled BOOLEAN NOT NULL DEFAULT FALSE;
