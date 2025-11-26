# Agent Profiler App - Master Implementation Plan

> **IMPORTANT**: This document is the single source of truth for the Agent Profiler application. It tracks all fixes, features, and infrastructure. Update status markers as work progresses.
>
> **AFTER COMPACTION**: Read this file first to resume work.
>
> **TESTING**: No local testing - deploy directly to Cloud Run for testing.

---

## Quick Reference

| Item | Value |
|------|-------|
| **Repository** | `/Users/michaelreed/es-code/profile-app/agent-profiler` |
| **Backend URL** | https://agent-profiler-api-1041758516609.us-central1.run.app |
| **Frontend URL** | https://agent-profiler-frontend-1041758516609.us-central1.run.app |
| **Database** | Cloud SQL: `client-profiler-db` (PostgreSQL 17) |
| **GCS Bucket** | `client-profiler-473903-agent-profiler-data` |
| **Auth Domain** | `@enterprisesight.com` (Google Workspace) |
| **GCP Project** | `client-profiler-473903` |
| **Region** | `us-central1` |

---

## STATUS LEGEND
- ⬜ Not Started
- 🔄 In Progress
- ✅ Completed
- ❌ Blocked
- ⚠️ Needs Review

---

## CURRENT STATUS (2025-11-26)

**Phase 1: Critical Code Fixes** ✅ COMPLETED & DEPLOYED
- All schema/model/code mismatches fixed
- Migration script created and applied to Cloud SQL
- Backend deployed to Cloud Run (revision: agent-profiler-api-00027-9z4)
- Health check: PASSING
- Auth in production: ENFORCED

**Verified Working:**
- `/health` endpoint returns `{"status":"healthy","environment":"production"}`
- `/api/uploads/history` returns `{"detail":"Authentication required"}` (correct - auth enforced)

**Next Steps:**
1. ⬜ Frontend Google Sign-In button
2. ⬜ Session persistence implementation
3. ⬜ Token refresh implementation

---

# PART 1: CRITICAL FIXES ✅ COMPLETED

## CHOSEN STRATEGY: Update Schema + Fix Code

**Decision Made:** 2025-11-25
- Add missing columns (user_id, data_source_id) to database schema
- Fix code field names to match the models
- Keep useful new features

## 1.1 Schema/Model/Code Alignment ✅ COMPLETED

### Files Modified:
| File | Changes |
|------|---------|
| `backend/app/models.py` | Table names fixed, user_id added, UserSession model added |
| `backend/app/agents/base.py` | AgentActivityLog & AgentLLMConversation field names fixed |
| `backend/app/routers/conversations.py` | ConversationMessage field names fixed, get_db_session |
| `backend/app/agents/data_ingestion.py` | DataSource & Client field names fixed |
| `backend/app/auth.py` | Production security checks added |
| `database/schema.sql` | V1.3.0 additions for user tracking |
| `backend/scripts/migrate_v1.3.0.sql` | NEW - Database migration script |

---

# PART 2: AUTHENTICATION & USER SESSION TRACKING

## 2.1 Google Workspace OAuth ⬜

### Current Status:
- ✅ OAuth flow implemented
- ✅ Domain restriction to `@enterprisesight.com`
- ✅ Dev mode bypass secured (only works when APP_ENV=development)
- ⬜ Session persistence not implemented
- ⬜ Token refresh not implemented

### Required Environment Variables:
```bash
APP_ENV=production  # CRITICAL - must be 'production' in Cloud Run
GOOGLE_CLIENT_ID=<from-console>
GOOGLE_CLIENT_SECRET=<stored-in-secret-manager>
JWT_SECRET_KEY=<generate-secure-key>
ALLOWED_DOMAIN=enterprisesight.com
```

---

# PART 3: FEATURE STATUS

## 3.1 What Should Work After Deployment

| Feature | Status | Notes |
|---------|--------|-------|
| CSV Upload | ✅ Fixed | Field mismatches resolved |
| Chat/Conversations | ✅ Fixed | Field names corrected |
| Agent Logging | ✅ Fixed | All agents should log properly |
| SQL Analytics Agent | ✅ Complete | Query gen + execution |
| Segmentation Agent | ✅ Complete | All capabilities |
| Benchmark Agent | ✅ Complete | All evaluations |
| Recommendation Agent | ✅ Complete | All actions |

## 3.2 Partial/Incomplete

| Feature | Status | Notes |
|---------|--------|-------|
| Semantic Search | ⚠️ Partial | Text search works, embeddings placeholder |
| Pattern Recognition | ⚠️ Partial | Analysis works, time-series placeholder |
| CRM Connectors | ⬜ Stubbed | Salesforce/Wealthbox - Phase 3 |
| Frontend Auth | ⬜ Not Done | Google Sign-In button needed |

---

# PART 4: INFRASTRUCTURE PARAMETERS

## 4.1 Cloud Run - Backend

```yaml
Service: agent-profiler-api
Region: us-central1
CPU: 2
Memory: 4Gi
Min Instances: 1
Max Instances: 100
Concurrency: 80
Request Timeout: 300s

Environment:
  APP_ENV: production  # CRITICAL
  GOOGLE_CLOUD_PROJECT: client-profiler-473903
  VERTEX_AI_LOCATION: us-central1
  GCS_BUCKET_NAME: client-profiler-473903-agent-profiler-data
  GEMINI_FLASH_MODEL: gemini-2.0-flash-exp
  GEMINI_PRO_MODEL: gemini-1.5-pro

Cloud SQL: client-profiler-473903:us-central1:client-profiler-db
```

## 4.2 Cloud SQL

```yaml
Instance: client-profiler-db
Version: PostgreSQL 17
Database: agent_profiler
Region: us-central1-a
```

---

# PART 5: NEXT STEPS

## Step 1: Apply Database Migration ⬜
```bash
# Connect to Cloud SQL and run:
# backend/scripts/migrate_v1.3.0.sql
```

## Step 2: Deploy Backend ⬜
```bash
cd /Users/michaelreed/es-code/profile-app/agent-profiler
gcloud builds submit --config=cloudbuild.yaml
```

## Step 3: Test on Cloud Run ⬜
- Test health endpoint
- Test CSV upload
- Test chat endpoint
- Verify agent logging in database

---

# PART 6: DECISION LOG

| Date | Decision | Rationale |
|------|----------|-----------|
| 2025-11-25 | Update Schema + Fix Code | Keep useful features, add missing columns |
| 2025-11-25 | No local testing | Local env not configured, test on Cloud Run |
| 2025-11-25 | Models use schema table names | `conversation_sessions`, `uploaded_files` |

---

# APPENDIX: Key Field Mappings

## AgentActivityLog (FIXED)
- `session_id` (was conversation_id)
- `activity_type` (was action)
- `duration_ms` (was execution_time_ms)
- `user_id` (added)

## AgentLLMConversation (FIXED)
- `session_id` (was conversation_id)
- `model_used` (was model_name)
- `prompt` (was prompt_text)
- `response` (was response_text)
- `token_usage` JSONB (was tokens_used int)
- `user_id` (added)

## DataSource/uploaded_files (FIXED)
- `file_type` (was source_type)
- `gcs_path` (was file_path)
- `meta_data` (was metadata)
- `records_imported` (was records_ingested)

---

*Document Version: 1.1*
*Created: 2025-11-25*
*Last Updated: 2025-11-25*
