# Agent Profiler Database

## Overview
This database uses a **JSONB-heavy design** for maximum flexibility with unknown data structures. The schema supports dynamic, agent-driven analysis without hard-coded business logic.

## Database Information
- **Database Name**: `agent_profiler`
- **Instance**: `client-profiler-db` (existing Cloud SQL instance)
- **Engine**: PostgreSQL 17
- **Key Feature**: Extensive use of JSONB for flexible data storage

## Setup Instructions

### 1. Create Database
```bash
# Connect to Cloud SQL instance
gcloud sql connect client-profiler-db --user=postgres
# Password: reedmichael

# In psql prompt:
CREATE DATABASE agent_profiler;
\c agent_profiler
```

### 2. Run Schema
```bash
# From local machine with schema.sql
psql -h 136.114.255.63 -U postgres -d agent_profiler -f schema.sql

# Or via Cloud SQL Proxy
./cloud-sql-proxy client-profiler-473903:us-central1:client-profiler-db &
psql -h 127.0.0.1 -U postgres -d agent_profiler -f schema.sql
```

### 3. Verify Setup
```sql
-- Check all tables created
\dt

-- Verify indexes
\di

-- Check JSONB columns
SELECT table_name, column_name, data_type
FROM information_schema.columns
WHERE table_schema = 'public' AND data_type = 'jsonb';
```

## Schema Design Philosophy

### JSONB-Heavy Approach
The schema extensively uses JSONB columns for flexibility:

- **`clients.core_data`**: Standard but variable fields (phone, address, dates)
- **`clients.custom_data`**: All custom/unknown CRM fields
- **`clients.computed_metrics`**: Dynamic scores, segments, benchmarks
- **`crm_connections.config`**: Full CRM configuration
- **`crm_schemas.schema_data`**: Complete discovered CRM schemas
- **`field_mappings.mapping_data`**: Intelligent field mapping rules
- **`benchmark_definitions.definition`**: Agent-generated benchmark logic

### Why JSONB?
1. **Flexibility**: Handle unknown CRM schemas without schema migrations
2. **Agent-Driven**: Agents can work with any data structure
3. **Performance**: GIN indexes on JSONB for fast queries
4. **PostgreSQL Native**: Full SQL support for JSONB querying

## Key Tables

### CRM Integration
- **`crm_connections`**: User CRM connections (Salesforce, Wealthbox, etc.)
- **`crm_schemas`**: Cached schemas from connected CRMs
- **`field_mappings`**: Intelligent mappings to unified schema
- **`sync_jobs`**: Data sync operation tracking

### Client Data
- **`clients`**: Unified client records (minimal structure + JSONB)
- **`uploaded_files`**: CSV upload tracking

### Agent System
- **`agent_activity_log`**: Real-time agent operations
- **`agent_llm_conversations`**: All LLM prompts/responses
- **`sql_query_log`**: All SQL queries executed
- **`data_transformation_log`**: Data transformation tracking

### Analysis & Benchmarks
- **`benchmark_definitions`**: Dynamic benchmark configurations
- **`analysis_results`**: Cached analysis results

### User Interface
- **`conversation_sessions`**: User chat sessions
- **`conversation_messages`**: Chat messages

### Compliance
- **`audit_log`**: Complete audit trail

## Example Queries

### Find all clients from Salesforce
```sql
SELECT id, client_name, contact_email, custom_data
FROM clients
WHERE source_type = 'salesforce';
```

### Get client with custom field lookup
```sql
SELECT client_name,
       custom_data->>'engagement_score' as engagement_score,
       custom_data->>'risk_level' as risk_level
FROM clients
WHERE custom_data->>'account_type' = 'high_value';
```

### View recent agent activity
```sql
SELECT agent_name, activity_type, status,
       started_at, duration_ms
FROM agent_activity_log
WHERE session_id = 'some-session-id'
ORDER BY started_at DESC;
```

### Find all LLM conversations for a session
```sql
SELECT agent_name, model_used,
       LEFT(prompt, 100) as prompt_preview,
       token_usage, latency_ms
FROM agent_llm_conversations
WHERE session_id = 'some-session-id'
ORDER BY created_at;
```

### View SQL queries executed in analysis
```sql
SELECT agent_name,
       query_text,
       execution_time_ms,
       result_summary
FROM sql_query_log
WHERE session_id = 'some-session-id'
ORDER BY created_at;
```

### Get benchmark definitions for a user
```sql
SELECT benchmark_name, benchmark_type,
       definition, criteria, is_active
FROM benchmark_definitions
WHERE user_id = 'user@enterprisesight.com'
AND is_active = true;
```

## Connection String Format

### For Cloud Run (Unix Socket)
```
postgresql+asyncpg://postgres:reedmichael@/agent_profiler?host=/cloudsql/client-profiler-473903:us-central1:client-profiler-db
```

### For Local Development (Cloud SQL Proxy)
```
postgresql+asyncpg://postgres:reedmichael@127.0.0.1:5432/agent_profiler
```

## Indexes

All JSONB columns have GIN indexes for fast querying:
- `idx_clients_core_data` on `clients.core_data`
- `idx_clients_custom_data` on `clients.custom_data`

Time-series indexes for observability:
- `idx_agent_activity_time` on `agent_activity_log.started_at`
- `idx_sql_query_time` on `sql_query_log.created_at`
- `idx_audit_time` on `audit_log.created_at`

## Maintenance

### Vacuum JSONB Tables Regularly
```sql
VACUUM ANALYZE clients;
VACUUM ANALYZE agent_activity_log;
VACUUM ANALYZE agent_llm_conversations;
```

### Monitor JSONB Index Usage
```sql
SELECT schemaname, tablename, indexname, idx_scan
FROM pg_stat_user_indexes
WHERE indexname LIKE '%jsonb%'
ORDER BY idx_scan DESC;
```

### Archive Old Logs
```sql
-- Archive agent activity older than 90 days
DELETE FROM agent_activity_log
WHERE started_at < NOW() - INTERVAL '90 days';

-- Archive SQL query logs older than 30 days
DELETE FROM sql_query_log
WHERE created_at < NOW() - INTERVAL '30 days';
```

## Security Notes

1. **Credentials**: Never store API keys or passwords in database
   - Use Secret Manager references only
2. **PII**: Be mindful of PII in JSONB fields
3. **Audit**: All user actions logged in `audit_log`
4. **Encryption**: Data encrypted at rest by Cloud SQL

## Migration Strategy

Since we're using JSONB extensively, schema changes are minimal:
- Add new tables as needed
- No need to alter JSONB structures
- Agents adapt to new fields automatically

## Next Steps

1. Create database: `CREATE DATABASE agent_profiler;`
2. Run schema: `psql -d agent_profiler -f schema.sql`
3. Verify setup: Check tables and indexes
4. Update backend connection strings
5. Test connectivity from Cloud Run
