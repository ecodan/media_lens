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
---

# media-lens-gcp-debug Skill

## Summary
Comprehensive debugging and diagnostics skill for media-lens production issues on Google Cloud Platform. Helps investigate VM status, container logs, job execution history, Cloud Storage, and scheduling configuration.

## Triggers
Activate this skill when:
- User says: "debug gcp", "gcp debug", "investigate production", "what's wrong with gcp", "check gcp status"
- User reports: "media lens isn't running", "no jobs yesterday", "results missing for date X"
- User asks: "why didn't the job run", "check if vm is running", "see container logs"
- User needs: "diagnose deployment issue", "troubleshoot cloud run", "why is production broken"

## Capabilities

### 1. VM Instance Diagnostics
- Check instance status (running/stopped)
- Get external IP address
- Retrieve instance metadata and configuration
- List all compute instances
- Check startup script execution logs
- SSH into VM for manual investigation

### 2. Container & Application State
- View Docker container logs (with time ranges, tail limits)
- Check container status and lifecycle
- List running/stopped containers
- Access container shell for debugging
- Monitor application health (HTTP endpoints)

### 3. Job & Output Tracking
- List recent job directories on VM persistent disk
- Check job timestamps and execution order
- Verify job output files (daily_news.txt, JSON artifacts, HTML)
- Examine cursor files (format_cursor, deploy_cursor) to track pipeline stage
- Compare job counts and coverage by date

### 4. Cloud Storage & GCS
- List bucket contents and structure
- Check storage usage and quotas
- Verify files in gs://media-lens-storage
- Compare local vs cloud storage state
- Validate bucket permissions

### 5. Cloud Scheduler & Cron
- List all Cloud Scheduler jobs
- Check job execution history
- View last execution time and status
- Manually trigger jobs for testing
- Examine cron job configuration on VM

### 6. Persistent Disk & Mounts
- Check disk attachment status
- Verify mount points and permissions
- Monitor disk space usage
- Detect mount issues or corruption

### 7. Network & Connectivity
- Test health check endpoints (port 8080)
- Trigger manual runs via HTTP API
- Check web server responsiveness
- Validate external IP accessibility

## Implementation Details

### Prerequisites
- Google Cloud SDK (`gcloud`) installed and authenticated
- Project ID: `medialens`
- VM zone: `us-central1-a`
- Container name: `media-lens`
- Persistent disk: `media-lens-data` mounted at `/app/working`

### Critical: Scheduled Lifecycle
⚠️ **The VM and container are NOT continuously running.** They follow this schedule:
- **Normal state**: VM is **STOPPED** (saves costs)
- **6:00 AM UTC (1 AM PT)**: Cloud Scheduler starts the VM
- **~7:00 AM UTC (2 AM PT)**: Container runs pipeline (harvest → extract → interpret → format → deploy)
- **~9:00 AM UTC (4 AM PT)**: Cloud Scheduler stops the VM (unless pipeline still running)
- **Rest of day**: VM remains STOPPED

**When debugging**:
1. If VM is stopped, offer to start it (understand this keeps costs running)
2. After diagnostics, ALWAYS shut down the VM (unless user explicitly wants to leave it running)
3. Note: If VM is already running, container may or may not be active (could be between job runs, stuck, or restarting)

### Command Structure
All commands follow this pattern:
```bash
# Check VM status
gcloud compute instances describe media-lens-vm --zone=us-central1-a --format="get(status)"

# Start VM (if needed for diagnostics)
gcloud compute instances start media-lens-vm --zone=us-central1-a

# SSH and run commands
gcloud compute ssh media-lens-vm --zone=us-central1-a --command="docker logs media-lens --tail=50"

# Stop VM (after diagnostics)
gcloud compute instances stop media-lens-vm --zone=us-central1-a

# GCS operations
gsutil ls gs://media-lens-storage/
```

### Key File Locations

**On VM (`/app/working/out/`)**:
- Jobs: `jobs/YYYY/MM/DD/HHmmss/` (structured by date/time)
- Outputs: `intermediate/`, `staging/`
- Cursors: `format_cursor.txt`, `deploy_cursor.txt`
- Logs: via `docker logs media-lens`

**In GCS (`gs://media-lens-storage/`)**:
- Mirrors `/app/working/out/jobs/` structure
- Historical backups and archives

### Workflow

1. **Check VM Lifecycle State**
   - Is VM running or stopped?
   - If stopped (normal): Offer to start it for diagnostics (with cost warning)
   - If running: Check how long and why (scheduled run, stuck, user-initiated)
   - Note: After diagnostics, remind user to stop VM to avoid unnecessary costs

