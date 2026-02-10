# 漫画翻译器（中文入口）

本文档是当前项目的中文起始页。

## 项目简介

本仓库提供漫画翻译的桌面与 Web 双栈能力，当前推荐使用 Web 路径：

- 前端：Vue3
- 后端：FastAPI
- 鉴权：`/auth/login` + `X-Session-Token`
- Scraper：多 provider（`mangaforfree` / `toongod` / `generic`）

## 快速开始

### 1. 安装依赖

```bash
pip install -r requirements_cpu.txt
# 或根据硬件改用 requirements_gpu.txt / requirements_amd.txt
```

### 2. 启动 Web 服务

```bash
python -m manga_translator web
```

### 3. 构建前端（首次或前端改动后）

```bash
cd frontend
npm ci
npm run build
```

## Web 访问入口

- `/`：书架首页
- `/signin`：登录页
- `/admin`：管理页
- `/scraper`：爬虫页
- `/manga/:id`：漫画章节页
- `/read/:mangaId/:chapterId`：阅读页

## 鉴权初始化（首次部署）

系统没有默认账号密码。请按固定流程初始化：

1. `GET /auth/status`
2. 若 `need_setup=true`，执行 `POST /auth/setup`
3. 使用创建的账号执行 `POST /auth/login`
4. 后续请求在 Header 中携带 `X-Session-Token`

初始化示例：

```bash
curl -s http://localhost:8000/auth/status

curl -s -X POST http://localhost:8000/auth/setup \
  -H 'Content-Type: application/json' \
  -d '{"username":"admin","password":"ChangeMe123"}'
```

## 文档导航

- 文档总览：[`doc/INDEX.md`](INDEX.md)
- 安装指南：[`doc/INSTALLATION.md`](INSTALLATION.md)
- CLI/Web/API 用法：[`doc/CLI_USAGE.md`](CLI_USAGE.md)
- 工程侧文档：[`docs/INDEX.md`](../docs/INDEX.md)
- API 合同：[`docs/api/2026-02-10-v1-api-contract.md`](../docs/api/2026-02-10-v1-api-contract.md)

## 常见问题

### Q1：前端构建产物要提交到仓库吗？
不需要。`manga_translator/server/static/dist/**` 仅用于构建验证和部署产物，源码入库、产物不入库。

### Q2：登录默认账号密码是什么？
没有默认账号密码。必须先执行 `/auth/status` 与 `/auth/setup` 初始化管理员。

### Q3：历史 changelog 在哪里看？
见 [`doc/CHANGELOG_INDEX.md`](CHANGELOG_INDEX.md)。该索引只做导航，不回写历史内容。
