# 82 + Cloud Run 混合部署指南

## 目标

- 前端与状态后端部署在 `82.22.36.81`
- Cloud Run 仅承载翻译计算接口：`POST /internal/translate/page`
- 对外接口继续走 `82` 同源入口，不改变 `/api/v1/*` 使用方式

## 架构

1. 浏览器 -> Nginx (`82`)。
2. Nginx 将 `/api` `/auth` `/admin` `/output` 反代到本机 FastAPI。
3. FastAPI 章节任务按页调用 `TranslateExecutor`。
4. 当 `MANGA_TRANSLATE_EXECUTION_BACKEND=cloudrun` 时，FastAPI 调 Cloud Run 内部接口并落盘到本地 `/output`。

## 必要环境变量

82 后端：

- `MANGA_TRANSLATE_EXECUTION_BACKEND=local|cloudrun`
- `MANGA_CLOUDRUN_EXEC_URL=https://<cloud-run-service-url>`
- `MANGA_INTERNAL_API_TOKEN=<internal-token>`
- `MANGA_CLOUDRUN_EXECUTOR_RETRIES=2`
- `MANGA_CLOUDRUN_TIMEOUT_SEC=120`

Cloud Run 计算服务（compute-only，不加载 scraper）：

- `MANGA_INTERNAL_API_TOKEN=<same-token>`
- `MANGA_TRANSLATE_EXECUTION_BACKEND=local`
- `MANGA_CLOUDRUN_COMPUTE_ONLY=1`

Cloud Run 推荐资源（已实测）：

- `memory=8Gi`（`2Gi` 与 `4Gi` 在真实漫画页都出现 OOM）
- `cpu=4`
- `concurrency=1`
- `timeout=900s`（单页重型推理+远端模型调用需要更长超时窗口）
- `maxScale=2`（按配额与峰值再调）
- 镜像打包必须包含：
  - `dict/**`（HQ prompt 与系统提示词）
  - `fonts/**`（渲染字体）
  - `manga_translator/utils/panel/lib/**`（运行时依赖模块）

## 章节失败边界语义

- 章节逐页执行，已成功页保留。
- 失败页按 executor 重试策略重试。
- 超过重试上限后仅标记该页失败。
- 章节最终状态：
  - `success_count == 0` -> `error`
  - `success_count > 0 && failed_count > 0` -> `partial`
  - `failed_count == 0` -> `success`
- 前端可继续调用 `/api/v1/translate/page` 对失败页重试。

## gemini_hq 上下文策略

- 固定传前 3 页译文：`context_translations`
- 82 侧构建并传输，Cloud Run 不保留会话缓存

## 指标与阈值

- `cold_start_latency_p95`
- `single_page_p95`
- `chapter_10p_p95`
- `sse_delay_p95`
- `remote_503_rate`

告警建议：

- 连续 3 天 `cold_start_latency_p95 > 25s` 或 `single_page_p95 > 90s`，评审切 `min-instances=1`。
- `remote_503_rate > 1%`（15 分钟）触发告警。

## 传输与成本审计（一期二进制回传）

- 一期固定链路：Cloud Run 返回译图二进制 -> `82` 写入 `/output`。
- 章节维度记录项（建议写入日志或报表）：
  - `request_bytes_total`（上传原图总字节）
  - `response_bytes_total`（下载译图总字节）
  - `remote_elapsed_ms_total`（Cloud Run 端总耗时）
  - `translate_elapsed_ms_total`（章节总翻译耗时）
  - `transport_ratio = remote_elapsed_ms_total / translate_elapsed_ms_total`
- 评审触发建议：
  - 若 `transport_ratio` 长期 > `0.35`，或章节网络流量长期超预算，立项二期 `GCS 直写`（Cloud Run 产图直接写对象存储，82 仅拉取 URL）。

## 安全加固基线（上线前必做）

- 82 主机（Linux）：
  - 轮换 `root` 密码并禁用密码登录：`/etc/ssh/sshd_config` 设置 `PermitRootLogin no`、`PasswordAuthentication no`，仅保留密钥登录。
  - 新建最小权限部署用户（例如 `deploy`），服务用该用户运行。
  - 开启主机防火墙，仅放行 `22/80/443` 必需端口。
