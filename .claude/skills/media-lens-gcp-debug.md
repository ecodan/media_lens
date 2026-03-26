---
name: media-lens-gcp-debug
type: diagnostic
description: "Debug and diagnose media-lens production issues on Google Cloud Platform"
domain: "Media Lens Infrastructure"
triggers:
  - "debug gcp"
  - "gcp debug"
  - "check gcp status"
  - "media lens isn't running"
  - "investigate production"
  - "what went wrong with gcp"
---

# Media Lens GCP Debug Skill

## Quick Start

This skill helps you debug media-lens production issues on Google Cloud Platform. It handles:
- VM lifecycle (start/stop with cost awareness)
- Container health monitoring
- Job execution tracking
- Log inspection
- Cloud Scheduler verification

**Key context**: The VM runs on a schedule (6 AM-9 AM UTC daily) and is normally STOPPED to save costs.

---

## Getting Started

### Check Status
```bash
# Is the VM running?
gcloud compute instances describe media-lens-vm --zone=us-central1-a --format="get(status)"

# When was the last job?
gcloud compute ssh media-lens-vm --zone=us-central1-a --command="ls -lah /app/working/out/jobs/2026/03/ | tail -5"

# Check pipeline cursors (which step last ran)
gcloud compute ssh media-lens-vm --zone=us-central1-a --command="cat /app/working/out/format_cursor.txt && echo '---' && cat /app/working/out/deploy_cursor.txt"
```

---

## VM Lifecycle Management

### Check VM Status
```bash
gcloud compute instances describe media-lens-vm --zone=us-central1-a --format="get(status)"
# Returns: RUNNING or STOPPED
```

### Start VM (For Diagnostics)
⚠️ **Cost warning**: Running incurs Compute Engine charges. Ensure you stop it afterward.

```bash
gcloud compute instances start media-lens-vm --zone=us-central1-a
# Wait 30-60 seconds for VM to boot
```

### Verify VM is Running
```bash
gcloud compute instances describe media-lens-vm --zone=us-central1-a --format="get(status)"
# Should return: RUNNING
```

### Stop VM (After Diagnostics)
🛑 **Always do this** to prevent unnecessary charges.

```bash
gcloud compute instances stop media-lens-vm --zone=us-central1-a
```

---

## Container Diagnostics

### Container Status
```bash
gcloud compute ssh media-lens-vm --zone=us-central1-a --command="docker ps -a | grep media-lens"
```

### Recent Container Logs
```bash
# Last 50 lines
gcloud compute ssh media-lens-vm --zone=us-central1-a --command="docker logs media-lens --tail=50"

# Last 2 hours with timestamps
gcloud compute ssh media-lens-vm --zone=us-central1-a --command="docker logs -t media-lens --since=2h"

# Search for errors
gcloud compute ssh media-lens-vm --zone=us-central1-a --command="docker logs media-lens 2>&1 | grep -i error | tail -20"

# Search for specific step
gcloud compute ssh media-lens-vm --zone=us-central1-a --command="docker logs media-lens 2>&1 | grep 'Starting.*step' | tail -10"
```

### Restart Container
```bash
gcloud compute ssh media-lens-vm --zone=us-central1-a --command="docker compose --profile cloud restart"
```

---

## Job Execution Tracking

### List Recent Jobs
```bash
# Most recent jobs by date
gcloud compute ssh media-lens-vm --zone=us-central1-a --command="ls -lah /app/working/out/jobs/2026/03/ | tail -20"

# All jobs with timestamps (YYYY/MM/DD/HHmmss format)
gcloud compute ssh media-lens-vm --zone=us-central1-a --command="find /app/working/out/jobs -type d -name '[0-9]*' | sort | tail -20"
```

### Check Job Artifacts
```bash
# List job contents (look for daily_news.txt, JSON files)
gcloud compute ssh media-lens-vm --zone=us-central1-a --command="ls -la /app/working/out/jobs/2026/03/24/160000/"

# Get job summary
gcloud compute ssh media-lens-vm --zone=us-central1-a --command="cat /app/working/out/jobs/2026/03/24/160000/daily_news.txt | head -20"
```

