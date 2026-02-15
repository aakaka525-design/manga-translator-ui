"""Compatibility v1 scraper routes with provider registry and persistent tasks."""

from __future__ import annotations

import asyncio
import contextlib
import hashlib
import logging
import os
import re
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Awaitable, Callable, Optional
from urllib.parse import urlparse, urljoin
from uuid import uuid4

import aiohttp
from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile
from fastapi.responses import Response
from pydantic import BaseModel

from manga_translator.server.core.middleware import require_auth
from manga_translator.server.core.models import Session
from manga_translator.server.scraper_v1 import (
    BrowserUnavailableError,
    CloudflareChallengeError,
    CloudflareSolver,
    DEFAULT_ALERT_SETTINGS,
    ProviderContext,
    ProviderAdapter,
    ProviderUnavailableError,
    ScraperAlertEngine,
    ScraperTaskStore,
    get_cookie_store,
    get_state_info,
    get_http_client,
    merge_cookies,
    normalize_alert_settings,
    normalize_base_url,
    provider_allows_image_host,
    provider_auth_url,
    providers_payload,
    resolve_provider,
    save_state_payload,
    send_test_webhook,
)
from manga_translator.server.scraper_v1.download_service import DownloadService


router = APIRouter(prefix="/api/v1/scraper", tags=["v1-scraper"])

SERVER_DIR = Path(__file__).resolve().parents[1]
DATA_DIR = SERVER_DIR / "data"
RAW_DIR = DATA_DIR / "raw"
STATE_DIR = DATA_DIR / "state"
TASK_DB_PATH = DATA_DIR / "scraper_tasks.db"
TASKS_TTL_SEC = 3600
TASK_RETENTION_DAYS = 7
IDEMPOTENT_WINDOW_MINUTES = 30
TASK_MAX_RETRIES = 2
TASK_RETRY_DELAY_SEC = 15.0
STALE_TASK_MINUTES = 10
IMAGE_RETRY_DELAYS = (0.5, 1.0, 2.0)
RETRYABLE_HTTP_STATUS = {429, 500, 502, 503, 504}
ACTIVE_TASK_STATUSES = {"pending", "running", "retrying"}

_scraper_tasks: dict[str, dict[str, object]] = {}
_scraper_tasks_lock = asyncio.Lock()
_task_store: ScraperTaskStore | None = None
_download_service: DownloadService | None = None
_cf_solver: CloudflareSolver | None = None
_alert_scheduler_task: asyncio.Task | None = None
_alert_scheduler_lock = asyncio.Lock()
_alert_runtime: dict[str, Any] = {
    "running": False,
    "enabled": True,
    "poll_interval_sec": 30,
    "last_run_at": None,
    "last_error": None,
    "last_emitted": 0,
    "started_at": None,
    "stopped_at": None,
}
_UNSET = object()
logger = logging.getLogger(__name__)


class MangaPayload(BaseModel):
    id: str
    title: Optional[str] = None
    url: Optional[str] = None
    cover_url: Optional[str] = None


class ChapterPayload(BaseModel):
    id: str
    title: Optional[str] = None
    url: Optional[str] = None
    index: Optional[int] = None
    downloaded: bool = False
    downloaded_count: int = 0
    downloaded_total: int = 0


class ScraperBaseRequest(BaseModel):
    base_url: str
    http_mode: bool = True
    headless: bool = True
    manual_challenge: bool = False
    storage_state_path: Optional[str] = None
    user_data_dir: Optional[str] = None
    browser_channel: Optional[str] = None
    cookies: Optional[dict[str, str]] = None
    concurrency: int = 6
    rate_limit_rps: float = 2.0
    user_agent: Optional[str] = None
    site_hint: Optional[str] = None
    force_engine: Optional[str] = None


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


class ScraperStateInfoRequest(BaseModel):
    base_url: Optional[str] = None
    storage_state_path: Optional[str] = None


class ScraperAccessCheckRequest(BaseModel):
    base_url: str
    storage_state_path: Optional[str] = None
    path: Optional[str] = None
    site_hint: Optional[str] = None


class ScraperTaskStatus(BaseModel):
    task_id: str
    status: str
    message: Optional[str] = None
    report: Optional[dict[str, object]] = None
    persisted: Optional[bool] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None
    retry_count: Optional[int] = None
    max_retries: Optional[int] = None
    next_retry_at: Optional[str] = None
    error_code: Optional[str] = None
    last_error: Optional[str] = None
    queue_status: Optional[str] = None
    enqueued_at: Optional[str] = None
    dequeued_at: Optional[str] = None
    worker_id: Optional[str] = None
    progress_completed: Optional[int] = None
    progress_total: Optional[int] = None


class ScraperCatalogResponse(BaseModel):
    page: int
    has_more: bool
    items: list[MangaPayload]


class ScraperStateInfoResponse(BaseModel):
    status: str
    cookie_name: Optional[str] = None
    expires_at: Optional[float] = None
    expires_at_text: Optional[str] = None
    expires_in_sec: Optional[int] = None
    message: Optional[str] = None


class ScraperAccessCheckResponse(BaseModel):
    status: str
    http_status: Optional[int] = None
    message: Optional[str] = None


class ScraperUploadResponse(BaseModel):
    path: str
    status: str
    message: Optional[str] = None
    expires_at: Optional[float] = None
    expires_at_text: Optional[str] = None


class ScraperAuthUrlResponse(BaseModel):
    url: str


def init_task_store(db_path: Path | str | None = None) -> ScraperTaskStore:
    global _task_store, TASK_DB_PATH
    if db_path is not None:
        TASK_DB_PATH = Path(db_path)
    TASK_DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    _task_store = ScraperTaskStore(TASK_DB_PATH)
    return _task_store


def _get_task_store() -> ScraperTaskStore:
    global _task_store
    if _task_store is None:
        return init_task_store()
    return _task_store


def _get_download_service() -> DownloadService:
    global _download_service
    if _download_service is None:
        _download_service = DownloadService(
            raw_dir=RAW_DIR,
            http_client=get_http_client(default_user_agent=_default_user_agent()),
            set_task_state=_set_task_state,
            image_retry_delays=IMAGE_RETRY_DELAYS,
            task_retry_delay_sec=int(TASK_RETRY_DELAY_SEC),
            max_task_retries=TASK_MAX_RETRIES,
        )
    return _download_service


