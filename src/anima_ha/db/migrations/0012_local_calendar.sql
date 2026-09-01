-- Phase 11: first-party local calendar events.
CREATE TABLE IF NOT EXISTS anima_calendar_events (
    event_id UUID PRIMARY KEY,
    household_id UUID NOT NULL,
    title TEXT NOT NULL CHECK (length(title) BETWEEN 1 AND 200),
    start_at TIMESTAMPTZ NOT NULL,
    end_at TIMESTAMPTZ NOT NULL,
    timezone TEXT NOT NULL CHECK (length(timezone) BETWEEN 1 AND 64),
    location TEXT NOT NULL DEFAULT '' CHECK (length(location) <= 500),
    description TEXT NOT NULL DEFAULT '' CHECK (length(description) <= 4000),
    status TEXT NOT NULL CHECK (status IN ('ACTIVE', 'CANCELLED')),
    version INTEGER NOT NULL CHECK (version >= 1),
    creator_principal_id UUID,
    creator_episode_id UUID,
    creation_idempotency_key TEXT NOT NULL UNIQUE,
    creation_fingerprint TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL,
    CHECK (end_at > start_at)
);

CREATE INDEX IF NOT EXISTS anima_calendar_events_window_idx
    ON anima_calendar_events (household_id, status, start_at, end_at, event_id);
