"""Compatibility v1 translation routes and SSE events."""

from __future__ import annotations

import asyncio
import hashlib
import io
import json
import logging
import os
import tempfile
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Optional
from urllib.parse import quote, unquote

import httpx
from fastapi import APIRouter, Depends, File, Form, Header, HTTPException, UploadFile
from fastapi.responses import Response, StreamingResponse
from PIL import Image, ImageChops
from pydantic import BaseModel, Field
from starlette.requests import Request

from manga_translator.server.core.library_service import LibraryService, IMAGE_EXTENSIONS
from manga_translator.server.core.middleware import require_auth
from manga_translator.server.core.models import Session
from manga_translator.server.core.ctx_cache import CtxCache
from manga_translator.server.core.v1_event_bus import v1_event_bus


router = APIRouter(prefix="/api/v1/translate", tags=["v1-translate"])
internal_router = APIRouter(prefix="/internal/translate", tags=["internal-translate"])
library_service = LibraryService()
logger = logging.getLogger(__name__)
_CLOUDRUN_SERIAL_GATE: asyncio.Lock | None = None
_SPLIT_TRANSLATE_GATE: asyncio.Semaphore | None = None


def _env_positive_int(name: str, default: int) -> int:
    raw = os.getenv(name)
    if raw is None:
        return default
    try:
        parsed = int(raw)
    except (TypeError, ValueError):
        return default
    return parsed if parsed > 0 else default


def _env_non_negative_int(name: str, default: int) -> int:
    raw = os.getenv(name)
    if raw is None:
        return default
    try:
        parsed = int(raw)
    except (TypeError, ValueError):
        return default
    return parsed if parsed >= 0 else default


def _env_float_series(name: str, default: tuple[float, ...]) -> tuple[float, ...]:
    raw = os.getenv(name)
    if raw is None:
        return default
    values: list[float] = []
    for chunk in str(raw).split(","):
        item = chunk.strip()
        if not item:
            continue
        try:
            parsed = float(item)
        except (TypeError, ValueError):
            continue
        if parsed > 0:
            values.append(parsed)
    if not values:
        return default
    return tuple(values)


_SPLIT_CTX_CACHE = CtxCache(
    max_size=_env_positive_int("MANGA_SPLIT_CTX_CACHE_MAX_SIZE", 24),
    default_ttl=_env_positive_int("MANGA_SPLIT_CTX_CACHE_TTL_SEC", 300),
)


# CLI-compatible default: no hard timeout unless explicitly configured.
TRANSLATE_CONTEXT_TIMEOUT_SEC = _env_non_negative_int("MANGA_TRANSLATE_CONTEXT_TIMEOUT_SEC", 0)
CHAPTER_PAGE_CONCURRENCY_DEFAULT = 3
CHAPTER_EXECUTION_MODE_CHOICES = {"single_page", "batch_pipeline", "auto"}
RUNTIME_PROFILE_CHOICES = {"off", "basic"}
TRANSLATE_EXECUTION_BACKEND_CHOICES = {"local", "cloudrun"}
TRANSLATE_PIPELINE_MODE_CHOICES = {"unified", "split"}
CONTEXT_TRANSLATION_LIMIT = 3
CLOUDRUN_EXECUTOR_TIMEOUT_SEC = _env_positive_int("MANGA_CLOUDRUN_TIMEOUT_SEC", 120)
CLOUDRUN_EXECUTOR_RETRIES = _env_non_negative_int("MANGA_CLOUDRUN_EXECUTOR_RETRIES", 2)
CLOUDRUN_EXECUTOR_RETRY_BACKOFFS = _env_float_series(
    "MANGA_CLOUDRUN_EXECUTOR_RETRY_BACKOFFS",
    (8.0, 16.0, 32.0),
)
CLOUDRUN_RETRYABLE_STATUS = {408, 429, 500, 502, 503, 504}
INTERNAL_TOKEN_HEADER = "X-Internal-Token"
GEMINI_PRIMARY_MODEL_DEFAULT = "gemini-3-flash-preview"
GEMINI_FALLBACK_MODEL_DEFAULT = "gemini-2.5-flash"
DEPRECATED_GEMINI_MODELS = {"gemini-2.0-flash"}

LANG_CODE_ALIASES = {
    "ar": "ARA",
    "cs": "CSY",
    "de": "DEU",
    "en": "ENG",
    "es": "ESP",
    "fil": "FIL",
    "fr": "FRA",
    "hr": "HRV",
    "hu": "HUN",
    "id": "IND",
    "it": "ITA",
    "ja": "JPN",
    "ko": "KOR",
    "nl": "NLD",
    "pl": "POL",
    "pt": "PTB",
    "ro": "ROM",
    "ru": "RUS",
    "sr": "SRP",
    "th": "THA",
    "tr": "TRK",
    "uk": "UKR",
    "vi": "VIN",
    "zh": "CHS",
    "zh-cn": "CHS",
    "zh-hans": "CHS",
    "zh-hant": "CHT",
    "zh-hk": "CHT",
    "zh-tw": "CHT",
}


class ChapterTranslateRequest(BaseModel):
    manga_id: str
    chapter_id: str
    source_language: Optional[str] = None
    target_language: Optional[str] = None


class PageTranslateRequest(BaseModel):
    manga_id: str
    chapter_id: str
    image_name: str
    source_language: Optional[str] = None
    target_language: Optional[str] = None


class InternalPageTranslateRequest(BaseModel):
    source_language: Optional[str] = None
    target_language: Optional[str] = None
    context_translations: list[str] = Field(default_factory=list)


class InternalRenderRegion(BaseModel):
    region_index: int
    translation: str = ""


class InternalRenderRequest(BaseModel):
    task_id: str
    image_hash: str
    translated_regions: list[InternalRenderRegion] = Field(default_factory=list)
    primary_model: Optional[str] = None
    fallback_model: Optional[str] = None
    selected_model: Optional[str] = None
    fallback_used: Optional[bool] = None
    fallback_reason: Optional[str] = None
    translation_text: Optional[str] = None


class CloudRunExecutionError(RuntimeError):
    def __init__(
        self,
        *,
        status_code: int | None = None,
        message: str,
        failure_stage: str = "remote",
        retryable: bool = False,
    ) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.failure_stage = failure_stage
        self.retryable = retryable


def _natural_key(value: str) -> list[object]:
    import re

    return [int(chunk) if chunk.isdigit() else chunk.lower() for chunk in re.split(r"(\d+)", value)]


def _chapter_images(manga_id: str, chapter_id: str) -> list[Path]:
    chapter_dir = (library_service.raw_dir / manga_id / chapter_id).resolve()
    if not chapter_dir.exists() or not chapter_dir.is_dir():
        raise FileNotFoundError("Chapter not found")

    images = sorted(
        [p for p in chapter_dir.iterdir() if p.is_file() and p.suffix.lower() in IMAGE_EXTENSIONS],
        key=lambda p: _natural_key(p.name),
    )
    if not images:
        raise FileNotFoundError("No images found in chapter")
    return images


def _normalize_language_code(value: str | None) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    key = text.lower().replace("_", "-")
    alias = LANG_CODE_ALIASES.get(key)
    if alias:
        return alias
    return text.upper()


def _resolve_target_language(target_language: str | None) -> str:
    normalized = _normalize_language_code(target_language)
    return normalized or "CHS"


def _resolve_translate_attempts(config) -> int:
    server_retry_attempts = None
    try:
        from manga_translator.server.core.task_manager import get_server_config

        server_retry_attempts = get_server_config().get("retry_attempts")
    except Exception:  # noqa: BLE001
        pass

    if isinstance(server_retry_attempts, int) and (server_retry_attempts > 0 or server_retry_attempts == -1):
        return server_retry_attempts

    cli_attempts = getattr(getattr(config, "cli", None), "attempts", None)
    if isinstance(cli_attempts, int) and (cli_attempts > 0 or cli_attempts == -1):
        return cli_attempts

    configured_attempts = getattr(getattr(config, "translator", None), "attempts", None)
    if isinstance(configured_attempts, int) and (configured_attempts > 0 or configured_attempts == -1):
        return configured_attempts

    # Keep a bounded default to avoid unintentional long-tail retries in API path.
    return 3


async def _await_translate_context(awaitable, timeout_seconds: int):
    if timeout_seconds > 0:
        return await asyncio.wait_for(awaitable, timeout=timeout_seconds)
    return await awaitable


def _to_non_negative_int(value: object, default: int = 0) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return default
    return parsed if parsed >= 0 else default


def _encode_header_value(value: object, limit: int = 2000) -> str:
    """Encode arbitrary text into ASCII-safe header payload."""
    text = str(value or "").replace("\r", " ").replace("\n", " ").strip()
    if len(text) > limit:
        text = text[:limit]
    return quote(text, safe="-_.~")


def _decode_header_value(value: object | None) -> str:
    if value is None:
        return ""
    try:
        return unquote(str(value))
    except Exception:  # noqa: BLE001
        return str(value)


def _normalize_execution_mode(value: object, default: str = "auto") -> str:
    normalized = str(value or "").strip().lower()
    return normalized if normalized in CHAPTER_EXECUTION_MODE_CHOICES else default


def _normalize_runtime_profile(value: object, default: str = "basic") -> str:
    normalized = str(value or "").strip().lower()
    return normalized if normalized in RUNTIME_PROFILE_CHOICES else default


def _resolve_translator_name() -> str | None:
    try:
        from manga_translator.server.core.config_manager import load_default_config

        config = load_default_config()
        translator_name = getattr(getattr(config, "translator", None), "translator", None)
        if isinstance(translator_name, str) and translator_name.strip():
            return translator_name.strip()
    except Exception:  # noqa: BLE001
        pass
    return None


def _resolve_chapter_execution_mode(total_pages: int, translator_name: str | None = None) -> str:
    configured = "auto"

    try:
        from manga_translator.server.core.task_manager import get_server_config

        configured = _normalize_execution_mode(get_server_config().get("chapter_execution_mode"), "auto")
    except Exception:  # noqa: BLE001
        pass

    env_override = os.getenv("MANGA_V1_CHAPTER_EXECUTION_MODE")
    if env_override is not None:
        configured = _normalize_execution_mode(env_override, configured)

    if configured != "auto":
        return configured

    if total_pages <= 1:
        return "single_page"
    return "batch_pipeline"


