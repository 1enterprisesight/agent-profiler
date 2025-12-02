# Agent Profiler - Master Project Document & Baseline Reset Plan

**Created:** 2025-12-01
**Purpose:** Complete documentation for project reset to clean baseline
**This is the single source of truth for this project.**

---

## CRITICAL PRINCIPLES

### 1. NO CHANGES WITHOUT APPROVAL
- **NEVER** make code changes without explicit user approval
- **ALWAYS** explain what will change and why BEFORE doing it
- **ALWAYS** show the specific changes planned
- **WAIT** for user approval before implementing

### 2. NO NEW TECH OR ARCHITECTURE CHANGES
- Do NOT add libraries, frameworks, or dependencies without approval
- Do NOT change database schema without approval
- Do NOT change deployment architecture without approval
- Stick to existing technology stack

### 3. STEP-BY-STEP EXECUTION
- Execute ONE step at a time
- Show what was done after each step
- Ask for approval before proceeding to next step
- If something fails, STOP and report

### 4. NO HARDCODING (For Future Agent Work)
- NO keyword-based routing
- NO agent-to-agent awareness
- LLM decides routing, not code
- Agents describe capabilities, not specific queries

---

## PROJECT INFORMATION

### GCP Project
| Property | Value |
|----------|-------|
| Project Name | Client-profiler-01 |
| Project ID | `client-profiler-473903` |
| Project Number | `1041758516609` |
| Organization ID | `248577987929` |
| Primary Region | `us-central1` |
| Primary Zone | `us-central1-a` |

### GitHub Repository
| Property | Value |
|----------|-------|
| Repository | `git@github.com:1enterprisesight/agent-profiler.git` |
| HTTPS URL | `https://github.com/1enterprisesight/agent-profiler` |
| Branch | `main` |
| GitHub Org | `1enterprisesight` |

---

## SERVICE ACCOUNTS

### 1. Primary Automation Service Account
```
Email: claude-automation@ent-sight-dev-esml01.iam.gserviceaccount.com
Roles: Owner + comprehensive permissions
```

### 2. Cloud Run Service Account (Used by deployed services)
```
Email: 1041758516609-compute@developer.gserviceaccount.com
Roles: Cloud SQL Client, Logs Writer, Monitoring Metric Writer
```

### 3. Cloud Build Service Account
```
Email: 1041758516609@cloudbuild.gserviceaccount.com
Roles: Cloud Build Builder, Cloud SQL Client, IAM Service Account User, Cloud Run Admin
```

---

## CREDENTIALS & SECRETS

### Database (Cloud SQL PostgreSQL)
```
Instance Name: client-profiler-db
Database Engine: PostgreSQL 17
Database Name: agent_profiler
Region: us-central1-a
Public IP: 136.114.255.63

Username: postgres
Password: reedmichael
```

### Database Connection Strings
```bash
# Cloud Run (Unix Socket via Cloud SQL Proxy)
postgresql+asyncpg://postgres:reedmichael@/agent_profiler?host=/cloudsql/client-profiler-473903:us-central1:client-profiler-db

# Local Development (via Cloud SQL Proxy on localhost)
postgresql+asyncpg://postgres:reedmichael@127.0.0.1:5432/agent_profiler
```

### Google OAuth (Workspace Authentication)
```
Client ID: 1041758516609-p7k2rjrc8efpob1dvqir2d4v62l0hl2b.apps.googleusercontent.com
Allowed Domain: enterprisesight.com
JWT Algorithm: HS256
JWT Expiration: 24 hours
```

### Google Cloud Storage
```
Bucket Name: client-profiler-473903-agent-profiler-data
```

### Gemini Models
```
Flash Model: gemini-2.0-flash
Pro Model: gemini-2.5-pro
```

---

## SERVICE URLs

### Production (Cloud Run)
```
Backend API: https://agent-profiler-api-1041758516609.us-central1.run.app
Frontend: https://agent-profiler-frontend-1041758516609.us-central1.run.app
```

### Container Registry
```
Backend Image: gcr.io/client-profiler-473903/agent-profiler-api
Frontend Image: gcr.io/client-profiler-473903/agent-profiler-frontend
```

---

## TECHNOLOGY STACK

### Backend
- **Framework:** FastAPI 0.109.0
- **Runtime:** Python 3.11, Uvicorn
- **Database:** SQLAlchemy[asyncio] 2.0.25, AsyncPG 0.29.0
- **AI:** Google Vertex AI (Gemini models via aiplatform)
- **Storage:** Google Cloud Storage
- **Auth:** PyJWT, python-jose, Google OAuth2

### Frontend
- **Framework:** React 18 + TypeScript
- **Build:** Vite
- **Styling:** Tailwind CSS
- **Auth:** @react-oauth/google
- **HTTP:** Axios

