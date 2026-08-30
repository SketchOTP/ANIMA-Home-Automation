CREATE TABLE IF NOT EXISTS anima_actions (
    action_id UUID PRIMARY KEY,
    idempotency_key TEXT NOT NULL UNIQUE,
    request_digest TEXT NOT NULL,
    household_id UUID NOT NULL,
    tool_id TEXT NOT NULL,
    arguments JSONB NOT NULL,
    resource_ids JSONB NOT NULL DEFAULT '[]'::jsonb,
    preconditions JSONB NOT NULL DEFAULT '[]'::jsonb,
    status TEXT NOT NULL CHECK (status IN (
        'PLANNED', 'EXECUTING', 'SUCCEEDED', 'FAILED', 'RESOURCE_BUSY',
        'PRECONDITION_FAILED', 'POLICY_DENIED', 'REQUIRE_CONFIRMATION',
        'REQUIRE_STRONGER_AUTH', 'VERIFICATION_FAILED', 'UNKNOWN_RESULT',
        'PARTIAL', 'RECOVERY_REQUIRED'
    )),
    detail TEXT,
    result JSONB,
    latest_truth JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL,
    CHECK (jsonb_typeof(arguments) = 'object'),
    CHECK (jsonb_typeof(resource_ids) = 'array'),
    CHECK (jsonb_typeof(preconditions) = 'array'),
    CHECK (jsonb_typeof(latest_truth) = 'object')
);

CREATE INDEX IF NOT EXISTS anima_actions_status_idx
    ON anima_actions (status, updated_at, action_id);

CREATE TABLE IF NOT EXISTS anima_action_effects (
    effect_id UUID PRIMARY KEY,
    action_id UUID NOT NULL REFERENCES anima_actions(action_id),
    effect_index INTEGER NOT NULL CHECK (effect_index >= 0),
    outcome TEXT NOT NULL,
    observed JSONB,
    detail TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (action_id, effect_index),
    CHECK (observed IS NULL OR jsonb_typeof(observed) IN ('object', 'array', 'string', 'number', 'boolean', 'null'))
);
