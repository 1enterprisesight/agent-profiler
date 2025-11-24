# Agent Profiler

**Multi-Agent AI System for Client Data Analysis with Complete Transparency**

## Overview

Agent Profiler is a standalone, agent-driven platform for analyzing wealth management client data. The system uses multiple specialized AI agents powered by Google Gemini (Flash + Pro hybrid) to provide intelligent analysis, pattern recognition, segmentation, and actionable recommendations.

### Key Features

- **Multi-Agent Intelligence**: 7 specialized AI agents working collaboratively
- **Complete Transparency**: Real-time visibility into all agent operations, SQL queries, and LLM conversations
- **CRM Integration**: Connect to Salesforce, Wealthbox, Redtail, Junxure, and other wealth management CRMs
- **Dynamic Benchmarking**: Agent-driven, configurable benchmarks with no hard-coded logic
- **CSV Upload**: Ad-hoc data analysis from CSV files
- **JSONB-Heavy Database**: Flexible schema supporting unknown data structures
- **Google Workspace Auth**: Secure authentication for @enterprisesight.com users

## Architecture

### Technology Stack

**Backend**:
- Python 3.11 + FastAPI (async)
- PostgreSQL with JSONB (flexible schema)
- Google Vertex AI (Gemini Flash + Pro)
- SQLAlchemy (async ORM)
- Redis (caching only)

**Infrastructure**:
- Google Cloud Run (compute)
- Cloud SQL PostgreSQL (database)
- Cloud Storage (file uploads)
- Cloud Memorystore (Redis cache)
- Secret Manager (credentials)

**Authentication**:
- Google Workspace OAuth 2.0
- JWT tokens
- Domain-restricted (@enterprisesight.com)

### AI Agents

1. **Orchestrator Agent** (Gemini Flash) - Request routing and workflow coordination
2. **Data Ingestion Agent** (Gemini Flash) - CSV upload, CRM schema discovery, field mapping
3. **SQL Analytics Agent** (Gemini Flash) - Dynamic SQL query generation and execution
4. **Pattern Recognition Agent** (Gemini Pro) - Complex pattern analysis
5. **Segmentation Agent** (Gemini Flash) - Client grouping and classification
6. **Benchmark Agent** (Gemini Flash) - Dynamic benchmark evaluation
7. **Recommendation Agent** (Gemini Pro) - Strategic recommendations

## Project Structure

```
agent-profiler/
├── backend/
│   ├── app/
│   │   ├── __init__.py
│   │   ├── main.py              # FastAPI application
│   │   ├── config.py            # Configuration management
│   │   ├── database.py          # Database connection
│   │   ├── models.py            # SQLAlchemy models
│   │   ├── auth.py              # Authentication & authorization
│   │   ├── agents/              # AI agent implementations
│   │   │   ├── __init__.py
│   │   │   ├── orchestrator.py
│   │   │   ├── data_ingestion.py
│   │   │   ├── sql_analytics.py
│   │   │   ├── pattern_recognition.py
│   │   │   ├── segmentation.py
│   │   │   ├── benchmark.py
│   │   │   └── recommendation.py
│   │   ├── routers/             # FastAPI route handlers
│   │   │   ├── __init__.py
│   │   │   ├── conversations.py
│   │   │   ├── crm_connections.py
│   │   │   ├── data_upload.py
│   │   │   ├── agents.py
│   │   │   ├── analysis.py
│   │   │   └── benchmarks.py
│   │   ├── services/            # Business logic
│   │   │   ├── __init__.py
│   │   │   ├── gemini.py
│   │   │   ├── crm/
│   │   │   │   ├── salesforce.py
│   │   │   │   ├── wealthbox.py
│   │   │   │   ├── redtail.py
│   │   │   │   └── junxure.py
│   │   │   ├── storage.py
│   │   │   └── cache.py
│   │   └── utils/               # Utilities
│   │       ├── __init__.py
│   │       ├── logging.py
│   │       └── validators.py
│   ├── requirements.txt
│   ├── Dockerfile
│   └── .env.example
├── frontend/                     # To be implemented
│   └── README.md
├── database/
│   ├── schema.sql               # Database schema
│   └── README.md
├── cloudbuild.yaml              # CI/CD configuration
└── README.md                    # This file
```

