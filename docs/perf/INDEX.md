# Performance Docs Index

## 目的

该目录存放性能分析与对照实验文档，分为“结论文档”与“实验产物”两类。

## 结论文档（优先阅读）

- 快速基准：`docs/perf/2026-02-10-quick-benchmark.md`
- Web 优化报告：`docs/perf/2026-02-10-web-optimization-report.md`
- Web 与 Qt 对齐基线：`docs/perf/2026-02-10-web-vs-qt-aligned-baseline.md`
- 上下文交接：`docs/perf/CONTEXT_HANDOFF.md`

## 实验产物

- 目录：`docs/perf/artifacts/`
- 说明：存放样例图与可视化对照证据，用于复现实验结论。
- 当前样例：`docs/perf/artifacts/2026-02-10-real-image-view/README.md`

## 维护约定

- 文档结论更新写入 `.md`，不要只留在截图或临时脚本输出。
- artifacts 仅保留关键复现样本，避免持续膨胀。
- 若结论与主计划冲突，以最新 `docs/gpu-translation-split-plan.md` 与 `docs/2026-02-10-project-audit.md` 为准，并在本目录文档注明差异来源。
