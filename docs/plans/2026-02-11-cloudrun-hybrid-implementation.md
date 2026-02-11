# 2026-02-11 CloudRun Hybrid Implementation Plan

## Goal

在不破坏现有 `/api/v1/*` 契约的前提下，实现“82 状态后端 + Cloud Run 计算后端”的混合部署基础能力。

## Scope

1. 引入翻译执行器抽象：`local` / `cloudrun`。
2. 章节翻译新增任务元数据与执行后端可观测字段。
3. 新增内部计算端点：`POST /internal/translate/page`。
4. 章节失败边界语义固定：成功页保留，失败页重试后独立失败，章节可 `partial`。
5. 部署模板与文档补齐：Nginx、systemd、Cloud Run 部署脚本。

## Non-goals

1. 一期不做 GCS 直写。
2. 不引入 `/api/v2`。
3. 不改现有前端路由结构。

## Deliverables

1. 代码：
   - `manga_translator/server/routes/v1_translate.py`
   - `manga_translator/server/request_extraction.py`
   - `manga_translator/server/core/task_manager.py`
   - `manga_translator/server/main.py`
   - `manga_translator/server/routes/__init__.py`
2. 测试：
   - `tests/test_v1_routes.py`
3. 部署模板：
   - `deploy/nginx/manga-translator-82.conf`
   - `deploy/systemd/manga-translator.service`
   - `deploy/cloudrun/deploy-compute.sh`
4. 文档：
   - `docs/deployment/2026-02-11-82-cloudrun-hybrid.md`
   - `docs/api/2026-02-10-v1-api-contract.md`
   - `README.md`, `doc/INDEX.md`, `docs/INDEX.md`