def _resolve_runtime_profile() -> str:
    configured = "basic"
    try:
        from manga_translator.server.core.task_manager import get_server_config

        configured = _normalize_runtime_profile(get_server_config().get("runtime_profile"), "basic")
    except Exception:  # noqa: BLE001
        pass

    env_override = os.getenv("MANGA_V1_RUNTIME_PROFILE")
    if env_override is not None:
        configured = _normalize_runtime_profile(env_override, configured)
    return configured


def _build_context_translations(values: list[str] | None) -> list[str]:
    if not values:
        return []
    cleaned = [str(item).strip() for item in values if item and str(item).strip()]
    if not cleaned:
        return []
    return cleaned[-CONTEXT_TRANSLATION_LIMIT:]


def _resolve_translate_execution_backend() -> str:
    configured = "local"
    try:
        from manga_translator.server.core.task_manager import get_server_config

        configured = str(get_server_config().get("translate_execution_backend", "local")).strip().lower()
    except Exception:  # noqa: BLE001
        pass

    env_override = os.getenv("MANGA_TRANSLATE_EXECUTION_BACKEND")
    if env_override is not None:
        configured = str(env_override).strip().lower()
    if configured not in TRANSLATE_EXECUTION_BACKEND_CHOICES:
        return "local"
    return configured


def _resolve_translate_pipeline_mode() -> str:
    configured = "unified"
    try:
        from manga_translator.server.core.task_manager import get_server_config

        configured = str(get_server_config().get("translate_pipeline_mode", "unified")).strip().lower()
    except Exception:  # noqa: BLE001
        pass

    env_override = os.getenv("MANGA_TRANSLATE_PIPELINE_MODE")
    if env_override is not None:
        configured = str(env_override).strip().lower()
    if configured not in TRANSLATE_PIPELINE_MODE_CHOICES:
        return "unified"
    return configured


def _split_translate_semaphore() -> asyncio.Semaphore:
    global _SPLIT_TRANSLATE_GATE
    if _SPLIT_TRANSLATE_GATE is None:
        _SPLIT_TRANSLATE_GATE = asyncio.Semaphore(1)
    return _SPLIT_TRANSLATE_GATE


def _hash_payload(payload: bytes) -> str:
    return f"sha256:{hashlib.sha256(payload).hexdigest()}"


def _extract_region_text(region: dict[str, Any]) -> str:
    text = str(region.get("text") or "").strip()
    if text:
        return text
    texts = region.get("texts")
    if isinstance(texts, list):
        cleaned = [str(item).strip() for item in texts if str(item).strip()]
        return "\n".join(cleaned).strip()
    return ""


def _is_split_cache_fallback_error(exc: CloudRunExecutionError) -> bool:
    return exc.status_code in {404, 410, 422}


def _resolve_cloudrun_executor_url() -> str:
    return str(os.getenv("MANGA_CLOUDRUN_EXEC_URL", "")).strip()


def _resolve_internal_token() -> str:
    return str(os.getenv("MANGA_INTERNAL_API_TOKEN", "")).strip()


def _is_cloudrun_compute_only() -> bool:
    return str(os.getenv("MANGA_CLOUDRUN_COMPUTE_ONLY", "")).strip().lower() in {"1", "true", "yes", "on"}


def _has_runtime_gemini_key() -> bool:
    return bool(str(os.getenv("GEMINI_API_KEY", "")).strip())


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


def _resolve_gemini_primary_model(requested_model: str | None = None) -> str:
    if requested_model is not None and str(requested_model).strip():
        return _normalize_gemini_model(requested_model, role="primary")
    configured = str(os.getenv("GEMINI_MODEL", "")).strip()
    return _normalize_gemini_model(configured, role="primary")


def _resolve_gemini_fallback_model(requested_model: str | None = None) -> str:
    if requested_model is not None and str(requested_model).strip():
        return _normalize_gemini_model(requested_model, role="fallback")
    configured = str(os.getenv("GEMINI_FALLBACK_MODEL", "")).strip()
    return _normalize_gemini_model(configured, role="fallback")


def _requires_gemini_key() -> bool:
    primary_model = _resolve_gemini_primary_model().lower()
    fallback_model = _resolve_gemini_fallback_model().lower()
    return "gemini" in primary_model or "gemini" in fallback_model


def _ensure_internal_compute_ready() -> None:
    if not _is_cloudrun_compute_only():
        return
    if _requires_gemini_key() and not _has_runtime_gemini_key():
        raise HTTPException(
            status_code=503,
            detail="compute runtime missing GEMINI_API_KEY",
        )


def _verify_internal_token(received: str | None) -> None:
    required = _resolve_internal_token()
    if not required:
        return
    if not received or received.strip() != required:
        raise HTTPException(status_code=401, detail="internal token required")


def _cloudrun_serial_lock() -> asyncio.Lock:
    global _CLOUDRUN_SERIAL_GATE
    if _CLOUDRUN_SERIAL_GATE is None:
        _CLOUDRUN_SERIAL_GATE = asyncio.Lock()
    return _CLOUDRUN_SERIAL_GATE


def _extract_context_text(ctx) -> str:
    text_regions = getattr(ctx, "text_regions", None) or []
    values: list[str] = []
    for region in text_regions:
        translated = str(getattr(region, "translation", "") or "").strip()
        if translated:
            values.append(translated)
    return "\n".join(values).strip()


def _to_non_negative_float(value: Any, default: float = 0.0) -> float:
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return float(default)
    return parsed if parsed >= 0 else float(default)


def _normalize_split_detect_elapsed(raw_elapsed: Any) -> dict[str, Any]:
    source = dict(raw_elapsed or {}) if isinstance(raw_elapsed, dict) else {}
    total_ms = _to_non_negative_float(source.get("total"), default=0.0)
    detect_ms = _to_non_negative_float(source.get("detect"), default=total_ms)
    if total_ms <= 0 and detect_ms > 0:
        total_ms = detect_ms
    if total_ms <= 0 and detect_ms <= 0:
        detect_ms = 0.0
        total_ms = 0.0

    # _translate_until_translation currently returns an aggregated detect+ocr stage.
    return {
        "detect": round(total_ms, 3),
        "ocr": None,
        "total": round(total_ms, 3),
        "mode": "aggregated_detect_ocr",
    }


def _resolve_chapter_page_concurrency(
    execution_mode: str | None = None,
    translator_name: str | None = None,
) -> int:
    configured = CHAPTER_PAGE_CONCURRENCY_DEFAULT
    max_concurrent_tasks = None

    try:
        from manga_translator.server.core.task_manager import get_server_config

        server_config = get_server_config()
        configured_value = server_config.get("chapter_page_concurrency")
        if isinstance(configured_value, int) and configured_value > 0:
            configured = configured_value

        max_tasks_value = server_config.get("max_concurrent_tasks")
        if isinstance(max_tasks_value, int) and max_tasks_value > 0:
            max_concurrent_tasks = max_tasks_value
    except Exception:  # noqa: BLE001
        pass

    # Env override is useful for quick A/B without touching persisted server config.
    if os.getenv("MANGA_V1_CHAPTER_PAGE_CONCURRENCY") is not None:
        configured = _env_positive_int("MANGA_V1_CHAPTER_PAGE_CONCURRENCY", configured)

    mode_key = (execution_mode or "").strip().lower()
    translator_key = (translator_name or "").strip().lower()

    # Single-page mode executes through one shared translator instance.
    # Force serial page execution to avoid cross-page mutable state races.
    if mode_key and mode_key != "batch_pipeline":
        configured = 1
    elif translator_key == "gemini_hq" and mode_key != "batch_pipeline":
        configured = min(configured, 1)

    if max_concurrent_tasks is None:
        return max(1, configured)
    return max(1, min(configured, max_concurrent_tasks))


def _run_split_detect_sync(
    payload: bytes,
    image_name: str,
    source_language: str | None,
    target_language: str | None,
) -> dict[str, Any]:
    from manga_translator.server.core.config_manager import load_default_config
    from manga_translator.server.core.task_manager import (
        _ensure_runtime_for_translator,
        begin_translation_operation,
        end_translation_operation,
        get_global_translator,
    )
    from manga_translator.server.request_extraction import (
        _drain_pending_tasks,
        _get_translation_event_loop,
        prepare_translator_params,
    )

    _ensure_runtime_for_translator()
    config = load_default_config()
    config.translator.attempts = _resolve_translate_attempts(config)
    if source_language:
        config.translator.skip_lang = None
    config.translator.target_lang = _resolve_target_language(target_language)
    prepare_translator_params(config, "normal")

    pil_image = Image.open(io.BytesIO(payload))
    pil_image.load()
    translator = get_global_translator()
    loop = _get_translation_event_loop()
    started_at = time.perf_counter()
    begin_translation_operation()
    try:
        ctx = loop.run_until_complete(translator._translate_until_translation(pil_image, config))
        total_ms = (time.perf_counter() - started_at) * 1000.0
        regions = list(getattr(ctx, "text_regions", []) or [])
        return {
            "ctx": ctx,
            "config": config,
            "image_name": image_name,
            "from_lang": str(getattr(ctx, "from_lang", "") or ""),
            "regions": regions,
            "elapsed_ms": _normalize_split_detect_elapsed(
                {
                    "detect": round(total_ms, 3),
                    "ocr": None,
                    "total": round(total_ms, 3),
                }
            ),
        }
    finally:
        end_translation_operation()
        _drain_pending_tasks(loop)


