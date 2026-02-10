# 2026-02-10 v1 Scraper Phase3 API Contract

## 兼容原则

- 保持现有 `/api/v1/*` 端点不删除、不修改必填字段。
- 新增能力均以可选字段与新增端点方式扩展。

## `GET /api/v1/scraper/task/{task_id}` 响应扩展（可选）

新增字段：
- `retry_count?: number`
- `max_retries?: number`
- `next_retry_at?: string`
- `error_code?: string`
- `last_error?: string`

说明：
- 旧客户端可忽略新增字段，不受影响。
- 时间字段统一使用 ISO-8601 UTC。

## 管理端新增接口

### `GET /admin/scraper/tasks`

查询参数：
- `status?: string`
- `provider?: string`
- `limit?: number`（默认 20）
- `offset?: number`（默认 0）

返回：
```json
{
  "items": [
    {
      "task_id": "...",
      "status": "retrying",
      "message": "下载重试中",
      "provider": "toongod",
      "retry_count": 1,
      "max_retries": 2,
      "error_code": null,
      "updated_at": "2026-02-10T08:00:00+00:00"
    }
  ],
  "total": 1,
  "limit": 20,
  "offset": 0,
  "has_more": false
}
```

### `GET /admin/scraper/metrics`

查询参数：
- `hours?: number`（默认 24）

返回：
```json
{
  "hours": 24,
  "total": 42,
  "success": 30,
  "partial": 5,
  "error": 7,
  "success_rate": 0.7143,
  "provider_breakdown": {
    "toongod": 20,
    "mangaforfree": 12,
    "generic": 10
  },
  "error_code_breakdown": {
    "SCRAPER_RETRY_EXHAUSTED": 4,
    "SCRAPER_BROWSER_UNAVAILABLE": 3
  }
}
```

## 错误码扩展

- `SCRAPER_TASK_DUPLICATE`：幂等命中，任务已存在。
- `SCRAPER_TASK_STALE`：服务重启后发现陈旧任务并标记失败。
- `SCRAPER_RETRY_EXHAUSTED`：达到重试上限后仍失败。

## 数据持久化扩展

`scraper_tasks` 表新增字段：
- `retry_count INTEGER NOT NULL DEFAULT 0`
- `max_retries INTEGER NOT NULL DEFAULT 2`
- `next_retry_at TEXT`
- `last_error TEXT`
- `request_fingerprint TEXT`
- `started_at TEXT`

并保留：
- `task_id,status,message,report_json,request_json,provider,created_at,updated_at,finished_at,error_code`
