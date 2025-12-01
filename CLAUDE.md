# Agent Profiler - Architecture Guidelines

---

## CRITICAL: NO HARDCODING

**This is the #1 rule of this system. Read this before making ANY changes.**

### What NO HARDCODING means:

- **NO hardcoded routing rules** - Don't add `if "segment" in query: use_agent("segmentation")`
- **NO hardcoded examples in prompts** - Don't add `"when_not_to_use": ["segment by company"]`
- **NO keyword-based routing** - Don't match specific phrases to specific agents
- **NO predetermined agent sequences** - Don't assume "always do SQL then Segmentation"
- **NO agent cross-awareness** - Agents don't know about or route to other agents

### Why NO HARDCODING:

- We don't know the user's data source until runtime
- We don't know the user's query until runtime
- Both can change at any time
- Hardcoded rules break when data/queries don't match assumptions
- LLMs are better at understanding intent than keyword matching

### What to do instead:

- **Agents describe CAPABILITIES** (what they can do), not specific queries they handle
- **Orchestrator's LLM decides** routing based on agent descriptions + user query
- **Trust the LLMs** to interpret intent and make routing decisions
- **Keep agent descriptions general** - describe the type of work, not specific phrases

### Examples of violations:

```python
# WRONG - hardcoded phrase
"when_not_to_use": ["segment by company", "group by city"]

# RIGHT - describes capability
"when_not_to_use": ["Simple GROUP BY operations (use SQL Analytics)"]
```

```python
# WRONG - agent routing to another agent
return {"for_sql_analytics": True, "field": "company"}

# RIGHT - agent does its job, returns results
return {"clusters": [...], "insights": [...]}
```

```python
# WRONG - hardcoded routing in orchestrator
if "segment" in query.lower():
    use_agent("segmentation")

# RIGHT - LLM decides based on agent descriptions
plan = await llm.create_plan(query, agent_descriptions)
```

---

## Architecture Overview

### Orchestrator Agent

The orchestrator is the "brain" that:

1. Receives the user query
2. Reads all agent self-descriptions (via `get_agent_info()`)
3. Understands the data/schema context
4. **Dynamically creates an execution plan** using its LLM
5. Routes to agents in whatever order is needed
6. Can use the **same agent multiple times** if needed
7. Can use **any combination** of agents
8. Aggregates results and responds to user

The orchestrator's LLM has **full autonomy** - no constraints on which agents, what order, or how many times.

### Individual Agents

Each agent:

- Has a **specialized LLM with a specialized prompt** for its specific task
- Does **ONE thing well** - no capability duplication across agents
- Is **NOT responsible for solving the user query** - only for doing its specific job
- Describes itself via `get_agent_info()` for orchestrator discovery
- Does **NOT know about other agents** or try to route to them
- Returns results to orchestrator, which decides next steps

---

## Agent Capabilities (No Overlap)

### SQL Analytics
- Quantitative operations: COUNT, SUM, AVG, MIN, MAX
- GROUP BY operations (including on text fields)
- Exact value filtering and ranges
- Date/time operations
- Sorting and ranking
- **Does NOT do**: LIKE/ILIKE, regex, fuzzy matching, semantic understanding

### Semantic Search
- Text search using embeddings
- Fuzzy/approximate matching
- Semantic similarity
- Finding related content by meaning
- **Does NOT do**: Numerical calculations, aggregations

