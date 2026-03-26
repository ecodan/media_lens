# Media Lens GCP Debug Skill - Draft Review

## Overview
This skill enables systematic debugging and diagnostics of media-lens production issues running on Google Cloud Platform (GCP). It provides structured approaches to investigating VM status, container health, job execution, storage, and scheduling.

**Key Context**: The media-lens infrastructure is designed for cost efficiency:
- VM auto-starts at 6:00 AM UTC via Cloud Scheduler
- Pipeline runs for ~1-2 hours
- VM auto-stops at 9:00 AM UTC
- **Rest of day**: VM is STOPPED (normal state, saves ~$150/month vs continuous running)

When debugging, the skill safely manages VM lifecycle—offering to start it for diagnostics and ensuring shutdown afterward to prevent unnecessary charges.

## What This Skill Does

### Primary Purpose
When media-lens production reports issues (missing results, stalled jobs, deployment failures), this skill provides:
1. **Lifecycle awareness** - Understands the scheduled VM lifecycle (stopped most of day, runs at 6 AM UTC)
2. **Safe VM access** - Offers to start VM for diagnostics, ensures shutdown after to avoid costs
3. **Quick status checks** - Is the VM running? Is the container healthy? When did the last job run?
4. **Root cause analysis** - Systematic investigation of logs, files, timestamps, and configuration
5. **Remediation guidance** - Exact commands and steps to resolve common issues

### Scope
- **Operational diagnosis only** - no code fixes, no architectural changes
- **GCP infrastructure** - VM lifecycle, Cloud Storage, Cloud Scheduler, Docker containers
- **Deployment workflows** - job execution, cursor tracking, output generation, SFTP deployment
- **Observable state** - logs, file timestamps, process status, network connectivity
- **Cost-aware VM management** - Safe start/stop operations with warnings and cleanup

### Not In Scope
- Auto-starting/stopping VM without explicit user request
- Code-level debugging (logic errors, bugs in extraction/interpretation)
- Architecture redesign or infrastructure changes
- Permanent fixes (only temporary troubleshooting)
- Data recovery or backups beyond what's observable

## Usage Pattern

**User says**: "Media lens isn't showing Monday or Wednesday results"

**Skill does**:
1. Check if GCP VM is running
2. Get last job timestamp and compare to expected date
3. Check if format step generated HTML
4. Check if deploy step uploaded files
5. Inspect container logs for errors
6. Report findings and recommend next steps

**Output**: "Last job was March 23. Format_cursor shows March 23. No March 24 or 25 jobs found. Scheduler jobs are listed as [X, Y, Z]. Cron should fire at 4 PM UTC. Check: [exact command] to verify."

## Implementation Status

### ✅ Complete
- SKILL.md with full capability matrix
- emergence-config.json with metadata
- Trigger definitions and example invocations
- Error patterns and solutions table
- Integration points documented

### ⏳ Pending (Post-Kickoff)
- Skill validation (`validate_skill.py`)
- GCP command implementation (exact bash/gcloud calls)
- Test invocations against real GCP environment
- Performance tuning (log tailing, query efficiency)

## Knowledge Base Integrated

This skill synthesizes knowledge from:
- **CLAUDE.md** - Deployment architecture, GCP resources, file locations
- **readme-deployment.md** - Step-by-step GCP setup, troubleshooting section
- **startup-script.sh** - VM initialization, container orchestration
- **Project observations** - Actual cursor files, job structure, error patterns

## Triggers (When to Use)

Auto-activate when:
- "debug gcp"
- "check gcp status"
- "media lens isn't running"
- "why didn't the job run"
- "investigate production"
- "production is broken"
- Or any user query about missing/broken media lens output

## Example Investigation Flow

**User Report**: "Results missing for Monday (March 24)"

