# Media Lens Project Guidelines

## Overview
A Python-based tool for comparative analysis of media worldviews through automated headline and content analysis. Uses hybrid temporal analysis: rolling 7-day windows for current events, ISO week boundaries for historical tracking.

Live version: [Media Lens](https://www.dancripe.com/reports/medialens.html)

### Key Analysis Questions
The system analyzes media coverage to answer five core questions:
1. What is the most important news right now?
2. What are the biggest issues in the world right now?
3. How is the U.S. President performing based on media portrayal?
4. What three adjectives best describe the situation in the U.S.?
5. What three adjectives best describe the U.S. President's performance and character?

### Requirements
- Python 3.8+ (tested with Python 3.12)
- AI Provider API access:
  - **Anthropic Claude** (default) - requires API key
  - **Google Vertex AI** (optional) - requires GCP service account and project setup
- SFTP information for web server deployment (optional)

## Quick Start Commands

### Basic Execution
```bash
# Full daily workflow
python -m src.media_lens.runner run -s harvest extract interpret_weekly summarize_daily format deploy

# Local development with minimal browser restrictions
python -m src.media_lens.runner run -s harvest extract --playwright-mode local

# Scrape only (for later processing)
python -m src.media_lens.runner run -s harvest_scrape --sites www.bbc.com

# Process existing scraped content
python -m src.media_lens.runner run -s harvest_clean extract interpret -j jobs/2025/06/07/120000

# Incremental deployment (only new files)
python -m src.media_lens.runner run -s format deploy

# Force complete regeneration
python -m src.media_lens.runner run -s format deploy --force-full-format --force-full-deploy
```

### Development Commands
```bash
# Install dependencies
pip install -r requirements.txt

# Create virtual environment
python -m venv venv && source venv/bin/activate

# Run tests
pytest

# Audit directories
python -m src.media_lens.runner audit [--start-date YYYY-MM-DD] [--end-date YYYY-MM-DD]
```

### Docker Commands
```bash
# Local Mac ARM64 development
docker compose -f docker-compose.yml -f docker-compose.local.yml --profile local up --build
docker compose -f docker-compose.yml -f docker-compose.local.yml --profile local up -d  # background
docker logs -f media-lens-local  # view logs
docker compose -f docker-compose.yml -f docker-compose.local.yml --profile local down  # stop

# Cloud simulation (x86_64)
docker compose --profile cloud up --build

# Direct CLI in container
docker exec -it media-lens-local python -m src.media_lens.runner run -s harvest --sites www.bbc.com
```

## Code Style Guidelines
- **Imports**: Standard library first, third-party second, local imports last with full paths. Put ALL imports at the top of the file.
- **Types**: Use type annotations for all function params, return values, and variable declarations
- **Naming**: PascalCase for classes, snake_case for functions/variables, UPPER_SNAKE_CASE for constants
- **Documentation**: Google-style docstrings for classes and public functions
- **Error Handling**: Use specific exceptions, proper logging, and graceful recovery
- **Logging**: Use the common logger from `common.py` with appropriate log levels
- **Async**: Use async/await pattern for I/O-bound operations
- **Path handling**: Use pathlib.Path objects instead of string concatenation
- **Environment**: Load from .env file, never hardcode credentials

## Project Structure
- **Collection**: Content scraping and cleaning
- **Extraction**: Headline and article content isolation, summarization and interpretation
- **Presentation**: HTML output generation and SFTP deployment
- Use dependency injection for extensibility
- Each component should have a single responsibility
- Storage: File system-based (database-ready architecture)

## Incremental Processing (Cursor Mechanism)
The format and deploy steps now support incremental processing using cursor files to track the last processed timestamp:

### Cursor Files
- **Format Cursor** (`format_cursor.txt`): Tracks last processed job timestamp for HTML generation
- **Deploy Cursor** (`deploy_cursor.txt`): Tracks last deployed file timestamp

### Cursor Behavior
- **Format Step**: Only regenerates HTML for weeks with new job directories since cursor
- **Deploy Step**: Only uploads files modified since cursor timestamp
- **No Cursor**: First run processes all content (full generation/deployment)
- **No New Content**: Skips processing if no changes since cursor

### Cursor Management Commands
```bash
# Reset both cursors (forces full regeneration/deployment)
python -m src.media_lens.runner reset-cursor

# Reset specific cursors
python -m src.media_lens.runner reset-cursor --format
python -m src.media_lens.runner reset-cursor --deploy
python -m src.media_lens.runner reset-cursor --all

# Force full processing (ignore cursors for single run)
python -m src.media_lens.runner run -s format --force-full-format
python -m src.media_lens.runner run -s deploy --force-full-deploy
python -m src.media_lens.runner run -s format deploy --force-full-format --force-full-deploy
```

## Workflow Steps
The media lens pipeline supports granular control over each stage:

### Available Steps
- **`harvest`**: Complete workflow (sequential scrape → clean)
- **`harvest_scrape`**: Scraping only - downloads raw HTML from websites
- **`harvest_clean`**: Cleaning only - processes scraped content into articles
- **`re-harvest`**: Re-harvest existing content
- **`extract`**: Extract structured data from cleaned content
- **`interpret`**: Generate AI interpretations for individual runs
- **`interpret_weekly`**: Generate weekly AI interpretations (uses hybrid approach: rolling 7-day for current week, ISO boundaries for historical weeks)
- **`summarize_daily`**: Create daily summaries
- **`format`**: Generate HTML output files
- **`deploy`**: Deploy files to SFTP remote server

### Step Validation Rules
- ❌ `harvest + harvest_scrape` (conflicting - harvest includes scraping)
- ❌ `harvest + harvest_clean` (conflicting - harvest includes cleaning)
- ❌ `harvest_scrape + harvest_clean` (redundant - use harvest instead)
- ✅ Individual steps work alone
- ✅ Sequential workflow: `harvest_scrape` then `harvest_clean`

### Common CLI Options
```bash
# Override default sites
python -m src.media_lens.runner run -s harvest --sites www.bbc.com www.cnn.com

# Process specific job directory
python -m src.media_lens.runner run -s extract interpret -j jobs/2025/06/07/120000

# Process date range
python -m src.media_lens.runner run -s format --start-date 2025-01-01 --end-date 2025-01-31

# Rewind cursors before running
python -m src.media_lens.runner run -s format deploy --rewind-days 7

# Assign custom run ID for tracking
python -m src.media_lens.runner run -s harvest --run-id my-custom-run
```

### Additional CLI Commands

**Summarization**:
```bash
# Summarize all days
python -m src.media_lens.runner summarize

# Force re-summarization
python -m src.media_lens.runner summarize --force
```

**Weekly Reinterpretation**:
```bash
# Reinterpret weekly content from specific date
python -m src.media_lens.runner reinterpret-weeks --date 2025-01-01

# Don't overwrite existing interpretations
python -m src.media_lens.runner reinterpret-weeks --date 2025-01-01 --no-overwrite

# Note: Current week uses rolling 7-day analysis, historical weeks use ISO boundaries
```

**Stop Running Process**:
```bash
# Stop current run
python -m src.media_lens.runner stop
```

## Environment Configuration

### Browser Configuration
- **Playwright Mode**: Use `--playwright-mode` or set `PLAYWRIGHT_MODE` environment variable
  - `local`: Minimal browser restrictions for local development (macOS/Linux laptops)
  - `cloud`: Container-optimized browser settings for cloud/Docker deployment (default)
- **Environment Variable**: `export PLAYWRIGHT_MODE=local` for persistent local development

### AI Provider Configuration
```bash
# Choose provider (default: vertex)
export AI_PROVIDER=claude  # Options: "claude", "vertex"

# Anthropic Claude
export ANTHROPIC_API_KEY=your-anthropic-api-key

# Google Vertex AI
export GOOGLE_APPLICATION_CREDENTIALS=path/to/service-account-key.json
export VERTEX_AI_PROJECT_ID=your-gcp-project-id
export VERTEX_AI_LOCATION=us-central1
export VERTEX_AI_MODEL=gemini-2.5-flash
```

### Storage Configuration
```bash
# Google Cloud Storage
export GOOGLE_CLOUD_PROJECT=your-gcp-project-id
export GCP_STORAGE_BUCKET=your-storage-bucket-name
export USE_CLOUD_STORAGE=false  # true for cloud, false for local

# Local Storage
export LOCAL_STORAGE_PATH=/path/to/your/working/directory

# SFTP Deployment
export FTP_REMOTE_PATH=/path/to/remote/directory
```

## Web API Endpoints

The application includes a Flask web server (port 8080) for HTTP-based control:

### Starting the Web Server
```bash
# Local development
python -m src.media_lens.cloud_entrypoint

# Docker (preferred for local testing)
docker compose -f docker-compose.yml -f docker-compose.local.yml --profile local up --build
```

### API Endpoints

**Pipeline Execution**:
```bash
# Start pipeline run
curl -X POST http://localhost:8080/run \
  -H "Content-Type: application/json" \
  -d '{"steps": ["harvest", "extract", "interpret", "format", "deploy"]}'

# Run with custom sites
curl -X POST http://localhost:8080/run \
  -H "Content-Type: application/json" \
  -d '{"steps": ["harvest"], "sites": ["www.bbc.com", "www.cnn.com"]}'

# Run with cursor rewind
curl -X POST http://localhost:8080/run \
  -H "Content-Type: application/json" \
  -d '{"steps": ["format", "deploy"], "rewind_days": 7}'

# Run with custom run ID
curl -X POST http://localhost:8080/run \
  -H "Content-Type: application/json" \
  -d '{"steps": ["harvest"], "run_id": "my-custom-run"}'
```

**Weekly Processing**:
```bash
# Process current week (rolling 7-day)
curl -X POST http://localhost:8080/weekly \
  -H "Content-Type: application/json" \
  -d '{"current_week_only": true}'

# Process specific historical weeks (ISO boundaries)
curl -X POST http://localhost:8080/weekly \
  -H "Content-Type: application/json" \
  -d '{"specific_weeks": ["2025-W08", "2025-W09"], "overwrite": true}'

# Force ISO boundaries for current week
curl -X POST http://localhost:8080/weekly \
  -H "Content-Type: application/json" \
  -d '{"current_week_only": true, "use_rolling_for_current": false}'
```

**Summarization**:
```bash
# Run daily summarization
curl -X POST http://localhost:8080/summarize \
  -H "Content-Type: application/json" \
  -d '{"force": false}'

# Force re-summarization
curl -X POST http://localhost:8080/summarize \
  -H "Content-Type: application/json" \
  -d '{"force": true}'
```

**Status and Control**:
```bash
# Check overall status
curl http://localhost:8080/status

# Check specific run status
curl http://localhost:8080/status?run_id=your-run-id

# Stop a running process
curl -X POST http://localhost:8080/stop/your-run-id

# Health check
curl http://localhost:8080/health

# Application info
curl http://localhost:8080/
```

## Deployment Architecture
- **Deployment Type**: Google Cloud VM (not Cloud Run) due to Playwright browser dependencies
- Application runs as a scheduled job via cron, not a long-running service
- Workers timeout: 600 seconds for long-running tasks
- VM auto-starts daily before jobs, auto-stops after completion
- Web server runs on port 8080 for HTTP-based job triggering

## Google Cloud VM Deployment

### Initial Setup

1. **Create GCP Resources**:
   ```bash
   # Create storage bucket
   gsutil mb -l us-central1 gs://media-lens-storage

   # Set IAM permissions
   gsutil iam ch serviceAccount:458497915682-compute@developer.gserviceaccount.com:roles/storage.objectAdmin gs://media-lens-storage
   ```

2. **Create VM Instance with Persistent Storage**:
   ```bash
   # List existing instances
   gcloud compute instances list

   # Create VM instance
   gcloud compute instances create media-lens-vm \
     --machine-type=e2-medium \
     --image-family=debian-11 \
     --image-project=debian-cloud \
     --boot-disk-size=20GB \
     --boot-disk-type=pd-standard \
     --scopes=storage-full,cloud-platform

   # Create and attach persistent disk
   gcloud compute disks create media-lens-data --size=50GB --type=pd-standard
   gcloud compute instances attach-disk media-lens-vm --disk=media-lens-data

   # Confirm attachment
   gcloud compute instances describe media-lens-vm --format="get(disks)"
   ```

3. **Configure Startup Script**:
   ```bash
   # Upload startup script
   gcloud compute instances add-metadata media-lens-vm \
     --metadata-from-file startup-script=startup-script.sh

   # Set environment variables
   gcloud compute instances add-metadata media-lens-vm \
     --metadata=ANTHROPIC_API_KEY=your_key,GIT_REPO_URL=https://github.com/your-user/media_lens.git,GIT_BRANCH=master
   ```

4. **First-Time Manual Setup**:
   ```bash
   # SSH into VM
   gcloud compute ssh media-lens-vm

   # Format persistent disk (first time only)
   sudo mkfs.ext4 -m 0 -E lazy_itable_init=0,lazy_journal_init=0,discard /dev/sdb

   # Mount disk
   sudo mkdir -p /app/working /app/keys
   sudo mount -o discard,defaults /dev/sdb /app/working
   sudo chmod a+w /app/working

   # Add to fstab for persistence
   echo "/dev/sdb /app/working ext4 discard,defaults 0 2" | sudo tee -a /etc/fstab

   # Copy credentials (from local machine)
   gcloud compute scp ./keys/medialens-*.json media-lens-vm:/app/keys/

   # Restart to apply startup script
   exit
   gcloud compute instances stop media-lens-vm
   gcloud compute instances start media-lens-vm
   ```

5. **Monitor Deployment**:
   ```bash
   # SSH back in to check status
   gcloud compute ssh media-lens-vm

   # Check startup script logs
   sudo journalctl -u google-startup-scripts.service

   # List containers
   docker ps -a

   # Check container logs
   docker logs media-lens

   # Test health endpoint
   curl http://localhost:8080/health
   ```

6. **Set Up Scheduled Jobs**:
   ```bash
   # VM auto-start before daily job
   gcloud scheduler jobs create http start-media-lens-vm \
     --schedule="0 6 * * *" \
     --uri="https://compute.googleapis.com/compute/v1/projects/medialens/zones/us-central1-a/instances/media-lens-vm/start" \
     --http-method=POST \
     --oauth-service-account-email=458497915682-compute@developer.gserviceaccount.com \
     --location="us-central1"

   # VM auto-stop after job completes
   gcloud scheduler jobs create http stop-media-lens-vm \
     --schedule="0 9 * * *" \
     --uri="https://compute.googleapis.com/compute/v1/projects/medialens/zones/us-central1-a/instances/media-lens-vm/stop" \
     --http-method=POST \
     --oauth-service-account-email=458497915682-compute@developer.gserviceaccount.com \
     --location="us-central1"
   ```

   **Cron Job Setup** (via startup script or manual):
   ```bash
   # SSH into VM and edit crontab
   sudo crontab -e
   # Add: 0 16 * * * /usr/local/bin/run-container-job.sh

   # Create job script at /usr/local/bin/run-container-job.sh:
   #!/bin/bash
   curl -X POST -H "Content-Type: application/json" \
     -d '{"steps":["harvest","extract","interpret_weekly","format","deploy"]}' \
     http://0.0.0.0:8080/run
   ```

### Updating Deployment

**Automatic Update (Recommended)**:
```bash
# Restart VM to pull latest code via startup script
gcloud compute instances stop media-lens-vm
gcloud compute instances start media-lens-vm
```

**Manual Update**:
```bash
# SSH into VM
gcloud compute ssh media-lens-vm

# Stop and remove container
docker stop media-lens && docker rm media-lens

# Pull latest code
cd /app && git pull

# Rebuild and restart
sudo docker build -t gcr.io/medialens/media-lens .

# Or run startup script
cd /app && sudo bash startup-script.sh
```

### Testing and Debugging

```bash
# Health check (from outside VM)
curl http://EXTERNAL_IP:8080/health

# Trigger manual run
curl -X POST http://EXTERNAL_IP:8080/run \
  -H "Content-Type: application/json" \
  -d '{"steps":["harvest"]}'

# Check status
curl http://EXTERNAL_IP:8080/status

# SSH and check logs
gcloud compute ssh media-lens-vm
docker logs media-lens
ls -la /app/working/out
```

## Docker Configuration

### Container Name
- VM container: `media-lens`
- Local Mac container: `media-lens-local`

### Docker Profiles
- **Local (ARM64)**: For Mac Apple Silicon development
  ```bash
  docker compose -f docker-compose.yml -f docker-compose.local.yml --profile local up --build
  ```
- **Cloud (x86_64)**: For production VM deployment
  ```bash
  docker compose --profile cloud up --build
  ```

### Key Differences
| Feature | Local (ARM64) | Cloud (x86_64) |
|---------|--------------|----------------|
| Architecture | ARM64 | x86_64 |
| Dockerfile | `Dockerfile.local` | `Dockerfile` |
| Storage | Local filesystem | GCS |
| Secrets | .env file | Secret Manager |
| Playwright Mode | local | cloud |

See `DOCKER_README.md` for detailed configuration differences.
- Always use UV for python package management and launch if it's a UV project