### Segmentation
- AI-driven clustering (understands MEANING, not just values)
- Creating personas and archetypes
- Finding behaviorally similar clients
- Intelligent categorization based on multiple attributes
- **Provides insight**: e.g., groups Amazon/Wayfair/Target as "retail" vs Intel/AMD as "semiconductor"
- **Does NOT do**: Simple GROUP BY counts (that's SQL Analytics)

### Data Discovery
- Exploring and profiling data structure
- Computing statistics and thresholds
- Understanding data quality and completeness
- Providing semantic context

### Pattern Recognition
- Identifying trends over time
- Detecting anomalies and outliers
- Finding correlations between variables

### Recommendation
- Generating actionable recommendations
- Prioritizing tasks or outreach
- Suggesting next best actions

---

## SQL vs AI: Same Field, Different Insights

| Operation | Agent | Result |
|-----------|-------|--------|
| COUNT by company | SQL Analytics | `{Acme: 10, Intel: 5, Amazon: 8}` |
| Cluster by company type | Segmentation | `{retail: [Amazon, Target], tech: [Intel, AMD]}` |

- **SQL**: Treats text as literal strings, exact operations
- **AI**: Understands meaning, provides semantic insight

---

## Schema Context

Text field guidance for SQL Analytics:
- **CAN do**: GROUP BY, COUNT, exact match (=)
- **Should NOT do**: LIKE, ILIKE, regex (use Semantic Search)

---

## Git & GitHub

### Repository
- **GitHub**: `git@github.com:1enterprisesight/agent-profiler.git`
- **Branch**: main

### Commit and Push
```bash
git add .
git commit -m "feat/fix/docs: Description of changes"
git push origin main
```

### Commit Message Format
- `feat:` New feature
- `fix:` Bug fix
- `docs:` Documentation
- `refactor:` Code refactoring

---

## Deployment Process

### Project Info
- **GCP Project**: client-profiler-473903
- **Region**: us-central1
- **Database**: Cloud SQL PostgreSQL (client-profiler-db)

### Service URLs
- **Backend API**: https://agent-profiler-api-1041758516609.us-central1.run.app
- **Frontend**: https://agent-profiler-frontend-1041758516609.us-central1.run.app

### Version Tagging
Use semantic versioning: `v1.10.9`, `v1.10.10`, etc.
- Check current version: `gcloud container images list-tags gcr.io/client-profiler-473903/agent-profiler-api --limit=1`

---

### Backend Deployment

From project root (`agent-profiler/`):

```bash
# 1. Build and tag image (from backend directory)
cd backend
docker build -t gcr.io/client-profiler-473903/agent-profiler-api:v1.X.X .

# 2. Push to Container Registry
docker push gcr.io/client-profiler-473903/agent-profiler-api:v1.X.X

# 3. Deploy to Cloud Run
gcloud run deploy agent-profiler-api \
  --image gcr.io/client-profiler-473903/agent-profiler-api:v1.X.X \
  --region us-central1 \
  --platform managed \
  --project client-profiler-473903
```

**OR use Cloud Build (recommended):**
```bash
cd backend
gcloud builds submit --tag gcr.io/client-profiler-473903/agent-profiler-api:v1.X.X --project=client-profiler-473903

gcloud run deploy agent-profiler-api \
  --image gcr.io/client-profiler-473903/agent-profiler-api:v1.X.X \
  --region us-central1 \
  --platform managed \
  --project client-profiler-473903
```

---

### Frontend Deployment

From project root (`agent-profiler/`):

```bash
# 1. Build the frontend (creates dist/)
cd frontend
npm run build

# 2. Build Docker image (uses dist/ and nginx.conf)
gcloud builds submit --tag gcr.io/client-profiler-473903/agent-profiler-frontend:v1.X.X --project=client-profiler-473903

# 3. Deploy to Cloud Run
gcloud run deploy agent-profiler-frontend \
  --image gcr.io/client-profiler-473903/agent-profiler-frontend:v1.X.X \
  --region us-central1 \
  --platform managed \
  --allow-unauthenticated \
  --port 8080 \
  --project client-profiler-473903
```

---

### Environment Variables (Backend Cloud Run)
- `GOOGLE_CLOUD_PROJECT`: client-profiler-473903
- `VERTEX_AI_LOCATION`: us-central1
- `DATABASE_URL`: postgresql+asyncpg://postgres:reedmichael@/agent_profiler?host=/cloudsql/client-profiler-473903:us-central1:client-profiler-db
- `GCS_BUCKET_NAME`: client-profiler-473903-agent-profiler-data
- `APP_ENV`: production

### Cloud SQL Connection
Backend uses Cloud SQL proxy via: `--add-cloudsql-instances=client-profiler-473903:us-central1:client-profiler-db`

---

## Making Changes

### REQUIRED: Ask for Approval Before ANY Code Changes

**Do NOT make changes without explicit user approval.**

Before modifying any code:
1. **Explain** what you want to change and why
2. **Show** the specific changes you plan to make
3. **Wait** for user approval before implementing
4. **Discuss** if the user has concerns or alternative approaches

This prevents reactive changes that violate the architecture.

### Pre-Change Checklist

Before proposing any agent modification, verify:

1. **Does this add hardcoding?** → Don't propose it
2. **Does this add specific examples/phrases?** → Don't propose it
3. **Does this duplicate capabilities from another agent?** → Don't propose it
4. **Does this make the agent aware of other agents?** → Don't propose it
5. **Does this change the agent's core purpose?** → Discuss first

### Research Before Proposing

Before suggesting fixes:
1. **Understand the current state** - Read the relevant code
2. **Understand the history** - Check git history for context
3. **Understand the root cause** - Don't fix symptoms, fix causes
4. **Verify against architecture** - Does the fix align with NO HARDCODING principle?

### Testing

**We do NOT test locally. All testing is done on Cloud Run.**

- Deploy to Cloud Run first
- Test against the deployed service
- Use the live URLs to verify functionality
- Check Cloud Run logs for errors: `gcloud run logs read agent-profiler-api --project=client-profiler-473903`

---

## Version History

Track significant architecture changes here:

- **v1.10.x**: Phase E - Dynamic schema discovery
- **Initial**: Phase D - Self-describing agents with LLM-driven routing
