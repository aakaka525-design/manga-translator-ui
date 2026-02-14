#!/usr/bin/env bash
set -euo pipefail

# Usage:
# PROJECT_ID=xxx REGION=asia-east1 SERVICE_NAME=mt-compute IMAGE=gcr.io/xxx/mt-compute:latest \
# INTERNAL_TOKEN=xxx GEMINI_API_KEY_SECRET=gemini-api-key ./deploy/cloudrun/deploy-compute.sh

: "${PROJECT_ID:?PROJECT_ID is required}"
: "${REGION:?REGION is required}"
: "${SERVICE_NAME:?SERVICE_NAME is required}"
: "${IMAGE:?IMAGE is required}"
: "${INTERNAL_TOKEN:?INTERNAL_TOKEN is required}"
: "${GEMINI_API_KEY_SECRET:?GEMINI_API_KEY_SECRET is required}"
GEMINI_API_KEY_SECRET_VERSION="${GEMINI_API_KEY_SECRET_VERSION:-latest}"

gcloud run deploy "${SERVICE_NAME}" \
  --project "${PROJECT_ID}" \
  --region "${REGION}" \
  --image "${IMAGE}" \
  --platform managed \
  --no-allow-unauthenticated \
  --gpu 1 \
  --gpu-type nvidia-l4 \
  --no-gpu-zonal-redundancy \
  --cpu 4 \
  --memory 16Gi \
  --concurrency 1 \
  --timeout 900 \
  --max-instances 1 \
  --no-cpu-throttling \
  --set-env-vars "MANGA_INTERNAL_API_TOKEN=${INTERNAL_TOKEN},MANGA_TRANSLATE_EXECUTION_BACKEND=local,MANGA_CLOUDRUN_COMPUTE_ONLY=1,MT_USE_GPU=true,MANGA_REQUIRE_GPU=1,GEMINI_MODEL=gemini-3-flash-preview,GEMINI_FALLBACK_MODEL=gemini-2.5-flash" \
  --set-secrets "GEMINI_API_KEY=${GEMINI_API_KEY_SECRET}:${GEMINI_API_KEY_SECRET_VERSION}"

echo "Cloud Run compute service deployed: ${SERVICE_NAME}"
