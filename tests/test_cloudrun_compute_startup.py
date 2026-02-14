from __future__ import annotations

import pytest

from manga_translator.server import cloudrun_compute_main


@pytest.fixture
def anyio_backend():
    return "asyncio"


def test_cloudrun_runtime_gemini_models_normalize_legacy(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("GEMINI_MODEL", "gemini-2.0-flash")
    monkeypatch.delenv("GEMINI_FALLBACK_MODEL", raising=False)
    primary, fallback = cloudrun_compute_main._resolve_runtime_gemini_models()
    assert primary == "gemini-2.5-flash"
    assert fallback == "gemini-2.5-flash"


@pytest.mark.anyio
async def test_startup_event_requires_cuda_provider_when_gpu_required(
    monkeypatch: pytest.MonkeyPatch,
):
    monkeypatch.setenv("MT_USE_GPU", "true")
    monkeypatch.setenv("MANGA_REQUIRE_GPU", "1")

    monkeypatch.setattr(
        cloudrun_compute_main.task_manager,
        "_ensure_runtime_for_translator",
        lambda *args, **kwargs: True,
    )
    monkeypatch.setattr(cloudrun_compute_main.task_manager, "init_semaphore", lambda: None)
    monkeypatch.setattr(
        cloudrun_compute_main,
        "_detect_onnxruntime_providers",
        lambda: ["CPUExecutionProvider"],
        raising=False,
    )
    monkeypatch.setattr(
        cloudrun_compute_main,
        "_probe_onnxruntime_cuda_provider_library",
        lambda: {"status": "error", "message": "probe-failed"},
        raising=False,
    )

    monkeypatch.setattr(cloudrun_compute_main, "_startup_ready", False, raising=False)
    monkeypatch.setattr(cloudrun_compute_main, "_startup_error", None, raising=False)
    cloudrun_compute_main._background_init()
    assert cloudrun_compute_main._startup_ready is False
    assert cloudrun_compute_main._startup_error is not None
    assert "CUDAExecutionProvider" in cloudrun_compute_main._startup_error


@pytest.mark.anyio
async def test_startup_event_allows_cuda_provider_when_gpu_required(
    monkeypatch: pytest.MonkeyPatch,
):
    monkeypatch.setenv("MT_USE_GPU", "true")
    monkeypatch.setenv("MANGA_REQUIRE_GPU", "1")

    monkeypatch.setattr(
        cloudrun_compute_main.task_manager,
        "_ensure_runtime_for_translator",
        lambda *args, **kwargs: True,
    )
    monkeypatch.setattr(cloudrun_compute_main.task_manager, "init_semaphore", lambda: None)
    monkeypatch.setattr(
        cloudrun_compute_main,
        "_detect_onnxruntime_providers",
        lambda: ["CUDAExecutionProvider", "CPUExecutionProvider"],
        raising=False,
    )
    monkeypatch.setattr(
        cloudrun_compute_main,
        "_probe_onnxruntime_cuda_provider_library",
        lambda: {"status": "ok", "library_path": "/tmp/libonnxruntime_providers_cuda.so"},
        raising=False,
    )

    monkeypatch.setattr(cloudrun_compute_main, "_startup_ready", False, raising=False)
    monkeypatch.setattr(cloudrun_compute_main, "_startup_error", None, raising=False)
    cloudrun_compute_main._background_init()
    assert cloudrun_compute_main._startup_error is None
    assert cloudrun_compute_main._startup_ready is True
