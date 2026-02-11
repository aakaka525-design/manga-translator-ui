#!/usr/bin/env bash
set -euo pipefail

# Usage:
# PROJECT_ID=xxx REGION=asia-east1 SERVICE_NAME=mt-compute IMAGE=gcr.io/xxx/mt-compute:latest \
# INTERNAL_TOKEN=xxx ./deploy/cloudrun/deploy-compute.sh

: "${PROJECT_ID:?PROJECT_ID is required}"
: "${REGION:?REGION is required}"
: "${SERVICE_NAME:?SERVICE_NAME is required}"
: "${IMAGE:?IMAGE is required}"
: "${INTERNAL_TOKEN:?INTERNAL_TOKEN is required}"

gcloud run deploy "${SERVICE_NAME}" \
  --project "${PROJECT_ID}" \
  --region "${REGION}" \
  --image "${IMAGE}" \
  --platform managed \
  --no-allow-unauthenticated \
  --cpu 4 \
  --memory 16Gi \
  --concurrency 1 \
  --timeout 3600 \
  --set-env-vars "MANGA_INTERNAL_API_TOKEN=${INTERNAL_TOKEN},MANGA_TRANSLATE_EXECUTION_BACKEND=local"

echo "Cloud Run compute service deployed: ${SERVICE_NAME}"
