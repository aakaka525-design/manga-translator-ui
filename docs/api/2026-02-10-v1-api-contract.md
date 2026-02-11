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

补充行为约束：

- `translated_url` 带缓存戳查询参数：`?v=<mtime_ns>`，用于避免前端读取旧缓存图。
- 若结果文件与原图内容完全一致（字节级一致），该页不会被视为“已翻译”（`translated_url=null`，`status=pending`）。

## Translate

6. `POST /api/v1/translate/chapter`
- 事件：`chapter_start -> progress -> chapter_complete`
- 语义收敛：仅当页面存在可翻译文本区域（`regions_count > 0`）且输出有可见变化时计入成功；否则计入失败。
- 返回可选字段：`task_id`, `execution_backend`, `accepted_at`
- 章节失败边界：逐页执行，已成功页保留；失败页按 executor 重试策略处理，超限后仅标记该页失败；当 `success_count>0 && failed_count>0` 时章节状态为 `partial`。

7. `POST /api/v1/translate/page`
- 事件：`page_complete | page_failed`
- 当翻译流程执行完成但输出图与输入图无可见差异时，返回 `409`（detail 含 `no visible changes`），并触发 `page_failed`。
- 当翻译流程执行完成但未检测到可翻译文本区域（`regions_count <= 0`）时，返回 `409`（detail 含 `no detected text regions`），并触发 `page_failed`。
- 兼容语言码：请求中的 `target_language` 支持 UI 常用短码并在后端归一化（如 `zh -> CHS`, `zh-TW -> CHT`, `en -> ENG`）；未传时默认 `CHS`。

8. `GET /api/v1/translate/events`
- SSE，`Content-Type: text/event-stream`
- 可选事件字段：`execution_backend`, `remote_elapsed_ms`, `failure_stage`

内部计算接口（仅服务间调用，非公网契约）：

- `POST /internal/translate/page`
- 用于 82 编排服务调用 Cloud Run 计算服务；请求可选 `context_translations`（固定最多 3 条）

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

## Settings 与 System（兼容补充）

22. `GET /api/v1/settings`
23. `POST /api/v1/settings/model`
24. `POST /api/v1/settings/upscale`
25. `GET /api/v1/system/logs?lines=`

鉴权要求：

- `/api/v1/settings*`：需要 `X-Session-Token`
- `/api/v1/system/logs`：需要 admin 权限（与 `/admin/logs` 一致，兼容 legacy `X-Admin-Token`）

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
