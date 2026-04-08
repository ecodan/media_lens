# Media Lens Deployment Guide

This document provides step-by-step instructions for deploying the Media Lens application both locally using Docker and to Google Cloud.

## Local Docker Deployment

### Overview

Media Lens provides two Docker configurations:
- **Local (Mac ARM64)**: Optimized for Apple Silicon development - uses `Dockerfile.local`
- **Cloud (x86_64)**: Production configuration for Google Cloud - uses `Dockerfile`

See `DOCKER_README.md` for detailed configuration differences.

### Prerequisites
- Docker and Docker Compose installed on your machine
- Python 3.9+ (for local development outside Docker)
- UV package manager (for local development)
- API keys for required services (Anthropic Claude or Google Vertex AI)
- For Mac: Apple Silicon (M1/M2/M3) or Intel-based Mac

### Steps for Local Deployment

1. **Clone the repository**
   ```bash
   git clone <repository-url>
   cd media_lens
   ```

2. **Create a local environment file**
   Create a `.env` file in the project root with the following variables:
   ```bash
   # AI Provider (default: vertex)
   AI_PROVIDER=vertex

   # Google Vertex AI (recommended)
   GOOGLE_APPLICATION_CREDENTIALS=keys/your-service-account.json
   VERTEX_AI_PROJECT_ID=your-gcp-project-id
   VERTEX_AI_LOCATION=us-central1
   VERTEX_AI_MODEL=gemini-2.5-flash
   GOOGLE_CLOUD_PROJECT=your-gcp-project-id

   # Or use Anthropic Claude
   # AI_PROVIDER=claude
   # ANTHROPIC_API_KEY=your_anthropic_api_key_here

   # Local storage (required for Docker)
   USE_CLOUD_STORAGE=false
   LOCAL_STORAGE_PATH=/app/working/out
   PLAYWRIGHT_MODE=local

   # Google Cloud Storage (optional for local)
   GCP_STORAGE_BUCKET=media-lens-storage

   # FTP deployment (optional)
   FTP_HOSTNAME=
   FTP_USERNAME=
   FTP_KEY_PATH=
   FTP_PORT=
   FTP_PASSPHRASE=
   FTP_REMOTE_PATH=
   ```

3. **Build and run the Docker container**

   **For Mac (ARM64 - Apple Silicon):**
   ```bash
   # Build and run with local ARM64 configuration
   docker compose -f docker-compose.yml -f docker-compose.local.yml --profile local up --build

   # Or run in detached mode
   docker compose -f docker-compose.yml -f docker-compose.local.yml --profile local up -d

   # View logs
   docker logs -f media-lens-local
   ```

   **For Cloud Simulation (x86_64):**
   ```bash
   # Test cloud configuration locally (requires x86_64 or emulation)
   docker compose --profile cloud up --build
   ```

4. **Development Workflow (Fast Iteration)**

   The local configuration mounts your source code as volumes, enabling fast development without rebuilds:

   **For Python code changes** (no rebuild needed):
   ```bash
   # Edit your Python files in src/
   # Then simply restart the container
   docker compose -f docker-compose.yml -f docker-compose.local.yml --profile local restart app

   # Container restarts in ~2 seconds with your new code
   ```

   **For dependency changes** (rebuild required):
   ```bash
   # After modifying pyproject.toml or adding dependencies with uv add
   docker compose -f docker-compose.yml -f docker-compose.local.yml --profile local up --build
   ```

   **For direct development** (no Docker):
   ```bash
   # Install dependencies
   uv sync

   # Install pre-commit hooks
   uv run pre-commit install

   # Run application
   uv run python -m src.media_lens.runner run -s harvest extract

   # Run tests
   uv run pytest --cov=src/media_lens
   ```

   **When to rebuild vs restart:**
   | Change Type | Action | Time | Command |
   |-------------|--------|------|---------|
   | Python code in `src/` | Restart | ~2s | `docker compose ... restart app` |
   | Config files in `config/` | Restart | ~2s | `docker compose ... restart app` |
   | `pyproject.toml` | Rebuild | ~60s | `docker compose ... up --build` |
   | Dockerfile changes | Rebuild | ~60s | `docker compose ... up --build` |
   | System dependencies | Rebuild | ~60s | `docker compose ... up --build` |

   **Note**: The cloud/production configuration does NOT mount source code as volumes, ensuring the container matches exactly what will be deployed.

   For complete development setup details, see `UV_SETUP.md`.

