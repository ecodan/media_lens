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

Media Lens runs on a **scheduled GCP VM** (`media-lens-vm`, zone `us-central1-a`):
- VM starts at ~6 AM UTC via Cloud Scheduler, runs pipeline, stops at ~9 AM UTC
- **Normal state: VM is STOPPED** — this is expected and not an error
- Job outputs are written to **GCS bucket** `gs://media-lens-storage/` as the canonical store
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

# Check last execution time and status for VM start job
gcloud scheduler jobs describe start-media-lens-vm \
  --location=us-central1 \
  --project=medialens \
  --format="table(name, schedule, state, lastAttemptTime, status)"
```

**Decision**:
- Scheduler job is **DISABLED or PAUSED** → That's why the VM never started. Report to user.
- Scheduler shows **success** but no logs → VM started but pipeline didn't run. May need VM access to investigate (ask user first).
- Scheduler shows **failure** → Report the scheduler error to user.

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
  2. [e.g. "Start VM to inspect container logs and check cron configuration"]
  3. [e.g. "Manually trigger a pipeline run to catch up on missed dates"]
```

**Do not take any action until the user reviews this report and approves.**

---

## VM Access (Only If Needed and Approved)

⚠️ **The VM is normally STOPPED. Do not start it without explicit user approval.**

If investigation requires VM access (e.g., logs not in Cloud Logging, need to inspect cron config):

```bash
# 1. Check current VM state first
gcloud compute instances describe media-lens-vm \
  --zone=us-central1-a --format="get(status)"

# 2. If STOPPED — present to user:
#    "The VM is currently stopped. Starting it will incur Compute Engine charges
#     until we stop it again. Shall I start it for diagnostics?"

# 3. Only after approval:
gcloud compute instances start media-lens-vm --zone=us-central1-a

# 4. After diagnostics — confirm with user then stop:
gcloud compute instances stop media-lens-vm --zone=us-central1-a
```

### Useful VM Commands (once running and approved)

```bash
# Container logs
gcloud compute ssh media-lens-vm --zone=us-central1-a \
  --command="docker logs media-lens --tail=100"

# Errors only
gcloud compute ssh media-lens-vm --zone=us-central1-a \
  --command="docker logs media-lens 2>&1 | grep -E 'ERROR|FAILED|Exception' | tail -30"

# Cron configuration (set up by startup-script.sh, not baked into image)
gcloud compute ssh media-lens-vm --zone=us-central1-a \
  --command="sudo crontab -l"

# Startup script log (startup-script.sh writes here on every boot)
gcloud compute ssh media-lens-vm --zone=us-central1-a \
  --command="sudo tail -100 /var/log/startup-script.log"

# Startup script systemd journal (alternative)
gcloud compute ssh media-lens-vm --zone=us-central1-a \
  --command="sudo journalctl -u google-startup-scripts.service -n 50"

# Disk space
gcloud compute ssh media-lens-vm --zone=us-central1-a \
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
- `startup-script.sh` logs everything to `/var/log/startup-script.log` on the VM — check this when diagnosing VM startup failures
- The startup script clears `/app` and re-clones the repo on every VM boot
- Cron job (`0 16 * * * /usr/local/bin/run-container-job.sh`) is set up by the startup script, not baked into the image
- The job script calls `http://0.0.0.0:8080/run` with the full pipeline steps

---

## GCP Project Reference

| Resource | Value |
|----------|-------|
| Project ID | `medialens` |
| VM | `media-lens-vm` |
| Zone | `us-central1-a` |
| Container | `media-lens` |
| GCS Bucket | `gs://media-lens-storage/` |
| Scheduler Region | `us-central1` |
| Start schedule | `0 6 * * *` (6 AM UTC) |
| Stop schedule | `0 9 * * *` (9 AM UTC) |
