CREATE TABLE IF NOT EXISTS anima_ui_sessions (
    session_id UUID PRIMARY KEY,
    secret_hash TEXT NOT NULL,
    household_id UUID NOT NULL,
    principal_id UUID NOT NULL,
    created_at TIMESTAMPTZ NOT NULL,
    last_seen_at TIMESTAMPTZ NOT NULL,
    expires_at TIMESTAMPTZ NOT NULL,
    device_label TEXT,
    csrf_hash TEXT NOT NULL,
    revoked_at TIMESTAMPTZ,
    CHECK (length(secret_hash) = 64),
    CHECK (length(csrf_hash) = 64),
    CHECK (expires_at > created_at)
);

CREATE INDEX IF NOT EXISTS anima_ui_sessions_expiry_idx
    ON anima_ui_sessions (expires_at)
    WHERE revoked_at IS NULL;
