"""HTTP-first MangaForFree scraper helpers."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Optional
from urllib.parse import quote_plus, urljoin, urlparse

import aiohttp
from bs4 import BeautifulSoup


@dataclass(frozen=True)
class MangaItem:
    id: str
    title: str
    url: str
    cover_url: Optional[str] = None


@dataclass(frozen=True)
class ChapterItem:
    id: str
    title: str
    url: str
    index: int


class CloudflareChallengeError(RuntimeError):
    pass


def _infer_slug(url: str) -> str:
    parsed = urlparse(url)
    parts = [p for p in parsed.path.split("/") if p]
    return parts[-1] if parts else parsed.netloc


def _normalize_url(base_url: str, maybe_url: str) -> str:
    if not maybe_url:
        return maybe_url
    if maybe_url.startswith("//"):
        return f"https:{maybe_url}"
    return urljoin(base_url, maybe_url)


def _canonical_series_url(base_url: str, maybe_url: str, *, allowed_sections: tuple[str, ...]) -> Optional[str]:
    full_url = _normalize_url(base_url, maybe_url)
    parsed = urlparse(full_url)
    parts = [part for part in parsed.path.split("/") if part]
    if len(parts) != 2:
        return None

    section, slug = parts
    if section not in allowed_sections or not slug:
        return None

    return f"{parsed.scheme}://{parsed.netloc}/{section}/{slug}/"


def _looks_like_challenge(html: str) -> bool:
    sample = html.lower()
    indicators = ["cloudflare", "cf-challenge", "attention required", "just a moment"]
    return any(mark in sample for mark in indicators)


def _request_headers(user_agent: str) -> dict[str, str]:
    return {
        "User-Agent": user_agent,
        "Accept-Encoding": "gzip, deflate",
    }


async def _fetch_html(
    url: str,
    *,
    cookies: dict[str, str],
    headers: dict[str, str],
    timeout_sec: float = 25,
) -> str:
    timeout = aiohttp.ClientTimeout(total=timeout_sec)
    request_headers = {"Accept-Encoding": "gzip, deflate"}
    request_headers.update(headers)
    async with aiohttp.ClientSession(timeout=timeout, cookies=cookies) as session:
        async with session.get(url, headers=request_headers) as response:
            text = await response.text()
            if _looks_like_challenge(text):
                raise CloudflareChallengeError("检测到站点验证，请先上传可用状态文件")
            response.raise_for_status()
    return text


def _extract_ajax_config(html: str, base_url: str) -> Optional[tuple[str, str]]:
    soup = BeautifulSoup(html, "html.parser")
    holder = soup.select_one("#manga-chapters-holder[data-id]")
    if holder is None:
        return None

    manga_id = str(holder.get("data-id") or "").strip()
    if not manga_id:
        return None

    ajax_url = None
    match = re.search(r'"ajax_url"\s*:\s*"([^"]+)"', html)
    if match:
        ajax_url = _normalize_url(base_url, match.group(1))
    if not ajax_url:
        ajax_url = _normalize_url(base_url, "/wp-admin/admin-ajax.php")

    return ajax_url, manga_id


async def _fetch_chapters_via_ajax(
    ajax_url: str,
    manga_id: str,
    *,
    cookies: dict[str, str],
    headers: dict[str, str],
    referer: str,
    timeout_sec: float = 25,
) -> str:
    timeout = aiohttp.ClientTimeout(total=timeout_sec)
    request_headers = {"Accept-Encoding": "gzip, deflate", "Referer": referer}
    request_headers.update(headers)

    async with aiohttp.ClientSession(timeout=timeout, cookies=cookies) as session:
        async with session.post(
            ajax_url,
            headers=request_headers,
            data={"action": "manga_get_chapters", "manga": manga_id},
        ) as response:
            text = await response.text()
            if _looks_like_challenge(text):
                raise CloudflareChallengeError("检测到站点验证，请先上传可用状态文件")
            response.raise_for_status()
            return text


def _extract_cover(item, base_url: str) -> Optional[str]:
    # Prefer explicit image tags
    image = item.select_one("img")
    if image:
        for attr in ("src", "data-src", "data-original", "data-lazy-src", "data-srcset"):
            value = image.get(attr)
            if not value:
                continue
            if attr.endswith("srcset"):
                first = str(value).split(",")[-1].strip().split(" ")[0]
                if first:
                    return _normalize_url(base_url, first)
            else:
                return _normalize_url(base_url, str(value))

    style_node = item.select_one("[style*='background-image']")
    if style_node and style_node.has_attr("style"):
        match = re.search(r"url\((['\"]?)([^)\"']+)\1\)", str(style_node["style"]))
        if match:
            return _normalize_url(base_url, match.group(2))
    return None


def parse_search(html: str, base_url: str) -> list[MangaItem]:
    soup = BeautifulSoup(html, "html.parser")
    results: list[MangaItem] = []
    selectors = [".c-tabs-item__content", ".page-item-detail", "a[href*='/manga/']"]

    seen: set[str] = set()
    for selector in selectors:
        for item in soup.select(selector):
            link = item.get("href")
            if not link:
                anchor = item.select_one("a[href]")
                link = anchor.get("href") if anchor else None
            if not link:
                continue

            full_url = _canonical_series_url(base_url, str(link), allowed_sections=("manga",))
            if not full_url:
                continue
            manga_id = _infer_slug(full_url)
            if full_url in seen:
                continue

            title_node = item.select_one(".post-title, .h5 a, .manga-name")
            title = title_node.get_text(strip=True) if title_node else manga_id
            cover = _extract_cover(item, base_url)
            results.append(MangaItem(id=manga_id, title=title or manga_id, url=full_url, cover_url=cover))
            seen.add(full_url)

    return results


def parse_catalog_has_more(html: str) -> bool:
    soup = BeautifulSoup(html, "html.parser")
    selectors = [
        "a[rel='next']",
        "a.page-numbers.next",
        ".nav-links a.next",
        ".pagination a.next",
    ]
    return any(soup.select_one(selector) is not None for selector in selectors)


def parse_chapters(html: str, base_url: str) -> list[ChapterItem]:
    soup = BeautifulSoup(html, "html.parser")
    chapters: list[ChapterItem] = []

    links = soup.select("li.wp-manga-chapter a, .listing-chapters_wrap a")
    if not links:
        links = soup.select("a[href*='/chapter/'], a[href*='/manga/'][href*='chapter']")

    seen: set[str] = set()
    for idx, link in enumerate(links, start=1):
        href = link.get("href")
        if not href:
            continue
        full_url = _normalize_url(base_url, str(href))
        chapter_id = _infer_slug(full_url)
        if chapter_id in seen:
            continue
        title = link.get_text(strip=True) or chapter_id
        chapters.append(ChapterItem(id=chapter_id, title=title, url=full_url, index=idx))
        seen.add(chapter_id)

    # MangaForFree often renders latest chapter first; reverse so oldest->newest.
    chapters.reverse()
    return chapters


def parse_reader_images(html: str, base_url: str) -> list[str]:
    soup = BeautifulSoup(html, "html.parser")
    urls: list[str] = []
    seen: set[str] = set()
    for image in soup.select(".reading-content img, img.wp-manga-chapter-img, .reader-area img"):
        for attr in ("src", "data-src", "data-original", "data-lazy-src", "data-srcset"):
            value = image.get(attr)
            if not value:
                continue
            if attr.endswith("srcset"):
                value = str(value).split(",")[-1].strip().split(" ")[0]
            if not value:
                continue
            full_url = _normalize_url(base_url, str(value))
            if full_url.startswith("data:") or full_url in seen:
                continue
            seen.add(full_url)
            urls.append(full_url)
            break

    # Fallback: parse image urls embedded in scripts.
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
) -> list[MangaItem]:
    search_url = urljoin(base_url, f"/?s={quote_plus(keyword)}&post_type=wp-manga")
    html = await _fetch_html(search_url, cookies=cookies, headers=_request_headers(user_agent))
    results = parse_search(html, base_url)

    # fast path for slug-style query
    slug = re.sub(r"[^a-z0-9]+", "-", keyword.lower()).strip("-")
    if slug and not results:
        direct_url = urljoin(base_url, f"/manga/{slug}/")
        results.append(MangaItem(id=slug, title=keyword, url=direct_url, cover_url=None))

    if _looks_like_challenge(html) and not results:
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

    html = await _fetch_html(url, cookies=cookies, headers=_request_headers(user_agent))
    items = parse_search(html, base_url)
    has_more = parse_catalog_has_more(html)
    if _looks_like_challenge(html) and not items:
        raise CloudflareChallengeError("检测到站点验证，请先上传可用状态文件")
    return items, has_more


async def list_chapters(
    base_url: str,
    manga_url: str,
    *,
    cookies: dict[str, str],
    user_agent: str,
) -> list[ChapterItem]:
    headers = _request_headers(user_agent)
    html = await _fetch_html(manga_url, cookies=cookies, headers=headers)
    chapters = parse_chapters(html, base_url)
    if not chapters:
        config = _extract_ajax_config(html, base_url)
        if config:
            ajax_url, manga_id = config
            ajax_html = await _fetch_chapters_via_ajax(
                ajax_url,
                manga_id,
                cookies=cookies,
                headers=headers,
                referer=manga_url,
            )
            chapters = parse_chapters(ajax_html, base_url)

    if _looks_like_challenge(html) and not chapters:
        raise CloudflareChallengeError("检测到站点验证，请先上传可用状态文件")
    return chapters


async def fetch_reader_images(
    base_url: str,
    chapter_url: str,
    *,
    cookies: dict[str, str],
    user_agent: str,
) -> list[str]:
    html = await _fetch_html(chapter_url, cookies=cookies, headers=_request_headers(user_agent))
    images = parse_reader_images(html, base_url)
    if _looks_like_challenge(html) and not images:
        raise CloudflareChallengeError("检测到站点验证，请先上传可用状态文件")
    return images
