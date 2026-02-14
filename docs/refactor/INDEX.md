# Refactor Index

## 文档入口

- 用户侧文档入口：`doc/INDEX.md`
- 工程侧文档入口：`docs/INDEX.md`

## 核心实施文档

- Plan: `docs/plans/2026-02-10-vue-web-scraper-refactor.md`
- Worklog: `docs/refactor/2026-02-10-worklog.md`
- Cleanup Manifest: `docs/refactor/2026-02-10-cleanup-manifest.md`
- API Contract: `docs/api/2026-02-10-v1-api-contract.md`
- Phase2 Plan: `docs/plans/2026-02-10-scraper-phase2-multisite.md`
- Phase2 Worklog: `docs/refactor/2026-02-10-phase2-worklog.md`
- Phase2 API Contract: `docs/api/2026-02-10-v1-scraper-phase2-contract.md`
- Phase3 Plan: `docs/plans/2026-02-10-scraper-phase3-reliability.md`
- Phase3 Worklog: `docs/refactor/2026-02-10-phase3-worklog.md`
- Phase3 API Contract: `docs/api/2026-02-10-v1-scraper-phase3-contract.md`
- Phase4 Eval Plan: `docs/plans/2026-02-10-phase4-priority-evaluation.md`
- Phase4 Eval Worklog: `docs/refactor/2026-02-10-phase4-eval-worklog.md`
- Phase4 Decision: `docs/decisions/2026-02-10-phase4-go-no-go.md`
- Phase4 S1 Plan: `docs/plans/2026-02-10-phase4-s1-implementation.md`
- Phase4 S1 Worklog: `docs/refactor/2026-02-10-phase4-impl-worklog.md`
- Phase4 S1 API Contract: `docs/api/2026-02-10-v1-scraper-phase4-s1-contract.md`
- Project Audit: `docs/2026-02-10-project-audit.md`
- Docs Optimization Plan: `docs/plans/2026-02-10-doc-optimization.md`
- Docs Optimization Worklog: `docs/refactor/2026-02-10-doc-optimization-worklog.md`
- CloudRun Hybrid Plan: `docs/plans/2026-02-11-cloudrun-hybrid-implementation.md`
- CloudRun Hybrid Deployment Guide: `docs/deployment/2026-02-11-82-cloudrun-hybrid.md`
- Split Pipeline Baseline Plan: `docs/gpu-translation-split-plan.md`
- Split Pipeline Implementation Plan: `docs/plans/2026-02-14-gpu-translation-split-implementation.md`
- Split Pipeline Worklog: `docs/refactor/2026-02-14-split-pipeline-worklog.md`
- Split Pipeline API Contract: `docs/api/2026-02-14-internal-split-pipeline-contract.md`

## 验证快照

- 后端: `pytest -q tests/test_v1_routes.py` -> pass
- 后端（phase2）: `pytest -q tests/test_v1_routes.py tests/test_v1_scraper_phase2.py` -> pass
- 后端（phase3）: `pytest -q tests/test_v1_routes.py tests/test_v1_scraper_phase2.py tests/test_v1_scraper_phase3.py` -> pass
- 后端（phase4 S1）: `pytest -q tests/test_v1_routes.py tests/test_v1_scraper_phase2.py tests/test_v1_scraper_phase3.py tests/test_v1_scraper_phase4.py` -> pass
- 后端（scraper fixes）: `pytest -q tests/test_v1_scraper_phase4.py -k 'legacy_token or store_failure or non_retryable or thread_offload'` -> pass
- 前端单测: `cd frontend && npm test` -> pass
- 前端构建: `cd frontend && npm run build` -> pass
- 远端仓库: `gh repo view aakaka525-design/manga-translator-ui --json name,owner,isPrivate,defaultBranchRef,url` -> pass（private=true, defaultBranch=main）
- 远端分支: `git ls-remote --heads personal` -> pass（含 `main`, `codex/vue-web-refactor`）

## 交付规则

- 前端源码入库：`frontend/**`
- 前端构建产物不入库：`manga_translator/server/static/dist/**`
- 远端协作仓库：`https://github.com/aakaka525-design/manga-translator-ui`
