"""Generic scraper adapter for custom sites."""

from __future__ import annotations

import asyncio
import re
from urllib.parse import quote_plus, urljoin

from bs4 import BeautifulSoup

from .base import (
    canonical_series_url,
    extract_cover,
    infer_slug,
    looks_like_challenge,
    normalize_url,
    parse_catalog_has_more,
)
from .http_client import get_http_client
from .mangaforfree import ChapterItem, CloudflareChallengeError, MangaItem


class BrowserUnavailableError(RuntimeError):
    pass


def _fetch_html_playwright_sync(url: str, user_agent: str, timeout_ms: int = 25000) -> str:
    try:
        from playwright.sync_api import sync_playwright
    except Exception as exc:  # noqa: BLE001
        raise BrowserUnavailableError(str(exc)) from exc

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        context = browser.new_context(user_agent=user_agent)
        page = context.new_page()
        try:
            resp = page.goto(url, wait_until="domcontentloaded", timeout=timeout_ms)
            status = resp.status if resp else 0
            if status >= 400:
                raise RuntimeError(f"请求失败（{status}）")
            return page.content()
        finally:
            page.close()
            context.close()
            browser.close()


async def _fetch_html(
    url: str,
    *,
    cookies: dict[str, str],
    user_agent: str,
    http_mode: bool,
    force_engine: str | None,
    rate_limit_rps: float | None = None,
    concurrency: int | None = None,
) -> str:
    engine = (force_engine or "").strip().lower()
    use_playwright = engine == "playwright" or (engine == "" and not http_mode)
    if use_playwright:
        return await asyncio.to_thread(_fetch_html_playwright_sync, url, user_agent)

    client = get_http_client(default_user_agent=user_agent)
    html = await client.fetch_html(
        url,
        cookies=cookies,
        user_agent=user_agent,
        rate_limit_rps=rate_limit_rps,
        concurrency=concurrency,
    )
    if looks_like_challenge(html):
        raise CloudflareChallengeError("检测到站点验证，请先上传可用状态文件")
    return html


def _optional_limits_kwargs(
    *,
    rate_limit_rps: float | None = None,
    concurrency: int | None = None,
) -> dict[str, float | int]:
    kwargs: dict[str, float | int] = {}
    if rate_limit_rps is not None:
        kwargs["rate_limit_rps"] = rate_limit_rps
    if concurrency is not None:
        kwargs["concurrency"] = concurrency
    return kwargs


def parse_search(html: str, base_url: str) -> list[MangaItem]:
    soup = BeautifulSoup(html, "html.parser")
    selectors = [
        ".c-tabs-item__content",
        ".page-item-detail",
        "a[href*='/manga/']",
        "a[href*='/webtoon/']",
        "a[href*='/comic/']",
        "a[href*='/series/']",
    ]
    allowed_sections = ("manga", "webtoon", "comic", "series")
    seen: set[str] = set()
    items: list[MangaItem] = []

    for selector in selectors:
        for node in soup.select(selector):
            href = node.get("href")
            if not href:
                anchor = node.select_one("a[href]")
                href = anchor.get("href") if anchor else None
            if not href:
                continue
            url = canonical_series_url(base_url, str(href), allowed_sections=allowed_sections)
            if not url:
                continue
            manga_id = infer_slug(url)
            if url in seen:
                continue
            title_node = node.select_one(".post-title, .h5 a, .manga-name, h3, h2, .entry-title")
            title = title_node.get_text(strip=True) if title_node else manga_id
            items.append(MangaItem(id=manga_id, title=title or manga_id, url=url, cover_url=extract_cover(node, base_url)))
            seen.add(url)
    return items


def parse_chapters(html: str, base_url: str) -> list[ChapterItem]:
    soup = BeautifulSoup(html, "html.parser")
    selectors = [
        "li.wp-manga-chapter a",
        ".listing-chapters_wrap a",
        "a[href*='/chapter/']",
        "a[href*='chapter']",
    ]
    seen: set[str] = set()
    chapters: list[ChapterItem] = []
    index = 1
    for selector in selectors:
        for node in soup.select(selector):
            href = node.get("href")
            if not href:
                continue
            url = normalize_url(base_url, str(href))
            chapter_id = infer_slug(url)
            if chapter_id in seen:
                continue
            title = node.get_text(strip=True) or chapter_id
            chapters.append(ChapterItem(id=chapter_id, title=title, url=url, index=index))
            seen.add(chapter_id)
            index += 1
    chapters.reverse()
    return chapters


