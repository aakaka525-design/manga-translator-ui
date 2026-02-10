"""Compatibility v1 translation routes and SSE events."""

from __future__ import annotations

import asyncio
import io
import logging
import os
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


TRANSLATE_CONTEXT_TIMEOUT_SEC = _env_positive_int("MANGA_TRANSLATE_CONTEXT_TIMEOUT_SEC", 600)
TRANSLATE_MAX_ATTEMPTS = 1

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


def _to_non_negative_int(value: object, default: int = 0) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return default
    return parsed if parsed >= 0 else default


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


async def _build_translate_context(request: Request, config, payload: bytes):
    from manga_translator.server.request_extraction import get_ctx

    return await get_ctx(request, config, payload, "normal")


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


async def _translate_single_image(
    image_path: Path,
    output_path: Path,
    source_language: str | None,
    target_language: str | None,
) -> dict:
    payload = image_path.read_bytes()
    output_path.parent.mkdir(parents=True, exist_ok=True)

    try:
        from manga_translator.server.core.config_manager import load_default_config

        config = load_default_config()
        attempts = getattr(config.translator, "attempts", None)
        if not isinstance(attempts, int) or attempts <= 0:
            config.translator.attempts = TRANSLATE_MAX_ATTEMPTS
        if source_language:
            config.translator.skip_lang = None
        config.translator.target_lang = _resolve_target_language(target_language)

        fake_request = Request({"type": "http", "method": "POST", "path": "/api/v1/translate/page", "headers": []})
        ctx = await asyncio.wait_for(
            _build_translate_context(fake_request, config, payload),
            timeout=TRANSLATE_CONTEXT_TIMEOUT_SEC,
        )
        if not getattr(ctx, "result", None):
            raise RuntimeError("Translation produced no output image")

        prepared_result = _prepare_output_image(ctx.result, output_path)
        prepared_result.save(output_path)
        regions_count = len(getattr(ctx, "text_regions", []) or [])
        output_changed = _image_has_visible_changes(payload, output_path)
        no_change_reason = None
        if not output_changed:
            no_change_reason = "no_text_regions_detected" if regions_count == 0 else "output_matches_source"
        return {
            "output_path": str(output_path),
            "regions_count": regions_count,
            "output_changed": output_changed,
            "no_change_reason": no_change_reason,
            "fallback_used": False,
            "fallback_reason": None,
        }
    except Exception as exc:  # noqa: BLE001
        # Compatibility fallback for environments where full translator deps are unavailable.
        logger.exception("v1 translate fallback used for %s", image_path)
        fallback_reason = str(exc).strip() or exc.__class__.__name__
        output_path.write_bytes(payload)
        return {
            "output_path": str(output_path),
            "regions_count": 0,
            "output_changed": False,
            "no_change_reason": "fallback_copy",
            "fallback_used": True,
            "fallback_reason": fallback_reason,
        }


async def _process_chapter_job(request: ChapterTranslateRequest) -> None:
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

    await v1_event_bus.publish(
        {
            "type": "chapter_start",
            "manga_id": request.manga_id,
            "chapter_id": request.chapter_id,
            "total_pages": total,
        }
    )

    for image_path in images:
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
            result = await _translate_single_image(
                image_path,
                out_path,
                request.source_language,
                request.target_language,
            )
            fallback_used = bool(result.get("fallback_used"))
            output_changed = bool(result.get("output_changed", True))
            regions_count = _to_non_negative_int(result.get("regions_count"), default=0)
            has_regions = regions_count > 0
            if fallback_used or not output_changed or not has_regions:
                failed += 1
                _cleanup_translated_variants(request.manga_id, request.chapter_id, image_path.name)
                if fallback_used:
                    error_message = f"fallback used: {result.get('fallback_reason') or 'translation unavailable'}"
                elif not has_regions:
                    error_message = "no detected text regions"
                else:
                    error_message = (
                        "no visible changes: "
                        f"{result.get('no_change_reason') or 'unknown_no_change_reason'}"
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
                    }
                )
            else:
                success += 1
                await v1_event_bus.publish(
                    {
                        "type": "progress",
                        "task_id": task_id,
                        "manga_id": request.manga_id,
                        "chapter_id": request.chapter_id,
                        "image_name": image_path.name,
                        "stage": "complete",
                        "status": "completed",
                    }
                )
        except Exception as exc:  # noqa: BLE001
            failed += 1
            await v1_event_bus.publish(
                {
                    "type": "progress",
                    "task_id": task_id,
                    "manga_id": request.manga_id,
                    "chapter_id": request.chapter_id,
                    "image_name": image_path.name,
                    "stage": "failed",
                    "status": "failed",
                    "error_message": str(exc),
                }
            )

    if success <= 0:
        status = "error"
    elif failed > 0:
        status = "partial"
    else:
        status = "success"

    await v1_event_bus.publish(
        {
            "type": "chapter_complete",
            "manga_id": request.manga_id,
            "chapter_id": request.chapter_id,
            "status": status,
            "success_count": success,
            "failed_count": failed,
            "total_count": total,
        }
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
        }
    )

    return {
        "task_id": task_id,
        "status": "completed",
        "output_path": result["output_path"],
        "translated_url": translated_url,
        "output_changed": True,
        "regions_count": result["regions_count"],
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
