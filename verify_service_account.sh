#!/bin/bash
set -e

echo "Verifying VM service account and permissions..."

# Check if running on a GCP VM
if curl -s -f -H "Metadata-Flavor: Google" http://metadata.google.internal/computeMetadata/v1/instance > /dev/null 2>&1; then
  echo "✅ Running on a GCP VM."
else
  echo "❌ Not running on a GCP VM. Workload identity will not work."
  exit 1
fi

# Get the VM's service account
SERVICE_ACCOUNT=$(curl -s -H "Metadata-Flavor: Google" http://metadata.google.internal/computeMetadata/v1/instance/service-accounts/default/email)
echo "📄 VM service account: $SERVICE_ACCOUNT"

# Check if gcloud is available
if command -v gcloud > /dev/null; then
  # Check VM service account permissions on the storage bucket
  echo "📄 Checking permissions on storage bucket..."
  BUCKET_NAME=${GCP_STORAGE_BUCKET:-media-lens-storage}
  
  echo "Testing access to bucket: $BUCKET_NAME"
  if gsutil ls -b gs://$BUCKET_NAME > /dev/null 2>&1; then
    echo "✅ VM service account has access to bucket gs://$BUCKET_NAME"
  else
    echo "❌ VM service account cannot access bucket gs://$BUCKET_NAME"
    echo "Run this command to grant permissions:"
    echo "gsutil iam ch serviceAccount:$SERVICE_ACCOUNT:roles/storage.objectAdmin gs://$BUCKET_NAME"
  fi
else
  echo "⚠️ gcloud not available, skipping permission check."
fi

# Check credential paths
echo "📄 Checking credential paths..."
for path in /var/run/secrets/cloud.google.com /var/google-cloud/auth /etc/google/auth; do
  if [ -d "$path" ]; then
    echo "✅ Found credential path: $path"
    ls -la $path
  else
    echo "❌ Credential path not found: $path"
  fi
done

# Check if application default credentials exist
echo "📄 Checking for application default credentials..."
if [ -f "$HOME/.config/gcloud/application_default_credentials.json" ]; then
  echo "✅ Found application default credentials at $HOME/.config/gcloud/application_default_credentials.json"
else
  echo "⚠️ No application default credentials found in user home."
fi

echo "📄 All checks complete!"