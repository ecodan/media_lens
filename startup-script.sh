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
mkdir -p /app/keys
cd /app

# Ensure the keys directory exists and has proper permissions
echo "Setting up credentials directory..."
chmod 700 /app/keys

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

# Check if we need to rebuild the Docker image
CURRENT_HASH=$(git rev-parse HEAD)
# Use a more reliable way to get the user directory for VM environments
if [ -n "$SUDO_USER" ]; then
    USER_HOME="/home/$SUDO_USER"
elif [ -n "$USER" ]; then
    USER_HOME="/home/$USER"
else
    USER_HOME="/root"
fi
PERSISTENT_DIR="$USER_HOME/media-lens"
LAST_BUILD_HASH_FILE="$PERSISTENT_DIR/.last_build_hash"

# Ensure the persistent directory exists
mkdir -p "$PERSISTENT_DIR"


# ANTHROPIC_API_KEY and other secrets are now loaded by the Python application at startup
# This provides more reliable error handling and eliminates VM startup issues

# Check for service account JSON files in the keys directory
SERVICE_ACCOUNT_FILE=$(ls -1 /app/keys/*.json 2>/dev/null | head -1)
if [ -n "$SERVICE_ACCOUNT_FILE" ]; then
    echo "Found service account file: $SERVICE_ACCOUNT_FILE"
    export GOOGLE_APPLICATION_CREDENTIALS="$SERVICE_ACCOUNT_FILE"
    export USE_WORKLOAD_IDENTITY=false
else 
    echo "No service account JSON files found in /app/keys. Falling back to workload identity."
    export USE_WORKLOAD_IDENTITY=true
    export GOOGLE_APPLICATION_CREDENTIALS=""
fi

# Export variables for docker-compose and create .env file
export GIT_REPO_URL=${GIT_REPO_URL:-"https://github.com/ecodan/media_lens.git"}
export GIT_BRANCH=${GIT_BRANCH:-"master"}
export GOOGLE_CLOUD_PROJECT=${GOOGLE_CLOUD_PROJECT:-medialens}
export GCP_STORAGE_BUCKET=${GCP_STORAGE_BUCKET:-media-lens-storage}
export USE_CLOUD_STORAGE=true

# AI Provider Configuration
export AI_PROVIDER=${AI_PROVIDER:-vertex}
export VERTEX_AI_PROJECT_ID=${GOOGLE_CLOUD_PROJECT:-medialens}
export VERTEX_AI_LOCATION=${VERTEX_AI_LOCATION:-us-central1}
export VERTEX_AI_MODEL=${VERTEX_AI_MODEL:-gemini-2.5-flash}

# Storage and Browser Configuration
export LOCAL_STORAGE_PATH=${LOCAL_STORAGE_PATH:-/app/working/out}
export PLAYWRIGHT_MODE=${PLAYWRIGHT_MODE:-cloud}

# FTP secrets and other credentials are now loaded by the Python application at startup
# Set default FTP SSH key file path (physical file still needs to be available)
export FTP_SSH_KEY_FILE="/app/keys/siteground"

# Create .env file for docker-compose with cloud-specific settings
# Secrets are now loaded by the Python application, so we only set configuration values
{
    printf "GIT_REPO_URL=\"%s\"\n" "$GIT_REPO_URL"
    printf "GIT_BRANCH=\"%s\"\n" "$GIT_BRANCH"
    printf "GOOGLE_CLOUD_PROJECT=\"%s\"\n" "$GOOGLE_CLOUD_PROJECT"
    printf "GCP_STORAGE_BUCKET=\"%s\"\n" "$GCP_STORAGE_BUCKET"
    printf "USE_CLOUD_STORAGE=\"%s\"\n" "$USE_CLOUD_STORAGE"
    printf "USE_WORKLOAD_IDENTITY=\"%s\"\n" "$USE_WORKLOAD_IDENTITY"
    printf "GOOGLE_APPLICATION_CREDENTIALS=\"%s\"\n" "$GOOGLE_APPLICATION_CREDENTIALS"
    printf "FTP_SSH_KEY_FILE=\"%s\"\n" "$FTP_SSH_KEY_FILE"
    printf "AI_PROVIDER=\"%s\"\n" "$AI_PROVIDER"
    printf "VERTEX_AI_PROJECT_ID=\"%s\"\n" "$GOOGLE_CLOUD_PROJECT"
    printf "VERTEX_AI_LOCATION=\"%s\"\n" "$VERTEX_AI_LOCATION"
    printf "VERTEX_AI_MODEL=\"%s\"\n" "$VERTEX_AI_MODEL"
    printf "LOCAL_STORAGE_PATH=\"%s\"\n" "$LOCAL_STORAGE_PATH"
    printf "PLAYWRIGHT_MODE=\"%s\"\n" "$PLAYWRIGHT_MODE"
    printf "USE_SECRET_MANAGER=\"%s\"\n" "true"
} > /app/.env

# Merge FTP credentials from .env.ftp if it exists
FTP_ENV_FILE="/home/dan/media-lens/.env.ftp"
if [ -f "$FTP_ENV_FILE" ]; then
    echo "Found FTP credentials file, merging with main .env..."
    
    # Read each line from .env.ftp and append to main .env if variable doesn't already exist
    while IFS= read -r line || [ -n "$line" ]; do
        # Skip empty lines and comments
        if [[ -n "$line" && ! "$line" =~ ^[[:space:]]*# ]]; then
            # Extract variable name (everything before the first =)
            var_name=$(echo "$line" | cut -d'=' -f1)
            
            # Check if this variable already exists in .env
            if ! grep -q "^${var_name}=" /app/.env; then
                echo "Adding FTP variable: $var_name"
                echo "$line" >> /app/.env
                # Also export to current environment so docker-compose can use it
                export "$line"
            else
                echo "Variable $var_name already exists in .env, skipping"
            fi
        fi
    done < "$FTP_ENV_FILE"
    
    echo "FTP credentials merged successfully"
else
    echo "No FTP credentials file found at $FTP_ENV_FILE"
fi

# Check if the current code has changed since the last build
if [ -f "$LAST_BUILD_HASH_FILE" ]; then
    LAST_BUILD_HASH=$(cat "$LAST_BUILD_HASH_FILE")
else
    LAST_BUILD_HASH=""
fi

# Rebuild the Docker image if the code has changed
if [ "$CURRENT_HASH" != "$LAST_BUILD_HASH" ]; then
    echo "Code has changed (${LAST_BUILD_HASH} -> ${CURRENT_HASH}), rebuilding Docker image..."
    docker-compose build --no-cache app
    echo "$CURRENT_HASH" > "$LAST_BUILD_HASH_FILE"
    echo "Docker image rebuilt successfully"
else
    echo "No code changes detected, using existing Docker image"
fi

# Clean up Docker resources before starting
echo "Cleaning up old Docker resources..."
docker system prune -f --volumes 2>/dev/null || true

# Setup disk monitoring
echo "Setting up disk space monitoring..."
chmod +x /app/monitor-disk-space.sh
/app/monitor-disk-space.sh setup

# Run docker-compose with the cloud profile to start only necessary services
echo "Starting services with docker-compose using cloud profile..."
cd /app
export WORKING_DIR="/app/working"
# Use the container's persistent /app/keys directory
# Start only the app service explicitly to avoid dependency issues
docker-compose --profile cloud up -d app

# Check if app container started
container_name=$(docker-compose ps -q app 2>/dev/null)

# Create the cron job script
echo "Creating cron job script..."
cat > /usr/local/bin/run-container-job.sh << 'EOF'
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
EOF

chmod +x /usr/local/bin/run-container-job.sh
echo "Cron job script created successfully"

# Set up the cron job (runs daily at 7 AM PT / 4 PM UTC)
echo "Setting up cron job..."
(crontab -l 2>/dev/null | grep -v '/usr/local/bin/run-container-job.sh'; echo "0 16 * * * /usr/local/bin/run-container-job.sh") | crontab -
echo "Cron job configured successfully"

# Final disk space check
echo "Final disk usage check:"
/app/monitor-disk-space.sh status

echo "Startup script completed at $(date)"