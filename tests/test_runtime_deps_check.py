from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = REPO_ROOT / "scripts" / "check_runtime_deps.py"


def _run_check(required_modules: str) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env["CHECK_RUNTIME_DEPS_REQUIRED"] = required_modules
    return subprocess.run(
        [sys.executable, str(SCRIPT_PATH)],
        cwd=str(REPO_ROOT),
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )


def test_runtime_deps_check_returns_zero_when_all_required_modules_are_available():
    result = _run_check("json,sys")
    assert result.returncode == 0, result.stdout + result.stderr
    output = result.stdout + result.stderr
    assert "OK json" in output
    assert "OK sys" in output


def test_runtime_deps_check_returns_one_when_dependency_is_missing():
    result = _run_check("json,definitely_missing_runtime_dep_12345")
    assert result.returncode == 1, result.stdout + result.stderr
    output = result.stdout + result.stderr
    assert "FAIL definitely_missing_runtime_dep_12345" in output
    assert "pip install" in output
