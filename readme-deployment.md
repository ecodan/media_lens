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
   # After modifying requirements.txt
   docker compose -f docker-compose.yml -f docker-compose.local.yml --profile local up --build
   ```

   **When to rebuild vs restart:**
   | Change Type | Action | Time | Command |
   |-------------|--------|------|---------|
   | Python code in `src/` | Restart | ~2s | `docker compose ... restart app` |
   | Config files in `config/` | Restart | ~2s | `docker compose ... restart app` |
   | `requirements.txt` | Rebuild | ~60s | `docker compose ... up --build` |
   | Dockerfile changes | Rebuild | ~60s | `docker compose ... up --build` |
   | System dependencies | Rebuild | ~60s | `docker compose ... up --build` |

   **Note**: The cloud/production configuration does NOT mount source code as volumes, ensuring the container matches exactly what will be deployed.

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
     -d '{"steps": ["harvest", "extract", "interpret", "format"]}'
   
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

### Alternative: Direct CLI Usage in Container

If you prefer to run CLI commands directly instead of using the web API:

```bash
# Run CLI commands inside the container
docker exec -it media-lens python -m src.media_lens.runner run -s harvest --sites www.bbc.com

# Or access the container shell
docker exec -it media-lens /bin/bash
# Then run commands inside the container:
python -m src.media_lens.runner run -s harvest extract
```

### Troubleshooting Local Docker

- **Container fails to start**: Check `docker logs media-lens-local` (or `media-lens` for cloud) for error messages
- **API not responding**: Ensure the container is running and port 8080 is not blocked
- **Storage issues**: Verify the `working` directory is properly mounted
- **Browser/Playwright errors**: The container includes all necessary browser dependencies
- **ARM64 package errors on Mac**: Ensure you're using `docker-compose.local.yml` which uses `Dockerfile.local`
- **x86_64 errors**: If testing cloud config on Mac, you may need to enable Docker's x86_64 emulation
- **Build fails with package errors**: Check that Debian package names match your architecture (ARM64 packages may have `t64` suffix)

## Google Cloud VM Deployment

Due to the complexity of Playwright and its browser dependencies, Media Lens is deployed on a Google Cloud VM instead of Cloud Run for production use.

### Prerequisites
- Google Cloud account with billing enabled
- Google Cloud SDK installed locally
- Service account with appropriate permissions
- Project ID and other GCP resources set up

### First-Time Deployment

1. **Create GCP Resources**
   ```bash
   # Create a storage bucket
   gsutil mb -l us-central1 gs://media-lens-storage
   
   # Set appropriate IAM permissions on the bucket
   gsutil iam ch serviceAccount:458497915682-compute@developer.gserviceaccount.com:roles/storage.objectAdmin gs://media-lens-storage
   ```

2. **Create VM Instance with Persistent Storage**
   ```bash
   # List VM instances to check for existing instances
   gcloud compute instances list

   # Create a VM instance
   gcloud compute instances create media-lens-vm \
     --machine-type=e2-medium \
     --image-family=debian-11 \
     --image-project=debian-cloud \
     --boot-disk-size=20GB \
     --boot-disk-type=pd-standard \
     --scopes=storage-full,cloud-platform
   
   # Create persistent disk for storage
   gcloud compute disks create media-lens-data \
     --size=50GB \
     --type=pd-standard

   # Attach disk to VM
   gcloud compute instances attach-disk media-lens-vm \
     --disk=media-lens-data
   
   # Confirm disk attachment
   gcloud compute instances describe media-lens-vm --format="get(disks)"
   ```

3. **Configure Startup Script**
   The startup script automates most of the VM setup, including:
   - Mounting persistent disk
   - Installing Docker
   - Cloning the repository
   - Setting up environment variables
   - Building and running the application

   ```bash
   # Upload the startup script to the VM
   gcloud compute instances add-metadata media-lens-vm \
     --metadata-from-file startup-script=startup-script.sh
   
   # Set required environment variables for the startup script
   gcloud compute instances add-metadata media-lens-vm \
     --metadata=ANTHROPIC_API_KEY=your_anthropic_api_key,GIT_REPO_URL=https://github.com/your-username/media_lens.git,GIT_BRANCH=master
   ```

4. **First-Time Manual Setup (Required Once)**
   SSH into the VM to set up persistent disk:

   ```bash
   # Connect to VM
   gcloud compute ssh media-lens-vm
   
   # Format the persistent disk (only needed the first time)
   sudo mkfs.ext4 -m 0 -E lazy_itable_init=0,lazy_journal_init=0,discard /dev/sdb
   
   # Set up mount point
   sudo mkdir -p /app/working
   sudo mkdir -p /app/keys
   sudo mount -o discard,defaults /dev/sdb /app/working
   sudo chmod a+w /app/working
   
   # Add to fstab for persistence across reboots
   echo "/dev/sdb /app/working ext4 discard,defaults 0 2" | sudo tee -a /etc/fstab
   
   # Copy credentials to VM (if needed)
   # From local machine:
   gcloud compute scp ./keys/medialens-d479cf10632d.json media-lens-vm:/app/keys/
   
   # Restart the VM to apply the startup script
   gcloud compute instances stop media-lens-vm
   gcloud compute instances start media-lens-vm
   ```
   
4.5. **See what's going on (from inside the VM)**
   ```bash
   # Check the logs of the startup script
   sudo journalctl -u google-startup-scripts.service
   
   # list all containers
    docker ps -a
    # Check the logs of the media lens container
    docker logs media-lens 
    
   # Check if the application is running
   curl http://EXTERNAL_IP:8080/health
   ```


5. **Set Up Scheduled Jobs**
   Create Cloud Scheduler jobs to automatically start/stop the VM and trigger jobs:

   ```bash
   # Schedule VM to start daily before jobs
   gcloud scheduler jobs create http start-media-lens-vm \
     --schedule="0 6 * * *" \
     --uri="https://compute.googleapis.com/compute/v1/projects/medialens/zones/us-central1-a/instances/media-lens-vm/start" \
     --http-method=POST \
     --oauth-service-account-email=458497915682-compute@developer.gserviceaccount.com \
     --location="us-central1"
   
   # Schedule VM to stop after jobs complete
   gcloud scheduler jobs create http stop-media-lens-vm \
     --schedule="0 9 * * *" \
     --uri="https://compute.googleapis.com/compute/v1/projects/medialens/zones/us-central1-a/instances/media-lens-vm/stop" \
     --http-method=POST \
     --oauth-service-account-email=458497915682-compute@developer.gserviceaccount.com \
     --location="us-central1"
   ```

   **NOTE: the following should be set via the startup script, but listed here in case you want to do it manually**
   ```
   # Set up a cron job on the VM to trigger the application
   # SSH into the VM
   sudo crontab -e
   # Add the following line to run the application every day at 7 AM PT
   0 16 * * * /usr/local/bin/run-container-job.sh
   ```
   Create /usr/local/bin/run-container-job.sh in the VM  (not Docker image) with the following content:
   ```bash
   #!/bin/bash
   curl -X POST \
     -H "Content-Type: application/json" \
     -d '{
       "steps": [
         "harvest",
         "extract",
         "interpret_weekly",
         "format",
         "deploy"
       ]
     }' \
   http://0.0.0.0:8080/run
    ```
6. **Test the Deployment**
   ```bash
   # Check if the application is running
   curl http://EXTERNAL_IP:8080/health
   
   # Trigger a test run
   curl -X POST http://EXTERNAL_IP:8080/run \
     -H "Content-Type: application/json" \
     -d '{"steps":["harvest"]}'
   
   # SSH into VM to check logs and results
   gcloud compute ssh media-lens-vm
   docker logs media-lens
   ls -la /app/working/out
   ```

### Updating an Existing Deployment

1. **Update Repository and Restart**
   The startup script is configured to automatically pull the latest code on VM restart:

   ```bash
   # Restart the VM to pull latest code and restart container
   gcloud compute instances stop media-lens-vm
   gcloud compute instances start media-lens-vm
   ```

2. **Manual Update (Alternative)**
   SSH into the VM to manually update:

   ```bash
   # Connect to VM
   gcloud compute ssh media-lens-vm
   
   # Stop and remove existing container
   docker stop media-lens
   docker rm media-lens
   
   # Pull latest code
   cd /app
   git pull
   
   # Rebuild and restart
   sudo docker build -t gcr.io/medialens/media-lens .
   ```
   ALT
 ```bash
  cd /app
  sudo bash startup-script.sh
   ```
   

## About the Startup Script

The startup script (`startup-script.sh`) automatically sets up the VM environment and deploys the application on VM startup:

- Installs Docker if not present
- Clones the repository to `/app`
- Creates necessary directories
- Mounts the persistent disk
- Builds and runs the Docker container
- Sets up logging and monitoring

Key features of the startup script:

```bash
# The script:
# 1. Installs Docker if needed
# 2. Clones the repository
# 3. Sets up working directories
# 4. Builds and runs the Docker container
# 5. Configures all necessary environment variables
```

For full details, see the `startup-script.sh` file in the repository.

## Troubleshooting

### Common Issues with VM Deployment
- **VM not starting**: Check VM instance status in Google Cloud Console
- **Disk not mounting**: Check `dmesg` and ensure disk is properly attached
- **Docker container failures**: SSH into VM and check Docker logs with `docker logs media-lens`
- **Startup script issues**: Check startup script logs with `sudo journalctl -u google-startup-scripts.service`
- **Storage issues**: Ensure the persistent disk has enough space with `df -h`
- **Playwright errors**: Check if browser dependencies are installed in the Docker container

For more detailed troubleshooting, examine the logs in `/app/working/` and within the Docker container.