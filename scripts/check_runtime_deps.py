#!/usr/bin/env python3
from __future__ import annotations

import importlib
import os
import sys

DEFAULT_REQUIRED = ["py3langid", "fastapi", "uvicorn"]


def parse_required() -> list[str]:
    raw = os.getenv("CHECK_RUNTIME_DEPS_REQUIRED", "")
    if raw.strip():
        return [item.strip() for item in raw.split(",") if item.strip()]
    return DEFAULT_REQUIRED


def main() -> int:
    required = parse_required()
    missing: list[str] = []

    print(f"[check_runtime_deps] Python {sys.version.split()[0]}")
    for module_name in required:
        try:
            importlib.import_module(module_name)
            print(f"OK {module_name}")
        except Exception as exc:  # pragma: no cover - broad by design for startup check
            missing.append(module_name)
            print(f"FAIL {module_name}: {exc}")
            print(f"  -> pip install {module_name}")

    if missing:
        print(f"[check_runtime_deps] Missing {len(missing)} module(s)")
        return 1

    print("[check_runtime_deps] All runtime dependencies are available")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
