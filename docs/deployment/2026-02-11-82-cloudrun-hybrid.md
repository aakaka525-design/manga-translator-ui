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
  - 生产建议固定：`GEMINI_MODEL=gemini-3-flash-preview`
  - fallback 固定：`GEMINI_FALLBACK_MODEL=gemini-2.5-flash`（`gemini-2.0-flash` 已弃用并在运行时归一化到 2.5）
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

## Cloud Run GPU 收敛复测（`onyx-hangout-468807-a4`，2026-02-11）

- 项目与服务：
  - project: `onyx-hangout-468807-a4`
  - service: `manga-translator-compute`
  - 起始稳定 revision: `manga-translator-compute-00004-rxg`
- GPU 镜像构建：
  - image: `gcr.io/onyx-hangout-468807-a4/manga-translator-compute:gpu-20260211-211034`
  - digest: `sha256:5b6c78081b4bcd696efcc212010878179ff42ce523bfbd0e16c5df074c3f1fec`
  - build: `364f862b-9a8b-4fef-b08f-8a4a0b54f57e`（SUCCESS）
- europe-west1 验证结果：
  - `00007-25f`：镜像与 L4 规格已挂载（`nvidia.com/gpu: 1`, `nodeSelector=nvidia-l4`），最终未 Ready。
  - `00008-k77`：明确报错 `Quota exceeded for total allowable count of GPUs per project per region`。
- us-central1 回退结果：
  - `--no-gpu-zonal-redundancy`：报错无对应 quota。
  - `--gpu-zonal-redundancy`：同样报错无对应 quota。
- quota preference 结果（run.googleapis.com）：
  - `l4-nozonal-euw1`、`l4-zonal-euw1`、`run-l4-nozr-uscentral1`、`run-l4-zr-uscentral1`
  - 统一回写：`preferredValue=1`，`grantedValue=0`
- 稳定性回退（已执行）：
  - 通过 `gcloud run services replace` 回写 CPU 基线模板。
  - 当前稳定 revision: `manga-translator-compute-00009-pv4`（`Ready=True`，流量 100%）。
  - 服务 URL：`https://manga-translator-compute-814352053861.europe-west1.run.app`
- 当前烟测（CPU）：
  - `POST /internal/translate/page`（真实样图 `001.jpg`）返回 `HTTP 200`
  - 总耗时 `444.178s`，输出 `738791 bytes`，`fallback_used=0`
  - 结论：链路可用但仍是 CPU 性能，不满足 GPU 提速目标。

### 下一步（解锁条件）

1. 至少一个目标区域获得 `NvidiaL4GpuAlloc*` 的 `grantedValue >= 1`。
2. 获批后复跑同镜像同参数部署（先 `europe-west1`，失败再 `us-central1`）。
3. GPU revision Ready 后再执行 82 挂接切换与 CPU/GPU 性能对照验收。

## Cloud Run GPU 正式部署（`gen-lang-client-0238401140`，2026-02-12）

- 部署项目：`gen-lang-client-0238401140`
- 区域：`europe-west1`
- 服务：`manga-translator-compute`
- 镜像：`gcr.io/gen-lang-client-0238401140/manga-translator-compute:gpu-20260212-003244`
- 镜像 digest：`sha256:be2d6e9f598ad6603d06fae703caf7ebd52c4015b3abfaff173c41df4e1d9ddb`
- Cloud Build：`ae90b109-9e42-43c5-a003-8f62edeec8f7`（SUCCESS）
- 当前 ready revision：`manga-translator-compute-00001-44n`（created=ready，流量 100%）
- 服务 URL：`https://manga-translator-compute-3lzbxzz5dq-ew.a.run.app`

### 资源规格（运行中）

- `nvidia.com/gpu: 1`
- `nodeSelector: run.googleapis.com/accelerator=nvidia-l4`
- `cpu=4`
- `memory=16Gi`
- `concurrency=1`
- `timeout=900`
- `maxScale=1`
- `cpu-throttling=false`（instance-based billing）
- `gpu-zonal-redundancy-disabled=true`

### 内部翻译烟测（真实样图）

- 测试端点：`POST /internal/translate/page`
- 鉴权：`X-Internal-Token`（与 82 后端一致）
- 样图：`docs/perf/artifacts/2026-02-10-real-image-view/raw/bench_manga/chapter_bench/001.jpg`
- 连续 3 次结果：
  - run1: `HTTP=200`, `TOTAL=29.065804s`, `SIZE=742323`, `x-fallback-used=0`, `x-remote-elapsed-ms=26568`
  - run2: `HTTP=200`, `TOTAL=29.261523s`, `SIZE=742323`, `x-fallback-used=0`, `x-remote-elapsed-ms=26644`
  - run3: `HTTP=200`, `TOTAL=26.192682s`, `SIZE=742323`, `x-fallback-used=0`, `x-remote-elapsed-ms=23491`
- 结论：单图烟测稳定通过，未出现 503。

### 82 服务器切换结果

