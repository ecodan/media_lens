#!/bin/bash
set -e

STARTUP_VERSION="1.5.2"

# Log all commands for debugging
exec > >(tee -a /var/log/startup-script.log) 2>&1
echo "Starting startup script at $(date) version: ${STARTUP_VERSION}"

# Install Docker if not installed
if ! command -v docker &> /dev/null; then
    echo "Docker not found, installing..."
    apt-get update
    apt-get install -y apt-transport-https ca-certificates curl gnupg lsb-release
    curl -fsSL https://download.docker.com/linux/debian/gpg | gpg --dearmor -o /usr/share/keyrings/docker-archive-keyring.gpg
    echo "deb [arch=amd64 signed-by=/usr/share/keyrings/docker-archive-keyring.gpg] https://download.docker.com/linux/debian $(lsb_release -cs) stable" | tee /etc/apt/sources.list.d/docker.list > /dev/null
    apt-get update
    apt-get install -y docker-ce docker-ce-cli containerd.io
    systemctl enable docker
    systemctl start docker
    echo "Docker installed successfully"
fi

# Install Docker Compose if not installed
if ! command -v docker-compose &> /dev/null; then
    echo "Docker Compose not found, installing..."
    # Install Docker Compose standalone binary (more reliable across distributions)
    COMPOSE_VERSION=$(curl -s https://api.github.com/repos/docker/compose/releases/latest | grep 'tag_name' | cut -d\" -f4)
    echo "Installing Docker Compose version ${COMPOSE_VERSION}..."
    curl -L "https://github.com/docker/compose/releases/download/${COMPOSE_VERSION}/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
    chmod +x /usr/local/bin/docker-compose
    echo "Docker Compose installed successfully"
fi

# Make sure Docker is running
systemctl status docker || systemctl start docker
echo "Docker status: $(systemctl is-active docker)"

# Clone the latest code from repository
echo "Cloning the latest code..."
GIT_REPO_URL=${GIT_REPO_URL:-"https://github.com/ecodan/media_lens.git"}
GIT_BRANCH=${GIT_BRANCH:-"master"}

# Create app directory if it doesn't exist
mkdir -p /app
cd /app

# Clear app directory of any previous content except directories we want to preserve
echo "Cleaning app directory..."
find /app -mindepth 1 -maxdepth 1 -not -path "/app/.playwright" -not -path "/app/keys" -not -path "/app/working" -exec rm -rf {} \;

# Clone the repository
echo "Cloning from $GIT_REPO_URL branch $GIT_BRANCH"
git clone -b "$GIT_BRANCH" "$GIT_REPO_URL" /tmp/media-lens || {
  echo "Git clone failed. Check if repository and branch exist and are accessible."
  exit 1
}

# Move repository contents to app directory
echo "Moving repository contents to /app"
cp -r /tmp/media-lens/* /app/
cp -r /tmp/media-lens/.* /app/ 2>/dev/null || true

# Clean up the temporary repository
rm -rf /tmp/media-lens

# Make sure all required directories exist
mkdir -p /app/working/out
mkdir -p /app/keys

echo "Setting up Docker container..."
# Stop any existing containers
docker-compose down 2>/dev/null || true

# Retrieve ANTHROPIC_API_KEY from Secret Manager if not already set
if [ -z "${ANTHROPIC_API_KEY}" ]; then
    echo "ANTHROPIC_API_KEY not found in environment, retrieving from Secret Manager..."
    # Get the Google Cloud project ID from metadata server if not already set
    if [ -z "${GOOGLE_CLOUD_PROJECT}" ]; then
        GOOGLE_CLOUD_PROJECT=$(curl -s "http://metadata.google.internal/computeMetadata/v1/project/project-id" -H "Metadata-Flavor: Google")
    fi
    
    # Check if gcloud is installed
    if command -v gcloud &> /dev/null; then
        # Use the VM's service account to access the secret
        ANTHROPIC_API_KEY=$(gcloud secrets versions access latest --secret="anthropic-api-key" --project="${GOOGLE_CLOUD_PROJECT:-medialens}")
        if [ -z "${ANTHROPIC_API_KEY}" ]; then
            echo "WARNING: Failed to retrieve ANTHROPIC_API_KEY from Secret Manager"
        else
            echo "Successfully retrieved ANTHROPIC_API_KEY from Secret Manager"
        fi
    else
        echo "WARNING: gcloud not installed, cannot retrieve ANTHROPIC_API_KEY from Secret Manager"
    fi
fi

# Create .env file for docker-compose with cloud-specific settings
cat > /app/.env << EOF
GIT_REPO_URL=${GIT_REPO_URL:-"https://github.com/ecodan/media_lens.git"}
GIT_BRANCH=${GIT_BRANCH:-"master"}
GOOGLE_CLOUD_PROJECT=${GOOGLE_CLOUD_PROJECT:-medialens}
GCP_STORAGE_BUCKET=${GCP_STORAGE_BUCKET:-media-lens-storage}
USE_CLOUD_STORAGE=true
USE_WORKLOAD_IDENTITY=true
ANTHROPIC_API_KEY=${ANTHROPIC_API_KEY}
EOF

# Run docker-compose with the cloud profile to start only necessary services
echo "Starting services with docker-compose using cloud profile..."
cd /app
export WORKING_DIR="/app/working"
# Start only the app service explicitly to avoid dependency issues
docker-compose --profile cloud up -d app

# Check if app container started
container_name=$(docker-compose ps -q app 2>/dev/null)

# Check if container started
if [ -n "$container_name" ] && docker ps | grep -q "$container_name"; then
  echo "Container started successfully at $(date)"
else
  echo "Container failed to start. Docker compose logs:" 
  docker-compose logs || echo "No logs available"
  exit 1
fi

echo "Startup script completed at $(date)"