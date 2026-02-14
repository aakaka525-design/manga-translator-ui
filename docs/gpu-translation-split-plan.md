# GPU/翻译分离架构方案 v2

**目标**: 将 Gemini API 调用从 GPU Worker 剥离，GPU 占用时间从 ~34s/页降至 ~2.5s/页，吞吐量提升 ~14 倍，稳定性增强。

**状态**: 可立项 (v2.3 final)

## 实施状态更新（2026-02-14）

- 已落地：`/internal/translate/detect`、`/internal/translate/render`、`CtxCache`、split/unified 自动降级链路。
- 已落地：`translate_pipeline_mode=unified|split`（默认 unified，支持环境变量覆盖）。
- 已落地：`/render` 错误状态机 `401 -> 503 -> 404 -> 410 -> 422 -> 400`。
- 已落地：前端降级提示（`pipeline_mode=fallback_to_unified`）Toast 告警。
- 已完成：本地小样本灰度证据（1 图 split/unified 一致；10 页章节 `success_count=10`、`failed_count=0`、文件数=10）。

---

## 1. 当前架构与瓶颈数据

```
用户请求 → 82 后端 → PPIO GPU Worker (RTX 4090)
                        ├─ context 阶段 (检测+OCR+Gemini)  34,342ms  99.7%
                        └─ render 阶段  (mask+inpaint+渲染)    104ms   0.3%
                     总服务端: 34,446ms
                     端到端:   46,900ms
```

**实测数据源**: 2026-02-14 PPIO endpoint `89765ac35176d0e1`, 图片 001.jpg (720×14046, 705KB), 16 个文本区域。

---

## 2. 目标架构

```
用户请求 → 82 后端 (协调者)
              │
              ├─① POST /internal/translate/detect  (GPU, ~2s)
              │   返回: task_id + serialized_regions + image_hash + ttl
              │
              ├─② 82 后端本地: _batch_translate_texts 复用  (~30s, 零 GPU 成本)
              │   复用现有翻译器统一逻辑 (模型选择/重试/上下文/幻觉检测)
              │
              └─③ POST /internal/translate/render   (GPU, ~0.5s)
              │   按 task_id 恢复 ctx 缓存 → 填入译文 → mask + inpaint + render
              │   cache miss → 自动降级到一体式 /internal/translate/page
              │
           GPU 总占用: ~2.5s/页

           回退路径: /internal/translate/page (一体式，不动)
```

---

## 3. API 契约

### 3.1 POST /internal/translate/detect

**入参**: multipart/form-data

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| image | UploadFile | ✅ | 原图 |
| source_language | str | 否 | 源语言 |
| target_language | str | 否 | 目标语言 |
| X-Internal-Token | Header | ✅ | 鉴权 |

**返回**: JSON

```jsonc
{
  "task_id": "a1b2c3d4",                // UUID, 关联 ctx 缓存
  "ttl_seconds": 300,                   // ctx 缓存 TTL
  "image_hash": "sha256:abc123...",      // 用于 /render 校验
  "regions_count": 16,
  "regions": [                           // TextBlock.to_dict() 完整字段子集 + region_index
    {
      "region_index": 0,                 // 服务端生成, 0..n-1, 与 ctx.text_regions 数组下标一一对应
      "lines": [[x1,y1], [x2,y2], [x3,y3], [x4,y4]],
      "texts": ["日本語テキスト"],
      "text": "日本語テキスト",
      "angle": 0.0,
      "font_size": 24,
      "fg_colors": [0, 0, 0],
      "bg_colors": [255, 255, 255],
      "direction": "h",
      "alignment": "center",
      "target_lang": "CHS",
      "source_lang": "JPN",
      "line_spacing": 1.0,
      "stroke_width": 0.2,
      "stroke_color_type": "white",
      "adjust_bg_color": true,
      "prob": 0.95
    }
  ],
  "from_lang": "JPN",                   // ctx.from_lang, 供 Phase2 使用
  "elapsed_ms": {
    "detect": 850,
    "ocr": 1200,
    "total": 2100
  }
}
```

