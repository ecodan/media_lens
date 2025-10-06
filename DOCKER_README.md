# Docker Configuration Guide

This project has two Docker configurations optimized for different environments:

## 1. Local Development (Mac ARM64)

For local testing on Apple Silicon Macs.

### Files
- `Dockerfile.local` - ARM64-optimized Dockerfile
- `docker-compose.local.yml` - Local override configuration

### Usage
```bash
# Build and run locally
docker compose -f docker-compose.yml -f docker-compose.local.yml --profile local up --build

# Run in background
docker compose -f docker-compose.yml -f docker-compose.local.yml --profile local up -d

# View logs
docker logs -f media-lens-local

# Stop
docker compose -f docker-compose.yml -f docker-compose.local.yml --profile local down
```

### Environment
- Platform: `linux/arm64`
- Storage: Local filesystem (`./working`, `./logs`)
- Secrets: Loaded from `.env` file
- AI Provider: Vertex AI (Gemini)
- Playwright Mode: `local`

## 2. Google Cloud Deployment (x86_64 Linux)

For production deployment on Google Cloud Run or VM.

### Files
- `Dockerfile` - x86_64-optimized Dockerfile
- `docker-compose.yml` - Cloud configuration

### Usage

#### Local Cloud Simulation
```bash
# Build for cloud (x86_64)
docker compose --profile cloud build

# Run cloud configuration locally
docker compose --profile cloud up
```

#### Deploy to Google Cloud
```bash
# Build and push to Google Container Registry
gcloud builds submit --tag gcr.io/medialens/media-lens

# Deploy to Cloud Run (or update VM)
gcloud run deploy media-lens \
  --image gcr.io/medialens/media-lens \
  --platform managed \
  --region us-central1 \
  --memory 4Gi \
  --timeout 600s
```

### Environment
- Platform: `linux/amd64` (x86_64)
- Storage: Google Cloud Storage
- Secrets: Google Secret Manager
- AI Provider: Vertex AI (Gemini)
- Playwright Mode: `cloud`

## Key Differences

| Feature | Local (ARM64) | Cloud (x86_64) |
|---------|--------------|----------------|
| Architecture | ARM64 | x86_64 |
| OS Libraries | Debian (ARM packages) | Debian (x86 packages) |
| Storage | Local filesystem | GCS |
| Secrets | .env file | Secret Manager |
| Playwright | Local mode | Cloud/headless mode |
| Use Case | Development/Testing | Production |

## Troubleshooting

### ARM64 Build Issues
If you see package errors on Mac:
- Ensure you're using `Dockerfile.local`
- Check Debian package names include `t64` suffix (e.g., `libasound2t64`)

### x86_64 Build Issues
If building cloud image on Mac ARM64:
- Use `docker buildx` for cross-platform builds
- Or build in cloud: `gcloud builds submit`

### Playwright Issues
- Local: Ensure `PLAYWRIGHT_MODE=local` in docker-compose.local.yml
- Cloud: Ensure all Chromium dependencies are installed in Dockerfile

## Testing Before Cloud Deployment

Always test locally first:
```bash
# 1. Test with local config
docker compose -f docker-compose.yml -f docker-compose.local.yml --profile local up --build

# 2. Run extraction test
docker exec media-lens-local python -m src.media_lens.runner run -s extract

# 3. Check logs
docker logs media-lens-local

# 4. If successful, deploy to cloud
gcloud builds submit --tag gcr.io/medialens/media-lens
```
