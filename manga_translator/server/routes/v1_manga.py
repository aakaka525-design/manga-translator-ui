"""Compatibility v1 manga routes."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from manga_translator.server.core.library_service import LibraryService
from manga_translator.server.core.middleware import require_auth
from manga_translator.server.core.models import Session


router = APIRouter(prefix="/api/v1/manga", tags=["v1-manga"])
library_service = LibraryService()


@router.get("")
async def list_manga(_session: Session = Depends(require_auth)):
    return [item.__dict__ for item in library_service.list_manga()]


@router.get("/{manga_id}/chapters")
async def list_chapters(manga_id: str, _session: Session = Depends(require_auth)):
    try:
        chapters = library_service.list_chapters(manga_id)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return [item.__dict__ for item in chapters]


@router.get("/{manga_id}/chapter/{chapter_id}")
async def get_chapter(manga_id: str, chapter_id: str, _session: Session = Depends(require_auth)):
    try:
        return library_service.get_chapter(manga_id, chapter_id)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.delete("/{manga_id}")
async def delete_manga(manga_id: str, _session: Session = Depends(require_auth)):
    try:
        return library_service.delete_manga(manga_id)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.delete("/{manga_id}/chapter/{chapter_id}")
async def delete_chapter(manga_id: str, chapter_id: str, _session: Session = Depends(require_auth)):
    try:
        return library_service.delete_chapter(manga_id, chapter_id)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