**ctx 缓存内容** (GPU Worker 内存, 不序列化传输):

```python
# 按 task_id 缓存的完整 ctx 对象, 包含:
# - ctx.img_rgb          (numpy array, 渲染依赖)
# - ctx.img_alpha        (PIL Image or None)
# - ctx.input            (PIL Image, 原图)
# - ctx.upscaled         (PIL Image)
# - ctx.text_regions     (List[TextBlock], 含检测结果但 translation 为空)
# - ctx.mask             (可能为 None, _complete_translation_pipeline 会自行生成)
# - ctx.mask_raw         (numpy array or None)
# - ctx.from_lang        (str)
# - ctx.image_name       (str)
```

**错误码**:

| HTTP | 错误码 | 场景 |
|------|--------|------|
| 401 | UNAUTHORIZED | Token 无效 |
| 503 | NOT_READY | 模型仍在加载 |
| 400 | INVALID_IMAGE | 图片无法解析 |
| 200 | - | 检测到 0 区域也返回 200 |

### 3.2 Phase 2: 82 后端本地翻译

**关键约束**: 不写新翻译核心，复用现有 `_batch_translate_texts` 语义。

**线程安全约束**: Phase2 调用 **必须通过 `asyncio.Semaphore(1)` 显式串行化**，
保证同一时刻只有一个翻译任务触达全局 translator。

```python
_translate_semaphore = asyncio.Semaphore(1)  # 模块级单例

async def split_pipeline_translate(...):
    # Phase 1: detect (不在锁内)
    ...
    # Phase 2: 翻译 (必须在锁内)
    async with _translate_semaphore:
        translated = await translator._batch_translate_texts(...)
    # Phase 3: render (不在锁内)
    ...
```

> 仅靠 `asyncio.await` **不能** 保证串行：多个并发 HTTP 请求会在同一事件循环中交替执行，
> 不加显式锁的 await 仍可能并发触达 translator（历史 503 问题的根因）。

```python
# 82 后端侧的协调逻辑 (伪代码)
async def split_pipeline_translate(image_bytes, source_lang, target_lang, context_translations):
    
    # Phase 1: GPU 检测 + OCR
    detect_result = await call_ppio("/internal/translate/detect", {
        "image": image_bytes,
        "source_language": source_lang,
        "target_language": target_lang,
    })
    
    if detect_result["regions_count"] == 0:
        return original_image, {"output_changed": False, "no_change_reason": "no_text"}
    
    # Phase 2: 本地复用 _batch_translate_texts
    # ⚠️ _batch_translate_texts 必须在 semaphore 内执行
    texts = [r["text"] for r in detect_result["regions"]]
    async with _translate_semaphore:
        translator = get_global_translator()  # 单例
        translated_texts = await translator._batch_translate_texts(
            texts=texts,
            config=config,  # 复用现有 config 构建
            ctx=minimal_ctx,  # 含 from_lang 等
        )
    
    # Phase 3: GPU 渲染 (在 semaphore 外, 不占翻译锁)
    render_result = await call_ppio("/internal/translate/render", {
        "task_id": detect_result["task_id"],
        "image_hash": detect_result["image_hash"],
        "translated_regions": [
            {"region_index": r["region_index"], "translation": t}
            for r, t in zip(detect_result["regions"], translated_texts)
        ],
    })
    
    return render_result
```

**翻译器一致性保障**:
- 模型选择: 沿用 `config.translator.translator` (gemini/openai/gemini_hq 等)
- 重试逻辑: 沿用 `translator.attempts` 配置
- 上下文: 沿用 `translator.set_prev_context()` + `_build_prev_context()`
- 幻觉检测: 沿用 `_check_repetition_hallucination()`
- 取消回调: 沿用 `set_cancel_check_callback()`
- 串行保证: `asyncio.Semaphore(1)` 包住 `_batch_translate_texts` 调用全程, detect/render 在锁外