### Infrastructure
- **Container:** Docker
- **CI/CD:** Google Cloud Build
- **Hosting:** Google Cloud Run
- **Database:** Google Cloud SQL (PostgreSQL 17)
- **Storage:** Google Cloud Storage

---

## DEPLOYMENT COMMANDS

### Backend Deployment
```bash
# From agent-profiler/ directory

# 1. Commit changes first
git add .
git commit -m "feat|fix|docs: Description"
git push origin main

# 2. Build image with Cloud Build
cd backend
gcloud builds submit \
  --tag gcr.io/client-profiler-473903/agent-profiler-api:vX.X.X \
  --project=client-profiler-473903

# 3. Deploy to Cloud Run
gcloud run deploy agent-profiler-api \
  --image gcr.io/client-profiler-473903/agent-profiler-api:vX.X.X \
  --region us-central1 \
  --platform managed \
  --project client-profiler-473903 \
  --add-cloudsql-instances=client-profiler-473903:us-central1:client-profiler-db \
  --set-env-vars="GOOGLE_CLOUD_PROJECT=client-profiler-473903,VERTEX_AI_LOCATION=us-central1,APP_ENV=production,DATABASE_URL=postgresql+asyncpg://postgres:reedmichael@/agent_profiler?host=/cloudsql/client-profiler-473903:us-central1:client-profiler-db,GCS_BUCKET_NAME=client-profiler-473903-agent-profiler-data"
```

### Frontend Deployment
```bash
# From agent-profiler/ directory

# 1. Build frontend
cd frontend
npm run build

# 2. Build image with Cloud Build
gcloud builds submit \
  --tag gcr.io/client-profiler-473903/agent-profiler-frontend:vX.X.X \
  --project=client-profiler-473903

# 3. Deploy to Cloud Run
gcloud run deploy agent-profiler-frontend \
  --image gcr.io/client-profiler-473903/agent-profiler-frontend:vX.X.X \
  --region us-central1 \
  --platform managed \
  --allow-unauthenticated \
  --port 8080 \
  --project client-profiler-473903
```

### Verify Deployment
```bash
# Check backend logs
gcloud run logs read agent-profiler-api --project=client-profiler-473903 --limit=50

# Check frontend logs
gcloud run logs read agent-profiler-frontend --project=client-profiler-473903 --limit=50

# List current image versions
gcloud container images list-tags gcr.io/client-profiler-473903/agent-profiler-api --limit=5
gcloud container images list-tags gcr.io/client-profiler-473903/agent-profiler-frontend --limit=5
```

---

## PROJECT STRUCTURE (After Baseline Reset)

```
agent-profiler/
├── backend/
│   ├── app/
│   │   ├── __init__.py
│   │   ├── main.py              # FastAPI entry (KEEP - needs cleanup)
│   │   ├── config.py            # Configuration (KEEP)
│   │   ├── auth.py              # Authentication logic (KEEP)
│   │   ├── database.py          # DB connection (KEEP)
│   │   ├── models.py            # SQLAlchemy models (KEEP)
│   │   ├── routers/
│   │   │   ├── __init__.py      # (KEEP)
│   │   │   ├── auth.py          # OAuth endpoint (KEEP)
│   │   │   └── uploads.py       # Upload endpoint (KEEP)
│   │   └── agents/
│   │       ├── __init__.py      # (KEEP - needs cleanup)
│   │       ├── base.py          # BaseAgent class (KEEP)
│   │       ├── data_ingestion.py # CSV processing (KEEP)
│   │       └── data_discovery.py # Metadata computation (KEEP)
│   ├── Dockerfile               # (KEEP)
│   └── requirements.txt         # (KEEP)
├── frontend/
│   ├── src/
│   │   ├── main.tsx             # React entry (KEEP)
│   │   ├── App.tsx              # Main app (KEEP - needs cleanup)
│   │   ├── contexts/
│   │   │   └── AuthContext.tsx  # Auth state (KEEP)
│   │   ├── services/
│   │   │   └── api.ts           # API client (KEEP - needs cleanup)
│   │   ├── types/
│   │   │   └── index.ts         # TypeScript types (KEEP - needs cleanup)
│   │   └── components/
│   │       ├── LoginButton.tsx      # (KEEP)
│   │       ├── DataUpload.tsx       # (KEEP)
│   │       ├── DataSourceList.tsx   # (KEEP)
│   │       ├── DataSourceBadge.tsx  # (KEEP)
│   │       └── ErrorBoundary.tsx    # (KEEP)
│   ├── Dockerfile               # (KEEP)
│   ├── package.json             # (KEEP)
│   └── .env                     # (KEEP)
├── database/
│   └── schema.sql               # (KEEP - no changes)
├── cloudbuild.yaml              # (KEEP)
└── PROJECT-MASTER.md            # (THIS DOCUMENT)
```

