"""Shared scraper parsing helpers and provider context."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Optional
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup


@dataclass(frozen=True)
class ProviderContext:
    base_url: str
    cookies: dict[str, str]
    user_agent: str
    http_mode: bool
    force_engine: str | None
    rate_limit_rps: float = 2.0
    concurrency: int = 6


def infer_slug(url: str) -> str:
    parsed = urlparse(url)
    parts = [p for p in parsed.path.split("/") if p]
    return parts[-1] if parts else parsed.netloc


def normalize_url(base_url: str, maybe_url: str) -> str:
    if not maybe_url:
        return maybe_url
    if maybe_url.startswith("//"):
        return f"https:{maybe_url}"
    return urljoin(base_url, maybe_url)


def canonical_series_url(base_url: str, maybe_url: str, *, allowed_sections: tuple[str, ...]) -> Optional[str]:
    full_url = normalize_url(base_url, maybe_url)
    parsed = urlparse(full_url)
    parts = [part for part in parsed.path.split("/") if part]
    if len(parts) != 2:
        return None

    section, slug = parts
    if section not in allowed_sections or not slug:
        return None

    return f"{parsed.scheme}://{parsed.netloc}/{section}/{slug}/"


def looks_like_challenge(html: str) -> bool:
    """Detect Cloudflare challenge pages without false-positiving on real content.

    Real pages often contain "cloudflare" in CDN URLs (e.g. cdnjs.cloudflare.com),
    so we use more specific indicators. Pages > 50 KB are unlikely to be challenges
    but are still checked with a higher threshold (2+ indicators required).
    """
    if not html:
        return False
    sample = html.lower()
    # High-confidence CF challenge indicators (avoid bare "cloudflare")
    cf_indicators = (
        "just a moment",         # CF title: "Just a moment..." (various suffixes)
        "cf-challenge-running",
        "cf_challenge",
        "attention required",    # "Attention Required! | Cloudflare"
        "cf-please-wait",
        "challenge-form",
        "jschl_vc",
        "jschl-answer",
    )
    hits = sum(1 for mark in cf_indicators if mark in sample)
    # Large pages need 2+ indicators to avoid false positives from CDN refs;
    # small pages (typical challenges are 5-15 KB) need only 1.
    threshold = 2 if len(html) > 50_000 else 1
    return hits >= threshold


def parse_catalog_has_more(html: str) -> bool:
    soup = BeautifulSoup(html, "html.parser")
    selectors = (
        "a[rel='next']",
        "a.page-numbers.next",
        ".nav-links a.next",
        ".pagination a.next",
    )
    return any(soup.select_one(selector) is not None for selector in selectors)


def extract_ajax_config(html: str, base_url: str) -> Optional[tuple[str, str]]:
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
        ajax_url = normalize_url(base_url, match.group(1))
    if not ajax_url:
        ajax_url = normalize_url(base_url, "/wp-admin/admin-ajax.php")

    return ajax_url, manga_id


def extract_cover(node, base_url: str) -> str | None:
    image = node.select_one("img")
    if image:
        for attr in ("src", "data-src", "data-original", "data-lazy-src", "data-srcset"):
            value = image.get(attr)
            if not value:
                continue
            if attr.endswith("srcset"):
                value = str(value).split(",")[-1].strip().split(" ")[0]
            return normalize_url(base_url, str(value))

    style_node = node.select_one("[style*='background-image']")
    if style_node and style_node.has_attr("style"):
        match = re.search(r"url\((['\"]?)([^)\"']+)\1\)", str(style_node["style"]))
        if match:
            return normalize_url(base_url, match.group(2))
    return None


def parse_chapters(html: str, base_url: str):
    from .mangaforfree import ChapterItem

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
        full_url = normalize_url(base_url, str(href))
        chapter_id = infer_slug(full_url)
        if chapter_id in seen:
            continue
        title = link.get_text(strip=True) or chapter_id
        chapters.append(ChapterItem(id=chapter_id, title=title, url=full_url, index=idx))
        seen.add(chapter_id)

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
