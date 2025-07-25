#!/bin/bash

# Cloud Scheduler Setup for Investment Agent
# This script creates a Cloud Scheduler job to run your investment agent every 30 minutes during trading hours

# Configuration
PROJECT_ID="magnetic-planet-464215-a3"
FUNCTION_NAME="investment-agent"
REGION="us-central1"
JOB_NAME="investment-agent-scheduler"

# Cron schedule: Every 30 minutes from 9 AM to 4:30 PM EST (1 PM to 8:30 PM UTC), Monday-Friday
# This gives you 16 executions per day = 80 requests (well within 100 daily limit)
SCHEDULE="0,30 13-20 * * 1-5"

# Time zone (Eastern Time for US trading hours)
TIMEZONE="America/New_York"

# Cloud Function URL (replace with your actual function URL)
FUNCTION_URL="https://${REGION}-${PROJECT_ID}.cloudfunctions.net/${FUNCTION_NAME}"

echo "Creating Cloud Scheduler job..."
echo "Schedule: Every 30 minutes during trading hours (9 AM - 5 PM EST)"
echo "Function URL: ${FUNCTION_URL}"

gcloud scheduler jobs create http ${JOB_NAME} \
    --location=${REGION} \
    --schedule="${SCHEDULE}" \
    --time-zone="${TIMEZONE}" \
    --uri="${FUNCTION_URL}" \
    --http-method=GET \
    --description="Automated investment analysis every 30 minutes during trading hours" \
    --project=${PROJECT_ID}

echo "Scheduler job created successfully!"
echo ""
echo "Job Details:"
echo "- Name: ${JOB_NAME}"
echo "- Schedule: ${SCHEDULE}"
echo "- Timezone: ${TIMEZONE}"
echo "- Target: ${FUNCTION_URL}"
echo ""
echo "This will execute:"
echo "- 16 times per trading day"
echo "- 80 API requests per day (within 100 free tier limit)"
echo "- Times: 9:00, 9:30, 10:00, 10:30, 11:00, 11:30, 12:00, 12:30, 1:00, 1:30, 2:00, 2:30, 3:00, 3:30, 4:00, 4:30 PM EST"
