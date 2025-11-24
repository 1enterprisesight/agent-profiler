# Agent Profiler - Deployment Guide

Step-by-step guide to deploy Agent Profiler to Google Cloud Run.

## Prerequisites Checklist

- [ ] GCP Project: `client-profiler-473903` (confirmed)
- [ ] Cloud SQL Instance: `client-profiler-db` (exists)
- [ ] Service Account: `claude-automation@ent-sight-dev-esml01.iam.gserviceaccount.com` (configured)
- [ ] gcloud CLI installed and authenticated
- [ ] Project code in `/Users/michaelreed/es-code/profile-app/agent-profiler/`

## Step 1: Create Database

```bash
# Connect to Cloud SQL
gcloud sql connect client-profiler-db --user=postgres
# Password: reedmichael

# Create database
CREATE DATABASE agent_profiler;

# Connect to new database
\c agent_profiler

# Run schema (exit psql first, then run from local machine)
\q
```

```bash
# Apply schema from local machine
psql -h 136.114.255.63 -U postgres -d agent_profiler -f /Users/michaelreed/es-code/profile-app/agent-profiler/database/schema.sql
```

**Verify**:
```sql
-- Reconnect to database
psql -h 136.114.255.63 -U postgres -d agent_profiler

-- Check tables
\dt

-- Should see:
-- agent_activity_log
-- agent_llm_conversations
-- analysis_results
-- audit_log
-- benchmark_definitions
-- clients
-- conversation_messages
-- conversation_sessions
-- crm_connections
-- crm_schemas
-- data_transformation_log
-- field_mappings
-- sql_query_log
-- sync_jobs
-- uploaded_files

-- Exit
\q
```

## Step 2: Create Cloud Storage Bucket

```bash
gcloud storage buckets create gs://client-profiler-473903-agent-profiler-data \
  --project=client-profiler-473903 \
  --location=us-central1 \
  --storage-class=STANDARD

# Verify
gcloud storage buckets describe gs://client-profiler-473903-agent-profiler-data
```

## Step 3: Set Up Secrets in Secret Manager

```bash
# JWT Secret Key (generate a random secure key)
openssl rand -base64 32 | gcloud secrets create jwt-secret-key \
  --project=client-profiler-473903 \
  --data-file=-

# Google OAuth Client Secret (replace with your actual secret)
echo -n "YOUR_GOOGLE_OAUTH_CLIENT_SECRET" | gcloud secrets create google-oauth-client-secret \
  --project=client-profiler-473903 \
  --data-file=-

# Grant service account access to secrets
gcloud secrets add-iam-policy-binding jwt-secret-key \
  --project=client-profiler-473903 \
  --member="serviceAccount:claude-automation@ent-sight-dev-esml01.iam.gserviceaccount.com" \
  --role="roles/secretmanager.secretAccessor"

gcloud secrets add-iam-policy-binding google-oauth-client-secret \
  --project=client-profiler-473903 \
  --member="serviceAccount:claude-automation@ent-sight-dev-esml01.iam.gserviceaccount.com" \
  --role="roles/secretmanager.secretAccessor"

# Verify secrets
gcloud secrets list --project=client-profiler-473903
```

## Step 4: Set Google Cloud Project

```bash
gcloud config set project client-profiler-473903

# Verify
gcloud config list
```

## Step 5: Build and Push Docker Image

```bash
cd /Users/michaelreed/es-code/profile-app/agent-profiler

# Build and push using Cloud Build
gcloud builds submit \
  --tag gcr.io/client-profiler-473903/agent-profiler-api:v1.0.0 \
  --timeout=20m \
  backend/

# This will:
# 1. Build the Docker image
# 2. Push to Google Container Registry
# 3. Take about 5-10 minutes
```

**Verify image**:
```bash
gcloud container images list --repository=gcr.io/client-profiler-473903

# Should see: agent-profiler-api
```

## Step 6: Deploy to Cloud Run (First Deployment)

```bash
gcloud run deploy agent-profiler-api \
  --image=gcr.io/client-profiler-473903/agent-profiler-api:v1.0.0 \
  --region=us-central1 \
  --platform=managed \
  --allow-unauthenticated \
  --port=8080 \
  --memory=4Gi \
  --cpu=2 \
  --timeout=600 \
  --min-instances=1 \
  --max-instances=100 \
  --concurrency=80 \
  --add-cloudsql-instances=client-profiler-473903:us-central1:client-profiler-db \
  --service-account=claude-automation@ent-sight-dev-esml01.iam.gserviceaccount.com \
  --set-env-vars="GOOGLE_CLOUD_PROJECT=client-profiler-473903,VERTEX_AI_LOCATION=us-central1,APP_ENV=production,DATABASE_URL=postgresql+asyncpg://postgres:reedmichael@/agent_profiler?host=/cloudsql/client-profiler-473903:us-central1:client-profiler-db,GCS_BUCKET_NAME=client-profiler-473903-agent-profiler-data,GEMINI_FLASH_MODEL=gemini-2.0-flash-exp,GEMINI_PRO_MODEL=gemini-1.5-pro,ALLOWED_DOMAIN=enterprisesight.com,ENABLE_CSV_UPLOAD=true,ENABLE_SALESFORCE_CONNECTOR=true"

# This will:
# 1. Deploy the container to Cloud Run
# 2. Configure all settings
# 3. Return a service URL
# 4. Take about 2-5 minutes
```

## Step 7: Retrieve Secrets and Update Environment

The deployment above doesn't include secrets from Secret Manager. We need to configure the service to access them:

