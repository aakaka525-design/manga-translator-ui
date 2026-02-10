# 安装指南（当前架构）

本文档覆盖当前仓库的可执行安装路径，并与 Web 路由/鉴权流程保持一致。

## 系统要求

- Python 3.12（建议）
- Node.js 20+（仅前端构建需要）
- 可选 GPU 依赖（NVIDIA/AMD）

## 方式一：源码安装（推荐）

### 1. 获取代码

```bash
git clone https://github.com/hgmzhn/manga-translator-ui.git
cd manga-translator-ui
```

### 2. 创建虚拟环境并激活

```bash
python -m venv .venv
source .venv/bin/activate
```

### 3. 安装依赖

```bash
# CPU
pip install -r requirements_cpu.txt

# NVIDIA GPU
# pip install -r requirements_gpu.txt

# AMD
# pip install -r requirements_amd.txt
```

### 4. 依赖检查

```bash
python scripts/check_runtime_deps.py
```

### 5. 启动 Web 服务

```bash
python -m manga_translator web
```

### 6. 构建前端（首次或前端改动后）

```bash
cd frontend
npm ci
npm run build
```

- 输出目录：`manga_translator/server/static/dist`
- Git 策略：构建产物不入库（仅源码入库）

### 7. 访问入口

- `http://localhost:8000/`
- `http://localhost:8000/signin`
- `http://localhost:8000/admin`
- `http://localhost:8000/scraper`

### 8. 前端开发模式（可选）

```bash
cd frontend
npm ci
npm run dev
```

开发模式下 `/api`、`/auth`、`/admin` 会代理到后端 `http://localhost:8000`。

## 首次管理员初始化

> 系统没有默认账号密码。

1. 查询初始化状态：

```bash
curl -s http://localhost:8000/auth/status
```

2. 如果返回 `need_setup=true`，创建管理员：

```bash
curl -s -X POST http://localhost:8000/auth/setup \
  -H 'Content-Type: application/json' \
  -d '{"username":"admin","password":"ChangeMe123"}'
```

3. 登录获取会话令牌：

```bash
curl -s -X POST http://localhost:8000/auth/login \
  -H 'Content-Type: application/json' \
  -d '{"username":"admin","password":"ChangeMe123"}'
```

4. 访问受保护接口时携带：`X-Session-Token`

## 方式二：Qt 桌面启动（可选）

```bash
python -m desktop_qt_ui.main
```

> Qt 路径保留用于兼容与参考，不影响当前 Web 主线文档。

## Docker（可选）

如需容器化运行，请确保镜像和命令与当前仓库版本一致。推荐优先使用源码运行路径验证功能一致性。

## 常见问题

### 前端空白页

- 确认已执行 `npm run build`
- 确认 `manga_translator/server/static/dist/index.html` 存在

### 登录失败

- 先检查 `/auth/status` 是否需要初始化
- 如已初始化，确认登录用的是 `/auth/login` 而非历史旧接口

### 文档入口

- 用户文档总览：[`doc/INDEX.md`](INDEX.md)
- 工程文档总览：[`docs/INDEX.md`](../docs/INDEX.md)
