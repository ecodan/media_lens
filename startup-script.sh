#!/bin/bash
set -e

# Install Docker if not installed
if ! command -v docker &> /dev/null; then
  echo "Installing Docker..."
  # Update apt and install required packages
  sudo apt-get update
  sudo apt-get install -y ca-certificates curl gnupg

  # Add Docker's official GPG key
  sudo install -m 0755 -d /etc/apt/keyrings
  curl -fsSL https://download.docker.com/linux/debian/gpg | sudo gpg --dearmor -o /etc/apt/keyrings/docker.gpg
  sudo chmod a+r /etc/apt/keyrings/docker.gpg

  # Add the repository to apt sources
  echo \
    "deb [arch="$(dpkg --print-architecture)" signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/debian \
    "$(. /etc/os-release && echo "$VERSION_CODENAME")" stable" | \
    sudo tee /etc/apt/sources.list.d/docker.list > /dev/null

  # Install Docker
  sudo apt-get update
  sudo apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin

  # Add current user to docker group (to run docker without sudo)
  # Fixed: added username parameter
  USER=$(whoami)
  sudo usermod -aG docker $USER
  echo "Docker installed successfully"

  # Need to refresh group membership for current session
  # Using a safer approach that doesn't terminate script execution
  sudo -u $USER -g docker bash -c "echo 'Group membership updated for docker'"
fi

# Install Docker Compose if not installed
if ! command -v docker compose &> /dev/null; then
  echo "Installing Docker Compose..."
  sudo curl -L "https://github.com/docker/compose/releases/download/v2.24.6/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
  sudo chmod +x /usr/local/bin/docker-compose
  sudo ln -s /usr/local/bin/docker-compose /usr/bin/docker-compose
  echo "Docker Compose installed successfully"
fi

# Mount the persistent disk - using more robust detection
MOUNT_PATH="/media-lens-data"

# Find the disk device
echo "Looking for persistent disk..."
ROOT_DEVICE=$(mount | grep " / " | cut -d' ' -f1)
echo "Root device is $ROOT_DEVICE"

# List all disks
echo "Available disks:"
sudo lsblk

# Try to identify persistent disk (assume it's the one that's not mounted)
if [[ "$ROOT_DEVICE" == *"sdb"* ]]; then
  DISK_DEVICE="/dev/sda"
else
  DISK_DEVICE="/dev/sdb"
fi

echo "Using $DISK_DEVICE as persistent disk"

# Check if it's already mounted
if ! grep -q $DISK_DEVICE /etc/mtab; then
  echo "Mounting persistent disk from $DISK_DEVICE..."
  sudo mkdir -p $MOUNT_PATH

  # Check if it's formatted
  FORMATTED=$(sudo file -sL $DISK_DEVICE)
  echo "Disk format check: $FORMATTED"

  # Format disk if not already formatted
  if ! echo "$FORMATTED" | grep -q "ext4" && ! echo "$FORMATTED" | grep -q "XFS" && ! echo "$FORMATTED" | grep -q "filesystem"; then
    echo "Formatting disk..."
    sudo mkfs.ext4 -m 0 -F -E lazy_itable_init=0,lazy_journal_init=0,discard $DISK_DEVICE
  fi

  # Mount the disk
  sudo mount -o discard,defaults $DISK_DEVICE $MOUNT_PATH
  sudo chmod 777 $MOUNT_PATH
  echo "Disk mounted successfully at $MOUNT_PATH"
else
  echo "Disk is already mounted"
fi

# Make sure Docker daemon is running
if ! systemctl is-active --quiet docker; then
  echo "Docker service not running. Starting docker service..."
  sudo systemctl start docker
  sleep 5
fi

# Fix Docker permissions
sudo chmod 666 /var/run/docker.sock

# Create Docker volumes directory if it doesn't exist
mkdir -p $MOUNT_PATH/docker-volumes || echo "Could not create $MOUNT_PATH/docker-volumes"

# Pull latest MediaLens image or build from source
# Set HOME if not already set
HOME=${HOME:-/root}
cd $HOME
if [ ! -d "media_lens" ]; then
  echo "Cloning MediaLens repository..."
  # Install git if needed
  sudo apt-get install -y git
  git clone https://github.com/ecodan/media_lens media_lens
  cd media_lens
else
  cd media_lens
  git pull
fi

# Set up environment variables
cat > .env << EOL
ANTHROPIC_API_KEY=${ANTHROPIC_API_KEY}
GOOGLE_CLOUD_PROJECT=medialens
GOOGLE_APPLICATION_CREDENTIALS=/app/keys/${GOOGLE_APPLICATION_CREDENTIALS}
GCP_STORAGE_BUCKET=media-lens-storage
USE_CLOUD_STORAGE=true
FTP_HOSTNAME=${FTP_HOSTNAME:-localhost}
FTP_USERNAME=${FTP_USERNAME:-user}
FTP_KEY_PATH=${FTP_KEY_PATH:-/app/keys/id_ed25519}
FTP_REMOTE_PATH=${FTP_REMOTE_PATH:-/var/www/html}
EOL

# Set up service account key securely
mkdir -p keys
echo "Setting up service account authentication..."

# Option 1: Use workload identity federation (preferred for GCP)
if [ -z "${GOOGLE_APPLICATION_CREDENTIALS}" ]; then
  echo "No explicit credentials file specified, using workload identity"
  # Add an environment variable to indicate we're using workload identity
  echo "USE_WORKLOAD_IDENTITY=true" >> .env
  # The container will inherit the VM's service account permissions
  
# Option 2: Access the key from Secret Manager
else
  echo "Fetching service account key from Secret Manager..."
  KEY_NAME="medialens-sa-key"
  
  # Check if Secret Manager CLI is available
  if command -v gcloud > /dev/null; then
    gcloud secrets versions access latest --secret=${KEY_NAME} > keys/${GOOGLE_APPLICATION_CREDENTIALS} || \
    echo "Failed to fetch key from Secret Manager - check permissions or create the secret with:"
    echo "  cat YOUR_KEY_FILE | gcloud secrets create ${KEY_NAME} --data-file=- --replication-policy=automatic"
  else
    echo "gcloud command not available, please install Google Cloud SDK or manually add the key file"
    echo "Failed to set up credentials" 
  fi
fi

# Ensure the key file has proper permissions if it exists
if [ -f keys/${GOOGLE_APPLICATION_CREDENTIALS} ]; then
  chmod 600 keys/${GOOGLE_APPLICATION_CREDENTIALS}
fi

# Run the Docker container
echo "Starting Docker container..."
docker compose up --build -d || echo "Failed to start Docker container"

# Wait for container to initialize
sleep 30

# Trigger the MediaLens job via HTTP request
echo "Triggering MediaLens job..."
curl -X POST http://localhost:8080/run \
  -H "Content-Type: application/json" \
  -d '{"steps": ["harvest", "extract", "interpret", "deploy"]}' || echo "Failed to trigger job"

# Wait for job to complete (adjust timeout as needed based on your typical job duration)
echo "Waiting for job to complete..."
sleep 3600  # 1 hour timeout

# Shutdown the VM once job is complete
echo "Job completed, shutting down VM..."
sudo shutdown -h now