---

## FILES TO DELETE

### Backend Agents (7 files)
```
backend/app/agents/orchestrator.py       # Multi-agent coordinator - broken
backend/app/agents/sql_analytics.py      # SQL agent - agent chaining issues
backend/app/agents/semantic_search.py    # Semantic search agent
backend/app/agents/segmentation.py       # Segmentation - hardcoded phrases
backend/app/agents/pattern_recognition.py # Pattern recognition agent
backend/app/agents/recommendation.py     # Recommendation agent
backend/app/agents/benchmark.py          # Benchmarking agent
```

### Backend Routers (2 files)
```
backend/app/routers/conversations.py     # 600+ lines chat handling
backend/app/routers/streaming.py         # WebSocket streaming
```

### Frontend Components (5 files)
```
frontend/src/components/ChatInterface.tsx    # 400+ lines chat UI
frontend/src/components/AgentNetwork.tsx     # 400+ lines agent visualization
frontend/src/components/WorkflowDisplay.tsx  # 400+ lines workflow UI
frontend/src/components/CrossSourceView.tsx  # Data analysis visualization
frontend/src/components/DataSourceManager.tsx # Advanced data management
```

### Old Documentation to Remove (4 files)
```
/Users/michaelreed/es-code/profile-app/NEW-APP-QUICKSTART.md           # Outdated
/Users/michaelreed/es-code/profile-app/CRM_INTEGRATION_GUIDE.md        # Not needed for baseline
/Users/michaelreed/es-code/profile-app/agent-profiler/CLAUDE.md        # Replace with PROJECT-MASTER.md
/Users/michaelreed/es-code/profile-app/agent-profiler/database/README.md # Redundant, info in PROJECT-MASTER.md
```

---

## EXECUTION PLAN (Step-by-Step with Approval)

### PHASE 1: Create Master Document
**Step 1.1:** Create `/Users/michaelreed/es-code/profile-app/agent-profiler/PROJECT-MASTER.md`
- Copy this plan content to project directory
- This becomes the single source of truth
- **APPROVAL REQUIRED** before proceeding

### PHASE 2: Clean Up Old Documentation
**Step 2.1:** Delete old .md files (after backup review)
- `/Users/michaelreed/es-code/profile-app/NEW-APP-QUICKSTART.md`
- `/Users/michaelreed/es-code/profile-app/CRM_INTEGRATION_GUIDE.md`
- `/Users/michaelreed/es-code/profile-app/agent-profiler/CLAUDE.md`
- **APPROVAL REQUIRED** before proceeding

### PHASE 3: Delete Backend Agent Files
**Step 3.1:** Delete agent files one by one
```bash
rm backend/app/agents/orchestrator.py
# Show result, ask for approval to continue

rm backend/app/agents/sql_analytics.py
# Show result, ask for approval to continue

rm backend/app/agents/semantic_search.py
# Show result, ask for approval to continue

rm backend/app/agents/segmentation.py
# Show result, ask for approval to continue

rm backend/app/agents/pattern_recognition.py
# Show result, ask for approval to continue

rm backend/app/agents/recommendation.py
# Show result, ask for approval to continue

rm backend/app/agents/benchmark.py
# Show result, ask for approval to continue
```
- **APPROVAL REQUIRED** before each deletion

### PHASE 4: Delete Backend Router Files
**Step 4.1:** Delete router files
```bash
rm backend/app/routers/conversations.py
# Show result, ask for approval

rm backend/app/routers/streaming.py
# Show result, ask for approval
```
- **APPROVAL REQUIRED** before each deletion

### PHASE 5: Update Backend main.py
**Step 5.1:** Show current imports and router includes
**Step 5.2:** Show proposed changes (remove deleted imports/routers)
**Step 5.3:** Apply changes after approval
- **APPROVAL REQUIRED** before making changes

### PHASE 6: Update Backend agents/__init__.py
**Step 6.1:** Show current exports
**Step 6.2:** Show proposed changes (keep only BaseAgent, DataIngestionAgent, DataDiscoveryAgent)
**Step 6.3:** Apply changes after approval
- **APPROVAL REQUIRED** before making changes

### PHASE 7: Delete Frontend Component Files
**Step 7.1:** Delete component files one by one
```bash
rm frontend/src/components/ChatInterface.tsx
rm frontend/src/components/AgentNetwork.tsx
rm frontend/src/components/WorkflowDisplay.tsx
rm frontend/src/components/CrossSourceView.tsx
rm frontend/src/components/DataSourceManager.tsx
```
- **APPROVAL REQUIRED** before each deletion

### PHASE 8: Update Frontend App.tsx
**Step 8.1:** Show current imports and component usage
**Step 8.2:** Show proposed simplified layout (Login + Upload + DataSourceList only)
**Step 8.3:** Apply changes after approval
- **APPROVAL REQUIRED** before making changes

