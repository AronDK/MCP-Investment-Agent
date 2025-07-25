# Cloud Scheduler Configuration for Investment Agent

## Current vs Recommended Schedule

### Your Current Schedule: `*/5 9-16 * * 1-5`
- **Frequency**: Every 5 minutes
- **Hours**: 9 AM - 4 PM (8 hours)
- **Days**: Monday-Friday
- **Total executions**: 96 per day (8 hours × 12 times per hour)
- **API requests**: 480 per day (96 × 5 requests each)
- **Problem**: Exceeds free tier limit of 100 requests/day

### Recommended Schedule: `0,30 13-20 * * 1-5`
- **Frequency**: Every 30 minutes (at :00 and :30)
- **Hours**: 1 PM - 8 PM UTC (9 AM - 4 PM EST)
- **Days**: Monday-Friday
- **Total executions**: 16 per day
- **API requests**: 80 per day (16 × 5 requests each)
- **Benefit**: Stays within free tier with 20-request buffer

## Setup Instructions

### Option 1: Run the setup script
```bash
chmod +x cloud-scheduler-setup.sh
./cloud-scheduler-setup.sh
```

### Option 2: Manual gcloud command
```bash
gcloud scheduler jobs create http investment-agent-scheduler \
    --location=us-central1 \
    --schedule="0,30 13-20 * * 1-5" \
    --time-zone="America/New_York" \
    --uri="https://us-central1-magnetic-planet-464215-a3.cloudfunctions.net/investment-agent" \
    --http-method=GET \
    --description="Investment agent - every 30 minutes during trading hours"
```

### Option 3: Google Cloud Console
1. Go to Cloud Console → Cloud Scheduler
2. Click "Create Job"
3. Fill in:
   - **Name**: `investment-agent-scheduler`
   - **Region**: `us-central1`
   - **Frequency**: `0,30 13-20 * * 1-5`
   - **Timezone**: `America/New_York`
   - **Target Type**: HTTP
   - **URL**: Your Cloud Function URL
   - **HTTP Method**: GET

## Schedule Explanation

The cron expression `0,30 13-20 * * 1-5` means:
- `0,30`: At minutes 0 and 30 (twice per hour)
- `13-20`: Between 1 PM and 8 PM UTC
- `*`: Every day of month
- `*`: Every month
- `1-5`: Monday through Friday

## Free Tier Optimization

This schedule ensures you stay within Gemini free tier limits:
- **Daily executions**: 16
- **Daily API requests**: 80 (16 × 5 requests per cycle)
- **Free tier limit**: 100 requests/day
- **Safety buffer**: 20 requests for errors/retries

## Execution Times (EST)
- 9:00 AM, 9:30 AM
- 10:00 AM, 10:30 AM  
- 11:00 AM, 11:30 AM
- 12:00 PM, 12:30 PM
- 1:00 PM, 1:30 PM
- 2:00 PM, 2:30 PM
- 3:00 PM, 3:30 PM
- 4:00 PM, 4:30 PM

This provides frequent analysis during active trading hours while respecting API limits.
