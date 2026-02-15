# 架构决策：翻译管线与部署策略

> **最后更新**: 2026-02-15

---

## 1. Split vs Unified 管线切换策略 (A1)

### 当前状态

- `split` 和 `unified` 两种管线均已实现并在生产环境中验证。
- 管线选择通过 82 executor 内部逻辑自动决定：
  - GPU Worker 可用 + split 端点可用 → `split`
  - 否则 → `unified` (fallback 到 `/internal/translate/page`)

### 切换策略

| 场景 | 使用管线 | 原因 |
|------|---------|------|
| 正常生产 | `split` | 吞吐量提升 1.5-1.7x |
| Cache miss / worker 重启 | 自动降级 `unified` | 无感知降级，无需人工干预 |
| Gemini key 异常 | `unified` (82 local) | 止血模式，82 本地翻译 |
| 新功能验证 | 可手动切换 | `MANGA_TRANSLATE_EXECUTION_BACKEND=local` |

### 灰度计划

- 当前：未设 AB 测试开关，`unified` 为默认管线（`config_manager.py` 默认值）。
- 运行时自动探测 GPU Worker 可用性后可升级到 `split`。
- 已有前端降级提示：`pipeline=fallback_to_unified` 时显示 Toast。
- 后续**计划**通过 `MANGA_SPLIT_PIPELINE_RATIO` 环境变量控制灰度比例（尚未实现）。

---

## 2. 缓存-翻译耦合说明 (A2)

### 当前架构

```
82 executor → POST /detect → GPU Worker (cache 在 GPU Worker 内存)
           → POST /render  → GPU Worker (通过 task_id 取 cache)
```

- Cache (`CtxCache`) 位于 GPU Worker 进程内，`max_size=24`，`TTL=300s`。
- 翻译 (`_translate_texts_for_split`) 当前在 **82 侧串行执行**（通过 `_split_translate_semaphore` 限流 `Semaphore(1)`），而非 GPU Worker。
- Cache 与检测/渲染耦合在 GPU Worker 进程中是**有意设计**，因为：
  - Context 对象包含完整模型推理结果（text_regions、原图数据），约 50-200MB
  - 跨网络传输 context 不现实（带宽/延迟成本远超本地内存访问）

### 当前 split 流程

1. `/detect` → GPU Worker 检测并缓存 context
2. 82 侧串行调用 Gemini 翻译（`_translate_texts_for_split`，`Semaphore(1)`）
3. `/render` → GPU Worker 接收译文 + task_id 恢复 cache → 渲染

> 翻译在 82 侧运行是因为 Gemini API 调用不依赖 GPU 算力。

---

## 3. 多平台部署决策 (A3 + P3)

### 当前生产用哪个？

| 平台 | 角色 | 状态 |
|------|------|------|
| Cloud Run (main1-487412) | **主选** GPU 计算 | ⚠️ 待 Gemini key 轮换后恢复 |
| PPIO RTX 4090 | **备选** GPU 计算 | ✅ 可用 |
| 82 local | **止血回退** | ✅ 当前使用 |

### 故障切换机制

- 当前：手动切换 `MANGA_TRANSLATE_EXECUTION_BACKEND` 环境变量
- 计划中：executor 自动探测 Cloud Run 可用性，失败后降级到 PPIO/local
- 未实现：自动 failover 需要在 executor 中增加 backend 优先级列表

---

## 4. 双鉴权系统淘汰计划 (S4)

### 现状

两套鉴权并行运行：

| 系统 | 路由 | 存储 | 状态 |
|------|------|------|------|
| 新系统 (v1) | `/auth/*`, `/api/v1/*` | bcrypt + JSON | ✅ 主推 |
| 旧系统 (admin) | `/admin/login`, `/admin/*` | 明文 → bcrypt | ⚠️ 待淘汰 |

### 淘汰时间线

1. **Phase 1 (已完成)**: 旧系统密码存储迁移到 bcrypt
2. **Phase 2 (待启动)**: 前端移除 `/admin/login` 入口，统一到 `/auth/signin`
3. **Phase 3 (待启动)**: 后端标记 `/admin/login` 为 deprecated（返回 301 到新路由）
4. **Phase 4 (计划)**: 删除旧鉴权代码路径

> 在 Phase 4 之前，旧路由仍可用但不推荐。

---

## 5. 服务命名重叠说明 (C6)

以下 3 对服务/文件名存在命名重叠，属于历史遗留：

| 文件 A | 文件 B | 职责区分 |
|--------|--------|---------|
| `config_manager.py` | `config_management_service.py` | 前者管理 JSON 配置加载，后者管理运行时配置状态 |
| `task_manager.py` | `translate_task_service.py` | 前者管理并发任务队列，后者管理翻译任务生命周期 |
| `main.py` (server) | `cloudrun_compute_main.py` | 前者全功能入口，后者 compute-only 入口 |

- 短期不合并（改名影响导入路径和测试）
- 后续重构时可考虑更清晰的命名约定：`xxx_store.py` / `xxx_orchestrator.py`
