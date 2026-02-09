"""Compatibility v1 scraper routes (MangaForFree first)."""

from __future__ import annotations

import asyncio
import os
import re
from pathlib import Path
from typing import Optional
from urllib.parse import urlparse, urljoin
from uuid import uuid4

import aiohttp
from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile
from fastapi.responses import Response
from pydantic import BaseModel

from manga_translator.server.core.middleware import require_auth
from manga_translator.server.core.models import Session
from manga_translator.server.scraper_v1 import (
    CloudflareChallengeError,
    collect_cookies,
    fetch_reader_images,
    get_state_info,
    list_catalog,
    list_chapters,
    load_state_payload,
    normalize_base_url,
    save_state_payload,
    search_manga,
)


router = APIRouter(prefix="/api/v1/scraper", tags=["v1-scraper"])

SERVER_DIR = Path(__file__).resolve().parents[1]
DATA_DIR = SERVER_DIR / "data"
RAW_DIR = DATA_DIR / "raw"
STATE_DIR = DATA_DIR / "state"
TASKS_TTL_SEC = 3600

_scraper_tasks: dict[str, dict[str, object]] = {}
_scraper_tasks_lock = asyncio.Lock()


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


class ScraperTaskStatus(BaseModel):
    task_id: str
    status: str
    message: Optional[str] = None
    report: Optional[dict[str, object]] = None


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


def _scraper_http_error(status_code: int, code: str, message: str) -> HTTPException:
    return HTTPException(status_code=status_code, detail={"code": code, "message": message})


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


def _supported_site(base_url: str) -> bool:
    host = (urlparse(normalize_base_url(base_url)).hostname or "").lower()
    return host == "mangaforfree.com" or host.endswith(".mangaforfree.com")


def _default_user_agent() -> str:
    return os.environ.get(
        "SCRAPER_DEFAULT_USER_AGENT",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_0) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    )


def _merge_cookies(base_url: str, storage_state_path: str | None, extra: dict[str, str] | None) -> dict[str, str]:
    cookies: dict[str, str] = {}
    if storage_state_path:
        path = Path(storage_state_path)
        if path.exists() and path.is_file():
            try:
                payload = load_state_payload(path)
                host = (urlparse(normalize_base_url(base_url)).hostname or "").lower()
                for item in collect_cookies(payload, host or None):
                    cookies[item.name] = item.value
            except Exception:
                pass
    if extra:
        cookies.update(extra)
    return cookies


def _task_payload(task_id: str) -> dict[str, object]:
    return _scraper_tasks.get(task_id) or {"task_id": task_id, "status": "missing", "message": "任务不存在", "report": None}


async def _prune_tasks() -> None:
    if not _scraper_tasks:
        return
    now = asyncio.get_event_loop().time()
    stale: list[str] = []
    for task_id, payload in _scraper_tasks.items():
        created = float(payload.get("created_at", 0) or 0)
        status = str(payload.get("status", ""))
        if status in {"success", "partial", "error"} and now - created > TASKS_TTL_SEC:
            stale.append(task_id)
    for task_id in stale:
        _scraper_tasks.pop(task_id, None)


async def _download_image(
    session: aiohttp.ClientSession,
    url: str,
    output_path: Path,
    *,
    referer: str,
    headers: dict[str, str],
) -> bool:
    req_headers = dict(headers)
    req_headers.setdefault("Referer", referer)
    try:
        async with session.get(url, headers=req_headers) as response:
            if response.status >= 400:
                return False
            payload = await response.read()
            if not payload:
                return False
            output_path.write_bytes(payload)
            return True
    except Exception:
        return False


