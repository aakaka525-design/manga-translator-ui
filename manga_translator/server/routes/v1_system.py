"""Compatibility v1 system routes."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from manga_translator.server.core.logging_manager import global_log_queue, task_logs_lock
from manga_translator.server.core.middleware import require_admin
from manga_translator.server.core.models import Session


router = APIRouter(prefix="/api/v1/system", tags=["v1-system"])


@router.get("/logs")
async def get_system_logs(
    lines: int = Query(200, ge=1, le=1000),
    _session: Session = Depends(require_admin),
) -> list[str]:
    with task_logs_lock:
        entries = list(global_log_queue)[-lines:]

    formatted: list[str] = []
    for entry in entries:
        timestamp = str(entry.get("timestamp") or "")
        level = str(entry.get("level") or "INFO")
        message = str(entry.get("message") or "")
        formatted.append(f"[{timestamp}] [{level}] {message}")
    return formatted
