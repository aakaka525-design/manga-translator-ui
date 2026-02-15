"""Pydantic models for scraper routes."""

from __future__ import annotations

from typing import Any, Optional

from pydantic import BaseModel


class MangaPayload(BaseModel):
    id: str
    title: str
    url: Optional[str] = None


class ChapterPayload(BaseModel):
    id: str
    title: str
    url: Optional[str] = None


class ScraperBaseRequest(BaseModel):
    base_url: str
    storage_state_path: Optional[str] = None
    cookies: Optional[dict[str, str]] = None
    user_agent: Optional[str] = None
    http_mode: bool = True
    force_engine: Optional[str] = None
    site_hint: Optional[str] = None


class ScraperSearchRequest(ScraperBaseRequest):
    keyword: str


class ScraperCatalogRequest(ScraperBaseRequest):
    page: int = 1
    orderby: Optional[str] = None
    path: Optional[str] = None


class ScraperChaptersRequest(ScraperBaseRequest):
    manga: MangaPayload


class ScraperDownloadRequest(ScraperBaseRequest):
    manga: MangaPayload
    chapter: ChapterPayload
    concurrency: int = 6
    rate_limit_rps: float = 2.0


class ScraperStateInfoRequest(BaseModel):
    base_url: str
    storage_state_path: Optional[str] = None


class ScraperAccessCheckRequest(ScraperBaseRequest):
    sample_url: Optional[str] = None


class ScraperTaskStatus(BaseModel):
    task_id: str
    status: str
    message: str
    report: Optional[dict[str, Any]] = None
    persisted: bool = True
    created_at: Optional[str] = None
    updated_at: Optional[str] = None
    retry_count: int = 0
    max_retries: int = 2
    next_retry_at: Optional[str] = None
    error_code: Optional[str] = None
    last_error: Optional[str] = None
    queue_status: Optional[str] = None
    enqueued_at: Optional[str] = None
    dequeued_at: Optional[str] = None
    worker_id: Optional[str] = None


class ScraperCatalogResponse(BaseModel):
    page: int
    has_more: bool
    items: list[MangaPayload]


class ScraperStateInfoResponse(BaseModel):
    status: str
    message: str
    cookie_name: Optional[str] = None
    expires_at: Optional[float] = None
    expires_at_text: Optional[str] = None
    expires_in_sec: Optional[int] = None


class ScraperAccessCheckResponse(BaseModel):
    status: str
    message: str
    http_status: Optional[int] = None
    detail: Optional[str] = None


class ScraperUploadResponse(BaseModel):
    status: str
    message: str
    storage_state_path: Optional[str] = None


class ScraperAuthUrlResponse(BaseModel):
    url: str