```bash
# Get JWT secret (to verify it exists)
gcloud secrets versions access latest --secret=jwt-secret-key --project=client-profiler-473903

# Update Cloud Run service with secret references
gcloud run services update agent-profiler-api \
  --region=us-central1 \
  --update-secrets=JWT_SECRET_KEY=jwt-secret-key:latest \
  --update-secrets=GOOGLE_OAUTH_CLIENT_SECRET=google-oauth-client-secret:latest
```

## Step 8: Test Deployment

```bash
# Get service URL
SERVICE_URL=$(gcloud run services describe agent-profiler-api \
  --region=us-central1 \
  --format='value(status.url)')

echo "Service URL: $SERVICE_URL"

# Test health endpoint
curl $SERVICE_URL/health

# Expected response:
# {
#   "status": "healthy",
#   "timestamp": "2025-11-23T...",
#   "environment": "production",
#   "version": "1.0.0"
# }

# Test root endpoint
curl $SERVICE_URL/

# Expected response:
# {
#   "name": "Agent Profiler API",
#   "version": "1.0.0",
#   "description": "Multi-agent AI system for client data analysis",
#   "status": "running",
#   "documentation": null
# }
```

## Step 9: View Logs

```bash
# Stream logs in real-time
gcloud run services logs tail agent-profiler-api --region=us-central1

# View recent logs
gcloud run services logs read agent-profiler-api \
  --region=us-central1 \
  --limit=50
```

## Step 10: Set Up Cloud Build Trigger (Optional - for CI/CD)

If you want automatic deployments on git push:

```bash
# Create trigger
gcloud builds triggers create github \
  --name=agent-profiler-deploy \
  --repo-name=YOUR_REPO_NAME \
  --repo-owner=YOUR_GITHUB_ORG \
  --branch-pattern=^main$ \
  --build-config=cloudbuild.yaml \
  --region=us-central1
```

## Troubleshooting

### Issue: Database Connection Fails

**Check Cloud SQL connection**:
```bash
gcloud sql instances describe client-profiler-db
```

**Verify service account has Cloud SQL Client role**:
```bash
gcloud projects get-iam-policy client-profiler-473903 \
  --flatten="bindings[].members" \
  --filter="bindings.members:claude-automation@ent-sight-dev-esml01.iam.gserviceaccount.com"
```

### Issue: Container Fails to Start

**Check logs**:
```bash
gcloud run services logs read agent-profiler-api --region=us-central1 --limit=100
```

**Check service details**:
```bash
gcloud run services describe agent-profiler-api --region=us-central1
```

### Issue: Cannot Access Secrets

**Verify secret exists**:
```bash
gcloud secrets list --project=client-profiler-473903
```

**Check IAM permissions**:
```bash
gcloud secrets get-iam-policy jwt-secret-key --project=client-profiler-473903
```

### Issue: 502 Bad Gateway

Usually means the application is failing to start. Check:
1. Logs for error messages
2. Database connectivity
3. Environment variables are correct
4. Secrets are accessible

## Updating the Service

### Quick Update (same image, different env vars)

```bash
gcloud run services update agent-profiler-api \
  --region=us-central1 \
  --set-env-vars="NEW_VAR=value"
```

### Deploy New Version

```bash
# Build new image
gcloud builds submit \
  --tag gcr.io/client-profiler-473903/agent-profiler-api:v1.0.1 \
  backend/

# Deploy new version
gcloud run deploy agent-profiler-api \
  --image=gcr.io/client-profiler-473903/agent-profiler-api:v1.0.1 \
  --region=us-central1
```

### Rollback

```bash
# List revisions
gcloud run revisions list --service=agent-profiler-api --region=us-central1

# Route traffic to previous revision
gcloud run services update-traffic agent-profiler-api \
  --region=us-central1 \
  --to-revisions=REVISION_NAME=100
```

## Monitoring

### View Service Status

```bash
gcloud run services describe agent-profiler-api --region=us-central1
```

### View Metrics

```bash
# Open in Cloud Console
gcloud run services browse agent-profiler-api --region=us-central1
```

Or visit:
https://console.cloud.google.com/run/detail/us-central1/agent-profiler-api?project=client-profiler-473903

## Security Checklist

- [ ] Database password rotated if needed
- [ ] JWT secret is secure and random
- [ ] Service account has minimal required permissions
- [ ] Cloud SQL instance has authorized networks configured
- [ ] CORS origins configured correctly
- [ ] Secrets stored in Secret Manager (never in code)
- [ ] Audit logging enabled
- [ ] Domain restriction enabled (@enterprisesight.com)

## Next Steps

After successful deployment:

1. **Test Authentication**: Set up Google OAuth client in Google Cloud Console
2. **Create Frontend**: Deploy React/Next.js frontend
3. **Implement Agents**: Build out the 7 AI agents
4. **Add CRM Connectors**: Implement Salesforce and other CRM integrations
5. **Enable Monitoring**: Set up alerts and dashboards

## Useful Commands Reference

```bash
# View service URL
gcloud run services describe agent-profiler-api --region=us-central1 --format='value(status.url)'

# Tail logs
gcloud run services logs tail agent-profiler-api --region=us-central1

# Delete service (if needed)
gcloud run services delete agent-profiler-api --region=us-central1

# List all Cloud Run services
gcloud run services list --region=us-central1

# Update memory
gcloud run services update agent-profiler-api --region=us-central1 --memory=8Gi

# Update CPU
gcloud run services update agent-profiler-api --region=us-central1 --cpu=4

# Update min instances
gcloud run services update agent-profiler-api --region=us-central1 --min-instances=2
```

---

**Deployment Complete!** 🚀

Your Agent Profiler API is now running on Cloud Run.