def _get_cf_solver() -> CloudflareSolver:
    global _cf_solver
    if _cf_solver is None:
        _cf_solver = CloudflareSolver(
            get_http_client(default_user_agent=_default_user_agent()),
            cookie_store=get_cookie_store(),
        )
    return _cf_solver


def _task_status_to_queue_status(status: str) -> str:
    normalized = (status or "").strip().lower()
    if normalized == "pending":
        return "queued"
    if normalized == "running":
        return "running"
    if normalized == "retrying":
        return "retrying"
    if normalized in {"success", "partial"}:
        return "done"
    if normalized == "error":
        return "failed"
    return normalized or "queued"


def _load_alert_settings() -> dict[str, Any]:
    settings = None
    try:
        from manga_translator.server.core.config_manager import admin_settings

        settings = admin_settings.get("scraper_alerts")
    except Exception:
        settings = None
    return normalize_alert_settings(settings or DEFAULT_ALERT_SETTINGS)


def get_alert_runtime_snapshot() -> dict[str, Any]:
    settings = _load_alert_settings()
    return {
        "running": bool(_alert_runtime.get("running", False)),
        "enabled": bool(settings.get("enabled", True)),
        "poll_interval_sec": int(settings.get("poll_interval_sec", 30)),
        "last_run_at": _alert_runtime.get("last_run_at"),
        "last_error": _alert_runtime.get("last_error"),
        "last_emitted": int(_alert_runtime.get("last_emitted", 0) or 0),
        "started_at": _alert_runtime.get("started_at"),
        "stopped_at": _alert_runtime.get("stopped_at"),
    }


def get_scraper_health_snapshot() -> dict[str, Any]:
    settings = _load_alert_settings()
    runtime = get_alert_runtime_snapshot()
    db_ok = True
    db_error: str | None = None
    try:
        _get_task_store().metrics(hours=1)
    except Exception as exc:  # noqa: BLE001
        db_ok = False
        db_error = str(exc)

    scheduler_expected = bool(settings.get("enabled", True))
    scheduler_running = bool(runtime.get("running", False))
    runtime_error = str(runtime.get("last_error") or "").strip() or None
    degraded = (not db_ok) or bool(runtime_error) or (scheduler_expected and not scheduler_running)
    status = "degraded" if degraded else "ok"

    return {
        "status": status,
        "db": {
            "path": str(TASK_DB_PATH),
            "available": db_ok,
            "error": db_error,
        },
        "scheduler": runtime,
        "alerts": {
            "enabled": bool(settings.get("enabled", True)),
            "cooldown_sec": int(settings.get("cooldown_sec", 300)),
            "webhook_enabled": bool((settings.get("webhook", {}) or {}).get("enabled", False)),
        },
        "time": _now_iso(),
    }


async def run_alert_cycle_once() -> list[dict[str, Any]]:
    store = _get_task_store()
    settings = _load_alert_settings()
    engine = ScraperAlertEngine(store, settings)
    _alert_runtime["enabled"] = bool(settings.get("enabled", True))
    _alert_runtime["poll_interval_sec"] = int(settings.get("poll_interval_sec", 30))

    if not engine.enabled():
        _alert_runtime["last_run_at"] = _now_iso()
        _alert_runtime["last_error"] = None
        _alert_runtime["last_emitted"] = 0
        return []

    try:
        records = await engine.run_once()
        _alert_runtime["last_run_at"] = _now_iso()
        _alert_runtime["last_error"] = None
        _alert_runtime["last_emitted"] = len(records)
        return [item.to_payload() for item in records]
    except Exception as exc:  # noqa: BLE001
        _alert_runtime["last_run_at"] = _now_iso()
        _alert_runtime["last_error"] = str(exc)
        _alert_runtime["last_emitted"] = 0
        return []


async def _alert_scheduler_loop() -> None:
    while True:
        await run_alert_cycle_once()
        interval = int(_alert_runtime.get("poll_interval_sec", 30) or 30)
        await asyncio.sleep(max(5, interval))


async def start_alert_scheduler() -> None:
    global _alert_scheduler_task
    async with _alert_scheduler_lock:
        settings = _load_alert_settings()
        _alert_runtime["enabled"] = bool(settings.get("enabled", True))
        _alert_runtime["poll_interval_sec"] = int(settings.get("poll_interval_sec", 30))
        _alert_runtime["last_error"] = None

        if not settings.get("enabled", True):
            _alert_runtime["running"] = False
            _alert_runtime["stopped_at"] = _now_iso()
            return

        if _alert_scheduler_task is not None and not _alert_scheduler_task.done():
            _alert_runtime["running"] = True
            return

        _alert_scheduler_task = asyncio.create_task(_alert_scheduler_loop())
        _alert_runtime["running"] = True
        _alert_runtime["started_at"] = _now_iso()
        _alert_runtime["stopped_at"] = None


async def stop_alert_scheduler() -> None:
    global _alert_scheduler_task
    async with _alert_scheduler_lock:
        task = _alert_scheduler_task
        _alert_scheduler_task = None
        if task is not None and not task.done():
            task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await task
        _alert_runtime["running"] = False
        _alert_runtime["stopped_at"] = _now_iso()


async def trigger_test_webhook(webhook_url: str | None = None) -> dict[str, Any]:
    settings = _load_alert_settings()
    webhook_cfg = settings.get("webhook", {}) or {}
    target = (webhook_url or webhook_cfg.get("url") or "").strip()
    if not target:
        raise ValueError("webhook url is not configured")
    result = await send_test_webhook(
        webhook_url=target,
        timeout_sec=int(webhook_cfg.get("timeout_sec", 5)),
        max_retries=int(webhook_cfg.get("max_retries", 3)),
    )
    return result


def _scraper_http_error(status_code: int, code: str, message: str) -> HTTPException:
    return HTTPException(status_code=status_code, detail={"code": code, "message": message})


def _optional_text(value: object | None) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    if text.lower() == "none":
        return None
    return text


