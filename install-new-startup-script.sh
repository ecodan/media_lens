#!/bin/bash
set -e

# Script to install/update the startup script on the Google Cloud VM
# This script uploads the local startup-script.sh to the VM and configures it to run on startup

echo "Uploading startup script to VM metadata..."
gcloud compute instances add-metadata media-lens-vm \
    --zone=us-central1-a \
    --project=medialens \
    --metadata-from-file startup-script=startup-script.sh
echo "Startup script installed successfully!"