async def _run_download_task(task_id: str, req: ScraperDownloadRequest) -> None:
    payload = _task_payload(task_id)
    payload.update({"status": "running", "message": "下载中..."})

    base_url = normalize_base_url(req.base_url)
    manga_id = _safe_name(req.manga.id or req.manga.title or "manga")
    chapter_id = _safe_name(req.chapter.id or req.chapter.title or "chapter")
    chapter_url = req.chapter.url or urljoin(base_url, f"/manga/{req.manga.id}/{req.chapter.id}/")

    cookies = _merge_cookies(base_url, req.storage_state_path, req.cookies)
    user_agent = req.user_agent or _default_user_agent()

    RAW_DIR.mkdir(parents=True, exist_ok=True)
    output_dir = RAW_DIR / manga_id / chapter_id
    output_dir.mkdir(parents=True, exist_ok=True)

    try:
        image_urls = await fetch_reader_images(
            base_url,
            chapter_url,
            cookies=cookies,
            user_agent=user_agent,
        )
    except CloudflareChallengeError as exc:
        payload.update({"status": "error", "message": str(exc), "report": {"success_count": 0, "failed_count": 0, "total_count": 0}})
        return
    except Exception as exc:  # noqa: BLE001
        payload.update({"status": "error", "message": f"抓取失败: {exc}", "report": {"success_count": 0, "failed_count": 0, "total_count": 0}})
        return

    if not image_urls:
        payload.update(
            {
                "status": "error",
                "message": "章节未返回可下载图片",
                "report": {"success_count": 0, "failed_count": 0, "total_count": 0},
            }
        )
        return

    timeout = aiohttp.ClientTimeout(total=30)
    headers = {"User-Agent": user_agent}
    connector = aiohttp.TCPConnector(limit=max(1, min(32, int(req.concurrency or 6))))

    async with aiohttp.ClientSession(timeout=timeout, cookies=cookies, connector=connector) as session:
        semaphore = asyncio.Semaphore(max(1, min(32, int(req.concurrency or 6))))
        results: list[bool] = []

        async def worker(index: int, image_url: str) -> None:
            ext = Path(urlparse(image_url).path).suffix.lower()
            if ext not in {".jpg", ".jpeg", ".png", ".webp"}:
                ext = ".jpg"
            filename = f"{index:03d}{ext}"
            output_path = output_dir / filename
            async with semaphore:
                ok = await _download_image(
                    session,
                    image_url,
                    output_path,
                    referer=chapter_url,
                    headers=headers,
                )
                results.append(ok)

        await asyncio.gather(*[worker(idx, image_url) for idx, image_url in enumerate(image_urls, start=1)])

    success_count = sum(1 for flag in results if flag)
    failed_count = max(len(image_urls) - success_count, 0)
    if success_count <= 0:
        status = "error"
    elif failed_count > 0:
        status = "partial"
    else:
        status = "success"

    payload.update(
        {
            "status": status,
            "message": "下载完成" if status == "success" else "下载部分完成" if status == "partial" else "下载失败",
            "report": {
                "success_count": success_count,
                "failed_count": failed_count,
                "total_count": len(image_urls),
                "output_dir": str(output_dir),
                "manga_id": manga_id,
                "chapter_id": chapter_id,
            },
        }
    )


@router.post("/search")
async def search(req: ScraperSearchRequest, _session: Session = Depends(require_auth)):
    base_url = normalize_base_url(req.base_url)
    if not _supported_site(base_url):
        raise _scraper_http_error(400, "SCRAPER_SITE_UNSUPPORTED", "当前仅支持 MangaForFree")

    cookies = _merge_cookies(base_url, req.storage_state_path, req.cookies)
    user_agent = req.user_agent or _default_user_agent()

    try:
        items = await search_manga(base_url, req.keyword, cookies=cookies, user_agent=user_agent)
    except CloudflareChallengeError as exc:
        raise _scraper_http_error(403, "SCRAPER_AUTH_CHALLENGE", str(exc)) from exc
    except Exception as exc:  # noqa: BLE001
        raise _scraper_http_error(500, "SCRAPER_SEARCH_FAILED", str(exc)) from exc

    return [item.__dict__ for item in items]


@router.post("/catalog", response_model=ScraperCatalogResponse)
async def catalog(req: ScraperCatalogRequest, _session: Session = Depends(require_auth)):
    base_url = normalize_base_url(req.base_url)
    if not _supported_site(base_url):
        raise _scraper_http_error(400, "SCRAPER_SITE_UNSUPPORTED", "当前仅支持 MangaForFree")

    cookies = _merge_cookies(base_url, req.storage_state_path, req.cookies)
    user_agent = req.user_agent or _default_user_agent()

    try:
        items, has_more = await list_catalog(
            base_url,
            page=req.page,
            orderby=req.orderby,
            path=_normalize_catalog_path(req.path),
            cookies=cookies,
            user_agent=user_agent,
        )
    except CloudflareChallengeError as exc:
        raise _scraper_http_error(403, "SCRAPER_AUTH_CHALLENGE", str(exc)) from exc
    except Exception as exc:  # noqa: BLE001
        raise _scraper_http_error(500, "SCRAPER_CATALOG_FAILED", str(exc)) from exc

    return ScraperCatalogResponse(page=max(1, req.page), has_more=has_more, items=[MangaPayload(**item.__dict__) for item in items])


@router.post("/chapters")
async def chapters(req: ScraperChaptersRequest, _session: Session = Depends(require_auth)):
    base_url = normalize_base_url(req.base_url)
    if not _supported_site(base_url):
        raise _scraper_http_error(400, "SCRAPER_SITE_UNSUPPORTED", "当前仅支持 MangaForFree")

    cookies = _merge_cookies(base_url, req.storage_state_path, req.cookies)
    user_agent = req.user_agent or _default_user_agent()

    manga_url = req.manga.url or urljoin(base_url, f"/manga/{req.manga.id}/")
    try:
        items = await list_chapters(base_url, manga_url, cookies=cookies, user_agent=user_agent)
    except CloudflareChallengeError as exc:
        raise _scraper_http_error(403, "SCRAPER_AUTH_CHALLENGE", str(exc)) from exc
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
    base_url = normalize_base_url(req.base_url)
    if not _supported_site(base_url):
        raise _scraper_http_error(400, "SCRAPER_SITE_UNSUPPORTED", "当前仅支持 MangaForFree")

    task_id = str(uuid4())
    async with _scraper_tasks_lock:
        _scraper_tasks[task_id] = {
            "task_id": task_id,
            "status": "pending",
            "message": "已提交下载任务",
            "report": None,
            "created_at": asyncio.get_event_loop().time(),
        }

    asyncio.create_task(_run_download_task(task_id, req))
    return {"task_id": task_id, "status": "pending", "message": "已提交下载任务"}


