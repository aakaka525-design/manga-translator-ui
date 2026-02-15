# 2026-02-10 Web Optimization Report

## Summary
This round implemented the Vue Web chapter translation acceleration plan with two tracks:
1. Runtime alignment controls (GPU/mode/concurrency visibility)
2. Chapter execution and cleanup stabilization (bounded mode selection + cleanup throttling)

Primary outcome:
- Mock benchmark meets target in the standard scenario (`>=30%` improvement).
- Real one-page benchmark improved by `27.57%` (`batch_pipeline` vs `single_page`) in this environment.

## Implemented Changes

### 1) New runtime knobs and server config plumbing
Updated to support env + runtime config for:
- `MANGA_V1_CLEANUP_INTERVAL_REQUESTS` (default `8`)
- `MANGA_V1_CHAPTER_EXECUTION_MODE` (`single_page|batch_pipeline|auto`, default `auto`)
- `MANGA_V1_RUNTIME_PROFILE` (`off|basic`, default `basic`)

Files:
- `manga_translator/server/core/task_manager.py`
- `manga_translator/server/core/config_manager.py`
- `manga_translator/server/routes/admin.py`
- `manga_translator/server/main.py`
- `manga_translator/args.py`

### 2) Chapter execution mode routing + runtime event snapshot
`/api/v1/translate/chapter` now:
- resolves execution mode (`single_page|batch_pipeline|auto`)
- emits `chapter_start.runtime` payload:
  - `runtime.use_gpu`
  - `runtime.execution_mode`
  - `runtime.page_concurrency`
  - `runtime.translator`

File:
- `manga_translator/server/routes/v1_translate.py`

### 3) Batch pipeline path for chapter job
Added Web-side chapter `batch_pipeline` branch:
- one batch entry for chapter pages
- page-level progress semantics preserved (`progress` + `chapter_complete`)
- per-page validation keeps existing failure classification (`fallback/no_regions/no_change`)

File:
- `manga_translator/server/routes/v1_translate.py`

### 4) Cleanup throttling + in-flight guard
`cleanup_after_request()` changed from per-request hard cleanup to throttled cleanup:
- triggers by request interval (default every 8 requests)
- defers cleanup when translations are still in-flight
- keeps low-memory fast-path check

Files:
- `manga_translator/server/core/task_manager.py`
- `manga_translator/server/request_extraction.py`

### 5) Example config sync
Added top-level `chapter_page_concurrency: 3` in example config.

File:
- `examples/config-example.json`

## Tests Added/Updated
- `tests/test_v1_translate_perf_quick.py`
  - cleanup throttling + in-flight deferral
  - execution mode route selection (`single_page`, `batch_pipeline`, `auto`)
  - existing perf smoke + config compatibility checks retained
- `tests/test_v1_routes.py`
  - chapter start runtime payload compatibility assertions

## Verification Results

### Automated tests
```bash
pytest -q tests/test_v1_translate_perf_quick.py
# 9 passed, 1 skipped

pytest -q tests/test_v1_routes.py -k "translate"
# 11 passed

pytest -q tests/test_v1_translate_perf_quick.py tests/test_v1_routes.py -k "translate or cleanup"
# 20 passed, 1 skipped
```

### Mock performance (quick)
Measured using 3 synthetic images (1280x720):

| Scenario | chapter_total_ms | Gain vs serial |
|---|---:|---:|
| Serial (30/30/30ms) | 95.25 | - |
| Parallel candidate (concurrency=3) | 63.89 | **32.93%** |
| Tail serial (30/30/80ms) | 144.96 | - |
| Tail parallel (concurrency=3) | 113.83 | 21.48% |

Interpretation:
- Standard workload reaches target (`>=30%`).
- Tail-heavy workload improves but below 30%, consistent with long-tail dominance.

### Real-image quick check (1 page)
Dataset: `.../chapter-1/001.jpg`, translator `gemini_hq`.

| Mode | chapter_total_ms | status |
|---|---:|---|
| single_page | 80506.85 | success |
| batch_pipeline | 58313.14 | success |

Observed gain: **27.57%**.

## Remaining Risks
1. Qt/local parity benchmark remains blocked by environment dependencies (`PyQt6` missing for local mode in this shell).
2. `gemini_hq` still exhibits high variance; one-page improvement does not guarantee chapter-level `P95` stability.
3. Full 10-page aligned benchmark has not been completed in this run due runtime cost.

## Next Focus
1. Restore Qt/local benchmark environment, then run aligned 10-page A/B (`P50/P95`).
2. Add a dedicated regression test for `chapter_start.runtime.execution_mode` under `auto + gemini_hq`.
3. Add runtime profile aggregation to persist per-chapter stage timings in a report file.
