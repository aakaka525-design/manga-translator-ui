# CLI 与 Web/API 使用指南

本文档提供两类能力：

1. CLI 本地翻译模式
2. Web/API 模式（包含 `/api/v1/*` 与 `/admin/*`）

## 1. CLI 本地翻译

### 基本命令

```bash
python -m manga_translator local -i manga.jpg
python -m manga_translator -i ./manga_folder/
```

### 常用参数

- `-i, --input`：输入文件或目录
- `-o, --output`：输出路径
- `--config`：配置文件路径
- `-v, --verbose`：详细日志
- `--overwrite`：覆盖输出

### 配置文件优先级

1. `examples/config.json`
2. `examples/config-example.json`

命令行参数优先于配置文件。

## 2. Web 服务运行

推荐启动顺序（固定）：

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements_cpu.txt
python scripts/check_runtime_deps.py
python -m manga_translator web
```

若为 GPU/AMD 环境，请将 `requirements_cpu.txt` 替换为对应依赖文件。

启动命令：

```bash
python -m manga_translator web
```

常用页面：

- `/`
- `/signin`
- `/admin`
- `/scraper`

## 3. 鉴权流程（Web/API）

无默认账号密码，首次必须初始化：

1. `GET /auth/status`
2. `POST /auth/setup`
3. `POST /auth/login`
4. 受保护接口携带 `X-Session-Token`

## 4. API 端点总览（精简）

### Auth

- `POST /auth/login`
- `POST /auth/logout`
- `GET /auth/check`
- `GET /auth/status`
- `POST /auth/setup`

### v1（详细字段请看契约）

- Manga: `/api/v1/manga*`
- Translate: `/api/v1/translate/*`
- Scraper: `/api/v1/scraper/*`（含 `/providers`、`/task/{task_id}`）
- Parser: `/api/v1/parser/*`
- Settings: `GET /api/v1/settings`、`POST /api/v1/settings/model`、`POST /api/v1/settings/upscale`
- System: `GET /api/v1/system/logs?lines=`（admin 权限）

设置与系统日志接口鉴权说明：

- `/api/v1/settings*`：需要 `X-Session-Token`
- `/api/v1/system/logs`：需要 admin（与 `/admin/logs` 权限一致，兼容 legacy `X-Admin-Token`）

### Admin（Scraper 可观测）

- `GET /admin/scraper/tasks`
- `GET /admin/scraper/metrics`
- `GET /admin/scraper/health`
- `GET /admin/scraper/alerts`
- `POST /admin/scraper/alerts/test-webhook`
- `GET /admin/scraper/queue/stats`

## 5. API 合同（Single Source）

- v1 总契约：[`docs/api/2026-02-10-v1-api-contract.md`](../docs/api/2026-02-10-v1-api-contract.md)
- Scraper phase4 S1：[`docs/api/2026-02-10-v1-scraper-phase4-s1-contract.md`](../docs/api/2026-02-10-v1-scraper-phase4-s1-contract.md)

> 本文档仅保留端点总览，字段细节统一在 contract 文档维护。

## 6. 前端构建产物策略

```bash
cd frontend
npm ci
npm run build
```

- 输出目录：`manga_translator/server/static/dist`
- 策略：只提交源码，不提交 `dist` 产物

## 7. Scraper 关键兼容字段

Scraper 请求体可选字段：

- `site_hint`: `mangaforfree | toongod | generic`
- `force_engine`: `http | playwright`

`GET /api/v1/scraper/task/{task_id}` 可选扩展字段：

- `persisted`, `created_at`, `updated_at`
- `retry_count`, `max_retries`, `next_retry_at`, `error_code`, `last_error`
- `queue_status`, `enqueued_at`, `dequeued_at`, `worker_id`

## 8. 文档导航

- 安装指南：[`doc/INSTALLATION.md`](INSTALLATION.md)
- 用户文档总览：[`doc/INDEX.md`](INDEX.md)
- 工程文档总览：[`docs/INDEX.md`](../docs/INDEX.md)
