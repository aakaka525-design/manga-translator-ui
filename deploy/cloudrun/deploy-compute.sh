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

# --- 部署后冒烟测试 ---
SERVICE_URL=$(gcloud run services describe "${SERVICE_NAME}" \
  --project "${PROJECT_ID}" --region "${REGION}" \
  --format='value(status.url)')

echo "Running smoke test against ${SERVICE_URL} ..."

# 1) 健康检查
HTTP_STATUS=$(curl -sS -o /dev/null -w '%{http_code}' "${SERVICE_URL}/")
if [ "${HTTP_STATUS}" != "200" ]; then
  echo "❌ Health check failed: HTTP ${HTTP_STATUS}"
  exit 1
fi
echo "✅ Health check passed (HTTP 200)"

# 2) 内部 token 鉴权验证（无 token 应返回 401/403）
HTTP_STATUS=$(curl -sS -o /dev/null -w '%{http_code}' -X POST "${SERVICE_URL}/internal/translate/page")
if [ "${HTTP_STATUS}" = "200" ]; then
  echo "❌ Token auth bypass detected: POST /internal/translate/page returned 200 without token"
  exit 1
fi
echo "✅ Token auth verified (no-token returns HTTP ${HTTP_STATUS})"

echo "🎉 Smoke test passed"
