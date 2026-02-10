# 文档风格与质量门槛

## 1. 目标

保证文档可执行、可追溯、可维护，避免信息分叉。

## 2. 写作约定

- 主语言：中文（英文仅保留必要导航）
- 路由/命令/API 使用反引号包裹
- 新增接口优先写入 `docs/api/*contract.md`
- README 只保留入口与关键能力，不复制整份接口表

## 3. 单一事实来源

- API 字段定义：`docs/api/*contract.md`
- 用户安装启动：`doc/INSTALLATION.md`
- CLI/Web 操作：`doc/CLI_USAGE.md`
- 历史记录：`doc/CHANGELOG_INDEX.md` + `doc/CHANGELOG_*.md`

## 4. 文档改动最小检查

提交前至少完成：

1. 入口一致：`/`、`/signin`、`/admin`、`/scraper`
2. 鉴权流程一致：`/auth/status`、`/auth/setup`、`/auth/login`
3. 坏链检查：Active 文档不存在本地缺失链接
4. `dist` 策略一致：`manga_translator/server/static/dist/**` 不入库

## 5. 历史文档策略

- 不回写历史 phase/changelog 内容
- 仅更新索引文档增强导航
- 若历史内容与现状冲突，在 Active 文档中给出“以当前契约为准”说明
