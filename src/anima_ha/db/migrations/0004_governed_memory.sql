CREATE TABLE IF NOT EXISTS anima_memory_records (
    memory_id UUID PRIMARY KEY,
    household_id UUID NOT NULL,
    subject_id UUID REFERENCES anima_graph_nodes(canonical_id),
    memory_type TEXT NOT NULL CHECK (memory_type IN (
        'EXPLICIT_PREFERENCE', 'EXPLICIT_FACT', 'OBSERVED_CONTEXT',
        'INFERRED_PATTERN', 'INTERACTION_MEMORY', 'AGENT_LESSON',
        'TEMPORARY_EPISODIC'
    )),
    content TEXT NOT NULL CHECK (length(trim(content)) > 0),
    retrieval_text TEXT NOT NULL CHECK (length(trim(retrieval_text)) > 0),
    provenance_kind TEXT NOT NULL CHECK (provenance_kind IN (
        'EXPLICIT_INPUT', 'EVENT_JOURNAL', 'TRUTH_OBSERVATION',
        'HOUSEHOLD_GRAPH', 'INFERRED_FROM_HISTORY', 'PRIOR_MEMORY',
        'AGENT_LESSON'
    )),
    source_ref TEXT NOT NULL CHECK (length(trim(source_ref)) > 0),
    source_event_id TEXT,
    created_at TIMESTAMPTZ NOT NULL,
    valid_from TIMESTAMPTZ,
    valid_until TIMESTAMPTZ,
    confidence DOUBLE PRECISION,
    expires_at TIMESTAMPTZ,
    status TEXT NOT NULL CHECK (status IN ('ACTIVE', 'SUPERSEDED', 'EXPIRED', 'RETRACTED')),
    supersedes_memory_id UUID REFERENCES anima_memory_records(memory_id),
    superseded_by_memory_id UUID REFERENCES anima_memory_records(memory_id),
    graph_refs JSONB NOT NULL DEFAULT '[]'::jsonb CHECK (jsonb_typeof(graph_refs) = 'array'),
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb CHECK (jsonb_typeof(metadata) = 'object'),
    CHECK (confidence IS NULL OR (confidence >= 0 AND confidence <= 1)),
    CHECK (valid_until IS NULL OR valid_from IS NULL OR valid_until >= valid_from),
    CHECK (supersedes_memory_id IS NULL OR supersedes_memory_id <> memory_id),
    CHECK (superseded_by_memory_id IS NULL OR superseded_by_memory_id <> memory_id)
);

CREATE INDEX IF NOT EXISTS anima_memory_household_active_idx
    ON anima_memory_records (household_id, status, created_at DESC);
CREATE INDEX IF NOT EXISTS anima_memory_subject_idx
    ON anima_memory_records (household_id, subject_id, status);
CREATE INDEX IF NOT EXISTS anima_memory_type_idx
    ON anima_memory_records (household_id, memory_type, status);
CREATE INDEX IF NOT EXISTS anima_memory_expiry_idx
    ON anima_memory_records (household_id, expires_at) WHERE status = 'ACTIVE';

CREATE TABLE IF NOT EXISTS anima_memory_search_index (
    memory_id UUID PRIMARY KEY REFERENCES anima_memory_records(memory_id),
    search_document TSVECTOR NOT NULL,
    indexed_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS anima_memory_search_document_idx
    ON anima_memory_search_index USING GIN (search_document);

CREATE TABLE IF NOT EXISTS anima_routine_models (
    routine_id UUID PRIMARY KEY,
    household_id UUID NOT NULL,
    model_key TEXT NOT NULL,
    model_version INTEGER NOT NULL CHECK (model_version > 0),
    subject_id UUID REFERENCES anima_graph_nodes(canonical_id),
    label TEXT NOT NULL CHECK (length(trim(label)) > 0),
    model JSONB NOT NULL CHECK (jsonb_typeof(model) = 'object'),
    confidence DOUBLE PRECISION NOT NULL CHECK (confidence >= 0 AND confidence <= 1),
    sample_count INTEGER NOT NULL CHECK (sample_count >= 0),
    source_start TIMESTAMPTZ,
    source_end TIMESTAMPTZ,
    source_event_ids JSONB NOT NULL DEFAULT '[]'::jsonb CHECK (jsonb_typeof(source_event_ids) = 'array'),
    generated_at TIMESTAMPTZ NOT NULL,
    UNIQUE (household_id, model_key, model_version)
);

CREATE INDEX IF NOT EXISTS anima_routine_household_idx
    ON anima_routine_models (household_id, model_key, model_version);
