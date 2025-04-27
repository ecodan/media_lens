#!/bin/bash
set -e

echo "Starting media-lens container..."

# Create required directories
mkdir -p /app/working/out

# Make sure the Python path is set correctly
export PYTHONPATH=/app/src

# Start the Flask application
exec gunicorn --bind 0.0.0.0:8080 --workers 1 --timeout 600 --log-level info media_lens.cloud_entrypoint:app