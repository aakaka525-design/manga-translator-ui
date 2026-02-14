#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Cloud Run GPU 翻译服务基准测试

对 /internal/translate/page 发送不同尺寸图片，记录：
- 总响应时间（含网络 + 冷启动 + 翻译）
- 服务端返回的 stage_elapsed_ms 细分
- cold_start 标记
- regions_count

用法：
    python3 test_cloudrun_benchmark.py
"""

import requests
import time
import json
import os
import sys
from pathlib import Path

# ============================================================
# 配置
# ============================================================
CLOUDRUN_URL = os.getenv(
    "MANGA_CLOUDRUN_BENCH_URL",
    "https://manga-translator-compute-1020452004370.europe-west1.run.app",
)
INTERNAL_TOKEN = os.getenv("MANGA_INTERNAL_API_TOKEN", "")
ENDPOINT = f"{CLOUDRUN_URL.rstrip('/')}/internal/translate/page"

# 测试图片（从小到大）
REPO_ROOT = Path(__file__).resolve().parent
DEFAULT_DATA_DIR = (
    REPO_ROOT
    / "manga_translator/server/data/raw/isekai-dragondick-knight-commander/chapter-1"
)
DATA_DIR = Path(os.getenv("MANGA_TEST_DATA_DIR", str(DEFAULT_DATA_DIR)))
TEST_IMAGES = [
    "016.jpg",  # 720x8837   340KB  (最小)
    "002.jpg",  # 720x13385  472KB  (中等)
    "001.jpg",  # 720x14046  468KB  (最大)
]

# GPU 单价（europe-west1, 无冗余, CPU always allocated）
GPU_PRICE_PER_SEC = 0.0001867
CPU_PRICE_PER_SEC = 0.0000180  # per vCPU
MEM_PRICE_PER_SEC = 0.0000020  # per GiB
VCPUS = 4
MEM_GIB = 16


def estimate_cost(seconds: float) -> float:
    """估算一次请求的费用"""
    gpu = seconds * GPU_PRICE_PER_SEC
    cpu = seconds * VCPUS * CPU_PRICE_PER_SEC
    mem = seconds * MEM_GIB * MEM_PRICE_PER_SEC
    return gpu + cpu + mem


def run_benchmark(image_path: Path, run_label: str) -> dict:
    """发送一次翻译请求并记录指标"""
    file_size_kb = image_path.stat().st_size / 1024

    # 获取图片尺寸
    try:
        from PIL import Image
        with Image.open(image_path) as img:
            width, height = img.size
        size_str = f"{width}x{height}"
    except Exception:
        size_str = "unknown"

    print(f"\n  [{run_label}] {image_path.name} ({size_str}, {file_size_kb:.0f}KB)")
    print(f"  发送请求到 Cloud Run...", end="", flush=True)

    t0 = time.perf_counter()
    try:
        with open(image_path, "rb") as f:
            resp = requests.post(
                ENDPOINT,
                files={"image": (image_path.name, f, "image/jpeg")},
                data={
                    "target_language": "CHS",
                    "context_translations": "[]",
                },
                headers={"X-Internal-Token": INTERNAL_TOKEN},
                timeout=600,  # 10分钟超时（含冷启动）
            )
        elapsed = time.perf_counter() - t0
    except requests.exceptions.Timeout:
        elapsed = time.perf_counter() - t0
        print(f" ❌ 超时 ({elapsed:.1f}s)")
        return {"status": "timeout", "elapsed": elapsed}
    except Exception as e:
        elapsed = time.perf_counter() - t0
        print(f" ❌ 错误: {e} ({elapsed:.1f}s)")
        return {"status": "error", "elapsed": elapsed, "error": str(e)}

    result = {
        "image": image_path.name,
        "size": size_str,
        "file_kb": round(file_size_kb),
        "elapsed_s": round(elapsed, 2),
        "status_code": resp.status_code,
    }

    if resp.status_code == 200:
        # 解析响应头
        regions = resp.headers.get("x-regions-count", "?")
        cold_start = resp.headers.get("x-cold-start", "?")
        remote_elapsed = resp.headers.get("x-remote-elapsed-ms", "?")
        stage_elapsed_raw = resp.headers.get("x-stage-elapsed-ms", "{}")
        output_changed = resp.headers.get("x-output-changed", "?")
        fallback_used = resp.headers.get("x-fallback-used", "0")

        try:
            stage_elapsed = json.loads(stage_elapsed_raw)
        except Exception:
            stage_elapsed = {}

        result.update({
            "regions": int(regions) if regions != "?" else 0,
            "cold_start": cold_start,
            "remote_elapsed_ms": remote_elapsed,
            "stage_elapsed_ms": stage_elapsed,
            "output_changed": output_changed,
            "fallback_used": fallback_used,
            "response_kb": round(len(resp.content) / 1024),
            "cost_usd": round(estimate_cost(elapsed), 5),
        })

        cost_str = f"${result['cost_usd']:.4f}"
        print(f" ✅ {elapsed:.1f}s | {regions} 区域 | 冷启动={cold_start} | 费用≈{cost_str}")

        if stage_elapsed:
            print(f"    服务端分阶段耗时:")
            for k, v in stage_elapsed.items():
                print(f"      {k}: {v}ms ({v/1000:.1f}s)")
    else:
        body = resp.text[:200]
        print(f" ❌ HTTP {resp.status_code}: {body} ({elapsed:.1f}s)")
        result["error"] = body

    return result


def main():
    if not INTERNAL_TOKEN:
        print("❌ 缺少 MANGA_INTERNAL_API_TOKEN，无法调用内部接口")
        return 1

    print("=" * 70)
    print("🔬 Cloud Run GPU 翻译基准测试")
    print(f"   服务: {CLOUDRUN_URL}")
    print(f"   GPU 单价: ${GPU_PRICE_PER_SEC}/s (L4, europe-west1)")
    print("=" * 70)

    # 检查图片
    available = []
    for name in TEST_IMAGES:
        p = DATA_DIR / name
        if p.exists():
            available.append(p)
        else:
            print(f"⚠️  跳过不存在的图片: {name}")

    if not available:
        print("❌ 没有可用的测试图片")
        return 1

    results = []

    # 第一轮：冷启动测试（如果实例已缩容）
    print(f"\n{'─' * 70}")
    print("📊 第 1 轮：可能包含冷启动")
    print(f"{'─' * 70}")
    for img in available:
        r = run_benchmark(img, "R1")
        results.append(r)

    # 第二轮：热实例测试
    print(f"\n{'─' * 70}")
    print("📊 第 2 轮：热实例（无冷启动）")
    print(f"{'─' * 70}")
    for img in available:
        r = run_benchmark(img, "R2")
        results.append(r)

    # 汇总
    print(f"\n{'=' * 70}")
    print("📊 汇总")
    print("=" * 70)
    print(f"{'轮次':>4s}  {'图片':>10s}  {'尺寸':>12s}  {'耗时':>8s}  {'区域':>4s}  {'冷启动':>6s}  {'费用':>8s}")
    print(f"{'─' * 4}  {'─' * 10}  {'─' * 12}  {'─' * 8}  {'─' * 4}  {'─' * 6}  {'─' * 8}")

    for i, r in enumerate(results):
        if r.get("status_code") == 200:
            round_num = "R1" if i < len(available) else "R2"
            print(
                f"{round_num:>4s}  {r['image']:>10s}  {r['size']:>12s}  "
                f"{r['elapsed_s']:>7.1f}s  {r.get('regions', '?'):>4}  "
                f"{r.get('cold_start', '?'):>6s}  ${r.get('cost_usd', 0):.4f}"
            )

    # 月费估算
    ok_results = [r for r in results if r.get("status_code") == 200]
    if ok_results:
        avg_time = sum(r["elapsed_s"] for r in ok_results) / len(ok_results)
        avg_cost = sum(r.get("cost_usd", 0) for r in ok_results) / len(ok_results)
        print(f"\n  平均单页: {avg_time:.1f}s, ${avg_cost:.4f}")
        for label, pages_per_month in [("轻度(1章/天)", 300), ("中度(5章/天)", 1500), ("重度(20章/天)", 6000)]:
            print(f"  {label}: {pages_per_month} 页/月 ≈ ${pages_per_month * avg_cost:.1f}/月")

    return 0

if __name__ == "__main__":
    sys.exit(main())