def _run_split_translate_sync(
    texts: list[str],
    source_language: str | None,
    target_language: str | None,
    from_lang: str | None,
    context_translations: list[str] | None,
    model_name: str,
) -> list[str]:
    from manga_translator.server.core.config_manager import load_default_config
    from manga_translator.server.core.task_manager import (
        _ensure_runtime_for_translator,
        begin_translation_operation,
        end_translation_operation,
        get_global_translator,
    )
    from manga_translator.server.request_extraction import (
        _drain_pending_tasks,
        _get_translation_event_loop,
        prepare_translator_params,
    )

    _ensure_runtime_for_translator()
    config = load_default_config()
    config.translator.attempts = _resolve_translate_attempts(config)
    if source_language:
        config.translator.skip_lang = None
    config.translator.target_lang = _resolve_target_language(target_language)
    if hasattr(config, "translator"):
        config.translator.user_api_model = model_name
    prepare_translator_params(config, "normal")

    translator = get_global_translator()
    loop = _get_translation_event_loop()
    begin_translation_operation()

    previous_page_translations = None
    previous_context_size = None
    seeded_context = _build_context_translations(context_translations or [])
    if seeded_context and hasattr(translator, "all_page_translations"):
        try:
            previous_page_translations = list(getattr(translator, "all_page_translations", []) or [])
        except Exception:  # noqa: BLE001
            previous_page_translations = []
        translator.all_page_translations = [{str(i + 1): text} for i, text in enumerate(seeded_context)]
        if hasattr(translator, "context_size"):
            try:
                previous_context_size = int(getattr(translator, "context_size", 0))
            except Exception:  # noqa: BLE001
                previous_context_size = 0
            translator.context_size = max(len(seeded_context), previous_context_size or 0)

    pseudo_ctx = SimpleNamespace(from_lang=str(from_lang or "auto"), text_regions=[])
    try:
        translated = loop.run_until_complete(translator._batch_translate_texts(texts, config, pseudo_ctx))
        return [str(item or "") for item in translated]
    finally:
        if previous_page_translations is not None and hasattr(translator, "all_page_translations"):
            translator.all_page_translations = previous_page_translations
        if previous_context_size is not None and hasattr(translator, "context_size"):
            translator.context_size = previous_context_size
        end_translation_operation()
        _drain_pending_tasks(loop)


def _run_split_render_sync(
    cache_payload: dict[str, Any],
    translated_regions: list[dict[str, Any]],
) -> tuple[bytes, dict[str, Any]]:
    from manga_translator.server.core.task_manager import (
        _ensure_runtime_for_translator,
        begin_translation_operation,
        cleanup_context,
        end_translation_operation,
        get_global_translator,
    )
    from manga_translator.server.request_extraction import _drain_pending_tasks, _get_translation_event_loop

    _ensure_runtime_for_translator()
    ctx = cache_payload["ctx"]
    config = cache_payload["config"]
    image_name = str(cache_payload.get("image_name") or "page.jpg")
    text_regions = list(getattr(ctx, "text_regions", []) or [])
    for item in translated_regions:
        idx = int(item.get("region_index", -1))
        if idx < 0 or idx >= len(text_regions):
            raise ValueError("RENDER_INPUT_INVALID")
        text_regions[idx].translation = str(item.get("translation") or "")

    translator = get_global_translator()
    loop = _get_translation_event_loop()
    started_at = time.perf_counter()
    begin_translation_operation()
    try:
        ctx = loop.run_until_complete(translator._complete_translation_pipeline(ctx, config))
        if not getattr(ctx, "result", None):
            raise RuntimeError("render produced no output image")
        suffix = Path(image_name).suffix.lower() or ".jpg"
        format_map = {".jpg": "JPEG", ".jpeg": "JPEG", ".png": "PNG", ".webp": "WEBP"}
        target_path = Path(tempfile.gettempdir()) / f"split-render-{uuid.uuid4().hex}{suffix}"
        prepared = _prepare_output_image(ctx.result, target_path)
        output = io.BytesIO()
        prepared.save(output, format=format_map.get(suffix, "PNG"))
        render_ms = (time.perf_counter() - started_at) * 1000.0
        stage_elapsed = {
            "render": round(render_ms, 3),
            "total": round(render_ms, 3),
        }
        return output.getvalue(), {
            "regions_count": len(text_regions),
            "stage_elapsed_ms": stage_elapsed,
            "page_translation_text": _extract_context_text(ctx),
        }
    finally:
        end_translation_operation()
        _drain_pending_tasks(loop)
        cleanup_context(ctx)


async def _split_detect_payload(
    payload: bytes,
    image_name: str,
    source_language: str | None,
    target_language: str | None,
) -> dict[str, Any]:
    from manga_translator.server.core.task_manager import run_in_translator_thread

    raw = await run_in_translator_thread(
        _run_split_detect_sync,
        payload,
        image_name,
        source_language,
        target_language,
    )
    task_id = str(uuid.uuid4())
    image_hash = _hash_payload(payload)
    ttl_seconds = _SPLIT_CTX_CACHE.put(task_id, image_hash, raw)

    serialized_regions: list[dict[str, Any]] = []
    for idx, region in enumerate(raw.get("regions") or []):
        if hasattr(region, "to_dict"):
            item = dict(region.to_dict() or {})
        elif isinstance(region, dict):
            item = dict(region)
        else:
            item = {}
        item["region_index"] = idx
        serialized_regions.append(item)

    return {
        "task_id": task_id,
        "ttl_seconds": ttl_seconds,
        "image_hash": image_hash,
        "regions_count": len(serialized_regions),
        "regions": serialized_regions,
        "from_lang": str(raw.get("from_lang") or ""),
        "elapsed_ms": _normalize_split_detect_elapsed(raw.get("elapsed_ms")),
    }


async def _split_render_payload(
    cache_payload: dict[str, Any],
    translated_regions: list[dict[str, Any]],
) -> tuple[bytes, dict[str, Any]]:
    from manga_translator.server.core.task_manager import run_in_translator_thread

    return await run_in_translator_thread(_run_split_render_sync, cache_payload, translated_regions)


async def _split_translate_texts_impl(
    texts: list[str],
    source_language: str | None,
    target_language: str | None,
    from_lang: str | None,
    context_translations: list[str] | None,
    model_name: str,
) -> list[str]:
    from manga_translator.server.core.task_manager import run_in_translator_thread

    return await run_in_translator_thread(
        _run_split_translate_sync,
        texts,
        source_language,
        target_language,
        from_lang,
        context_translations or [],
        model_name,
    )


async def _translate_texts_for_split(
    texts: list[str],
    source_language: str | None,
    target_language: str | None,
    from_lang: str | None,
    context_translations: list[str] | None,
    primary_model: str | None = None,
    fallback_model: str | None = None,
) -> dict[str, Any]:
    resolved_primary = _resolve_gemini_primary_model(primary_model)
    resolved_fallback = _resolve_gemini_fallback_model(fallback_model)
    selected_model = resolved_primary
    model_fallback_reason: str | None = None

    async with _split_translate_semaphore():
        try:
            translated = await _split_translate_texts_impl(
                texts,
                source_language,
                target_language,
                from_lang,
                context_translations,
                resolved_primary,
            )
        except Exception as primary_exc:  # noqa: BLE001
            primary_reason = str(primary_exc).strip() or primary_exc.__class__.__name__
            if resolved_fallback == resolved_primary:
                raise
            selected_model = resolved_fallback
            model_fallback_reason = primary_reason
            translated = await _split_translate_texts_impl(
                texts,
                source_language,
                target_language,
                from_lang,
                context_translations,
                resolved_fallback,
            )

    return {
        "translations": translated,
        "primary_model": resolved_primary,
        "fallback_model": resolved_fallback,
        "selected_model": selected_model,
        "model_fallback_reason": model_fallback_reason,
    }


class TranslateExecutor:
    backend = "local"

    async def translate_page(
        self,
        image_path: Path,
        output_path: Path,
        source_language: str | None,
        target_language: str | None,
        *,
        context_translations: list[str] | None = None,
    ) -> dict:
        raise NotImplementedError


class LocalTranslateExecutor(TranslateExecutor):
    backend = "local"

    async def translate_page(
        self,
        image_path: Path,
        output_path: Path,
        source_language: str | None,
        target_language: str | None,
        *,
        context_translations: list[str] | None = None,
    ) -> dict:
        try:
            return await _translate_single_image(
                image_path,
                output_path,
                source_language,
                target_language,
                context_translations=context_translations,
            )
        except TypeError as exc:
            if "context_translations" not in str(exc):
                raise
            # Compatibility path for tests/mocks with legacy signature.
            return await _translate_single_image(
                image_path,
                output_path,
                source_language,
                target_language,
            )


