# 部署来源注册表 (Single Source of Truth)

> **最后更新**: 2026-02-14 | **维护者**: 手动维护

本文件记录当前生产环境实际使用的所有部署目标及其状态。
其它文档中如涉及部署信息，以本文件为准。

---

## 当前生产环境

### 82 服务器 (前端 + 状态后端)

| 项 | 值 |
|----|------|
| IP | `82.22.36.81` |
| 服务管理 | systemd `manga-translator.service` |
| Nginx | `/etc/nginx/sites-available/manga-translator.conf` |
| 工作目录 | `/opt/manga-translator` |
| Python | `.venv/bin/python -m manga_translator web --host 0.0.0.0 --port 8000` |
| 翻译 backend | `MANGA_TRANSLATE_EXECUTION_BACKEND=cloudrun` |
| Cloud Run URL | 见下方 Cloud Run 生产节 |
| 部署用户 | `deploy` |

### Cloud Run GPU 计算服务 (当前生产)

| 项 | 值 |
|----|------|
| GCP 项目 | `main1-487412` |
| 账号 | `aakaka525@gmail.com` |
| 区域 | `europe-west1` |
| 服务名 | `manga-translator-compute` |
| 镜像 | `juniya1314/manga-translator-compute:gpu-20260214-v2` |
| GPU | NVIDIA L4, 1× |
| CPU/内存 | 4 vCPU / 16 GiB |
| 并发 | `concurrency=1` |
| 超时 | `600s` |
| 缩放 | `min=0, max=1` |
| CPU 计费 | `no-cpu-throttling` (GPU 强制) |
| 认证 | `--allow-unauthenticated` + `X-Internal-Token` |
| 估算成本 | ~$1.16/h 活跃, ~$0.0088/页 |

> ⚠️ **安全备注**: 当前使用 `--allow-unauthenticated`，仅靠 `X-Internal-Token` 保护。
> 建议恢复 `--no-allow-unauthenticated` 并用 IAM 服务账号调用。

### PPIO GPU Worker (备选)

| 项 | 值 |
|----|------|
| Endpoint ID | `89765ac35176d0e1` |
| GPU | RTX 4090 24GB |
| 镜像 | `juniya1314/manga-translator-compute:gpu-20260214-v2` |
| freeTimeout | `60s` |
| maxConcurrent | `1` |
| 状态 | ✅ 可用 |

### PPIO RTX 3090 (已放弃)

| 项 | 值 |
|----|------|
| 状态 | ❌ 不可用 (资源池无可用 worker) |
| 备注 | 多次尝试失败，115 个 worker 循环创建/销毁 |

---

## 退役/历史项目 (不再使用)

以下 Cloud Run 项目出现在历史文档中，**当前均不用于生产**：

| GCP 项目 | 用途 | 当前状态 |
|----------|------|---------|
| `manga-translator-2602111442` | 早期 Cloud Run 测试 | GPU 配额 0，已弃用 |
| `onyx-hangout-468807-a4` | Cloud Run GPU 验证 | GPU 配额 0，已弃用 |
| `gen-lang-client-0238401140` | Cloud Run GPU 正式部署 v1 | 费用已关闭，已弃用 |

> 如 `82-cloudrun-hybrid.md` 中引用上述项目的 URL，以本文件为准。

---

## 密钥管理

| 密钥 | 存储位置 | 建议 |
|------|---------|------|
| `MANGA_INTERNAL_API_TOKEN` | Cloud Run env var / 82 systemd env | 建议迁移到 Secret Manager |
| `GEMINI_API_KEY` | Cloud Run env var / 82 `.env` | 建议迁移到 Secret Manager |
| `PPIO_KEY` | 82 `.env` | 仅本地使用 |

---

## 部署脚本

| 脚本 | 用途 | 注意事项 |
|------|------|---------|
| `deploy/cloudrun/deploy-compute.sh` | Cloud Run GPU 部署 | 使用 `--set-secrets GEMINI_API_KEY=<secret>:<version>` 注入密钥 |
| `deploy/systemd/manga-translator.service` | 82 服务器 systemd 模板 | token/URL 为空，需手动填写 |
| `deploy/nginx/manga-translator-82.conf` | 82 Nginx 反代模板 | 已包含 `/data/` 反代块 |
