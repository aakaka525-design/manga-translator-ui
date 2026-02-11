# 项目审核评估报告

> **审核日期**：2026-02-10 | **项目版本**：v2.0.x（Scraper Phase4 S1）

## 审核摘要

| 维度 | 评级 | 关键发现 |
|------|------|----------|
| **安全性** | 🟡 已收敛 | P0 与旧链路限流问题已修复；仍建议推进统一鉴权迁移 |
| **架构** | 🟠 有债务 | 巨型 God Class × 2、双鉴权并行、命名重叠 |
| **测试** | 🟡 部分覆盖 | 前端 48/48 ✅；后端回归已接入 CI，核心服务深度单测持续补齐中 |
| **输入校验** | 🟡 混合 | 新端点 Pydantic ✅、旧端点无校验 |
| **错误处理** | 🟡 可改进 | 142+ 处宽泛 `except Exception` |
| **前端** | 🟡 可改进 | API 层薄弱、大型 Store/View |
| **模块依赖** | 🟢 健康 | 60 个模块、193 条边、无循环依赖 |
| **文档** | 🟢 良好 | API 契约文档准确、双体系清晰 |
| **部署** | 🟢 完善 | CI/CD 构建完整、Docker 支持 |

---

## 修复进展（2026-02-10 当日回填）

| 审计项 | 状态 | 备注 |
|--------|------|------|
| 明文密码存储与比对（P0-1） | ✅ 已修复 | `/admin/*`、`/user/login` 改为 bcrypt 优先 + legacy 迁移；配置加载阶段自动迁移旧明文 |
| CORS 配置违规（P0-2） | ✅ 已修复 | `allow_origins=["*"]` 场景下 `allow_credentials=False`，并支持 `MANGA_TRANSLATOR_CORS_ORIGINS` 配置 |
| 路径遍历风险（P0-3） | ✅ 已修复 | `/result/{folder_name}/final.png`、`/results/{folder_name}` 新增目录名校验与路径边界检查 |
| 相关回归测试 | ✅ 已补齐 | 新增 `tests/test_security_audit_fixes.py` 并通过 |
| 旧端点无速率限制（P1-6） | ✅ 已修复 | `/admin/login`、`/admin/change-password`、`/user/login` 接入 5 分钟窗口/10 次失败限流，超限返回 `429 RATE_LIMIT_EXCEEDED` |
| CI 无测试步骤（P1-7 部分） | ✅ 已修复 | `build-and-release.yml` 与 `docker-build-push.yml` 新增后端测试门禁 job，构建前执行 pytest |
| 核心服务单测缺口（P1-7 部分） | ✅ 已修复（首批） | 新增 `tests/test_core_services.py` 覆盖 `AccountService`、`SessionService`、`PermissionService` 关键路径 |
| 安全支撑服务单测缺口（P1-7 部分） | ✅ 已修复（第二批） | 新增 `tests/test_security_support_services.py` 覆盖 `SessionSecurityService` 与 `AuditService` 关键行为 |
| 中间件与配额服务单测缺口（P1-7 部分） | ✅ 已修复（第三批） | 新增 `tests/test_middleware_and_quota_services.py` 覆盖 `require_auth/require_admin` 关键分支与 `QuotaManagementService` 主流程 |
| 配额-用户组接口不一致（运行缺陷） | ✅ 已修复 | `GroupService` 新增 `get_group_config` 兼容方法，修复 `QuotaManagementService` 调用失败问题 |
| 翻译“成功但无译图”语义偏差（运行缺陷） | ✅ 已修复 | `/api/v1/translate/*` 收敛为“`regions_count > 0` 且 `output_changed=True` 才算成功”；并统一 `target_language` 短码映射（`zh -> CHS`） |
| 翻译落盘失败导致“显示成功但图片不变”（运行缺陷） | ✅ 已修复 | `v1_translate` 对 JPEG 输出自动处理 RGBA->RGB，避免 `cannot write mode RGBA as JPEG` 回退；失败分支清理同 stem 历史译图，避免前端误判 translated；翻译超时改为环境变量可配置（默认 600s） |
| Vue/API 与 Qt/CLI 链路一致性与 503 收敛（运行缺陷） | ✅ 已修复 | `v1_translate` 新增章节级 `pipeline/stage_elapsed_ms/failure_stage` 诊断字段；`single_page` 模式强制串行避免共享翻译器竞态；`web` 模式 `use_gpu` 默认对齐配置文件；渲染多边形并集改为 `_safe_union_polygons` 容错；实图复测（同一张图）CLI `54.058s`，API `48.590s`，两侧均成功产图且 API 无 fallback/503 |

