#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
测试 Vue/API 路径翻译（模拟 _translate_single_image 的完整流程）
直接调用核心逻辑，无需启动 HTTP 服务器和认证。
"""
import asyncio
import sys
import os
import time

# 在 PyTorch 初始化前设置显存优化
os.environ.setdefault('PYTORCH_ALLOC_CONF', 'expandable_segments:True')

async def run_translate_single_image_demo():
    from pathlib import Path

    repo_root = Path(__file__).resolve().parents[2]
    default_image = repo_root / (
        "manga_translator/server/data/raw/"
        "isekai-dragondick-knight-commander/chapter-1/001.jpg"
    )
    default_output = repo_root / "result/test_vue_api_output.jpg"
    image_path = Path(os.getenv("MANGA_TEST_IMAGE", str(default_image)))
    output_path = Path(os.getenv("MANGA_TEST_OUTPUT", str(default_output)))
    
    if not image_path.exists():
        print(f"❌ 图片不存在: {image_path}")
        return
    
    print(f"📖 输入图片: {image_path}")
    print(f"📝 输出路径: {output_path}")
    print(f"📐 图片大小: {image_path.stat().st_size / 1024:.1f} KB")
    print()
    
    # 模拟 Vue/API 路径: _translate_single_image
    payload = image_path.read_bytes()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    t_start = time.time()
    
    try:
        from manga_translator.server.core.config_manager import load_default_config
        from manga_translator.server.core.task_manager import get_global_translator, get_server_config
        from manga_translator.server.main import _ensure_runtime_server_config
        from manga_translator.server.request_extraction import get_ctx
        from starlette.requests import Request
        
        resolved_use_gpu = _ensure_runtime_server_config()
        runtime_cfg = get_server_config()

        # 1. 加载默认配置
        config = load_default_config()
        print(f"✅ 配置加载完成")
        print(f"   翻译器: {config.translator.translator}")
        print(f"   目标语言: {config.translator.target_lang}")
        print(f"   attempts: {config.translator.attempts}")
        print(
            f"   runtime: use_gpu={resolved_use_gpu}, "
            f"source={runtime_cfg.get('_runtime_config_source')}"
        )
        print()
        
        # 2. 构造 fake request（和 v1_translate.py 一致）
        fake_request = Request({
            "type": "http", 
            "method": "POST", 
            "path": "/api/v1/translate/page", 
            "headers": []
        })
        
        # 3. 调用 get_ctx（这是 Vue/API 路径的核心）
        print(f"🔄 开始翻译（Vue/API 路径: get_ctx → _run_translate_sync）...")
        t_translate_start = time.time()
        
        ctx = await get_ctx(fake_request, config, payload, "normal")
        
        t_translate_end = time.time()
        translate_ms = (t_translate_end - t_translate_start) * 1000
        
        # 4. 检查结果
        if not getattr(ctx, "result", None):
            print(f"❌ 翻译没有产生输出图片 (ctx.result is None)")
            print(f"   ctx attributes: {[a for a in dir(ctx) if not a.startswith('_')]}")
            return
        
        # 5. 保存结果（处理 RGBA→RGB 转换）
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
        
        t_total = time.time() - t_start
        
        print()
        print("=" * 60)
        print("📊 翻译结果")
        print("=" * 60)
        print(f"   ✅ 翻译成功！")
        print(f"   📝 检测到文本区域数: {regions_count}")
        print(f"   ⏱️  翻译耗时: {translate_ms:.0f}ms ({translate_ms/1000:.1f}s)")
        print(f"   ⏱️  总耗时: {t_total*1000:.0f}ms ({t_total:.1f}s)")
        print(f"   💾 输出文件: {output_path}")
        print(f"   💾 输出大小: {output_path.stat().st_size / 1024:.1f} KB")
        print(f"   ⚙️  translator.device: {getattr(translator, 'device', 'unknown')}")
        
        # 打印翻译的文本
        if hasattr(ctx, 'text_regions') and ctx.text_regions:
            print()
            print("📖 翻译的文本:")
            for i, region in enumerate(ctx.text_regions):
                src = getattr(region, 'text', '') or ''
                tgt = getattr(region, 'translation', '') or ''
                if src or tgt:
                    print(f"   [{i+1}] {src[:50]} → {tgt[:50]}")
        
    except Exception as exc:
        t_total = time.time() - t_start
        print(f"❌ 翻译失败！")
        print(f"   异常类型: {exc.__class__.__name__}")
        print(f"   异常信息: {exc}")
        print(f"   ⏱️  耗时: {t_total*1000:.0f}ms ({t_total:.1f}s)")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    print("=" * 60)
    print("🔬 Vue/API 路径翻译测试")
    print("=" * 60)
    print()
    asyncio.run(run_translate_single_image_demo())
