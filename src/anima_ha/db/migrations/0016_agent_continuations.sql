CREATE TABLE IF NOT EXISTS anima_agent_continuations (
    episode_id UUID NOT NULL REFERENCES anima_agent_episodes(episode_id),
    approval_id UUID NOT NULL UNIQUE REFERENCES anima_pending_approvals(approval_id),
    request_number INTEGER NOT NULL CHECK (request_number > 0),
    result JSONB NOT NULL,
    transcript_digest TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (episode_id, request_number),
    CHECK (jsonb_typeof(result) = 'object')
);

CREATE INDEX IF NOT EXISTS anima_agent_continuations_episode_idx
    ON anima_agent_continuations (episode_id, request_number);
