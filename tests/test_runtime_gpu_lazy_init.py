from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

import manga_translator
from manga_translator.server.core import task_manager
from manga_translator.server.core import config_manager
from manga_translator.utils import BASE_PATH


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


def test_load_default_config_dict_falls_back_to_config_example(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    fallback = tmp_path / "config-example.json"
    fallback.write_text(
        (Path(BASE_PATH) / "examples" / "config-example.json").read_text(encoding="utf-8"),
        encoding="utf-8",
    )

    monkeypatch.setattr(config_manager, "SERVER_CONFIG_PATH", str(tmp_path / "missing-config.json"))
    monkeypatch.setattr(config_manager, "SERVER_CONFIG_FALLBACK_PATH", str(fallback))
    monkeypatch.delenv("MANGA_SERVER_CONFIG_PATH", raising=False)

    config_dict = config_manager.load_default_config_dict()

    assert config_dict["translator"]["translator"] == "gemini_hq"
    assert bool(config_dict["cli"]["use_gpu"]) is True


def test_load_default_config_dict_prefers_env_override(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    env_config = tmp_path / "env-config.json"
    env_config.write_text(
        '{"translator":{"translator":"openai_hq"},"cli":{"use_gpu":false}}',
        encoding="utf-8",
    )

    fallback = tmp_path / "config-example.json"
    fallback.write_text(
        (Path(BASE_PATH) / "examples" / "config-example.json").read_text(encoding="utf-8"),
        encoding="utf-8",
    )

    monkeypatch.setenv("MANGA_SERVER_CONFIG_PATH", str(env_config))
    monkeypatch.setattr(config_manager, "SERVER_CONFIG_PATH", str(tmp_path / "missing-config.json"))
    monkeypatch.setattr(config_manager, "SERVER_CONFIG_FALLBACK_PATH", str(fallback))

    config_dict = config_manager.load_default_config_dict()

    assert config_dict["translator"]["translator"] == "openai_hq"
    assert bool(config_dict["cli"]["use_gpu"]) is False
