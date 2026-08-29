CREATE TABLE IF NOT EXISTS anima_graph_nodes (
    canonical_id UUID PRIMARY KEY,
    kind TEXT NOT NULL CHECK (kind IN (
        'HOUSEHOLD', 'PROPERTY', 'BUILDING', 'FLOOR', 'ROOM', 'ZONE', 'OUTSIDE',
        'ENTRANCE', 'RESOURCE', 'SENSOR', 'PERSON', 'PET', 'VEHICLE', 'CAPABILITY'
    )),
    name TEXT NOT NULL CHECK (length(trim(name)) > 0),
    security_sensitive BOOLEAN NOT NULL DEFAULT false,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    retired_at TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS anima_graph_nodes_kind_idx
    ON anima_graph_nodes (kind) WHERE retired_at IS NULL;

CREATE TABLE IF NOT EXISTS anima_graph_relationships (
    relationship_id UUID PRIMARY KEY,
    relationship_type TEXT NOT NULL CHECK (relationship_type IN (
        'CONTAINS', 'MEMBER_OF', 'CONNECTS', 'INSTALLED_IN', 'EXPOSES',
        'MONITORS', 'CONTROLS', 'COVERS', 'ASSOCIATED_WITH'
    )),
    source_id UUID NOT NULL REFERENCES anima_graph_nodes(canonical_id),
    target_id UUID NOT NULL REFERENCES anima_graph_nodes(canonical_id),
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    retired_at TIMESTAMPTZ,
    CONSTRAINT anima_graph_relationship_distinct CHECK (source_id <> target_id)
);

CREATE UNIQUE INDEX IF NOT EXISTS anima_graph_relationship_active_idx
    ON anima_graph_relationships (relationship_type, source_id, target_id)
    WHERE retired_at IS NULL;
CREATE INDEX IF NOT EXISTS anima_graph_relationship_source_idx
    ON anima_graph_relationships (source_id) WHERE retired_at IS NULL;
CREATE INDEX IF NOT EXISTS anima_graph_relationship_target_idx
    ON anima_graph_relationships (target_id) WHERE retired_at IS NULL;

CREATE TABLE IF NOT EXISTS anima_graph_aliases (
    alias_id UUID PRIMARY KEY,
    normalized_alias TEXT NOT NULL,
    display_alias TEXT NOT NULL,
    canonical_id UUID NOT NULL REFERENCES anima_graph_nodes(canonical_id),
    node_kind TEXT NOT NULL CHECK (node_kind IN (
        'HOUSEHOLD', 'PROPERTY', 'BUILDING', 'FLOOR', 'ROOM', 'ZONE', 'OUTSIDE',
        'ENTRANCE', 'RESOURCE', 'SENSOR', 'PERSON', 'PET', 'VEHICLE', 'CAPABILITY'
    )),
    scope_id UUID REFERENCES anima_graph_nodes(canonical_id),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    retired_at TIMESTAMPTZ
);

CREATE UNIQUE INDEX IF NOT EXISTS anima_graph_alias_active_idx
    ON anima_graph_aliases (normalized_alias, canonical_id, COALESCE(scope_id, '00000000-0000-0000-0000-000000000000'::uuid))
    WHERE retired_at IS NULL;
CREATE INDEX IF NOT EXISTS anima_graph_alias_lookup_idx
    ON anima_graph_aliases (normalized_alias, node_kind) WHERE retired_at IS NULL;

CREATE TABLE IF NOT EXISTS anima_graph_provider_refs (
    provider_reference_id UUID PRIMARY KEY,
    provider TEXT NOT NULL,
    provider_scope TEXT NOT NULL,
    external_object_kind TEXT NOT NULL,
    external_id TEXT NOT NULL,
    target_id UUID NOT NULL REFERENCES anima_graph_nodes(canonical_id),
    target_kind TEXT NOT NULL CHECK (target_kind IN ('NODE', 'CAPABILITY')),
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    retired_at TIMESTAMPTZ,
    CHECK (length(trim(provider)) > 0 AND length(trim(provider_scope)) > 0),
    CHECK (length(trim(external_object_kind)) > 0 AND length(trim(external_id)) > 0)
);

CREATE UNIQUE INDEX IF NOT EXISTS anima_graph_provider_ref_active_idx
    ON anima_graph_provider_refs (provider, provider_scope, external_object_kind, external_id)
    WHERE retired_at IS NULL;
CREATE INDEX IF NOT EXISTS anima_graph_provider_ref_target_idx
    ON anima_graph_provider_refs (target_id) WHERE retired_at IS NULL;

CREATE TABLE IF NOT EXISTS anima_graph_truth_bindings (
    binding_id UUID PRIMARY KEY,
    target_id UUID NOT NULL REFERENCES anima_graph_nodes(canonical_id),
    target_kind TEXT NOT NULL CHECK (target_kind IN ('NODE', 'CAPABILITY')),
    truth_key TEXT NOT NULL,
    semantic_attribute TEXT NOT NULL,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    retired_at TIMESTAMPTZ,
    UNIQUE (target_id, truth_key, semantic_attribute)
);

CREATE INDEX IF NOT EXISTS anima_graph_truth_binding_target_idx
    ON anima_graph_truth_bindings (target_id) WHERE retired_at IS NULL;
CREATE INDEX IF NOT EXISTS anima_graph_truth_binding_key_idx
    ON anima_graph_truth_bindings (truth_key) WHERE retired_at IS NULL;
