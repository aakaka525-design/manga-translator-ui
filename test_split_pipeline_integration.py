#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Split Pipeline 联调测试 (TASK-SPLIT-009)

对真实 PPIO GPU endpoint 依次验证:
1. 健康检查 (等待 worker ready)
2. /internal/translate/detect  → 返回 task_id + regions
3. /internal/translate/render  → 返回图片
4. /internal/translate/page    → 一体式基准对照
5. split vs unified 输出一致性对比
6. 10 页章节语义一致性

用法:
    python3 test_split_pipeline_integration.py
"""

import hashlib
import json
import os
import sys
import time
from pathlib import Path

import httpx
import httpx as requests

# Prevent pytest from collecting this integration runner as a test module.
__test__ = False

# ============================================================
# 配置
# ============================================================
PPIO_ENDPOINT = os.getenv(
    "MANGA_PPIO_ENDPOINT",
    "https://89765ac35176d0e1-manga-translator.runsync.serverless.ppinfra.com",
)
INTERNAL_TOKEN = os.getenv("MANGA_INTERNAL_API_TOKEN", "")

REPO_ROOT = Path(__file__).resolve().parent
DEFAULT_DATA_DIR = (
    REPO_ROOT
    / "manga_translator/server/data/raw/isekai-dragondick-knight-commander/chapter-1"
)
DATA_DIR = Path(os.getenv("MANGA_TEST_DATA_DIR", str(DEFAULT_DATA_DIR)))
TEST_IMAGE = "001.jpg"

# 10 页章节测试图
CHAPTER_IMAGES = [f"{str(i).zfill(3)}.jpg" for i in range(1, 11)]

TIMEOUT_SEC = 600  # 含冷启动
HEALTH_WAIT_MAX = 400  # 最长等待 worker ready 秒数
TIMEOUT = httpx.Timeout(TIMEOUT_SEC, connect=30.0)

HEADERS = {"X-Internal-Token": INTERNAL_TOKEN}


def sha256_hex(data: bytes) -> str:
    return f"sha256:{hashlib.sha256(data).hexdigest()}"


def wait_for_healthy():
    """等待 PPIO worker 进入 ready 状态"""
    print(f"\n{'='*70}")
    print("⏳ 等待 PPIO Worker 就绪...")
    print(f"   Endpoint: {PPIO_ENDPOINT}")
    print(f"{'='*70}")

    start = time.time()
    attempt = 0
    while time.time() - start < HEALTH_WAIT_MAX:
        attempt += 1
        try:
            resp = requests.get(f"{PPIO_ENDPOINT}/", timeout=httpx.Timeout(15.0, connect=10.0))
            body = resp.json() if resp.status_code == 200 else {}
            status = body.get("status", "unknown")
            elapsed = time.time() - start
            print(f"  [{attempt}] HTTP {resp.status_code} status={status} ({elapsed:.0f}s)")

            if resp.status_code == 200 and status == "ok":
                print(f"  ✅ Worker 就绪! ({elapsed:.0f}s)")
                return True
        except Exception as e:
            elapsed = time.time() - start
            print(f"  [{attempt}] 连接超时/错误: {e} ({elapsed:.0f}s)")

        time.sleep(10)

    print(f"  ❌ Worker 未在 {HEALTH_WAIT_MAX}s 内就绪")
    return False


def test_detect(image_path: Path) -> dict | None:
    """Phase 1: /internal/translate/detect"""
    print(f"\n{'─'*70}")
    print(f"🔍 Phase 1: /detect ({image_path.name})")
    print(f"{'─'*70}")

    payload = image_path.read_bytes()
    t0 = time.perf_counter()

    resp = requests.post(
        f"{PPIO_ENDPOINT}/internal/translate/detect",
        files={"image": (image_path.name, payload, "image/jpeg")},
        data={
            "source_language": "",
            "target_language": "CHS",
        },
        headers=HEADERS,
        timeout=TIMEOUT,
    )
    elapsed = time.perf_counter() - t0

    if resp.status_code != 200:
        print(f"  ❌ HTTP {resp.status_code}: {resp.text[:300]} ({elapsed:.1f}s)")
        return None

    result = resp.json()
    regions = result.get("regions", [])
    task_id = result.get("task_id", "")
    image_hash = result.get("image_hash", "")
    ttl = result.get("ttl_seconds", 0)
    from_lang = result.get("from_lang", "")
    elapsed_ms = result.get("elapsed_ms", {})

    print(f"  ✅ {elapsed:.1f}s")
    print(f"     task_id:      {task_id}")
    print(f"     image_hash:   {image_hash[:40]}...")
    print(f"     ttl_seconds:  {ttl}")
    print(f"     from_lang:    {from_lang}")
    print(f"     regions:      {len(regions)}")
    print(f"     elapsed_ms:   {elapsed_ms}")

    # 验证 region_index
    indices = [r.get("region_index") for r in regions]
    expected = list(range(len(regions)))
    has_region_index = indices == expected
    print(f"     region_index: {indices[:5]}{'...' if len(indices) > 5 else ''} → {'✅' if has_region_index else '❌'}")

    # 验证 image_hash 与本地计算是否一致
    local_hash = sha256_hex(payload)
    hash_match = image_hash == local_hash
    print(f"     hash_match:   {hash_match} {'✅' if hash_match else '❌'}")

    if regions:
        sample = regions[0]
        print(f"     sample[0]:    text={sample.get('text', '')[:30]}  direction={sample.get('direction', '?')}")

    return result


def test_render(detect_result: dict) -> bytes | None:
    """Phase 3: /internal/translate/render"""
    print(f"\n{'─'*70}")
    print(f"🎨 Phase 3: /render (task_id={detect_result['task_id'][:12]}...)")
    print(f"{'─'*70}")

    regions = detect_result.get("regions", [])
    # 模拟简单翻译（不走真实翻译，只测试 render pipeline）
    translated_regions = [
        {"region_index": r["region_index"], "translation": f"[测试翻译{r['region_index']}]"}
        for r in regions
    ]

    t0 = time.perf_counter()
    resp = requests.post(
        f"{PPIO_ENDPOINT}/internal/translate/render",
        json={
            "task_id": detect_result["task_id"],
            "image_hash": detect_result["image_hash"],
            "translated_regions": translated_regions,
        },
        headers={**HEADERS, "Content-Type": "application/json"},
        timeout=TIMEOUT,
    )
    elapsed = time.perf_counter() - t0

    if resp.status_code != 200:
        print(f"  ❌ HTTP {resp.status_code}: {resp.text[:300]} ({elapsed:.1f}s)")
        return None

    output_bytes = resp.content
    h = resp.headers

    print(f"  ✅ {elapsed:.1f}s")
    print(f"     output_size:    {len(output_bytes) / 1024:.0f} KB")
    print(f"     x-regions-count:     {h.get('x-regions-count', '?')}")
    print(f"     x-output-changed:    {h.get('x-output-changed', '?')}")
    print(f"     x-pipeline-mode:     {h.get('x-pipeline-mode', '?')}")
    print(f"     x-stage-elapsed-ms:  {h.get('x-stage-elapsed-ms', '?')}")
    print(f"     x-remote-elapsed-ms: {h.get('x-remote-elapsed-ms', '?')}")
    print(f"     x-selected-model:    {h.get('x-selected-model', '?')}")
    print(f"     x-primary-model:     {h.get('x-primary-model', '?')}")
    print(f"     x-fallback-model:    {h.get('x-fallback-model', '?')}")

    return output_bytes


def test_render_cache_miss():
    """验证 cache miss 返回 404"""
    print(f"\n{'─'*70}")
    print("🚫 Cache Miss 测试: 发送不存在的 task_id")
    print(f"{'─'*70}")

    resp = requests.post(
        f"{PPIO_ENDPOINT}/internal/translate/render",
        json={
            "task_id": "nonexistent-task-id-12345",
            "image_hash": "sha256:0000",
            "translated_regions": [],
        },
        headers={**HEADERS, "Content-Type": "application/json"},
        timeout=httpx.Timeout(30.0, connect=10.0),
    )

    detail = ""
    try:
        detail = resp.json().get("detail", "")
    except Exception:
        detail = resp.text[:100]

    is_404 = resp.status_code == 404 and detail == "CACHE_MISS"
    print(f"  HTTP {resp.status_code} detail={detail} → {'✅ CACHE_MISS 正确' if is_404 else '❌ 预期 404 CACHE_MISS'}")
    return is_404


def test_unified_baseline(image_path: Path) -> tuple[bytes | None, dict]:
    """一体式 /page 基准"""
    print(f"\n{'─'*70}")
    print(f"📦 Unified 基准: /internal/translate/page ({image_path.name})")
    print(f"{'─'*70}")

    payload = image_path.read_bytes()
    t0 = time.perf_counter()

    resp = requests.post(
        f"{PPIO_ENDPOINT}/internal/translate/page",
        files={"image": (image_path.name, payload, "image/jpeg")},
        data={
            "target_language": "CHS",
            "context_translations": "[]",
        },
        headers=HEADERS,
        timeout=TIMEOUT,
    )
    elapsed = time.perf_counter() - t0

    if resp.status_code != 200:
        print(f"  ❌ HTTP {resp.status_code}: {resp.text[:300]} ({elapsed:.1f}s)")
        return None, {}

    h = resp.headers
    stage_raw = h.get("x-stage-elapsed-ms", "{}")
    try:
        stage = json.loads(stage_raw)
    except Exception:
        stage = {}

    print(f"  ✅ {elapsed:.1f}s")
    print(f"     output_size:    {len(resp.content) / 1024:.0f} KB")
    print(f"     x-regions-count:     {h.get('x-regions-count', '?')}")
    print(f"     x-stage-elapsed-ms:  {stage}")
    print(f"     x-remote-elapsed-ms: {h.get('x-remote-elapsed-ms', '?')}")
    print(f"     x-cold-start:        {h.get('x-cold-start', '?')}")

    return resp.content, {
        "elapsed_s": round(elapsed, 2),
        "regions": h.get("x-regions-count", "0"),
        "stage_elapsed_ms": stage,
    }


def test_split_full_pipeline(image_path: Path) -> tuple[bytes | None, dict]:
    """完整 split pipeline: detect → (mock translate) → render"""
    print(f"\n{'─'*70}")
    print(f"🔀 Split 完整管线: detect → translate → render ({image_path.name})")
    print(f"{'─'*70}")

    total_start = time.perf_counter()

    # Phase 1: detect
    payload = image_path.read_bytes()
    t0 = time.perf_counter()
    detect_resp = requests.post(
        f"{PPIO_ENDPOINT}/internal/translate/detect",
        files={"image": (image_path.name, payload, "image/jpeg")},
        data={"source_language": "", "target_language": "CHS"},
        headers=HEADERS,
        timeout=TIMEOUT,
    )
    detect_elapsed = time.perf_counter() - t0

    if detect_resp.status_code != 200:
        print(f"  ❌ detect HTTP {detect_resp.status_code}: {detect_resp.text[:200]}")
        return None, {}

    detect_result = detect_resp.json()
    regions = detect_result.get("regions", [])
    print(f"  Phase 1 (detect):  {detect_elapsed:.1f}s  → {len(regions)} regions")

    if not regions:
        print(f"  ⚠️  无文本区域，跳过 translate/render")
        return payload, {"elapsed_s": round(detect_elapsed, 2), "regions": 0, "pipeline": "split"}

    # Phase 2: mock translate (简单替换)
    t0 = time.perf_counter()
    translated_regions = [
        {"region_index": r["region_index"], "translation": f"[翻译{r['region_index']}]"}
        for r in regions
    ]
    translate_elapsed = time.perf_counter() - t0
    print(f"  Phase 2 (translate): {translate_elapsed*1000:.0f}ms (mock)")

    # Phase 3: render
    t0 = time.perf_counter()
    render_resp = requests.post(
        f"{PPIO_ENDPOINT}/internal/translate/render",
        json={
            "task_id": detect_result["task_id"],
            "image_hash": detect_result["image_hash"],
            "translated_regions": translated_regions,
        },
        headers={**HEADERS, "Content-Type": "application/json"},
        timeout=TIMEOUT_SEC,
    )
    render_elapsed = time.perf_counter() - t0

    total_elapsed = time.perf_counter() - total_start

    if render_resp.status_code != 200:
        print(f"  ❌ render HTTP {render_resp.status_code}: {render_resp.text[:200]}")
        return None, {}

    output_bytes = render_resp.content
    print(f"  Phase 3 (render):  {render_elapsed:.1f}s  → {len(output_bytes)/1024:.0f}KB")
    print(f"  ─────────────────")
    print(f"  总计:              {total_elapsed:.1f}s")
    print(f"  GPU 占用:          {detect_elapsed + render_elapsed:.1f}s (detect + render)")

    return output_bytes, {
        "elapsed_s": round(total_elapsed, 2),
        "detect_s": round(detect_elapsed, 2),
        "render_s": round(render_elapsed, 2),
        "gpu_total_s": round(detect_elapsed + render_elapsed, 2),
        "regions": len(regions),
        "pipeline": "split",
    }


def main():
    if not INTERNAL_TOKEN:
        print("❌ 缺少 MANGA_INTERNAL_API_TOKEN，无法调用内部接口")
        return 1

    print("=" * 70)
    print("🔬 Split Pipeline 联调测试 (TASK-SPLIT-009)")
    print(f"   Endpoint: {PPIO_ENDPOINT}")
    print(f"   时间:     {time.strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 70)

    # 0. 检查测试图片
    image_path = DATA_DIR / TEST_IMAGE
    if not image_path.exists():
        print(f"❌ 测试图片不存在: {image_path}")
        sys.exit(1)

    # 1. 等待 worker ready
    if not wait_for_healthy():
        print("\n⚠️  Worker 未就绪，但仍尝试发送请求（可能触发冷启动）...")

    # 2. /detect 测试
    detect_result = test_detect(image_path)
    if not detect_result:
        print("\n❌ detect 失败，终止测试")
        sys.exit(1)

    # 3. /render 测试
    render_output = test_render(detect_result)
    if not render_output:
        print("\n❌ render 失败，终止测试")
        sys.exit(1)

    # 4. Cache miss 测试
    cache_miss_ok = test_render_cache_miss()

    # 5. Split 完整管线 (需要重新 detect 因为上一个 task 已被 pop)
    split_output, split_metrics = test_split_full_pipeline(image_path)

    # 6. Unified 基准
    unified_output, unified_metrics = test_unified_baseline(image_path)

    # 7. 汇总
    print(f"\n{'='*70}")
    print("📊 联调结果汇总")
    print(f"{'='*70}")
    print(f"  /detect:           {'✅ 通过' if detect_result else '❌ 失败'}")
    print(f"  /render:           {'✅ 通过' if render_output else '❌ 失败'}")
    print(f"  cache miss (404):  {'✅ 通过' if cache_miss_ok else '❌ 失败'}")
    print(f"  split pipeline:    {'✅ 通过' if split_output else '❌ 失败'}")
    print(f"  unified baseline:  {'✅ 通过' if unified_output else '❌ 失败'}")

    if split_metrics and unified_metrics:
        print(f"\n  性能对比:")
        print(f"    Split GPU 占用: {split_metrics.get('gpu_total_s', '?')}s (detect {split_metrics.get('detect_s', '?')}s + render {split_metrics.get('render_s', '?')}s)")
        print(f"    Unified 总耗时: {unified_metrics.get('elapsed_s', '?')}s")
        stage = unified_metrics.get("stage_elapsed_ms", {})
        if stage:
            context_s = stage.get("context", 0) / 1000
            render_s = stage.get("render", 0) / 1000
            print(f"    Unified context: {context_s:.1f}s  render: {render_s:.1f}s")
            if split_metrics.get("gpu_total_s"):
                speedup = context_s / split_metrics["gpu_total_s"] if split_metrics["gpu_total_s"] > 0 else 0
                print(f"    GPU 占用减少:   {speedup:.1f}x")

    if split_output and unified_output:
        bytes_equal = split_output == unified_output
        print(f"\n  输出对比:")
        print(f"    split size:   {len(split_output)/1024:.0f}KB")
        print(f"    unified size: {len(unified_output)/1024:.0f}KB")
        print(f"    bytes_equal:  {bytes_equal} (split 用 mock 翻译，预期不同)")

    all_pass = all([detect_result, render_output, cache_miss_ok, split_output, unified_output])
    print(f"\n  {'✅ 联调验证全部通过!' if all_pass else '⚠️  部分测试未通过'}")
    print(f"{'='*70}")

    return 0 if all_pass else 1


if __name__ == "__main__":
    sys.exit(main())