## Getting Started

### Prerequisites

1. **Google Cloud Project**: `client-profiler-473903`
2. **Cloud SQL Instance**: `client-profiler-db` (PostgreSQL 17)
3. **Service Account**: `claude-automation@ent-sight-dev-esml01.iam.gserviceaccount.com`
4. **Google Workspace Account**: @enterprisesight.com domain

### Database Setup

1. Create the database:
```bash
gcloud sql connect client-profiler-db --user=postgres
# Password: reedmichael

CREATE DATABASE agent_profiler;
\c agent_profiler
\i database/schema.sql
```

2. Verify setup:
```bash
\dt  # List tables
\di  # List indexes
```

### Local Development

1. **Install dependencies**:
```bash
cd backend
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt
```

2. **Set up environment**:
```bash
cp .env.example .env
# Edit .env with your configuration
```

3. **Start Cloud SQL Proxy** (for local development):
```bash
./cloud-sql-proxy client-profiler-473903:us-central1:client-profiler-db
```

4. **Run the application**:
```bash
cd backend
uvicorn app.main:app --reload --port 8080
```

5. **Access the API**:
- API: http://localhost:8080
- Docs: http://localhost:8080/docs
- Health: http://localhost:8080/health

### Deploy to Cloud Run

#### Manual Deployment

```bash
# Build and push Docker image
cd backend
gcloud builds submit --tag gcr.io/client-profiler-473903/agent-profiler-api

# Deploy to Cloud Run
gcloud run deploy agent-profiler-api \
  --image gcr.io/client-profiler-473903/agent-profiler-api \
  --region us-central1 \
  --platform managed \
  --allow-unauthenticated \
  --memory 4Gi \
  --cpu 2 \
  --timeout 600 \
  --add-cloudsql-instances client-profiler-473903:us-central1:client-profiler-db \
  --service-account claude-automation@ent-sight-dev-esml01.iam.gserviceaccount.com
```

#### Automatic Deployment (Cloud Build)

1. **Connect GitHub repository** to Cloud Build

2. **Create trigger**:
```bash
gcloud builds triggers create github \
  --name=agent-profiler-deploy \
  --repo-name=YOUR_REPO_NAME \
  --repo-owner=YOUR_GITHUB_ORG \
  --branch-pattern=^main$ \
  --build-config=cloudbuild.yaml
```

3. **Push to main branch** to trigger deployment

### Create Cloud Storage Bucket

```bash
gcloud storage buckets create gs://client-profiler-473903-agent-profiler-data \
  --location=us-central1 \
  --storage-class=STANDARD
```

### Set Up Secrets

```bash
# JWT Secret
echo -n "your-secret-key" | gcloud secrets create jwt-secret-key --data-file=-

# Google OAuth Client Secret
echo -n "your-client-secret" | gcloud secrets create google-oauth-client-secret --data-file=-

# Grant service account access
gcloud secrets add-iam-policy-binding jwt-secret-key \
  --member="serviceAccount:claude-automation@ent-sight-dev-esml01.iam.gserviceaccount.com" \
  --role="roles/secretmanager.secretAccessor"
```

## API Documentation

### Authentication

All API endpoints (except `/health` and `/`) require authentication.

**Get access token**:
```bash
POST /api/v1/auth/google
{
  "token": "google-oauth-id-token"
}
```

**Use token in requests**:
```bash
curl -H "Authorization: Bearer YOUR_JWT_TOKEN" \
  https://agent-profiler-api-HASH.run.app/api/v1/status
```

### Key Endpoints

- `GET /health` - Health check
- `GET /api/v1/status` - System status (authenticated)
- `POST /api/v1/auth/google` - Authenticate with Google
- `GET /api/v1/auth/me` - Get current user info
- More endpoints to be added as features are implemented

## Database Schema

The database uses a **JSONB-heavy design** for maximum flexibility:

### Key Tables

