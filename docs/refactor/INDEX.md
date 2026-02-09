# Refactor Index

## 核心文档
- Plan: `docs/plans/2026-02-10-vue-web-scraper-refactor.md`
- Worklog: `docs/refactor/2026-02-10-worklog.md`
- Cleanup Manifest: `docs/refactor/2026-02-10-cleanup-manifest.md`
- API Contract: `docs/api/2026-02-10-v1-api-contract.md`

## 验证快照
- 后端: `pytest -q tests/test_v1_routes.py` -> pass
- 前端单测: `cd frontend && npm test` -> pass
- 前端构建: `cd frontend && npm run build` -> pass
- 远端仓库: `gh repo view aakaka525-design/manga-translator-ui --json name,owner,isPrivate,defaultBranchRef,url` -> pass（private=true, defaultBranch=main）
- 远端分支: `git ls-remote --heads personal` -> pass（含 `main`, `codex/vue-web-refactor`）

## 交付规则
- 前端源码入库：`frontend/**`
- 前端构建产物不入库：`manga_translator/server/static/dist/**`
- 远端协作仓库：`https://github.com/aakaka525-design/manga-translator-ui`