### 3.3 POST /internal/translate/render

**入参**: JSON (application/json)

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| task_id | str | ✅ | 关联 /detect 返回的缓存 |
| image_hash | str | ✅ | 校验 task_id 对应的图片 |
| translated_regions | list | ✅ | `[{"region_index": 0, "translation": "译文"}, ...]` |
| X-Internal-Token | Header | ✅ | 鉴权 |

> **region_index 映射规则**: `/detect` 返回的 `region_index` 是服务端生成的 0..n-1 整数,
> 与缓存的 `ctx.text_regions` 数组下标一一对应。`/render` 按 `region_index` 将 `translation`
> 写入 `ctx.text_regions[region_index].translation`。TextBlock.to_dict() 无需新增 id 字段。

**返回**: 

- 成功: `application/octet-stream` (图片), 带 x-* 响应头
- Cache miss: **不返回假成功**, 返回特定错误码

**响应头** (与现有 /page 一致):

```
x-regions-count: 16
x-output-changed: 1
x-fallback-used: 0                   # 由 82 后端透传, GPU Worker 不设置
x-stage-elapsed-ms: {"render": 103}   # 仅含 GPU 本地阶段
x-remote-elapsed-ms: 500
x-cold-start: 0
x-selected-model: gemini-3-flash-preview  # ⚠️ 由 82 后端透传, 非 GPU Worker 本地选择
x-primary-model: gemini-3-flash-preview   # 同上
x-fallback-model: gemini-2.5-flash        # 同上
x-pipeline-mode: split                    # 新增: 标识分离模式
x-translation-text: ...
```

> **模型头语义说明**: split 模式下, 模型选择发生在 Phase2 (82 后端), 不发生在 GPU Worker 内部。
> `/render` 响应中的 `x-selected-model`, `x-primary-model`, `x-fallback-model`, `x-fallback-used`
> 均为 82 后端在调用 `/render` 时作为请求参数传入, GPU Worker 原样回传。
> 排障时注意: 这些头 **不代表 GPU Worker 做了模型选择**。

**错误码**:

| 优先级 | HTTP | 错误码 | 场景 | 82 后端处理 |
|--------|------|--------|------|------------|
| 1 (最先) | 401 | UNAUTHORIZED | Token 无效 | 报错, 不降级 |
| 2 | 503 | NOT_READY | 模型仍在加载 | 重试 (指数退避) |
| 3 | 404 | CACHE_MISS | task_id 不存在 (含 worker 重启) | 自动降级到 /page |
| 4 | 410 | TASK_EXPIRED | task_id 存在但 ttl 已过 | 自动降级到 /page |
| 5 | 422 | IMAGE_HASH_MISMATCH | task_id 存在但 hash 不一致 | 自动降级到 /page |
| 6 | 400 | RENDER_INPUT_INVALID | region_index 越界或数量不匹配 | 报错, 不降级 |

> **判定状态机**: GPU Worker 按上表优先级从高到低逐条检查, 命中即返回, 保证同一条件唯一返回码。
> 例如: task_id 不存在时直接返回 404 CACHE_MISS, 不再检查 hash 或 regions。
> TASK_EXPIRED 从 400 改为 **410 Gone**, 语义更精确 (资源曾存在但已过期)。

---

## 4. ctx 缓存协议 (P0 补齐)

### 4.0 部署前提

> **CtxCache 作用域**: 单进程、单 worker。
> GPU compute 服务必须以 `uvicorn --workers 1` 方式启动（当前 Dockerfile/entrypoint 已满足）。
> 多进程 (workers > 1) 会导致跨进程 cache miss, 分离模式将频繁降级到一体式, 失去意义。
> 此约束在 `ppio_entrypoint.sh` 和 `cloudrun_compute_main.py` 中均已固化, 无需额外配置。

### 4.1 缓存生命周期

