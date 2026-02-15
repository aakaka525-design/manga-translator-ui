# Scraper 5 项增强实施计划（2026-02-16）

> 分支：`codex/scraper-5-enhancements-20260216`
> 工作树：`/Users/xa/Desktop/projiect/worktrees/manga-translator-ui_scraper5-20260216`
> 基线：`codex/scraper-v2-refactor-20260215`

## 实施范围

1. Provider Schema 自描述（`features`、`form_schema`、`image_cache_public`）。
2. 前端动态站点与动态表单渲染（schema 驱动）。
3. DTO 扩展（`MangaItem` 与 `ChapterItem` 可选字段）。
4. 异常指令化（`action`/`payload`）与 cookie 注入闭环。
5. 图片代理增强（统一 HTTP client、CF 挑战提示、缓存策略）。

## 接口兼容策略

1. 不删除/重命名既有 `/api/v1/scraper/*` 与 `/admin/scraper/*`。
2. 既有返回字段保持可用，仅新增可选字段。
3. 本轮新增端点：`POST /api/v1/scraper/inject_cookies`。

## TASK 清单

- TASK-S5-001：`ProviderAdapter` 与 `/providers` 元数据扩展。
- TASK-S5-002：`MangaItem`/`ChapterItem` 与路由 payload 扩展。
- TASK-S5-003：`/api/v1/scraper/image` 统一 client + challenge 指令 + 缓存头。
- TASK-S5-004：`_scraper_http_error` 支持 `action/payload`。
- TASK-S5-005：新增 `POST /api/v1/scraper/inject_cookies`。
- TASK-S5-006：前端站点选择与 `form_schema` 动态渲染。
- TASK-S5-007：前端 challenge 弹窗 -> 注入 cookie -> 自动重试闭环。
- TASK-S5-008：后端/前端回归测试。
- TASK-S5-009：文档、索引与工作日志闭环。

## 验收门禁

```bash
pytest -q tests/test_v1_routes.py tests/test_v1_scraper_phase2.py tests/test_v1_scraper_phase3.py tests/test_v1_scraper_phase4.py
cd frontend && npm test -- --run && npm run build
```

