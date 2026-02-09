"""Provider registry for scraper v1."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Awaitable, Callable
from urllib.parse import urlparse

from . import generic, mangaforfree, toongod
from .mangaforfree import ChapterItem, MangaItem
from .state import normalize_base_url


class ProviderUnavailableError(ValueError):
    pass


BrowserUnavailableError = generic.BrowserUnavailableError


SearchFn = Callable[[str, str, dict[str, str], str, bool, str | None], Awaitable[list[MangaItem]]]
CatalogFn = Callable[
    [str, int, str | None, str | None, dict[str, str], str, bool, str | None],
    Awaitable[tuple[list[MangaItem], bool]],
]
ChaptersFn = Callable[[str, str, dict[str, str], str, bool, str | None], Awaitable[list[ChapterItem]]]
ReaderImagesFn = Callable[[str, str, dict[str, str], str, bool, str | None], Awaitable[list[str]]]


@dataclass(frozen=True)
class ProviderAdapter:
    key: str
    label: str
    hosts: tuple[str, ...]
    supports_http: bool
    supports_playwright: bool
    supports_custom_host: bool
    default_catalog_path: str
    search: SearchFn
    catalog: CatalogFn
    chapters: ChaptersFn
    reader_images: ReaderImagesFn
    auth_url: str


def _host_match(host: str, expected: str) -> bool:
    return host == expected or host.endswith(f".{expected}")


async def _mff_search(
    base_url: str,
    keyword: str,
    cookies: dict[str, str],
    user_agent: str,
    _http_mode: bool,
    _force_engine: str | None,
) -> list[MangaItem]:
    return await mangaforfree.search_manga(base_url, keyword, cookies=cookies, user_agent=user_agent)


async def _mff_catalog(
    base_url: str,
    page: int,
    orderby: str | None,
    path: str | None,
    cookies: dict[str, str],
    user_agent: str,
    _http_mode: bool,
    _force_engine: str | None,
) -> tuple[list[MangaItem], bool]:
    return await mangaforfree.list_catalog(
        base_url,
        page=page,
        orderby=orderby,
        path=path,
        cookies=cookies,
        user_agent=user_agent,
    )


async def _mff_chapters(
    base_url: str,
    manga_url: str,
    cookies: dict[str, str],
    user_agent: str,
    _http_mode: bool,
    _force_engine: str | None,
) -> list[ChapterItem]:
    return await mangaforfree.list_chapters(base_url, manga_url, cookies=cookies, user_agent=user_agent)


async def _mff_reader_images(
    base_url: str,
    chapter_url: str,
    cookies: dict[str, str],
    user_agent: str,
    _http_mode: bool,
    _force_engine: str | None,
) -> list[str]:
    return await mangaforfree.fetch_reader_images(base_url, chapter_url, cookies=cookies, user_agent=user_agent)


async def _toongod_search(
    base_url: str,
    keyword: str,
    cookies: dict[str, str],
    user_agent: str,
    _http_mode: bool,
    _force_engine: str | None,
) -> list[MangaItem]:
    return await toongod.search_manga(base_url, keyword, cookies=cookies, user_agent=user_agent)


async def _toongod_catalog(
    base_url: str,
    page: int,
    orderby: str | None,
    path: str | None,
    cookies: dict[str, str],
    user_agent: str,
    _http_mode: bool,
    _force_engine: str | None,
) -> tuple[list[MangaItem], bool]:
    return await toongod.list_catalog(
        base_url,
        page=page,
        orderby=orderby,
        path=path,
        cookies=cookies,
        user_agent=user_agent,
    )


async def _toongod_chapters(
    base_url: str,
    manga_url: str,
    cookies: dict[str, str],
    user_agent: str,
    _http_mode: bool,
    _force_engine: str | None,
) -> list[ChapterItem]:
    return await toongod.list_chapters(base_url, manga_url, cookies=cookies, user_agent=user_agent)


async def _toongod_reader_images(
    base_url: str,
    chapter_url: str,
    cookies: dict[str, str],
    user_agent: str,
    _http_mode: bool,
    _force_engine: str | None,
) -> list[str]:
    return await toongod.fetch_reader_images(base_url, chapter_url, cookies=cookies, user_agent=user_agent)


async def _generic_search(
    base_url: str,
    keyword: str,
    cookies: dict[str, str],
    user_agent: str,
    http_mode: bool,
    force_engine: str | None,
) -> list[MangaItem]:
    return await generic.search_manga(
        base_url,
        keyword,
        cookies=cookies,
        user_agent=user_agent,
        http_mode=http_mode,
        force_engine=force_engine,
    )


async def _generic_catalog(
    base_url: str,
    page: int,
    orderby: str | None,
    path: str | None,
    cookies: dict[str, str],
    user_agent: str,
    http_mode: bool,
    force_engine: str | None,
) -> tuple[list[MangaItem], bool]:
    return await generic.list_catalog(
        base_url,
        page=page,
        orderby=orderby,
        path=path,
        cookies=cookies,
        user_agent=user_agent,
        http_mode=http_mode,
        force_engine=force_engine,
    )


async def _generic_chapters(
    base_url: str,
    manga_url: str,
    cookies: dict[str, str],
    user_agent: str,
    http_mode: bool,
    force_engine: str | None,
) -> list[ChapterItem]:
    return await generic.list_chapters(
        base_url,
        manga_url,
        cookies=cookies,
        user_agent=user_agent,
        http_mode=http_mode,
        force_engine=force_engine,
    )


async def _generic_reader_images(
    base_url: str,
    chapter_url: str,
    cookies: dict[str, str],
    user_agent: str,
    http_mode: bool,
    force_engine: str | None,
) -> list[str]:
    return await generic.fetch_reader_images(
        base_url,
        chapter_url,
        cookies=cookies,
        user_agent=user_agent,
        http_mode=http_mode,
        force_engine=force_engine,
    )


PROVIDERS: dict[str, ProviderAdapter] = {
    "mangaforfree": ProviderAdapter(
        key="mangaforfree",
        label="MangaForFree",
        hosts=("mangaforfree.com",),
        supports_http=True,
        supports_playwright=False,
        supports_custom_host=False,
        default_catalog_path="/manga/",
        search=_mff_search,
        catalog=_mff_catalog,
        chapters=_mff_chapters,
        reader_images=_mff_reader_images,
        auth_url="https://mangaforfree.com",
    ),
    "toongod": ProviderAdapter(
        key="toongod",
        label="ToonGod",
        hosts=("toongod.org",),
        supports_http=True,
        supports_playwright=False,
        supports_custom_host=False,
        default_catalog_path="/webtoon/",
        search=_toongod_search,
        catalog=_toongod_catalog,
        chapters=_toongod_chapters,
        reader_images=_toongod_reader_images,
        auth_url="https://toongod.org",
    ),
    "generic": ProviderAdapter(
        key="generic",
        label="Generic",
        hosts=(),
        supports_http=True,
        supports_playwright=True,
        supports_custom_host=True,
        default_catalog_path="/manga/",
        search=_generic_search,
        catalog=_generic_catalog,
        chapters=_generic_chapters,
        reader_images=_generic_reader_images,
        auth_url="",
    ),
}


def resolve_provider(base_url: str, site_hint: str | None = None) -> ProviderAdapter:
    normalized = normalize_base_url(base_url)
    host = (urlparse(normalized).hostname or "").lower()
    if not host:
        raise ProviderUnavailableError("无效的 base_url")

    hint = (site_hint or "").strip().lower()
    if hint:
        provider = PROVIDERS.get(hint)
        if provider is None:
            raise ProviderUnavailableError(f"未知站点标识: {site_hint}")
        if provider.hosts and not any(_host_match(host, domain) for domain in provider.hosts):
            if provider.supports_custom_host:
                return provider
            raise ProviderUnavailableError(f"base_url 与站点标识不匹配: {site_hint}")
        return provider

    for provider in PROVIDERS.values():
        if provider.hosts and any(_host_match(host, domain) for domain in provider.hosts):
            return provider
    return PROVIDERS["generic"]


def provider_auth_url(provider: ProviderAdapter, normalized_base_url: str) -> str:
    if provider.auth_url:
        return provider.auth_url
    return normalized_base_url


def provider_allows_image_host(provider: ProviderAdapter, target_url: str, normalized_base_url: str) -> bool:
    host = (urlparse(target_url).hostname or "").lower()
    if not host:
        return False
    base_host = (urlparse(normalized_base_url).hostname or "").lower()

    if provider.key == "mangaforfree":
        allowlist = {"mangaforfree.com", "i0.wp.com", "i1.wp.com", "i2.wp.com"}
        if base_host:
            allowlist.add(base_host)
        return any(_host_match(host, domain) for domain in allowlist)

    if provider.key == "toongod":
        allowlist = {"toongod.org", "i0.wp.com", "i1.wp.com", "i2.wp.com"}
        if base_host:
            allowlist.add(base_host)
        return any(_host_match(host, domain) for domain in allowlist)

    # generic
    if not base_host:
        return False
    return _host_match(host, base_host)


def providers_payload() -> dict[str, Any]:
    items = []
    for provider in PROVIDERS.values():
        items.append(
            {
                "key": provider.key,
                "label": provider.label,
                "hosts": list(provider.hosts),
                "supports_http": provider.supports_http,
                "supports_playwright": provider.supports_playwright,
                "supports_custom_host": provider.supports_custom_host,
                "default_catalog_path": provider.default_catalog_path,
            }
        )
    return {"items": items}
