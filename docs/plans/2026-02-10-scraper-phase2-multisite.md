# 2026-02-10 Scraper Phase2 Multisite Plan

> 实施状态追踪（本轮执行记录）

| TASK-ID | 状态 | 改动文件 | 接口影响 | 验证命令 | 验证结果 | 提交哈希 |
|---|---|---|---|---|---|---|
| TASK-013 | completed | `docs/plans/2026-02-10-scraper-phase2-multisite.md`, `docs/refactor/2026-02-10-phase2-worklog.md`, `docs/api/2026-02-10-v1-scraper-phase2-contract.md`, `docs/refactor/INDEX.md` | 无 | `ls docs/plans docs/refactor docs/api` | pass | ce4fbbe |
| TASK-014 | completed | `manga_translator/server/scraper_v1/providers.py`, `manga_translator/server/scraper_v1/__init__.py`, `manga_translator/server/routes/v1_scraper.py` | 新增 provider registry + `site_hint`/`force_engine` | `pytest -q tests/test_v1_scraper_phase2.py -k provider` | pass | ce4fbbe |
| TASK-015 | completed | `manga_translator/server/scraper_v1/toongod.py`, `manga_translator/server/scraper_v1/generic.py`, `manga_translator/server/routes/v1_parser.py` | 新增 ToonGod/Generic 抓取适配与 parser generic 能力 | `pytest -q tests/test_v1_scraper_phase2.py -k 'toongod or generic or parser'` | pass | ce4fbbe |
| TASK-016 | completed | `manga_translator/server/routes/v1_scraper.py` | 新增 `GET /api/v1/scraper/providers`，并将 search/catalog/chapters/download/access-check/image 接入 registry | `pytest -q tests/test_v1_scraper_phase2.py -k 'search or catalog or chapters or providers'` | pass | ce4fbbe |
| TASK-017 | completed | `manga_translator/server/scraper_v1/task_store.py`, `manga_translator/server/routes/v1_scraper.py`, `manga_translator/server/main.py` | `GET /api/v1/scraper/task/{task_id}` 增加 `persisted/created_at/updated_at` | `pytest -q tests/test_v1_scraper_phase2.py -k 'task_store or task_status or restart'` | pass | ce4fbbe |
| TASK-018 | completed | `frontend/src/stores/scraper.js`, `frontend/src/views/scraper/ScraperConfig.vue`, `frontend/src/views/ScraperView.vue` | 前端 payload 增加 `site_hint`/`force_engine`，新增 provider 元数据展示 | `cd frontend && npm test -- --run` | pass | ce4fbbe |
| TASK-019 | completed | `tests/test_v1_scraper_phase2.py`, `frontend/tests/scraper_multisite_phase2.test.js`, `frontend/tests/scraper_error_messages.test.js`, `tests/test_v1_routes.py` | 二期回归用例补齐（provider、generic、SQLite、鉴权） | `pytest -q tests/test_v1_routes.py tests/test_v1_scraper_phase2.py && cd frontend && npm test -- --run && npm run build` | pass | ce4fbbe |
| TASK-020 | completed | `docs/refactor/2026-02-10-phase2-worklog.md`, `docs/api/2026-02-10-v1-scraper-phase2-contract.md`, `docs/plans/2026-02-10-scraper-phase2-multisite.md`, `docs/refactor/INDEX.md`, `README.md`, `doc/CLI_USAGE.md` | 文档闭环，明确二期接口与交付策略 | `rg -n 'scraper/providers|site_hint|force_engine|SQLite|dist' README.md doc/CLI_USAGE.md docs/api/2026-02-10-v1-scraper-phase2-contract.md` | pass | ce4fbbe |

## Locked Decisions

- 二期继续保持 `/api/v1` 兼容，不引入 `/api/v2` 强制迁移。
- 多站点首批支持：`mangaforfree`、`toongod`、`generic`。
- `generic` 默认 HTTP-first；`force_engine=playwright` 时按需启用浏览器能力。
- 爬虫任务状态使用 SQLite 持久化（`manga_translator/server/data/scraper_tasks.db`），完成态保留 7 天。
- 前端构建产物 `manga_translator/server/static/dist/**` 不入库。
