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
- 提交哈希: 09b9383

## TASK-DOC-001

- TASK-ID: TASK-DOC-001
- 状态: completed
- 改动文件: `docs/plans/2026-02-14-gpu-translation-split-implementation.md`, `docs/refactor/2026-02-14-split-pipeline-worklog.md`, `docs/api/2026-02-14-internal-split-pipeline-contract.md`, `docs/refactor/INDEX.md`, `docs/INDEX.md`, `docs/gpu-translation-split-plan.md`
- 接口影响: 文档新增 internal split pipeline 契约说明
- 验证命令: `ls docs/plans docs/refactor docs/api`
- 验证结果: pass
- 提交哈希: 09b9383

## TASK-SPLIT-001

- TASK-ID: TASK-SPLIT-001
- 状态: completed
- 改动文件: `manga_translator/server/core/ctx_cache.py`
- 接口影响: 新增 CtxCache 组件（`put/get/pop` + reason 语义）
- 验证命令: `pytest -q tests/test_split_pipeline.py::test_ctx_cache_reason_codes`
- 验证结果: pass
- 提交哈希: 09b9383

## TASK-SPLIT-002

- TASK-ID: TASK-SPLIT-002
- 状态: completed
- 改动文件: `manga_translator/server/routes/v1_translate.py`
- 接口影响: 新增 `POST /internal/translate/detect`，返回 `task_id/ttl/image_hash/regions/from_lang/elapsed_ms`
- 验证命令: `pytest -q tests/test_split_pipeline.py::test_internal_detect_returns_region_index`
- 验证结果: pass
- 提交哈希: 09b9383

## TASK-SPLIT-003

- TASK-ID: TASK-SPLIT-003
- 状态: completed
- 改动文件: `manga_translator/server/routes/v1_translate.py`
- 接口影响: 新增 `POST /internal/translate/render`，实现 `401 -> 503 -> 404 -> 410 -> 422 -> 400` 状态机
- 验证命令: `pytest -q tests/test_split_pipeline.py::test_internal_render_state_machine`
- 验证结果: pass
- 提交哈希: 09b9383

## TASK-SPLIT-004

- TASK-ID: TASK-SPLIT-004
- 状态: completed
- 改动文件: `manga_translator/server/routes/v1_translate.py`
- 接口影响: CloudRun executor 新增 split 协调链路（detect -> local phase2 -> render）并对 cache 状态自动降级 unified
- 验证命令: `pytest -q tests/test_split_pipeline.py::test_cloudrun_split_falls_back_to_unified_on_cache_state`
- 验证结果: pass
- 提交哈希: 09b9383

## TASK-SPLIT-005

- TASK-ID: TASK-SPLIT-005
- 状态: completed
- 改动文件: `manga_translator/server/core/config_manager.py`, `manga_translator/server/core/task_manager.py`, `manga_translator/server/main.py`, `manga_translator/server/routes/v1_translate.py`
- 接口影响: 新增 `translate_pipeline_mode=unified|split`（默认 unified）并支持 `MANGA_TRANSLATE_PIPELINE_MODE`
- 验证命令: `pytest -q tests/test_v1_translate_concurrency.py tests/test_v1_routes.py`
- 验证结果: pass
- 提交哈希: 09b9383

## TASK-SPLIT-006

- TASK-ID: TASK-SPLIT-006
- 状态: completed
- 改动文件: `manga_translator/server/routes/v1_translate.py`
- 接口影响: 页级事件补充 `pipeline_mode`（含 `fallback_to_unified`），保持 `success/partial/error` 章节语义不变
- 验证命令: `pytest -q tests/test_v1_translate_pipeline.py tests/test_v1_routes.py`
- 验证结果: pass
- 提交哈希: 09b9383

## TASK-SPLIT-007

- TASK-ID: TASK-SPLIT-007
- 状态: completed
- 改动文件: `tests/test_split_pipeline.py`
- 接口影响: 新增 split pipeline 自动化回归（region_index、状态机、串行 gate、cache fallback）
- 验证命令: `pytest -q tests/test_split_pipeline.py tests/test_v1_translate_pipeline.py tests/test_v1_translate_concurrency.py tests/test_v1_routes.py`
- 验证结果: pass（57 passed）
- 提交哈希: 09b9383

## TASK-SPLIT-008

- TASK-ID: TASK-SPLIT-008
- 状态: completed
- 改动文件: 无（本地灰度验证执行）
- 接口影响: 无
- 验证命令: 小样本实图（单图 + 10页章节）
- 验证结果: 本地小样本灰度实测完成（1图 + 10页）：`GRAY_SINGLE_PAGE_BYTES_EQUAL=True`；`CH10_TOTAL=10`、`CH10_SUCCESS=10`、`CH10_FAILED=0`、`CH10_FILE_COUNT=10`
- 提交哈希: ac9d1ba

## TASK-SPLIT-009

- TASK-ID: TASK-SPLIT-009
- 状态: completed
- 改动文件: `test_split_pipeline_integration.py`（联调验证脚本执行）
- 接口影响: 无
- 验证命令: 联调环境灰度复测（82 + 远端计算服务）单图与10页章节
- 验证结果: pass（PPIO endpoint 联调通过：Worker ready HTTP 200；`/detect` 通过且 `regions=16`/`region_index` 连续；`/render` 通过且 `x-pipeline-mode=split`；`CACHE_MISS` 返回 404；split 管线通过（约 21.5s）与 unified 基线通过（约 35.8s））
- 提交哈希: f878f97

## TASK-DOC-002

- TASK-ID: TASK-DOC-002
- 状态: completed
- 改动文件: `docs/gpu-translation-split-plan.md`, `docs/2026-02-10-project-audit.md`, `docs/refactor/2026-02-14-split-pipeline-worklog.md`
- 接口影响: 文档补充 split 落地与回归证据
- 验证命令: `rg -n "split|internal/translate/detect|internal/translate/render|fallback_to_unified" docs/gpu-translation-split-plan.md docs/2026-02-10-project-audit.md docs/refactor/2026-02-14-split-pipeline-worklog.md`
- 验证结果: pass
- 提交哈希: 8e90eab

## TASK-GIT-001

- TASK-ID: TASK-GIT-001
- 状态: completed
- 改动文件: 待提交文件集合
- 接口影响: 无
- 验证命令: `git status --short && git log --oneline -n 10 && git push -u personal codex/split-pipeline-20260214`
- 验证结果: pass（分支已推送到 personal 远端）
- 提交哈希: 09b9383, 8e90eab

## TASK-MERGE-CLOSE-004

- TASK-ID: TASK-MERGE-CLOSE-004
- 状态: partial
- 改动文件: 无（远端推送验证）
- 接口影响: 无
- 验证命令: `git push personal main`、`git push origin main`
- 验证结果: partial（`personal/main` 推送成功；`origin/main` 于 2026-02-14 20:39:53 CST 返回 403：`Permission to hgmzhn/manga-translator-ui.git denied to aakaka525-design`）
- 提交哈希: 待回填（push audit note commit）