### Check Format/Deploy Cursor
```bash
# Format cursor (when format step completed)
gcloud compute ssh media-lens-vm --zone=us-central1-a --command="cat /app/working/out/format_cursor.txt"

# Deploy cursor (when deploy step completed)
gcloud compute ssh media-lens-vm --zone=us-central1-a --command="cat /app/working/out/deploy_cursor.txt"
```

**Interpretation**:
- If `format_cursor` is recent but `deploy_cursor` is very old → format runs but deploy doesn't
- If both are old → jobs aren't running at all
- If format_cursor is newer than expected → recent jobs ran

---

## Cloud Scheduler

### List All Scheduler Jobs
```bash
gcloud scheduler jobs list --location=us-central1
```

### Check VM Start Job
```bash
# When does it run and what's its status?
gcloud scheduler jobs describe start-media-lens-vm --location=us-central1 --format=json | jq '{schedule: .schedule, nextRunTime: .lastExecutionTime, state: .state}'
```

### Check VM Stop Job
```bash
gcloud scheduler jobs describe stop-media-lens-vm --location=us-central1 --format=json | jq '{schedule: .schedule, lastExecution: .lastExecutionTime, state: .state}'
```

### Manually Trigger Scheduler Job
```bash
# Start VM immediately (for testing)
gcloud scheduler jobs run start-media-lens-vm --location=us-central1

# Stop VM immediately (for testing)
gcloud scheduler jobs run stop-media-lens-vm --location=us-central1
```

---

## Web API Testing

### Get External IP
```bash
EXTERNAL_IP=$(gcloud compute instances describe media-lens-vm --zone=us-central1-a --format="get(networkInterfaces[0].accessConfigs[0].natIP)")
echo "External IP: $EXTERNAL_IP"
```

### Health Check
```bash
curl http://$EXTERNAL_IP:8080/health
# Should return: {"status": "ok"} or similar
```

### Check Status
```bash
curl http://$EXTERNAL_IP:8080/status
# Returns current run status if any
```

### Manually Trigger Pipeline
```bash
# Run full pipeline
curl -X POST http://$EXTERNAL_IP:8080/run \
  -H "Content-Type: application/json" \
  -d '{
    "steps": ["harvest", "extract", "interpret_weekly", "format", "deploy"]
  }'

# Run only harvest (for quick testing)
curl -X POST http://$EXTERNAL_IP:8080/run \
  -H "Content-Type: application/json" \
  -d '{"steps": ["harvest"]}'
```

---

## VM SSH Access

### SSH Into VM
```bash
gcloud compute ssh media-lens-vm --zone=us-central1-a
```

### Run Single Command
```bash
gcloud compute ssh media-lens-vm --zone=us-central1-a --command="whoami"
```

### Access Container Shell
```bash
gcloud compute ssh media-lens-vm --zone=us-central1-a --command="docker exec -it media-lens /bin/bash"
```

### Check Disk Space
```bash
gcloud compute ssh media-lens-vm --zone=us-central1-a --command="df -h"
```

### Check Persistent Disk Mount
```bash
gcloud compute ssh media-lens-vm --zone=us-central1-a --command="mount | grep /app/working"
```

---

## Cloud Storage (GCS)

### List Bucket Contents
```bash
gsutil ls gs://media-lens-storage/

# List jobs in bucket
gsutil ls gs://media-lens-storage/jobs/2026/03/

# List recent job dates
gsutil ls -r gs://media-lens-storage/jobs/ | grep "jobs/2026" | tail -20
```

### Check Storage Usage
```bash
gsutil du -s gs://media-lens-storage/
```

### Download Job Output
```bash
# Download a specific job's daily_news.txt
gsutil cp gs://media-lens-storage/jobs/2026/03/23/160000/daily_news.txt ./

# Compare local vs cloud
diff /app/working/out/jobs/2026/03/23/160000/daily_news.txt ./daily_news.txt
```

---

## Troubleshooting Flows

### Issue: "No results for March 24-25"

**Step 1**: Check what dates have jobs
```bash
gcloud compute ssh media-lens-vm --zone=us-central1-a --command="ls -1 /app/working/out/jobs/2026/03/"
# If only "23" exists, no jobs ran on 24/25
```

**Step 2**: Check if VM is still running (might be stuck)
```bash
gcloud compute instances describe media-lens-vm --zone=us-central1-a --format="get(status)"
```

