-- Phase 13: durable, bounded intelligence-provider request/result boundary.
CREATE TABLE IF NOT EXISTS anima_intelligence_requests (
    request_id UUID PRIMARY KEY,
    trigger_id UUID,
    household_id UUID NOT NULL,
    principal_id UUID,
    origin TEXT NOT NULL CHECK (origin IN (
        'DIRECT_UI_USER', 'AUTONOMOUS_ATTENTION', 'DURABLE_TASK',
        'APPROVAL_RESOLUTION', 'TESTING'
    )),
    correlation_id TEXT,
    causation_id TEXT,
    context_packet_id UUID NOT NULL,
    context_digest TEXT NOT NULL,
    catalogue_digest TEXT NOT NULL,
    provider_id TEXT NOT NULL,
    provider_version TEXT NOT NULL,
    idempotency_key TEXT NOT NULL UNIQUE,
    lifecycle TEXT NOT NULL DEFAULT 'PENDING' CHECK (lifecycle IN (
        'PENDING', 'CLAIMED', 'DELIVERED_TO_PROVIDER', 'PROVIDER_RUNNING',
        'WAITING_CONFIRMATION', 'WAITING_STRONGER_AUTH', 'RESULT_RECEIVED',
        'COMPLETED', 'NO_ACTION', 'FAILED', 'UNKNOWN_RESULT',
        'RECOVERY_REQUIRED', 'CANCELLED'
    )),
    claim_owner TEXT,
    fencing_generation BIGINT NOT NULL DEFAULT 0 CHECK (fencing_generation >= 0),
    lease_expires_at TIMESTAMPTZ,
    attempt_count INTEGER NOT NULL DEFAULT 0 CHECK (attempt_count >= 0),
    request_metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    result_status TEXT,
    response_digest TEXT,
    result_metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    completed_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CHECK (jsonb_typeof(request_metadata) = 'object'),
    CHECK (jsonb_typeof(result_metadata) = 'object')
);

CREATE INDEX IF NOT EXISTS anima_intelligence_requests_claim_idx
    ON anima_intelligence_requests (lifecycle, lease_expires_at, created_at);
CREATE INDEX IF NOT EXISTS anima_intelligence_requests_household_idx
    ON anima_intelligence_requests (household_id, created_at DESC);

CREATE TABLE IF NOT EXISTS anima_intelligence_transitions (
    transition_id BIGSERIAL PRIMARY KEY,
    request_id UUID NOT NULL REFERENCES anima_intelligence_requests(request_id),
    from_lifecycle TEXT,
    to_lifecycle TEXT NOT NULL,
    fencing_generation BIGINT NOT NULL,
    actor TEXT NOT NULL,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CHECK (jsonb_typeof(metadata) = 'object')
);

CREATE INDEX IF NOT EXISTS anima_intelligence_transitions_request_idx
    ON anima_intelligence_transitions (request_id, transition_id);
