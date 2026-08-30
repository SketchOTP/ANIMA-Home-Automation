CREATE TABLE IF NOT EXISTS anima_attention_profiles (
    profile_version TEXT PRIMARY KEY,
    profile_digest TEXT NOT NULL UNIQUE,
    configuration JSONB NOT NULL,
    activated_at TIMESTAMPTZ NOT NULL,
    active BOOLEAN NOT NULL DEFAULT FALSE,
    CHECK (jsonb_typeof(configuration) = 'object')
);

CREATE UNIQUE INDEX IF NOT EXISTS anima_attention_one_active_profile
    ON anima_attention_profiles (active) WHERE active;

CREATE TABLE IF NOT EXISTS anima_attention_cursors (
    consumer_name TEXT PRIMARY KEY,
    profile_version TEXT NOT NULL REFERENCES anima_attention_profiles(profile_version),
    last_position BIGINT NOT NULL DEFAULT 0,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    last_error TEXT
);

CREATE TABLE IF NOT EXISTS anima_attention_decisions (
    attention_decision_id UUID PRIMARY KEY,
    idempotency_key TEXT NOT NULL UNIQUE,
    source_event_id TEXT NOT NULL REFERENCES anima_event_journal(event_id),
    journal_position BIGINT NOT NULL,
    attention_profile_version TEXT NOT NULL REFERENCES anima_attention_profiles(profile_version),
    decision TEXT NOT NULL CHECK (decision IN (
        'TRIGGER', 'SUPPRESS', 'AGGREGATE_PENDING', 'AGGREGATE_TRIGGER'
    )),
    reason_code TEXT NOT NULL,
    correlation_key TEXT,
    aggregation_key TEXT,
    created_at TIMESTAMPTZ NOT NULL,
    resulting_trigger_id UUID,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    CHECK (jsonb_typeof(metadata) = 'object')
);

CREATE INDEX IF NOT EXISTS anima_attention_decisions_position_idx
    ON anima_attention_decisions (journal_position, attention_decision_id);
CREATE INDEX IF NOT EXISTS anima_attention_decisions_profile_idx
    ON anima_attention_decisions (attention_profile_version, decision, reason_code);

CREATE TABLE IF NOT EXISTS anima_reasoning_triggers (
    trigger_id UUID PRIMARY KEY,
    decision_id UUID NOT NULL UNIQUE REFERENCES anima_attention_decisions(attention_decision_id),
    trigger_type TEXT NOT NULL,
    source_event_ids JSONB NOT NULL,
    journal_position_start BIGINT NOT NULL,
    journal_position_end BIGINT NOT NULL,
    subject_refs JSONB NOT NULL,
    correlation_id TEXT,
    attention_reason TEXT NOT NULL,
    priority INTEGER NOT NULL CHECK (priority BETWEEN 0 AND 100),
    created_at TIMESTAMPTZ NOT NULL,
    attention_profile_version TEXT NOT NULL REFERENCES anima_attention_profiles(profile_version),
    context_status TEXT NOT NULL DEFAULT 'PENDING'
        CHECK (context_status IN ('PENDING', 'CONTEXT_READY', 'FAILED_CONTEXT')),
    status TEXT NOT NULL DEFAULT 'PENDING' CHECK (status IN ('PENDING', 'CONTEXT_READY', 'FAILED_CONTEXT')),
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    CHECK (jsonb_typeof(source_event_ids) = 'array'),
    CHECK (jsonb_typeof(subject_refs) = 'array'),
    CHECK (journal_position_end >= journal_position_start)
);

ALTER TABLE anima_attention_decisions
    DROP CONSTRAINT IF EXISTS anima_attention_decisions_resulting_trigger_id_fkey;
ALTER TABLE anima_attention_decisions
    ADD CONSTRAINT anima_attention_decisions_resulting_trigger_id_fkey
    FOREIGN KEY (resulting_trigger_id) REFERENCES anima_reasoning_triggers(trigger_id)
    DEFERRABLE INITIALLY DEFERRED;

CREATE INDEX IF NOT EXISTS anima_reasoning_triggers_pending_idx
    ON anima_reasoning_triggers (status, created_at, trigger_id);

