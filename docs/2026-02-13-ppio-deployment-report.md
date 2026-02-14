# PPIO Serverless GPU 部署报告

**日期**: 2026-02-13  
**状态**: ✅ 部署成功，翻译功能正常

---

## 1. 部署概览

| 项目 | 值 |
|------|-----|
| **Endpoint URL** | `https://2f9fb35f70c5b595-manga-translator.runsync.serverless.ppinfra.com` |
| **Endpoint ID** | `2f9fb35f70c5b595` |
| **Endpoint Name** | `manga-gpu` |
| **App Name** | `manga-translator` |
| **GPU Product** | Product `"1"` (RTX 4090 24GB) |
| **Docker 镜像** | `juniya1314/manga-translator-compute:gpu` |
| **镜像大小** | ~9.9GB (压缩) |
| **服务端口** | 8080 |
| **CUDA 版本** | 12.8 |
| **健康检查路径** | `/` |
| **类型** | Sync (同步) |

---

## 2. Worker 配置

| 配置项 | 值 | 说明 |
|--------|-----|------|
| **minNum** | 0 | 无请求时缩至 0，不产生费用 |
| **maxNum** | 1 | 最多 1 个 Worker |
| **freeTimeout** | 300s | Worker 空闲 5 分钟后释放 |
| **maxConcurrent** | 1 | 单 Worker 最大并发 1 |
| **gpuNum** | 1 | 每 Worker 1 张 GPU |
| **requestTimeout** | 600s | 单请求最大 10 分钟 |
| **rootfsSize** | 130GB | 系统盘（平台最大值） |
| **弹性策略** | concurrency / value=1 | 按并发请求数扩缩容 |

---

## 3. 环境变量

| 变量名 | 值 | 用途 |
|--------|-----|------|
| `PPIO_MODE` | `1` | 启用两阶段启动脚本 |
| `MANGA_CLOUDRUN_COMPUTE_ONLY` | `1` | 仅加载计算路由 |
| `MT_USE_GPU` | `true` | 启用 GPU 推理 |
| `PORT` | `8080` | 服务端口 |
| `MANGA_INTERNAL_API_TOKEN` | `f88ffee...` | 内部 API 鉴权 Token |
| `GEMINI_API_KEY` | `AIzaSyB5...` | Gemini 翻译模型 Key |
| `GEMINI_MODEL` | `gemini-3-flash-preview` | Gemini 主模型 |
| `GEMINI_FALLBACK_MODEL` | `gemini-2.5-flash` | 主模型失败时 fallback |

> 模型策略收敛：`gemini-2.0-flash` 已弃用，运行时若收到旧值会自动归一化到 `gemini-2.5-flash` 并输出告警日志。

---

## 4. 关键技术方案

### 4.1 两阶段启动 (解决健康检查超时)

**问题**: PPIO 健康检查 `initialDelay=10s`，`failureThreshold=3`，总窗口 ~40s。GPU 镜像的 Python import + 模型加载远超此时间，导致 Worker 反复被杀。

**方案**: `packaging/ppio_entrypoint.sh` 两阶段启动脚本

```
阶段 1 (< 1s):  启动极简 Python HTTP server → 立刻返回 {"status":"warming_up"} → 通过健康检查
阶段 2 (后台):  启动 uvicorn + 模型加载 → 就绪后切换到完整服务
```

**触发条件**: 环境变量 `PPIO_MODE=1`

**Dockerfile CMD 逻辑**:
```dockerfile
CMD ["/bin/sh", "-c", "if [ \"${PPIO_MODE:-0}\" = \"1\" ]; then exec /app/ppio_entrypoint.sh; elif ..."]
```

### 4.2 后台模型初始化 (cloudrun_compute_main.py)

同时修改了 `cloudrun_compute_main.py`，将模型加载从 FastAPI `startup_event` 移到后台线程：

```python
@app.on_event("startup")
async def startup_event() -> None:
    thread = threading.Thread(target=_background_init, daemon=True)
    thread.start()

@app.get("/")
async def root_health() -> JSONResponse:
    if _startup_error:
        return JSONResponse({"status": "error"}, status_code=503)
    if not _startup_ready:
        return JSONResponse({"status": "warming_up"}, status_code=200)
    return JSONResponse({"status": "ok"}, status_code=200)
```

---

