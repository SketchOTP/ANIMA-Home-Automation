CREATE TABLE IF NOT EXISTS anima_event_journal (
    journal_position BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    event_id TEXT NOT NULL UNIQUE,
    schema_version INTEGER NOT NULL,
    event_type TEXT NOT NULL,
    source TEXT NOT NULL,
    source_event_id TEXT,
    subject_key TEXT NOT NULL,
    occurred_at TIMESTAMPTZ NOT NULL,
    recorded_at TIMESTAMPTZ NOT NULL,
    source_sequence BIGINT,
    correlation_id TEXT,
    causation_id TEXT,
    confidence DOUBLE PRECISION,
    evidence_kind TEXT NOT NULL,
    importance TEXT NOT NULL,
    delivery_class TEXT NOT NULL,
    payload JSONB NOT NULL,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    CHECK (jsonb_typeof(payload) = 'object'),
    CHECK (jsonb_typeof(metadata) = 'object'),
    CHECK (confidence IS NULL OR (confidence >= 0 AND confidence <= 1)),
    CHECK (source_sequence IS NULL OR source_sequence >= 0)
);

CREATE UNIQUE INDEX IF NOT EXISTS anima_event_source_identity
    ON anima_event_journal (source, source_event_id)
    WHERE source_event_id IS NOT NULL;

CREATE INDEX IF NOT EXISTS anima_event_journal_time_idx
    ON anima_event_journal (occurred_at, journal_position);
CREATE INDEX IF NOT EXISTS anima_event_journal_type_idx
    ON anima_event_journal (event_type, journal_position);
CREATE INDEX IF NOT EXISTS anima_event_journal_source_idx
    ON anima_event_journal (source, journal_position);
CREATE INDEX IF NOT EXISTS anima_event_journal_subject_idx
    ON anima_event_journal (subject_key, journal_position);
CREATE INDEX IF NOT EXISTS anima_event_journal_correlation_idx
    ON anima_event_journal (correlation_id, journal_position);

CREATE OR REPLACE FUNCTION anima_event_journal_append_only() RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
    RAISE EXCEPTION 'anima_event_journal is append-only';
END;
$$;

DROP TRIGGER IF EXISTS anima_event_journal_no_update ON anima_event_journal;
CREATE TRIGGER anima_event_journal_no_update
    BEFORE UPDATE OR DELETE ON anima_event_journal
    FOR EACH ROW EXECUTE FUNCTION anima_event_journal_append_only();

CREATE TABLE IF NOT EXISTS anima_truth_observations (
    event_id TEXT PRIMARY KEY REFERENCES anima_event_journal(event_id),
    journal_position BIGINT NOT NULL,
    truth_key TEXT NOT NULL,
    source TEXT NOT NULL,
    state TEXT NOT NULL CHECK (state IN ('KNOWN', 'UNKNOWN', 'UNAVAILABLE')),
    value JSONB,
    observed_at TIMESTAMPTZ NOT NULL,
    received_at TIMESTAMPTZ NOT NULL,
    source_sequence BIGINT,
    confidence DOUBLE PRECISION,
    evidence_kind TEXT NOT NULL,
    freshness_seconds BIGINT,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    CHECK (state <> 'KNOWN' OR value IS NOT NULL OR evidence_kind IN ('UNKNOWN', 'UNAVAILABLE')),
    CHECK (state = 'KNOWN' OR value IS NULL),
    CHECK (confidence IS NULL OR (confidence >= 0 AND confidence <= 1)),
    CHECK (freshness_seconds IS NULL OR freshness_seconds >= 0)
);

CREATE INDEX IF NOT EXISTS anima_truth_observations_key_idx
    ON anima_truth_observations (truth_key, source, observed_at, journal_position);

CREATE TABLE IF NOT EXISTS anima_truth_state (
    truth_key TEXT PRIMARY KEY,
    status TEXT NOT NULL,
    value JSONB,
    confidence DOUBLE PRECISION,
    evidence_kind TEXT,
    last_observed_at TIMESTAMPTZ,
    last_received_at TIMESTAMPTZ,
    resolution JSONB NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS anima_projection_checkpoints (
    projection_name TEXT PRIMARY KEY,
    last_position BIGINT NOT NULL DEFAULT 0,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    last_error TEXT
);

CREATE TABLE IF NOT EXISTS anima_projection_failures (
    projection_name TEXT NOT NULL,
    journal_position BIGINT NOT NULL,
    error TEXT NOT NULL,
    failed_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    retry_count INTEGER NOT NULL DEFAULT 1,
    PRIMARY KEY (projection_name, journal_position)
);
