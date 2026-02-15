# Scraper v2 实施计划（2026-02-15）

> 分支：`codex/scraper-v2-refactor-20260215`  
> 工作树：`/Users/xa/Desktop/projiect/worktrees/manga-translator-ui_scraper-v2-20260215`  
> 验收策略：Scraper 范围门禁（不阻塞于全量 pytest）

## 目标

1. 完成 Scraper v2 内部重构，保持 `/api/v1/scraper/*` 与 `/admin/scraper/*` 对外兼容。
2. 引入统一网络层、Provider 上下文、下载服务拆分与任务进度持久化。
3. 保留旧测试桩与 monkeypatch 兼容调用，确保 phase2/3/4 与 v1_routes 回归稳定。

## 范围

### In Scope

1. `scraper_v1` 内部结构重构：`http_client.py`、`cf_solver.py`、`base.py`、`models.py`、`helpers.py`、`download_service.py`。
2. `v1_scraper.py` 路由层兼容桥接（新旧 provider 签名兼容、旧 hook 兼容）。
3. `v1_parser.py` 与统一网络策略对齐，同时保留 `asyncio.to_thread` 兼容语义。
4. `task_store.py` 非破坏扩展：`progress_completed`、`progress_total`。
5. 文档与交付收口（计划、契约、worklog、索引、测试证据）。

### Out of Scope

1. 修改 `examples/config-example.json` 默认翻译器。
2. 处理非 Scraper 业务链路（翻译主链路、Scraper 之外的全量回归修复）。
3. 改动 `/api/v1/*`、`/admin/*` 的路由路径与必填 schema。

## 关键实现摘要

1. 统一 HTTP 客户端，支持 `aiohttp|curl_cffi` feature flag、域名并发控制、速率限制与 cookie 注入。
2. Provider 层引入 `ProviderContext`，同时在路由层保留旧签名 fallback 调用。
3. `/download` 路径保持旧 monkeypatch 兼容（`_run_download_task`、`_download_image`）并保留重试语义。
4. Parser 路由保持 `asyncio.to_thread(_fetch_html, ...)`，兼容现有测试断言。
5. 任务状态与进度字段写入 SQLite，并在 API 查询中保持可见。

## 测试门禁

### 阻塞门禁（本轮）

```bash
pytest -q \
  /Users/xa/Desktop/projiect/worktrees/manga-translator-ui_scraper-v2-20260215/tests/test_v1_routes.py \
  /Users/xa/Desktop/projiect/worktrees/manga-translator-ui_scraper-v2-20260215/tests/test_v1_scraper_phase2.py \
  /Users/xa/Desktop/projiect/worktrees/manga-translator-ui_scraper-v2-20260215/tests/test_v1_scraper_phase3.py \
  /Users/xa/Desktop/projiect/worktrees/manga-translator-ui_scraper-v2-20260215/tests/test_v1_scraper_phase4.py
```

结果：`78 passed`。

### 观察项（非阻塞）

```bash
pytest -q -x
```

当前首个失败：`tests/test_runtime_gpu_lazy_init.py::test_load_default_config_dict_falls_back_to_config_example`  
失败原因：测试期望 `examples/config-example.json` 默认 translator 为 `gemini_hq`，仓库当前为 `openai`。  
处置：标记为非本轮范围，记录到 worklog，不修改 `examples/config-example.json`。

## 交付与提交策略

1. 提交 1：Scraper v2 核心代码改动。
2. 提交 2：2026-02-15 文档初始化与索引更新。
3. 提交 3：门禁测试证据与收口记录。
4. 推送顺序：`personal` -> `origin`；`origin` 失败仅记录事件，不回滚已验证交付。
