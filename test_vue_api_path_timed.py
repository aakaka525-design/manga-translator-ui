#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
分阶段计时诊断脚本 — 精确定位 Vue/API 路径翻译的耗时分布。

基于 test_vue_api_path.py，在翻译流程的关键节点插入 monkey-patch 计时，
分别测量：模型初始化、检测、OCR、翻译（Gemini API 调用）、渲染等阶段耗时。

用法：
    python test_vue_api_path_timed.py

可选：运行两次来区分首次模型加载与稳态翻译耗时：
    python test_vue_api_path_timed.py --runs 2
"""
import asyncio
import sys
import os
import time
import argparse

# 在 PyTorch 初始化前设置显存优化
os.environ.setdefault('PYTORCH_ALLOC_CONF', 'expandable_segments:True')

# ======================================================================
# Monkey-patch: 在 MangaTranslator 的关键方法中注入计时
# ======================================================================

_timings = {}

def _record(name, elapsed):
    """记录一个阶段的耗时"""
    _timings.setdefault(name, []).append(elapsed)


def install_timing_hooks():
    """
    对 MangaTranslator 的关键方法进行 monkey-patch，注入计时逻辑。
    """
    from manga_translator.manga_translator import MangaTranslator

    # --- Hook: _translate_until_translation (预处理 = 检测 + OCR + 文本行合并) ---
    _orig_translate_until = MangaTranslator._translate_until_translation

    async def _timed_translate_until(self, image, config, *args, **kwargs):
        t0 = time.perf_counter()
        result = await _orig_translate_until(self, image, config, *args, **kwargs)
        _record("1_预处理(检测+OCR)", time.perf_counter() - t0)
        return result

    MangaTranslator._translate_until_translation = _timed_translate_until

    # --- Hook: _batch_translate_texts (翻译阶段 = Gemini API 调用) ---
    _orig_batch_translate = MangaTranslator._batch_translate_texts

    async def _timed_batch_translate(self, *args, **kwargs):
        t0 = time.perf_counter()
        result = await _orig_batch_translate(self, *args, **kwargs)
        _record("2_翻译(Gemini API)", time.perf_counter() - t0)
        return result

    MangaTranslator._batch_translate_texts = _timed_batch_translate

    # --- Hook: _complete_translation_pipeline (渲染阶段 = mask + inpaint + render) ---
    _orig_complete = MangaTranslator._complete_translation_pipeline

    async def _timed_complete(self, ctx, config, *args, **kwargs):
        t0 = time.perf_counter()
        result = await _orig_complete(self, ctx, config, *args, **kwargs)
        _record("3_渲染(mask+inpaint+render)", time.perf_counter() - t0)
        return result

    MangaTranslator._complete_translation_pipeline = _timed_complete

    # --- Hook: _apply_post_translation_processing (后处理) ---
    _orig_post = MangaTranslator._apply_post_translation_processing

    async def _timed_post(self, ctx, config, *args, **kwargs):
        t0 = time.perf_counter()
        result = await _orig_post(self, ctx, config, *args, **kwargs)
        _record("4_后处理(过滤+校验)", time.perf_counter() - t0)
        return result

    MangaTranslator._apply_post_translation_processing = _timed_post

    # --- Hook: _load_and_prepare_prompts (提示词加载) ---
    if hasattr(MangaTranslator, '_load_and_prepare_prompts'):
        _orig_prompts = MangaTranslator._load_and_prepare_prompts

        async def _timed_prompts(self, config, ctx, *args, **kwargs):
            t0 = time.perf_counter()
            result = await _orig_prompts(self, config, ctx, *args, **kwargs)
            _record("2a_提示词加载", time.perf_counter() - t0)
            return result

        MangaTranslator._load_and_prepare_prompts = _timed_prompts

    print("✅ 计时钩子已安装")


def print_timing_report(run_label: str = ""):
    """打印分阶段耗时报告"""
    print()
    print("=" * 65)
    print(f"⏱️  分阶段耗时报告 {run_label}")
    print("=" * 65)

    total = 0
    for name, times in sorted(_timings.items()):
        elapsed = sum(times)
        total += elapsed
        calls = len(times)
        avg = elapsed / calls if calls > 1 else elapsed
        if calls > 1:
            print(f"  {name:40s}  {elapsed:8.2f}s  ({calls} 次, 均 {avg:.2f}s)")
        else:
            print(f"  {name:40s}  {elapsed:8.2f}s")

    print(f"  {'─' * 40}  {'─' * 8}")
    print(f"  {'已追踪的总耗时':40s}  {total:8.2f}s")
    print()


async def run_translate(image_path_str: str, output_path_str: str, run_num: int):
    from pathlib import Path

    image_path = Path(image_path_str)
    output_path = Path(output_path_str)

    if not image_path.exists():
        print(f"❌ 图片不存在: {image_path}")
        return

    print(f"\n{'─' * 65}")
    print(f"🔬 第 {run_num} 次运行")
    print(f"{'─' * 65}")
    print(f"📖 图片: {image_path.name} ({image_path.stat().st_size / 1024:.1f} KB)")

    payload = image_path.read_bytes()
    output_path.parent.mkdir(parents=True, exist_ok=True)

    _timings.clear()

    try:
        from manga_translator.server.core.config_manager import load_default_config
        from manga_translator.server.core.task_manager import get_global_translator, get_server_config
        from manga_translator.server.main import _ensure_runtime_server_config
        from manga_translator.server.request_extraction import get_ctx
        from starlette.requests import Request

        resolved_use_gpu = _ensure_runtime_server_config()
        runtime_cfg = get_server_config()

        # 1. Config 加载计时
        t0 = time.perf_counter()
        config = load_default_config()
        _record("0_Config加载", time.perf_counter() - t0)
        print(f"   翻译器: {config.translator.translator}, 目标语言: {config.translator.target_lang}")
        print(
            f"   runtime: use_gpu={resolved_use_gpu}, "
            f"source={runtime_cfg.get('_runtime_config_source')}"
        )

        # 2. 构造 fake request
        fake_request = Request({
            "type": "http",
            "method": "POST",
            "path": "/api/v1/translate/page",
            "headers": []
        })

        # 3. 翻译（包含翻译器初始化 + 完整翻译流程）
        print(f"🔄 开始翻译...")
        t_total_start = time.perf_counter()

        ctx = await get_ctx(fake_request, config, payload, "normal")

        t_total = time.perf_counter() - t_total_start
        _record("TOTAL_get_ctx", t_total)

        # 4. 结果处理
        if not getattr(ctx, "result", None):
            print(f"❌ 翻译失败: ctx.result is None")
            print_timing_report(f"(第 {run_num} 次)")
            return

        # 保存结果
        from PIL import Image
        result_image = ctx.result
        if output_path.suffix.lower() in {".jpg", ".jpeg"} and result_image.mode in {"RGBA", "LA"}:
            background = Image.new("RGB", result_image.size, (255, 255, 255))
            if "A" in result_image.getbands():
                background.paste(result_image.convert("RGB"), mask=result_image.getchannel("A"))
            else:
                background.paste(result_image.convert("RGB"))
            result_image = background
        elif result_image.mode not in {"RGB", "L"}:
            result_image = result_image.convert("RGB")
        result_image.save(output_path)

        regions_count = len(getattr(ctx, "text_regions", []) or [])
        translator = get_global_translator()

        print(f"   ✅ 翻译成功! 检测到 {regions_count} 个文本区域")
        print(f"   ⏱️  总耗时: {t_total:.1f}s")
        print(f"   💾 输出: {output_path}")
        print(f"   ⚙️  translator.device: {getattr(translator, 'device', 'unknown')}")

    except Exception as exc:
        print(f"❌ 翻译失败: {exc.__class__.__name__}: {exc}")
        import traceback
        traceback.print_exc()

    # 打印分阶段报告
    print_timing_report(f"(第 {run_num} 次)")


async def main():
    parser = argparse.ArgumentParser(description="Vue/API 路径分阶段计时诊断")
    parser.add_argument("--runs", type=int, default=1,
                        help="运行次数（默认 1，设为 2 可对比首次加载 vs 稳态翻译）")
    parser.add_argument("--image", type=str,
                        default="/Users/xa/Desktop/projiect/manga-translator-ui_副本/manga_translator/server/data/raw/isekai-dragondick-knight-commander/chapter-1/001.jpg",
                        help="输入图片路径")
    parser.add_argument("--output", type=str,
                        default="/Users/xa/Desktop/projiect/manga-translator-ui_副本/result/test_timed_output.jpg",
                        help="输出图片路径")
    args = parser.parse_args()

    print("=" * 65)
    print("🔬 Vue/API 路径 — 分阶段计时诊断")
    print("=" * 65)

    # 安装计时钩子
    install_timing_hooks()

    for run in range(1, args.runs + 1):
        await run_translate(args.image, args.output, run)

    if args.runs > 1:
        print("\n" + "=" * 65)
        print("💡 提示: 第 1 次包含模型加载，第 2 次是纯翻译耗时")
        print("   如果两次耗时差距很大，说明模型加载是主要瓶颈")
        print("=" * 65)


if __name__ == "__main__":
    asyncio.run(main())
