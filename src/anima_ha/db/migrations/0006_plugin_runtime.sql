CREATE TABLE IF NOT EXISTS anima_plugins (
    plugin_id TEXT PRIMARY KEY,
    plugin_version TEXT NOT NULL,
    manifest_version INTEGER NOT NULL,
    requires_core TEXT NOT NULL,
    name TEXT NOT NULL,
    runtime_kind TEXT NOT NULL,
    trust_class TEXT NOT NULL,
    state TEXT NOT NULL,
    enabled BOOLEAN NOT NULL DEFAULT FALSE,
    configuration JSONB NOT NULL DEFAULT '{}'::jsonb,
    manifest JSONB NOT NULL,
    last_error TEXT,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS anima_plugin_tools (
    tool_id TEXT PRIMARY KEY,
    plugin_id TEXT NOT NULL REFERENCES anima_plugins(plugin_id),
    descriptor JSONB NOT NULL,
    available BOOLEAN NOT NULL DEFAULT FALSE,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS anima_plugin_tools_plugin_idx ON anima_plugin_tools(plugin_id);