- systemd 环境变量已生效：
  - `MANGA_TRANSLATE_EXECUTION_BACKEND=cloudrun`
  - `MANGA_CLOUDRUN_EXEC_URL=https://manga-translator-compute-3lzbxzz5dq-ew.a.run.app`
  - `MANGA_CLOUDRUN_TIMEOUT_SEC=900`
  - `MANGA_CLOUDRUN_EXECUTOR_RETRIES=2`
- 服务状态：`manga-translator.service` = `active`
- 路由可达性（82 本机）：`/`、`/signin`、`/scraper`、`/manga/test-id`、`/read/m1/c1` 均 `HTTP 200`
- 当前联调限制：`/auth/status` 仍是 `need_setup=true`，未执行登录后端到端翻译 UI 场景。

### 性能对照（GPU vs CPU 基线）

- CPU 基线（历史同样图、Cloud Run CPU revision）：`444.178s`
- GPU 当前实测（3 次均值）：约 `28.17s`
- 提升幅度：约 `93.7%`（显著超过“至少 30% 改善”门槛）
- 结论：GPU 计算服务已达到上线目标，可作为 82 的 cloudrun backend 使用。

## 82 图片加载故障修复（`/data` 反代缺失，2026-02-12）

- 问题现象：
  - 前端章节页显示图片加载失败。
  - `http://127.0.0.1:8000/data/raw/...jpg` 返回 `image/jpeg`；
  - `http://127.0.0.1/data/raw/...jpg` 返回 `text/html`（被 SPA fallback 吞掉）。
- 根因：
  - Nginx 缺少 `location /data/` 反代，`/data/*` 请求落入 `location /` 的 `try_files ... /index.html`。
- 线上修复：
  - 修改 `/etc/nginx/sites-available/manga-translator.conf`，新增：
    - `location /data/ { proxy_pass http://127.0.0.1:8000; ... }`
  - 执行 `nginx -t` 与 `systemctl reload nginx`。
  - 备份文件：`/etc/nginx/sites-available/manga-translator.conf.bak.20260211-182913`
- 模板同步：
  - 仓库模板 `deploy/nginx/manga-translator-82.conf` 同步新增 `/data/` 反代块，避免后续部署回归。
- 验证结果：
  - 采样 URL：`/data/raw/isekai-dragondick-knight-commander/chapter-1/006.jpg`
  - backend (`:8000`)：`HTTP 200` + `content-type: image/jpeg`
  - nginx (`:80`)：`HTTP 200` + `Content-Type: image/jpeg`
  - 路由回归：`/`、`/signin`、`/scraper`、`/manga/test-id`、`/read/m1/c1` 均 `HTTP 200`
  - 非目标路径：`/api/v1/manga` 仍 `401`、`/admin/scraper/health` 仍 `401`（鉴权行为未变化）

## Cloud Run cuDNN9 收敛修复（`gen-lang-client-0238401140`，2026-02-12）

- 根因确认：
  - 旧 GPU revision 在运行时日志出现：
    - `Failed to create CUDAExecutionProvider`
    - `libcudnn_cnn.so.9: undefined symbol ... version libcudnn_graph.so.9`
  - 说明 ORT CUDA provider 在运行期未正确装载，实际回退 CPU。
- 修复动作：
  - 镜像基底统一到 `CUDA 12.8 + cuDNN runtime`，并固定 GPU 运行库搜索路径：
    - `LD_LIBRARY_PATH` 指向 pip 安装的 `nvidia/*/lib`（cudnn/cublas/cudart/cufft/curand/cusolver/cusparse/nccl/nvjitlink）。
  - 构建期新增 GPU 装载校验：
    - `onnxruntime providers` 必须包含 `CUDAExecutionProvider`
    - `ldd -r libonnxruntime_providers_cuda.so` 不允许 `not found` 或非白名单 `undefined symbol`
  - 运行期 startup 闸门升级：
    - `MANGA_REQUIRE_GPU=1` 时执行 `ldd -r` 探测，不通过则启动失败（拒绝 silently CPU fallback）
- 构建与发布：
  - build: `f4d406dd-ceaf-4ec1-84ac-fd4badaf055a`（SUCCESS）
  - image: `gcr.io/gen-lang-client-0238401140/manga-translator-compute:gpu-cudnn9-hotfix4-20260212-112250`
  - digest: `sha256:3f5569afb169a52f3b8c5d90c5f2f1757c82714559163bf23f760e22c2aaf5d5`
  - canary revision: `manga-translator-compute-00010-xej`（ready）
  - 全量切流：`100% -> manga-translator-compute-00010-xej`
- 验证结果：
  - Cloud Run（canary）`POST /internal/translate/page`：连续 3 次 `HTTP 200`，`x-fallback-used=0`
  - 82 服务器直连主域计算端点：`HTTP 200`，`x-fallback-used=0`
  - 新 revision 日志中未再出现 `Failed to create CUDAExecutionProvider` 与 `libcudnn_* undefined symbol`
- 联调补充：
  - 为满足既定“公网入口 + `X-Internal-Token`”策略，已为 `manga-translator-compute` 补充 `roles/run.invoker` 给 `allUsers`，避免 82 调用被 IAM 403 拦截。
