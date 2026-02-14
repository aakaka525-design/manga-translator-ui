# GPU Translation Split Pipeline Implementation Plan

## Goal

在不破坏既有 `/api/v1/*` 契约前提下，落地 split pipeline（detect -> local translate -> render），保留 unified `/internal/translate/page` 作为自动回退路径。

## Scope

- 新增内部端点：`/internal/translate/detect`、`/internal/translate/render`
- 新增缓存组件：`CtxCache`
- 82 侧协调逻辑：split/unified 可切换，支持自动降级
- 文档与测试闭环

## Out of Scope

- 不引入 `/api/v2`
- 不改鉴权模型
- 不迁移 scraper

## Task Status

1. `TASK-WT-001` completed
2. `TASK-DOC-001` completed
3. `TASK-SPLIT-001` completed
4. `TASK-SPLIT-002` completed
5. `TASK-SPLIT-003` completed
6. `TASK-SPLIT-004` completed
7. `TASK-SPLIT-005` completed
8. `TASK-SPLIT-006` completed
9. `TASK-SPLIT-007` completed
10. `TASK-SPLIT-008` completed（本地小样本灰度实测）
11. `TASK-DOC-002` completed
12. `TASK-GIT-001` completed

## Verification Snapshot

- `pytest -q tests/test_split_pipeline.py` -> pass
- `pytest -q tests/test_v1_translate_pipeline.py tests/test_v1_translate_concurrency.py tests/test_v1_routes.py tests/test_split_pipeline.py` -> pass (57 passed)

## Acceptance

- detect/render 可用，状态机正确
- cache miss 自动降级 unified，且无假成功
- `success_count + failed_count == total_count`
- 前端成功页数与文件数一致（本地灰度 + 联调环境已确认）