---

## 🔴 P0 — 历史发现（已修复）

> 说明：本节保留原始审计发现作为追溯证据，当前状态以“修复进展（2026-02-10 当日回填）”表格为准。

### 1. 明文密码存储与比对（3 处）

| 位置 | 行号 | 问题 |
|------|------|------|
| `manga_translator/server/routes/admin.py` | L54-99 | `/admin/setup`、`/admin/login`、`/admin/change-password` 明文比对 |
| `manga_translator/server/routes/web.py` | L252 | `/user/login` 用户密码明文比对 (`password == user_access.get('user_password', '')`) |
| `manga_translator/server/core/auth.py` | 全文 | `admin_login`、`setup_admin_password`、`change_admin_password` 均为明文 |

**对比**：新鉴权系统 `/auth/*` 使用 `AccountService` + bcrypt 哈希 ✅

---

### 2. CORS 配置违规

- **位置**：`manga_translator/server/main.py` L221-227
- **问题**：`allow_origins=["*"]` + `allow_credentials=True` 违反安全规范
- **建议**：生产环境限定具体域名；开发环境可保留 `*` 但关闭 `allow_credentials`

---

### 3. 路径遍历风险

- **位置**：`manga_translator/server/routes/web.py` L101, L168
- **问题**：`folder_name` 参数直接拼接到 `os.path.join(result_dir, folder_name)` 中，未做路径清理
- **攻击方式**：请求 `/results/../../../etc/passwd` 等可能读取任意文件
- **建议**：使用 `os.path.basename(folder_name)` 或验证结果路径不包含 `..`

---

### 4. 巨型 God Class

| 文件 | 大小 | 行数 | 方法数 | 职责 |
|------|------|------|--------|------|
| `manga_translator/manga_translator.py` | 247KB | 4,790 | 71 | 完整翻译管线（检测→OCR→翻译→修复→渲染） |
| `desktop_qt_ui/app_logic.py` | 170KB | 3,366 | 91 | Qt 桌面端全部业务逻辑 |

---

## 🟠 P1 — 重要（应尽快处理）

### 5. 双鉴权系统并行运行

| 维度 | 旧系统 (`/admin/*`, `/user/login`) | 新系统 (`/auth/*`) |
|------|-------------------------------------|---------------------|
| 密码存储 | 明文 `admin_config.json` | bcrypt `accounts.json` |
| Token 存储 | 内存 `set()`，无持久化 | JSON 文件持久化 |
| 过期机制 | ❌ 无 | ✅ 60 分钟超时 |
| 速率限制 | ✅ 5 分钟窗口/10 次失败（legacy 回溯补齐） | ✅ `SessionSecurityService` |
| 审计日志 | ❌ 无 | ✅ `AuditService` |
| 权限模型 | Token 一刀切 | ✅ RBAC + 用户组 |

中间件 `require_admin`（`middleware.py`）同时兼容两套 token。

---

### 6. 旧端点无速率限制

- **状态**：✅ 已修复（2026-02-10）
- `/admin/login`、`/admin/change-password`、`/user/login` 已接入登录失败限制（5 分钟窗口/10 次上限）
- 超限行为：返回 `429`，错误码 `RATE_LIMIT_EXCEEDED`，并带 `retry_after`
- **对比**：新系统 `session_security_service.py` 仍保留独立速率限制逻辑

