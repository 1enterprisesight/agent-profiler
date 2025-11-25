# Agent Profiler

Multi-Agent AI System for Client Data Analysis

## Current Status

**Backend**: v1.2.0 deployed to Cloud Run
**Frontend**: v1.2.1 deployed to Cloud Run
**Database**: PostgreSQL 17 on Cloud SQL (`agent_profiler`)

## Live Services

- **Backend API**: https://agent-profiler-api-*.run.app
- **Frontend**: https://agent-profiler-frontend-*.run.app
- **Database**: Cloud SQL `client-profiler-db`
- **Storage**: `gs://client-profiler-473903-agent-profiler-data`

## Architecture

### Backend (FastAPI + Python 3.11)
- 8 AI Agents (Orchestrator + 7 specialized)
- Google Gemini (Flash + Pro hybrid)
- PostgreSQL with JSONB (flexible schema)
- SQLAlchemy async ORM

### Frontend (React + TypeScript)
- Real-time agent network visualization
- Chat interface for multi-agent conversations
- Workflow execution display
- CSV data upload with drag-and-drop
- Data source management

### Infrastructure
- Google Cloud Run (serverless containers)
- Cloud SQL PostgreSQL 17
- Cloud Storage (file uploads)
- Vertex AI (Gemini models)

## Key Features

1. **CSV Upload**: Drag-and-drop client data upload
2. **Data Management**: View, manage, and delete uploaded datasets
3. **Multi-Agent System**: 8 specialized AI agents
4. **Complete Transparency**: All agent operations logged
5. **JSONB Schema**: Flexible data structure support

## Quick Reference

### Deploy Backend
```bash
# Build
gcloud builds submit --tag gcr.io/client-profiler-473903/agent-profiler-api:vX.X.X backend/

# Deploy
gcloud run deploy agent-profiler-api \
  --image gcr.io/client-profiler-473903/agent-profiler-api:vX.X.X \
  --region us-central1 \
  --set-env-vars "DATABASE_URL=postgresql+asyncpg://postgres:reedmichael@/agent_profiler?host=/cloudsql/client-profiler-473903:us-central1:client-profiler-db" \
  --add-cloudsql-instances client-profiler-473903:us-central1:client-profiler-db
```

### Deploy Frontend
```bash
# Build local assets first
cd frontend && npm run build

# Build Docker image
gcloud builds submit --tag gcr.io/client-profiler-473903/agent-profiler-frontend:vX.X.X frontend/

# Deploy
gcloud run deploy agent-profiler-frontend \
  --image gcr.io/client-profiler-473903/agent-profiler-frontend:vX.X.X \
  --region us-central1
```

### View Logs
```bash
# Backend logs
gcloud run services logs tail agent-profiler-api --region us-central1

# Frontend logs
gcloud run services logs tail agent-profiler-frontend --region us-central1
```

## Project Structure

```
agent-profiler/
├── backend/
│   ├── app/
│   │   ├── main.py           # FastAPI app
│   │   ├── models.py         # SQLAlchemy models
│   │   ├── auth.py           # Authentication
│   │   ├── agents/           # 8 AI agents
│   │   └── routers/          # API endpoints
│   ├── Dockerfile
│   └── requirements.txt
├── frontend/
│   ├── src/
│   │   ├── components/       # React components
│   │   ├── services/         # API clients
│   │   └── App.tsx
│   ├── Dockerfile
│   └── package.json
├── database/
│   ├── schema.sql
│   └── README.md             # Database docs
├── CHANGELOG.md              # Current work tracking
└── README.md                 # This file
```

## Database

**Connection**: Cloud SQL PostgreSQL 17
**Instance**: `client-profiler-db`
**Database**: `agent_profiler`
**User**: `postgres`

See `database/README.md` for schema details.

## Development

### Backend Local
```bash
cd backend
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8080
```

### Frontend Local
```bash
cd frontend
npm install
npm run dev
```

## API Endpoints

### Uploads
- `POST /api/uploads/csv` - Upload CSV file
- `GET /api/uploads/history` - Get upload history
- `DELETE /api/uploads/{id}` - Delete data source

### System
- `GET /health` - Health check
- `GET /api/status` - System status

## Authentication

**Development Mode**: Currently using dev mode bypass (`APP_ENV=development`)
**Production**: Will use Google Workspace OAuth for @enterprisesight.com

## Support

See `CHANGELOG.md` for latest changes and pending work.

---

**Last Updated**: 2025-11-25
**Backend**: v1.2.0 (deployed)
**Frontend**: v1.2.1 (deployed)