**Skill Execution**:
```
Step 0: Check VM Lifecycle
  gcloud compute instances describe media-lens-vm --zone=us-central1-a --format="get(status)"
  → Status: STOPPED (normal state for 2:30 PM UTC) ✓

  OFFER: "The VM is stopped (expected state). Would you like me to start it to
  investigate? Note: Starting will incur Compute Engine charges until we stop it."
  USER: "Yes, start it"

  gcloud compute instances start media-lens-vm --zone=us-central1-a
  → VM starting... (wait ~30 seconds)

Step 1: Verify VM Started
  gcloud compute instances describe media-lens-vm --zone=us-central1-a --format="get(status)"
  → Status: RUNNING ✓

Step 2: Check container
  gcloud compute ssh media-lens-vm --zone=us-central1-a --command="docker ps"
  → Container: media-lens (running) ✓

Step 3: Check last job
  gcloud compute ssh ... --command="ls -la /app/working/out/jobs/2026/03/"
  → Found: 23/ only. Missing: 24/, 25/ ✗

Step 4: Check cursors
  ... --command="cat /app/working/out/format_cursor.txt"
  → 2026-03-23T16:00:00+00:00 ✓ (matches job)
  ... --command="cat /app/working/out/deploy_cursor.txt"
  → 2025-05-22T18:07:33.937850+00:00 ✗ (very old!)

Step 5: Check logs
  gcloud compute ssh ... --command="docker logs media-lens --tail=100 | grep -i error"
  → [Show any errors from March 23-24]

Step 6: Check scheduler
  gcloud scheduler jobs list --location=us-central1
  → [List jobs, show last execution times]

Step 7: Findings & Recommendations
  "No jobs ran on March 24+. VM started successfully, container is healthy, but format step
   succeeded on March 23 and deploy step hasn't run since May. Likely issues:
   1. Cloud Scheduler job disabled or not configured
   2. Cron job on VM not running
   3. HTTP API not being triggered

   Recommended next steps:
   - Run: gcloud scheduler jobs list
   - Check: sudo crontab -l on VM
   - Test: curl -X POST http://<EXTERNAL_IP>:8080/run ..."

Step 8: Cleanup (CRITICAL)
  REMINDER: "Investigation complete. The VM is currently running and will incur charges.
  Stopping the VM now..."

  gcloud compute instances stop media-lens-vm --zone=us-central1-a
  → VM stopping...

  gcloud compute instances describe media-lens-vm --zone=us-central1-a --format="get(status)"
  → Status: STOPPED ✓
```

**Result**: User gets exact debugging path + specific commands + safe VM lifecycle management.

## Prerequisites

- `gcloud` CLI installed and authenticated to `medialens` project
- SSH access to `media-lens-vm`
- Valid .ssh key for SFTP/SSH authentication
- `gsutil` for bucket inspection (optional)

## Next Steps

1. **Review**: Check if SKILL.md triggers and capabilities match your needs
2. **Approve**: Confirm scope and implementation approach
3. **Kickoff**: Run `python {cicadas-dir}/scripts/kickoff.py skill-media-lens-gcp-debug --intent "GCP production diagnostics"`
4. **Create Branch**: `git checkout -b skill/media-lens-gcp-debug`
5. **Implement**: Add actual gcloud/bash commands to function the skill
6. **Validate**: Run `validate_skill.py` to check spec compliance
7. **Test**: Test with real media-lens GCP instance
8. **Publish**: Publish to `.claude/skills/` for use with Claude Code

## Questions for Clarification

Before proceeding, consider:
1. ✅ **VM Lifecycle**: Skill should ALWAYS ask before starting VM and warn about costs - confirmed
2. ✅ **Shutdown Behavior**: Skill should ensure VM is stopped after diagnostics - confirmed
3. Should the skill auto-remediate (e.g., restart container) or always ask first?
4. Should it access Cloud Logging or stick to container logs?
5. Should it include performance profiling (container resource usage)?
6. Should it support other GCP projects besides "medialens"?
7. Should it integrate with incident tracking (Slack notifications, etc.)?
8. Should the 6 AM UTC / 9 AM UTC schedule be configurable, or hardcoded for now?

---

**Status**: ✅ Draft Ready for Review
**Created**: 2026-03-25
**Estimated Implementation Time**: 1-2 hours (once approved)
