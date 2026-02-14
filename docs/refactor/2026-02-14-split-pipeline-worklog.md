# Split Pipeline Worklog (2026-02-14)

## Record Template

- TASK-ID:
- 状态:
- 改动文件:
- 接口影响:
- 验证命令:
- 验证结果:
- 提交哈希:

## TASK-WT-001

- TASK-ID: TASK-WT-001
- 状态: completed
- 改动文件: 无（工作树操作）
- 接口影响: 无
- 验证命令: `git worktree list && git -C /Users/xa/Desktop/projiect/worktrees/manga-translator-ui_split-20260214 branch --show-current`
- 验证结果: pass（新工作树已创建，分支 `codex/split-pipeline-20260214`）
- 提交哈希: N/A

## TASK-DOC-001

- TASK-ID: TASK-DOC-001
- 状态: completed
- 改动文件: `docs/plans/2026-02-14-gpu-translation-split-implementation.md`, `docs/refactor/2026-02-14-split-pipeline-worklog.md`, `docs/api/2026-02-14-internal-split-pipeline-contract.md`, `docs/refactor/INDEX.md`, `docs/INDEX.md`, `docs/gpu-translation-split-plan.md`
- 接口影响: 文档新增 internal split pipeline 契约说明
- 验证命令: `ls docs/plans docs/refactor docs/api`
- 验证结果: pass
- 提交哈希: N/A

## TASK-SPLIT-001

- TASK-ID: TASK-SPLIT-001
- 状态: completed
- 改动文件: `manga_translator/server/core/ctx_cache.py`
- 接口影响: 新增 CtxCache 组件（`put/get/pop` + reason 语义）
- 验证命令: `pytest -q tests/test_split_pipeline.py::test_ctx_cache_reason_codes`
- 验证结果: pass
- 提交哈希: N/A

## TASK-SPLIT-002

- TASK-ID: TASK-SPLIT-002
- 状态: completed
- 改动文件: `manga_translator/server/routes/v1_translate.py`
- 接口影响: 新增 `POST /internal/translate/detect`，返回 `task_id/ttl/image_hash/regions/from_lang/elapsed_ms`
- 验证命令: `pytest -q tests/test_split_pipeline.py::test_internal_detect_returns_region_index`
- 验证结果: pass
- 提交哈希: N/A

## TASK-SPLIT-003

- TASK-ID: TASK-SPLIT-003
- 状态: completed
- 改动文件: `manga_translator/server/routes/v1_translate.py`
- 接口影响: 新增 `POST /internal/translate/render`，实现 `401 -> 503 -> 404 -> 410 -> 422 -> 400` 状态机
- 验证命令: `pytest -q tests/test_split_pipeline.py::test_internal_render_state_machine`
- 验证结果: pass
- 提交哈希: N/A

## TASK-SPLIT-004

- TASK-ID: TASK-SPLIT-004
- 状态: completed
- 改动文件: `manga_translator/server/routes/v1_translate.py`
- 接口影响: CloudRun executor 新增 split 协调链路（detect -> local phase2 -> render）并对 cache 状态自动降级 unified
- 验证命令: `pytest -q tests/test_split_pipeline.py::test_cloudrun_split_falls_back_to_unified_on_cache_state`
- 验证结果: pass
- 提交哈希: N/A

## TASK-SPLIT-005

- TASK-ID: TASK-SPLIT-005
- 状态: completed
- 改动文件: `manga_translator/server/core/config_manager.py`, `manga_translator/server/core/task_manager.py`, `manga_translator/server/main.py`, `manga_translator/server/routes/v1_translate.py`
- 接口影响: 新增 `translate_pipeline_mode=unified|split`（默认 unified）并支持 `MANGA_TRANSLATE_PIPELINE_MODE`
- 验证命令: `pytest -q tests/test_v1_translate_concurrency.py tests/test_v1_routes.py`
- 验证结果: pass
- 提交哈希: N/A

## TASK-SPLIT-006

- TASK-ID: TASK-SPLIT-006
- 状态: completed
- 改动文件: `manga_translator/server/routes/v1_translate.py`
- 接口影响: 页级事件补充 `pipeline_mode`（含 `fallback_to_unified`），保持 `success/partial/error` 章节语义不变
- 验证命令: `pytest -q tests/test_v1_translate_pipeline.py tests/test_v1_routes.py`
- 验证结果: pass
- 提交哈希: N/A

## TASK-SPLIT-007

- TASK-ID: TASK-SPLIT-007
- 状态: completed
- 改动文件: `tests/test_split_pipeline.py`
- 接口影响: 新增 split pipeline 自动化回归（region_index、状态机、串行 gate、cache fallback）
- 验证命令: `pytest -q tests/test_split_pipeline.py tests/test_v1_translate_pipeline.py tests/test_v1_translate_concurrency.py tests/test_v1_routes.py`
- 验证结果: pass（57 passed）
- 提交哈希: N/A

## TASK-SPLIT-008

- TASK-ID: TASK-SPLIT-008
- 状态: pending
- 改动文件: N/A
- 接口影响: 无
- 验证命令: 小样本实图（单图 + 10页章节）
- 验证结果: 待在联调环境执行
- 提交哈希: N/A

## TASK-DOC-002

- TASK-ID: TASK-DOC-002
- 状态: completed
- 改动文件: `docs/gpu-translation-split-plan.md`, `docs/2026-02-10-project-audit.md`, `docs/refactor/2026-02-14-split-pipeline-worklog.md`
- 接口影响: 文档补充 split 落地与回归证据
- 验证命令: `rg -n "split|internal/translate/detect|internal/translate/render|fallback_to_unified" docs/gpu-translation-split-plan.md docs/2026-02-10-project-audit.md docs/refactor/2026-02-14-split-pipeline-worklog.md`
- 验证结果: pass
- 提交哈希: N/A

## TASK-GIT-001

- TASK-ID: TASK-GIT-001
- 状态: pending
- 改动文件: 待提交文件集合
- 接口影响: 无
- 验证命令: `git status --short && git log --oneline -n 10`
- 验证结果: pending
- 提交哈希: N/A
