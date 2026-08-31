-- Phase 10: declarative durable task intent and occurrence leases.
-- This schema stores future intent and provenance, never executable payloads.
CREATE TABLE IF NOT EXISTS anima_durable_tasks (
    task_id UUID PRIMARY KEY,
    household_id UUID NOT NULL,
    task_type TEXT NOT NULL CHECK (task_type IN ('REASONING_DUE', 'EPISODE_CONTINUATION')),
    title TEXT NOT NULL CHECK (length(title) BETWEEN 1 AND 240),
    payload JSONB NOT NULL CHECK (jsonb_typeof(payload) = 'object'),
    schedule JSONB NOT NULL CHECK (jsonb_typeof(schedule) = 'object'),
    timezone TEXT NOT NULL,
    status TEXT NOT NULL CHECK (status IN ('ACTIVE', 'PAUSED', 'CANCELLED', 'COMPLETED', 'FAILED')),
    creator_principal_id UUID,
    creator_episode_id UUID,
    creation_idempotency_key TEXT NOT NULL UNIQUE,
    creation_fingerprint TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL,
    next_run_at TIMESTAMPTZ NOT NULL,
    last_run_at TIMESTAMPTZ,
    recurrence_version INTEGER NOT NULL CHECK (recurrence_version >= 1),
    misfire_policy TEXT NOT NULL CHECK (misfire_policy IN ('FIRE_ONCE_NOW', 'SKIP', 'COALESCE_ONE')),
    max_attempts INTEGER NOT NULL CHECK (max_attempts BETWEEN 1 AND 20),
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb CHECK (jsonb_typeof(metadata) = 'object'),
    provenance JSONB NOT NULL DEFAULT '{}'::jsonb CHECK (jsonb_typeof(provenance) = 'object')
);

CREATE INDEX IF NOT EXISTS anima_durable_tasks_due_idx
    ON anima_durable_tasks (status, next_run_at, task_id);
CREATE INDEX IF NOT EXISTS anima_durable_tasks_household_idx
    ON anima_durable_tasks (household_id, status, next_run_at);

CREATE TABLE IF NOT EXISTS anima_durable_task_runs (
    run_id UUID PRIMARY KEY,
    task_id UUID NOT NULL REFERENCES anima_durable_tasks(task_id),
    scheduled_for TIMESTAMPTZ NOT NULL,
    claimed_at TIMESTAMPTZ,
    claimed_by TEXT,
    lease_expires_at TIMESTAMPTZ,
    attempt INTEGER NOT NULL CHECK (attempt >= 1),
    status TEXT NOT NULL CHECK (status IN ('PENDING', 'CLAIMED', 'DISPATCHING', 'DISPATCHED', 'COMPLETED', 'FAILED', 'CANCELLED', 'MISSED')),
    source_event_id TEXT NOT NULL,
    started_at TIMESTAMPTZ,
    completed_at TIMESTAMPTZ,
    outcome JSONB,
    error_class TEXT,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb CHECK (jsonb_typeof(metadata) = 'object'),
    UNIQUE (task_id, scheduled_for)
);

CREATE INDEX IF NOT EXISTS anima_durable_task_runs_due_idx
    ON anima_durable_task_runs (status, lease_expires_at, scheduled_for);
CREATE INDEX IF NOT EXISTS anima_durable_task_runs_task_idx
    ON anima_durable_task_runs (task_id, scheduled_for);
