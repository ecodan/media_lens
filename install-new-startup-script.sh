#!/bin/bash
set -e

# Script to install/update the startup script on GCS for the MIG.
# The MIG instance template uses startup-script-url pointing to GCS,
# so updating GCS is all that's needed — the next VM boot will pick it up.

echo "Uploading startup script to GCS..."
gsutil cp startup-script.sh gs://media-lens-storage/startup-script.sh
echo "Startup script uploaded to gs://media-lens-storage/startup-script.sh"
echo "The MIG will use this script on next instance boot."
