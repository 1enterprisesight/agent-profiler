#!/bin/bash
# Script to apply database schema to agent_profiler database

echo "==================================================================="
echo "Agent Profiler - Database Schema Application"
echo "==================================================================="
echo ""
echo "This script will apply the database schema to the agent_profiler database."
echo ""
echo "Options:"
echo ""
echo "1. Via Cloud SQL Console (Easiest)"
echo "   - Go to: https://console.cloud.google.com/sql/instances/client-profiler-db/databases/agent_profiler?project=client-profiler-473903"
echo "   - Click 'Query' button"
echo "   - Copy contents of database/schema.sql"
echo "   - Paste and execute"
echo ""
echo "2. Via gcloud sql connect (if password is known)"
echo "   Run: gcloud sql connect client-profiler-db --user=postgres --database=agent_profiler"
echo "   Then paste the contents of database/schema.sql"
echo ""
echo "3. Via Cloud Shell"
echo "   - Open Cloud Shell: https://console.cloud.google.com/cloudshell"
echo "   - Upload database/schema.sql"
echo "   - Run: gcloud sql connect client-profiler-db --user=postgres --database=agent_profiler < schema.sql"
echo ""
echo "4. Apply schema directly from this script:"
echo ""

read -p "Do you want to try connecting now? (y/n): " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]
then
    echo "Connecting to Cloud SQL..."
    gcloud sql connect client-profiler-db --user=postgres --database=agent_profiler < database/schema.sql

    if [ $? -eq 0 ]; then
        echo ""
        echo "✅ Schema applied successfully!"
        echo ""
        echo "You can now redeploy the Cloud Run service:"
        echo "cd /Users/michaelreed/es-code/profile-app/agent-profiler"
        echo "./redeploy.sh"
    else
        echo ""
        echo "❌ Schema application failed."
        echo "Please use one of the manual methods above."
    fi
else
    echo ""
    echo "Schema not applied. Please use one of the methods above."
fi

echo ""
echo "After applying the schema, verify with:"
echo "gcloud sql connect client-profiler-db --user=postgres --database=agent_profiler"
echo "Then run: \\dt"
echo "You should see 15 tables listed."
echo ""