class CloudRunTranslateExecutor(TranslateExecutor):
    backend = "cloudrun"

    def __init__(
        self,
        endpoint: str,
        timeout_sec: int = CLOUDRUN_EXECUTOR_TIMEOUT_SEC,
        pipeline_mode: str | None = None,
    ) -> None:
        self._endpoint = endpoint.rstrip("/")
        self._timeout_sec = max(1, int(timeout_sec))
        resolved_mode = str(pipeline_mode or _resolve_translate_pipeline_mode()).strip().lower()
        self._pipeline_mode = resolved_mode if resolved_mode in TRANSLATE_PIPELINE_MODE_CHOICES else "unified"

    async def translate_page(
        self,
        image_path: Path,
        output_path: Path,
        source_language: str | None,
        target_language: str | None,
        *,
        context_translations: list[str] | None = None,
    ) -> dict:
        if self._pipeline_mode == "split":
            try:
                return await self._translate_via_split_pipeline(
                    image_path=image_path,
                    output_path=output_path,
                    source_language=source_language,
                    target_language=target_language,
                    context_translations=context_translations,
                )
            except CloudRunExecutionError as exc:
                if _is_split_cache_fallback_error(exc):
                    fallback = await self._translate_via_unified_pipeline(
                        image_path=image_path,
                        output_path=output_path,
                        source_language=source_language,
                        target_language=target_language,
                        context_translations=context_translations,
                    )
                    fallback["pipeline_mode"] = "fallback_to_unified"
                    return fallback
                raise

        return await self._translate_via_unified_pipeline(
            image_path=image_path,
            output_path=output_path,
            source_language=source_language,
            target_language=target_language,
            context_translations=context_translations,
        )

    async def _translate_via_unified_pipeline(
        self,
        *,
        image_path: Path,
        output_path: Path,
        source_language: str | None,
        target_language: str | None,
        context_translations: list[str] | None,
    ) -> dict:
        payload = image_path.read_bytes()
        context = _build_context_translations(context_translations)
        primary_model = _resolve_gemini_primary_model()
        fallback_model = _resolve_gemini_fallback_model()
        token = _resolve_internal_token()
        headers: dict[str, str] = {}
        if token:
            headers[INTERNAL_TOKEN_HEADER] = token
        headers["Accept-Encoding"] = "gzip, deflate"

        data = {
            "source_language": source_language or "",
            "target_language": target_language or "",
            "context_translations": json.dumps(context, ensure_ascii=False),
            "primary_model": primary_model,
            "fallback_model": fallback_model,
        }
        files = {
            "image": (image_path.name, payload, "application/octet-stream"),
        }

        timeout = httpx.Timeout(self._timeout_sec)
        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.post(
                f"{self._endpoint}/internal/translate/page",
                data=data,
                files=files,
                headers=headers,
            )

        if response.status_code != 200:
            detail_text = response.text.strip()
            detail = f"cloudrun status={response.status_code}"
            if detail_text:
                detail = f"{detail}; detail={detail_text}"
            raise CloudRunExecutionError(
                status_code=response.status_code,
                message=detail,
                failure_stage="remote",
                retryable=response.status_code in CLOUDRUN_RETRYABLE_STATUS,
            )

        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_bytes(response.content)
        stage_elapsed_raw = _decode_header_value(response.headers.get("x-stage-elapsed-ms", "{}"))
        try:
            stage_elapsed_ms = json.loads(stage_elapsed_raw)
            if not isinstance(stage_elapsed_ms, dict):
                stage_elapsed_ms = {}
        except Exception:  # noqa: BLE001
            stage_elapsed_ms = {}

        regions_count = _to_non_negative_int(response.headers.get("x-regions-count"), default=0)
        output_changed = _image_has_visible_changes(payload, output_path)
        fallback_used = response.headers.get("x-fallback-used", "0") == "1"
        fallback_reason = _decode_header_value(response.headers.get("x-fallback-reason")) or None
        no_change_reason = _decode_header_value(response.headers.get("x-no-change-reason")) or None
        failure_stage = _decode_header_value(response.headers.get("x-failure-stage")) or None
        page_translation_text = _decode_header_value(response.headers.get("x-translation-text", "")).strip()
        selected_model = _decode_header_value(response.headers.get("x-selected-model")) or primary_model
        resolved_primary_model = _decode_header_value(response.headers.get("x-primary-model")) or primary_model
        resolved_fallback_model = _decode_header_value(response.headers.get("x-fallback-model")) or fallback_model
        model_fallback_reason = _decode_header_value(response.headers.get("x-model-fallback-reason")) or None
        remote_elapsed_ms = _to_non_negative_int(response.headers.get("x-remote-elapsed-ms"), default=0)
        cold_start = response.headers.get("x-cold-start", "0") == "1"

        if fallback_used:
            reason = fallback_reason or "unknown_fallback_reason"
            stage = failure_stage or "translate"
            raise CloudRunExecutionError(
                status_code=200,
                message=f"cloudrun fallback used: {reason}",
                failure_stage=stage,
                retryable=False,
            )

        return {
            "output_path": str(output_path),
            "regions_count": regions_count,
            "output_changed": output_changed,
            "no_change_reason": no_change_reason,
            "fallback_used": fallback_used,
            "fallback_reason": fallback_reason,
            "stage_elapsed_ms": stage_elapsed_ms,
            "failure_stage": failure_stage,
            "execution_backend": "cloudrun",
            "remote_elapsed_ms": remote_elapsed_ms,
            "cold_start": cold_start,
            "page_translation_text": page_translation_text,
            "primary_model": resolved_primary_model,
            "fallback_model": resolved_fallback_model,
            "selected_model": selected_model,
            "model_fallback_reason": model_fallback_reason,
            "pipeline_mode": "unified",
        }

    async def _translate_via_split_pipeline(
        self,
        *,
        image_path: Path,
        output_path: Path,
        source_language: str | None,
        target_language: str | None,
        context_translations: list[str] | None,
    ) -> dict:
        payload = image_path.read_bytes()
        token = _resolve_internal_token()
        headers: dict[str, str] = {
            "Accept-Encoding": "gzip, deflate",
        }
        if token:
            headers[INTERNAL_TOKEN_HEADER] = token

        timeout = httpx.Timeout(self._timeout_sec)
        async with httpx.AsyncClient(timeout=timeout) as client:
            detect_response = await client.post(
                f"{self._endpoint}/internal/translate/detect",
                headers=headers,
                files={"image": (image_path.name, payload, "application/octet-stream")},
                data={
                    "source_language": source_language or "",
                    "target_language": target_language or "",
                },
            )

            if detect_response.status_code != 200:
                detail_text = detect_response.text.strip()
                detail = f"cloudrun detect status={detect_response.status_code}"
                if detail_text:
                    detail = f"{detail}; detail={detail_text}"
                raise CloudRunExecutionError(
                    status_code=detect_response.status_code,
                    message=detail,
                    failure_stage="detect",
                    retryable=detect_response.status_code in CLOUDRUN_RETRYABLE_STATUS,
                )

            detect_payload = detect_response.json()
            regions = list(detect_payload.get("regions") or [])
            if not regions:
                output_path.parent.mkdir(parents=True, exist_ok=True)
                output_path.write_bytes(payload)
                return {
                    "output_path": str(output_path),
                    "regions_count": 0,
                    "output_changed": False,
                    "no_change_reason": "no_text_regions_detected",
                    "fallback_used": False,
                    "fallback_reason": None,
                    "stage_elapsed_ms": {"total": 0.0},
                    "failure_stage": "detect",
                    "execution_backend": "cloudrun",
                    "remote_elapsed_ms": 0,
                    "cold_start": False,
                    "page_translation_text": "",
                    "primary_model": _resolve_gemini_primary_model(),
                    "fallback_model": _resolve_gemini_fallback_model(),
                    "selected_model": _resolve_gemini_primary_model(),
                    "model_fallback_reason": None,
                    "pipeline_mode": "split",
                }

            texts = [_extract_region_text(region) for region in regions]
            translated = await _translate_texts_for_split(
                texts=texts,
                source_language=source_language,
                target_language=target_language,
                from_lang=str(detect_payload.get("from_lang") or ""),
                context_translations=context_translations or [],
            )
            translated_regions = []
            for index, region in enumerate(regions):
                region_index = int(region.get("region_index", index))
                translated_text = ""
                if index < len(translated["translations"]):
                    translated_text = str(translated["translations"][index] or "")
                translated_regions.append(
                    {
                        "region_index": region_index,
                        "translation": translated_text,
                    }
                )

            render_response = await client.post(
                f"{self._endpoint}/internal/translate/render",
                headers=headers,
                json={
                    "task_id": str(detect_payload.get("task_id") or ""),
                    "image_hash": str(detect_payload.get("image_hash") or ""),
                    "translated_regions": translated_regions,
                    "primary_model": translated.get("primary_model"),
                    "fallback_model": translated.get("fallback_model"),
                    "selected_model": translated.get("selected_model"),
                    "fallback_reason": translated.get("model_fallback_reason"),
                    "translation_text": "\n".join(translated.get("translations") or []),
                },
            )

        if render_response.status_code != 200:
            detail_text = render_response.text.strip()
            detail = f"cloudrun render status={render_response.status_code}"
            if detail_text:
                detail = f"{detail}; detail={detail_text}"
            raise CloudRunExecutionError(
                status_code=render_response.status_code,
                message=detail,
                failure_stage="render",
                retryable=render_response.status_code in {503, 504},
            )

        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_bytes(render_response.content)
        stage_elapsed_raw = _decode_header_value(render_response.headers.get("x-stage-elapsed-ms", "{}"))
        try:
            stage_elapsed_ms = json.loads(stage_elapsed_raw)
            if not isinstance(stage_elapsed_ms, dict):
                stage_elapsed_ms = {}
        except Exception:  # noqa: BLE001
            stage_elapsed_ms = {}

        regions_count = _to_non_negative_int(render_response.headers.get("x-regions-count"), default=0)
        output_changed = _image_has_visible_changes(payload, output_path)
        page_translation_text = _decode_header_value(render_response.headers.get("x-translation-text", "")).strip()
        selected_model = _decode_header_value(render_response.headers.get("x-selected-model")) or str(
            translated.get("selected_model") or ""
        )
        resolved_primary_model = _decode_header_value(render_response.headers.get("x-primary-model")) or str(
            translated.get("primary_model") or ""
        )
        resolved_fallback_model = _decode_header_value(render_response.headers.get("x-fallback-model")) or str(
            translated.get("fallback_model") or ""
        )
        model_fallback_reason = _decode_header_value(render_response.headers.get("x-model-fallback-reason")) or str(
            translated.get("model_fallback_reason") or ""
        )
        remote_elapsed_ms = _to_non_negative_int(render_response.headers.get("x-remote-elapsed-ms"), default=0)
        return {
            "output_path": str(output_path),
            "regions_count": regions_count,
            "output_changed": output_changed,
            "no_change_reason": None if output_changed else "output_matches_source",
            "fallback_used": False,
            "fallback_reason": None,
            "stage_elapsed_ms": stage_elapsed_ms,
            "failure_stage": None,
            "execution_backend": "cloudrun",
            "remote_elapsed_ms": remote_elapsed_ms,
            "cold_start": False,
            "page_translation_text": page_translation_text,
            "primary_model": resolved_primary_model,
            "fallback_model": resolved_fallback_model,
            "selected_model": selected_model,
            "model_fallback_reason": model_fallback_reason or None,
            "pipeline_mode": "split",
        }


def _get_translate_executor(backend: str | None = None) -> TranslateExecutor:
    backend = (backend or _resolve_translate_execution_backend()).strip().lower()
    if backend == "cloudrun":
        endpoint = _resolve_cloudrun_executor_url()
        if endpoint:
            return CloudRunTranslateExecutor(
                endpoint=endpoint,
                pipeline_mode=_resolve_translate_pipeline_mode(),
            )
        logger.warning("cloudrun execution backend requested but MANGA_CLOUDRUN_EXEC_URL is empty; fallback to local")
    return LocalTranslateExecutor()


def _cleanup_translated_variants(manga_id: str, chapter_id: str, image_name: str) -> None:
    """Remove translated outputs with the same stem to avoid stale 'translated' states."""
    translated_dir = (library_service.results_dir / manga_id / chapter_id).resolve()
    if not translated_dir.exists() or not translated_dir.is_dir():
        return

    stem = Path(image_name).stem
    for file_path in translated_dir.iterdir():
        if not file_path.is_file() or file_path.suffix.lower() not in IMAGE_EXTENSIONS:
            continue
        if file_path.stem != stem:
            continue
        try:
            file_path.unlink()
        except OSError:
            logger.warning("failed to remove stale translated file: %s", file_path)


async def _build_translate_context(
    request: Request,
    config,
    payload: bytes,
    cleanup_reason: str | None = "single_request_complete",
    cleanup_force: bool = False,
):
    from manga_translator.server.request_extraction import get_ctx

    return await get_ctx(
        request,
        config,
        payload,
        "normal",
        cleanup_reason=cleanup_reason,
        cleanup_force=cleanup_force,
    )


