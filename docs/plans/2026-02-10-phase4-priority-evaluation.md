# 2026-02-10 Phase4 Priority Evaluation (4-week window)

## 评估目标与边界

- 目标：判断是否立项四期（Scraper 运维可观测性方向）。
- 评估维度：价值（40）+ 成本（30）+ 风险（30）。
- 窗口：4 周；容量：1 人并行维护。
- 本文仅做评估，不实施生产改动。

## TASK 跟踪（评估回合）

| TASK-ID | 状态 | 改动文件 | 接口影响 | 验证命令 | 验证结果 | 提交哈希 |
|---|---|---|---|---|---|---|
| TASK-029 | completed | `docs/plans/2026-02-10-phase4-priority-evaluation.md`, `docs/refactor/2026-02-10-phase4-eval-worklog.md`, `docs/decisions/2026-02-10-phase4-go-no-go.md`, `docs/refactor/INDEX.md` | 无 | `ls docs/plans docs/refactor docs/decisions` | pass | N/A |
| TASK-030 | completed | `docs/plans/2026-02-10-phase4-priority-evaluation.md` | 无（证据采样） | `rg -n "IDEMPOTENT_WINDOW_MINUTES|/admin/scraper/metrics|task_logs|redis|workflow" manga_translator/server .github/workflows requirements_*.txt` | pass | N/A |
| TASK-031 | completed | `docs/plans/2026-02-10-phase4-priority-evaluation.md` | 候选接口草案（不实施） | `rg -n "候选接口草案 A|方案 S0|方案 S1|方案 S2" docs/plans/2026-02-10-phase4-priority-evaluation.md` | pass | N/A |
| TASK-032 | completed | `docs/plans/2026-02-10-phase4-priority-evaluation.md` | 无（成本/风险评估） | `rg -n "成本估算|风险登记表|Redis 故障|告警风暴" docs/plans/2026-02-10-phase4-priority-evaluation.md` | pass | N/A |
| TASK-033 | completed | `docs/plans/2026-02-10-phase4-priority-evaluation.md` | 无（验证场景设计） | `rg -n "评估验证场景|队列堆积|Redis 重启|Webhook 连续失败|鉴权回归" docs/plans/2026-02-10-phase4-priority-evaluation.md` | pass | N/A |
| TASK-034 | completed | `docs/decisions/2026-02-10-phase4-go-no-go.md`, `docs/refactor/2026-02-10-phase4-eval-worklog.md` | 决策输出（不实施） | `rg -n "总分矩阵|GO/NO-GO|结论|替代优化清单" docs/decisions/2026-02-10-phase4-go-no-go.md` | pass | N/A |

## TASK-030 三期现状证据表

| 证据ID | 代码/配置位置 | 当前能力 | 缺口描述 | 影响等级 |
|---|---|---|---|---|
| E-001 | `manga_translator/server/routes/v1_scraper.py` | 已有幂等窗口与重试（常量） | 参数硬编码，无法按环境动态调优 | 中 |
| E-002 | `manga_translator/server/routes/admin.py` | 已有 `/admin/scraper/tasks`、`/admin/scraper/metrics` | 无健康探针与告警事件流 | 高 |
| E-003 | `manga_translator/server/scraper_v1/task_store.py` | SQLite 持久化 + 分页/聚合 | 无实时队列/消费者概念 | 高 |
| E-004 | `manga_translator/server/core/logging_manager.py` | 日志队列已存在（内存 deque） | 无结构化指标导出、无告警通道 | 高 |
| E-005 | `frontend/src/views/AdminView.vue` | 管理页已展示 scraper 任务/指标 | 仅轮询展示，无告警看板与SLA视图 | 中 |
| E-006 | `requirements_cpu.txt` / `requirements_gpu.txt` | 当前依赖不含 Redis 客户端 | 引入 Redis 需新增依赖与部署要求 | 高 |
| E-007 | `.github/workflows/*` | 当前工作流偏构建发布 | 缺少 pytest/npm test 门禁及 Redis 集成测试流 | 中 |
| E-008 | `tests/test_v1_scraper_phase3.py` | 已覆盖重试/stale/admin 基线 | 未覆盖 Redis 失联、Webhook 失败策略 | 高 |
| E-009 | `docs/api/2026-02-10-v1-scraper-phase3-contract.md` | 三期接口文档完整 | 无 phase4 健康/告警/队列统计契约草案 | 中 |
| E-010 | 仓库整体 | 三期稳定性能力已落地 | 没有统一可观测SLO与运行基线 | 高 |

## 候选接口草案 A（仅用于评分，不实施）

### 新增管理端接口草案

1. `GET /admin/scraper/health`
2. `GET /admin/scraper/alerts`
3. `POST /admin/scraper/alerts/test-webhook`
4. `GET /admin/scraper/queue/stats`

### `GET /api/v1/scraper/task/{task_id}` 可选字段草案

- `queue_status?: "queued" | "running" | "retrying" | "done" | "failed"`
- `enqueued_at?: string`
- `dequeued_at?: string`
- `worker_id?: string`

