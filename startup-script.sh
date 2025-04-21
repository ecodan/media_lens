#!/bin/bash
set -e

# Log all commands for debugging
exec > >(tee -a /var/log/startup-script.log) 2>&1
echo "Starting startup script at $(date)"

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
# Stop any existing container
docker stop media-lens || true
docker rm media-lens || true

# Pull the base image (in case it's in a registry and not local)
echo "Pulling media-lens-base image..."
docker pull media-lens-base || echo "Image not in registry, using local image"

# Run the container
echo "Starting media-lens container..."
docker run -d \
  --name media-lens \
  -p 8080:8080 \
  --volume /app/working:/app/working \
  --volume /app/keys:/app/keys:ro \
  -e GIT_REPO_URL="${GIT_REPO_URL}" \
  -e GIT_BRANCH="${GIT_BRANCH}" \
  -e GOOGLE_CLOUD_PROJECT=medialens \
  -e GCP_STORAGE_BUCKET=media-lens-storage \
  -e USE_CLOUD_STORAGE=true \
  -e ANTHROPIC_API_KEY="${ANTHROPIC_API_KEY}" \
  media-lens-base \
  gunicorn --bind 0.0.0.0:8080 --workers 1 --timeout 600 --log-level info src.media_lens.cloud_entrypoint:app

# Check if container started
if docker ps | grep -q media-lens; then
  echo "Container started successfully at $(date)"
else
  echo "Container failed to start. Docker logs:" 
  docker logs media-lens || echo "No logs available"
  exit 1
fi

echo "Startup script completed at $(date)"