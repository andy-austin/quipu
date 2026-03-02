-- Create runs table for tracking past agent executions
CREATE TABLE IF NOT EXISTS runs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id TEXT NOT NULL,
    agent TEXT NOT NULL DEFAULT 'chat',
    status TEXT NOT NULL DEFAULT 'completed',
    conversation_id UUID REFERENCES conversations(id),
    input_params JSONB NOT NULL DEFAULT '{}'::jsonb,
    result JSONB,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_runs_user_id ON runs (user_id, created_at DESC);
