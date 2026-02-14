from __future__ import annotations

import asyncio
import os
from types import SimpleNamespace

import pytest

import manga_translator.server.main as server_main
import manga_translator.server.routes.v1_translate as v1_translate
from manga_translator.server.core import task_manager


@pytest.fixture
def anyio_backend():
    return "asyncio"


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
    assert task_manager.server_config["_runtime_config_initialized"] is True
    assert task_manager.server_config["_runtime_config_source"] == "run_server"


def test_run_server_explicit_flag_overrides_env_and_config(monkeypatch: pytest.MonkeyPatch):
    class _CliConfig:
        use_gpu = True

    class _Config:
        cli = _CliConfig()

    args = SimpleNamespace(
        host="127.0.0.1",
        port=8124,
        use_gpu=False,
        verbose=False,
        models_ttl=0,
        retry_attempts=None,
        start_instance=False,
        nonce=None,
    )

    server_main.nonce = "test-nonce"
    monkeypatch.setenv("MT_USE_GPU", "true")
    monkeypatch.setattr(server_main.config_manager, "load_default_config", lambda: _Config())
    monkeypatch.setattr(server_main.config_manager, "admin_settings", {})
    monkeypatch.setattr(server_main, "prepare", lambda _args: None)

    import uvicorn

    monkeypatch.setattr(uvicorn, "run", lambda *args, **kwargs: None)

    server_main.run_server(args)

    assert task_manager.server_config["use_gpu"] is False
    assert task_manager.server_config["_runtime_config_source"] == "run_server"


def test_runtime_gemini_model_resolution_normalizes_legacy(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.delenv("GEMINI_MODEL", raising=False)
    monkeypatch.delenv("GEMINI_FALLBACK_MODEL", raising=False)
    primary, fallback = server_main._resolve_runtime_gemini_models()
    assert primary == "gemini-3-flash-preview"
    assert fallback == "gemini-2.5-flash"
    assert os.getenv("GEMINI_MODEL") == "gemini-3-flash-preview"
    assert os.getenv("GEMINI_FALLBACK_MODEL") == "gemini-2.5-flash"

    monkeypatch.setenv("GEMINI_MODEL", "gemini-2.0-flash")
    primary_legacy, fallback_legacy = server_main._resolve_runtime_gemini_models()
    assert primary_legacy == "gemini-2.5-flash"
    assert fallback_legacy == "gemini-2.5-flash"


def test_ensure_runtime_server_config_initializes_from_default_config(
    monkeypatch: pytest.MonkeyPatch,
):
    class _CliConfig:
        use_gpu = True

    class _Config:
        cli = _CliConfig()

    monkeypatch.delenv("MT_USE_GPU", raising=False)
    monkeypatch.setattr(server_main.config_manager, "load_default_config", lambda: _Config())
    monkeypatch.setitem(task_manager.server_config, "use_gpu", False)
    monkeypatch.setitem(task_manager.server_config, "_runtime_config_initialized", False)
    monkeypatch.setitem(task_manager.server_config, "_runtime_config_source", "unknown")

    resolved = server_main._ensure_runtime_server_config()

    assert resolved is True
    assert task_manager.server_config["use_gpu"] is True
    assert task_manager.server_config["_runtime_config_initialized"] is True
    assert task_manager.server_config["_runtime_config_source"] == "startup_auto"


def test_ensure_runtime_server_config_prefers_env_over_default_config(
    monkeypatch: pytest.MonkeyPatch,
):
    class _CliConfig:
        use_gpu = True

    class _Config:
        cli = _CliConfig()

    monkeypatch.setenv("MT_USE_GPU", "false")
    monkeypatch.setattr(server_main.config_manager, "load_default_config", lambda: _Config())
    monkeypatch.setitem(task_manager.server_config, "use_gpu", True)
    monkeypatch.setitem(task_manager.server_config, "_runtime_config_initialized", False)
    monkeypatch.setitem(task_manager.server_config, "_runtime_config_source", "unknown")

    resolved = server_main._ensure_runtime_server_config()

    assert resolved is False
    assert task_manager.server_config["use_gpu"] is False
    assert task_manager.server_config["_runtime_config_initialized"] is True
    assert task_manager.server_config["_runtime_config_source"] == "startup_auto"


def test_run_server_uses_task_manager_runtime_initializer(monkeypatch: pytest.MonkeyPatch):
    args = SimpleNamespace(
        host="127.0.0.1",
        port=8125,
        use_gpu=None,
        verbose=False,
        models_ttl=0,
        retry_attempts=None,
        start_instance=False,
        nonce=None,
    )

    captured: dict[str, object] = {}

    def _fake_ensure_runtime(explicit, *, source, force):
        captured["explicit"] = explicit
        captured["source"] = source
        captured["force"] = force
        task_manager.server_config["use_gpu"] = True
        task_manager.server_config["_runtime_config_initialized"] = True
        task_manager.server_config["_runtime_config_source"] = source
        return True

    server_main.nonce = "test-nonce"
    monkeypatch.setattr(task_manager, "_ensure_runtime_for_translator", _fake_ensure_runtime)
    monkeypatch.setattr(server_main.config_manager, "admin_settings", {})
    monkeypatch.setattr(server_main, "prepare", lambda _args: None)

    import uvicorn

    monkeypatch.setattr(uvicorn, "run", lambda *args, **kwargs: None)

    server_main.run_server(args)

    assert captured == {"explicit": None, "source": "run_server", "force": True}
    assert task_manager.server_config["_runtime_config_source"] == "run_server"


@pytest.mark.anyio
async def test_cloudrun_executor_requests_are_serialized_by_global_gate(tmp_path):
    image_a = tmp_path / "001.jpg"
    image_b = tmp_path / "002.jpg"
    image_a.write_bytes(b"raw-a")
    image_b.write_bytes(b"raw-b")

    class _CloudRunExecutor(v1_translate.TranslateExecutor):
        backend = "cloudrun"

        def __init__(self):
            self.active = 0
            self.max_active = 0

        async def translate_page(self, image_path, output_path, source_language, target_language, *, context_translations=None):
            _ = (image_path, source_language, target_language, context_translations)
            self.active += 1
            self.max_active = max(self.max_active, self.active)
            await asyncio.sleep(0.02)
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_bytes(b"translated")
            self.active -= 1
            return {
                "output_path": str(output_path),
                "regions_count": 1,
                "output_changed": True,
                "stage_elapsed_ms": {},
            }

    executor = _CloudRunExecutor()
    # Ensure clean lock object for deterministic assertion.
    v1_translate._CLOUDRUN_SERIAL_GATE = None

    async def _run_one(image_path):
        output_path = tmp_path / "out" / image_path.name
        return await v1_translate._execute_page_with_retry(
            executor=executor,
            image_path=image_path,
            output_path=output_path,
            source_language="en",
            target_language="zh",
            max_retries=0,
        )

    await asyncio.gather(_run_one(image_a), _run_one(image_b))
    assert executor.max_active == 1


def test_cloudrun_execution_error_retryable_semantics():
    retryable_err = v1_translate.CloudRunExecutionError(
        status_code=429,
        message="cloudrun status=429",
        retryable=True,
    )
    fatal_err = v1_translate.CloudRunExecutionError(
        status_code=503,
        message="cloudrun fallback used",
        retryable=False,
    )

    assert v1_translate._is_retryable_executor_error(retryable_err) is True
    assert v1_translate._is_retryable_executor_error(fatal_err) is False
