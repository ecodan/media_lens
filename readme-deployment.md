# Media Lens Deployment Guide

This document provides step-by-step instructions for deploying the Media Lens application both locally using Docker and to Google Cloud.

## Local Docker Deployment

### Prerequisites
- Docker and Docker Compose installed on your machine
- Python 3.9+ (for local development outside Docker)
- API keys for required services (Anthropic)

### Steps for Local Deployment

1. **Clone the repository**
   ```bash
   git clone <repository-url>
   cd media_lens
   ```

2. **Create a local environment file**
   Create a `.env` file in the project root with the following variables:
   ```
   ANTHROPIC_API_KEY=your_anthropic_api_key
   USE_CLOUD_STORAGE=false
   # Add any other local-specific environment variables here
   ```

3. **Build and run the Docker container**
   ```bash
   docker compose up --build

    # Alternatively, if you want to run in detached mode:
   docker compose up -d --build
   ```

4. **Test the application**
   The application should now be running in Docker. You can trigger operations using the available scripts:
   ```bash
   # Example: Run the harvesting process
   docker exec -it media_lens-app-1 python src/media_lens/runner.py run --steps harvest -o /working/out
   
   # Example: run all steps for one site
   docker exec -it media_lens-app-1 python src/media_lens/runner.py run --steps harvest extract summarize_daily interpret_weekly format deploy -o /working/out --sites www.bbc.com
   ```

5. **View the results**
   Output files will be stored in the `working` directory which is mounted as a volume in the Docker container.
   ```bash
   # Check the output directory
   docker exec -it media_lens-app-1 ls -la /app/working/out
   
   # Copy files from the container to your local machine
   docker cp media_lens_app:/app/working/out /path/to/local/directory
   ```

6. **Stop the container**
   ```bash
   docker compose down
   ```

## Google Cloud VM Deployment

Due to the complexity of Playwright and its browser dependencies, Media Lens is deployed on a Google Cloud VM instead of Cloud Run for production use.

### Prerequisites
- Google Cloud account with billing enabled
- Google Cloud SDK installed locally
- Service account with appropriate permissions
- Project ID and other GCP resources set up

### First-Time Deployment
0. Create a VM disk image with base dependencies:
  **Create a VM to build your base image**
```bash
  gcloud compute instances create base-image-builder \
    --machine-type=e2-medium \
    --zone=us-central1-a \
    --image-family=debian-12 \
    --image-project=debian-cloud
 ```
  **SSH into the VM**
  ```bash
  gcloud compute ssh base-image-builder
  ```
  **Inside the VM, install Docker**
 ```bash
  sudo apt-get update
  sudo apt-get install -y docker.io git
 ```

  **Create a directory for your app**
 ```bash
  mkdir -p /home/$(whoami)/media-lens
```
  **Copy your Dockerfile (base version without application code)**
 ```bash
  # Create the Dockerfile in the VM
  # NOTE: THIS MAY BE OBSOLETE AS THE DOCKERFILE CONTAINS THE SRC
  cat > /home/$(whoami)/media-lens/Dockerfile << 'EOF'
  FROM python:3.12-slim
  
  #Install system dependencies for Playwright and git
  RUN apt-get update && apt-get install -y \
      fonts-liberation \
      libasound2 \
      libatk-bridge2.0-0 \
      libatk1.0-0 \
      libatspi2.0-0 \
      libcups2 \
      libdbus-1-3 \
      libdrm2 \
      libgbm1 \
      libgtk-3-0 \
      libnspr4 \
      libnss3 \
      libwayland-client0 \
      libxcomposite1 \
      libxdamage1 \
      libxfixes3 \
      libxkbcommon0 \
      libxrandr2 \
      xdg-utils \
      curl \
      libx11-6 \
      libx11-xcb1 \
      libpangocairo-1.0-0 \
      libxss1 \
      git \
      --no-install-recommends \
      && rm -rf /var/lib/apt/lists/*

  WORKDIR /app

  # Copy requirements and install dependencies
  COPY requirements.txt .
  RUN pip install --no-cache-dir --root-user-action=ignore -r requirements.txt

  # Install Playwright browsers with system dependencies
  ENV PLAYWRIGHT_BROWSERS_PATH=/app/.playwright/browsers
  RUN python -m playwright install --with-deps chromium

  # Create directories
  RUN mkdir -p /app/working/out
  RUN mkdir -p /app/keys

  # Set environment variables
  ENV PYTHONPATH=/app
  ENV USE_CLOUD_STORAGE=true

  # Expose the port
  EXPOSE 8080
  EOF
```

  **Create requirements.txt**
  **Copy your requirements.txt to the VM**

  **Build the base image**
 ```bash   
  cd /home/$(whoami)/media-lens
  sudo docker build -t media-lens-base .
  ```

  **Create a snapshot of the VM disk**
 ```bash
  sudo shutdown -h now
 ```

  **Create a disk image after VM shuts down**
 ```bash
  gcloud compute images create media-lens-base-image \
    --source-disk=base-image-builder \
    --source-disk-zone=us-central1-a \
    --family=media-lens
 ```

  **Delete the base image VM**
 ```bash
  gcloud compute instances delete base-image-builder --zone=us-central1-a
 ```

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
     --oauth-service-account-email=458497915682-compute@developer.gserviceaccount.com
   
   # Schedule VM to stop after jobs complete
   gcloud scheduler jobs create http stop-media-lens-vm \
     --schedule="0 9 * * *" \
     --uri="https://compute.googleapis.com/compute/v1/projects/medialens/zones/us-central1-a/instances/media-lens-vm/stop" \
     --http-method=POST \
     --oauth-service-account-email=458497915682-compute@developer.gserviceaccount.com
   
   # Schedule application runs (HTTP trigger to the app running on the VM)
   gcloud scheduler jobs create http daily-media-lens-run \
     --schedule="0 7 * * *" \
     --uri="http://EXTERNAL_IP:8080/run" \
     --http-method=POST \
     --message-body='{"steps":["harvest","extract","summarize_daily","interpret_weekly","format"]}' \
     --headers="Content-Type=application/json"
   
   # Weekly processing (Sunday)
   gcloud scheduler jobs create http weekly-media-lens-processing \
     --schedule="0 6 * * 0" \
     --uri="http://EXTERNAL_IP:8080/weekly" \
     --http-method=POST \
     --message-body='{"current_week_only":true}' \
     --headers="Content-Type=application/json"
   ```
   Replace `EXTERNAL_IP` with your VM's external IP address.

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