def _image_has_visible_changes(source_payload: bytes, output_path: Path) -> bool:
    if not output_path.exists():
        return False
    try:
        with Image.open(io.BytesIO(source_payload)) as source_img, Image.open(output_path) as output_img:
            src_rgb = source_img.convert("RGB")
            out_rgb = output_img.convert("RGB")
            if src_rgb.size != out_rgb.size:
                return True
            return ImageChops.difference(src_rgb, out_rgb).getbbox() is not None
    except Exception:  # noqa: BLE001
        try:
            return output_path.read_bytes() != source_payload
        except OSError:
            return False


def _prepare_output_image(image: Image.Image, output_path: Path) -> Image.Image:
    """Normalize image mode for target format to avoid save-time fallback errors."""
    suffix = output_path.suffix.lower()
    if suffix in {".jpg", ".jpeg"} and image.mode in {"RGBA", "LA"}:
        alpha = image.getchannel("A") if "A" in image.getbands() else None
        base = Image.new("RGB", image.size, color=(255, 255, 255))
        if alpha is not None:
            base.paste(image.convert("RGB"), mask=alpha)
        else:
            base.paste(image.convert("RGB"))
        return base
    if suffix in {".jpg", ".jpeg"} and image.mode not in {"RGB", "L"}:
        return image.convert("RGB")
    return image


def _empty_stage_timing() -> dict[str, float]:
    return {
        "context": 0.0,
        "render": 0.0,
        "total": 0.0,
    }


def _executor_retry_limit() -> int:
    return _env_non_negative_int("MANGA_TRANSLATE_EXECUTOR_MAX_RETRIES", 2)


def _is_retryable_executor_error(exc: Exception) -> bool:
    if isinstance(exc, CloudRunExecutionError):
        return bool(exc.retryable)
    if isinstance(exc, httpx.TimeoutException):
        return True
    if isinstance(exc, httpx.TransportError):
        return True
    message = str(exc).lower()
    if not message:
        return False
    retryable_markers = (
        "timed out",
        "timeout",
        "temporarily unavailable",
        "connection reset",
        "connection refused",
        "503",
        "502",
        "504",
        "429",
    )
    return any(marker in message for marker in retryable_markers)


async def _translate_single_image(
    image_path: Path,
    output_path: Path,
    source_language: str | None,
    target_language: str | None,
    cleanup_reason: str | None = "single_request_complete",
    cleanup_force: bool = False,
    context_translations: list[str] | None = None,
    primary_model: str | None = None,
    fallback_model: str | None = None,
) -> dict:
    started_at = time.perf_counter()
    payload = image_path.read_bytes()
    output_path.parent.mkdir(parents=True, exist_ok=True)

    resolved_primary_model = _resolve_gemini_primary_model(primary_model)
    resolved_fallback_model = _resolve_gemini_fallback_model(fallback_model)
    selected_model = resolved_primary_model
    model_fallback_reason: str | None = None

    try:
        from manga_translator.server.core.config_manager import load_default_config

        config = load_default_config()
        config.translator.attempts = _resolve_translate_attempts(config)
        if source_language:
            config.translator.skip_lang = None
        config.translator.target_lang = _resolve_target_language(target_language)
        if context_translations:
            setattr(config, "_context_translations_seed", _build_context_translations(context_translations))
        else:
            setattr(config, "_context_translations_seed", [])
        if hasattr(config, "translator"):
            config.translator.user_api_model = resolved_primary_model

        fake_request = Request({"type": "http", "method": "POST", "path": "/api/v1/translate/page", "headers": []})

        async def _run_with_model(model_name: str) -> dict:
            stage_elapsed_ms = _empty_stage_timing()
            failure_stage = "context"
            if hasattr(config, "translator"):
                config.translator.user_api_model = model_name
            context_started_at = time.perf_counter()
            try:
                context_awaitable = _build_translate_context(
                    fake_request,
                    config,
                    payload,
                    cleanup_reason=cleanup_reason,
                    cleanup_force=cleanup_force,
                )
            except TypeError as exc:
                if "cleanup_reason" not in str(exc):
                    raise
                # Backward-compatible path for tests/mocks overriding legacy signature.
                context_awaitable = _build_translate_context(fake_request, config, payload)

            ctx = await _await_translate_context(context_awaitable, TRANSLATE_CONTEXT_TIMEOUT_SEC)
            stage_elapsed_ms["context"] = (time.perf_counter() - context_started_at) * 1000.0
            # Merge HQ sub-stage timings if available (preprocess/translate/hq_render)
            hq_sub = getattr(ctx, "_hq_stage_elapsed_ms", None)
            if isinstance(hq_sub, dict):
                stage_elapsed_ms.update(hq_sub)
            if not getattr(ctx, "result", None):
                raise RuntimeError("Translation produced no output image")

            failure_stage = "render"
            render_started_at = time.perf_counter()
            prepared_result = _prepare_output_image(ctx.result, output_path)
            prepared_result.save(output_path)
            stage_elapsed_ms["render"] = (time.perf_counter() - render_started_at) * 1000.0
            regions_count = len(getattr(ctx, "text_regions", []) or [])
            page_translation_text = _extract_context_text(ctx)
            # Fast path: if OCR detected text regions, treat output as changed.
            # This avoids expensive full-image diff on every translated page.
            output_changed = regions_count > 0
            if not output_changed:
                output_changed = _image_has_visible_changes(payload, output_path)
            no_change_reason = None
            if not output_changed:
                no_change_reason = "no_text_regions_detected" if regions_count == 0 else "output_matches_source"
            stage_elapsed_ms["total"] = (time.perf_counter() - started_at) * 1000.0
            return {
                "output_path": str(output_path),
                "regions_count": regions_count,
                "output_changed": output_changed,
                "no_change_reason": no_change_reason,
                "fallback_used": False,
                "fallback_reason": None,
                "stage_elapsed_ms": stage_elapsed_ms,
                "failure_stage": None,
                "execution_backend": "local",
                "remote_elapsed_ms": None,
                "page_translation_text": page_translation_text,
                "primary_model": resolved_primary_model,
                "fallback_model": resolved_fallback_model,
                "selected_model": model_name,
                "model_fallback_reason": model_fallback_reason,
            }

        try:
            selected_model = resolved_primary_model
            return await _run_with_model(selected_model)
        except Exception as primary_exc:  # noqa: BLE001
            primary_reason = str(primary_exc).strip() or primary_exc.__class__.__name__
            if resolved_fallback_model != resolved_primary_model:
                selected_model = resolved_fallback_model
                model_fallback_reason = primary_reason
                logger.warning(
                    "Primary Gemini model failed; retrying with fallback model primary_model=%s fallback_model=%s fallback_reason=%s",
                    resolved_primary_model,
                    resolved_fallback_model,
                    primary_reason,
                )
                return await _run_with_model(selected_model)
            raise
    except Exception as exc:  # noqa: BLE001
        # Compatibility fallback for environments where full translator deps are unavailable.
        logger.exception("v1 translate fallback used for %s", image_path)
        fallback_reason = str(exc).strip() or exc.__class__.__name__
        failure_stage = "translate"
        if "render" in fallback_reason.lower():
            failure_stage = "render"
        output_path.write_bytes(payload)
        stage_elapsed_ms = _empty_stage_timing()
        stage_elapsed_ms["total"] = (time.perf_counter() - started_at) * 1000.0
        return {
            "output_path": str(output_path),
            "regions_count": 0,
            "output_changed": False,
            "no_change_reason": "fallback_copy",
            "fallback_used": True,
            "fallback_reason": fallback_reason,
            "stage_elapsed_ms": stage_elapsed_ms,
            "failure_stage": failure_stage,
            "execution_backend": "local",
            "remote_elapsed_ms": None,
            "page_translation_text": "",
            "primary_model": resolved_primary_model,
            "fallback_model": resolved_fallback_model,
            "selected_model": selected_model,
            "model_fallback_reason": model_fallback_reason,
        }


def _build_runtime_snapshot(execution_mode: str, page_concurrency: int, translator_name: str | None) -> dict:
    use_gpu = False
    try:
        from manga_translator.server.core.task_manager import get_server_config

        use_gpu = bool(get_server_config().get("use_gpu", False))
    except Exception:  # noqa: BLE001
        pass

    primary_model = _resolve_gemini_primary_model()
    fallback_model = _resolve_gemini_fallback_model()

    return {
        "use_gpu": use_gpu,
        "execution_mode": execution_mode,
        "pipeline_mode": _resolve_translate_pipeline_mode(),
        "page_concurrency": page_concurrency,
        "translator": translator_name or "unknown",
        "primary_model": primary_model,
        "fallback_model": fallback_model,
    }


