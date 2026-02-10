"""Compatibility v1 translation routes and SSE events."""

from __future__ import annotations

import asyncio
import io
import logging
import os
import time
import uuid
from pathlib import Path
from typing import Optional
from urllib.parse import quote

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from PIL import Image, ImageChops
from pydantic import BaseModel
from starlette.requests import Request

from manga_translator.server.core.library_service import LibraryService, IMAGE_EXTENSIONS
from manga_translator.server.core.middleware import require_auth
from manga_translator.server.core.models import Session
from manga_translator.server.core.v1_event_bus import v1_event_bus


router = APIRouter(prefix="/api/v1/translate", tags=["v1-translate"])
library_service = LibraryService()
logger = logging.getLogger(__name__)


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


# CLI-compatible default: no hard timeout unless explicitly configured.
TRANSLATE_CONTEXT_TIMEOUT_SEC = _env_non_negative_int("MANGA_TRANSLATE_CONTEXT_TIMEOUT_SEC", 0)
CHAPTER_PAGE_CONCURRENCY_DEFAULT = 3
CHAPTER_EXECUTION_MODE_CHOICES = {"single_page", "batch_pipeline", "auto"}
RUNTIME_PROFILE_CHOICES = {"off", "basic"}

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


async def _translate_single_image(
    image_path: Path,
    output_path: Path,
    source_language: str | None,
    target_language: str | None,
    cleanup_reason: str | None = "single_request_complete",
    cleanup_force: bool = False,
) -> dict:
    started_at = time.perf_counter()
    stage_elapsed_ms = _empty_stage_timing()
    failure_stage = "context"
    payload = image_path.read_bytes()
    output_path.parent.mkdir(parents=True, exist_ok=True)

    try:
        from manga_translator.server.core.config_manager import load_default_config

        config = load_default_config()
        config.translator.attempts = _resolve_translate_attempts(config)
        if source_language:
            config.translator.skip_lang = None
        config.translator.target_lang = _resolve_target_language(target_language)

        fake_request = Request({"type": "http", "method": "POST", "path": "/api/v1/translate/page", "headers": []})
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
        if not getattr(ctx, "result", None):
            raise RuntimeError("Translation produced no output image")

        failure_stage = "render"
        render_started_at = time.perf_counter()
        prepared_result = _prepare_output_image(ctx.result, output_path)
        prepared_result.save(output_path)
        stage_elapsed_ms["render"] = (time.perf_counter() - render_started_at) * 1000.0
        regions_count = len(getattr(ctx, "text_regions", []) or [])
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
        }
    except Exception as exc:  # noqa: BLE001
        # Compatibility fallback for environments where full translator deps are unavailable.
        logger.exception("v1 translate fallback used for %s", image_path)
        fallback_reason = str(exc).strip() or exc.__class__.__name__
        output_path.write_bytes(payload)
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
        }


def _build_runtime_snapshot(execution_mode: str, page_concurrency: int, translator_name: str | None) -> dict:
    use_gpu = False
    try:
        from manga_translator.server.core.task_manager import get_server_config

        use_gpu = bool(get_server_config().get("use_gpu", False))
    except Exception:  # noqa: BLE001
        pass

    return {
        "use_gpu": use_gpu,
        "execution_mode": execution_mode,
        "page_concurrency": page_concurrency,
        "translator": translator_name or "unknown",
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

    try:
        from manga_translator.server.core.config_manager import load_default_config
        from manga_translator.server.core.task_manager import cleanup_context
        from manga_translator.server.request_extraction import get_batch_ctx

        config = load_default_config()
        config.translator.attempts = _resolve_translate_attempts(config)
        if request.source_language:
            config.translator.skip_lang = None
        config.translator.target_lang = _resolve_target_language(request.target_language)

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
        contexts = await _await_translate_context(
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
                    },
                    exc,
                )
            )

    return outputs


async def _publish_page_result(
    request: ChapterTranslateRequest,
    image_path: Path,
    task_id: str,
    result: dict | None,
    error: Exception | None,
    pipeline: str,
) -> bool:
    stage_elapsed = dict(result.get("stage_elapsed_ms") or {}) if result else {}
    if error is not None:
        _cleanup_translated_variants(request.manga_id, request.chapter_id, image_path.name)
        await v1_event_bus.publish(
            {
                "type": "progress",
                "task_id": task_id,
                "manga_id": request.manga_id,
                "chapter_id": request.chapter_id,
                "image_name": image_path.name,
                "stage": "failed",
                "status": "failed",
                "error_message": str(error),
                "pipeline": pipeline,
                "failure_stage": "translate",
                "stage_elapsed_ms": stage_elapsed,
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
                "pipeline": pipeline,
                "failure_stage": "translate",
                "stage_elapsed_ms": stage_elapsed,
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
                "pipeline": pipeline,
                "failure_stage": failure_stage,
                "stage_elapsed_ms": stage_elapsed,
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
            "pipeline": pipeline,
            "stage_elapsed_ms": stage_elapsed,
        }
    )
    return True


async def _process_chapter_job(request: ChapterTranslateRequest) -> None:
    chapter_started_at = time.perf_counter()
    runtime_profile = _resolve_runtime_profile()

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
    page_concurrency = _resolve_chapter_page_concurrency(execution_mode, translator_name)
    runtime = _build_runtime_snapshot(execution_mode, page_concurrency, translator_name)

    await v1_event_bus.publish(
        {
            "type": "chapter_start",
            "manga_id": request.manga_id,
            "chapter_id": request.chapter_id,
            "total_pages": total,
            "page_concurrency": page_concurrency,
            "pipeline": execution_mode,
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
            )
            if page_success:
                success += 1
            else:
                failed += 1
    else:
        semaphore = asyncio.Semaphore(page_concurrency)

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
                    result = await _translate_single_image(
                        image_path,
                        out_path,
                        request.source_language,
                        request.target_language,
                    )
                return image_path, task_id, result, None
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
            "execution_mode": execution_mode,
            "pipeline": execution_mode,
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

    asyncio.create_task(_process_chapter_job(request))
    return {
        "message": "Chapter translation started",
        "page_count": len(images),
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
        }
    )

    return {
        "task_id": task_id,
        "status": "completed",
        "output_path": result["output_path"],
        "translated_url": translated_url,
        "output_changed": True,
        "regions_count": result["regions_count"],
        "stage_elapsed_ms": result.get("stage_elapsed_ms") or {},
    }


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
