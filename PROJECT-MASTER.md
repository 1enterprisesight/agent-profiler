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

## CURRENT BASELINE STATE

**Baseline Tag:** `v2.0.0-baseline`
**Date Reset:** 2025-12-02

### Files in baseline:
```
backend/app/agents/
├── __init__.py
├── base.py              # BaseAgent class
├── data_ingestion.py    # CSV processing (NEEDS REWRITE)
├── data_discovery.py    # Metadata computation (NEEDS REWRITE)
└── schema_utils.py      # Schema discovery utilities
```

### Baseline Functionality:
- Google Workspace authentication
- CSV upload to GCS
- Basic data ingestion
- Data source listing

---

## REWRITE SESSION LOG

### Session Started: 2025-12-02

**Approach:** Architecture-first design. Agree on design, then implement, then test.

**Order of work:**
1. data_ingestion agent
2. data_discovery agent
3. (future agents TBD)

---

### LOG ENTRIES

| # | Date | Action | Status | Notes |
|---|------|--------|--------|-------|
| 1 | 2025-12-02 | Reverted to v2.0.0-baseline | DONE | Clean slate established |
| 2 | 2025-12-02 | Cleaned up PROJECT-MASTER.md | DONE | Removed old execution plan |
| 3 | | data_ingestion architecture design | PENDING | |
| 4 | | data_ingestion implementation | PENDING | |
| 5 | | data_ingestion testing | PENDING | |
| 6 | | data_discovery architecture design | PENDING | |
| 7 | | data_discovery implementation | PENDING | |
| 8 | | data_discovery testing | PENDING | |

---

## ARCHITECTURE PRINCIPLES (Reference)

From CLAUDE.md (preserved for reference):

### NO HARDCODING - THE #1 RULE

- **NO hardcoded routing rules** - Don't add `if "segment" in query: use_agent("segmentation")`
- **NO hardcoded examples in prompts** - Don't add specific phrases agents handle
- **NO keyword-based routing** - Don't match specific phrases to specific agents
- **NO predetermined agent sequences** - Don't assume specific agent order
- **NO agent cross-awareness** - Agents don't know about or route to other agents

### What to do instead:

- **Agents describe CAPABILITIES** (what they can do), not specific queries they handle
- **Orchestrator's LLM decides** routing based on agent descriptions + user query
- **Trust the LLMs** to interpret intent and make routing decisions
- **Keep agent descriptions general** - describe the type of work, not specific phrases

### Agent Responsibilities:

- Each agent does **ONE thing well**
- Agent is **NOT responsible for solving the user query** - only for doing its specific job
- Agent **does NOT know about other agents** or try to route to them
- Agent returns results to orchestrator, which decides next steps