CREATE TABLE IF NOT EXISTS anima_attention_cooldowns (
    profile_version TEXT NOT NULL REFERENCES anima_attention_profiles(profile_version),
    household_scope TEXT NOT NULL,
    rule_id TEXT NOT NULL,
    subject_key TEXT NOT NULL,
    last_trigger_at TIMESTAMPTZ NOT NULL,
    PRIMARY KEY (profile_version, household_scope, rule_id, subject_key)
);

CREATE TABLE IF NOT EXISTS anima_attention_rate_windows (
    profile_version TEXT NOT NULL REFERENCES anima_attention_profiles(profile_version),
    household_scope TEXT NOT NULL,
    rule_id TEXT NOT NULL,
    window_start TIMESTAMPTZ NOT NULL,
    trigger_count INTEGER NOT NULL CHECK (trigger_count >= 0),
    PRIMARY KEY (profile_version, household_scope, rule_id, window_start)
);

CREATE TABLE IF NOT EXISTS anima_attention_aggregates (
    aggregate_id UUID PRIMARY KEY,
    idempotency_key TEXT NOT NULL UNIQUE,
    profile_version TEXT NOT NULL REFERENCES anima_attention_profiles(profile_version),
    household_scope TEXT NOT NULL,
    rule_id TEXT NOT NULL,
    aggregation_key TEXT NOT NULL,
    event_type TEXT NOT NULL,
    subject_key TEXT NOT NULL,
    window_start TIMESTAMPTZ NOT NULL,
    window_end TIMESTAMPTZ NOT NULL,
    event_count INTEGER NOT NULL CHECK (event_count > 0),
    first_seen TIMESTAMPTZ NOT NULL,
    last_seen TIMESTAMPTZ NOT NULL,
    source_event_ids JSONB NOT NULL,
    journal_positions JSONB NOT NULL,
    closed_at TIMESTAMPTZ,
    resulting_trigger_id UUID REFERENCES anima_reasoning_triggers(trigger_id),
    CHECK (jsonb_typeof(source_event_ids) = 'array'),
    CHECK (jsonb_typeof(journal_positions) = 'array'),
    CHECK (window_end > window_start)
);

CREATE INDEX IF NOT EXISTS anima_attention_aggregates_due_idx
    ON anima_attention_aggregates (profile_version, window_end) WHERE closed_at IS NULL;

CREATE TABLE IF NOT EXISTS anima_attention_failures (
    consumer_name TEXT NOT NULL,
    journal_position BIGINT NOT NULL,
    source_event_id TEXT NOT NULL,
    error_class TEXT NOT NULL,
    error_message TEXT NOT NULL,
    failed_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    retry_count INTEGER NOT NULL DEFAULT 1,
    resolved_at TIMESTAMPTZ,
    PRIMARY KEY (consumer_name, journal_position)
);

CREATE TABLE IF NOT EXISTS anima_context_packets (
    context_packet_id UUID PRIMARY KEY,
    trigger_id UUID NOT NULL UNIQUE REFERENCES anima_reasoning_triggers(trigger_id),
    schema_version INTEGER NOT NULL,
    selection_profile_version TEXT NOT NULL,
    assembled_at TIMESTAMPTZ NOT NULL,
    packet_digest TEXT NOT NULL,
    packet JSONB NOT NULL,
    serialized_bytes INTEGER NOT NULL CHECK (serialized_bytes > 0),
    CHECK (jsonb_typeof(packet) = 'object')
);

CREATE TABLE IF NOT EXISTS anima_attention_metrics (
    profile_version TEXT NOT NULL,
    metric_name TEXT NOT NULL,
    metric_value BIGINT NOT NULL DEFAULT 0,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (profile_version, metric_name)
);

CREATE OR REPLACE FUNCTION anima_attention_immutable() RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
    RAISE EXCEPTION '% is append-only', TG_TABLE_NAME;
END;
$$;

DROP TRIGGER IF EXISTS anima_attention_decisions_no_update ON anima_attention_decisions;
CREATE TRIGGER anima_attention_decisions_no_update
    BEFORE UPDATE OR DELETE ON anima_attention_decisions
    FOR EACH ROW EXECUTE FUNCTION anima_attention_immutable();

DROP TRIGGER IF EXISTS anima_context_packets_no_update ON anima_context_packets;
CREATE TRIGGER anima_context_packets_no_update
    BEFORE UPDATE OR DELETE ON anima_context_packets
    FOR EACH ROW EXECUTE FUNCTION anima_attention_immutable();
