# 2026-02-10 v1 API Contract

## Auth Contract
- 复用现有会话机制：`POST /auth/login` + `X-Session-Token`。
- 所有 `/api/v1/*` 路由均受保护。
- SSE 与图片代理支持 `?token=` 查询参数（用于浏览器受限场景）。

## Manga

1. `GET /api/v1/manga`
- 返回: `[{ id, name, cover_url, chapter_count }]`

2. `GET /api/v1/manga/{manga_id}/chapters`
- 返回: `[{ id, name, has_original, has_translated, translated_count, page_count, is_complete }]`

3. `GET /api/v1/manga/{manga_id}/chapter/{chapter_id}`
- 返回: `{ manga_id, chapter_id, pages: [{ name, original_url, translated_url, status, status_reason, warning_counts }] }`

4. `DELETE /api/v1/manga/{manga_id}`
- 返回: `{ message }`

5. `DELETE /api/v1/manga/{manga_id}/chapter/{chapter_id}`
- 返回: `{ message }`

## Translate

6. `POST /api/v1/translate/chapter`
- 请求: `{ manga_id, chapter_id, source_language?, target_language? }`
- 返回: `{ message, page_count }`
- 事件: `chapter_start` -> `progress` -> `chapter_complete`

7. `POST /api/v1/translate/page`
- 请求: `{ manga_id, chapter_id, image_name, source_language?, target_language? }`
- 返回: `{ task_id, status, output_path, regions_count }`
- 事件: `page_complete` / `page_failed`

8. `GET /api/v1/translate/events`
- SSE 数据流，`Content-Type: text/event-stream`

## Scraper (MangaForFree only)

9. `POST /api/v1/scraper/search`
- 请求: `{ base_url, keyword, ...scraper options }`
- 返回: `[{ id, title, url, cover_url }]`

10. `POST /api/v1/scraper/catalog`
- 请求: `{ base_url, page, orderby?, path?, ... }`
- 返回: `{ page, has_more, items: [...] }`

11. `POST /api/v1/scraper/chapters`
- 请求: `{ base_url, manga, ... }`
- 返回: `[{ id, title, url, index, downloaded, downloaded_count, downloaded_total }]`

12. `POST /api/v1/scraper/download`
- 请求: `{ base_url, manga, chapter, ... }`
- 返回: `{ task_id, status, message }`

13. `GET /api/v1/scraper/task/{task_id}`
- 返回: `{ task_id, status, message, report? }`

14. `POST /api/v1/scraper/state-info`
- 请求: `{ base_url?, storage_state_path? }`
- 返回: `{ status, cookie_name?, expires_at?, expires_at_text?, expires_in_sec?, message? }`

15. `POST /api/v1/scraper/access-check`
- 请求: `{ base_url, storage_state_path?, path? }`
- 返回: `{ status, http_status?, message? }`

16. `POST /api/v1/scraper/upload-state`
- Form: `base_url`, `file(json)`
- 返回: `{ path, status, message?, expires_at?, expires_at_text? }`

17. `GET /api/v1/scraper/auth-url`
- 返回: `{ url }`

18. `GET /api/v1/scraper/image`
- 查询: `url`, `base_url`, `storage_state_path?`, `user_agent?`, `token?`
- 返回: 图片流

- 非 MangaForFree 站点统一返回结构化错误:
  - `detail.code = SCRAPER_SITE_UNSUPPORTED`

## Parser

19. `POST /api/v1/parser/parse`
- 请求: `{ url, mode }`
- 返回: `{ url, title, author, cover_url, paragraphs, warnings }`

20. `POST /api/v1/parser/list`
- 请求: `{ url, mode }`
- 返回: `{ page_type, recognized, site, downloadable, items, warnings }`

## SPA Routes

- `/`
- `/signin`
- `/admin`
- `/scraper`
- `/manga/:id`
- `/read/:mangaId/:chapterId`

以上路由均由后端返回 `manga_translator/server/static/dist/index.html`。
