"""Compute-only Cloud Run entrypoint.

This app intentionally exposes only the internal translation endpoint
to avoid loading unrelated web/admin/scraper routes in compute service.
"""

from __future__ import annotations

import asyncio
import ctypes.util
import logging
import os
import subprocess
import threading
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import JSONResponse

from manga_translator.server.core import config_manager, task_manager
from manga_translator.server.routes import internal_translate_router


logger = logging.getLogger("manga_translator.server.cloudrun_compute")
os.environ.setdefault("MANGA_TRANSLATOR_WEB_SERVER", "true")
GEMINI_PRIMARY_MODEL_DEFAULT = "gemini-3-flash-preview"
GEMINI_FALLBACK_MODEL_DEFAULT = "gemini-2.5-flash"
DEPRECATED_GEMINI_MODELS = {"gemini-2.0-flash"}

# Ensure admin/runtime config file exists for config-dependent utilities.
config_manager.init_server_config_file()

app = FastAPI(title="Manga Translator Compute Service")
app.include_router(internal_translate_router)

# ---------- 启动状态追踪 ----------
_startup_ready = False
_startup_error: str | None = None


def _normalize_gemini_model(model_name: str | None, *, role: str) -> str:
    fallback = GEMINI_FALLBACK_MODEL_DEFAULT if role == "fallback" else GEMINI_PRIMARY_MODEL_DEFAULT
    normalized = str(model_name or "").strip() or fallback
    if normalized.lower() in DEPRECATED_GEMINI_MODELS:
        logger.warning(
            "Deprecated Gemini model '%s' requested for %s; normalized to '%s'",
            normalized,
            role,
            GEMINI_FALLBACK_MODEL_DEFAULT,
        )
        return GEMINI_FALLBACK_MODEL_DEFAULT
    return normalized


def _resolve_runtime_gemini_models() -> tuple[str, str]:
    primary = _normalize_gemini_model(os.getenv("GEMINI_MODEL"), role="primary")
    fallback = _normalize_gemini_model(os.getenv("GEMINI_FALLBACK_MODEL"), role="fallback")
    os.environ["GEMINI_MODEL"] = primary
    os.environ["GEMINI_FALLBACK_MODEL"] = fallback
    return primary, fallback


def _is_enabled(value: str | None, default: bool = False) -> bool:
    if value is None:
        return default
    return str(value).strip().lower() in {"1", "true", "yes", "on"}


def _detect_onnxruntime_providers() -> list[str]:
    try:
        import onnxruntime as ort

        providers = ort.get_available_providers()
    except Exception as exc:  # noqa: BLE001
        raise RuntimeError(f"failed to query onnxruntime providers: {exc}") from exc
    return [str(provider) for provider in providers]


def _probe_onnxruntime_cuda_provider_library() -> dict[str, str]:
    try:
        import onnxruntime as ort
    except Exception as exc:  # noqa: BLE001
        return {"status": "error", "message": f"import onnxruntime failed: {exc}"}

    lib_path = Path(ort.__file__).resolve().parent / "capi" / "libonnxruntime_providers_cuda.so"
    if not lib_path.exists():
        return {"status": "error", "message": f"provider library missing: {lib_path}"}

    check = subprocess.run(
        ["ldd", "-r", str(lib_path)],
        capture_output=True,
        text=True,
        check=False,
    )
    check_output = (check.stdout or "") + "\n" + (check.stderr or "")
    if check.returncode != 0:
        return {
            "status": "error",
            "message": f"ldd -r failed with code {check.returncode}",
            "library_path": str(lib_path),
            "details": check_output.strip()[-2000:],
        }
    unresolved_lines = []
    for line in check_output.splitlines():
        line_lower = line.lower()
        if "not found" in line_lower:
            unresolved_lines.append(line.strip())
            continue
        if "undefined symbol" in line_lower and "provider_gethost" not in line_lower:
            unresolved_lines.append(line.strip())
    if unresolved_lines:
        return {
            "status": "error",
            "message": "ldd -r detected unresolved CUDA provider dependencies",
            "library_path": str(lib_path),
            "details": "\n".join(unresolved_lines)[-2000:],
        }

    return {"status": "ok", "library_path": str(lib_path)}