- **`crm_connections`**: CRM system connections (Salesforce, Wealthbox, etc.)
- **`crm_schemas`**: Cached CRM schemas (full JSONB)
- **`field_mappings`**: Intelligent field mappings (JSONB transformations)
- **`clients`**: Unified client data (minimal columns + JSONB)
- **`agent_activity_log`**: Real-time agent operations
- **`agent_llm_conversations`**: All LLM prompts/responses
- **`sql_query_log`**: Executed SQL queries and results
- **`data_transformation_log`**: Data transformation tracking
- **`benchmark_definitions`**: Dynamic benchmark configurations
- **`analysis_results`**: Cached analysis results

See `database/README.md` for detailed schema documentation.

## Development Roadmap

### Phase 1: Foundation ✅ (Current)
- [x] Database schema design
- [x] FastAPI application structure
- [x] Google Workspace OAuth
- [x] Docker configuration
- [x] Cloud Run deployment setup

### Phase 2: Data Ingestion (In Progress)
- [ ] CSV upload functionality
- [ ] Data Ingestion Agent
- [ ] Salesforce connector
- [ ] CRM connection management UI

### Phase 3: Agent Framework
- [ ] Orchestrator Agent
- [ ] SQL Analytics Agent
- [ ] Agent communication protocol
- [ ] Comprehensive logging system

### Phase 4: Intelligence Agents
- [ ] Pattern Recognition Agent
- [ ] Segmentation Agent
- [ ] Benchmark Agent
- [ ] Recommendation Agent

### Phase 5: Frontend & UI
- [ ] Conversational chat interface
- [ ] Agent activity dashboard
- [ ] SQL query viewer
- [ ] Data transformation visualizer
- [ ] Benchmark configuration UI

### Phase 6: Additional CRMs
- [ ] Wealthbox connector
- [ ] Redtail connector
- [ ] Junxure connector

### Phase 7: Production Optimization
- [ ] Redis caching layer
- [ ] LLM prompt optimization
- [ ] Monitoring and alerting
- [ ] Performance testing
- [ ] Security audit

## Configuration

### Environment Variables

See `.env.example` for all available configuration options.

Key variables:
- `GOOGLE_CLOUD_PROJECT`: GCP project ID
- `DATABASE_URL`: PostgreSQL connection string
- `GEMINI_FLASH_MODEL`: Gemini Flash model name
- `GEMINI_PRO_MODEL`: Gemini Pro model name
- `ALLOWED_DOMAIN`: Allowed email domain (enterprisesight.com)

### Feature Flags

Enable/disable features via environment variables:
- `ENABLE_CSV_UPLOAD`
- `ENABLE_SALESFORCE_CONNECTOR`
- `ENABLE_WEALTHBOX_CONNECTOR`
- `ENABLE_REDTAIL_CONNECTOR`
- `ENABLE_JUNXURE_CONNECTOR`

## Monitoring & Observability

### Cloud Logging

All logs are sent to Cloud Logging with structured JSON format.

**View logs**:
```bash
gcloud run services logs read agent-profiler-api \
  --region=us-central1 \
  --limit=50
```

### Metrics

Cloud Run provides automatic metrics:
- Request count
- Request latency
- Error rate
- Instance count
- CPU/Memory usage

**View metrics** in Cloud Console:
https://console.cloud.google.com/run/detail/us-central1/agent-profiler-api

### Database Observability

The system logs all operations for transparency:
- Agent activity: `agent_activity_log`
- LLM conversations: `agent_llm_conversations`
- SQL queries: `sql_query_log`
- Data transformations: `data_transformation_log`

## Security

- **Authentication**: Google Workspace OAuth 2.0 only
- **Domain Restriction**: Only @enterprisesight.com users allowed
- **Credentials**: Stored in Secret Manager (never in code/database)
- **Encryption**: Data encrypted at rest (Cloud SQL) and in transit (HTTPS)
- **IAM**: Minimal service account permissions
- **Audit Logging**: Complete audit trail in `audit_log` table

## Contributing

This is an internal Enterprise Sight project. Development follows:

1. Create feature branch from `main`
2. Implement changes with tests
3. Submit pull request
4. Code review required
5. Merge to `main` triggers auto-deployment

## Support

For questions or issues:
- Technical: Contact development team
- Access: Contact IT for Google Workspace provisioning
- Infrastructure: Contact cloud operations team

## License

Proprietary - Enterprise Sight Internal Use Only

---

**Last Updated**: 2025-11-23
**Version**: 1.0.0
**Status**: Phase 1 Complete
