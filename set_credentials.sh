#!/bin/bash
# Script to set up credentials for Media Lens application
# To be used on the VM

# Set environment variables for the credentials
export USE_WORKLOAD_IDENTITY=false

# Determine the name of the service account JSON file
CREDS_FILE=$(ls -1 /app/keys/*.json 2>/dev/null | head -1)

if [ -n "$CREDS_FILE" ]; then
  echo "Found credentials file: $CREDS_FILE"
  export GOOGLE_APPLICATION_CREDENTIALS="$CREDS_FILE"
else
  echo "No JSON credentials file found in /app/keys directory!"
  exit 1
fi

# Add any other environment variables needed here

# Output confirmation
echo "Environment variables set:"
echo "USE_WORKLOAD_IDENTITY=$USE_WORKLOAD_IDENTITY"
echo "GOOGLE_APPLICATION_CREDENTIALS=$GOOGLE_APPLICATION_CREDENTIALS"

# You can source this file in your VM startup scripts
# Example: source /path/to/set_credentials.sh