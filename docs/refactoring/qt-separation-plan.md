# Qt Separation Plan (Execution Complete)

## Scope

- Remove `desktop_qt_ui` from runtime and packaging path.
- Keep Web/Vue as the only active frontend route.
- Retire `chapter_splitter` packaging artifacts.

## Completed Work

1. Migrated text export/import shared functions to `manga_translator/utils/text_export.py`.
2. Rewired runtime callers:
   - `manga_translator/manga_translator.py`
   - `manga_translator/server/routes/translation.py`
3. Moved locales to `manga_translator/server/locales` and updated:
   - `manga_translator/server/main.py`
   - `manga_translator/server/routes/locales.py`
   - `manga_translator/server/core/config_manager.py`
4. Removed local/subprocess dependency on Qt services by adding:
   - `manga_translator/utils/local_runtime_services.py`
5. Retired Qt/chapter splitter packaging and startup path:
   - deleted `packaging/manga-chapter-splitter.spec`
   - deleted `packaging/create-manga-pdfs.spec`
   - updated `packaging/manga-translator-cpu.spec`
   - updated `packaging/manga-translator-gpu.spec`
   - updated `packaging/launch.py` (`--ui` now `web` only)
6. Removed `PyQt6` from requirements files (`cpu/gpu/metal/amd`).
7. Updated startup scripts to Web route and retired Qt startup scripts.
8. Removed `desktop_qt_ui/` from the repository working tree.

## Compatibility

- `/api/v1/*` and `/admin/*` contracts unchanged.
- Web translation, export/import, locales routes remain available.

## Validation

- `python -m py_compile` passed for changed runtime modules.
- `pytest -q tests/test_v1_routes.py tests/test_runtime_deps_check.py` passed.
- `pytest -q` currently has 2 pre-existing failures tied to `examples/config-example.json` baseline assertions (tracked in worklog).