async def _translate_chapter_batch_pipeline(
    request: ChapterTranslateRequest,
    images: list[Path],
    page_concurrency: int,
) -> list[tuple[Path, dict | None, Exception | None]]:
    started_at = time.perf_counter()
    context_elapsed_ms = 0.0
    payloads = [image_path.read_bytes() for image_path in images]
    outputs: list[tuple[Path, dict | None, Exception | None]] = []
    primary_model = _resolve_gemini_primary_model()
    fallback_model = _resolve_gemini_fallback_model()
    selected_model = primary_model
    model_fallback_reason: str | None = None

    try:
        from manga_translator.server.core.config_manager import load_default_config
        from manga_translator.server.core.task_manager import cleanup_context
        from manga_translator.server.request_extraction import get_batch_ctx

        config = load_default_config()
        config.translator.attempts = _resolve_translate_attempts(config)
        if request.source_language:
            config.translator.skip_lang = None
        config.translator.target_lang = _resolve_target_language(request.target_language)
        if hasattr(config, "translator"):
            config.translator.user_api_model = primary_model

        fake_request = Request(
            {
                "type": "http",
                "method": "POST",
                "path": "/api/v1/translate/chapter",
                "headers": [],
            }
        )
        batch_timeout = TRANSLATE_CONTEXT_TIMEOUT_SEC * max(1, len(images))
        context_started_at = time.perf_counter()

        async def _run_batch_contexts(model_name: str):
            if hasattr(config, "translator"):
                config.translator.user_api_model = model_name
            return await _await_translate_context(
                get_batch_ctx(
                    fake_request,
                    config,
                    payloads,
                    batch_size=max(1, page_concurrency),
                    workflow="normal",
                    cleanup_reason="chapter_batch_complete",
                    cleanup_force=False,
                ),
                batch_timeout,
            )

        try:
            contexts = await _run_batch_contexts(primary_model)
            selected_model = primary_model
        except Exception as primary_exc:  # noqa: BLE001
            primary_reason = str(primary_exc).strip() or primary_exc.__class__.__name__
            if fallback_model != primary_model:
                selected_model = fallback_model
                model_fallback_reason = primary_reason
                logger.warning(
                    "Batch pipeline primary model failed; retrying fallback model primary_model=%s fallback_model=%s fallback_reason=%s",
                    primary_model,
                    fallback_model,
                    primary_reason,
                )
                contexts = await _run_batch_contexts(fallback_model)
            else:
                raise

        context_elapsed_ms = (time.perf_counter() - context_started_at) * 1000.0

        contexts_list = list(contexts or [])
        for idx, image_path in enumerate(images):
            payload = payloads[idx]
            output_path = library_service.results_dir / request.manga_id / request.chapter_id / image_path.name
            output_path.parent.mkdir(parents=True, exist_ok=True)

            if idx >= len(contexts_list) or contexts_list[idx] is None:
                fallback_reason = "translation returned empty result"
                output_path.write_bytes(payload)
                page_stage = _empty_stage_timing()
                page_stage["context"] = context_elapsed_ms
                page_stage["total"] = context_elapsed_ms
                outputs.append(
                    (
                        image_path,
                        {
                            "output_path": str(output_path),
                            "regions_count": 0,
                            "output_changed": False,
                            "no_change_reason": "fallback_copy",
                            "fallback_used": True,
                            "fallback_reason": fallback_reason,
                            "stage_elapsed_ms": page_stage,
                            "failure_stage": "translate",
                            "primary_model": primary_model,
                            "fallback_model": fallback_model,
                            "selected_model": selected_model,
                            "model_fallback_reason": model_fallback_reason,
                        },
                        None,
                    )
                )
                continue

            ctx = contexts_list[idx]
            try:
                if not getattr(ctx, "result", None):
                    raise RuntimeError("Translation produced no output image")

                render_started_at = time.perf_counter()
                prepared_result = _prepare_output_image(ctx.result, output_path)
                prepared_result.save(output_path)
                render_elapsed_ms = (time.perf_counter() - render_started_at) * 1000.0
                regions_count = len(getattr(ctx, "text_regions", []) or [])
                # Fast path: if OCR detected text regions, treat output as changed.
                # This avoids expensive full-image diff on every translated page.
                output_changed = regions_count > 0
                if not output_changed:
                    output_changed = _image_has_visible_changes(payload, output_path)
                no_change_reason = None
                if not output_changed:
                    no_change_reason = "no_text_regions_detected" if regions_count == 0 else "output_matches_source"
                page_stage = _empty_stage_timing()
                page_stage["context"] = context_elapsed_ms
                page_stage["render"] = render_elapsed_ms
                page_stage["total"] = context_elapsed_ms + render_elapsed_ms
                outputs.append(
                    (
                        image_path,
                        {
                            "output_path": str(output_path),
                            "regions_count": regions_count,
                            "output_changed": output_changed,
                            "no_change_reason": no_change_reason,
                            "fallback_used": False,
                            "fallback_reason": None,
                            "stage_elapsed_ms": page_stage,
                            "failure_stage": None,
                            "primary_model": primary_model,
                            "fallback_model": fallback_model,
                            "selected_model": selected_model,
                            "model_fallback_reason": model_fallback_reason,
                        },
                        None,
                    )
                )
            except Exception as page_exc:  # noqa: BLE001
                fallback_reason = str(page_exc).strip() or page_exc.__class__.__name__
                output_path.write_bytes(payload)
                page_stage = _empty_stage_timing()
                page_stage["context"] = context_elapsed_ms
                page_stage["total"] = context_elapsed_ms
                outputs.append(
                    (
                        image_path,
                        {
                            "output_path": str(output_path),
                            "regions_count": 0,
                            "output_changed": False,
                            "no_change_reason": "fallback_copy",
                            "fallback_used": True,
                            "fallback_reason": fallback_reason,
                            "stage_elapsed_ms": page_stage,
                            "failure_stage": "render",
                            "primary_model": primary_model,
                            "fallback_model": fallback_model,
                            "selected_model": selected_model,
                            "model_fallback_reason": model_fallback_reason,
                        },
                        page_exc,
                    )
                )
            finally:
                cleanup_context(ctx)
    except Exception as exc:  # noqa: BLE001
        logger.exception("v1 chapter batch pipeline fallback used for %s/%s", request.manga_id, request.chapter_id)
        fallback_reason = str(exc).strip() or exc.__class__.__name__
        for image_path, payload in zip(images, payloads):
            output_path = library_service.results_dir / request.manga_id / request.chapter_id / image_path.name
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_bytes(payload)
            page_stage = _empty_stage_timing()
            page_stage["context"] = context_elapsed_ms
            page_stage["total"] = (time.perf_counter() - started_at) * 1000.0
            outputs.append(
                (
                    image_path,
                    {
                        "output_path": str(output_path),
                        "regions_count": 0,
                        "output_changed": False,
                        "no_change_reason": "fallback_copy",
                        "fallback_used": True,
                        "fallback_reason": fallback_reason,
                        "stage_elapsed_ms": page_stage,
                        "failure_stage": "translate",
                        "primary_model": primary_model,
                        "fallback_model": fallback_model,
                        "selected_model": selected_model,
                        "model_fallback_reason": model_fallback_reason,
                    },
                    exc,
                )
            )

    return outputs


async def _translate_payload_via_temp_files(
    payload: bytes,
    image_name: str,
    source_language: str | None,
    target_language: str | None,
    *,
    context_translations: list[str] | None = None,
    primary_model: str | None = None,
    fallback_model: str | None = None,
) -> tuple[bytes, dict]:
    suffix = Path(image_name).suffix or ".jpg"
    with tempfile.TemporaryDirectory(prefix="mt-internal-translate-") as temp_dir:
        temp_root = Path(temp_dir)
        source_path = temp_root / f"source{suffix}"
        output_path = temp_root / f"output{suffix}"
        source_path.write_bytes(payload)
        result = await _translate_single_image(
            source_path,
            output_path,
            source_language,
            target_language,
            context_translations=context_translations,
            primary_model=primary_model,
            fallback_model=fallback_model,
        )
        if not output_path.exists():
            raise RuntimeError("internal translate produced no output file")
        return output_path.read_bytes(), result


async def _execute_page_with_retry(
    *,
    executor: TranslateExecutor,
    image_path: Path,
    output_path: Path,
    source_language: str | None,
    target_language: str | None,
    context_translations: list[str] | None = None,
    max_retries: int | None = None,
) -> tuple[dict | None, Exception | None, int]:
    retries = _executor_retry_limit() if max_retries is None else max(0, int(max_retries))
    attempts = retries + 1
    last_error: Exception | None = None
    executed_attempts = 0

    for attempt_index in range(attempts):
        executed_attempts = attempt_index + 1
        try:
            if executor.backend == "cloudrun":
                async with _cloudrun_serial_lock():
                    result = await executor.translate_page(
                        image_path,
                        output_path,
                        source_language,
                        target_language,
                        context_translations=context_translations,
                    )
            else:
                result = await executor.translate_page(
                    image_path,
                    output_path,
                    source_language,
                    target_language,
                    context_translations=context_translations,
                )
            stage = dict(result.get("stage_elapsed_ms") or {})
            stage["executor_attempts"] = attempt_index + 1
            result["stage_elapsed_ms"] = stage
            return result, None, executed_attempts
        except Exception as exc:  # noqa: BLE001
            last_error = exc
            if attempt_index >= retries or not _is_retryable_executor_error(exc):
                break
            backoff_idx = min(attempt_index, len(CLOUDRUN_EXECUTOR_RETRY_BACKOFFS) - 1)
            await asyncio.sleep(CLOUDRUN_EXECUTOR_RETRY_BACKOFFS[backoff_idx])

    return None, last_error, max(1, executed_attempts)


