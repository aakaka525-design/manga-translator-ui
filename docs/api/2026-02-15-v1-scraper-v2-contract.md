# v1 Scraper v2 契约说明（2026-02-15）

## 契约结论

1. 对外 API 路径不变：`/api/v1/scraper/*` 与 `/admin/scraper/*` 保持兼容。
2. 不新增或删除必填字段；现有调用方无需修改请求体必填参数。
3. 本轮变更为内部实现重构与兼容桥接，不引入 `/api/v2`。

## 对外接口兼容清单

1. `/api/v1/scraper/search`
2. `/api/v1/scraper/catalog`
3. `/api/v1/scraper/chapters`
4. `/api/v1/scraper/download`
5. `/api/v1/scraper/task/{task_id}`
6. `/api/v1/scraper/image`
7. `/api/v1/scraper/providers`
8. `/api/v1/scraper/state-info`
9. `/api/v1/scraper/access-check`
10. `/api/v1/scraper/upload-state`
11. `/api/v1/scraper/auth-url`
12. `/admin/scraper/tasks`
13. `/admin/scraper/metrics`
14. `/admin/scraper/health`
15. `/admin/scraper/alerts`
16. `/admin/scraper/alerts/test-webhook`
17. `/admin/scraper/queue/stats`

## 内部实现变化（非破坏）

### 新增内部模块

1. `manga_translator/server/scraper_v1/http_client.py`
2. `manga_translator/server/scraper_v1/cf_solver.py`
3. `manga_translator/server/scraper_v1/base.py`
4. `manga_translator/server/scraper_v1/models.py`
5. `manga_translator/server/scraper_v1/helpers.py`
6. `manga_translator/server/scraper_v1/download_service.py`

### 数据层变化

1. `scraper_tasks` 表新增非破坏字段：
   - `progress_completed INTEGER NOT NULL DEFAULT 0`
   - `progress_total INTEGER NOT NULL DEFAULT 0`
2. 迁移方式：运行时自动迁移（向后兼容，旧数据可读）。

## 兼容策略

1. Provider 调用保留“双路径”：
   - 新签名：`ProviderContext` 方式。
   - 旧签名：位置参数方式回退（用于历史测试桩与 monkeypatch）。
2. Parser 路由保留 `asyncio.to_thread` 调用语义，维持历史测试与行为一致。
3. 下载路径保留旧 hook 可拦截点，避免 phase2/phase3 回归断裂。

## 已知非本轮问题（留痕）

1. 全量 `pytest -q -x` 首个失败位于
   `tests/test_runtime_gpu_lazy_init.py:82`。
2. 原因是 `examples/config-example.json` 默认 `translator=openai` 与该测试期望 `gemini_hq` 不一致。
3. 本轮决策：不修改 `examples/config-example.json`，作为非 Scraper 范围缺陷单独追踪。
