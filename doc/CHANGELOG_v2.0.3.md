# v2.0.3 更新日志

发布日期：2026-01-03

## 🐛 修复

### OCR 模块 GPU 清理重构
- **重构 GPU 显存清理逻辑**：将 `model_32px.py` 和 `model_48px.py` 中神经网络类内部的 GPU 清理代码移除，改为在外层模型类的 `_infer` 方法中使用统一的 `_cleanup_ocr_memory` 方法
- 删除 OCR 神经网络类中直接调用 `torch.cuda.empty_cache()` 的代码，避免神经网络类关心 GPU 管理细节
- 统一使用 `common.py` 中的 `_cleanup_ocr_memory` 方法，该方法会自动检查 `use_gpu` 标志，确保只在使用 GPU 时才清理显存
