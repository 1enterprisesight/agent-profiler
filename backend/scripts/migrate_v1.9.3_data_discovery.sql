-- Migration for Data Discovery Agent
-- Version: 1.9.3
-- Description: Add data_metadata table for storing computed statistics and thresholds

-- Create data_metadata table
CREATE TABLE IF NOT EXISTS data_metadata (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id VARCHAR(255) NOT NULL,

    -- Overall stats
    total_clients INTEGER DEFAULT 0,
    sources_summary JSONB,

    -- Field completeness (% of records with non-null values)
    field_completeness JSONB,

    -- Numeric field statistics
    numeric_stats JSONB,

    -- Date ranges
    date_ranges JSONB,

    -- Categorical field distributions
    categorical_distributions JSONB,

    -- Semantic context (AI-generated descriptions)
    data_description TEXT,
    field_descriptions JSONB,

    -- Thresholds (computed from data)
    computed_thresholds JSONB,

    -- Metadata
    last_computed_at TIMESTAMP DEFAULT NOW(),
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- Create index on user_id for quick lookup
CREATE INDEX IF NOT EXISTS idx_data_metadata_user_id ON data_metadata(user_id);

-- Create unique constraint on user_id (one metadata record per user)
CREATE UNIQUE INDEX IF NOT EXISTS idx_data_metadata_user_id_unique ON data_metadata(user_id);

-- Add comment
COMMENT ON TABLE data_metadata IS 'Stores computed statistics and thresholds about user data for DataDiscoveryAgent';
