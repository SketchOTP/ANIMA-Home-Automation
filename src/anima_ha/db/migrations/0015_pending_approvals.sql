-- Phase 12: durable exact-intent approval continuations.
-- This table stores only a bounded, server-normalized executable envelope;
-- context packets, secrets, and restricted provider content are excluded.
CREATE TABLE IF NOT EXISTS anima_pending_approvals (
    approval_id UUID PRIMARY KEY,
    challenge_id UUID NOT NULL UNIQUE REFERENCES anima_confirmation_challenges(challenge_id),
    action_id UUID NOT NULL UNIQUE REFERENCES anima_actions(action_id),
    action_intent_id UUID NOT NULL,
    household_id UUID NOT NULL,
    principal_id UUID NOT NULL,
    episode_id UUID REFERENCES anima_agent_episodes(episode_id),
    trigger_id UUID,
    tool_id TEXT NOT NULL,
    tool_version TEXT NOT NULL,
    arguments JSONB NOT NULL CHECK (jsonb_typeof(arguments) = 'object'),
    resource_ids JSONB NOT NULL DEFAULT '[]'::jsonb CHECK (jsonb_typeof(resource_ids) = 'array'),
    preconditions JSONB NOT NULL DEFAULT '[]'::jsonb CHECK (jsonb_typeof(preconditions) = 'array'),
    lock_scopes JSONB NOT NULL DEFAULT '[]'::jsonb CHECK (jsonb_typeof(lock_scopes) = 'array'),
    idempotency_key TEXT NOT NULL,
    origin TEXT NOT NULL,
    risk_class TEXT NOT NULL,
    safety_profile TEXT,
    summary TEXT NOT NULL CHECK (length(summary) BETWEEN 1 AND 500),
    issued_at TIMESTAMPTZ NOT NULL,
    expires_at TIMESTAMPTZ NOT NULL,
    status TEXT NOT NULL DEFAULT 'PENDING' CHECK (status IN (
        'PENDING', 'APPROVED', 'REJECTED', 'EXPIRED', 'FAILED'
    )),
    decision TEXT CHECK (decision IS NULL OR decision IN ('APPROVE', 'REJECT')),
    outcome_refs JSONB NOT NULL DEFAULT '{}'::jsonb CHECK (jsonb_typeof(outcome_refs) = 'object'),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CHECK (expires_at > issued_at)
);

CREATE INDEX IF NOT EXISTS anima_pending_approvals_principal_idx
    ON anima_pending_approvals (household_id, principal_id, status, expires_at);

CREATE INDEX IF NOT EXISTS anima_pending_approvals_episode_idx
    ON anima_pending_approvals (episode_id, status);