### PHASE 9: Update Frontend api.ts
**Step 9.1:** Show current API methods
**Step 9.2:** Show proposed changes (remove chat/conversation methods)
**Step 9.3:** Apply changes after approval
- **APPROVAL REQUIRED** before making changes

### PHASE 10: Update Frontend types/index.ts
**Step 10.1:** Show current types
**Step 10.2:** Show proposed changes (remove chat/conversation types)
**Step 10.3:** Apply changes after approval
- **APPROVAL REQUIRED** before making changes

### PHASE 11: Verify Build
**Step 11.1:** Test backend starts (Python)
```bash
cd backend && python -c "from app.main import app; print('Backend OK')"
```
**Step 11.2:** Test frontend builds
```bash
cd frontend && npm run build
```
- **APPROVAL REQUIRED** before proceeding to commit

### PHASE 12: Commit Clean Baseline
**Step 12.1:** Show git status
**Step 12.2:** Show proposed commit message
**Step 12.3:** Commit after approval
```bash
git add .
git commit -m "refactor: Strip to clean baseline - auth, upload, data processing only

Removed:
- All conversation/chat agents (orchestrator, sql_analytics, segmentation, etc.)
- All chat routers (conversations, streaming)
- All chat UI components (ChatInterface, AgentNetwork, WorkflowDisplay, etc.)

Kept:
- Google Workspace authentication
- CSV upload and GCS storage
- Data ingestion with LLM schema analysis
- Data source listing and metadata

This establishes a clean baseline for rebuilding the multi-agent system.

🤖 Generated with [Claude Code](https://claude.com/claude-code)

Co-Authored-By: Claude <noreply@anthropic.com>"
```
- **APPROVAL REQUIRED** before commit

### PHASE 13: Push to GitHub
```bash
git push origin main
```
- **APPROVAL REQUIRED** before push

### PHASE 14: Deploy Backend to Cloud Run
**Step 14.1:** Build image
```bash
cd backend
gcloud builds submit --tag gcr.io/client-profiler-473903/agent-profiler-api:v2.0.0-baseline --project=client-profiler-473903
```
**Step 14.2:** Deploy
```bash
gcloud run deploy agent-profiler-api \
  --image gcr.io/client-profiler-473903/agent-profiler-api:v2.0.0-baseline \
  --region us-central1 \
  --platform managed \
  --project client-profiler-473903
```
- **APPROVAL REQUIRED** before deployment

### PHASE 15: Deploy Frontend to Cloud Run
**Step 15.1:** Build frontend
```bash
cd frontend && npm run build
```
**Step 15.2:** Build image
```bash
gcloud builds submit --tag gcr.io/client-profiler-473903/agent-profiler-frontend:v2.0.0-baseline --project=client-profiler-473903
```
**Step 15.3:** Deploy
```bash
gcloud run deploy agent-profiler-frontend \
  --image gcr.io/client-profiler-473903/agent-profiler-frontend:v2.0.0-baseline \
  --region us-central1 \
  --platform managed \
  --allow-unauthenticated \
  --port 8080 \
  --project client-profiler-473903
```
- **APPROVAL REQUIRED** before deployment

### PHASE 16: Verify Deployment
**Step 16.1:** Test login at frontend URL
**Step 16.2:** Test CSV upload
**Step 16.3:** Verify data sources display
**Step 16.4:** Check logs for errors
```bash
gcloud run logs read agent-profiler-api --project=client-profiler-473903 --limit=20
```

---

## BASELINE FUNCTIONALITY (After Reset)

After completing all phases, the application will have ONLY:

1. **Google Workspace Login**
   - OAuth sign-in with @enterprisesight.com domain
   - JWT token-based session management
   - User isolation (user_id on all queries)

2. **CSV Upload**
   - File validation and upload to GCS
   - LLM-driven schema analysis (Gemini Flash)
   - Automatic field mapping to standard/custom fields
   - DataSource record creation
   - Client records creation

3. **Data Source Display**
   - List of uploaded data sources
   - Record counts
   - Upload timestamps
   - Delete functionality

4. **Metadata Computation**
   - Field completeness percentages
   - Source aggregation
   - Stored for future use

**NOT INCLUDED (Will be rebuilt in future session):**
- Chat/conversation interface
- Multi-agent orchestration
- SQL analytics
- Segmentation
- Benchmarking
- Any agent visualization

---

## NEXT SESSION SCOPE

After baseline is established, a separate session will:

1. Design proper multi-agent architecture from scratch
2. Build LLM-driven routing (NO hardcoding)
3. Implement clean orchestrator
4. Add agents one at a time with proper testing
5. Build new chat UI

This is OUT OF SCOPE for the current baseline reset session.
