from __future__ import annotations

from types import SimpleNamespace

import pytest

import manga_translator.server.main as server_main
import manga_translator.server.routes.v1_translate as v1_translate
from manga_translator.server.core import task_manager


def test_single_page_mode_forces_page_concurrency_one(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(
        "manga_translator.server.core.task_manager.get_server_config",
        lambda: {"chapter_page_concurrency": 4, "max_concurrent_tasks": 4},
    )

    assert v1_translate._resolve_chapter_page_concurrency("single_page", "gemini_hq") == 1
    assert v1_translate._resolve_chapter_page_concurrency("single_page", "openai_hq") == 1
    assert v1_translate._resolve_chapter_page_concurrency("single_page", "sakura") == 1


def test_run_server_defaults_to_config_gpu_when_cli_flag_unspecified(monkeypatch: pytest.MonkeyPatch):
    class _CliConfig:
        use_gpu = True

    class _Config:
        cli = _CliConfig()

    args = SimpleNamespace(
        host="127.0.0.1",
        port=8123,
        use_gpu=None,
        verbose=False,
        models_ttl=0,
        retry_attempts=None,
        start_instance=False,
        nonce=None,
    )

    server_main.nonce = "test-nonce"
    monkeypatch.setattr(server_main.config_manager, "load_default_config", lambda: _Config())
    monkeypatch.setattr(server_main.config_manager, "admin_settings", {})

    def _fake_prepare(_args):
        server_main.nonce = "test-nonce"
        return None

    monkeypatch.setattr(server_main, "prepare", _fake_prepare)

    # Patch uvicorn.run to avoid opening a real server in test.
    import uvicorn

    monkeypatch.setattr(uvicorn, "run", lambda *args, **kwargs: None)

    server_main.run_server(args)

    assert task_manager.server_config["use_gpu"] is True

