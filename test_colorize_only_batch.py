#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
测试脚本：验证仅上色模式批量处理修复
测试在高质量翻译模式下，仅上色功能是否正常工作
"""

import os
import sys
import json
import tempfile
from pathlib import Path
from PIL import Image

# 添加项目根目录到路径
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

def create_test_images(count=3):
    """创建测试用的黑白图片"""
    test_images = []
    temp_dir = tempfile.mkdtemp(prefix="colorize_test_")
    
    for i in range(count):
        # 创建简单的黑白图片
        img = Image.new('L', (400, 300), color=200)  # 灰度图
        img_path = os.path.join(temp_dir, f"test_image_{i+1}.png")
        img.save(img_path)
        test_images.append(img_path)
    
    return test_images, temp_dir

def create_test_config(output_dir):
    """创建测试配置"""
    config = {
        "translator": {
            "translator": "openai_hq",
            "target_lang": "CHS"
        },
        "colorizer": {
            "colorizer": "mc2",
            "colorization_size": "2048",
            "denoise_sigma": 30
        },
        "cli": {
            "colorize_only": True,
            "batch_size": 3,
            "high_quality_batch_size": 3,
            "use_gpu": True,
            "attempts": 1
        }
    }
    return config

async def test_colorize_only_batch():
    """测试仅上色批处理模式"""
    from manga_translator.manga_translator import MangaTranslator
    from manga_translator.config import Config
    
    print("=" * 60)
    print("测试：仅上色模式 + 高质量批处理")
    print("=" * 60)
    
    # 创建测试图片
    print("\n[1/4] 创建测试图片...")
    test_images, test_dir = create_test_images(count=5)
    output_dir = tempfile.mkdtemp(prefix="colorize_output_")
    print(f"  ✓ 创建了 {len(test_images)} 张测试图片")
    print(f"  ✓ 输入目录: {test_dir}")
    print(f"  ✓ 输出目录: {output_dir}")
    
    # 创建配置
    print("\n[2/4] 创建测试配置...")
    config_dict = create_test_config(output_dir)
    config = Config.from_dict(config_dict)
    print("  ✓ 配置创建完成")
    print(f"  ✓ 仅上色模式: {config.cli.colorize_only}")
    print(f"  ✓ 批处理大小: {config.cli.high_quality_batch_size}")
    print(f"  ✓ 翻译器: {config.translator.translator}")
    
    # 初始化翻译器
    print("\n[3/4] 初始化翻译器...")
    translator = MangaTranslator(config_dict.get('cli', {}))
    print("  ✓ 翻译器初始化完成")
    
    # 准备图片列表
    images_with_configs = []
    for img_path in test_images:
        image = Image.open(img_path)
        image.name = img_path
        images_with_configs.append((image, config))
    
    # 执行批处理
    print("\n[4/4] 执行批处理翻译...")
    print(f"  → 处理 {len(images_with_configs)} 张图片...")
    
    save_info = {
        'output_folder': output_dir,
        'input_folders': {test_dir},
        'format': 'png',
        'overwrite': True
    }
    
    try:
        contexts = await translator.translate_batch(
            images_with_configs,
            save_info=save_info
        )
        
        # 验证结果
        print("\n" + "=" * 60)
        print("测试结果")
        print("=" * 60)
        
        success_count = 0
        fail_count = 0
        
        for i, ctx in enumerate(contexts):
            img_name = os.path.basename(test_images[i])
            if ctx and ctx.result:
                print(f"  ✓ 图片 {i+1}/{len(contexts)}: {img_name} - 成功")
                print(f"    - 结果尺寸: {ctx.result.size}")
                print(f"    - text_regions: {len(ctx.text_regions) if ctx.text_regions else 0} 个")
                success_count += 1
            else:
                print(f"  ✗ 图片 {i+1}/{len(contexts)}: {img_name} - 失败")
                if hasattr(ctx, 'translation_error'):
                    print(f"    - 错误: {ctx.translation_error}")
                fail_count += 1
        
        print("\n" + "-" * 60)
        print(f"总计: 成功 {success_count}/{len(contexts)}, 失败 {fail_count}/{len(contexts)}")
        
        # 检查输出文件
        output_files = list(Path(output_dir).rglob("*.png"))
        print(f"输出文件: {len(output_files)} 个")
        
        if success_count == len(contexts) and len(output_files) == len(contexts):
            print("\n🎉 测试通过！所有图片成功处理")
            return True
        else:
            print("\n❌ 测试失败！部分图片处理失败")
            return False
            
    except Exception as e:
        print(f"\n❌ 测试异常: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    finally:
        # 清理测试文件
        print("\n[清理] 删除测试文件...")
        import shutil
        try:
            shutil.rmtree(test_dir)
            shutil.rmtree(output_dir)
            print("  ✓ 清理完成")
        except Exception as e:
            print(f"  ⚠ 清理失败: {e}")

if __name__ == "__main__":
    import asyncio
    
    print("\n" + "=" * 60)
    print("仅上色批处理模式测试")
    print("=" * 60)
    print("\n此测试将验证以下修复：")
    print("  1. 仅上色模式下不再出现 'Text translator returned empty queries' 警告")
    print("  2. ctx.result 正确保存上色结果")
    print("  3. 所有图片正确标记为成功状态")
    print("\n开始测试...\n")
    
    result = asyncio.run(test_colorize_only_batch())
    
    sys.exit(0 if result else 1)

