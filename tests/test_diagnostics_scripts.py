from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
DIAG_DIR = REPO_ROOT / "scripts" / "diagnostics"


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_diagnostics_directory_contains_expected_scripts():
    expected = {
        "README.md",
        "cloudrun_benchmark.py",
        "split_pipeline_integration.py",
        "qt_cli_path_timed.py",
        "vue_api_path.py",
        "vue_api_path_timed.py",
        "deep_diagnosis.py",
    }
    actual = {p.name for p in DIAG_DIR.glob("*") if p.is_file()}
    assert expected.issubset(actual)


def test_root_wrappers_have_pytest_guard_and_forwarding():
    wrappers = {
        "test_cloudrun_benchmark.py": "cloudrun_benchmark.py",
        "test_split_pipeline_integration.py": "split_pipeline_integration.py",
        "test_qt_cli_path_timed.py": "qt_cli_path_timed.py",
        "test_vue_api_path.py": "vue_api_path.py",
        "test_vue_api_path_timed.py": "vue_api_path_timed.py",
        "test_deep_diagnosis.py": "deep_diagnosis.py",
    }
    for wrapper_name, target_name in wrappers.items():
        content = _read(REPO_ROOT / wrapper_name)
        assert "__test__ = False" in content
        assert "diagnostics" in content
        assert target_name in content


def test_qt_cli_timed_hook_manager_is_idempotent_and_restorable():
    content = _read(DIAG_DIR / "qt_cli_path_timed.py")
    assert "class HookManager" in content
    assert "def install(self)" in content
    assert "if self.installed:" in content
    assert "def restore(self)" in content
    assert "hooks.restore()" in content


def test_qt_cli_timed_defaults_are_portable():
    content = _read(DIAG_DIR / "qt_cli_path_timed.py")
    assert "/Users/xa/Desktop/projiect/manga-translator-ui_副本" not in content
    assert "/Applications/Anaconda" not in content
    assert "MANGA_TEST_IMAGE" in content
    assert "MANGA_TEST_OUTPUT" in content