2. **Quick Status Check** (if VM is running or started)
   - Container health (docker ps, HTTP health check)
   - Last job timestamp on persistent disk
   - Format/deploy cursor values (indicates pipeline progress)

3. **Deep Dive (if issues found)**
   - SSH to VM and inspect working directory
   - Check docker logs for errors and timestamps
   - Examine failed step (harvest, extract, interpret, format, deploy)
   - Verify network connectivity and permissions
   - Check Cloud Scheduler and cron job configuration

4. **Root Cause Analysis**
   - Compare timestamps (job run vs cursor update vs deployment)
   - Check for stalled processes or zombie containers
   - Validate SFTP credentials and network access
   - Verify Cloud Scheduler jobs and cron settings

5. **Remediation**
   - Restart container if stuck
   - Reset cursors to reprocess dates
   - Manually trigger job via API (only if VM is running)
   - Review startup script for configuration issues
   - Check Cloud Scheduler job schedule/history

6. **Cleanup (Critical)**
   - After diagnostics complete: `gcloud compute instances stop media-lens-vm --zone=us-central1-a`
   - Confirm VM is STOPPED before closing
   - Document any findings for follow-up investigation

## Integration Points

### With Project Documentation
- CLAUDE.md: Deployment architecture and setup
- readme-deployment.md: Detailed GCP deployment guide
- startup-script.sh: Automated VM initialization

### With Application
- Web API: POST `/run`, GET `/status`, GET `/health`
- CLI: `python -m src.media_lens.runner` commands
- Environment: `.env` file or Secret Manager (GCP)

### With GCP
- Compute Engine: VM instances, disks, networking
- Cloud Storage: gs://media-lens-storage bucket
- Cloud Scheduler: Daily job triggers
- Cloud Logging: Centralized log aggregation (optional)

## Error Patterns & Solutions

| Pattern | Likely Cause | Debug Steps |
|---------|--------------|-------------|
| No jobs since date X | Cloud Scheduler disabled, cron misconfigured, startup script failed | Start VM (if stopped), check scheduler jobs + cron, review startup logs |
| VM won't start | GCP quota issue, disk corruption, startup script error | Check GCP quotas, try manual restart, review `google-startup-scripts.service` logs |
| Container crashed | Out of memory, missing dependencies, unhandled exception | Start VM, SSH in, run `docker logs media-lens`, check disk space (`df -h`) |
| Jobs run but not deployed | Deploy step fails, SFTP connectivity, permissions | Check `deploy_cursor` age vs last job, search logs for "upload\|deploy" errors |
| Partial output (few sites) | Scraping failures, Cloudflare blocks, API quota | Check harvest logs for specific site errors, verify rate limits |
| Cannot SSH to VM when running | Network security groups, VM not actually running | Verify VM status, check firewall rules, wait for startup to complete |
| VM is stopped (expected state) | Not an error - normal behavior | Only start if needed for diagnostics; **remember to stop it after** |

## Output Format

This skill provides:
- **Quick Summary**: Current VM status, last job time, any obvious issues
- **Detailed Findings**: Specific errors, timestamps, file states
- **Recommended Actions**: Exact commands to run or next investigation steps
- **Links to Docs**: References to CLAUDE.md, readme-deployment.md sections

## Limitations & Guardrails

This skill **does**:
- Start VM only with explicit user request (offers, doesn't auto-start)
- Always warn before starting VM (cost implications)
- Always ask before stopping VM
- Provide diagnostic commands for user to run manually
- Inspect logs and files (read-only)

This skill **does not**:
- Auto-start/stop VM without explicit user confirmation
- Modify code or configuration files
- Delete, archive, or modify data without explicit confirmation
- Make architectural changes or permanent fixes
- Troubleshoot code-level bugs (only deployment/operational issues)
- Keep VMs running after diagnostics (user responsibility to stop)

**Cost Warning**: Starting the VM enables billing for Compute Engine. Always stop when diagnostics are complete.

For application logic issues, refer to code review and testing workflows.

## Example Invocations

```
"Debug the media-lens GCP deployment - tell me why there are no results for Monday"

"Check if the VM is running and what state the container is in"

"I want to know the full timeline: when did each step last run, what's in storage, any errors?"

"media-lens production is broken, help me figure out what went wrong"

"Manually trigger a test run and show me the output"
```

---

**Version**: 1.0
**Last Updated**: 2026-03-25
**Skill Type**: Diagnostic / Operational Support
**Domain**: Media Lens GCP Infrastructure
