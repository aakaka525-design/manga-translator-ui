"""HTTP-first ToonGod scraper helpers."""

from __future__ import annotations

import re
from urllib.parse import quote_plus, urljoin

from bs4 import BeautifulSoup

from .base import (
    canonical_series_url,
    extract_ajax_config,
    extract_cover,
    infer_slug,
    looks_like_challenge,
    normalize_url,
    parse_catalog_has_more,
    parse_chapters,
    parse_reader_images,
)
from .mangaforfree import (
    ChapterItem,
    CloudflareChallengeError,
    MangaItem,
    _optional_limits_kwargs,
    _fetch_chapters_via_ajax,
    _fetch_html,
    _request_headers,
)


def parse_search(html: str, base_url: str) -> list[MangaItem]:
    soup = BeautifulSoup(html, "html.parser")
    results: list[MangaItem] = []
    selectors = [".c-tabs-item__content", ".page-item-detail", "a[href*='/webtoon/']", "a[href*='/manga/']"]
    allowed_sections = ("webtoon", "manga")
    seen: set[str] = set()

    for selector in selectors:
        for item in soup.select(selector):
            link = item.get("href")
            if not link:
                anchor = item.select_one("a[href]")
                link = anchor.get("href") if anchor else None
            if not link:
                continue

            full_url = canonical_series_url(base_url, str(link), allowed_sections=allowed_sections)
            if not full_url:
                continue
            manga_id = infer_slug(full_url)
            if full_url in seen:
                continue

            title_node = item.select_one(".post-title, .h5 a, .manga-name")
            title = title_node.get_text(strip=True) if title_node else manga_id
            cover = extract_cover(item, base_url)
            results.append(MangaItem(id=manga_id, title=title or manga_id, url=full_url, cover_url=cover))
            seen.add(full_url)

    return results


async def search_manga(
    base_url: str,
    keyword: str,
    *,
    cookies: dict[str, str],
    user_agent: str,
    rate_limit_rps: float | None = None,
    concurrency: int | None = None,
) -> list[MangaItem]:
    search_paths = [
        f"/?s={quote_plus(keyword)}&post_type=webtoon",
        f"/?s={quote_plus(keyword)}&post_type=wp-manga",
        f"/?s={quote_plus(keyword)}",
    ]
    results: list[MangaItem] = []
    html = ""
    limits_kwargs = _optional_limits_kwargs(rate_limit_rps=rate_limit_rps, concurrency=concurrency)
    for path in search_paths:
        html = await _fetch_html(
            urljoin(base_url, path),
            cookies=cookies,
            headers=_request_headers(user_agent),
            **limits_kwargs,
        )
        results = parse_search(html, base_url)
        if results:
            break

    slug = re.sub(r"[^a-z0-9]+", "-", keyword.lower()).strip("-")
    if slug and not results:
        direct_url = urljoin(base_url, f"/webtoon/{slug}/")
        results.append(MangaItem(id=slug, title=keyword, url=direct_url, cover_url=None))

    if looks_like_challenge(html) and not results:
        raise CloudflareChallengeError("检测到站点验证，请先上传可用状态文件")
    return results


async def list_catalog(
    base_url: str,
    *,
    page: int,
    orderby: str | None,
    path: str | None,
    cookies: dict[str, str],
    user_agent: str,
    rate_limit_rps: float | None = None,
    concurrency: int | None = None,
) -> tuple[list[MangaItem], bool]:
    page = max(1, page)
    base_path = (path or "/webtoon/").strip()
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
        headers=_request_headers(user_agent),
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
    rate_limit_rps: float | None = None,
    concurrency: int | None = None,
) -> list[ChapterItem]:
    headers = _request_headers(user_agent)
    limits_kwargs = _optional_limits_kwargs(rate_limit_rps=rate_limit_rps, concurrency=concurrency)
    html = await _fetch_html(
        manga_url,
        cookies=cookies,
        headers=headers,
        **limits_kwargs,
    )
    chapters = parse_chapters(html, base_url)
    if not chapters:
        config = extract_ajax_config(html, base_url)
        if config:
            ajax_url, manga_id = config
            ajax_html = await _fetch_chapters_via_ajax(
                ajax_url,
                manga_id,
                cookies=cookies,
                headers=headers,
                referer=manga_url,
                **limits_kwargs,
            )
            chapters = parse_chapters(ajax_html, base_url)

    if looks_like_challenge(html) and not chapters:
        raise CloudflareChallengeError("检测到站点验证，请先上传可用状态文件")
    return chapters


async def fetch_reader_images(
    base_url: str,
    chapter_url: str,
    *,
    cookies: dict[str, str],
    user_agent: str,
    rate_limit_rps: float | None = None,
    concurrency: int | None = None,
) -> list[str]:
    limits_kwargs = _optional_limits_kwargs(rate_limit_rps=rate_limit_rps, concurrency=concurrency)
    html = await _fetch_html(
        chapter_url,
        cookies=cookies,
        headers=_request_headers(user_agent),
        **limits_kwargs,
    )
    images = parse_reader_images(html, base_url)
    if looks_like_challenge(html) and not images:
        raise CloudflareChallengeError("检测到站点验证，请先上传可用状态文件")
    return images
