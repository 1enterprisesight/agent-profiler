-- Agent Profiler Database Schema
-- Database: agent_profiler
-- Design: JSONB-heavy for maximum flexibility with unknown data structures

-- ============================================================================
-- CRM CONNECTIONS & INTEGRATION
-- ============================================================================

-- CRM connection configurations (client credentials stored in Secret Manager)
CREATE TABLE crm_connections (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id VARCHAR(255) NOT NULL,  -- Google Workspace user email
    crm_type VARCHAR(50) NOT NULL,  -- 'salesforce', 'wealthbox', 'redtail', 'junxure'
    connection_name VARCHAR(255),    -- User-friendly name
    config JSONB NOT NULL,           -- Full connection config (instance_url, etc.)
    credentials_secret_name VARCHAR(255),  -- Reference to Secret Manager secret
    status VARCHAR(50) DEFAULT 'active',   -- 'active', 'disconnected', 'error'
    last_sync_at TIMESTAMP,
    last_sync_status VARCHAR(50),
    error_message TEXT,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_crm_connections_user ON crm_connections(user_id);
CREATE INDEX idx_crm_connections_type ON crm_connections(crm_type);

-- CRM schema cache (discovered schemas from CRM systems)
CREATE TABLE crm_schemas (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    connection_id UUID REFERENCES crm_connections(id) ON DELETE CASCADE,
    schema_data JSONB NOT NULL,      -- Complete CRM schema (objects, fields, relationships)
    schema_version VARCHAR(50),      -- Track schema changes over time
    discovered_at TIMESTAMP DEFAULT NOW(),
    UNIQUE(connection_id)
);

CREATE INDEX idx_crm_schemas_connection ON crm_schemas(connection_id);

-- Field mappings (intelligent mappings from CRM to unified schema)
CREATE TABLE field_mappings (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    connection_id UUID REFERENCES crm_connections(id) ON DELETE CASCADE,
    mapping_data JSONB NOT NULL,     -- Complete mapping configuration
    mapping_version INTEGER DEFAULT 1,
    confidence_score DECIMAL(3,2),   -- Gemini's confidence in mapping
    user_approved BOOLEAN DEFAULT FALSE,
    user_adjustments JSONB,          -- User overrides to AI mappings
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_field_mappings_connection ON field_mappings(connection_id);

-- ============================================================================
-- CLIENT DATA (Unified, Flexible)
-- ============================================================================

-- Unified client/contact records from all sources
CREATE TABLE clients (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    source_type VARCHAR(50) NOT NULL,     -- 'csv', 'salesforce', 'wealthbox', etc.
    source_id VARCHAR(255),                -- Original ID in source system
    connection_id UUID REFERENCES crm_connections(id) ON DELETE SET NULL,

    -- Minimal structured fields (most common across systems)
    client_name VARCHAR(500),
    contact_email VARCHAR(255),
    company_name VARCHAR(500),

    -- Everything else in flexible JSONB
    core_data JSONB,                -- Standard fields (phone, address, etc.)
    custom_data JSONB,              -- Custom/unknown fields from CRM
    computed_metrics JSONB,         -- Calculated scores, benchmarks, segments

    -- Metadata
    synced_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_clients_source ON clients(source_type, source_id);
CREATE INDEX idx_clients_connection ON clients(connection_id);
CREATE INDEX idx_clients_email ON clients(contact_email);
CREATE INDEX idx_clients_core_data ON clients USING GIN (core_data);
CREATE INDEX idx_clients_custom_data ON clients USING GIN (custom_data);

-- ============================================================================
-- DATA SYNC & JOBS
-- ============================================================================

-- Data synchronization jobs tracking
CREATE TABLE sync_jobs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    connection_id UUID REFERENCES crm_connections(id) ON DELETE CASCADE,
    sync_type VARCHAR(50),           -- 'initial', 'incremental', 'real-time', 'csv_upload'
    status VARCHAR(50),              -- 'pending', 'running', 'completed', 'failed'
    started_at TIMESTAMP DEFAULT NOW(),
    completed_at TIMESTAMP,
    records_processed INTEGER DEFAULT 0,
    records_succeeded INTEGER DEFAULT 0,
    records_failed INTEGER DEFAULT 0,
    error_details JSONB,
    processing_log JSONB             -- Detailed log of sync process
);

CREATE INDEX idx_sync_jobs_connection ON sync_jobs(connection_id);
CREATE INDEX idx_sync_jobs_status ON sync_jobs(status);

-- ============================================================================
-- AGENT SYSTEM & OBSERVABILITY
-- ============================================================================

-- Agent activity log (real-time tracking of agent operations)
CREATE TABLE agent_activity_log (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id UUID NOT NULL,
    agent_name VARCHAR(100) NOT NULL,    -- 'orchestrator', 'sql_analytics', etc.
    activity_type VARCHAR(100),          -- 'started', 'processing', 'completed', 'error'
    status VARCHAR(50),                  -- 'active', 'completed', 'failed'
    input_data JSONB,                    -- What the agent received
    output_data JSONB,                   -- What the agent produced
    metadata JSONB,                      -- Additional context
    started_at TIMESTAMP DEFAULT NOW(),
    completed_at TIMESTAMP,
    duration_ms INTEGER
);

CREATE INDEX idx_agent_activity_session ON agent_activity_log(session_id);
CREATE INDEX idx_agent_activity_agent ON agent_activity_log(agent_name);
CREATE INDEX idx_agent_activity_time ON agent_activity_log(started_at DESC);

-- Agent LLM conversations (prompts and responses for transparency)
CREATE TABLE agent_llm_conversations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id UUID NOT NULL,
    agent_name VARCHAR(100) NOT NULL,
    model_used VARCHAR(100),             -- 'gemini-2.0-flash-exp', 'gemini-1.5-pro'
    prompt TEXT NOT NULL,
    system_instruction TEXT,
    response TEXT,
    token_usage JSONB,                   -- Input/output token counts
    latency_ms INTEGER,
    error TEXT,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_agent_llm_session ON agent_llm_conversations(session_id);
CREATE INDEX idx_agent_llm_agent ON agent_llm_conversations(agent_name);

-- SQL query execution log (transparency for all SQL operations)
CREATE TABLE sql_query_log (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id UUID NOT NULL,
    agent_name VARCHAR(100),             -- Usually 'sql_analytics'
    query_text TEXT NOT NULL,
    query_params JSONB,
    result_summary JSONB,                -- Summary of results (row count, columns, etc.)
    execution_time_ms INTEGER,
    error TEXT,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_sql_query_session ON sql_query_log(session_id);
CREATE INDEX idx_sql_query_time ON sql_query_log(created_at DESC);

-- Data transformation log (field mappings, data cleaning, etc.)
CREATE TABLE data_transformation_log (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id UUID,
    sync_job_id UUID REFERENCES sync_jobs(id) ON DELETE SET NULL,
    transformation_type VARCHAR(100),    -- 'field_mapping', 'data_cleaning', 'validation'
    source_data JSONB,
    transformed_data JSONB,
    transformation_rules JSONB,
    status VARCHAR(50),
    error_details JSONB,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_transformation_session ON data_transformation_log(session_id);
CREATE INDEX idx_transformation_job ON data_transformation_log(sync_job_id);

-- ============================================================================
-- BENCHMARK & ANALYSIS
-- ============================================================================

-- Dynamic benchmark definitions (agent-driven, configurable)
CREATE TABLE benchmark_definitions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id VARCHAR(255) NOT NULL,
    benchmark_name VARCHAR(255) NOT NULL,
    benchmark_type VARCHAR(100),         -- 'completeness', 'risk', 'compliance', 'engagement', 'custom'
    definition JSONB NOT NULL,           -- Agent-generated benchmark logic
    criteria JSONB,                      -- Evaluation criteria
    thresholds JSONB,                    -- Score thresholds
    applies_to_sources JSONB,            -- Which data sources this applies to
    created_by_agent VARCHAR(100),
    user_approved BOOLEAN DEFAULT FALSE,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_benchmark_user ON benchmark_definitions(user_id);
CREATE INDEX idx_benchmark_type ON benchmark_definitions(benchmark_type);

-- Analysis results (cached results from agent analysis)
CREATE TABLE analysis_results (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id UUID NOT NULL,
    user_id VARCHAR(255) NOT NULL,
    analysis_type VARCHAR(100),          -- 'segmentation', 'pattern', 'benchmark', 'recommendation'
    input_parameters JSONB,
    results JSONB NOT NULL,              -- Complete analysis results
    confidence_score DECIMAL(3,2),
    performed_by_agents JSONB,           -- Which agents were involved
    execution_time_ms INTEGER,
    created_at TIMESTAMP DEFAULT NOW(),
    expires_at TIMESTAMP                 -- Optional cache expiration
);

CREATE INDEX idx_analysis_session ON analysis_results(session_id);
CREATE INDEX idx_analysis_user ON analysis_results(user_id);
CREATE INDEX idx_analysis_type ON analysis_results(analysis_type);
CREATE INDEX idx_analysis_expires ON analysis_results(expires_at);

-- ============================================================================
-- USER SESSIONS & CONVERSATIONS
-- ============================================================================

-- User conversation sessions
CREATE TABLE conversation_sessions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id VARCHAR(255) NOT NULL,
    title VARCHAR(500),
    context JSONB,                       -- Conversation context and state
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT NOW(),
    last_activity_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_conversation_user ON conversation_sessions(user_id);
CREATE INDEX idx_conversation_active ON conversation_sessions(is_active, last_activity_at DESC);

-- Conversation messages (user and assistant messages)
CREATE TABLE conversation_messages (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id UUID REFERENCES conversation_sessions(id) ON DELETE CASCADE,
    role VARCHAR(50) NOT NULL,           -- 'user', 'assistant'
    content TEXT NOT NULL,
    metadata JSONB,                      -- Additional message data
    agent_activities UUID[],             -- References to agent_activity_log entries
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_conversation_messages_session ON conversation_messages(session_id, created_at);

-- ============================================================================
-- FILE UPLOADS & DATASETS
-- ============================================================================

-- Uploaded files tracking
CREATE TABLE uploaded_files (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id VARCHAR(255) NOT NULL,
    file_name VARCHAR(500) NOT NULL,
    file_type VARCHAR(100),              -- 'csv', 'xlsx', etc.
    gcs_path VARCHAR(1000) NOT NULL,     -- Cloud Storage path
    file_size_bytes BIGINT,
    status VARCHAR(50),                  -- 'uploaded', 'processing', 'completed', 'error'
    metadata JSONB,                      -- File metadata, schema, etc.
    processing_results JSONB,            -- Results of processing
    records_imported INTEGER,
    error_details JSONB,
    uploaded_at TIMESTAMP DEFAULT NOW(),
    processed_at TIMESTAMP
);

CREATE INDEX idx_uploaded_files_user ON uploaded_files(user_id);
CREATE INDEX idx_uploaded_files_status ON uploaded_files(status);

-- ============================================================================
-- AUDIT & COMPLIANCE
-- ============================================================================

-- Complete audit trail
CREATE TABLE audit_log (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id VARCHAR(255),
    action VARCHAR(255) NOT NULL,
    resource_type VARCHAR(100),
    resource_id UUID,
    details JSONB,
    ip_address VARCHAR(100),
    user_agent TEXT,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_audit_user ON audit_log(user_id);
CREATE INDEX idx_audit_action ON audit_log(action);
CREATE INDEX idx_audit_time ON audit_log(created_at DESC);

-- ============================================================================
-- FUNCTIONS & TRIGGERS
-- ============================================================================

-- Updated timestamp trigger function
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Apply updated_at trigger to relevant tables
CREATE TRIGGER update_crm_connections_updated_at BEFORE UPDATE ON crm_connections
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_field_mappings_updated_at BEFORE UPDATE ON field_mappings
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_clients_updated_at BEFORE UPDATE ON clients
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_benchmark_definitions_updated_at BEFORE UPDATE ON benchmark_definitions
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- ============================================================================
-- INITIAL DATA / SETUP
-- ============================================================================

-- Example benchmark definition template (to be customized by agents)
INSERT INTO benchmark_definitions (
    user_id,
    benchmark_name,
    benchmark_type,
    definition,
    criteria,
    is_active
) VALUES (
    'system',
    'Data Completeness Template',
    'completeness',
    '{"description": "Measures the completeness of client data based on required fields", "evaluation_method": "agent_driven"}'::jsonb,
    '{"required_fields": [], "optional_fields": [], "scoring": "percentage"}'::jsonb,
    false  -- Template, not active
);

-- ============================================================================
-- COMMENTS
-- ============================================================================

COMMENT ON TABLE crm_connections IS 'CRM system connections configured by users';
COMMENT ON TABLE crm_schemas IS 'Cached schemas discovered from CRM systems';
COMMENT ON TABLE field_mappings IS 'Intelligent field mappings from CRM to unified schema';
COMMENT ON TABLE clients IS 'Unified client data from all sources with JSONB flexibility';
COMMENT ON TABLE sync_jobs IS 'Tracking for data synchronization operations';
COMMENT ON TABLE agent_activity_log IS 'Real-time log of all agent activities for transparency';
COMMENT ON TABLE agent_llm_conversations IS 'Complete LLM prompt/response history for observability';
COMMENT ON TABLE sql_query_log IS 'All SQL queries executed by agents with results';
COMMENT ON TABLE data_transformation_log IS 'Log of all data transformations and mappings';
COMMENT ON TABLE benchmark_definitions IS 'Dynamic benchmark definitions created/configured by agents';
COMMENT ON TABLE analysis_results IS 'Cached results from agent analyses';
COMMENT ON TABLE conversation_sessions IS 'User conversation sessions with agents';
COMMENT ON TABLE conversation_messages IS 'Individual messages in conversations';
COMMENT ON TABLE uploaded_files IS 'CSV and other file uploads tracking';
COMMENT ON TABLE audit_log IS 'Complete audit trail for compliance';
