from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parents[1]


def _read(rel_path: str, *, optional: bool = False) -> str:
    path = REPO_ROOT / rel_path
    if not path.exists():
        if optional:
            pytest.skip(f"optional file missing: {rel_path}")
        raise FileNotFoundError(rel_path)
    return path.read_text(encoding="utf-8")


def test_no_hardcoded_internal_token_in_diagnostic_scripts():
    benchmark_script = _read("test_cloudrun_benchmark.py", optional=True)
    split_script = _read("test_split_pipeline_integration.py", optional=True)
    assert 'INTERNAL_TOKEN = "' not in benchmark_script
    assert 'INTERNAL_TOKEN = "' not in split_script


def test_split_integration_script_not_collected_as_pytest_test_module():
    split_script = _read("test_split_pipeline_integration.py", optional=True)
    assert "__test__ = False" in split_script


def test_diagnostic_scripts_do_not_use_machine_bound_data_dir():
    benchmark_script = _read("test_cloudrun_benchmark.py", optional=True)
    split_script = _read("test_split_pipeline_integration.py", optional=True)
    machine_bound_prefix = "/Users/xa/Desktop/projiect/manga-translator-ui_副本"
    assert machine_bound_prefix not in benchmark_script
    assert machine_bound_prefix not in split_script


def test_deploy_compute_uses_secret_manager_for_gemini_api_key():
    deploy_script = _read("deploy/cloudrun/deploy-compute.sh")
    assert "--set-secrets" in deploy_script
    assert "GEMINI_API_KEY=${GEMINI_API_KEY}" not in deploy_script


def test_deployment_registry_doc_matches_secret_injection_strategy():
    registry_doc = _read("docs/deployment/2026-02-14-deployment-registry.md")
    assert "缺少 `GEMINI_API_KEY` 注入" not in registry_doc
    assert "Secret Manager" in registry_doc


def test_readme_does_not_include_machine_bound_paths():
    readme = _read("README.md")
    assert "/Users/" not in readme
    assert "C:\\Users\\" not in readme