def _map_upstream_client_error(exc: aiohttp.ClientResponseError, fallback_code: str) -> HTTPException:
    status = int(exc.status or 500)
    if status in {401, 403}:
        return _scraper_http_error(403, "SCRAPER_AUTH_CHALLENGE", str(exc))
    if status == 404:
        return _scraper_http_error(404, fallback_code, str(exc))
    return _scraper_http_error(500, fallback_code, str(exc))


def _safe_name(value: str, default: str = "item") -> str:
    cleaned = re.sub(r"[^\w\-]+", "_", value, flags=re.UNICODE).strip("_")
    return cleaned or default


def _normalize_catalog_path(value: Optional[str]) -> Optional[str]:
    if not value:
        return None
    trimmed = value.strip()
    if not trimmed:
        return None
    parsed = urlparse(trimmed)
    if parsed.scheme and parsed.netloc:
        return parsed.path or "/"
    if not trimmed.startswith("/"):
        return f"/{trimmed}"
    return trimmed


def _default_user_agent() -> str:
    return os.environ.get(
        "SCRAPER_DEFAULT_USER_AGENT",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_0) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    )


def _request_payload(model: BaseModel) -> dict[str, object]:
    if hasattr(model, "model_dump"):
        return model.model_dump()  # type: ignore[attr-defined]
    return model.dict()  # type: ignore[no-any-return]


def _merge_cookies(base_url: str, storage_state_path: str | None, extra: dict[str, str] | None) -> dict[str, str]:
    cookies: dict[str, str] = merge_cookies(base_url, storage_state_path, None)
    if extra:
        cookies.update(extra)
    return cookies


def _task_payload(task_id: str) -> dict[str, object]:
    return _scraper_tasks.get(task_id) or {
        "task_id": task_id,
        "status": "missing",
        "message": "任务不存在",
        "report": None,
        "retry_count": 0,
        "max_retries": TASK_MAX_RETRIES,
        "next_retry_at": None,
        "error_code": None,
        "last_error": None,
        "progress_completed": 0,
        "progress_total": 0,
    }


def _resolve_provider_or_error(base_url: str, site_hint: str | None) -> tuple[ProviderAdapter, str]:
    normalized_base = normalize_base_url(base_url)
    try:
        provider = resolve_provider(normalized_base, site_hint)
    except ProviderUnavailableError as exc:
        raise _scraper_http_error(400, "SCRAPER_PROVIDER_UNAVAILABLE", str(exc)) from exc
    return provider, normalized_base


def _validate_engine(force_engine: str | None) -> str | None:
    if not force_engine:
        return None
    value = force_engine.strip().lower()
    if value in {"http", "playwright"}:
        return value
    raise _scraper_http_error(400, "SCRAPER_PROVIDER_UNAVAILABLE", f"未知引擎: {force_engine}")


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _retry_eta_iso(delay_sec: float) -> str:
    return (datetime.now(timezone.utc) + timedelta(seconds=max(0.0, delay_sec))).isoformat()


