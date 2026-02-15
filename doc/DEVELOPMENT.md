# 开发者指南

## 目标

本文档聚焦当前仓库开发流程，并补充文档维护质量门槛，避免文档与代码漂移。

## 本地开发

### 环境

- Python 3.12
- Node.js 20+（前端）

### 启动方式

```bash
# Web 后端
python -m manga_translator web
```

### 前端

```bash
cd frontend
npm ci
npm run dev
# 或生产构建
npm run build
```

构建输出：`manga_translator/server/static/dist`（不入库）

## 测试建议

```bash
pytest -q tests/test_v1_routes.py tests/test_v1_scraper_phase2.py tests/test_v1_scraper_phase3.py tests/test_v1_scraper_phase4.py

cd frontend
npm test -- --run
npm run build
```

## 文档维护规范

### 文档检查清单

每次功能变更至少检查：

1. 入口一致：`/`、`/signin`、`/admin`、`/scraper`
2. 鉴权流程一致：`/auth/status -> /auth/setup -> /auth/login`
3. 坏链检查：Active 文档本地链接可达
4. 命令可执行：README/INSTALLATION/CLI 中关键命令可运行
5. `dist` 策略一致：产物不入库

### 文档更新映射

- 路由/页面改动：更新 `README.md`、`doc/INSTALLATION.md`
- 鉴权改动：更新 `README.md`、`doc/CLI_USAGE.md`、API contract
- API 字段改动：更新 `docs/api/*contract.md`（优先）并同步 `doc/CLI_USAGE.md` 概览
- 工程流程改动：更新 `doc/DEVELOPMENT.md` 与 `docs/DOC_STYLE.md`
- 历史阶段交付：更新 `docs/refactor/INDEX.md` 与对应 worklog

### 历史文档策略

- `doc/CHANGELOG_*.md`：只追加新文件，不回写历史内容
- `docs/refactor/*.md`、`docs/plans/*.md`：保留历史事实，不做语义重写
- 通过 `doc/CHANGELOG_INDEX.md`、`docs/refactor/INDEX.md` 提供导航

## 相关入口

- 用户文档总览：[`doc/INDEX.md`](INDEX.md)
- 工程文档总览：[`docs/INDEX.md`](../docs/INDEX.md)
- 文档风格规范：[`docs/DOC_STYLE.md`](../docs/DOC_STYLE.md)