---

### 7. 测试覆盖率

**前端**：✅ 20 个测试文件，49 个测试用例，全部通过

**后端覆盖现状**：
- ✅ 已新增：`account_service`、`session_service`、`permission_service` 核心行为测试（`tests/test_core_services.py`）
- ✅ 已新增：`session_security_service`、`audit_service` 核心行为测试（`tests/test_security_support_services.py`）
- ✅ 已新增：`middleware`、`quota_service` 主流程测试（`tests/test_middleware_and_quota_services.py`）
- ⏳ 待补：`quota_service` 调度/跨日重置等深度场景

**CI/CD（已修复）**：
- `build-and-release.yml` 已新增 `test-suite` 任务，构建前执行后端回归测试
- `docker-build-push.yml` 已新增 `test-before-build` 任务，镜像构建前执行后端回归测试

---

### 8. 宽泛异常捕获

- **统计**：142+ 处 `except Exception as e:` 或 `except Exception:`
- **分布**：routes/ 目录集中（admin.py 11 处、history.py 8 处、logs.py 11 处、resources.py 11 处等）
- **风险**：可能吞掉关键错误（如数据库连接失败、权限异常），增加调试难度
- **建议**：针对性捕获具体异常类型，避免吞掉 `KeyboardInterrupt`、`SystemExit` 等

---

## 🟡 P2 — 改进建议

### 9. 输入校验不一致

| 端点类型 | 校验方式 | 问题 |
|----------|----------|------|
| 新端点（`/auth/*`, `/groups/*` 等） | Pydantic BaseModel（30 个 Request 类） | ✅ 良好 |
| 旧 admin 端点（`/admin/setup`, `/admin/login`） | `Form(...)` 无额外约束 | ⚠️ 密码长度仅在 setup 检查，login 无校验 |
| `/user/login` | `Form(...)` | ⚠️ 无任何校验 |

---

### 10. 前端 API 层碎片化

- `frontend/src/api/index.js` 仅 159 行，覆盖 auth/manga/translate/system 4 组 API
- scraper 相关 API（93 个函数）直接在 `stores/scraper.js` 中使用 `authFetch`，未走统一 axios 实例
- **影响**：两套请求拦截逻辑、两套错误处理、两套 token 注入

---

### 11. 前端大型文件

| 文件 | 大小 | 行数 | 函数数 |
|------|------|------|--------|
| `frontend/src/stores/scraper.js` | 45KB | 1,319 | 93 |
| `frontend/src/views/ScraperView.vue` | 31KB | 577 | 70 |
| `manga_translator/server/routes/v1_scraper.py` | 45KB | — | — |
| `manga_translator/server/routes/translation.py` | 61KB | — | — |

---

### 12. 核心服务命名重叠

| 文件对 | 可能的职责重叠 |
|--------|---------------|
| `core/config_manager.py` vs `core/config_management_service.py` | 配置管理 |
| `core/permission_service.py` vs `core/permission_service_v2.py` | 权限管理 |
| `core/group_service.py` vs `core/group_management_service.py` | 用户组管理 |

---

## 🟢 P3 — 低优先级 / 已确认正常

### 13. 模块依赖（已通过）

- 60 个服务器模块、193 条导入边、**无循环依赖** ✅

### 14. API 契约文档（已通过）

- `docs/api/2026-02-10-v1-api-contract.md` 覆盖 25 个端点 + SPA 路由，与实现基本一致 ✅

### 15. Qt 桌面端

- `desktop_qt_ui/` 标记为"历史能力保留"
- `app_logic.py` 170KB God Class，如无持续维护计划建议归档冻结

### 16. 文档细节

- Changelog 存在版本号跳跃（缺 v1.7.2, v1.8.3, v1.8.8 等）— 不影响功能但影响追溯
- `.gitignore` 存在重复规则 — 可精简

### 17. 环境安全

- `.env` 已被 `.gitignore` 覆盖 ✅
- `presets/` 目录（含 API Key 配置）已排除 ✅
- 启动时打印 API Key 名称但不打印值 ✅