5. **Test the application**
   The application runs a web server on port 8080. You can trigger operations using HTTP API calls:
   
   ```bash
   # Check if the application is running
   curl http://localhost:8080/health
   
   # View available endpoints
   curl http://localhost:8080/
   
   # Run a simple harvest for testing
   curl -X POST http://localhost:8080/run \
     -H "Content-Type: application/json" \
     -d '{"steps": ["harvest"], "sites": ["www.bbc.com"]}'
   
   # Run a full pipeline
   curl -X POST http://localhost:8080/run \
     -H "Content-Type: application/json" \
     -d '{"steps": ["harvest", "extract", "interpret_weekly", "format"]}'
   
   # Check run status
   curl http://localhost:8080/status
   ```

6. **View the results**
   Output files will be stored in the `working` directory which is mounted as a volume in the Docker container.
   ```bash
   # Check the output directory
   docker exec -it media-lens-local ls -la /app/working

   # View container logs
   docker logs media-lens-local

   # Access the container shell if needed
   docker exec -it media-lens-local /bin/bash
   ```

7. **Stop the container**
   ```bash
   # For local Mac ARM64
   docker compose -f docker-compose.yml -f docker-compose.local.yml --profile local down

   # For cloud simulation
   docker compose --profile cloud down
   ```

### Alternative: Direct CLI Usage

You can run CLI commands either inside Docker containers or directly on your machine:

**Inside the container:**
```bash
# Run CLI commands inside the container
docker exec -it media-lens-local python -m src.media_lens.runner run -s harvest --sites www.bbc.com

# Or access the container shell
docker exec -it media-lens-local /bin/bash
# Then run commands inside the container:
uv run python -m src.media_lens.runner run -s harvest extract
```

**Directly on your machine** (requires UV):
```bash
# Install dependencies and hooks
uv sync
uv run pre-commit install

# Run CLI commands
uv run python -m src.media_lens.runner run -s harvest extract
uv run pytest --cov=src/media_lens
```

### Troubleshooting Local Docker

- **Container fails to start**: Check `docker logs media-lens-local` (or `media-lens` for cloud) for error messages
- **API not responding**: Ensure the container is running and port 8080 is not blocked
- **Storage issues**: Verify the `working` directory is properly mounted
- **Browser/Playwright errors**: The container includes all necessary browser dependencies
- **ARM64 package errors on Mac**: Ensure you're using `docker-compose.local.yml` which uses `Dockerfile.local`
- **x86_64 errors**: If testing cloud config on Mac, you may need to enable Docker's x86_64 emulation
- **Build fails with package errors**: Check that Debian package names match your architecture (ARM64 packages may have `t64` suffix)

## Google Cloud MIG Deployment

Due to the complexity of Playwright and its browser dependencies, Media Lens is deployed on a Google Cloud Managed Instance Group (MIG) instead of Cloud Run for production use. The MIG boots an ephemeral VM daily, runs the pipeline, and terminates — all storage is in GCS.

### Key Resources
| Resource | Value |
|----------|-------|
| Project ID | `medialens` |
| Region | `us-west1` |
| MIG | `media-lens-mig` |
| Instance Template | `media-lens-template-v2` |
| GCS Bucket | `gs://media-lens-storage/` |
| Startup Script (GCS) | `gs://media-lens-storage/startup-script.sh` |
| Scheduler Region | `us-central1` |
| Start schedule | `0 15 * * *` (15:00 UTC / 7 AM PT) |
| Stop schedule | `0 18 * * *` (18:00 UTC / 10 AM PT) |
| Service Account | `458497915682-compute@developer.gserviceaccount.com` |

### Prerequisites
- Google Cloud account with billing enabled
- Google Cloud SDK installed locally
- Project `medialens` with billing and required APIs enabled

### First-Time Deployment

1. **Create GCP Resources**
   ```bash
   # Create storage bucket in us-west1
   gsutil mb -l us-west1 gs://media-lens-storage
   
   # Set IAM permissions on the bucket
   gsutil iam ch serviceAccount:458497915682-compute@developer.gserviceaccount.com:roles/storage.objectAdmin gs://media-lens-storage
   ```

2. **Upload Startup Script to GCS**
   The instance template fetches the startup script from GCS on each boot.
   ```bash
   gsutil cp startup-script.sh gs://media-lens-storage/startup-script.sh
   # Or use the helper script:
   bash install-new-startup-script.sh
   ```

3. **Create Instance Template**
   ```bash
   gcloud compute instance-templates create media-lens-template-v2 \
     --machine-type=e2-medium \
     --image-family=debian-12 \
     --image-project=debian-cloud \
     --boot-disk-size=20GB \
     --boot-disk-type=pd-standard \
     --scopes=cloud-platform \
     --metadata=startup-script-url=gs://media-lens-storage/startup-script.sh,\
GIT_REPO_URL=https://github.com/ecodan/media_lens.git,\
GIT_BRANCH=master,\
GOOGLE_CLOUD_PROJECT=medialens,\
GCP_STORAGE_BUCKET=media-lens-storage \
     --project=medialens
   ```