def _request_fingerprint(
    *,
    base_url: str,
    provider_key: str,
    manga_id: str,
    chapter_id: str,
) -> str:
    payload = "|".join(
        [
            normalize_base_url(base_url).strip().lower(),
            provider_key.strip().lower(),
            (manga_id or "").strip().lower(),
            (chapter_id or "").strip().lower(),
        ]
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _is_call_signature_error(exc: TypeError) -> bool:
    text = str(exc)
    return any(
        marker in text
        for marker in (
            "required positional argument",
            "positional arguments but",
            "unexpected keyword argument",
        )
    )


async def _provider_search_compat(context: ProviderContext, provider: ProviderAdapter, keyword: str):
    try:
        return await provider.search(context, keyword)
    except TypeError as exc:
        if not _is_call_signature_error(exc):
            raise
        return await provider.search(
            context.base_url,
            keyword,
            context.cookies,
            context.user_agent,
            context.http_mode,
            context.force_engine,
        )


async def _provider_catalog_compat(
    context: ProviderContext,
    provider: ProviderAdapter,
    page: int,
    orderby: str | None,
    path: str | None,
):
    try:
        return await provider.catalog(context, page, orderby, path)
    except TypeError as exc:
        if not _is_call_signature_error(exc):
            raise
        return await provider.catalog(
            context.base_url,
            page,
            orderby,
            path,
            context.cookies,
            context.user_agent,
            context.http_mode,
            context.force_engine,
        )


async def _provider_chapters_compat(context: ProviderContext, provider: ProviderAdapter, manga_url: str):
    try:
        return await provider.chapters(context, manga_url)
    except TypeError as exc:
        if not _is_call_signature_error(exc):
            raise
        return await provider.chapters(
            context.base_url,
            manga_url,
            context.cookies,
            context.user_agent,
            context.http_mode,
            context.force_engine,
        )


async def _provider_reader_images_compat(context: ProviderContext, provider: ProviderAdapter, chapter_url: str):
    try:
        return await provider.reader_images(context, chapter_url)
    except TypeError as exc:
        if not _is_call_signature_error(exc):
            raise
        return await provider.reader_images(
            context.base_url,
            chapter_url,
            context.cookies,
            context.user_agent,
            context.http_mode,
            context.force_engine,
        )


async def _fetch_with_cf_solve(
    provider_fn: Callable[..., Awaitable[Any]],
    context: ProviderContext,
    target_url: str,
    *args: Any,
) -> Any:
    solve_target = target_url or context.base_url

    async def _retry_with_solver() -> Any:
        solver = _get_cf_solver()
        solved = await solver.solve(
            solve_target,
            current_cookies=context.cookies,
            user_agent=context.user_agent,
            referer=context.base_url,
        )
        merged_cookies = {**context.cookies, **(solved.cookies or {})}
        # CF cf_clearance is bound to both TLS fingerprint AND User-Agent.
        # When FlareSolverr returns a solved UA we must use it for the retry
        # so that Cloudflare accepts the cf_clearance cookie.
        retry_ua = solved.user_agent or context.user_agent
        # Bridge cookies into http_client's internal CF cache so that
        # subsequent fetch_binary calls (image proxy) can reuse them
        # without triggering a separate FlareSolverr solve per image.
        if solved.cookies:
            from ..scraper_v1.http_client import get_http_client
            get_http_client().inject_cf_cookies(
                solve_target, solved.cookies, solved.user_agent,
            )
        retry_ctx = replace(context, cookies=merged_cookies, user_agent=retry_ua)
        return await provider_fn(retry_ctx, *args)

    try:
        return await provider_fn(context, *args)
    except aiohttp.ClientResponseError as exc:
        if int(exc.status or 0) not in {401, 403}:
            raise
        return await _retry_with_solver()
    except CloudflareChallengeError:
        return await _retry_with_solver()


async def _set_task_state(
    task_id: str,
    *,
    status: str,
    message: str,
    report: dict[str, object] | None = None,
    error_code: str | None = None,
    finished: bool = False,
    retry_count: int | None = None,
    max_retries: int | None = None,
    next_retry_at: str | None | object = _UNSET,
    last_error: str | None | object = _UNSET,
    started_at: str | None | object = _UNSET,
    progress_completed: int | None = None,
    progress_total: int | None = None,
) -> None:
    now_iso = _now_iso()
    async with _scraper_tasks_lock:
        payload = _scraper_tasks.get(task_id) or {"task_id": task_id}
        payload["status"] = status
        payload["message"] = message
        payload["updated_at"] = now_iso
        if report is not None:
            payload["report"] = report
        if retry_count is not None:
            payload["retry_count"] = int(retry_count)
        if max_retries is not None:
            payload["max_retries"] = int(max_retries)
        if next_retry_at is not _UNSET:
            payload["next_retry_at"] = next_retry_at
        if last_error is not _UNSET:
            payload["last_error"] = last_error
        if started_at is not _UNSET:
            payload["started_at"] = started_at
        if progress_completed is not None:
            payload["progress_completed"] = max(0, int(progress_completed))
        if progress_total is not None:
            payload["progress_total"] = max(0, int(progress_total))
        if error_code is not None:
            payload["error_code"] = error_code
        if finished:
            payload["finished_at"] = now_iso
            payload["next_retry_at"] = None
        _scraper_tasks[task_id] = payload

    try:
        update_kwargs: dict[str, object] = {}
        if next_retry_at is not _UNSET:
            update_kwargs["next_retry_at"] = next_retry_at
        if last_error is not _UNSET:
            update_kwargs["last_error"] = last_error
        if started_at is not _UNSET:
            update_kwargs["started_at"] = started_at
        if progress_completed is not None:
            update_kwargs["progress_completed"] = max(0, int(progress_completed))
        if progress_total is not None:
            update_kwargs["progress_total"] = max(0, int(progress_total))

        store = _get_task_store()
        store.update_task(
            task_id,
            status=status,
            message=message,
            report=report,
            error_code=error_code,
            finished=finished,
            retry_count=retry_count,
            max_retries=max_retries,
            **update_kwargs,
        )
    except Exception as exc:  # noqa: BLE001
        logger.error("scraper task store update failed: task_id=%s status=%s error=%s", task_id, status, exc)


def recover_stale_tasks(stale_minutes: int = STALE_TASK_MINUTES) -> int:
    try:
        threshold = (datetime.now(timezone.utc) - timedelta(minutes=max(1, stale_minutes))).isoformat()
        return _get_task_store().mark_stale_tasks(
            stale_before=threshold,
            message="服务重启后检测到陈旧任务",
            error_code="SCRAPER_TASK_STALE",
            statuses=ACTIVE_TASK_STATUSES,
        )
    except Exception:
        return 0


async def _prune_tasks() -> None:
    if _scraper_tasks:
        now = asyncio.get_event_loop().time()
        stale: list[str] = []
        for task_id, payload in _scraper_tasks.items():
            created = float(payload.get("created_tick", 0) or 0)
            status = str(payload.get("status", ""))
            if status in {"success", "partial", "error"} and now - created > TASKS_TTL_SEC:
                stale.append(task_id)
        for task_id in stale:
            _scraper_tasks.pop(task_id, None)

    try:
        _get_task_store().prune_completed(days=TASK_RETENTION_DAYS)
    except Exception:
        pass


def _default_chapter_url(provider: ProviderAdapter, base_url: str, manga_id: str, chapter_id: str) -> str:
    if provider.key == "toongod":
        return urljoin(base_url, f"/webtoon/{manga_id}/{chapter_id}/")
    return urljoin(base_url, f"/manga/{manga_id}/{chapter_id}/")


async def _download_image(
    session: aiohttp.ClientSession,
    url: str,
    output_path: Path,
    *,
    referer: str,
    headers: dict[str, str],
) -> tuple[bool, str | None, bool]:
    req_headers = dict(headers)
    req_headers.setdefault("Referer", referer)
    delays = (0.0, *IMAGE_RETRY_DELAYS)
    last_error: str | None = None
    for attempt, delay in enumerate(delays):
        if delay > 0:
            await asyncio.sleep(delay)
        try:
            async with session.get(url, headers=req_headers) as response:
                if response.status >= 400:
                    last_error = f"HTTP {response.status}"
                    retryable = response.status in RETRYABLE_HTTP_STATUS
                    if retryable and attempt < len(delays) - 1:
                        continue
                    return False, last_error, retryable
                payload = await response.read()
                if not payload:
                    last_error = "empty payload"
                    if attempt < len(delays) - 1:
                        continue
                    return False, last_error, True
                output_path.write_bytes(payload)
                return True, None, False
        except (
            aiohttp.ClientConnectionError,
            aiohttp.ClientPayloadError,
            asyncio.TimeoutError,
            aiohttp.ServerTimeoutError,
        ) as exc:
            last_error = str(exc) or exc.__class__.__name__
            if attempt < len(delays) - 1:
                continue
            return False, last_error, True
        except Exception as exc:  # noqa: BLE001
            last_error = str(exc)
            return False, last_error, False
    return False, last_error or "下载失败", True


async def _run_download_task(
    task_id: str,
    req: ScraperDownloadRequest,
    provider: ProviderAdapter,
    base_url: str,
    cookies: dict[str, str],
    user_agent: str,
    force_engine: str | None,
    *,
    retry_count: int = 0,
    max_retries: int = TASK_MAX_RETRIES,
    request_fingerprint: str | None = None,
) -> None:
    await _set_task_state(
        task_id,
        status="running",
        message="下载中...",
        retry_count=retry_count,
        max_retries=max_retries,
        next_retry_at=None,
        started_at=_now_iso() if retry_count == 0 else _UNSET,
        progress_completed=0,
        progress_total=0,
    )

    manga_id = _safe_name(req.manga.id or req.manga.title or "manga")
    chapter_id = _safe_name(req.chapter.id or req.chapter.title or "chapter")
    chapter_url = req.chapter.url or _default_chapter_url(provider, base_url, req.manga.id, req.chapter.id)

    RAW_DIR.mkdir(parents=True, exist_ok=True)
    output_dir = RAW_DIR / manga_id / chapter_id
    output_dir.mkdir(parents=True, exist_ok=True)

    context = ProviderContext(
        base_url=base_url,
        cookies=cookies,
        user_agent=user_agent,
        http_mode=bool(req.http_mode),
        force_engine=force_engine,
        rate_limit_rps=float(req.rate_limit_rps or 2.0),
        concurrency=max(1, min(32, int(req.concurrency or 6))),
    )

    try:
        image_urls = await _fetch_with_cf_solve(
            _provider_reader_images_compat,
            context,
            chapter_url,
            provider,
            chapter_url,
        )
    except BrowserUnavailableError as exc:
        await _set_task_state(
            task_id,
            status="error",
            message=f"浏览器环境不可用: {exc}",
            report={"success_count": 0, "failed_count": 0, "total_count": 0},
            error_code="SCRAPER_BROWSER_UNAVAILABLE",
            finished=True,
            retry_count=retry_count,
            max_retries=max_retries,
            last_error=str(exc),
        )
        return
    except CloudflareChallengeError as exc:
        await _set_task_state(
            task_id,
            status="error",
            message=str(exc),
            report={"success_count": 0, "failed_count": 0, "total_count": 0},
            error_code="SCRAPER_AUTH_CHALLENGE",
            finished=True,
            retry_count=retry_count,
            max_retries=max_retries,
            last_error=str(exc),
        )
        return
    except Exception as exc:  # noqa: BLE001
        await _set_task_state(
            task_id,
            status="error",
            message=f"抓取失败: {exc}",
            report={"success_count": 0, "failed_count": 0, "total_count": 0},
            error_code="SCRAPER_DOWNLOAD_FAILED",
            finished=True,
            retry_count=retry_count,
            max_retries=max_retries,
            last_error=str(exc),
        )
        return

    if not image_urls:
        await _set_task_state(
            task_id,
            status="error",
            message="章节未返回可下载图片",
            report={"success_count": 0, "failed_count": 0, "total_count": 0},
            error_code="SCRAPER_IMAGE_EMPTY",
            finished=True,
            retry_count=retry_count,
            max_retries=max_retries,
            last_error="章节未返回可下载图片",
        )
        return

    timeout = aiohttp.ClientTimeout(total=30)
    headers = {"User-Agent": user_agent}
    connector = aiohttp.TCPConnector(limit=max(1, min(32, int(req.concurrency or 6))))

    async with aiohttp.ClientSession(timeout=timeout, cookies=cookies, connector=connector) as session:
        semaphore = asyncio.Semaphore(max(1, min(32, int(req.concurrency or 6))))
        results: list[tuple[bool, str | None, bool]] = []
        total_count = len(image_urls)

        async def worker(index: int, image_url: str) -> None:
            ext = Path(urlparse(image_url).path).suffix.lower()
            if ext not in {".jpg", ".jpeg", ".png", ".webp"}:
                ext = ".jpg"
            filename = f"{index:03d}{ext}"
            output_path = output_dir / filename
            async with semaphore:
                outcome = await _download_image(
                    session,
                    image_url,
                    output_path,
                    referer=chapter_url,
                    headers=headers,
                )
                if isinstance(outcome, tuple):
                    if len(outcome) == 3:
                        ok, error_text, retryable = outcome
                    elif len(outcome) == 2:
                        ok, error_text = outcome
                        retryable = not bool(ok)
                    else:
                        ok = bool(outcome[0]) if outcome else False
                        error_text = None
                        retryable = not ok
                else:
                    ok = bool(outcome)
                    error_text = None
                    retryable = not ok
                results.append((bool(ok), error_text, bool(retryable)))
                await _set_task_state(
                    task_id,
                    status="running",
                    message="下载中...",
                    progress_completed=len(results),
                    progress_total=total_count,
                )

        await asyncio.gather(*[worker(idx, image_url) for idx, image_url in enumerate(image_urls, start=1)])

    success_count = sum(1 for flag, _, _ in results if flag)
    failed_count = max(len(image_urls) - success_count, 0)

    retryable_failures = [entry for entry in results if (not entry[0] and entry[2])]
    failure_errors = [entry[1] for entry in results if (not entry[0] and entry[1])]
    last_error = failure_errors[-1] if failure_errors else None

    if success_count <= 0 and retry_count < max_retries and retryable_failures:
        next_retry_at = _retry_eta_iso(TASK_RETRY_DELAY_SEC)
        await _set_task_state(
            task_id,
            status="retrying",
            message=f"下载失败，准备重试 ({retry_count + 1}/{max_retries})",
            report={
                "success_count": success_count,
                "failed_count": failed_count,
                "total_count": len(image_urls),
                "output_dir": str(output_dir),
                "manga_id": manga_id,
                "chapter_id": chapter_id,
                "provider": provider.key,
            },
            retry_count=retry_count,
            max_retries=max_retries,
            next_retry_at=next_retry_at,
            last_error=last_error,
            progress_completed=len(image_urls),
            progress_total=len(image_urls),
        )

        async def _retry_later() -> None:
            await asyncio.sleep(TASK_RETRY_DELAY_SEC)
            await _run_download_task(
                task_id,
                req,
                provider,
                base_url,
                cookies,
                user_agent,
                force_engine,
                retry_count=retry_count + 1,
                max_retries=max_retries,
                request_fingerprint=request_fingerprint,
            )

        asyncio.create_task(_retry_later())
        return

    if success_count <= 0:
        status = "error"
        if retryable_failures and retry_count >= max_retries:
            error_code = "SCRAPER_RETRY_EXHAUSTED"
        else:
            error_code = "SCRAPER_DOWNLOAD_FAILED"
    elif failed_count > 0:
        status = "partial"
        error_code = None
    else:
        status = "success"
        error_code = None

    report = {
        "success_count": success_count,
        "failed_count": failed_count,
        "total_count": len(image_urls),
        "output_dir": str(output_dir),
        "manga_id": manga_id,
        "chapter_id": chapter_id,
        "provider": provider.key,
    }
    message = "下载完成" if status == "success" else "下载部分完成" if status == "partial" else "下载失败"
    await _set_task_state(
        task_id,
        status=status,
        message=message,
        report=report,
        finished=True,
        retry_count=retry_count,
        max_retries=max_retries,
        error_code=error_code,
        last_error=last_error,
        next_retry_at=None,
        progress_completed=len(image_urls),
        progress_total=len(image_urls),
    )


@router.get("/providers")
async def providers(_session: Session = Depends(require_auth)):
    return providers_payload()


@router.post("/search")
async def search(req: ScraperSearchRequest, _session: Session = Depends(require_auth)):
    provider, base_url = _resolve_provider_or_error(req.base_url, req.site_hint)
    force_engine = _validate_engine(req.force_engine)
    if force_engine == "playwright" and not provider.supports_playwright:
        raise _scraper_http_error(400, "SCRAPER_BROWSER_UNAVAILABLE", "当前 provider 不支持 playwright")

    cookies = _merge_cookies(base_url, req.storage_state_path, req.cookies)
    user_agent = req.user_agent or _default_user_agent()
    context = ProviderContext(
        base_url=base_url,
        cookies=cookies,
        user_agent=user_agent,
        http_mode=bool(req.http_mode),
        force_engine=force_engine,
        rate_limit_rps=float(req.rate_limit_rps or 2.0),
        concurrency=max(1, min(32, int(req.concurrency or 6))),
    )

    try:
        items = await _fetch_with_cf_solve(
            _provider_search_compat,
            context,
            base_url,
            provider,
            req.keyword,
        )
    except BrowserUnavailableError as exc:
        raise _scraper_http_error(400, "SCRAPER_BROWSER_UNAVAILABLE", str(exc)) from exc
    except CloudflareChallengeError as exc:
        raise _scraper_http_error(403, "SCRAPER_AUTH_CHALLENGE", str(exc)) from exc
    except aiohttp.ClientResponseError as exc:
        raise _map_upstream_client_error(exc, "SCRAPER_SEARCH_FAILED") from exc
    except Exception as exc:  # noqa: BLE001
        raise _scraper_http_error(500, "SCRAPER_SEARCH_FAILED", str(exc)) from exc

    return [item.__dict__ for item in items]


@router.post("/catalog", response_model=ScraperCatalogResponse)
async def catalog(req: ScraperCatalogRequest, _session: Session = Depends(require_auth)):
    provider, base_url = _resolve_provider_or_error(req.base_url, req.site_hint)
    force_engine = _validate_engine(req.force_engine)
    if force_engine == "playwright" and not provider.supports_playwright:
        raise _scraper_http_error(400, "SCRAPER_BROWSER_UNAVAILABLE", "当前 provider 不支持 playwright")

    cookies = _merge_cookies(base_url, req.storage_state_path, req.cookies)
    user_agent = req.user_agent or _default_user_agent()
    context = ProviderContext(
        base_url=base_url,
        cookies=cookies,
        user_agent=user_agent,
        http_mode=bool(req.http_mode),
        force_engine=force_engine,
        rate_limit_rps=float(req.rate_limit_rps or 2.0),
        concurrency=max(1, min(32, int(req.concurrency or 6))),
    )
    catalog_path = _normalize_catalog_path(req.path) or provider.default_catalog_path
    target_url = urljoin(base_url, catalog_path)

    try:
        items, has_more = await _fetch_with_cf_solve(
            _provider_catalog_compat,
            context,
            target_url,
            provider,
            max(1, req.page),
            req.orderby,
            catalog_path,
        )
    except BrowserUnavailableError as exc:
        raise _scraper_http_error(400, "SCRAPER_BROWSER_UNAVAILABLE", str(exc)) from exc
    except CloudflareChallengeError as exc:
        raise _scraper_http_error(403, "SCRAPER_AUTH_CHALLENGE", str(exc)) from exc
    except aiohttp.ClientResponseError as exc:
        raise _map_upstream_client_error(exc, "SCRAPER_CATALOG_FAILED") from exc
    except Exception as exc:  # noqa: BLE001
        raise _scraper_http_error(500, "SCRAPER_CATALOG_FAILED", str(exc)) from exc

    return ScraperCatalogResponse(page=max(1, req.page), has_more=has_more, items=[MangaPayload(**item.__dict__) for item in items])


@router.post("/chapters")
async def chapters(req: ScraperChaptersRequest, _session: Session = Depends(require_auth)):
    provider, base_url = _resolve_provider_or_error(req.base_url, req.site_hint)
    force_engine = _validate_engine(req.force_engine)
    if force_engine == "playwright" and not provider.supports_playwright:
        raise _scraper_http_error(400, "SCRAPER_BROWSER_UNAVAILABLE", "当前 provider 不支持 playwright")

    cookies = _merge_cookies(base_url, req.storage_state_path, req.cookies)
    user_agent = req.user_agent or _default_user_agent()
    context = ProviderContext(
        base_url=base_url,
        cookies=cookies,
        user_agent=user_agent,
        http_mode=bool(req.http_mode),
        force_engine=force_engine,
        rate_limit_rps=float(req.rate_limit_rps or 2.0),
        concurrency=max(1, min(32, int(req.concurrency or 6))),
    )

    fallback_path = provider.default_catalog_path.rstrip("/") or "/manga"
    manga_url = req.manga.url or urljoin(base_url, f"{fallback_path}/{req.manga.id}/")

    try:
        items = await _fetch_with_cf_solve(
            _provider_chapters_compat,
            context,
            manga_url,
            provider,
            manga_url,
        )
    except BrowserUnavailableError as exc:
        raise _scraper_http_error(400, "SCRAPER_BROWSER_UNAVAILABLE", str(exc)) from exc
    except CloudflareChallengeError as exc:
        raise _scraper_http_error(403, "SCRAPER_AUTH_CHALLENGE", str(exc)) from exc
    except aiohttp.ClientResponseError as exc:
        raise _map_upstream_client_error(exc, "SCRAPER_CHAPTERS_FAILED") from exc
    except Exception as exc:  # noqa: BLE001
        raise _scraper_http_error(500, "SCRAPER_CHAPTERS_FAILED", str(exc)) from exc

    manga_dir = RAW_DIR / _safe_name(req.manga.id)
    payload: list[dict[str, object]] = []
    for item in items:
        chapter_dir = manga_dir / _safe_name(item.id)
        downloaded_count = 0
        if chapter_dir.exists() and chapter_dir.is_dir():
            downloaded_count = sum(
                1
                for file_path in chapter_dir.iterdir()
                if file_path.is_file() and file_path.suffix.lower() in {".jpg", ".jpeg", ".png", ".webp"}
            )
        payload.append(
            {
                "id": item.id,
                "title": item.title,
                "url": item.url,
                "index": item.index,
                "downloaded": downloaded_count > 0,
                "downloaded_count": downloaded_count,
                "downloaded_total": downloaded_count,
            }
        )

    return payload


@router.post("/download")
async def download(req: ScraperDownloadRequest, _session: Session = Depends(require_auth)):
    provider, base_url = _resolve_provider_or_error(req.base_url, req.site_hint)
    force_engine = _validate_engine(req.force_engine)
    if force_engine == "playwright" and not provider.supports_playwright:
        raise _scraper_http_error(400, "SCRAPER_BROWSER_UNAVAILABLE", "当前 provider 不支持 playwright")

    request_fingerprint = _request_fingerprint(
        base_url=base_url,
        provider_key=provider.key,
        manga_id=req.manga.id,
        chapter_id=req.chapter.id,
    )

    try:
        existed = _get_task_store().find_active_by_fingerprint(
            request_fingerprint,
            within_minutes=IDEMPOTENT_WINDOW_MINUTES,
            statuses=ACTIVE_TASK_STATUSES,
        )
    except Exception as exc:  # noqa: BLE001
        raise _scraper_http_error(500, "SCRAPER_TASK_STORE_ERROR", str(exc)) from exc

    if existed is not None:
        return {
            "task_id": existed.task_id,
            "status": "existing",
            "message": "已存在下载任务",
            "error_code": "SCRAPER_TASK_DUPLICATE",
        }

    task_id = str(uuid4())
    created_iso = _now_iso()
    async with _scraper_tasks_lock:
        _scraper_tasks[task_id] = {
            "task_id": task_id,
            "status": "pending",
            "message": "已提交下载任务",
            "report": None,
            "provider": provider.key,
            "created_at": created_iso,
            "updated_at": created_iso,
            "created_tick": asyncio.get_event_loop().time(),
            "retry_count": 0,
            "max_retries": TASK_MAX_RETRIES,
            "next_retry_at": None,
            "error_code": None,
            "last_error": None,
            "progress_completed": 0,
            "progress_total": 0,
        }

    try:
        _get_task_store().create_task(
            task_id,
            status="pending",
            message="已提交下载任务",
            request_payload={**_request_payload(req), "normalized_base_url": base_url},
            provider=provider.key,
            retry_count=0,
            max_retries=TASK_MAX_RETRIES,
            progress_completed=0,
            progress_total=0,
            request_fingerprint=request_fingerprint,
        )
    except Exception as exc:  # noqa: BLE001
        async with _scraper_tasks_lock:
            _scraper_tasks.pop(task_id, None)
        raise _scraper_http_error(500, "SCRAPER_TASK_STORE_ERROR", str(exc)) from exc

    cookies = _merge_cookies(base_url, req.storage_state_path, req.cookies)
    user_agent = req.user_agent or _default_user_agent()
    asyncio.create_task(
        _run_download_task(
            task_id,
            req,
            provider,
            base_url,
            cookies,
            user_agent,
            force_engine,
            retry_count=0,
            max_retries=TASK_MAX_RETRIES,
            request_fingerprint=request_fingerprint,
        )
    )
    return {"task_id": task_id, "status": "pending", "message": "已提交下载任务"}


@router.get("/task/{task_id}", response_model=ScraperTaskStatus)
async def get_scraper_task(task_id: str, _session: Session = Depends(require_auth)):
    async with _scraper_tasks_lock:
        await _prune_tasks()
        task = _scraper_tasks.get(task_id)

    if task:
        status = _optional_text(task.get("status")) or "unknown"
        created_at = _optional_text(task.get("created_at"))
        started_at = _optional_text(task.get("started_at"))
        return ScraperTaskStatus(
            task_id=task_id,
            status=status,
            message=_optional_text(task.get("message")) or "",
            report=task.get("report") if isinstance(task.get("report"), dict) else None,
            persisted=True,
            created_at=created_at,
            updated_at=_optional_text(task.get("updated_at")),
            retry_count=int(task.get("retry_count", 0) or 0),
            max_retries=int(task.get("max_retries", TASK_MAX_RETRIES) or TASK_MAX_RETRIES),
            next_retry_at=_optional_text(task.get("next_retry_at")),
            error_code=_optional_text(task.get("error_code")),
            last_error=_optional_text(task.get("last_error")),
            queue_status=_task_status_to_queue_status(status),
            enqueued_at=created_at,
            dequeued_at=started_at,
            worker_id="local-worker",
            progress_completed=int(task.get("progress_completed", 0) or 0),
            progress_total=int(task.get("progress_total", 0) or 0),
        )

    try:
        record = _get_task_store().get_task(task_id)
    except Exception as exc:  # noqa: BLE001
        raise _scraper_http_error(500, "SCRAPER_TASK_STORE_ERROR", str(exc)) from exc

    if not record:
        raise _scraper_http_error(404, "SCRAPER_TASK_NOT_FOUND", "任务不存在")

    return ScraperTaskStatus(
        task_id=record.task_id,
        status=record.status,
        message=record.message,
        report=record.report,
        persisted=True,
        created_at=record.created_at,
        updated_at=record.updated_at,
        retry_count=record.retry_count,
        max_retries=record.max_retries,
        next_retry_at=record.next_retry_at,
        error_code=record.error_code,
        last_error=record.last_error,
        queue_status=_task_status_to_queue_status(record.status),
        enqueued_at=record.created_at,
        dequeued_at=record.started_at,
        worker_id="local-worker",
        progress_completed=int(getattr(record, "progress_completed", 0) or 0),
        progress_total=int(getattr(record, "progress_total", 0) or 0),
    )


@router.post("/state-info", response_model=ScraperStateInfoResponse)
async def state_info(req: ScraperStateInfoRequest, _session: Session = Depends(require_auth)):
    payload = get_state_info(req.base_url or "", req.storage_state_path)
    return ScraperStateInfoResponse(**payload)


@router.post("/access-check", response_model=ScraperAccessCheckResponse)
async def access_check(req: ScraperAccessCheckRequest, _session: Session = Depends(require_auth)):
    provider, base_url = _resolve_provider_or_error(req.base_url, req.site_hint)
    target_path = _normalize_catalog_path(req.path) or provider.default_catalog_path
    target_url = urljoin(base_url, target_path)
    cookies = _merge_cookies(base_url, req.storage_state_path, None)

    timeout = aiohttp.ClientTimeout(total=15)
    headers = {
        "User-Agent": _default_user_agent(),
        "Accept-Encoding": "gzip, deflate",
    }
    if cookies:
        headers["Cookie"] = "; ".join(f"{key}={value}" for key, value in cookies.items())

    try:
        async with aiohttp.ClientSession(timeout=timeout, cookies=cookies) as session:
            async with session.get(target_url, headers=headers) as response:
                if response.status == 403:
                    return ScraperAccessCheckResponse(status="forbidden", http_status=403, message="站点拒绝访问（403）")
                if response.status >= 400:
                    return ScraperAccessCheckResponse(
                        status="error",
                        http_status=response.status,
                        message=f"站点返回 HTTP {response.status}",
                    )

                try:
                    text = await response.text()
                except Exception as exc:  # noqa: BLE001
                    return ScraperAccessCheckResponse(status="error", http_status=response.status, message=str(exc))

                lowered = text.lower()
                if "just a moment" in lowered or ("cloudflare" in lowered and "attention required" in lowered):
                    return ScraperAccessCheckResponse(status="forbidden", http_status=403, message="触发站点验证")
                return ScraperAccessCheckResponse(status="ok", http_status=response.status, message="站点可访问")
    except Exception as exc:  # noqa: BLE001
        return ScraperAccessCheckResponse(status="error", http_status=None, message=str(exc))


@router.post("/upload-state", response_model=ScraperUploadResponse)
async def upload_state(
    base_url: str = Form(...),
    file: UploadFile = File(...),
    _session: Session = Depends(require_auth),
):
    if not file.filename.lower().endswith(".json"):
        raise _scraper_http_error(400, "SCRAPER_STATE_FILE_TYPE_INVALID", "仅支持上传 JSON 状态文件")

    payload = await file.read()
    try:
        out_path = save_state_payload(base_url, payload, STATE_DIR)
    except ValueError as exc:
        code = str(exc)
        if code == "file_too_large":
            raise _scraper_http_error(400, "SCRAPER_STATE_FILE_TOO_LARGE", "状态文件过大（最大 2MB）") from exc
        if code == "json_invalid":
            raise _scraper_http_error(400, "SCRAPER_STATE_JSON_INVALID", "状态文件不是有效 JSON") from exc
        if code == "cookie_missing":
            raise _scraper_http_error(400, "SCRAPER_STATE_COOKIE_MISSING", "状态文件中没有可用 cookie") from exc
        raise _scraper_http_error(400, "SCRAPER_STATE_UPLOAD_INVALID", "状态文件无效") from exc

    info = get_state_info(base_url, str(out_path))
    return ScraperUploadResponse(
        path=str(out_path),
        status="success",
        message="上传成功",
        expires_at=info.get("expires_at"),
        expires_at_text=info.get("expires_at_text"),
    )


@router.get("/auth-url", response_model=ScraperAuthUrlResponse)
async def auth_url(
    base_url: Optional[str] = Query(None),
    site_hint: Optional[str] = Query(None),
    _session: Session = Depends(require_auth),
):
    env_url = os.environ.get("SCRAPER_AUTH_URL")
    if env_url:
        return ScraperAuthUrlResponse(url=env_url)

    if base_url:
        provider, normalized_base = _resolve_provider_or_error(base_url, site_hint)
        return ScraperAuthUrlResponse(url=provider_auth_url(provider, normalized_base))

    hint = (site_hint or "").strip().lower()
    if hint == "toongod":
        return ScraperAuthUrlResponse(url="https://toongod.org")
    if hint == "mangaforfree":
        return ScraperAuthUrlResponse(url="https://mangaforfree.com")
    return ScraperAuthUrlResponse(url="https://mangaforfree.com")


@router.get("/image")
async def scraper_image(
    url: str = Query(...),
    base_url: str = Query(...),
    storage_state_path: Optional[str] = Query(None),
    user_agent: Optional[str] = Query(None),
    site_hint: Optional[str] = Query(None),
    _session: Session = Depends(require_auth),
):
    provider, normalized_base = _resolve_provider_or_error(base_url, site_hint)

    if not provider_allows_image_host(provider, url, normalized_base):
        raise _scraper_http_error(400, "SCRAPER_IMAGE_SOURCE_UNSUPPORTED", "封面来源不受支持")

    cookies = _merge_cookies(normalized_base, storage_state_path, None)
    headers = {
        "User-Agent": user_agent or _default_user_agent(),
        "Referer": normalized_base,
    }

    try:
        client = get_http_client(default_user_agent=headers["User-Agent"])
        image = await client.fetch_binary(
            url,
            cookies=cookies,
            user_agent=headers["User-Agent"],
            referer=normalized_base,
            timeout_sec=20,
        )
        if not image.payload:
            raise _scraper_http_error(403, "SCRAPER_IMAGE_FETCH_FORBIDDEN", "图片获取失败")
        return Response(content=image.payload, media_type=image.media_type or "image/jpeg")
    except HTTPException:
        raise
    except Exception as exc:  # noqa: BLE001
        raise _scraper_http_error(403, "SCRAPER_IMAGE_FETCH_FORBIDDEN", str(exc)) from exc