- Cloud Run：
  - 保持 `--no-allow-unauthenticated`，只允许受信服务账号调用。
  - `MANGA_INTERNAL_API_TOKEN` 不写死在镜像，放 Secret Manager 注入。
  - 82 到 Cloud Run 的调用携带 `X-Internal-Token`；token 轮换按月执行。
- 运维审计：
  - 记录管理员操作日志与部署变更日志。
  - 对 `remote_503_rate`、鉴权失败率、异常重试率设置告警并保留 30 天。

## 上线顺序

1. 先在 `82` 本机以 `local` backend 全量回归。
2. 部署 Cloud Run 计算服务并验证内部 token。
3. 灰度切换 `MANGA_TRANSLATE_EXECUTION_BACKEND=cloudrun`。
4. 观察 24h 指标与失败率，再决定是否扩容或常驻实例。

## 2026-02-11 实操记录（最新）

- Cloud Run 区域：`europe-west1`
- 计算服务：`manga-translator-compute`
- 当前稳定 revision：`manga-translator-compute-00011-wqp`
- 服务 URL：`https://manga-translator-compute-177058129447.europe-west1.run.app`
- 82 systemd 已固定：
  - `MANGA_TRANSLATE_EXECUTION_BACKEND=cloudrun`
  - `MANGA_CLOUDRUN_EXEC_URL=https://manga-translator-compute-177058129447.europe-west1.run.app`
- 实测结果（82 -> Cloud Run `POST /internal/translate/page`）：
  - `2Gi` 内存时：返回 `500`，Cloud Run 日志报 `Memory limit exceeded`
  - `4Gi` 内存时：真实漫画页仍可能 OOM（日志峰值约 `4384MiB`）
  - 升级到 `8Gi/4CPU/900s` 后：链路稳定，无 OOM 告警
- Gemini 模型约束（2026-02-11）：
  - 旧默认 `gemini-1.5-flash*` 在当前 Gemini API 上会返回 `404 model not found`
  - 生产建议固定：`GEMINI_MODEL=gemini-2.0-flash`
- Header 编码约束（2026-02-11）：
  - Cloud Run `internal/translate/page` 响应头需保证 ASCII 安全（非拉丁字符需编码），否则会触发 `UnicodeEncodeError` 并返回 500。

## Cloud Run GPU 落地状态（2026-02-11）

- 当前结论：`manga-translator-2602111442` 项目 GPU 配额为 `0`，暂时无法上线 GPU revision。
- 已执行验证：
  - `europe-west1` 直接更新现有服务到 L4 GPU：失败（with/without zonal redundancy 均 quota denied）
  - `us-central1` 新建 GPU 测试服务：同样失败（with/without zonal redundancy 均 quota denied）
- 已提交 quota preference（CLI）：
  - `run-l4-nozr-euw1` -> `NvidiaL4GpuAllocNoZonalRedundancyPerProjectRegion`
  - `run-l4-zr-euw1` -> `NvidiaL4GpuAllocPerProjectRegion`
  - 系统回写：`preferredValue=1`，`grantedValue=0`
- 追加排查（CLI）：
  - L4（no-zonal-redundancy）在 `us-central1/us-east1/us-east4/us-west1/asia-east1/asia-northeast1` 全部回写 `grantedValue=0`
  - RTX Pro 6000（no-zonal-redundancy）在 `europe-west1/us-central1` 全部回写 `grantedValue=0`
- 配额偏好对象（已创建）：
  - `run-l4-nozr-euw1`, `run-l4-zr-euw1`
  - `run-l4-nozr-uscentral1`, `run-l4-nozr-useast1`, `run-l4-nozr-useast4`, `run-l4-nozr-uswest1`, `run-l4-nozr-asiaeast1`, `run-l4-nozr-asianortheast1`
  - `run-rtx-nozr-europewest1`, `run-rtx-nozr-uscentral1`
- 阻塞解除条件：
  - 至少一个区域获得 `run.googleapis.com` 的 L4 GPU 配额（`grantedValue >= 1`）
  - 获批后复跑 GPU 部署命令并切流。