4. **Create Regional MIG**
   ```bash
   gcloud compute instance-groups managed create media-lens-mig \
     --template=media-lens-template-v2 \
     --size=0 \
     --region=us-west1 \
     --project=medialens
   ```

5. **Set Up Cloud Scheduler Jobs**
   ```bash
   # Scale MIG to 1 (start VM) daily
   gcloud scheduler jobs create http start-media-lens-vm \
     --schedule="0 15 * * *" \
     --uri="https://compute.googleapis.com/compute/v1/projects/medialens/regions/us-west1/instanceGroupManagers/media-lens-mig/resize?size=1" \
     --http-method=POST \
     --oauth-service-account-email=458497915682-compute@developer.gserviceaccount.com \
     --location="us-central1"
   
   # Scale MIG to 0 (terminate VM) after jobs
   gcloud scheduler jobs create http stop-media-lens-vm \
     --schedule="0 18 * * *" \
     --uri="https://compute.googleapis.com/compute/v1/projects/medialens/regions/us-west1/instanceGroupManagers/media-lens-mig/resize?size=0" \
     --http-method=POST \
     --oauth-service-account-email=458497915682-compute@developer.gserviceaccount.com \
     --location="us-central1"
   ```

6. **Verify Deployment**
   ```bash
   # Check MIG status
   gcloud compute instance-groups managed describe media-lens-mig \
     --region=us-west1 --project=medialens

   # Check scheduler jobs
   gcloud scheduler jobs list --location=us-central1 --project=medialens
   ```

### Updating an Existing Deployment

**Update startup script** (most common change):
```bash
# Upload updated script to GCS — MIG picks it up on next boot
bash install-new-startup-script.sh
```

**Force a fresh VM** (picks up latest code from git):
```bash
gcloud compute instance-groups managed resize media-lens-mig --size=0 --region=us-west1 --project=medialens
gcloud compute instance-groups managed resize media-lens-mig --size=1 --region=us-west1 --project=medialens
```

### Monitoring and Debugging

```bash
# Check MIG and running instances
gcloud compute instance-groups managed list-instances media-lens-mig \
  --region=us-west1 --project=medialens

# View logs (no SSH needed — use Cloud Logging)
gcloud logging read 'resource.type="gce_instance"' \
  --project=medialens --freshness=2d --limit=100 \
  --format="table(timestamp, jsonPayload.message)"

# SSH into a running instance (replace XXXX with actual instance suffix)
gcloud compute ssh media-lens-mig-XXXX --zone=us-west1-a --project=medialens

# Inside the VM:
docker logs media-lens
sudo tail -f /var/log/startup-script.log
sudo tail -f /var/log/run-container-job.log
```

### Manual Pipeline Trigger

```bash
# Scale up
gcloud compute instance-groups managed resize media-lens-mig --size=1 --region=us-west1 --project=medialens

# Wait ~5 min for boot, then SSH and trigger:
gcloud compute ssh media-lens-mig-XXXX --zone=us-west1-a --project=medialens \
  --command='curl -s -X POST http://0.0.0.0:8080/run -H "Content-Type: application/json" \
  -d "{\"steps\":[\"harvest\",\"extract\",\"interpret_weekly\",\"format\",\"deploy\"]}"'

# Scale back down when done
gcloud compute instance-groups managed resize media-lens-mig --size=0 --region=us-west1 --project=medialens
```

## About the Startup Script

The startup script (`startup-script.sh`) is stored in GCS and runs on every new MIG instance boot:

- Installs Docker
- Clones the repository to `/app`
- Installs and starts the `cron` daemon
- Builds and runs the Docker container via docker-compose (cloud profile)
- Sets up cron job to trigger the pipeline at 16:00 UTC daily
- Sets up disk space monitoring

To update: `bash install-new-startup-script.sh` — uploads to GCS, takes effect on next boot.

## Troubleshooting

### Common Issues with MIG Deployment
- **Pipeline never ran**: Check that `cron` daemon is running on the VM (`sudo systemctl status cron`); startup script installs it but check `/var/log/startup-script.log` for errors
- **MIG not scaling**: Check Cloud Scheduler job status (`gcloud scheduler jobs list --location=us-central1 --project=medialens`) and verify the resize URI is correct
- **Docker container failures**: SSH into instance and check `docker logs media-lens`
- **Startup script issues**: Check `/var/log/startup-script.log` on the VM
- **GCS access errors**: Verify the compute service account has `storage.objectAdmin` on the bucket
- **Playwright errors**: Check if browser dependencies are installed in the Docker container

For more detailed troubleshooting, examine Cloud Logging or SSH into the running instance.