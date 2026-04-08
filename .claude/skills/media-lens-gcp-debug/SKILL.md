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

## Context

Media Lens runs on a **scheduled GCP Managed Instance Group (MIG)** (`media-lens-mig`, region `us-west1`):
- MIG scales to 1 at 15:00 UTC via Cloud Scheduler, scales back to 0 (terminates instance) at 18:00 UTC
- **Normal state: MIG targetSize=0** — no running instances is expected and not an error
- Instances are ephemeral (no persistent disk) — all storage is in **GCS bucket** `gs://media-lens-storage/`
- Published HTML is uploaded via SFTP to the web hosting server

---

## Diagnostic Protocol

Follow these steps **in order**. Do not skip ahead. Do not start the VM. **Report findings to the user before suggesting any action.**

### Step 1 — Check GCS for the date(s) in question

GCS is the source of truth. This requires no VM access.

```bash
# List date directories for the current month
gsutil ls gs://media-lens-storage/jobs/YYYY/MM/

# Check if a specific date exists
gsutil ls gs://media-lens-storage/jobs/YYYY/MM/DD/
```

**Decision**:
- Date directory is **missing** → Job did not run or failed before writing output. Go to **Step 4 (Logs)**.
- Date directory **exists** → Go to **Step 2**.

---

### Step 2 — Inspect files for the date

Check that all expected artifacts are present and non-empty.

```bash
# List all files for that job run
gsutil ls -l gs://media-lens-storage/jobs/YYYY/MM/DD/HHmmss/

# Expected files per site (bbc, cnn, foxnews):
#   www.SITE.com.html                  (raw scraped HTML)
#   www.SITE.com-clean.html            (cleaned HTML)
#   www.SITE.com-clean-extracted.json  (extracted headlines)
#   www.SITE.com-clean-article-0..4.json  (article content)
#
# Also expected:
#   daily_news.txt  (daily summary — written at end of interpret step)

# Spot-check a file has content (size > 0)
gsutil cat gs://media-lens-storage/jobs/YYYY/MM/DD/HHmmss/daily_news.txt | head -20
```

**Decision**:
- Files are **missing or empty** → Process broke mid-run. Note which files are absent to identify the failing step. Go to **Step 4 (Logs)**.
- All files **present and non-empty** → Data was processed. Go to **Step 3 (Deploy)**.

---

### Step 3 — Investigate why files weren't published (FTP/SFTP)

If data is in GCS but not live on the site, the deploy step failed. Check Cloud Logging — no VM access needed.

```bash
# View recent logs from the media-lens container on GCP Logging
gcloud logging read \
  'resource.type="gce_instance" AND jsonPayload.message=~"deploy|upload|sftp|SFTP"' \
  --project=medialens \
  --limit=50 \
  --format="table(timestamp, jsonPayload.message)"

# Broaden to all recent container output
gcloud logging read \
  'resource.type="gce_instance"' \
  --project=medialens \
  --freshness=2d \
  --limit=100 \
  --format="table(timestamp, jsonPayload.message)"
```

**Decision**:
- Logs show SFTP/upload errors → credential issue, network issue, or remote permission problem. Report to user.
- Logs show deploy step never started → format step may have failed. Check for format errors in logs.
- No logs for the expected date → VM may not have run at all. Check Cloud Scheduler (Step 4b).

---

### Step 4 — Investigate why the job didn't run or broke mid-run

#### 4a — Check Cloud Logging for the date in question

```bash
# Look for errors on a specific date (adjust date)
gcloud logging read \
  'resource.type="gce_instance" AND severity>=ERROR' \
  --project=medialens \
  --freshness=2d \
  --limit=50 \
  --format="table(timestamp, severity, jsonPayload.message)"

# Check for step progression (harvest → extract → interpret → format → deploy)
gcloud logging read \
  'resource.type="gce_instance" AND jsonPayload.message=~"Starting.*step|Completed|Failed|ERROR"' \
  --project=medialens \
  --freshness=2d \
  --limit=100 \
  --format="table(timestamp, jsonPayload.message)"
```

#### 4b — Check Cloud Scheduler

```bash
# List all scheduler jobs and their state
gcloud scheduler jobs list --location=us-central1 --project=medialens

# Check last execution time and status for start job
gcloud scheduler jobs describe start-media-lens-vm \
  --location=us-central1 \
  --project=medialens \
  --format="yaml(schedule, state, lastAttemptTime, status, httpTarget.uri)"
```

**Decision**:
- Scheduler job is **DISABLED or PAUSED** → That's why the MIG never scaled up. Report to user.
- Scheduler shows **success** but no pipeline logs → MIG scaled up but pipeline didn't run (likely cron daemon issue — check startup script logs on VM).
- Scheduler shows **failure** → Report the scheduler error to user.
- Scheduler URI targets wrong region or resource → Update the scheduler job URI to match current MIG.

---

### Step 5 — Report Findings

Before taking any action, summarize what was found:

```
DIAGNOSIS REPORT
================
Date(s) checked: YYYY-MM-DD

GCS status:
  - Job directory: [present / missing]
  - Files: [list present/missing files]
  - daily_news.txt: [present and has data / missing / empty]

Deploy status:
  - [Files found but not deployed / Not reached / N/A]
  - Deploy logs: [any errors found]

Root cause:
  - [e.g. "Job directory missing — job did not run on this date"]
  - [e.g. "All files present but deploy step logged SFTP connection refused"]
  - [e.g. "Cloud Scheduler job start-media-lens-vm is PAUSED"]

Suggested next steps (awaiting your approval):
  1. [e.g. "Enable the Cloud Scheduler job"]
  2. [e.g. "Scale MIG to 1 to inspect container logs and verify cron is running"]
  3. [e.g. "Manually trigger a pipeline run to catch up on missed dates"]
```

**Do not take any action until the user reviews this report and approves.**

---

## MIG Instance Access (Only If Needed and Approved)

⚠️ **The MIG is normally at targetSize=0 (no instances). Do not scale it up without explicit user approval.**

If investigation requires instance access (e.g., logs not in Cloud Logging, need to inspect cron config):

```bash
# 1. Check current MIG state first
gcloud compute instance-groups managed describe media-lens-mig \
  --region=us-west1 --project=medialens --format="get(targetSize,status.isStable)"

# 2. If targetSize=0 — present to user:
#    "The MIG has no running instances. Scaling to 1 will start a new VM and incur
#     Compute Engine charges until we scale back to 0. Shall I scale up for diagnostics?"

# 3. Only after approval:
gcloud compute instance-groups managed resize media-lens-mig \
  --size=1 --region=us-west1 --project=medialens

# 4. Get instance name (wait ~2 min for it to appear):
gcloud compute instance-groups managed list-instances media-lens-mig \
  --region=us-west1 --project=medialens

# 5. After diagnostics — confirm with user then scale back down:
gcloud compute instance-groups managed resize media-lens-mig \
  --size=0 --region=us-west1 --project=medialens
```

### Useful Instance Commands (once running and approved)

```bash
# Replace XXXX with actual instance suffix from list-instances above
INSTANCE=media-lens-mig-XXXX
ZONE=us-west1-a  # check actual zone from list-instances

# Container logs
gcloud compute ssh $INSTANCE --zone=$ZONE \
  --command="docker logs media-lens --tail=100"

# Errors only
gcloud compute ssh $INSTANCE --zone=$ZONE \
  --command="docker logs media-lens 2>&1 | grep -E 'ERROR|FAILED|Exception' | tail -30"

# Cron configuration
gcloud compute ssh $INSTANCE --zone=$ZONE \
  --command="sudo crontab -l && sudo systemctl status cron"

# Cron job output log
gcloud compute ssh $INSTANCE --zone=$ZONE \
  --command="sudo tail -100 /var/log/run-container-job.log"

# Startup script log
gcloud compute ssh $INSTANCE --zone=$ZONE \
  --command="sudo tail -100 /var/log/startup-script.log"

# Disk space
gcloud compute ssh $INSTANCE --zone=$ZONE \
  --command="df -h"
```

---

## File Structure Reference

### GCS Job Artifacts (`gs://media-lens-storage/jobs/YYYY/MM/DD/HHmmss/`)
| File | Written by step | Indicates |
|------|----------------|-----------|
| `www.SITE.com.html` | harvest_scrape | Scrape succeeded |
| `www.SITE.com-clean.html` | harvest_clean | Clean succeeded |
| `www.SITE.com-clean-extracted.json` | extract | Extraction succeeded |
| `www.SITE.com-clean-article-N.json` | extract | Article parsing succeeded |
| `daily_news.txt` | interpret | Interpretation succeeded |

Missing files indicate which step failed.

### GCS Staging (`gs://media-lens-storage/staging/`)
```
staging/
├── medialens.html          ← index page
├── medialens-YYYY-WNN.html ← weekly report pages
└── articles/...            ← article reader views
```

---

## Additional Reference Documentation

Before or during an investigation, consult these local project files for deeper context:

| File | Contents |
|------|----------|
| `README.md` | Architecture overview, data flow, pipeline stages, analysis approach |
| `readme-deployment.md` | Step-by-step GCP setup, VM/disk/scheduler config, troubleshooting section |
| `startup-script.sh` | Full startup automation — what runs on VM boot, Docker install, repo clone, cron setup. Logs to `/var/log/startup-script.log` on the VM |

**Key things to know from these files**:
- `startup-script.sh` is stored in GCS (`gs://media-lens-storage/startup-script.sh`) and pulled by the instance template on each boot
- The startup script installs Docker, clones the repo, installs/starts the `cron` daemon, and builds/starts the container
- Cron job (`0 16 * * * /usr/local/bin/run-container-job.sh >> /var/log/run-container-job.log 2>&1`) is set up by the startup script, not baked into the image
- The job script calls `http://0.0.0.0:8080/run` with the full pipeline steps
- Instances are ephemeral — each boot is a fresh Debian 12 VM with no prior state

---

## GCP Project Reference

| Resource | Value |
|----------|-------|
| Project ID | `medialens` |
| MIG | `media-lens-mig` |
| Region | `us-west1` |
| Instance Template | `media-lens-template-v2` |
| Container | `media-lens` |
| GCS Bucket | `gs://media-lens-storage/` |
| Startup Script | `gs://media-lens-storage/startup-script.sh` |
| Scheduler Region | `us-central1` |
| Start schedule | `0 15 * * *` (15:00 UTC / 7 AM PT) |
| Stop schedule | `0 18 * * *` (18:00 UTC / 10 AM PT) |
