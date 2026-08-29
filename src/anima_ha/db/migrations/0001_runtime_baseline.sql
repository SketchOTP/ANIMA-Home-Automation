CREATE TABLE IF NOT EXISTS anima_runtime_metadata (
    component TEXT PRIMARY KEY,
    version TEXT NOT NULL,
    recorded_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

INSERT INTO anima_runtime_metadata (component, version)
VALUES ('anima-ha-runtime', '0.1.0')
ON CONFLICT (component) DO NOTHING;
