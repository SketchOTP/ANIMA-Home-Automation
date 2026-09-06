-- Goal-wide owner-facing notification route metadata.
CREATE TABLE IF NOT EXISTS anima_notification_routes (
    route_id UUID PRIMARY KEY,
    household_id UUID NOT NULL,
    provider_id TEXT NOT NULL CHECK (provider_id = 'anima.external.notifications'),
    destination_ref TEXT NOT NULL CHECK (destination_ref = 'configured_ntfy'),
    label TEXT NOT NULL CHECK (char_length(label) BETWEEN 1 AND 80),
    enabled BOOLEAN NOT NULL DEFAULT TRUE,
    minimum_priority INTEGER NOT NULL DEFAULT 0 CHECK (minimum_priority BETWEEN 0 AND 100),
    creator_principal_id UUID,
    version INTEGER NOT NULL DEFAULT 1 CHECK (version >= 1),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS anima_notification_routes_household_idx
    ON anima_notification_routes(household_id, route_id);

CREATE UNIQUE INDEX IF NOT EXISTS anima_notification_routes_destination_idx
    ON anima_notification_routes(household_id, provider_id, destination_ref);
