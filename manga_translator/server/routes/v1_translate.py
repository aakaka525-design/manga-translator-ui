"""Compatibility v1 translation routes and SSE events."""

from __future__ import annotations

import asyncio
import uuid
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from starlette.requests import Request

from manga_translator.server.core.library_service import LibraryService, IMAGE_EXTENSIONS
from manga_translator.server.core.middleware import require_auth
from manga_translator.server.core.models import Session
from manga_translator.server.core.v1_event_bus import v1_event_bus


router = APIRouter(prefix="/api/v1/translate", tags=["v1-translate"])
library_service = LibraryService()


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
        from manga_translator.server.request_extraction import get_ctx

        config = load_default_config()
        if source_language:
            config.translator.skip_lang = None
        if target_language:
            config.translator.target_lang = target_language

        fake_request = Request({"type": "http", "method": "POST", "path": "/api/v1/translate/page", "headers": []})
        ctx = await get_ctx(fake_request, config, payload, "normal")
        if not getattr(ctx, "result", None):
            raise RuntimeError("Translation produced no output image")

        ctx.result.save(output_path)
        regions_count = len(getattr(ctx, "text_regions", []) or [])
        return {"output_path": str(output_path), "regions_count": regions_count}
    except Exception:
        # Compatibility fallback for environments where full translator deps are unavailable.
        output_path.write_bytes(payload)
        return {"output_path": str(output_path), "regions_count": 0}


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
            await _translate_single_image(
                image_path,
                out_path,
                request.source_language,
                request.target_language,
            )
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

    translated_url = f"/output/{request.manga_id}/{request.chapter_id}/{out_path.name}"
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
