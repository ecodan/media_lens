#!/bin/bash
# Script to restart the Media Lens container with latest code
set -e

# Stop any running containers
echo "Stopping running containers..."
docker compose down

# Remove any cached images to force complete rebuild
echo "Removing docker images..."
docker rmi $(docker images -q media_lens-app) || echo "No images to remove"

# Make sure keys directory exists and has proper permissions
echo "Checking keys directory..."
mkdir -p keys
chmod 755 keys

# Handle credentials securely
KEY_FILE="keys/medialens-d479cf10632d.json"

# Check if key file exists and is a directory (incorrect)
if [ -d "$KEY_FILE" ]; then
  echo "ERROR: Key file is a directory, removing..."
  rm -rf "$KEY_FILE"
fi

# Check if key file exists
if [ ! -f "$KEY_FILE" ]; then
  echo "WARNING: Service account key not found at $KEY_FILE"
  echo "Options:"
  echo "  1. Export GOOGLE_APPLICATION_CREDENTIALS with path to your key file"
  echo "  2. Copy your key file to $KEY_FILE"
  echo "  3. Set up workload identity (if running on GCP)"
  echo ""
  echo "Application will fall back to local storage if no credentials are provided"
fi

# Clean up any __pycache__ files before rebuild
sudo find . -type d -name "__pycache__" -exec rm -rf {} +

# Rebuild and start the container
echo "Building and starting new container..."
docker compose up --build -d

# Wait for container to initialize
echo "Waiting for container to initialize..."
sleep 10

# Run the service
echo "Starting media lens service..."
curl -X GET http://localhost:8080/health || echo "Failed to start service - check container logs"

echo "Container restarted successfully"