---

### 18. Web/API GPU 启动路径一致性（2026-02-11）

- **状态**：✅ 已修复
- **问题**：仅通过 `python -m manga_translator web` 走 `run_server()` 时会显式写入 `server_config.use_gpu`；直接 `uvicorn manga_translator.server.main:app` 启动可能落回默认 `False`。
- **修复**：
  - 新增运行时解析函数 `_resolve_runtime_use_gpu()`（优先级：CLI 显式 > `MT_USE_GPU` > `examples/config.json` > `False`）。
  - 新增 startup 兜底 `_ensure_runtime_server_config()`，覆盖直接 `uvicorn` 启动路径。
  - `prepare_translator_params()` 仅在 runtime 配置已初始化时覆盖 `cli.use_gpu`，未初始化保留配置文件值。
- **验证证据**：
  - `python -m manga_translator web ...` 日志：`运行时配置: use_gpu=True, source=run_server`
  - `uvicorn manga_translator.server.main:app ...` 日志：`运行时配置: use_gpu=True, source=startup_auto`
  - `MT_USE_GPU=false uvicorn ...` 日志：`运行时配置: use_gpu=False, source=startup_auto`
- **影响**：不同启动方式下翻译链路 GPU 选择一致，避免诊断脚本/服务部署出现“同配置却走 CPU 慢路径”的偏差。

---

### 19. API 核心链路慢路径收敛（2026-02-11）

- **状态**：✅ 已修复
- **问题根因**：`get_ctx/_run_translate_sync` 直调路径在 runtime 未初始化时，`get_global_translator()` 可能使用默认 `use_gpu=False`，导致翻译器回落 CPU，表现为 API 路径显著慢于 Qt/CLI（可达 220s+）。
- **修复内容**：
  - `task_manager` 新增 lazy runtime 初始化兜底：`_resolve_runtime_use_gpu()` + `_ensure_runtime_for_translator()`。
  - `get_global_translator()` 在构建翻译器前自动执行 lazy init（`source=lazy_translator_init`）。
  - `request_extraction._run_translate_sync/_run_translate_batch_sync` 在获取全局翻译器前显式确保 runtime 已初始化。
  - `main.py` 的 runtime 解析改为复用 `task_manager` 统一逻辑，避免分散实现漂移。
  - 诊断脚本（`test_vue_api_path.py`、`test_vue_api_path_timed.py`、`test_deep_diagnosis.py`）统一先做 runtime 初始化，并输出 `runtime source/use_gpu/translator.device`。
- **验证证据**：
  - 定向回归：`pytest -q tests/test_runtime_gpu_lazy_init.py tests/test_v1_translate_concurrency.py tests/test_v1_routes.py` → `36 passed`
  - 全量回归：`pytest -q` → `121 passed, 1 skipped`
  - 实图对照（同一张 `chapter-1/001.jpg`）：
    - API：`test_vue_api_path_timed.py` → `TOTAL_get_ctx=57.11s`, `translator.device=mps`
    - Qt/CLI：`test_qt_cli_path_timed.py` → `TOTAL_translate_batch=55.96s`, `translator.device=mps`
    - 耗时比：`57.11 / 55.96 = 1.02`（满足阈值 `<= 1.3`）
- **影响**：API 核心链路与 Qt/CLI 在设备判定和耗时表现上已对齐；“脚本路径假慢”被消除。

---

## 修复优先级路线图（建议）

| 阶段 | 任务 | 预估工时 |
|------|------|----------|
| **第一周** | 废弃旧 admin/web 明文密码端点、修正 CORS、修复路径遍历 | 2-3 天 |
| **第二周** | CI 添加自动化测试步骤、核心服务补充单元测试 | 3-5 天 |
| **第三周** | 统一鉴权系统迁移、旧端点添加速率限制或废弃 | 3-5 天 |
| **后续** | 拆分 God Class、精化异常捕获、前端 API 层统一 | 5-10 天 |
