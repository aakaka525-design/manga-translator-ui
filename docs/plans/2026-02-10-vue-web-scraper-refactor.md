# 2026-02-10 Vue Web + Scraper Refactor Plan

> 实施状态追踪（本轮执行记录）

| TASK-ID | 状态 | 改动文件 | 接口影响 | 验证命令 | 验证结果 | 提交哈希 |
|---|---|---|---|---|---|---|
| TASK-001 | completed | `docs/plans/2026-02-10-vue-web-scraper-refactor.md`, `docs/refactor/2026-02-10-worklog.md`, `docs/refactor/2026-02-10-cleanup-manifest.md`, `docs/api/2026-02-10-v1-api-contract.md`, `docs/refactor/INDEX.md` | 无 | `ls docs/plans docs/refactor docs/api` | pass | 597f831 |
| TASK-002 | completed | `manga_translator/server/static/js/admin/i18n.js`, `manga_translator/server/static/js/admin/modules/permissions.js`, `manga_translator/server/static/js/admin/**`, `manga_translator/server/static/admin/css/admin.css`, `manga_translator/server/static/index.html`, `manga_translator/server/static/login.html`, `manga_translator/server/static/admin-new.html`, `manga_translator/server/static/style.css`, `manga_translator/server/static/script.js`, `manga_translator/server/static/js/history-gallery.js`, `manga_translator/server/static/js/i18n.js` | 无 | `find manga_translator/server/static -maxdepth 4 -type f | rg 'admin-new|index.html|login.html|style.css|script.js|history-gallery.js|js/i18n.js|js/admin'` | pass（无匹配） | 597f831 |
| TASK-003 | completed | `frontend/**`, `frontend/vite.config.js` | 新增 Vue SPA 源码 | `cd frontend && npm test` | pass | 597f831 |
| TASK-004 | completed | `manga_translator/server/static/*`（旧 UI 文件删除） | 旧静态入口移除 | `find manga_translator/server/static -maxdepth 4 -type f` | pass（仅 favicon + dist） | 597f831 |
| TASK-005 | completed | `manga_translator/server/routes/web.py`, `manga_translator/server/main.py` | SPA 路由与旧登录入口重定向 | `pytest -q tests/test_v1_routes.py -k spa` | pass | 597f831 |
| TASK-006 | completed | `manga_translator/server/routes/v1_manga.py`, `manga_translator/server/core/library_service.py` | 新增 `/api/v1/manga*` | `pytest -q tests/test_v1_routes.py -k v1_manga` | pass | 597f831 |
| TASK-007 | completed | `manga_translator/server/routes/v1_translate.py`, `manga_translator/server/core/v1_event_bus.py` | 新增 `/api/v1/translate/*` + SSE | `pytest -q tests/test_v1_routes.py -k translate` | pass | 597f831 |
| TASK-008 | completed | `manga_translator/server/routes/v1_scraper.py`, `manga_translator/server/scraper_v1/**` | 新增 `/api/v1/scraper/*`（MangaForFree） | `pytest -q tests/test_v1_routes.py -k scraper` | pass | 597f831 |
| TASK-009 | completed | `manga_translator/server/routes/v1_parser.py` | 新增 `/api/v1/parser/*` | `pytest -q tests/test_v1_routes.py -k parser` | pass | 597f831 |
| TASK-010 | completed | `frontend/src/views/AdminView.vue`, `frontend/src/router/index.js`, `frontend/src/components/layout/GlassNav.vue` | `/admin` 首版页面（状态/任务/登出） | `cd frontend && npm run build` | pass | 597f831 |
| TASK-011 | completed | `README.md`, `doc/INSTALLATION.md`, `doc/CLI_USAGE.md`, `.gitignore` | 文档改为新入口 + dist 忽略策略 | `rg -n 'admin\.html' README.md doc/INSTALLATION.md doc/CLI_USAGE.md` | pass（无旧入口） | 597f831 |
| TASK-012 | pending | Git remote/push | 无 | `git remote add personal https://github.com/aakaka525-design/manga-translator-ui.git && git push -u personal codex/vue-web-refactor` | fail（Repository not found，待确认仓库名/权限） | bc95d0d |

## Locked Decisions

- 保留 Qt 代码，仅作为参考，不改 Qt。
- 保留 `/auth/login` + `X-Session-Token` 鉴权机制。
- `dist` 只用于部署构建，不上传 GitHub。
- 爬虫首版仅支持 MangaForFree，其他站点返回结构化错误。