def parse_reader_images(html: str, base_url: str) -> list[str]:
    soup = BeautifulSoup(html, "html.parser")
    selectors = [
        ".reading-content img",
        "img.wp-manga-chapter-img",
        ".reader-area img",
        "article img",
        "main img",
    ]
    urls: list[str] = []
    seen: set[str] = set()
    for selector in selectors:
        for image in soup.select(selector):
            for attr in ("src", "data-src", "data-original", "data-lazy-src", "data-srcset"):
                value = image.get(attr)
                if not value:
                    continue
                if attr.endswith("srcset"):
                    value = str(value).split(",")[-1].strip().split(" ")[0]
                full_url = normalize_url(base_url, str(value))
                if full_url.startswith("data:") or full_url in seen:
                    continue
                seen.add(full_url)
                urls.append(full_url)
                break

    if not urls:
        for match in re.finditer(r'https?://[^"\'\s>]+\.(?:jpg|jpeg|png|webp)', html, flags=re.IGNORECASE):
            url = match.group(0)
            if url not in seen:
                seen.add(url)
                urls.append(url)
    return urls


async def search_manga(
    base_url: str,
    keyword: str,
    *,
    cookies: dict[str, str],
    user_agent: str,
    http_mode: bool = True,
    force_engine: str | None = None,
    rate_limit_rps: float | None = None,
    concurrency: int | None = None,
) -> list[MangaItem]:
    search_url = urljoin(base_url, f"/?s={quote_plus(keyword)}")
    limits_kwargs = _optional_limits_kwargs(rate_limit_rps=rate_limit_rps, concurrency=concurrency)
    html = await _fetch_html(
        search_url,
        cookies=cookies,
        user_agent=user_agent,
        http_mode=http_mode,
        force_engine=force_engine,
        **limits_kwargs,
    )
    items = parse_search(html, base_url)
    slug = re.sub(r"[^a-z0-9]+", "-", keyword.lower()).strip("-")
    if slug and not items:
        items.append(MangaItem(id=slug, title=keyword, url=urljoin(base_url, f"/manga/{slug}/"), cover_url=None))
    if looks_like_challenge(html) and not items:
        raise CloudflareChallengeError("检测到站点验证，请先上传可用状态文件")
    return items


async def list_catalog(
    base_url: str,
    *,
    page: int,
    orderby: str | None,
    path: str | None,
    cookies: dict[str, str],
    user_agent: str,
    http_mode: bool = True,
    force_engine: str | None = None,
    rate_limit_rps: float | None = None,
    concurrency: int | None = None,
) -> tuple[list[MangaItem], bool]:
    page = max(1, page)
    base_path = (path or "/manga/").strip()
    if not base_path.startswith("/"):
        base_path = f"/{base_path}"
    if not base_path.endswith("/"):
        base_path = f"{base_path}/"
    if page > 1:
        base_path = f"{base_path}page/{page}/"
    url = urljoin(base_url, base_path)
    if orderby:
        separator = "&" if "?" in url else "?"
        url = f"{url}{separator}m_orderby={quote_plus(orderby)}"

    limits_kwargs = _optional_limits_kwargs(rate_limit_rps=rate_limit_rps, concurrency=concurrency)
    html = await _fetch_html(
        url,
        cookies=cookies,
        user_agent=user_agent,
        http_mode=http_mode,
        force_engine=force_engine,
        **limits_kwargs,
    )
    items = parse_search(html, base_url)
    has_more = parse_catalog_has_more(html)
    if looks_like_challenge(html) and not items:
        raise CloudflareChallengeError("检测到站点验证，请先上传可用状态文件")
    return items, has_more


async def list_chapters(
    base_url: str,
    manga_url: str,
    *,
    cookies: dict[str, str],
    user_agent: str,
    http_mode: bool = True,
    force_engine: str | None = None,
    rate_limit_rps: float | None = None,
    concurrency: int | None = None,
) -> list[ChapterItem]:
    limits_kwargs = _optional_limits_kwargs(rate_limit_rps=rate_limit_rps, concurrency=concurrency)
    html = await _fetch_html(
        manga_url,
        cookies=cookies,
        user_agent=user_agent,
        http_mode=http_mode,
        force_engine=force_engine,
        **limits_kwargs,
    )
    chapters = parse_chapters(html, base_url)
    if looks_like_challenge(html) and not chapters:
        raise CloudflareChallengeError("检测到站点验证，请先上传可用状态文件")
    return chapters


async def fetch_reader_images(
    base_url: str,
    chapter_url: str,
    *,
    cookies: dict[str, str],
    user_agent: str,
    http_mode: bool = True,
    force_engine: str | None = None,
    rate_limit_rps: float | None = None,
    concurrency: int | None = None,
) -> list[str]:
    limits_kwargs = _optional_limits_kwargs(rate_limit_rps=rate_limit_rps, concurrency=concurrency)
    html = await _fetch_html(
        chapter_url,
        cookies=cookies,
        user_agent=user_agent,
        http_mode=http_mode,
        force_engine=force_engine,
        **limits_kwargs,
    )
    images = parse_reader_images(html, base_url)
    if looks_like_challenge(html) and not images:
        raise CloudflareChallengeError("检测到站点验证，请先上传可用状态文件")
    return images
