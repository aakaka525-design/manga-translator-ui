"""Compatibility v1 parser routes used by scraper UI."""

from __future__ import annotations

import asyncio
from urllib.parse import urlparse

from bs4 import BeautifulSoup
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from manga_translator.server.core.middleware import require_auth
from manga_translator.server.core.models import Session
from manga_translator.server.scraper_v1.http_client import ScraperHttpClient


router = APIRouter(prefix="/api/v1/parser", tags=["v1-parser"])


class ParseRequest(BaseModel):
    url: str
    mode: str = "http"


class ParserListResponse(BaseModel):
    page_type: str
    recognized: bool
    site: str | None
    downloadable: bool
    items: list[dict[str, object]]
    warnings: list[str]


def _fetch_html(url: str, mode: str = "http") -> str:
    mode = (mode or "http").strip().lower()
    if mode not in {"http", "playwright"}:
        raise HTTPException(status_code=400, detail="不支持的抓取模式")

    user_agent = (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_0) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
    )

    if mode == "http":
        client = ScraperHttpClient(default_user_agent=user_agent)
        try:
            return asyncio.run(client.fetch_html(url, user_agent=user_agent, timeout_sec=20.0))
        except Exception as exc:  # noqa: BLE001
            status = getattr(exc, "status", None)
            if isinstance(status, int) and status >= 400:
                raise HTTPException(status_code=400, detail=f"请求失败（{status}）") from exc
            raise HTTPException(status_code=400, detail=f"请求失败: {exc}") from exc

    try:
        from playwright.sync_api import sync_playwright
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(
            status_code=400,
            detail={"code": "SCRAPER_BROWSER_UNAVAILABLE", "message": str(exc)},
        ) from exc

    def _fetch_via_playwright() -> str:
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=True)
            context = browser.new_context(user_agent=user_agent)
            page = context.new_page()
            try:
                resp = page.goto(url, wait_until="domcontentloaded", timeout=20000)
                status_code = resp.status if resp else 0
                if status_code >= 400:
                    raise HTTPException(status_code=400, detail=f"请求失败（{status_code}）")
                return page.content()
            finally:
                page.close()
                context.close()
                browser.close()

    return _fetch_via_playwright()


def _recognize_site(url: str) -> tuple[str | None, str | None]:
    parsed = urlparse(url)
    host = (parsed.hostname or "").lower()
    if host.startswith("www."):
        host = host[4:]

    mapping = {
        "mangaforfree.com": "mangaforfree",
        "toongod.org": "toongod",
    }
    site = mapping.get(host)
    if not site:
        scheme = parsed.scheme or "https"
        base = f"{scheme}://{host}" if host else None
        return "generic", base

    scheme = parsed.scheme or "https"
    return site, f"{scheme}://{host}"


def _extract_list_items(html: str, base_url: str) -> list[dict[str, object]]:
    soup = BeautifulSoup(html, "html.parser")
    items: list[dict[str, object]] = []
    seen: set[str] = set()

    selectors = [
        ".c-tabs-item__content",
        ".page-item-detail",
        "a[href*='/manga/']",
        "a[href*='/webtoon/']",
        "a[href*='/comic/']",
        "a[href*='/series/']",
    ]
    markers = ("/manga/", "/webtoon/", "/comic/", "/series/")
    for selector in selectors:
        for node in soup.select(selector):
            link = node.get("href")
            if not link:
                anchor = node.select_one("a[href]")
                link = anchor.get("href") if anchor else None
            if not link:
                continue

            if link.startswith("//"):
                full_url = f"https:{link}"
            elif link.startswith("http://") or link.startswith("https://"):
                full_url = link
            else:
                full_url = f"{base_url.rstrip('/')}/{link.lstrip('/')}"

            if not any(marker in full_url for marker in markers):
                continue
            manga_id = [p for p in urlparse(full_url).path.split("/") if p][-1]
            if manga_id in seen:
                continue

            title_node = node.select_one(".post-title, .h5 a, .manga-name")
            title = title_node.get_text(strip=True) if title_node else manga_id

            cover = None
            image = node.select_one("img")
            if image:
                for attr in ("src", "data-src", "data-original", "data-lazy-src"):
                    value = image.get(attr)
                    if value:
                        if value.startswith("//"):
                            cover = f"https:{value}"
                        elif value.startswith("http://") or value.startswith("https://"):
                            cover = value
                        else:
                            cover = f"{base_url.rstrip('/')}/{value.lstrip('/')}"
                        break

            items.append({
                "id": manga_id,
                "title": title,
                "url": full_url,
                "cover_url": cover,
            })
            seen.add(manga_id)

    return items


def _extract_parse_result(html: str, url: str) -> dict:
    soup = BeautifulSoup(html, "html.parser")

    title = ""
    title_candidates = [
        soup.select_one("meta[property='og:title']"),
        soup.select_one("h1"),
        soup.select_one("title"),
    ]
    for node in title_candidates:
        if node is None:
            continue
        value = node.get("content") if node.name == "meta" else node.get_text(strip=True)
        if value:
            title = value
            break

    author = ""
    author_node = soup.select_one("meta[name='author'], .author-content a, .author")
    if author_node:
        author = author_node.get("content") if author_node.name == "meta" else author_node.get_text(strip=True)

    cover_url = ""
    cover_node = soup.select_one("meta[property='og:image'], .summary_image img, .tab-summary img")
    if cover_node:
        if cover_node.name == "meta":
            cover_url = cover_node.get("content") or ""
        else:
            cover_url = cover_node.get("src") or cover_node.get("data-src") or ""

    paragraphs: list[str] = []
    for node in soup.select("p"):
        text = node.get_text(" ", strip=True)
        if len(text) >= 10:
            paragraphs.append(text)
        if len(paragraphs) >= 40:
            break

    if not paragraphs:
        article = soup.select_one("article, main, .post-content, .entry-content")
        if article:
            text = article.get_text("\n", strip=True)
            paragraphs = [line.strip() for line in text.splitlines() if len(line.strip()) >= 10][:40]

    return {
        "url": url,
        "title": title,
        "author": author,
        "cover_url": cover_url,
        "paragraphs": paragraphs,
        "warnings": [],
    }


@router.post("/parse")
async def parse(payload: ParseRequest, _session: Session = Depends(require_auth)):
    html = await asyncio.to_thread(_fetch_html, payload.url, payload.mode)
    return _extract_parse_result(html, payload.url)


@router.post("/list", response_model=ParserListResponse)
async def list_parser(payload: ParseRequest, _session: Session = Depends(require_auth)):
    site, base_url = _recognize_site(payload.url)
    recognized = site in {"mangaforfree", "toongod"} and base_url is not None

    html = await asyncio.to_thread(_fetch_html, payload.url, payload.mode)
    items = _extract_list_items(html, base_url or f"{urlparse(payload.url).scheme}://{urlparse(payload.url).netloc}")

    warnings: list[str] = []
    if not recognized:
        warnings.append("Unsupported site; using generic parser")
    elif not items:
        warnings.append("Catalog fetch failed; using fallback parser")

    return ParserListResponse(
        page_type="list",
        recognized=recognized,
        site=site,
        downloadable=len(items) > 0,
        items=items,
        warnings=warnings,
    )
