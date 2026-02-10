# 2026-02-10 v1 API Contract

## 契约范围

本文件是 `/api/v1/*` 的总览契约（非破坏性扩展已合并）。

- 兼容策略：不删除既有 v1 端点，不修改既有必填字段
- 鉴权策略：`POST /auth/login` + `X-Session-Token`
- 浏览器受限场景：SSE 与图片代理支持 `?token=`

## Auth Contract

- `GET /auth/status`：检查是否需要初始化
- `POST /auth/setup`：首次创建管理员
- `POST /auth/login`：登录并获取会话 token
- `POST /auth/logout`：注销
- `GET /auth/check`：验证会话

> 无默认账号密码，必须先走 `status -> setup -> login`。

## Manga

1. `GET /api/v1/manga`
2. `GET /api/v1/manga/{manga_id}/chapters`
3. `GET /api/v1/manga/{manga_id}/chapter/{chapter_id}`
4. `DELETE /api/v1/manga/{manga_id}`
5. `DELETE /api/v1/manga/{manga_id}/chapter/{chapter_id}`

## Translate

6. `POST /api/v1/translate/chapter`
- 事件：`chapter_start -> progress -> chapter_complete`

7. `POST /api/v1/translate/page`
- 事件：`page_complete | page_failed`

8. `GET /api/v1/translate/events`
- SSE，`Content-Type: text/event-stream`

## Scraper

9. `GET /api/v1/scraper/providers`
- 返回 provider 与 capability 列表

10. `POST /api/v1/scraper/search`
11. `POST /api/v1/scraper/catalog`
12. `POST /api/v1/scraper/chapters`
13. `POST /api/v1/scraper/download`
14. `GET /api/v1/scraper/task/{task_id}`
15. `POST /api/v1/scraper/state-info`
16. `POST /api/v1/scraper/access-check`
17. `POST /api/v1/scraper/upload-state`
18. `GET /api/v1/scraper/auth-url`
19. `GET /api/v1/scraper/image`

Scraper 请求体扩展（可选）：

- `site_hint?: "mangaforfree" | "toongod" | "generic"`
- `force_engine?: "http" | "playwright"`

`GET /api/v1/scraper/task/{task_id}` 可选扩展字段：

- `persisted`, `created_at`, `updated_at`
- `retry_count`, `max_retries`, `next_retry_at`, `error_code`, `last_error`
- `queue_status`, `enqueued_at`, `dequeued_at`, `worker_id`

Scraper 相关错误码（扩展并保留旧码）：

- `SCRAPER_PROVIDER_UNAVAILABLE`
- `SCRAPER_BROWSER_UNAVAILABLE`
- `SCRAPER_TASK_STORE_ERROR`
- `SCRAPER_TASK_DUPLICATE`
- `SCRAPER_TASK_STALE`
- `SCRAPER_RETRY_EXHAUSTED`

## Parser

20. `POST /api/v1/parser/parse`
21. `POST /api/v1/parser/list`

## 管理端（Scraper 可观测）

管理端接口位于 `/admin/*`（admin 权限），详见：

- `docs/api/2026-02-10-v1-scraper-phase4-s1-contract.md`

核心端点：

- `GET /admin/scraper/tasks`
- `GET /admin/scraper/metrics`
- `GET /admin/scraper/health`
- `GET /admin/scraper/alerts`
- `POST /admin/scraper/alerts/test-webhook`
- `GET /admin/scraper/queue/stats`

## SPA Routes

以下路由由后端返回 `manga_translator/server/static/dist/index.html`：

- `/`
- `/signin`
- `/admin`
- `/scraper`
- `/manga/:id`
- `/read/:mangaId/:chapterId`

兼容入口：`/static/login.html -> /signin`（307）
