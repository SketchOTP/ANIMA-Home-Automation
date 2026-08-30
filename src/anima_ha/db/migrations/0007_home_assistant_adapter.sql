CREATE TABLE IF NOT EXISTS anima_ha_instances (
    instance_id UUID PRIMARY KEY,
    websocket_url TEXT NOT NULL,
    token_secret_name TEXT NOT NULL,
    expected_version TEXT NOT NULL,
    enabled BOOLEAN NOT NULL DEFAULT false,
    health TEXT NOT NULL,
    connected_version TEXT,
    last_state_sync TIMESTAMPTZ,
    last_event_at TIMESTAMPTZ,
    diagnostics JSONB NOT NULL DEFAULT '{}'::jsonb,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CHECK (length(trim(websocket_url)) > 0),
    CHECK (length(trim(token_secret_name)) > 0)
);

CREATE TABLE IF NOT EXISTS anima_ha_provider_inventory (
    instance_id UUID NOT NULL REFERENCES anima_ha_instances(instance_id),
    external_object_kind TEXT NOT NULL,
    external_id TEXT NOT NULL,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    present BOOLEAN NOT NULL DEFAULT true,
    first_seen_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    last_seen_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (instance_id, external_object_kind, external_id),
    CHECK (external_object_kind IN ('area', 'device', 'entity')),
    CHECK (length(trim(external_id)) > 0)
);

CREATE INDEX IF NOT EXISTS anima_ha_provider_inventory_present_idx
    ON anima_ha_provider_inventory (instance_id, external_object_kind)
    WHERE present = true;
