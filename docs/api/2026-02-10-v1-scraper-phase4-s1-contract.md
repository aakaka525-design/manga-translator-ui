# 2026-02-10 v1 Scraper Phase4 S1 API Contract

## 兼容原则

- 保持现有 `/api/v1/*` 端点不删除、不修改必填字段。
- phase4 仅通过新增管理端接口与可选字段扩展能力。
- 保持鉴权模型不变：`/auth/login` + `X-Session-Token`，管理端继续兼容 `X-Admin-Token`。

## `GET /api/v1/scraper/task/{task_id}` 响应扩展（可选）

新增可选字段：
- `queue_status?: "queued" | "running" | "retrying" | "done" | "failed"`
- `enqueued_at?: string`
- `dequeued_at?: string`
- `worker_id?: string`

映射规则：
- `pending -> queued`
- `running -> running`
- `retrying -> retrying`
- `success | partial -> done`
- `error -> failed`

## 新增管理端接口（admin 权限）

### `GET /admin/scraper/health`

返回固定顶层字段：`status`, `db`, `scheduler`, `alerts`, `time`。

返回示例：
```json
{
  "status": "ok",
  "db": {
    "path": "manga_translator/server/data/scraper_tasks.db",
    "available": true,
    "error": null
  },
  "scheduler": {
    "running": true,
    "enabled": true,
    "poll_interval_sec": 30,
    "last_run_at": "2026-02-10T08:00:00+00:00",
    "last_error": null,
    "last_emitted": 0,
    "started_at": "2026-02-10T08:00:00+00:00",
    "stopped_at": null
  },
  "alerts": {
    "enabled": true,
    "cooldown_sec": 300,
    "webhook_enabled": false
  },
  "time": "2026-02-10T08:00:30+00:00"
}
```

### `GET /admin/scraper/alerts?severity=&rule=&limit=&offset=`

返回固定字段：`items`, `total`, `limit`, `offset`, `has_more`。

`items` 字段：
- `id: number`
- `rule: string`
- `severity: string`
- `message: string`
- `payload?: object`
- `webhook_status: "pending" | "sent" | "failed" | "skipped"`
- `webhook_attempts: number`
- `webhook_last_error?: string`
- `created_at: string`
- `updated_at: string`

### `POST /admin/scraper/alerts/test-webhook`

请求体（可选）：
```json
{
  "webhook_url": "https://example.org/hook"
}
```

返回固定字段：
```json
{
  "sent": true,
  "attempts": 1,
  "status": "sent",
  "message": "webhook delivered (200)"
}
```

### `GET /admin/scraper/queue/stats`

返回固定字段：
- `pending: number`
- `running: number`
- `retrying: number`
- `done: number`
- `failed: number`
- `backlog: number`
- `oldest_pending_age_sec: number | null`

## 错误码扩展

- `SCRAPER_ALERT_WEBHOOK_FAILED`
- `SCRAPER_ALERT_CONFIG_INVALID`
- `SCRAPER_ALERT_STORE_ERROR`

## 告警规则（S1）

- `backlog_high`：`backlog >= threshold_backlog`
- `error_rate_high`：`metrics.total >= threshold_min_sample` 且 `metrics.error / metrics.total >= threshold_error_rate`
- `stale_detected`：`error_code_breakdown.SCRAPER_TASK_STALE > 0`

默认参数：
- `poll_interval_sec = 30`
- `cooldown_sec = 300`
- `threshold_backlog = 30`
- `threshold_error_rate = 0.25`
- `threshold_min_sample = 20`
- `webhook.timeout_sec = 5`
- `webhook.max_retries = 3`

## 数据持久化扩展

在 `scraper_tasks.db` 中新增告警表：

`scraper_alerts(id, rule, severity, message, payload_json, webhook_status, webhook_attempts, webhook_last_error, created_at, updated_at)`

索引：
- `idx_scraper_alerts_rule_created_at`
- `idx_scraper_alerts_webhook_status_created_at`
