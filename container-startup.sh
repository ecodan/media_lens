#!/bin/bash
set -e

echo "Starting media-lens container..."

# Create required directories
mkdir -p /app/working/out

# Make sure the Python path is set correctly
export PYTHONPATH=/app/src

# Check for GCP credentials
echo "Checking for GCP credentials..."

# Check if explicit credentials file is provided through env var
if [ -n "$GOOGLE_APPLICATION_CREDENTIALS" ] && [ -f "$GOOGLE_APPLICATION_CREDENTIALS" ]; then
    echo "Using credentials from: $GOOGLE_APPLICATION_CREDENTIALS"
    # For debugging only - don't log credentials in production
    echo "Credentials file exists and is readable"
elif [ "$USE_WORKLOAD_IDENTITY" = "true" ]; then
    echo "Workload identity enabled, checking VM credential paths"
    # Check common credential paths and create symlinks if needed
    for src_path in /var/run/secrets/cloud.google.com/*; do
        if [ -f "$src_path" ]; then
            echo "Found credential file: $src_path"
            # If it looks like a credentials file, create a known filename
            if grep -q "private_key" "$src_path" 2>/dev/null; then
                echo "Creating service-account.json symlink"
                ln -sf "$src_path" /var/run/secrets/cloud.google.com/service-account.json
            fi
        fi
    done
    
    # Export credential path if a file was found
    if [ -f "/var/run/secrets/cloud.google.com/service-account.json" ]; then
        echo "Setting GOOGLE_APPLICATION_CREDENTIALS to /var/run/secrets/cloud.google.com/service-account.json"
        export GOOGLE_APPLICATION_CREDENTIALS="/var/run/secrets/cloud.google.com/service-account.json"
    fi
else
    # Check if any JSON files exist in the /app/keys directory
    echo "Looking for credentials in /app/keys directory..."
    key_files=$(ls -1 /app/keys/*.json 2>/dev/null)
    if [ -n "$key_files" ]; then
        # Use the first JSON file found
        cred_file=$(echo "$key_files" | head -1)
        echo "Found credential file: $cred_file"
        export GOOGLE_APPLICATION_CREDENTIALS="$cred_file"
    else
        echo "WARNING: No credential files found in /app/keys directory"
    fi
fi

# Start the Flask application
echo "Starting application with GOOGLE_CLOUD_PROJECT=$GOOGLE_CLOUD_PROJECT"
exec gunicorn --bind 0.0.0.0:8080 --workers 1 --timeout 600 --log-level info media_lens.cloud_entrypoint:app