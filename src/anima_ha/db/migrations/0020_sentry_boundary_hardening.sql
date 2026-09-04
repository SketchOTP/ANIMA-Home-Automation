-- Phase 13 R1: durable request catalogue and provider ambiguity fencing.
ALTER TABLE anima_intelligence_requests
    ADD COLUMN IF NOT EXISTS request_catalogue JSONB NOT NULL DEFAULT '[]'::jsonb,
    ADD COLUMN IF NOT EXISTS provider_invocation_started BOOLEAN NOT NULL DEFAULT false;

ALTER TABLE anima_intelligence_requests
    DROP CONSTRAINT IF EXISTS anima_intelligence_requests_origin_check;
ALTER TABLE anima_intelligence_requests
    ADD CONSTRAINT anima_intelligence_requests_origin_check CHECK (origin IN (
        'DIRECT_UI_USER', 'DIRECT_SENTRY_INTERACTION', 'AUTONOMOUS_ATTENTION',
        'DURABLE_TASK', 'APPROVAL_RESOLUTION', 'TESTING'
    ));

ALTER TABLE anima_intelligence_requests
    ADD CONSTRAINT anima_intelligence_requests_catalogue_object_check
    CHECK (jsonb_typeof(request_catalogue) = 'array');
