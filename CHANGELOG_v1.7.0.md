# 更新日志 v1.7.0

## 🐛 Bug修复

### 修复仅上色模式批量处理失败问题
- **问题**: 在高质量翻译模式下使用仅上色功能时，所有图片被错误标记为失败
- **原因**: 仅上色模式设置了空的 `text_regions`，但高质量批处理的完成管道(`_complete_translation_pipeline`)仍然被调用，检测到空区域后触发"Text translator returned empty queries"警告并将 `ctx.result` 重置为 `None`
- **修复**: 
  - 在 `_complete_translation_pipeline` 方法开始处添加仅上色模式检查，直接返回上色结果
  - 在高质量批处理渲染阶段添加条件判断，跳过仅上色模式下的渲染管道调用
- **影响**: 仅上色模式现在可以正确保存结果并标记为成功状态

## 📝 配置更新

### examples/config-example.json
- 移除了绝对路径示例（`last_open_dir` 和 `last_output_path` 设为空字符串）
- 更新 `colorization_size` 从 576 到 2048（提高上色质量）
- 修正上色器配置

## 🧪 测试

- 新增 `test_colorize_only_batch.py` 测试脚本，用于验证仅上色批处理功能

## 📋 技术细节

**修改文件**:
1. `manga_translator/manga_translator.py`
   - 第3098-3100行：添加仅上色模式提前返回逻辑
   - 第3568-3570行：添加渲染管道跳过检查

2. `examples/config-example.json`
   - 清理示例配置文件的绝对路径
   - 优化默认上色参数

**版本对比**: 1.6.8 → 1.7.0

**发布日期**: 2025-10-26

