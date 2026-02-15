# 2026-02-10 Web vs Qt Aligned Baseline

## Goal
Establish an aligned baseline for Web chapter translation and Qt/local chain under the same runtime conditions, then quantify current gap.

## Alignment Checklist
- Host: same machine (`macOS`)
- Model: `gemini_hq`
- Runtime intent: GPU enabled (`use_gpu=True` in runtime config)
- Dataset: real chapter pages from `manga_translator/server/data/raw/isekai-dragondick-knight-commander/chapter-1`
- Chapter API path: `/api/v1/translate/chapter`
- Runtime knobs explicitly set:
  - `MANGA_V1_CHAPTER_PAGE_CONCURRENCY=2`
  - `MANGA_V1_RUNTIME_PROFILE=off`
  - `MANGA_V1_CHAPTER_EXECUTION_MODE=single_page|batch_pipeline`

## Web Real-Image Baseline (Measured)
Measured with one real page (`001.jpg`) to keep runtime short.

| Mode | chapter_total_ms | status | success_count | failed_count |
|---|---:|---|---:|---:|
| `single_page` | `80506.85` | success | 1 | 0 |
| `batch_pipeline` | `58313.14` | success | 1 | 0 |

Relative improvement (`batch_pipeline` vs `single_page`): **27.57%**.

## Qt/Local Parity Status
Direct Qt/local parity measurement is currently blocked in this environment:
1. `python -m manga_translator local ...` fails with `ModuleNotFoundError: No module named 'PyQt6'`.
2. Direct core-call benchmark (`MangaTranslator.translate`) on the same page with `gemini_hq` failed with `达到最大尝试次数 (1)，最后一次错误: Unknown error`.

Given these blockers, this document records **Web-side aligned baseline** and marks Qt parity as pending environment recovery.

## Repro Commands
```bash
# Web real one-page comparison (single_page vs batch_pipeline)
python - <<'PY'
# command used in session (benchmark harness)
PY

# Local parity attempt (blocked by PyQt6 missing)
python -m manga_translator local -i manga_translator/server/data/raw/isekai-dragondick-knight-commander/chapter-1/001.jpg -o /tmp/local-out --config examples/config.json --use-gpu --overwrite
```
