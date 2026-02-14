#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Qt/CLI 路径分阶段计时诊断 — 与 vue_api_path_timed.py 对比。

模拟 Qt/CLI 的批量翻译路径：
  translator.translate_batch([(image, config)])

用法：
    python3 scripts/diagnostics/qt_cli_path_timed.py --runs 1
"""

import argparse
import asyncio
import os
import time
from pathlib import Path

os.environ.setdefault("PYTORCH_ALLOC_CONF", "expandable_segments:True")

_timings = {}


def _record(name: str, elapsed: float) -> None:
    _timings.setdefault(name, []).append(elapsed)


class HookManager:
    """Manage temporary monkey patches for MangaTranslator timing hooks."""

    def __init__(self) -> None:
        self.installed = False
        self._originals = {}

    @staticmethod
    def _wrap_async(original_fn, label):
        async def wrapped(self, *args, **kwargs):
            t0 = time.perf_counter()
            result = await original_fn(self, *args, **kwargs)
            _record(label, time.perf_counter() - t0)
            return result

        return wrapped

    def install(self) -> None:
        if self.installed:
            print("✅ 计时钩子已安装（跳过重复安装）")
            return

        from manga_translator.manga_translator import MangaTranslator

        patch_specs = [
            ("_translate_until_translation", "1_预处理(检测+OCR)"),
            ("_batch_translate_texts", "2_翻译(Gemini API)"),
            ("_complete_translation_pipeline", "3_渲染(mask+inpaint+render)"),
            ("_apply_post_translation_processing", "4_后处理(过滤+校验)"),
        ]

        for attr_name, label in patch_specs:
            original = getattr(MangaTranslator, attr_name)
            self._originals[attr_name] = original
            setattr(MangaTranslator, attr_name, self._wrap_async(original, label))

        if hasattr(MangaTranslator, "_load_and_prepare_prompts"):
            original = getattr(MangaTranslator, "_load_and_prepare_prompts")
            self._originals["_load_and_prepare_prompts"] = original
            setattr(
                MangaTranslator,
                "_load_and_prepare_prompts",
                self._wrap_async(original, "2a_提示词加载"),
            )

        self.installed = True
        print("✅ 计时钩子已安装")

    def restore(self) -> None:
        if not self.installed:
            return

        from manga_translator.manga_translator import MangaTranslator

        for attr_name, original in self._originals.items():
            setattr(MangaTranslator, attr_name, original)

        self._originals.clear()
        self.installed = False
        print("✅ 计时钩子已恢复")


def print_timing_report(run_label: str = "") -> None:
    print()
    print("=" * 65)
    print(f"⏱️  分阶段耗时报告 {run_label}")
    print("=" * 65)
    total = 0
    for name, times in sorted(_timings.items()):
        elapsed = sum(times)
        total += elapsed
        calls = len(times)
        if calls > 1:
            print(
                f"  {name:40s}  {elapsed:8.2f}s  ({calls} 次, 均 {elapsed/calls:.2f}s)"
            )
        else:
            print(f"  {name:40s}  {elapsed:8.2f}s")
    print(f"  {'─' * 40}  {'─' * 8}")
    print(f"  {'已追踪的总耗时':40s}  {total:8.2f}s")
    print()


async def run_qt_cli_translate(image_path_str: str, output_path_str: str, run_num: int) -> None:
    """模拟 Qt/CLI 路径: 直接创建 translator 并调用 translate_batch."""

    from PIL import Image

    image_path = Path(image_path_str)
    output_path = Path(output_path_str)

    if not image_path.exists():
        print(f"❌ 图片不存在: {image_path}")
        return

    print(f"\n{'─' * 65}")
    print(f"🔬 第 {run_num} 次运行 (Qt/CLI 路径)")
    print(f"{'─' * 65}")
    print(f"📖 图片: {image_path.name} ({image_path.stat().st_size / 1024:.1f} KB)")

    _timings.clear()

    try:
        t0 = time.perf_counter()
        from manga_translator.server.core.config_manager import load_default_config

        config = load_default_config()
        _record("0_Config加载", time.perf_counter() - t0)

        print(f"   翻译器: {config.translator.translator}")
        print(f"   目标语言: {config.translator.target_lang}")
        print(f"   use_gpu: {config.cli.use_gpu if hasattr(config.cli, 'use_gpu') else 'N/A'}")
        print(f"   inpainter: {config.inpainter.inpainter}")
        print(f"   inpainting_size: {config.inpainter.inpainting_size}")
        print(f"   batch_size: {config.cli.batch_size if hasattr(config.cli, 'batch_size') else '1'}")

        t0 = time.perf_counter()
        from manga_translator import MangaTranslator

        use_gpu = config.cli.use_gpu if hasattr(config.cli, "use_gpu") else False
        params = {
            "use_gpu": use_gpu,
            "verbose": False,
            "models_ttl": 0,
        }
        translator = MangaTranslator(params=params)
        _record("0a_Translator创建", time.perf_counter() - t0)
        print(f"   translator.device: {translator.device}")

        t0 = time.perf_counter()
        with open(image_path, "rb") as fp:
            image = Image.open(fp)
            image.load()
        image.name = str(image_path)
        _record("0b_图片加载", time.perf_counter() - t0)

        images_with_configs = [(image, config)]
        output_path.parent.mkdir(parents=True, exist_ok=True)

        print("🔄 开始翻译 (Qt/CLI 路径: translator.translate_batch)...")
        t_translate_start = time.perf_counter()
        contexts = await translator.translate_batch(images_with_configs)
        total_translate = time.perf_counter() - t_translate_start
        _record("TOTAL_translate_batch", total_translate)

        if not contexts or not contexts[0] or not getattr(contexts[0], "result", None):
            print("❌ 翻译失败: context 无结果")
            print_timing_report(f"(第 {run_num} 次)")
            return

        ctx = contexts[0]
        result_image = ctx.result
        if output_path.suffix.lower() in {".jpg", ".jpeg"} and result_image.mode in {
            "RGBA",
            "LA",
        }:
            background = Image.new("RGB", result_image.size, (255, 255, 255))
            if "A" in result_image.getbands():
                background.paste(
                    result_image.convert("RGB"), mask=result_image.getchannel("A")
                )
            else:
                background.paste(result_image.convert("RGB"))
            result_image = background
        elif result_image.mode not in {"RGB", "L"}:
            result_image = result_image.convert("RGB")
        result_image.save(output_path)

        regions_count = len(getattr(ctx, "text_regions", []) or [])

        print(f"   ✅ 翻译成功! 检测到 {regions_count} 个文本区域")
        print(f"   ⏱️  translate_batch 耗时: {total_translate:.1f}s")
        print(f"   💾 输出: {output_path}")

    except Exception as exc:
        print(f"❌ 翻译失败: {exc.__class__.__name__}: {exc}")
        import traceback

        traceback.print_exc()

    print_timing_report(f"(第 {run_num} 次 — Qt/CLI 路径)")


async def main() -> None:
    repo_root = Path(__file__).resolve().parents[2]
    default_image = repo_root / (
        "manga_translator/server/data/raw/"
        "isekai-dragondick-knight-commander/chapter-1/001.jpg"
    )
    default_output = repo_root / "result/test_qt_cli_output.jpg"

    parser = argparse.ArgumentParser(description="Qt/CLI 路径分阶段计时诊断")
    parser.add_argument("--runs", type=int, default=1, help="运行次数（默认 1）")
    parser.add_argument(
        "--image",
        type=str,
        default=os.getenv("MANGA_TEST_IMAGE", str(default_image)),
        help="输入图片路径",
    )
    parser.add_argument(
        "--output",
        type=str,
        default=os.getenv("MANGA_TEST_OUTPUT", str(default_output)),
        help="输出路径",
    )
    args = parser.parse_args()

    print("=" * 65)
    print("🔬 Qt/CLI 路径 — 分阶段计时诊断")
    print("   直接调用 translator.translate_batch() — 无线程池/semaphore")
    print("=" * 65)

    hooks = HookManager()
    hooks.install()
    try:
        for run in range(1, args.runs + 1):
            await run_qt_cli_translate(args.image, args.output, run)
    finally:
        hooks.restore()


if __name__ == "__main__":
    asyncio.run(main())
