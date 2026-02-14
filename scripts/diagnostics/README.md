# Diagnostics Scripts

本目录收敛所有诊断脚本，避免与 `pytest` 的 `test_*.py` 语义冲突。

## 运行方式

优先使用本目录脚本：

```bash
python scripts/diagnostics/cloudrun_benchmark.py
python scripts/diagnostics/split_pipeline_integration.py
python scripts/diagnostics/qt_cli_path_timed.py --runs 1
python scripts/diagnostics/vue_api_path.py
python scripts/diagnostics/vue_api_path_timed.py --runs 1
python scripts/diagnostics/deep_diagnosis.py --mode vue
```

兼容入口仍保留在仓库根目录（`test_*.py`），这些文件仅做转调包装，且已设置 `__test__ = False`。

## 环境变量

- `MANGA_INTERNAL_API_TOKEN`: 内部接口鉴权 token
- `MANGA_TEST_DATA_DIR`: 测试数据目录（可选）
- `MANGA_TEST_IMAGE`: 单图输入路径（可选）
- `MANGA_TEST_OUTPUT`: 单图输出路径（可选）
- `MANGA_CLOUDRUN_BENCH_URL`: Cloud Run benchmark endpoint（可选）
- `MANGA_PPIO_ENDPOINT`: PPIO endpoint（可选）