```python
import time
from typing import Dict, Tuple, Optional
from threading import Lock

class CtxCache:
    """GPU Worker 内的 ctx 缓存, 线程安全, 仅限单进程部署"""
    
    def __init__(self, max_size: int = 10, default_ttl: int = 300):
        self._store: Dict[str, Tuple[float, str, 'Context']] = {}  # task_id -> (expire_at, image_hash, ctx)
        self._lock = Lock()
        self._max_size = max_size
        self._default_ttl = default_ttl
    
    def put(self, task_id: str, image_hash: str, ctx) -> int:
        """存入 ctx, 返回 ttl"""
        with self._lock:
            self._evict_expired()
            if len(self._store) >= self._max_size:
                # LRU: 淘汰最早的
                oldest = min(self._store, key=lambda k: self._store[k][0])
                del self._store[oldest]
            expire_at = time.time() + self._default_ttl
            self._store[task_id] = (expire_at, image_hash, ctx)
            return self._default_ttl
    
    def get(self, task_id: str, image_hash: str) -> Tuple[Optional['Context'], str]:
        """取出 ctx, 返回 (ctx, reason)
        
        reason 取值:
        - 'OK'                  → ctx 有效
        - 'CACHE_MISS'          → task_id 不存在 (含 worker 重启)
        - 'TASK_EXPIRED'        → task_id 存在但 ttl 已过
        - 'IMAGE_HASH_MISMATCH' → task_id 存在但 hash 不一致
        """
        with self._lock:
            entry = self._store.get(task_id)
            if entry is None:
                return None, 'CACHE_MISS'
            expire_at, stored_hash, ctx = entry
            if time.time() > expire_at:
                del self._store[task_id]
                return None, 'TASK_EXPIRED'
            if stored_hash != image_hash:
                return None, 'IMAGE_HASH_MISMATCH'
            return ctx, 'OK'
    
    def pop(self, task_id: str) -> Optional['Context']:
        """取出并删除 (render 后不再需要)"""
        with self._lock:
            entry = self._store.pop(task_id, None)
            if entry is None:
                return None
            _, _, ctx = entry
            return ctx
    
    def _evict_expired(self):
        now = time.time()
        expired = [k for k, (exp, _, _) in self._store.items() if now > exp]
        for k in expired:
            del self._store[k]

_ctx_cache = CtxCache(max_size=10, default_ttl=300)
```

### 4.2 Cache Miss 降级协议

```
82 后端 → /render (task_id=xxx)
         ├─ 200: 正常返回图片
         ├─ 404 CACHE_MISS:
         │    82 后端自动回退 → /internal/translate/page (一体式, 重发原图)
         │    前端标记 x-pipeline-mode: fallback_to_unified
         │    后端日志: WARNING "ctx cache miss, falling back to unified pipeline"
         ├─ 410 TASK_EXPIRED:
         │    同 404 回退路径
         │    后端日志: WARNING "ctx expired (ttl exceeded), falling back to unified pipeline"
         └─ 422 IMAGE_HASH_MISMATCH:
              同 404 回退路径
              后端日志: WARNING "image hash mismatch, falling back to unified pipeline"
```

### 4.3 Worker 重启/缩容场景

| 场景 | 影响 | 处理 |
|------|------|------|
| Worker 正常运行中 | 无 | ctx 在内存中 |
| Worker 被 PPIO 缩容 (min=0) | 所有 ctx 丢失 | /render 返回 CACHE_MISS, 82 后端回退到 /page |
| Worker 重启 (OOM/崩溃) | 同上 | 同上 |
| 重复请求同一 task_id | pop() 后 ctx 被删除 | 第二次返回 CACHE_MISS |

---

## 5. 并发约束说明 (P0 补齐)

### 当前约束

```
maxConcurrent=1  →  GPU Worker 同一时刻只处理一个请求
```

### 分离模式下的并发模型

```
              时间轴 →
GPU Worker:   [detect_1 2s][idle 30s][render_1 0.5s][detect_2 2s][idle 30s][render_2 0.5s]
82 后端:       [          gemini_1 30s          ]  [          gemini_2 30s          ]
```

