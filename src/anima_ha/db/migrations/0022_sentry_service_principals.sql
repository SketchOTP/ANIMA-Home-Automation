-- Phase 13 R2: ANIMA-owned SENTRY client identity registration.
CREATE TABLE IF NOT EXISTS anima_sentry_service_principals (
    client_id TEXT PRIMARY KEY,
    household_id UUID NOT NULL,
    provider_id TEXT NOT NULL CHECK (provider_id = 'sentry'),
    credential_generation BIGINT NOT NULL CHECK (credential_generation >= 1),
    token_digest TEXT NOT NULL,
    enabled BOOLEAN NOT NULL DEFAULT true,
    allowed_origins JSONB NOT NULL DEFAULT '["DIRECT_SENTRY_INTERACTION", "SENTRY_PROVIDER"]'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CHECK (jsonb_typeof(allowed_origins) = 'array')
);