async def _publish_page_result(
    request: ChapterTranslateRequest,
    image_path: Path,
    task_id: str,
    result: dict | None,
    error: Exception | None,
    pipeline: str,
    execution_backend: str = "local",
) -> bool:
    stage_elapsed = dict(result.get("stage_elapsed_ms") or {}) if result else {}
    page_pipeline = str((result or {}).get("pipeline_mode") or pipeline)
    remote_elapsed_ms = _to_non_negative_int((result or {}).get("remote_elapsed_ms"), default=0)
    primary_model = str((result or {}).get("primary_model") or "")
    fallback_model = str((result or {}).get("fallback_model") or "")
    selected_model = str((result or {}).get("selected_model") or "")
    model_fallback_reason = str((result or {}).get("model_fallback_reason") or "")
    if error is not None:
        _cleanup_translated_variants(request.manga_id, request.chapter_id, image_path.name)
        failure_stage = str(getattr(error, "failure_stage", "") or "translate")
        status_code = getattr(error, "status_code", None)
        error_detail = str(error).strip() or error.__class__.__name__
        if status_code is not None:
            error_detail = f"status={status_code}; {error_detail}"
        error_message = f"[{failure_stage}] {error_detail}"
        logger.warning(
            "translate_page_failed backend=%s image=%s task_id=%s status_code=%s failure_stage=%s fallback_used=%s attempts=%s primary_model=%s fallback_model=%s selected_model=%s fallback_reason=%s error=%s",
            execution_backend,
            image_path.name,
            task_id,
            status_code,
            failure_stage,
            False,
            stage_elapsed.get("executor_attempts"),
            primary_model,
            fallback_model,
            selected_model,
            model_fallback_reason,
            error_detail,
        )
        await v1_event_bus.publish(
            {
                "type": "progress",
                "task_id": task_id,
                "manga_id": request.manga_id,
                "chapter_id": request.chapter_id,
                "image_name": image_path.name,
                "stage": "failed",
                "status": "failed",
                "error_message": error_message,
                "pipeline": page_pipeline,
                "execution_backend": execution_backend,
                "failure_stage": failure_stage,
                "remote_elapsed_ms": remote_elapsed_ms,
                "stage_elapsed_ms": stage_elapsed,
                "primary_model": primary_model,
                "fallback_model": fallback_model,
                "selected_model": selected_model,
            }
        )
        return False

    if result is None:
        await v1_event_bus.publish(
            {
                "type": "progress",
                "task_id": task_id,
                "manga_id": request.manga_id,
                "chapter_id": request.chapter_id,
                "image_name": image_path.name,
                "stage": "failed",
                "status": "failed",
                "error_message": "translation returned empty result",
                "pipeline": page_pipeline,
                "execution_backend": execution_backend,
                "failure_stage": "translate",
                "remote_elapsed_ms": remote_elapsed_ms,
                "stage_elapsed_ms": stage_elapsed,
                "primary_model": primary_model,
                "fallback_model": fallback_model,
                "selected_model": selected_model,
            }
        )
        return False

    fallback_used = bool(result.get("fallback_used"))
    output_changed = bool(result.get("output_changed", True))
    regions_count = _to_non_negative_int(result.get("regions_count"), default=0)
    has_regions = regions_count > 0

    if fallback_used or not output_changed or not has_regions:
        _cleanup_translated_variants(request.manga_id, request.chapter_id, image_path.name)
        failure_stage = "validate"
        if fallback_used:
            error_message = f"fallback used: {result.get('fallback_reason') or 'translation unavailable'}"
            failure_stage = result.get("failure_stage") or "translate"
        elif not has_regions:
            error_message = "no detected text regions"
        else:
            error_message = f"no visible changes: {result.get('no_change_reason') or 'unknown_no_change_reason'}"
        logger.warning(
            "translate_page_failed backend=%s image=%s task_id=%s status_code=%s failure_stage=%s fallback_used=%s attempts=%s primary_model=%s fallback_model=%s selected_model=%s fallback_reason=%s error=%s",
            execution_backend,
            image_path.name,
            task_id,
            None,
            failure_stage,
            fallback_used,
            stage_elapsed.get("executor_attempts"),
            primary_model,
            fallback_model,
            selected_model,
            model_fallback_reason or str(result.get("fallback_reason") or ""),
            error_message,
        )
        await v1_event_bus.publish(
            {
                "type": "progress",
                "task_id": task_id,
                "manga_id": request.manga_id,
                "chapter_id": request.chapter_id,
                "image_name": image_path.name,
                "stage": "failed",
                "status": "failed",
                "error_message": error_message,
                "pipeline": page_pipeline,
                "execution_backend": execution_backend,
                "failure_stage": failure_stage,
                "remote_elapsed_ms": remote_elapsed_ms,
                "stage_elapsed_ms": stage_elapsed,
                "primary_model": primary_model,
                "fallback_model": fallback_model,
                "selected_model": selected_model,
            }
        )
        return False

    await v1_event_bus.publish(
        {
            "type": "progress",
            "task_id": task_id,
            "manga_id": request.manga_id,
            "chapter_id": request.chapter_id,
            "image_name": image_path.name,
            "stage": "complete",
            "status": "completed",
            "pipeline": page_pipeline,
            "execution_backend": execution_backend,
            "remote_elapsed_ms": remote_elapsed_ms,
            "stage_elapsed_ms": stage_elapsed,
            "primary_model": primary_model,
            "fallback_model": fallback_model,
            "selected_model": selected_model,
        }
    )
    return True


async def _process_chapter_job(
    request: ChapterTranslateRequest,
    *,
    chapter_task_id: str | None = None,
    accepted_at: str | None = None,
    execution_backend: str | None = None,
) -> None:
    chapter_started_at = time.perf_counter()
    runtime_profile = _resolve_runtime_profile()
    backend = execution_backend or _resolve_translate_execution_backend()
    executor = _get_translate_executor(backend)
    if executor.backend != backend:
        backend = executor.backend

    try:
        images = _chapter_images(request.manga_id, request.chapter_id)
    except FileNotFoundError as exc:
        await v1_event_bus.publish(
            {
                "type": "chapter_complete",
                "manga_id": request.manga_id,
                "chapter_id": request.chapter_id,
                "status": "error",
                "success_count": 0,
                "failed_count": 0,
                "total_count": 0,
                "error_message": str(exc),
            }
        )
        return

    total = len(images)
    success = 0
    failed = 0
    translator_name = _resolve_translator_name()
    execution_mode = _resolve_chapter_execution_mode(total, translator_name)
    if backend == "cloudrun":
        execution_mode = "single_page"
    page_concurrency = _resolve_chapter_page_concurrency(execution_mode, translator_name)
    runtime = _build_runtime_snapshot(execution_mode, page_concurrency, translator_name)
    runtime["execution_backend"] = backend

    await v1_event_bus.publish(
        {
            "type": "chapter_start",
            "task_id": chapter_task_id,
            "manga_id": request.manga_id,
            "chapter_id": request.chapter_id,
            "total_pages": total,
            "page_concurrency": page_concurrency,
            "pipeline": execution_mode,
            "execution_backend": backend,
            "accepted_at": accepted_at,
            "runtime": runtime,
        }
    )

    translate_started_at = time.perf_counter()

    if execution_mode == "batch_pipeline":
        task_ids = {image_path.name: str(uuid.uuid4()) for image_path in images}
        batch_results = await _translate_chapter_batch_pipeline(request, images, page_concurrency)
        for image_path, result, error in batch_results:
            task_id = task_ids.get(image_path.name, str(uuid.uuid4()))
            page_success = await _publish_page_result(
                request,
                image_path,
                task_id,
                result,
                error,
                pipeline="batch_pipeline",
                execution_backend=backend,
            )
            if page_success:
                success += 1
            else:
                failed += 1
    else:
        semaphore = asyncio.Semaphore(page_concurrency)
        context_lock = asyncio.Lock()
        chapter_context_history: list[str] = []

        async def _run_page(image_path: Path) -> tuple[Path, str, dict | None, Exception | None]:
            task_id = str(uuid.uuid4())
            out_path = library_service.results_dir / request.manga_id / request.chapter_id / image_path.name
            await v1_event_bus.publish(
                {
                    "type": "progress",
                    "task_id": task_id,
                    "manga_id": request.manga_id,
                    "chapter_id": request.chapter_id,
                    "image_name": image_path.name,
                    "stage": "init",
                    "status": "running",
                }
            )
            try:
                async with semaphore:
                    async with context_lock:
                        context_seed = _build_context_translations(chapter_context_history)
                    result, error, attempts = await _execute_page_with_retry(
                        executor=executor,
                        image_path=image_path,
                        output_path=out_path,
                        source_language=request.source_language,
                        target_language=request.target_language,
                        context_translations=context_seed,
                    )
                    if result is not None:
                        stage_elapsed = dict(result.get("stage_elapsed_ms") or {})
                        stage_elapsed["executor_attempts"] = attempts
                        result["stage_elapsed_ms"] = stage_elapsed
                        page_text = str(result.get("page_translation_text") or "").strip()
                        if page_text:
                            async with context_lock:
                                chapter_context_history.append(page_text)
                    if result is None and error is not None:
                        result = {
                            "stage_elapsed_ms": {"executor_attempts": attempts},
                            "execution_backend": backend,
                            "primary_model": runtime.get("primary_model"),
                            "fallback_model": runtime.get("fallback_model"),
                            "selected_model": runtime.get("primary_model"),
                        }
                    return image_path, task_id, result, error
            except Exception as exc:  # noqa: BLE001
                return image_path, task_id, None, exc

        tasks = [asyncio.create_task(_run_page(image_path)) for image_path in images]
        try:
            for done in asyncio.as_completed(tasks):
                image_path, task_id, result, error = await done
                page_success = await _publish_page_result(
                    request,
                    image_path,
                    task_id,
                    result,
                    error,
                    pipeline="single_page",
                    execution_backend=backend,
                )
                if page_success:
                    success += 1
                else:
                    failed += 1
        finally:
            for task in tasks:
                if not task.done():
                    task.cancel()
            if tasks:
                await asyncio.gather(*tasks, return_exceptions=True)

    if success <= 0:
        status = "error"
    elif failed > 0:
        status = "partial"
    else:
        status = "success"

    translate_ms = (time.perf_counter() - translate_started_at) * 1000.0
    total_ms = (time.perf_counter() - chapter_started_at) * 1000.0
    chapter_stage_elapsed_ms = {
        "translate": translate_ms,
        "total": total_ms,
    }

    try:
        from manga_translator.server.core.task_manager import cleanup_after_request

        cleanup_after_request(force=True, reason="chapter_complete")
    except Exception:  # noqa: BLE001
        logger.debug("chapter-level cleanup skipped", exc_info=True)

    await v1_event_bus.publish(
        {
            "type": "chapter_complete",
            "manga_id": request.manga_id,
            "chapter_id": request.chapter_id,
            "status": status,
            "success_count": success,
            "failed_count": failed,
            "total_count": total,
            "task_id": chapter_task_id,
            "execution_mode": execution_mode,
            "pipeline": execution_mode,
            "execution_backend": backend,
            "accepted_at": accepted_at,
            "runtime": runtime,
            "stage_elapsed_ms": chapter_stage_elapsed_ms,
        }
    )

    if runtime_profile == "basic":
        logger.info(
            "[v1_runtime] chapter=%s/%s mode=%s concurrency=%s use_gpu=%s "
            "success=%s failed=%s translate_ms=%.2f total_ms=%.2f",
            request.manga_id,
            request.chapter_id,
            execution_mode,
            page_concurrency,
            runtime.get("use_gpu", False),
            success,
            failed,
            translate_ms,
            total_ms,
        )


@router.post("/chapter")
async def translate_chapter(request: ChapterTranslateRequest, _session: Session = Depends(require_auth)):
    try:
        images = _chapter_images(request.manga_id, request.chapter_id)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    task_id = str(uuid.uuid4())
    accepted_at = datetime.now(timezone.utc).isoformat()
    execution_backend = _resolve_translate_execution_backend()
    asyncio.create_task(
        _process_chapter_job(
            request,
            chapter_task_id=task_id,
            accepted_at=accepted_at,
            execution_backend=execution_backend,
        )
    )
    return {
        "message": "Chapter translation started",
        "page_count": len(images),
        "task_id": task_id,
        "execution_backend": execution_backend,
        "accepted_at": accepted_at,
    }


