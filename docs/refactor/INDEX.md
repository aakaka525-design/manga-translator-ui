# Refactor Index

## 入口

- 工程总入口：`docs/INDEX.md`
- 用户文档入口：`doc/INDEX.md`

## 核心基线（先看）

- 总重构计划：`docs/plans/2026-02-10-vue-web-scraper-refactor.md`
- 主工作日志：`docs/refactor/2026-02-10-worklog.md`
- 主 API 契约：`docs/api/2026-02-10-v1-api-contract.md`
- 项目审计：`docs/2026-02-10-project-audit.md`

## 分阶段文档

- Phase2（Scraper 多站点）：
  - `docs/plans/2026-02-10-scraper-phase2-multisite.md`
  - `docs/refactor/2026-02-10-phase2-worklog.md`
  - `docs/api/2026-02-10-v1-scraper-phase2-contract.md`
- Phase3（稳定性 + 管理页）：
  - `docs/plans/2026-02-10-scraper-phase3-reliability.md`
  - `docs/refactor/2026-02-10-phase3-worklog.md`
  - `docs/api/2026-02-10-v1-scraper-phase3-contract.md`
- Phase4（评估与S1实施）：
  - `docs/plans/2026-02-10-phase4-priority-evaluation.md`
  - `docs/refactor/2026-02-10-phase4-eval-worklog.md`
  - `docs/decisions/2026-02-10-phase4-go-no-go.md`
  - `docs/plans/2026-02-10-phase4-s1-implementation.md`
  - `docs/refactor/2026-02-10-phase4-impl-worklog.md`
  - `docs/api/2026-02-10-v1-scraper-phase4-s1-contract.md`

## Split Pipeline

- 基线方案：`docs/gpu-translation-split-plan.md`
- 实施计划：`docs/plans/2026-02-14-gpu-translation-split-implementation.md`
- 实施日志：`docs/refactor/2026-02-14-split-pipeline-worklog.md`
- 内部接口契约：`docs/api/2026-02-14-internal-split-pipeline-contract.md`
- 审查报告：`docs/split-plan-review-2026-02-14.md`

## 文档治理与部署

- 文档优化计划：`docs/plans/2026-02-10-doc-optimization.md`
- 文档优化日志：`docs/refactor/2026-02-10-doc-optimization-worklog.md`
- 清理清单：`docs/refactor/2026-02-10-cleanup-manifest.md`
- CloudRun 混合部署计划：`docs/plans/2026-02-11-cloudrun-hybrid-implementation.md`
- CloudRun 混合部署文档：`docs/deployment/2026-02-11-82-cloudrun-hybrid.md`
- 部署来源注册：`docs/deployment/2026-02-14-deployment-registry.md`

## 交付规则

- 前端源码入库：`frontend/**`
- 构建产物不入库：`manga_translator/server/static/dist/**`
- 协作远端：`https://github.com/aakaka525-design/manga-translator-ui`
