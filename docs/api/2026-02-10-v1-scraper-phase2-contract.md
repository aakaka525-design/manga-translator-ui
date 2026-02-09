# 2026-02-10 v1 Scraper Phase2 API Contract

## 兼容原则

- 保持现有 `/api/v1/*` 路由兼容，不删除已发布端点。
- 新能力以可选字段方式扩展，不破坏旧请求。

## Scraper 请求体扩展（可选）

适用于 `/api/v1/scraper/search`、`/catalog`、`/chapters`、`/download`：

- `site_hint?: "mangaforfree" | "toongod" | "generic"`
- `force_engine?: "http" | "playwright"`

说明：
- 未提供 `site_hint` 时，后端根据 `base_url` 自动识别 provider。
- 未提供 `force_engine` 时，provider 采用默认策略。

## Scraper 新增端点

### `GET /api/v1/scraper/providers`

返回：
```json
{
  "items": [
    {
      "key": "mangaforfree",
      "label": "MangaForFree",
      "hosts": ["mangaforfree.com"],
      "supports_http": true,
      "supports_playwright": false,
      "supports_custom_host": false,
      "default_catalog_path": "/manga/"
    }
  ]
}
```

## Task 状态扩展

### `GET /api/v1/scraper/task/{task_id}`

新增可选字段：
- `persisted?: true`
- `created_at?: string`（ISO-8601 UTC）
- `updated_at?: string`（ISO-8601 UTC）

示例：
```json
{
  "task_id": "...",
  "status": "success",
  "message": "下载完成",
  "report": {"success_count": 10, "failed_count": 0, "total_count": 10},
  "persisted": true,
  "created_at": "2026-02-10T06:00:00+00:00",
  "updated_at": "2026-02-10T06:01:00+00:00"
}
```

## 错误码扩展

在 `detail.code` 返回：
- `SCRAPER_PROVIDER_UNAVAILABLE`
- `SCRAPER_BROWSER_UNAVAILABLE`
- `SCRAPER_TASK_STORE_ERROR`

## Provider 策略

- `mangaforfree`：站点定制适配。
- `toongod`：站点定制适配。
- `generic`：自定义站点适配（HTTP-first，可选 playwright）。

## 持久化策略

- SQLite 路径：`manga_translator/server/data/scraper_tasks.db`
- 表：`scraper_tasks(task_id,status,message,report_json,request_json,provider,created_at,updated_at,finished_at,error_code)`
- 清理：完成态任务保留 7 天。