@router.post("/page")
async def translate_page(request: PageTranslateRequest, _session: Session = Depends(require_auth)):
    image_path = (library_service.raw_dir / request.manga_id / request.chapter_id / request.image_name).resolve()
    if not image_path.exists() or not image_path.is_file():
        raise HTTPException(status_code=404, detail=f"Image not found: {image_path}")

    out_path = library_service.results_dir / request.manga_id / request.chapter_id / request.image_name
    task_id = str(uuid.uuid4())

    try:
        result = await _translate_single_image(
            image_path,
            out_path,
            request.source_language,
            request.target_language,
        )
    except Exception as exc:  # noqa: BLE001
        await v1_event_bus.publish(
            {
                "type": "page_failed",
                "manga_id": request.manga_id,
                "chapter_id": request.chapter_id,
                "image_name": request.image_name,
                "error_message": str(exc),
            }
        )
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    if result.get("fallback_used"):
        _cleanup_translated_variants(request.manga_id, request.chapter_id, request.image_name)
        await v1_event_bus.publish(
            {
                "type": "page_failed",
                "manga_id": request.manga_id,
                "chapter_id": request.chapter_id,
                "image_name": request.image_name,
                "error_message": f"fallback used: {result.get('fallback_reason') or 'translation unavailable'}",
            }
        )
        raise HTTPException(
            status_code=503,
            detail=f"translation fallback used: {result.get('fallback_reason') or 'translation unavailable'}",
        )

    output_changed = bool(result.get("output_changed", True))
    regions_count = _to_non_negative_int(result.get("regions_count"), default=0)
    if regions_count <= 0:
        _cleanup_translated_variants(request.manga_id, request.chapter_id, request.image_name)
        await v1_event_bus.publish(
            {
                "type": "page_failed",
                "manga_id": request.manga_id,
                "chapter_id": request.chapter_id,
                "image_name": request.image_name,
                "error_message": "no detected text regions",
            }
        )
        raise HTTPException(status_code=409, detail="translation completed with no detected text regions")

    if not output_changed:
        _cleanup_translated_variants(request.manga_id, request.chapter_id, request.image_name)
        reason = result.get("no_change_reason") or "unknown_no_change_reason"
        await v1_event_bus.publish(
            {
                "type": "page_failed",
                "manga_id": request.manga_id,
                "chapter_id": request.chapter_id,
                "image_name": request.image_name,
                "error_message": f"no visible changes: {reason}",
            }
        )
        raise HTTPException(status_code=409, detail=f"translation completed with no visible changes ({reason})")

    translated_url = (
        f"/output/{quote(request.manga_id)}/{quote(request.chapter_id)}/{quote(out_path.name)}"
        f"?v={out_path.stat().st_mtime_ns}"
    )
    await v1_event_bus.publish(
        {
            "type": "page_complete",
            "manga_id": request.manga_id,
            "chapter_id": request.chapter_id,
            "image_name": request.image_name,
            "url": translated_url,
            "pipeline": "single_page",
            "stage_elapsed_ms": result.get("stage_elapsed_ms") or {},
            "primary_model": result.get("primary_model"),
            "fallback_model": result.get("fallback_model"),
            "selected_model": result.get("selected_model"),
        }
    )

    return {
        "task_id": task_id,
        "status": "completed",
        "execution_backend": "local",
        "output_path": result["output_path"],
        "translated_url": translated_url,
        "output_changed": True,
        "regions_count": result["regions_count"],
        "stage_elapsed_ms": result.get("stage_elapsed_ms") or {},
        "primary_model": result.get("primary_model"),
        "fallback_model": result.get("fallback_model"),
        "selected_model": result.get("selected_model"),
    }


@internal_router.post("/detect")
async def internal_translate_detect(
    image: UploadFile = File(...),
    source_language: Optional[str] = Form(None),
    target_language: Optional[str] = Form(None),
    x_internal_token: Optional[str] = Header(None, alias=INTERNAL_TOKEN_HEADER),
):
    _verify_internal_token(x_internal_token)
    _ensure_internal_compute_ready()
    try:
        payload = await image.read()
        if not payload:
            raise HTTPException(status_code=400, detail="INVALID_IMAGE")
        result = await _split_detect_payload(
            payload=payload,
            image_name=image.filename or "page.jpg",
            source_language=source_language,
            target_language=target_language,
        )
        if not isinstance(result.get("regions"), list):
            result["regions"] = []
        for index, region in enumerate(result["regions"]):
            if not isinstance(region, dict):
                region = {}
                result["regions"][index] = region
            region["region_index"] = index
        result["regions_count"] = len(result["regions"])
        return result
    except HTTPException:
        raise
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=400, detail=f"INVALID_IMAGE: {exc}") from exc


@internal_router.post("/render")
async def internal_translate_render(
    request: InternalRenderRequest,
    x_internal_token: Optional[str] = Header(None, alias=INTERNAL_TOKEN_HEADER),
):
    _verify_internal_token(x_internal_token)
    _ensure_internal_compute_ready()

    cache_payload, reason = _SPLIT_CTX_CACHE.get(request.task_id, request.image_hash)
    if reason == "CACHE_MISS":
        raise HTTPException(status_code=404, detail="CACHE_MISS")
    if reason == "TASK_EXPIRED":
        raise HTTPException(status_code=410, detail="TASK_EXPIRED")
    if reason == "IMAGE_HASH_MISMATCH":
        raise HTTPException(status_code=422, detail="IMAGE_HASH_MISMATCH")

    try:
        ctx_obj = (cache_payload or {}).get("ctx") if isinstance(cache_payload, dict) else None
        text_regions = list(getattr(ctx_obj, "text_regions", []) or [])
        translated_regions_payload: list[dict[str, Any]] = []
        for item in request.translated_regions:
            region_index = int(item.region_index)
            if region_index < 0 or region_index >= len(text_regions):
                raise HTTPException(status_code=400, detail="RENDER_INPUT_INVALID")
            translated_regions_payload.append(
                {
                    "region_index": region_index,
                    "translation": str(item.translation or ""),
                }
            )

        started_at = time.perf_counter()
        try:
            output_bytes, render_result = await _split_render_payload(cache_payload, translated_regions_payload)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail="RENDER_INPUT_INVALID") from exc
    finally:
        _SPLIT_CTX_CACHE.pop(request.task_id)

    elapsed_ms = int((time.perf_counter() - started_at) * 1000.0)
    stage_elapsed = render_result.get("stage_elapsed_ms") or {}
    stage_elapsed_text = json.dumps(stage_elapsed, ensure_ascii=False)
    translation_text = str(request.translation_text or render_result.get("page_translation_text") or "").strip()
    if len(translation_text) > 1500:
        translation_text = translation_text[:1500]
    primary_model = _resolve_gemini_primary_model(request.primary_model)
    fallback_model = _resolve_gemini_fallback_model(request.fallback_model)
    selected_model = request.selected_model or primary_model

    headers = {
        "x-regions-count": str(_to_non_negative_int(render_result.get("regions_count"), default=0)),
        "x-output-changed": "1",
        "x-fallback-used": "1" if bool(request.fallback_used) else "0",
        "x-fallback-reason": _encode_header_value(request.fallback_reason or ""),
        "x-no-change-reason": "",
        "x-failure-stage": "",
        "x-stage-elapsed-ms": _encode_header_value(stage_elapsed_text),
        "x-remote-elapsed-ms": str(elapsed_ms),
        "x-cold-start": "0",
        "x-translation-text": _encode_header_value(translation_text),
        "x-primary-model": str(primary_model),
        "x-fallback-model": str(fallback_model),
        "x-selected-model": str(selected_model),
        "x-model-fallback-reason": _encode_header_value(request.fallback_reason or ""),
        "x-pipeline-mode": "split",
    }
    return Response(content=output_bytes, media_type="application/octet-stream", headers=headers)


@internal_router.post("/page")
async def internal_translate_page(
    image: UploadFile = File(...),
    source_language: Optional[str] = Form(None),
    target_language: Optional[str] = Form(None),
    context_translations: Optional[str] = Form("[]"),
    primary_model: Optional[str] = Form(None),
    fallback_model: Optional[str] = Form(None),
    x_internal_token: Optional[str] = Header(None, alias=INTERNAL_TOKEN_HEADER),
):
    _verify_internal_token(x_internal_token)
    _ensure_internal_compute_ready()

    try:
        payload = await image.read()
        if not payload:
            raise HTTPException(status_code=400, detail="empty image payload")
        parsed_context = json.loads(context_translations or "[]")
        if not isinstance(parsed_context, list):
            parsed_context = []
    except HTTPException:
        raise
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=400, detail=f"invalid internal request: {exc}") from exc

    started_at = time.perf_counter()
    output_bytes, result = await _translate_payload_via_temp_files(
        payload,
        image_name=image.filename or "page.jpg",
        source_language=source_language,
        target_language=target_language,
        context_translations=_build_context_translations(parsed_context),
        primary_model=primary_model,
        fallback_model=fallback_model,
    )
    elapsed_ms = int((time.perf_counter() - started_at) * 1000.0)

    stage_elapsed = result.get("stage_elapsed_ms") or {}
    stage_elapsed_text = json.dumps(stage_elapsed, ensure_ascii=False)
    context_text = str(result.get("page_translation_text") or "").replace("\n", " ").strip()
    if len(context_text) > 1500:
        context_text = context_text[:1500]

    headers = {
        "x-regions-count": str(_to_non_negative_int(result.get("regions_count"), default=0)),
        "x-output-changed": "1" if bool(result.get("output_changed")) else "0",
        "x-fallback-used": "1" if bool(result.get("fallback_used")) else "0",
        "x-fallback-reason": _encode_header_value(result.get("fallback_reason") or ""),
        "x-no-change-reason": _encode_header_value(result.get("no_change_reason") or ""),
        "x-failure-stage": _encode_header_value(result.get("failure_stage") or ""),
        "x-stage-elapsed-ms": _encode_header_value(stage_elapsed_text),
        "x-remote-elapsed-ms": str(elapsed_ms),
        "x-cold-start": "0",
        "x-translation-text": _encode_header_value(context_text),
        "x-primary-model": str(result.get("primary_model") or ""),
        "x-fallback-model": str(result.get("fallback_model") or ""),
        "x-selected-model": str(result.get("selected_model") or ""),
        "x-model-fallback-reason": _encode_header_value(result.get("model_fallback_reason") or ""),
        "x-pipeline-mode": "unified",
    }
    return Response(content=output_bytes, media_type="application/octet-stream", headers=headers)


@router.get("/events")
async def translate_events(_session: Session = Depends(require_auth)):
    queue: asyncio.Queue[str] = asyncio.Queue(maxsize=256)
    v1_event_bus.add_listener(queue)

    async def stream():
        try:
            while True:
                message = await queue.get()
                yield message
        except asyncio.CancelledError:
            raise
        finally:
            v1_event_bus.remove_listener(queue)

    return StreamingResponse(stream(), media_type="text/event-stream")