@router.get("/task/{task_id}", response_model=ScraperTaskStatus)
async def get_scraper_task(task_id: str, _session: Session = Depends(require_auth)):
    async with _scraper_tasks_lock:
        await _prune_tasks()
        task = _scraper_tasks.get(task_id)

    if not task:
        raise _scraper_http_error(404, "SCRAPER_TASK_NOT_FOUND", "任务不存在")

    return ScraperTaskStatus(
        task_id=task_id,
        status=str(task.get("status", "unknown")),
        message=str(task.get("message", "")),
        report=task.get("report") if isinstance(task.get("report"), dict) else None,
    )


@router.post("/state-info", response_model=ScraperStateInfoResponse)
async def state_info(req: ScraperStateInfoRequest, _session: Session = Depends(require_auth)):
    payload = get_state_info(req.base_url or "", req.storage_state_path)
    return ScraperStateInfoResponse(**payload)


@router.post("/access-check", response_model=ScraperAccessCheckResponse)
async def access_check(req: ScraperAccessCheckRequest, _session: Session = Depends(require_auth)):
    base_url = normalize_base_url(req.base_url)
    if not _supported_site(base_url):
        raise _scraper_http_error(400, "SCRAPER_SITE_UNSUPPORTED", "当前仅支持 MangaForFree")

    target_path = _normalize_catalog_path(req.path) or "/manga/"
    target_url = urljoin(base_url, target_path)
    cookies = _merge_cookies(base_url, req.storage_state_path, None)

    timeout = aiohttp.ClientTimeout(total=15)
    headers = {"User-Agent": _default_user_agent()}
    if cookies:
        headers["Cookie"] = "; ".join(f"{key}={value}" for key, value in cookies.items())

    try:
        async with aiohttp.ClientSession(timeout=timeout, cookies=cookies) as session:
            async with session.get(target_url, headers=headers) as response:
                text = await response.text()
                if response.status == 403:
                    return ScraperAccessCheckResponse(status="forbidden", http_status=403, message="站点拒绝访问（403）")
                if response.status >= 400:
                    return ScraperAccessCheckResponse(
                        status="error",
                        http_status=response.status,
                        message=f"站点返回 HTTP {response.status}",
                    )
                if "cloudflare" in text.lower() and "just a moment" in text.lower():
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
async def auth_url(_session: Session = Depends(require_auth)):
    url = os.environ.get("SCRAPER_AUTH_URL") or "https://mangaforfree.com"
    return ScraperAuthUrlResponse(url=url)


def _is_allowed_image_host(target_url: str, base_url: str) -> bool:
    parsed = urlparse(target_url)
    host = (parsed.hostname or "").lower()
    if not host:
        return False

    allowlist = {"mangaforfree.com", "i0.wp.com", "i1.wp.com", "i2.wp.com"}
    base_host = (urlparse(base_url).hostname or "").lower()
    if base_host:
        allowlist.add(base_host)

    return any(host == domain or host.endswith(f".{domain}") for domain in allowlist)


@router.get("/image")
async def scraper_image(
    url: str = Query(...),
    base_url: str = Query(...),
    storage_state_path: Optional[str] = Query(None),
    user_agent: Optional[str] = Query(None),
    _session: Session = Depends(require_auth),
):
    normalized_base = normalize_base_url(base_url)
    if not _supported_site(normalized_base):
        raise _scraper_http_error(400, "SCRAPER_SITE_UNSUPPORTED", "当前仅支持 MangaForFree")

    if not _is_allowed_image_host(url, normalized_base):
        raise _scraper_http_error(400, "SCRAPER_IMAGE_SOURCE_UNSUPPORTED", "封面来源不受支持")

    cookies = _merge_cookies(normalized_base, storage_state_path, None)
    headers = {
        "User-Agent": user_agent or _default_user_agent(),
        "Referer": normalized_base,
    }

    timeout = aiohttp.ClientTimeout(total=20)
    try:
        async with aiohttp.ClientSession(timeout=timeout, cookies=cookies) as session:
            async with session.get(url, headers=headers) as response:
                if response.status >= 400:
                    raise _scraper_http_error(403, "SCRAPER_IMAGE_FETCH_FORBIDDEN", "图片获取失败")
                body = await response.read()
                media_type = response.headers.get("content-type") or "image/jpeg"
                return Response(content=body, media_type=media_type)
    except HTTPException:
        raise
    except Exception as exc:  # noqa: BLE001
        raise _scraper_http_error(403, "SCRAPER_IMAGE_FETCH_FORBIDDEN", str(exc)) from exc
