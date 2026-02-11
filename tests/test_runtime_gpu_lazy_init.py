from __future__ import annotations

from types import SimpleNamespace

import pytest

import manga_translator
from manga_translator.server.core import task_manager


@pytest.fixture(autouse=True)
def _reset_translator_state():
    task_manager.reset_global_translator()
    original_use_gpu = task_manager.server_config.get("use_gpu")
    original_initialized = task_manager.server_config.get("_runtime_config_initialized")
    original_source = task_manager.server_config.get("_runtime_config_source")
    try:
        yield
    finally:
        task_manager.reset_global_translator()
        task_manager.server_config["use_gpu"] = original_use_gpu
        task_manager.server_config["_runtime_config_initialized"] = original_initialized
        task_manager.server_config["_runtime_config_source"] = original_source


def test_get_global_translator_lazy_init_sets_runtime_metadata(monkeypatch: pytest.MonkeyPatch):
    task_manager.server_config["use_gpu"] = False
    task_manager.server_config["_runtime_config_initialized"] = False
    task_manager.server_config["_runtime_config_source"] = "unknown"

    monkeypatch.setattr(task_manager, "_resolve_runtime_use_gpu", lambda explicit=None: True)

    captured: dict[str, object] = {}

    class _DummyTranslator:
        def __init__(self, params):
            captured["params"] = dict(params)
            self.device = "mps" if params.get("use_gpu") else "cpu"

    monkeypatch.setattr(manga_translator, "MangaTranslator", _DummyTranslator)

    translator = task_manager.get_global_translator()

    assert translator.device == "mps"
    assert task_manager.server_config["_runtime_config_initialized"] is True
    assert task_manager.server_config["_runtime_config_source"] == "lazy_translator_init"
    assert captured["params"]["use_gpu"] is True


def test_resolve_runtime_use_gpu_prefers_env_over_default_config(monkeypatch: pytest.MonkeyPatch):
    class _Cli:
        use_gpu = True

    class _Cfg:
        cli = _Cli()

    monkeypatch.setenv("MT_USE_GPU", "false")
    monkeypatch.setattr(
        "manga_translator.server.core.config_manager.load_default_config",
        lambda: _Cfg(),
    )

    assert task_manager._resolve_runtime_use_gpu(None) is False

