CREATE TABLE IF NOT EXISTS anima_agent_episodes (
    episode_id UUID PRIMARY KEY,
    trigger_id UUID NOT NULL UNIQUE REFERENCES anima_reasoning_triggers(trigger_id),
    context_packet_id UUID NOT NULL REFERENCES anima_context_packets(context_packet_id),
    household_id UUID NOT NULL,
    context_digest TEXT NOT NULL,
    cloud_projection_digest TEXT NOT NULL,
    cloud_payload_bytes INTEGER NOT NULL CHECK (cloud_payload_bytes >= 0),
    cloud_omission_count INTEGER NOT NULL CHECK (cloud_omission_count >= 0),
    instruction_version TEXT NOT NULL,
    codex_version TEXT NOT NULL,
    model TEXT NOT NULL,
    reasoning_effort TEXT NOT NULL,
    status TEXT NOT NULL CHECK (status IN (
        'PENDING', 'RUNNING', 'WAITING_CONFIRMATION', 'WAITING_STRONGER_AUTH',
        'COMPLETED', 'NO_ACTION', 'FAILED', 'TIMED_OUT', 'BUDGET_EXHAUSTED',
        'MODEL_REFUSED', 'BOUNDARY_VIOLATION'
    )),
    started_at TIMESTAMPTZ NOT NULL,
    completed_at TIMESTAMPTZ,
    codex_turn_count INTEGER NOT NULL DEFAULT 0 CHECK (codex_turn_count >= 0),
    tool_request_count INTEGER NOT NULL DEFAULT 0 CHECK (tool_request_count >= 0),
    input_tokens BIGINT NOT NULL DEFAULT 0 CHECK (input_tokens >= 0),
    cached_input_tokens BIGINT NOT NULL DEFAULT 0 CHECK (cached_input_tokens >= 0),
    output_tokens BIGINT NOT NULL DEFAULT 0 CHECK (output_tokens >= 0),
    reasoning_output_tokens BIGINT NOT NULL DEFAULT 0 CHECK (reasoning_output_tokens >= 0),
    final_disposition TEXT,
    response_text TEXT,
    failure_class TEXT,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    CHECK (jsonb_typeof(metadata) = 'object')
);

CREATE INDEX IF NOT EXISTS anima_agent_episodes_status_idx
    ON anima_agent_episodes (status, started_at, episode_id);

CREATE TABLE IF NOT EXISTS anima_agent_turns (
    episode_id UUID NOT NULL REFERENCES anima_agent_episodes(episode_id),
    turn_number INTEGER NOT NULL CHECK (turn_number > 0),
    decision JSONB,
    safe_event_types JSONB NOT NULL DEFAULT '[]'::jsonb,
    input_tokens BIGINT NOT NULL DEFAULT 0 CHECK (input_tokens >= 0),
    cached_input_tokens BIGINT NOT NULL DEFAULT 0 CHECK (cached_input_tokens >= 0),
    output_tokens BIGINT NOT NULL DEFAULT 0 CHECK (output_tokens >= 0),
    reasoning_output_tokens BIGINT NOT NULL DEFAULT 0 CHECK (reasoning_output_tokens >= 0),
    latency_ms DOUBLE PRECISION NOT NULL CHECK (latency_ms >= 0),
    error_class TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (episode_id, turn_number),
    CHECK (decision IS NULL OR jsonb_typeof(decision) = 'object'),
    CHECK (jsonb_typeof(safe_event_types) = 'array')
);

CREATE TABLE IF NOT EXISTS anima_agent_tool_requests (
    episode_id UUID NOT NULL REFERENCES anima_agent_episodes(episode_id),
    request_number INTEGER NOT NULL CHECK (request_number > 0),
    turn_number INTEGER NOT NULL CHECK (turn_number > 0),
    tool_id TEXT NOT NULL,
    arguments JSONB NOT NULL,
    outcome TEXT NOT NULL,
    sanitized_result JSONB,
    external_content_trust TEXT NOT NULL,
    elapsed_ms DOUBLE PRECISION NOT NULL CHECK (elapsed_ms >= 0),
    policy_decision_id UUID,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (episode_id, request_number),
    CHECK (jsonb_typeof(arguments) = 'object'),
    CHECK (sanitized_result IS NULL OR jsonb_typeof(sanitized_result) IN ('object', 'array', 'string', 'number', 'boolean', 'null'))
);
