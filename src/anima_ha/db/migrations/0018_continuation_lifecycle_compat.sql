-- H5V-R1: complete the repeat-safe continuation lifecycle shape for databases
-- that applied the first lifecycle migration before its final column set.
ALTER TABLE anima_agent_continuations
    ADD COLUMN IF NOT EXISTS claimed_at TIMESTAMPTZ,
    ADD COLUMN IF NOT EXISTS terminal_episode_id UUID REFERENCES anima_agent_episodes(episode_id);

DO $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conname = 'anima_agent_continuations_status_check'
    ) THEN
        ALTER TABLE anima_agent_continuations
            DROP CONSTRAINT anima_agent_continuations_status_check;
    END IF;
    ALTER TABLE anima_agent_continuations
        ADD CONSTRAINT anima_agent_continuations_status_check CHECK (
            continuation_status IN (
                'PENDING_RESOLUTION', 'CLAIMED', 'ACTION_AUTHORIZING', 'ACTION_EXECUTING',
                'ACTION_RESOLVED', 'MODEL_RESUMING', 'WAITING_CONFIRMATION',
                'WAITING_STRONGER_AUTH', 'COMPLETED', 'REJECTED', 'EXPIRED',
                'DENIED_AFTER_RECHECK', 'VERIFICATION_FAILED', 'UNKNOWN_RESULT',
                'RECOVERY_REQUIRED', 'FAILED'
            )
        );
END $$;
