"""Compatibility routes for frontend settings persistence."""

from __future__ import annotations

import json
import threading
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from manga_translator.server.core.middleware import require_auth
from manga_translator.server.core.models import Session


router = APIRouter(prefix="/api/v1/settings", tags=["v1-settings"])

SETTINGS_FILE = Path("manga_translator/server/data/user_settings.json")
_settings_lock = threading.Lock()

DEFAULT_USER_SETTINGS = {
    "ai_model": "zai-org/glm-4.7-flash",
    "source_language": "en",
    "target_language": "zh",
    "upscale_model": "realesrgan-x4plus-anime",
    "upscale_scale": 4,
    "upscale_enable": True,
}


class ModelUpdateRequest(BaseModel):
    model: str


class UpscaleUpdateRequest(BaseModel):
    model: str
    scale: int
    enabled: bool


def _ensure_data_dir() -> None:
    SETTINGS_FILE.parent.mkdir(parents=True, exist_ok=True)


def _load_all_settings() -> dict[str, dict]:
    if not SETTINGS_FILE.exists():
        return {}
    try:
        payload = json.loads(SETTINGS_FILE.read_text(encoding="utf-8"))
    except Exception:
        return {}
    if not isinstance(payload, dict):
        return {}
    return payload


def _atomic_save(all_settings: dict[str, dict]) -> None:
    _ensure_data_dir()
    temp_path = SETTINGS_FILE.with_suffix(".tmp")
    temp_path.write_text(
        json.dumps(all_settings, ensure_ascii=False, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    temp_path.replace(SETTINGS_FILE)


def _normalize_settings(raw: dict | None) -> dict:
    merged = dict(DEFAULT_USER_SETTINGS)
    if isinstance(raw, dict):
        merged.update(raw)

    merged["ai_model"] = str(merged.get("ai_model") or DEFAULT_USER_SETTINGS["ai_model"])
    merged["source_language"] = str(merged.get("source_language") or DEFAULT_USER_SETTINGS["source_language"])
    merged["target_language"] = str(merged.get("target_language") or DEFAULT_USER_SETTINGS["target_language"])
    merged["upscale_model"] = str(merged.get("upscale_model") or DEFAULT_USER_SETTINGS["upscale_model"])

    try:
        merged["upscale_scale"] = int(merged.get("upscale_scale", DEFAULT_USER_SETTINGS["upscale_scale"]))
    except (TypeError, ValueError):
        merged["upscale_scale"] = DEFAULT_USER_SETTINGS["upscale_scale"]
    merged["upscale_enable"] = bool(merged.get("upscale_enable", DEFAULT_USER_SETTINGS["upscale_enable"]))
    return merged


def _get_user_settings(username: str) -> dict:
    with _settings_lock:
        all_settings = _load_all_settings()
        user_settings = _normalize_settings(all_settings.get(username))
        all_settings[username] = user_settings
        _atomic_save(all_settings)
    return user_settings


def _update_user_settings(username: str, updates: dict) -> dict:
    with _settings_lock:
        all_settings = _load_all_settings()
        current = _normalize_settings(all_settings.get(username))
        current.update(updates)
        current = _normalize_settings(current)
        all_settings[username] = current
        _atomic_save(all_settings)
    return current


@router.get("")
async def get_settings(session: Session = Depends(require_auth)):
    return _get_user_settings(session.username)


@router.post("/model")
async def update_model(payload: ModelUpdateRequest, session: Session = Depends(require_auth)):
    model = (payload.model or "").strip()
    if not model:
        raise HTTPException(status_code=422, detail="model is required")
    _update_user_settings(session.username, {"ai_model": model})
    return {"success": True}


@router.post("/upscale")
async def update_upscale(payload: UpscaleUpdateRequest, session: Session = Depends(require_auth)):
    model = (payload.model or "").strip()
    if not model:
        raise HTTPException(status_code=422, detail="model is required")
    _update_user_settings(
        session.username,
        {
            "upscale_model": model,
            "upscale_scale": int(payload.scale),
            "upscale_enable": bool(payload.enabled),
        },
    )
    return {"success": True}