**maxConcurrent=1 下, 分离模式不会产生并发GPU请求:**
- 82 后端串行协调: detect → 等 gemini → render → 下一页
- GPU Worker 每次只收到一个请求 (detect 或 render)

**主要收益 (已确认):**
- GPU 占用时间: 2s + 0.5s = 2.5s/页 (vs 一体式 34.4s/页) → **吞吐量 ~14x**
- 单页 GPU 时间短, 请求超时风险大幅降低 → **稳定性提升**
- detect/render 各自简短, worker 缩容窗口内的失败率更低

**成本收益 (未证实, 大概率不成立):**

> PPIO serverless 按 **实例存活时长** 计费 (而非按请求负载时间), 分离模式下
> GPU worker 虽然每次只处理 2.5s, 但 worker 实例在 freeTimeout 内始终存活, 照常计费。
> **因此不应以成本节省作为分离方案的核心 ROI。**
>
> 若未来 PPIO 支持按请求时间的计费模式, 成本收益可自动解锁。

### 不推荐的并发优化

以下优化在当前阶段 **不实施**:
- ❌ maxConcurrent > 1 的交错调度 (历史上引发过 503)
- ❌ 多页 detect 批量提交 (增加复杂度, 收益不确定)
- ❌ GPU Worker 内部异步处理 detect+render 混合请求

---

## 6. 可观测性要求 (P1 补齐)

### 端到端透传字段

每阶段必须在响应头/日志中返回:

| 字段 | /detect | /render | /page (一体式) |
|------|---------|---------|---------------|
| x-regions-count | ✅ | ✅ | ✅ (已有) |
| x-stage-elapsed-ms | `{"detect":N,"ocr":N}` | `{"render":N}` | `{"context":N,"render":N}` (已有) |
| x-remote-elapsed-ms | ✅ | ✅ | ✅ (已有) |
| x-selected-model | - | ✅ (从82后端传入) | ✅ (已有) |
| x-fallback-used | - | ✅ (从82后端传入) | ✅ (已有) |
| x-failure-stage | ✅ | ✅ | ✅ (已有) |
| x-pipeline-mode | `split` | `split` | `unified` |
| x-cold-start | ✅ | ✅ | ✅ (已有) |

### 82 后端聚合

82 后端汇总三阶段的指标后, 向前端返回统一的 x-* 头:

```python
final_headers = {
    "x-pipeline-mode": "split",
    "x-stage-elapsed-ms": json.dumps({
        "detect": detect_ms,
        "translate": gemini_ms,  # 本地 Gemini 耗时
        "render": render_ms,
        "total": detect_ms + gemini_ms + render_ms,
    }),
    "x-regions-count": str(regions_count),
    "x-selected-model": selected_model,
    "x-fallback-used": "1" if fallback_used else "0",
}
```

---

## 7. 章节级失败语义 (P1 补齐)

沿用现有 success/partial/error 规则:

| 场景 | 状态 | 前端行为 |
|------|------|---------|
| 所有页 split pipeline 成功 | success | 正常展示 |
| 部分页 cache miss → 降级到 /page 成功 | success (标记 fallback) | Toast "X 页使用了降级翻译" |
| 部分页 /page 也失败 | partial | 展示成功页, 标记失败页 |
| 所有页失败 | error | 错误提示 |

**验收公式**:

```
assert success_count + failed_count == total_count   # 完整性: 每页必须有明确结果
```

- **灰度阶段 (阶段 C)**: `success_count == total_count` 才算通过, 任何 failed 都需排查
- **放量阶段**: 允许 partial, 但 `success_count == total_count` 仍为目标 SLA
- partial 状态下前端必须标记每个失败页的 `failure_stage` (detect/translate/render/fallback)

---

## 8. 收益统一口径

基于实测数据 (001.jpg, 16 regions):