## TASK-031 方案架构草案

### 方案 S0（对照组：维持三期）

- 组件（文字图）：`Client -> FastAPI -> SQLite(task_store)`
- 数据流：请求直入 API，任务状态写 SQLite，管理页轮询读取。
- 依赖清单：无新增。
- 接口影响：无。
- 优点：零迁移成本，风险最低。
- 局限：无法解决实时观测与告警缺口。

### 方案 S1（轻量：不引入 Redis）

- 组件（文字图）：`Client/Admin -> FastAPI -> SQLite + Metrics Aggregator + Webhook Sender`
- 数据流：任务生命周期写 SQLite；定时聚合指标；异常阈值触发 webhook。
- 依赖清单：可不引入 Redis；仅新增 webhook 发送与阈值配置模块。
- 接口影响：新增 health/alerts/queue-stats（queue 可基于 SQLite 近似统计）。
- 优点：改造面较小，4 周内可落地概率高。
- 局限：无真正实时队列能力，扩展上限有限。

### 方案 S2（主候选：SQLite+Redis 混合，Redis 强依赖）

- 组件（文字图）：`Client/Admin -> FastAPI -> Redis Queue/State Cache + SQLite Archive + Webhook`
- 数据流：下载任务先入 Redis 队列；worker 消费并写缓存状态；完成态归档 SQLite；告警由 Redis/SQLite 指标触发。
- 依赖清单：Redis 服务（强依赖）、Python Redis 客户端、健康检查与降级策略、Webhook 配置。
- 接口影响：草案 A 接口全部建议落地；task 状态增加 queue 字段。
- 优点：实时性和扩展性最好，后续多实例扩展路径清晰。
- 局限：部署与运维复杂度显著上升，1 人/4 周风险高。

### S2 上线前置条件（强依赖）

1. 目标环境具备可用 Redis（至少主从或托管实例），并有备份/恢复流程。
2. Redis 可用性与延迟有基础监控（否则触发一票否决）。
3. Webhook 通道具备稳定 SLA（至少可观测成功率与重试策略）。
4. CI 补齐 Redis 集成测试作业与失败阻断规则。

## TASK-032 成本估算与风险登记

### 成本估算（1 人并行维护）

| 方案 | 估算人天 | 主要工作包 | 置信度 |
|---|---:|---|---|
| S0 | 1-2 | 文档与运营约束整理 | 高 |
| S1 | 8-12 | 指标/健康/告警模块 + 管理页扩展 + 回归测试 | 中 |
| S2 | 18-26 | Redis 队列改造、状态一致性、告警链路、CI 集成、回滚机制 | 中低 |

### 风险登记表

| 风险ID | 触发条件 | 影响 | 缓解策略 | 残余风险 |
|---|---|---|---|---|
| R-001 | Redis 故障或抖动 | 任务阻塞、状态不可读 | 连接池超时+熔断；管理页健康告警；应急回退到只读 SQLite | 中高 |
| R-002 | Webhook 不可达 | 告警漏发 | 指数重试+死信记录+管理页告警补偿 | 中 |
| R-003 | 队列积压 | 延迟升高、用户体验下降 | 并发阈值 + 限流 + 积压看板 + 自动告警 | 中 |
| R-004 | 告警风暴 | 噪音过高、真实告警淹没 | 聚合窗口、去重、冷却时间、分级阈值 | 中 |
| R-005 | 回滚失败 | 发布窗口拉长 | 双写期/特性开关/回滚演练脚本 | 中高 |
| R-006 | 单人维护上下文切换 | 工期偏移 | 分阶段里程碑，先交付可观测最小闭环 | 中 |

## TASK-033 评估验证场景（若立项后必须通过）

1. 队列堆积场景  
   - 方法：模拟持续高于消费能力的任务注入。  
   - 通过标准：`queue/stats` 显示积压增长并在阈值内告警；管理页可见积压趋势。
2. Redis 重启场景  
   - 方法：在活跃任务期间重启 Redis。  
   - 通过标准：服务在规定时间内恢复；任务状态一致性可解释；无 silent failure。
3. Webhook 连续失败场景  
   - 方法：模拟 webhook 5xx/超时。  
   - 通过标准：重试策略触发，失败事件留痕，可在管理页追溯。
4. 管理页可观测一致性场景  
   - 方法：对比 API 与管理页展示的任务总量、错误码、延迟。  
   - 通过标准：关键指标偏差 < 1%。
5. 权限与鉴权回归场景  
   - 方法：未登录/非 admin 访问新增管理端接口。  
   - 通过标准：严格返回既有鉴权错误，不泄露系统状态明细。

## 评估中间结论（供 TASK-034 决策引用）

- 在“4 周 + 1 人并行维护”约束下，S2（Redis 强依赖）有明显收益，但成本与运维风险超出可控区间。
- 若强行推进 S2，最可能失效点是：运维保障不足 + CI 缺少 Redis 门禁 + 告警链路不可用。
- 更稳妥路径：先做 S1 形成可观测闭环，再以明确前置条件评估 S2。