## 5. 踩坑记录

### 5.1 Product ID

| Product ID | GPU 型号 | 状态 |
|-----------|---------|------|
| `"1"` | RTX 4090 24GB | ✅ 可用 |
| `"2"` | RTX 3090 24GB | ❌ 当前无资源 (`failed to schedule worker`) |
| `"3090.16c92g"` 等 | - | ❌ 仅适用于专用实例，serverless 不支持 |

> Serverless 产品使用简化 ID (`"1"`, `"2"`)，与专用实例的 product ID (`3090.16c92g`) 体系不同。

### 5.2 健康检查参数不可定制

PPIO API 的 `healthy` 参数仅支持 `path` 字段，`initialDelay`/`period`/`timeout` 等由平台固定：
- `initialDelay`: 10s
- `period`: 10s
- `timeout`: 10s
- `successThreshold`: 1
- `failureThreshold`: 3

**总窗口**: ~40s，必须在此时间内通过健康检查。

### 5.3 rootfsSize 限制

平台最大 `rootfsSize = 130GB`，不可自定义更大。对于 ~10GB 压缩镜像足够。

### 5.4 ONNX Runtime 线程警告

```
pthread_setaffinity_np failed for thread: 399, index: 0, mask: {64, }
```

**原因**: ONNX Runtime 尝试绑定到 64 号核心，但容器仅分配 16 核心。  
**影响**: 无。仅日志警告，不影响推理功能。  
**修复**: 可设置 `OMP_NUM_THREADS=16` 抑制，但需重新部署。

---

## 6. 性能数据

| 指标 | 值 |
|------|-----|
| **首次冷启动（含镜像拉取）** | ~333s (~5.5min) |
| **健康检查通过时间** | < 10s (Phase 1 HTTP server) |
| **Worker 空闲保留** | 300s (5min) |
| **翻译功能** | ✅ 正常工作 |

---

## 7. 费用估算

PPIO RTX 4090 按量计费 (Product `"1"`):

| 场景 | 估算月费 |
|------|------:|
| 不使用 | $0 |
| 轻度（1章/天, ~10页） | 待实测 |
| 中度（5章/天） | 待实测 |

> 具体单价需参考 PPIO 控制台账单页面。

---

## 8. 对比 Cloud Run

| 维度 | Cloud Run GPU | PPIO Serverless |
|------|-------------|----------------|
| **GPU 型号** | NVIDIA L4 | RTX 4090 |
| **GPU 显存** | 24GB | 24GB |
| **GPU 算力** | 较弱 | 更强 (~2x) |
| **健康检查** | 可配置 `startupProbe` | 固定 10s initialDelay |
| **冷启动** | ~40s (模型加载) | ~333s (首次含拉镜像) |
| **镜像拉取** | gcr.io 秒级 | Docker Hub ~5min |
| **定价透明度** | 按秒明码标价 | 需查控制台 |
| **区域** | europe-west1 | 全球多集群 |
| **复杂度** | 简单 (gcloud 部署) | 需两阶段启动 hack |

---

## 9. 管理命令参考

```bash
# 查看 endpoints
curl -s -H "Authorization: Bearer $PPIO_KEY" \
  https://api.ppio.com/gpu-instance/openapi/v1/endpoints

# 删除 endpoint
curl -s -X POST https://api.ppio.com/gpu-instance/openapi/v1/endpoint/delete \
  -H "Authorization: Bearer $PPIO_KEY" \
  -H "Content-Type: application/json" \
  -d '{"id":"<endpoint_id>"}'

# 更新 endpoint
curl -s -X POST https://api.ppio.com/gpu-instance/openapi/v1/endpoint/update \
  -H "Authorization: Bearer $PPIO_KEY" \
  -H "Content-Type: application/json" \
  -d '{"id":"<endpoint_id>", ...}'
```

---

## 10. 修改的文件

| 文件 | 变更 |
|------|------|
| `packaging/ppio_entrypoint.sh` | **新增** - 两阶段启动脚本 |
| `packaging/Dockerfile` | **修改** - 加入 PPIO 启动脚本、curl 安装、PPIO_MODE CMD 分支 |
| `manga_translator/server/cloudrun_compute_main.py` | **修改** - 模型加载改为后台线程，健康检查分状态返回 |
| `.env` | PPIO_KEY 已写入 |
