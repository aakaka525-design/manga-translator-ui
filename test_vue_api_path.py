#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Compatibility wrapper for scripts/diagnostics/vue_api_path.py."""

from pathlib import Path
import runpy

__test__ = False


def main() -> int:
    target = (
        Path(__file__).resolve().parent
        / "scripts"
        / "diagnostics"
        / "vue_api_path.py"
    )
    runpy.run_path(str(target), run_name="__main__")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
