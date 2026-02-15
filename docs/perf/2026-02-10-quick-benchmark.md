# Quick Benchmark (5-minute budget)

Date: 2026-02-10

Scope:

- Fast mock benchmark only (3 synthetic pages, 1280x720).
- One-page real smoke test is kept in test suite and may skip if runtime deps are unavailable.

## Commands

```bash
pytest -q tests/test_v1_translate_perf_quick.py
pytest -q tests/test_v1_routes.py -k "translate"
```

## Config notes

- Priority: `MANGA_V1_CHAPTER_PAGE_CONCURRENCY` > server config `chapter_page_concurrency` > default `3`.
- Final effective value is clamped by `max_concurrent_tasks`.

## Mock benchmark snapshot

- `serial_3x30_ms`: `94.95 ms`
- `parallel_3x30_ms`: `32.65 ms`
- `improvement_pct`: `65.6%`
- `serial_tail_ms` (30/30/80): `145.26 ms`
- `parallel_tail_ms` (30/30/80): `82.09 ms`
- `tail_improvement_pct`: `43.5%`

Conclusion:

- Bounded page-level concurrency (`chapter_page_concurrency=3`) beats serial baseline by more than the 30% acceptance threshold under quick mock scenarios.
- `_image_has_visible_changes` is not prioritized in this round unless its share exceeds 10% in future profiling.