| 指标 | 一体式 (实测) | 分离式 (估算) | 改善 |
|------|-------------|-------------|------|
| GPU 占用/页 | 34.4s | ~2.5s (detect 2s + render 0.5s) | **~14x** |
| 端到端延迟 | 46.9s | ~35s (detect 2s + gemini 30s + render 0.5s + 网络) | **~1.3x** |
| GPU 吞吐量 | 1.7 页/分 | ~24 页/分 | **~14x** |
| GPU 成本/页 | 34.4s × 单价 | ≈ 34.4s × 单价 (**按实例时长计费, 不省钱**) | **≈ 1x** |

> **核心收益是吞吐量与稳定性, 不是成本。**
> 成本节省依赖 PPIO 未来支持按请求负载时间计费, 当前不成立。

---

## 9. 实施计划

### 阶段 A: GPU Worker 端点 + 缓存 (P0, ~6h)

| 任务 | 文件 | 工时 |
|------|------|------|
| CtxCache 实现 | `manga_translator/server/core/ctx_cache.py` | 1h |
| `/detect` 端点 (调用 `_translate_until_translation` → 缓存 ctx → 返回 regions) | `routes/v1_translate.py` | 2h |
| `/render` 端点 (恢复 ctx → 填入译文 → 调用 `_complete_translation_pipeline`) | `routes/v1_translate.py` | 2h |
| Cache miss 降级路径 (返回 404 CACHE_MISS) | `routes/v1_translate.py` | 0.5h |
| 单元测试 | `tests/test_split_pipeline.py` | 0.5h |

### 阶段 B: 82 后端协调 (P1, ~4h)

| 任务 | 文件 | 工时 |
|------|------|------|
| split_pipeline 协调逻辑 | `manga_translator/server/routes/v1_translate.py` | 2h |
| Cache miss 自动降级到 /page | 同上 | 1h |
| 配置开关 (split/unified) | `config_manager.py` | 0.5h |
| 可观测性头透传 | 同上 | 0.5h |

### 阶段 C: 验证 (P0, ~4h)

| 任务 | 说明 | 工时 |
|------|------|------|
| 单页灰度测试 | 1 张图, 对比 split vs unified 结果一致性 | 1h |
| 10 页章节基准 | chapter-1 全部页, 验证成功页数=文件数 | 1h |
| Cache miss 场景测试 | 手动杀 worker, 验证自动降级 | 1h |
| 性能基准对比 | 同一图片, 对比 GPU 占用时间 | 1h |

**总工时: ~14h**

### 实施前前提

- [x] 确认分离方案的核心 ROI 来源是吞吐量与稳定性 (成本节省当前不成立)

### 通过条件 (可放量)

- [x] `/detect` 返回 task_id + region_index(0..n-1) + 完整 serialized_regions + image_hash + ttl
- [x] `/render` 按 task_id 取缓存, 按优先级状态机返回错误码, cache miss 自动降级到 /page, 不返回假成功
- [x] Phase 2 复用 `_batch_translate_texts` 语义, 通过显式 Semaphore(1) 串行执行, 不写新翻译核心
- [x] 单页灰度: split 输出与 unified 视觉一致
- [x] 10 页章节基准: success_count + failed_count == total_count, 且 success_count == total_count
- [x] 前端 Toast 标记降级页

### 2026-02-14 本地小样本实测证据

- 单页一致性（1 图）：
  - `GRAY_SINGLE_PAGE_UNIFIED_EXISTS True`
  - `GRAY_SINGLE_PAGE_SPLIT_EXISTS True`
  - `GRAY_SINGLE_PAGE_BYTES_EQUAL True`
- 10 页章节语义一致性：
  - `CH10_TOTAL 10`
  - `CH10_SUCCESS 10`
  - `CH10_FAILED 0`
  - `CH10_FILE_COUNT 10`
  - `CH10_ASSERT_SUM_OK True`
  - `CH10_ASSERT_ALL_SUCCESS True`
- 联调环境复测已完成并关闭：`TASK-SPLIT-009`（PPIO endpoint 联调通过）。
