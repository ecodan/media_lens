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

# Clean up any __pycache__ files before rebuild
find . -type d -name "__pycache__" -exec rm -rf {} +

# Rebuild and start the container
echo "Building and starting new container..."
docker compose up --build -d

# Wait for container to initialize
echo "Waiting for container to initialize..."
sleep 10

# Run the service
echo "Starting media lens service..."
curl -X POST http://localhost:8080/run \
  -H "Content-Type: application/json" \
  -d '{"steps": ["harvest"]}'

echo "Container restarted successfully"
