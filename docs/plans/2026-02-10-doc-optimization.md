# 2026-02-10 项目文档全仓库优化计划

## 目标

在不改动生产代码行为的前提下，完成全仓库文档的一致性优化：

1. 统一用户入口与工程入口导航。
2. 重写过时 README 文档，移除坏链与历史误导内容。
3. 统一 Web 路由、鉴权初始化、API 合同引用、`dist` 入库策略描述。
4. 保留历史 changelog/worklog 原文，仅通过索引增强可检索性。

## 范围

- 覆盖目录：`README.md`、`doc/`、`docs/`
- 不在范围：`manga_translator/**` 运行时代码、数据库结构、鉴权实现、前端运行逻辑

## 分层策略

- Active（持续维护）：用户使用、安装、CLI、API 合同、开发规范
- Legacy（保留但降级入口）：历史迁移入口说明与旧结构说明
- History（只追加索引，不回写）：phase worklog、历史 changelog

## 任务清单

- DOC-001：建立文档基线与工作日志
- DOC-002：新增统一入口索引（`doc/INDEX.md`、`docs/INDEX.md`）
- DOC-003：重写 `doc/README_CN.md` 与 `doc/README.md`
- DOC-004：统一安装与初始化流程说明
- DOC-005：统一 API 说明归属与引用
- DOC-006：新增 `doc/CHANGELOG_INDEX.md`
- DOC-007：清理坏链与陈旧术语（仅 Active 文档）
- DOC-008：补充文档维护规范与质量门槛
- DOC-009：文档交付闭环（7 字段记录 + 验证 + 提交）

## 验收标准

1. 新用户可按文档完成：安装 -> 启动 Web -> 初始管理员设置 -> 登录。
2. 从 README 或 CLI 文档可在 2 步内定位到 phase4 scraper 合同文档。
3. Active 文档不存在本地坏链。
4. `README`、`INSTALLATION`、`CLI_USAGE` 对入口、鉴权、`dist` 策略表述一致。
5. `doc/CHANGELOG_*.md` 内容保持不变，仅通过 `CHANGELOG_INDEX` 导航。

## 锁定约束

1. 本轮仅改文档，不改运行时行为。
2. 主语言中文；英文文档保留必要导航。
3. `manga_translator/server/static/dist/**` 继续不入库。
4. 历史 phase 文档与 changelog 仅做入口增强，不做语义改写。
