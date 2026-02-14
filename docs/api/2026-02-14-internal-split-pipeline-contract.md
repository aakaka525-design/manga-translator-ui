# Internal Split Pipeline Contract (2026-02-14)

## Endpoints

1. `POST /internal/translate/detect`
2. `POST /internal/translate/render`
3. Fallback: `POST /internal/translate/page`

## Detect Request

- Content-Type: `multipart/form-data`
- Fields:
  - `image` (required)
  - `source_language` (optional)
  - `target_language` (optional)
- Header:
  - `X-Internal-Token` (required when server configured)

## Detect Response

```json
{
  "task_id": "string",
  "ttl_seconds": 300,
  "image_hash": "sha256:...",
  "regions_count": 16,
  "regions": [
    {
      "region_index": 0,
      "text": "..."
    }
  ],
  "from_lang": "JPN",
  "elapsed_ms": {
    "detect": 123.4,
    "ocr": null,
    "total": 123.4,
    "mode": "aggregated_detect_ocr"
  }
}
```

说明:
- `region_index` 为连续整数 `0..n-1`，作为 render 回写锚点。
- `regions_count=0` 仍返回 `200`。
- `elapsed_ms` 当前为聚合口径：`detect` 与 `total` 表示 detect+ocr 总耗时，`ocr` 为 `null`。

## Render Request

- Content-Type: `application/json`

```json
{
  "task_id": "string",
  "image_hash": "sha256:...",
  "translated_regions": [
    {
      "region_index": 0,
      "translation": "译文"
    }
  ],
  "primary_model": "gemini-3-flash-preview",
  "fallback_model": "gemini-2.5-flash",
  "selected_model": "gemini-3-flash-preview",
  "fallback_reason": "optional",
  "translation_text": "optional"
}
```

## Render Error State Machine

优先级固定（命中即返回，不继续下探）：

1. `401 UNAUTHORIZED`
2. `503 NOT_READY`
3. `404 CACHE_MISS`
4. `410 TASK_EXPIRED`
5. `422 IMAGE_HASH_MISMATCH`
6. `400 RENDER_INPUT_INVALID`

## Render Success Response

- Content-Type: `application/octet-stream`
- Headers:
  - `x-pipeline-mode: split|unified|fallback_to_unified`
  - `x-stage-elapsed-ms`
  - `x-regions-count`
  - `x-selected-model`
  - `x-primary-model`
  - `x-fallback-model`
  - `x-fallback-used`
  - `x-fallback-reason`
  - `x-translation-text`
  - `x-remote-elapsed-ms`

## Backward Compatibility

- 不修改 `/api/v1/*` 与 `/admin/*` 契约。
- split 失败时，82 协调器可自动降级调用 `/internal/translate/page`。
