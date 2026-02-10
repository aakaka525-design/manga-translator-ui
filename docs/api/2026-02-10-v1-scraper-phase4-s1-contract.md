# 2026-02-10 v1 Scraper Phase4 S1 API Contract

## 定位

本文件定义 phase4 S1（轻量可观测）新增/扩展契约。

- v1 总览请看：`docs/api/2026-02-10-v1-api-contract.md`
- 本文件只描述 S1 的可观测扩展与管理端能力

## 兼容原则

- 保持现有 `/api/v1/*` 端点不删除、不修改必填字段。
- phase4 仅通过新增管理端接口与可选字段扩展能力。
- 鉴权不变：`/auth/login` + `X-Session-Token`。
- 管理端继续兼容 `X-Admin-Token`（历史客户端）。

## `GET /api/v1/scraper/task/{task_id}` 可选扩展

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

字段语义补充（2026-02-10 修订）：

- `retry_count` 表示“实际已执行重试次数”，不再在非重试耗尽失败场景写成 `max_retries`。
- `error_code` 仅在“可重试失败且达到重试上限”时使用 `SCRAPER_RETRY_EXHAUSTED`。
- 其他 `success_count == 0` 的下载失败场景使用 `SCRAPER_DOWNLOAD_FAILED`。

## 管理端新增接口（admin 权限）

鉴权兼容补充（2026-02-10 修订）：

- `/admin/scraper/*` 真实支持 legacy `X-Admin-Token` 直通。
- 未携带 token 仍返回 401；非 admin session 仍返回 403。

### `GET /admin/scraper/health`

固定返回字段：`status`, `db`, `scheduler`, `alerts`, `time`

### `GET /admin/scraper/alerts?severity=&rule=&limit=&offset=`

固定返回字段：`items`, `total`, `limit`, `offset`, `has_more`

`items` 字段：

- `id`
- `rule`
- `severity`
- `message`
- `payload?`
- `webhook_status: "pending" | "sent" | "failed" | "skipped"`
- `webhook_attempts`
- `webhook_last_error?`
- `created_at`
- `updated_at`

### `POST /admin/scraper/alerts/test-webhook`

请求体：

```json
{
  "webhook_url": "https://example.org/hook"
}
```

`webhook_url` 可选；缺省时使用配置中的 webhook 地址。

返回字段：`sent`, `attempts`, `status`, `message`

### `GET /admin/scraper/queue/stats`

固定返回字段：

- `pending`
- `running`
- `retrying`
- `done`
- `failed`
- `backlog`
- `oldest_pending_age_sec`

## 错误码扩展

- `SCRAPER_ALERT_WEBHOOK_FAILED`
- `SCRAPER_ALERT_CONFIG_INVALID`
- `SCRAPER_ALERT_STORE_ERROR`

## 告警规则（S1）

- `backlog_high`: `backlog >= threshold_backlog`
- `error_rate_high`: `total >= threshold_min_sample` 且 `error / total >= threshold_error_rate`
- `stale_detected`: `error_code_breakdown.SCRAPER_TASK_STALE > 0`

默认参数：

- `poll_interval_sec = 30`
- `cooldown_sec = 300`
- `threshold_backlog = 30`
- `threshold_error_rate = 0.25`
- `threshold_min_sample = 20`
- `webhook.timeout_sec = 5`
- `webhook.max_retries = 3`

## 持久化扩展（SQLite）

数据库：`manga_translator/server/data/scraper_tasks.db`

新增告警表：

`scraper_alerts(id, rule, severity, message, payload_json, webhook_status, webhook_attempts, webhook_last_error, created_at, updated_at)`

索引：

- `idx_scraper_alerts_rule_created_at`
- `idx_scraper_alerts_webhook_status_created_at`
