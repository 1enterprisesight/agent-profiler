-- ============================================================================
-- Migration v1.3.0: Align Schema with Application Requirements
-- Date: 2025-11-25
-- Purpose: Add missing columns for user tracking and data source relationships
-- ============================================================================

-- ============================================================================
-- STEP 1: Add user_id tracking to agent_activity_log
-- ============================================================================

ALTER TABLE agent_activity_log
ADD COLUMN IF NOT EXISTS user_id VARCHAR(255);

CREATE INDEX IF NOT EXISTS idx_agent_activity_user
ON agent_activity_log(user_id);

COMMENT ON COLUMN agent_activity_log.user_id IS 'Google Workspace user email tracking agent activity';

-- ============================================================================
-- STEP 2: Add user_id and data_source_id to clients table
-- ============================================================================

-- Add user_id for ownership tracking
ALTER TABLE clients
ADD COLUMN IF NOT EXISTS user_id VARCHAR(255);

-- Add data_source_id for cascade delete of uploaded data
ALTER TABLE clients
ADD COLUMN IF NOT EXISTS data_source_id UUID;

-- Create indexes
CREATE INDEX IF NOT EXISTS idx_clients_user
ON clients(user_id);

CREATE INDEX IF NOT EXISTS idx_clients_data_source
ON clients(data_source_id);

-- Add foreign key constraint (uploaded_files is the actual table name)
-- Note: Only add if the constraint doesn't exist
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.table_constraints
        WHERE constraint_name = 'fk_clients_data_source'
        AND table_name = 'clients'
    ) THEN
        ALTER TABLE clients
        ADD CONSTRAINT fk_clients_data_source
        FOREIGN KEY (data_source_id)
        REFERENCES uploaded_files(id)
        ON DELETE CASCADE;
    END IF;
END $$;

COMMENT ON COLUMN clients.user_id IS 'Google Workspace user email who owns this client record';
COMMENT ON COLUMN clients.data_source_id IS 'Reference to uploaded_files for cascade delete';

-- ============================================================================
-- STEP 3: Add user_id tracking to agent_llm_conversations
-- ============================================================================

ALTER TABLE agent_llm_conversations
ADD COLUMN IF NOT EXISTS user_id VARCHAR(255);

CREATE INDEX IF NOT EXISTS idx_agent_llm_user
ON agent_llm_conversations(user_id);

COMMENT ON COLUMN agent_llm_conversations.user_id IS 'Google Workspace user email for LLM usage tracking';

-- ============================================================================
-- STEP 4: Create user_sessions table for session tracking
-- ============================================================================

CREATE TABLE IF NOT EXISTS user_sessions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id VARCHAR(255) NOT NULL,
    email VARCHAR(255) NOT NULL,
    name VARCHAR(255),
    picture_url TEXT,
    access_token_hash VARCHAR(255),
    refresh_token_encrypted TEXT,
    expires_at TIMESTAMP NOT NULL,
    created_at TIMESTAMP DEFAULT NOW(),
    last_activity_at TIMESTAMP DEFAULT NOW(),
    is_active BOOLEAN DEFAULT TRUE,
    metadata JSONB
);

CREATE INDEX IF NOT EXISTS idx_user_sessions_user
ON user_sessions(user_id);

CREATE INDEX IF NOT EXISTS idx_user_sessions_email
ON user_sessions(email);

CREATE INDEX IF NOT EXISTS idx_user_sessions_active
ON user_sessions(is_active, expires_at);

COMMENT ON TABLE user_sessions IS 'User session tracking for Google Workspace OAuth';

-- ============================================================================
-- STEP 5: Verify migration completed
-- ============================================================================

-- Check that all columns exist
DO $$
DECLARE
    missing_cols TEXT := '';
BEGIN
    -- Check agent_activity_log.user_id
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'agent_activity_log' AND column_name = 'user_id'
    ) THEN
        missing_cols := missing_cols || 'agent_activity_log.user_id, ';
    END IF;

    -- Check clients.user_id
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'clients' AND column_name = 'user_id'
    ) THEN
        missing_cols := missing_cols || 'clients.user_id, ';
    END IF;

    -- Check clients.data_source_id
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'clients' AND column_name = 'data_source_id'
    ) THEN
        missing_cols := missing_cols || 'clients.data_source_id, ';
    END IF;

    -- Check agent_llm_conversations.user_id
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'agent_llm_conversations' AND column_name = 'user_id'
    ) THEN
        missing_cols := missing_cols || 'agent_llm_conversations.user_id, ';
    END IF;

    -- Check user_sessions table
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.tables
        WHERE table_name = 'user_sessions'
    ) THEN
        missing_cols := missing_cols || 'user_sessions table, ';
    END IF;

    IF missing_cols != '' THEN
        RAISE EXCEPTION 'Migration incomplete. Missing: %', missing_cols;
    ELSE
        RAISE NOTICE 'Migration v1.3.0 completed successfully!';
    END IF;
END $$;
