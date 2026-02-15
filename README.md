# Manga Translator UI

面向漫画翻译工作流的本地化项目，包含：

- FastAPI 后端（鉴权、翻译、爬虫、管理）
- Vue3 前端（`/signin`、`/`、`/scraper`、`/admin` 等页面）

> 项目基于上游 `manga-image-translator` 能力演进，当前仓库以本项目文档与接口契约为准。

## 文档入口

- 用户文档入口：[`doc/INDEX.md`](doc/INDEX.md)
- 工程文档入口：[`docs/INDEX.md`](docs/INDEX.md)
- 混合云部署指南：[`docs/deployment/2026-02-11-82-cloudrun-hybrid.md`](docs/deployment/2026-02-11-82-cloudrun-hybrid.md)

## 快速开始（源码运行）

1. 创建并激活 Python 虚拟环境：

```bash
python -m venv .venv
source .venv/bin/activate
```

2. 安装 Python 依赖（按硬件选择一套）：

```bash
pip install -r requirements_cpu.txt
# 或
pip install -r requirements_gpu.txt
# 或
pip install -r requirements_amd.txt
```

3. 运行前置检查（Python 版本与关键依赖）：

```bash
python scripts/check_runtime_deps.py
```

4. 启动 Web 服务：

```bash
python -m manga_translator web
```

5. 首次前端构建（仅首次或前端代码有改动时）：

```bash
cd frontend
npm ci
npm run build
```

6. 访问页面：
- 首页：`http://localhost:8000/`
- 登录页：`http://localhost:8000/signin`
- 管理页：`http://localhost:8000/admin`
- 爬虫页：`http://localhost:8000/scraper`

前端开发模式（可选）：

```bash
cd frontend
npm ci
npm run dev
```

开发模式下 `/api`、`/auth`、`/admin` 会代理到本地后端 `http://localhost:8000`。

## 鉴权初始化（无默认账号密码）

系统没有预置默认账号。首次使用请按以下流程初始化管理员：

1. 查询状态：`GET /auth/status`
2. 若 `need_setup=true`，执行初始化：`POST /auth/setup`
3. 使用新建账号登录：`POST /auth/login`
4. 后续请求携带：`X-Session-Token`

示例：

```bash
curl -s http://localhost:8000/auth/status

curl -s -X POST http://localhost:8000/auth/setup \
  -H 'Content-Type: application/json' \
  -d '{"username":"admin","password":"ChangeMe123"}'

curl -s -X POST http://localhost:8000/auth/login \
  -H 'Content-Type: application/json' \
  -d '{"username":"admin","password":"ChangeMe123"}'
```

## API 与管理端契约

- v1 总契约：[`docs/api/2026-02-10-v1-api-contract.md`](docs/api/2026-02-10-v1-api-contract.md)
- Scraper phase4 S1 契约：[`docs/api/2026-02-10-v1-scraper-phase4-s1-contract.md`](docs/api/2026-02-10-v1-scraper-phase4-s1-contract.md)

管理端 Scraper 可观测接口（admin 权限）：

- `GET /admin/scraper/health`
- `GET /admin/scraper/alerts`
- `POST /admin/scraper/alerts/test-webhook`
- `GET /admin/scraper/queue/stats`

## 前端构建产物策略

- 构建输出目录：`manga_translator/server/static/dist`
- Git 策略：仅提交前端源码，不提交构建产物目录

## 历史记录

- 变更日志索引：[`doc/CHANGELOG_INDEX.md`](doc/CHANGELOG_INDEX.md)
- 重构实施日志索引：[`docs/refactor/INDEX.md`](docs/refactor/INDEX.md)
