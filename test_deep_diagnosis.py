#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
深层诊断：打印图像尺寸 + 子步骤计时。修复了闭包变量冲突。
用法：
    python test_deep_diagnosis.py --mode vue   # Vue/API 路径
    python test_deep_diagnosis.py --mode qt    # Qt/CLI 路径
"""
import asyncio, sys, os, time, argparse

os.environ.setdefault('PYTORCH_ALLOC_CONF', 'expandable_segments:True')

_timings = {}
def _record(name, elapsed):
    _timings.setdefault(name, []).append(elapsed)

def _img_size_str(image):
    if image is None: return "None"
    if hasattr(image, 'shape'):
        return f"{image.shape[1]}x{image.shape[0]} ({image.dtype})"
    elif hasattr(image, 'size'):
        return f"{image.size[0]}x{image.size[1]} (mode={image.mode})"
    return str(type(image))


def _make_hook(orig_fn, label, pre_fn=None, post_fn=None):
    """创建一个安全的计时钩子，使用参数绑定避免闭包陷阱"""
    async def hooked(self, *args, **kwargs):
        if pre_fn:
            pre_fn(self, args, kwargs)
        t0 = time.perf_counter()
        result = await orig_fn(self, *args, **kwargs)
        elapsed = time.perf_counter() - t0
        _record(label, elapsed)
        if post_fn:
            post_fn(self, result, elapsed, args, kwargs)
        return result
    return hooked


def install_deep_timing_hooks():
    from manga_translator.manga_translator import MangaTranslator

    # -- _run_upscaling
    def pre_upscale(self, args, kwargs):
        ctx = args[1] if len(args) > 1 else kwargs.get('ctx')
        if ctx:
            print(f"    📐 超分前: {_img_size_str(getattr(ctx, 'img_colorized', None))}")
    def post_upscale(self, result, elapsed, args, kwargs):
        print(f"    📐 超分后: {_img_size_str(result)} ({elapsed:.2f}s)")
    MangaTranslator._run_upscaling = _make_hook(
        MangaTranslator._run_upscaling, "  1b_超分辨率", pre_upscale, post_upscale)

    # -- _run_detection
    def pre_detect(self, args, kwargs):
        ctx = args[1] if len(args) > 1 else kwargs.get('ctx')
        if ctx:
            img = getattr(ctx, 'upscaled', None)
            if img is None: img = getattr(ctx, 'img_colorized', None)
            if img is None: img = getattr(ctx, 'input', None)
            print(f"    📐 检测输入: {_img_size_str(img)}")
    MangaTranslator._run_detection = _make_hook(
        MangaTranslator._run_detection, "  1c_检测", pre_detect)

    # -- _run_ocr
    MangaTranslator._run_ocr = _make_hook(
        MangaTranslator._run_ocr, "  1d_OCR")

    # -- _run_mask_refinement
    MangaTranslator._run_mask_refinement = _make_hook(
        MangaTranslator._run_mask_refinement, "  3a_mask_refinement")

    # -- _run_inpainting
    def pre_inpaint(self, args, kwargs):
        ctx = args[1] if len(args) > 1 else kwargs.get('ctx')
        if ctx:
            img = getattr(ctx, 'img_rgb', None)
            if img is None: img = getattr(ctx, 'upscaled', None)
            print(f"    📐 Inpaint 输入: {_img_size_str(img)}")
    def post_inpaint(self, result, elapsed, args, kwargs):
        print(f"    📐 Inpaint 输出: {_img_size_str(result)} ({elapsed:.2f}s)")
    MangaTranslator._run_inpainting = _make_hook(
        MangaTranslator._run_inpainting, "  3b_inpainting", pre_inpaint, post_inpaint)

    # -- _run_text_rendering
    MangaTranslator._run_text_rendering = _make_hook(
        MangaTranslator._run_text_rendering, "  3c_text_rendering")

    # -- 顶层: _translate_until_translation
    _orig_tu = MangaTranslator._translate_until_translation
    async def _hook_tu(self, image, config, *a, **kw):
        print(f"  📐 预处理入口图像: {_img_size_str(image)}")
        t0 = time.perf_counter()
        r = await _orig_tu(self, image, config, *a, **kw)
        e = time.perf_counter() - t0
        _record("1_预处理_TOTAL", e)
        print(f"  📐 预处理后 img_rgb: {_img_size_str(getattr(r, 'img_rgb', None))}")
        return r
    MangaTranslator._translate_until_translation = _hook_tu

    # -- 顶层: _batch_translate_texts
    MangaTranslator._batch_translate_texts = _make_hook(
        MangaTranslator._batch_translate_texts, "2_翻译(Gemini)")

    # -- 顶层: _complete_translation_pipeline
    _orig_cp = MangaTranslator._complete_translation_pipeline
    async def _hook_cp(self, ctx, config, *a, **kw):
        print(f"  📐 渲染入口 img_rgb: {_img_size_str(getattr(ctx, 'img_rgb', None))}")
        t0 = time.perf_counter()
        r = await _orig_cp(self, ctx, config, *a, **kw)
        _record("3_渲染_TOTAL", time.perf_counter() - t0)
        return r
    MangaTranslator._complete_translation_pipeline = _hook_cp

    # -- 顶层: _apply_post_translation_processing
    MangaTranslator._apply_post_translation_processing = _make_hook(
        MangaTranslator._apply_post_translation_processing, "4_后处理")

    print("✅ 深层计时钩子已安装\n")


def print_report(label):
    print(f"\n{'=' * 70}")
    print(f"⏱️  {label}")
    print("=" * 70)
    total = 0
    for name, times in sorted(_timings.items()):
        e = sum(times)
        if not name.startswith("  "): total += e
        c = len(times)
        if c > 1:
            print(f"  {name:45s}  {e:8.2f}s  ({c}次)")
        else:
            print(f"  {name:45s}  {e:8.2f}s")
    print(f"  {'─' * 45}  {'─' * 8}")
    print(f"  {'顶层总耗时':45s}  {total:8.2f}s\n")


IMAGE_PATH = "/Users/xa/Desktop/projiect/manga-translator-ui_副本/manga_translator/server/data/raw/isekai-dragondick-knight-commander/chapter-1/001.jpg"


async def run_vue():
    from pathlib import Path
    payload = Path(IMAGE_PATH).read_bytes()
    print(f"📖 图片: {Path(IMAGE_PATH).name} ({len(payload)/1024:.1f} KB)")

    from manga_translator.server.core.config_manager import load_default_config
    from manga_translator.server.core.task_manager import get_global_translator, get_server_config
    from manga_translator.server.main import _ensure_runtime_server_config
    from manga_translator.server.request_extraction import get_ctx
    from starlette.requests import Request

    resolved_use_gpu = _ensure_runtime_server_config()
    runtime_cfg = get_server_config()
    config = load_default_config()
    print(f"   translator={config.translator.translator} target={config.translator.target_lang}")
    print(f"   upscale_ratio={config.upscale.upscale_ratio} inpainter={config.inpainter.inpainter} size={config.inpainter.inpainting_size}")
    print(f"   runtime: use_gpu={resolved_use_gpu} source={runtime_cfg.get('_runtime_config_source')}")

    fake_req = Request({"type": "http", "method": "POST", "path": "/t", "headers": []})
    t0 = time.perf_counter()
    ctx = await get_ctx(fake_req, config, payload, "normal")
    total = time.perf_counter() - t0
    translator = get_global_translator()
    print(f"   ✅ {len(getattr(ctx, 'text_regions', []) or [])} 个区域, 总耗时 {total:.1f}s")
    print(f"   device={getattr(translator, 'device', 'unknown')}")
    if hasattr(ctx, 'result') and ctx.result:
        print(f"   📐 输出图像: {_img_size_str(ctx.result)}")
    print_report("Vue/API (get_ctx)")


async def run_qt():
    from pathlib import Path
    from PIL import Image

    with open(IMAGE_PATH, 'rb') as f:
        image = Image.open(f); image.load()
    image.name = IMAGE_PATH
    print(f"📖 图片: {Path(IMAGE_PATH).name} ({image.size[0]}x{image.size[1]} mode={image.mode})")

    from manga_translator.server.core.config_manager import load_default_config
    from manga_translator import MangaTranslator

    config = load_default_config()
    print(f"   translator={config.translator.translator} target={config.translator.target_lang}")
    print(f"   upscale_ratio={config.upscale.upscale_ratio} inpainter={config.inpainter.inpainter} size={config.inpainter.inpainting_size}")

    translator = MangaTranslator(params={
        'use_gpu': config.cli.use_gpu if hasattr(config.cli, 'use_gpu') else False,
        'verbose': False, 'models_ttl': 0
    })
    print(f"   device={translator.device}")

    t0 = time.perf_counter()
    contexts = await translator.translate_batch([(image, config)])
    total = time.perf_counter() - t0
    ctx = contexts[0] if contexts else None
    regions = len(getattr(ctx, 'text_regions', []) or []) if ctx else 0
    print(f"   ✅ {regions} 个区域, 总耗时 {total:.1f}s")
    if ctx and hasattr(ctx, 'result') and ctx.result:
        print(f"   📐 输出图像: {_img_size_str(ctx.result)}")
    print_report("Qt/CLI (translate_batch)")


async def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", required=True, choices=["vue", "qt"])
    args = parser.parse_args()

    print(f"🔬 深层诊断 — {'Vue/API' if args.mode == 'vue' else 'Qt/CLI'} 路径\n")
    install_deep_timing_hooks()

    if args.mode == "vue":
        await run_vue()
    else:
        await run_qt()


if __name__ == "__main__":
    asyncio.run(main())