**Step 3**: If running, check logs for errors
```bash
gcloud compute ssh media-lens-vm --zone=us-central1-a --command="docker logs media-lens --tail=100 | grep -E 'ERROR|FAILED|Exception'"
```

**Step 4**: Check cursors to see where pipeline stopped
```bash
gcloud compute ssh media-lens-vm --zone=us-central1-a --command="cat /app/working/out/format_cursor.txt"
# If very old, format step hasn't run
```

**Step 5**: Check Cloud Scheduler
```bash
gcloud scheduler jobs list --location=us-central1 | grep media-lens
# Verify jobs exist and have "ENABLED" state
```

### Issue: "Container keeps crashing"

**Check logs**:
```bash
gcloud compute ssh media-lens-vm --zone=us-central1-a --command="docker logs media-lens --tail=200"
```

**Common causes**:
- Out of memory: Check `docker stats media-lens`
- Dependency missing: Look for "ModuleNotFoundError" or "ImportError"
- Disk full: Run `df -h`
- API quota: Look for 429 or quota errors in logs

**Restart container**:
```bash
gcloud compute ssh media-lens-vm --zone=us-central1-a --command="docker compose --profile cloud restart"
```

### Issue: "Deployment not working (format_cursor old but deploy_cursor older)"

**Check deploy logs**:
```bash
gcloud compute ssh media-lens-vm --zone=us-central1-a --command="docker logs media-lens 2>&1 | grep -i 'deploy\|upload\|sftp' | tail -20"
```

**Common causes**:
- SFTP credentials invalid
- Remote directory permissions issue
- Network connectivity to SFTP server
- Rate limiting on upload

**Check SFTP connectivity**:
```bash
gcloud compute ssh media-lens-vm --zone=us-central1-a --command="cat ~/.ssh/siteground && echo 'Key exists'"
```

### Issue: "VM won't start"

**Check GCP quotas**:
```bash
gcloud compute project-info describe --project=medialens | grep -A 5 "QUOTA"
```

**Check startup script**:
```bash
gcloud compute ssh media-lens-vm --zone=us-central1-a --command="sudo journalctl -u google-startup-scripts.service -n 50"
```

**Manual startup**:
```bash
gcloud compute ssh media-lens-vm --zone=us-central1-a --command="cd /app && sudo bash startup-script.sh"
```

---

## Common Commands Reference

| Task | Command |
|------|---------|
| VM status | `gcloud compute instances describe media-lens-vm --zone=us-central1-a --format="get(status)"` |
| Start VM | `gcloud compute instances start media-lens-vm --zone=us-central1-a` |
| Stop VM | `gcloud compute instances stop media-lens-vm --zone=us-central1-a` |
| Container logs | `gcloud compute ssh media-lens-vm --zone=us-central1-a --command="docker logs media-lens --tail=50"` |
| Last job date | `gcloud compute ssh media-lens-vm --zone=us-central1-a --command="ls -1 /app/working/out/jobs/2026/03/ \| tail -1"` |
| Format cursor | `gcloud compute ssh media-lens-vm --zone=us-central1-a --command="cat /app/working/out/format_cursor.txt"` |
| Scheduler jobs | `gcloud scheduler jobs list --location=us-central1` |
| SSH to VM | `gcloud compute ssh media-lens-vm --zone=us-central1-a` |
| Health check | `curl http://$(gcloud compute instances describe media-lens-vm --zone=us-central1-a --format="get(networkInterfaces[0].accessConfigs[0].natIP)"):8080/health` |

---

## Cost Awareness

**Running costs**: The e2-medium VM with persistent disk costs ~$0.30/day = ~$9/month continuous.

**Scheduled operation** (current): Only 2-3 hours daily = ~$0.25/month (saves ~$8.75/month vs continuous).

**When debugging**: Starting the VM manually incurs costs until you stop it. Always stop when done.

---

## Safety Guardrails

✅ **Always ask before starting VM** (cost implications)
✅ **Always stop VM after diagnostics** (prevent bill surprises)
✅ **Never auto-start/stop without explicit request**
✅ **Warn before running expensive operations**
✅ **Verify changes before committing**

---

**Last Updated**: 2026-03-25
**Skill Version**: 1.0
**GCP Project**: medialens
**VM Zone**: us-central1-a