def _gpu_runtime_diagnostics() -> dict[str, object]:
    libcudnn_adv = ctypes.util.find_library("cudnn_adv")
    libcudnn = ctypes.util.find_library("cudnn")
    cuda_provider_probe = _probe_onnxruntime_cuda_provider_library()
    return {
        "providers": _detect_onnxruntime_providers(),
        "cuda_provider_probe": cuda_provider_probe,
        "libraries": {
            "cudnn_adv": libcudnn_adv,
            "cudnn": libcudnn,
        },
    }


def _background_init() -> None:
    """在后台线程中完成模型加载和 GPU 诊断，不阻塞 FastAPI 启动。"""
    global _startup_ready, _startup_error
    try:
        resolved_use_gpu = task_manager._ensure_runtime_for_translator(
            None,
            source="cloudrun_compute_startup",
            force=False,
        )
        task_manager.init_semaphore()
        compute_only = _is_enabled(os.getenv("MANGA_CLOUDRUN_COMPUTE_ONLY"), default=False)
        require_gpu = _is_enabled(os.getenv("MANGA_REQUIRE_GPU"), default=False)
        gemini_model, gemini_fallback_model = _resolve_runtime_gemini_models()
        has_gemini_key = bool(str(os.getenv("GEMINI_API_KEY", "")).strip())
        diagnostics = {
            "providers": [],
            "cuda_provider_probe": {"status": "unknown"},
            "libraries": {"cudnn_adv": None, "cudnn": None},
        }
        if resolved_use_gpu:
            diagnostics = _gpu_runtime_diagnostics()
            providers = diagnostics.get("providers") or []
            cuda_probe = diagnostics.get("cuda_provider_probe") or {}
            cuda_probe_ok = cuda_probe.get("status") == "ok"
            if require_gpu and ("CUDAExecutionProvider" not in providers or not cuda_probe_ok):
                logger.error(
                    "CloudRun compute GPU validation failed: use_gpu=%s require_gpu=%s providers=%s cuda_probe=%s libraries=%s",
                    resolved_use_gpu,
                    require_gpu,
                    providers,
                    cuda_probe,
                    diagnostics.get("libraries"),
                )
                _startup_error = (
                    "CUDAExecutionProvider unavailable while MT_USE_GPU=true and MANGA_REQUIRE_GPU=1; "
                    f"provider_probe={cuda_probe}"
                )
                return

        logger.info(
            "CloudRun compute startup ready: use_gpu=%s source=%s compute_only=%s require_gpu=%s primary_model=%s fallback_model=%s has_gemini_key=%s providers=%s cuda_probe=%s libraries=%s",
            resolved_use_gpu,
            task_manager.server_config.get("_runtime_config_source", "unknown"),
            compute_only,
            require_gpu,
            gemini_model,
            gemini_fallback_model,
            has_gemini_key,
            diagnostics.get("providers"),
            diagnostics.get("cuda_provider_probe"),
            diagnostics.get("libraries"),
        )
        _startup_ready = True
    except Exception as exc:  # noqa: BLE001
        logger.exception("Background init failed")
        _startup_error = str(exc)


@app.on_event("startup")
async def startup_event() -> None:
    """FastAPI 启动后立刻返回（健康检查可响应），模型加载放到后台线程。"""
    thread = threading.Thread(target=_background_init, daemon=True, name="compute-init")
    thread.start()
    logger.info("Background init thread started, health check available immediately")


@app.get("/", include_in_schema=False)
async def root_health() -> JSONResponse:
    """健康检查：模型加载中返回 200 warming_up，加载完返回 200 ok，失败返回 503。"""
    if _startup_error:
        return JSONResponse({"status": "error", "detail": _startup_error}, status_code=503)
    if not _startup_ready:
        return JSONResponse({"status": "warming_up"}, status_code=200)
    return JSONResponse({"status": "ok"}, status_code=200)
