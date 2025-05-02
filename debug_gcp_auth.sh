#!/bin/bash

# Run inside the container to debug GCP auth
# Usage: docker exec media-lens /bin/bash /app/debug_gcp_auth.sh

echo "Debugging GCP authentication..."

# Check environment variables
echo "Environment variables:"
echo "======================"
env | grep -E "GOOGLE|WORKLOAD|CLOUD|STORAGE" | sort

# Check credential paths
echo
echo "Credential paths:"
echo "================="
for path in /var/run/secrets/cloud.google.com /var/google-cloud/auth /etc/google/auth; do
  echo "Checking $path:"
  if [ -d "$path" ]; then
    ls -la $path
    find $path -type f | while read file; do
      echo "File: $file"
      head -n1 "$file" | grep -v "PRIVATE" || echo "[Contains private key data]"
    done
  else
    echo "Directory doesn't exist: $path"
  fi
  echo
done

# Try to authenticate using gcloud directly
echo "Testing authentication:"
echo "======================"
python3 -c "
from google.cloud import storage
from google.auth import default
import os

print('Python test:')
print('------------')
try:
    print('Getting default credentials...')
    credentials, project = default()
    print(f'Retrieved credentials type: {type(credentials).__name__}')
    print(f'Project from credentials: {project}')
    
    print('\nAttempting to create storage client...')
    client = storage.Client(project=os.environ.get('GOOGLE_CLOUD_PROJECT', 'medialens'))
    print(f'Client created: {client}')
    
    print('\nAttempting to list buckets...')
    buckets = list(client.list_buckets(max_results=1))
    print(f'Successfully listed buckets: {buckets}')
    
    print('\nAttempting to access specific bucket...')
    bucket_name = os.environ.get('GCP_STORAGE_BUCKET', 'media-lens-storage')
    bucket = client.bucket(bucket_name)
    print(f'Does bucket exist: {bucket.exists()}')
    
except Exception as e:
    print(f'Error: {type(e).__name__}: {str(e)}')
"

echo
echo "Debug complete"