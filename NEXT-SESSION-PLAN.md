# Next Session Plan - Fix Architecture Violations

**Created**: 2025-12-01
**Context**: Local changes exist that violate the NO HARDCODING architecture principle

---

## IMPORTANT: Read CLAUDE.md First

Before making ANY changes, read `/CLAUDE.md` which documents:
- NO HARDCODING principle
- Architecture guidelines
- Deployment process
- Approval requirements

---

## Current State

### Deployed (v1.10.9)
Commit `aac6ed8` is deployed to Cloud Run.

### Local Changes (NOT committed)
There are ~983 lines of uncommitted changes across 11 files.

---

## What Needs To Be Done

### Step 1: Revert Broken Changes

**segmentation.py** - REVERT COMPLETELY
```bash
git checkout HEAD -- backend/app/agents/segmentation.py
```
Issues:
- `get_agent_info()` has hardcoded phrases: "segment by company", "group by city"
- `_segment_clients()` no longer does AI clustering - returns field info instead
- Added `for_sql_analytics: True` - agent cross-awareness (violates architecture)

**sql_analytics.py** - REVERT the `previous_step_results` logic
```bash
git checkout HEAD -- backend/app/agents/sql_analytics.py
```
Issue:
- Added agent chaining logic that violates "agents don't know about each other"

### Step 2: Keep Good Changes (Cherry-pick)

**schema_utils.py** - KEEP the base columns addition
- Lines 44-59 add base columns (client_name, company_name, etc.)
- This is GOOD - SQL Analytics needs to know about these fields

**schema_utils.py** - FIX text field guidance
- Line 282 says "Text fields (DO NOT query with SQL)"
- Should say: "Text fields - SQL CAN do GROUP BY/COUNT/exact match, should NOT do LIKE/ILIKE (use Semantic Search)"

### Step 3: Review Other Changes

**orchestrator.py** - Review against architecture
- Has `_understand_query()` for query canonicalization
- Has conversation history handling
- Check if these follow NO HARDCODING principle
- Keep if LLM-driven, remove if hardcoded

**Other files** - Review and decide:
- pattern_recognition.py
- recommendation.py
- semantic_search.py
- routers/conversations.py
- routers/streaming.py
- frontend files

### Step 4: Deploy and Test

1. Commit approved changes
2. Build and deploy to Cloud Run:
```bash
cd backend
gcloud builds submit --tag gcr.io/client-profiler-473903/agent-profiler-api:v1.11.0 --project=client-profiler-473903

gcloud run deploy agent-profiler-api \
  --image gcr.io/client-profiler-473903/agent-profiler-api:v1.11.0 \
  --region us-central1 \
  --platform managed \
  --project client-profiler-473903
```

3. Test on Cloud Run (NOT locally):
   - URL: https://agent-profiler-api-1041758516609.us-central1.run.app
   - Check logs: `gcloud run logs read agent-profiler-api --project=client-profiler-473903`

---

## Key Architecture Reminders

1. **NO HARDCODING** - No specific phrases, no keyword routing
2. **Agents don't know about each other** - No cross-awareness, no chaining logic
3. **Orchestrator decides routing** - Based on agent self-descriptions
4. **Each agent does ONE thing** - No capability duplication
5. **Ask for approval** before making changes

---

## Files to Review

```
backend/app/agents/segmentation.py      ← REVERT
backend/app/agents/sql_analytics.py     ← REVERT chaining logic
backend/app/agents/schema_utils.py      ← KEEP base columns, FIX text guidance
backend/app/agents/orchestrator.py      ← REVIEW
backend/app/agents/pattern_recognition.py
backend/app/agents/recommendation.py
backend/app/agents/semantic_search.py
backend/app/routers/conversations.py
backend/app/routers/streaming.py
frontend/src/components/ChatInterface.tsx
frontend/src/services/api.ts
```
