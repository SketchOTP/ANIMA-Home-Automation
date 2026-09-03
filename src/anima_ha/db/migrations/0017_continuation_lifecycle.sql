-- H5V-R1: durable continuation preflight, fencing, and bounded runtime identity.
ALTER TABLE anima_agent_continuations
    ADD COLUMN IF NOT EXISTS continuation_status TEXT NOT NULL DEFAULT 'ACTION_RESOLVED',
    ADD COLUMN IF NOT EXISTS schema_version INTEGER NOT NULL DEFAULT 1,
    ADD COLUMN IF NOT EXISTS fencing_generation BIGINT NOT NULL DEFAULT 0,
    ADD COLUMN IF NOT EXISTS claim_owner TEXT,
    ADD COLUMN IF NOT EXISTS claimed_at TIMESTAMPTZ,
    ADD COLUMN IF NOT EXISTS claim_expires_at TIMESTAMPTZ,
    ADD COLUMN IF NOT EXISTS last_transition_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    ADD COLUMN IF NOT EXISTS transcript_digest_before TEXT,
    ADD COLUMN IF NOT EXISTS tool_catalogue JSONB NOT NULL DEFAULT '[]'::jsonb,
    ADD COLUMN IF NOT EXISTS tool_catalogue_digest TEXT,
    ADD COLUMN IF NOT EXISTS runtime_identity JSONB NOT NULL DEFAULT '{}'::jsonb,
    ADD COLUMN IF NOT EXISTS model_continuation_state TEXT NOT NULL DEFAULT 'NOT_STARTED',
    ADD COLUMN IF NOT EXISTS action_dispatch_state TEXT,
    ADD COLUMN IF NOT EXISTS action_status TEXT,
    ADD COLUMN IF NOT EXISTS verification_status TEXT;

ALTER TABLE anima_agent_continuations
    ADD COLUMN IF NOT EXISTS terminal_episode_id UUID REFERENCES anima_agent_episodes(episode_id);

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conname = 'anima_agent_continuations_status_check'
    ) THEN
        ALTER TABLE anima_agent_continuations
        ADD CONSTRAINT anima_agent_continuations_status_check CHECK (
        continuation_status IN (
            'PENDING_RESOLUTION', 'CLAIMED', 'ACTION_AUTHORIZING', 'ACTION_EXECUTING',
            'ACTION_RESOLVED', 'MODEL_RESUMING',
            'WAITING_CONFIRMATION', 'WAITING_STRONGER_AUTH', 'COMPLETED', 'REJECTED',
            'EXPIRED', 'DENIED_AFTER_RECHECK', 'VERIFICATION_FAILED', 'UNKNOWN_RESULT',
            'RECOVERY_REQUIRED', 'FAILED'
        )
        );
    END IF;
END $$;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conname = 'anima_agent_continuations_catalogue_check'
    ) THEN
        ALTER TABLE anima_agent_continuations
        ADD CONSTRAINT anima_agent_continuations_catalogue_check CHECK (
            jsonb_typeof(tool_catalogue) = 'array'
        );
    END IF;
END $$;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conname = 'anima_agent_continuations_runtime_check'
    ) THEN
        ALTER TABLE anima_agent_continuations
        ADD CONSTRAINT anima_agent_continuations_runtime_check CHECK (
            jsonb_typeof(runtime_identity) = 'object'
        );
    END IF;
END $$;

ALTER TABLE anima_agent_episodes
    ADD COLUMN IF NOT EXISTS active_runtime_ms BIGINT NOT NULL DEFAULT 0;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conname = 'anima_agent_episodes_active_runtime_check'
    ) THEN
        ALTER TABLE anima_agent_episodes
        ADD CONSTRAINT anima_agent_episodes_active_runtime_check CHECK (active_runtime_ms >= 0);
    END IF;
END $$;

CREATE INDEX IF NOT EXISTS anima_agent_continuations_claim_idx
    ON anima_agent_continuations (continuation_status, claim_expires_at);
