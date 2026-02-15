"""Shared helpers for scraper routes/services."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import aiohttp
from fastapi import HTTPException

from .models import ScraperDownloadRequest


def scraper_http_error(status_code: int, code: str, message: str) -> HTTPException:
    return HTTPException(status_code=status_code, detail={"code": code, "message": message})


def optional_text(value: object) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text or text.lower() == "none":
        return None
    return text


def map_upstream_client_error(exc: aiohttp.ClientResponseError, fallback_code: str) -> HTTPException:
    status = int(exc.status or 0)
    message = optional_text(exc.message) or f"HTTP {status}"
    if status in {401, 403}:
        return scraper_http_error(403, "SCRAPER_AUTH_CHALLENGE", message)
    if status == 404:
        return scraper_http_error(404, fallback_code, message)
    return scraper_http_error(500, fallback_code, message)


def safe_name(value: str, fallback: str = "item") -> str:
    cleaned = "".join(ch if ch.isalnum() or ch in {"-", "_"} else "-" for ch in (value or "").strip())
    cleaned = cleaned.strip("-")
    return cleaned or fallback


def normalize_catalog_path(path: str | None) -> str | None:
    if not path:
        return None
    normalized = path.strip()
    if not normalized:
        return None
    if not normalized.startswith("/"):
        normalized = f"/{normalized}"
    if not normalized.endswith("/"):
        normalized = f"{normalized}/"
    return normalized


def default_user_agent() -> str:
    return (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/123.0.0.0 Safari/537.36"
    )


def request_payload(req: ScraperDownloadRequest) -> dict[str, Any]:
    return {
        "base_url": req.base_url,
        "site_hint": req.site_hint,
        "manga": req.manga.model_dump(),
        "chapter": req.chapter.model_dump(),
        "concurrency": req.concurrency,
        "rate_limit_rps": req.rate_limit_rps,
    }


def infer_output_extension(image_url: str) -> str:
    ext = Path(image_url.split("?", 1)[0]).suffix.lower()
    return ext if ext in {".jpg", ".jpeg", ".png", ".webp"} else ".jpg"
