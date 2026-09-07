CREATE TABLE IF NOT EXISTS anima_sentry_voice_settings (
    household_id UUID PRIMARY KEY,
    voice_id TEXT NOT NULL DEFAULT 'bm_george',
    speech_speed NUMERIC(3,2) NOT NULL DEFAULT 0.90 CHECK (speech_speed >= 0.75 AND speech_speed <= 1.30),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
