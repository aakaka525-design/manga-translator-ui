"""Provider registry for scraper v1."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Awaitable, Callable
from urllib.parse import urlparse

from . import generic, mangaforfree, toongod
from .base import ProviderContext
from .mangaforfree import ChapterItem, MangaItem
from .state import normalize_base_url


class ProviderUnavailableError(ValueError):
    pass


BrowserUnavailableError = generic.BrowserUnavailableError


SearchFn = Callable[[ProviderContext, str], Awaitable[list[MangaItem]]]
CatalogFn = Callable[[ProviderContext, int, str | None, str | None], Awaitable[tuple[list[MangaItem], bool]]]
ChaptersFn = Callable[[ProviderContext, str], Awaitable[list[ChapterItem]]]
ReaderImagesFn = Callable[[ProviderContext, str], Awaitable[list[str]]]


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
    features: tuple[str, ...] = ()
    form_schema: tuple[dict[str, Any], ...] = ()
    image_cache_public: bool = False


def _host_match(host: str, expected: str) -> bool:
    return host == expected or host.endswith(f".{expected}")


async def _mff_search(ctx: ProviderContext, keyword: str) -> list[MangaItem]:
    return await mangaforfree.search_manga(
        ctx.base_url,
        keyword,
        cookies=ctx.cookies,
        user_agent=ctx.user_agent,
        rate_limit_rps=ctx.rate_limit_rps,
        concurrency=ctx.concurrency,
    )


async def _mff_catalog(ctx: ProviderContext, page: int, orderby: str | None, path: str | None) -> tuple[list[MangaItem], bool]:
    return await mangaforfree.list_catalog(
        ctx.base_url,
        page=page,
        orderby=orderby,
        path=path,
        cookies=ctx.cookies,
        user_agent=ctx.user_agent,
        rate_limit_rps=ctx.rate_limit_rps,
        concurrency=ctx.concurrency,
    )


async def _mff_chapters(ctx: ProviderContext, manga_url: str) -> list[ChapterItem]:
    return await mangaforfree.list_chapters(
        ctx.base_url,
        manga_url,
        cookies=ctx.cookies,
        user_agent=ctx.user_agent,
        rate_limit_rps=ctx.rate_limit_rps,
        concurrency=ctx.concurrency,
    )


async def _mff_reader_images(ctx: ProviderContext, chapter_url: str) -> list[str]:
    return await mangaforfree.fetch_reader_images(
        ctx.base_url,
        chapter_url,
        cookies=ctx.cookies,
        user_agent=ctx.user_agent,
        rate_limit_rps=ctx.rate_limit_rps,
        concurrency=ctx.concurrency,
    )


async def _toongod_search(ctx: ProviderContext, keyword: str) -> list[MangaItem]:
    return await toongod.search_manga(
        ctx.base_url,
        keyword,
        cookies=ctx.cookies,
        user_agent=ctx.user_agent,
        rate_limit_rps=ctx.rate_limit_rps,
        concurrency=ctx.concurrency,
    )


async def _toongod_catalog(ctx: ProviderContext, page: int, orderby: str | None, path: str | None) -> tuple[list[MangaItem], bool]:
    return await toongod.list_catalog(
        ctx.base_url,
        page=page,
        orderby=orderby,
        path=path,
        cookies=ctx.cookies,
        user_agent=ctx.user_agent,
        rate_limit_rps=ctx.rate_limit_rps,
        concurrency=ctx.concurrency,
    )


async def _toongod_chapters(ctx: ProviderContext, manga_url: str) -> list[ChapterItem]:
    return await toongod.list_chapters(
        ctx.base_url,
        manga_url,
        cookies=ctx.cookies,
        user_agent=ctx.user_agent,
        rate_limit_rps=ctx.rate_limit_rps,
        concurrency=ctx.concurrency,
    )


async def _toongod_reader_images(ctx: ProviderContext, chapter_url: str) -> list[str]:
    return await toongod.fetch_reader_images(
        ctx.base_url,
        chapter_url,
        cookies=ctx.cookies,
        user_agent=ctx.user_agent,
        rate_limit_rps=ctx.rate_limit_rps,
        concurrency=ctx.concurrency,
    )


async def _generic_search(ctx: ProviderContext, keyword: str) -> list[MangaItem]:
    return await generic.search_manga(
        ctx.base_url,
        keyword,
        cookies=ctx.cookies,
        user_agent=ctx.user_agent,
        http_mode=ctx.http_mode,
        force_engine=ctx.force_engine,
        rate_limit_rps=ctx.rate_limit_rps,
        concurrency=ctx.concurrency,
    )


async def _generic_catalog(ctx: ProviderContext, page: int, orderby: str | None, path: str | None) -> tuple[list[MangaItem], bool]:
    return await generic.list_catalog(
        ctx.base_url,
        page=page,
        orderby=orderby,
        path=path,
        cookies=ctx.cookies,
        user_agent=ctx.user_agent,
        http_mode=ctx.http_mode,
        force_engine=ctx.force_engine,
        rate_limit_rps=ctx.rate_limit_rps,
        concurrency=ctx.concurrency,
    )


async def _generic_chapters(ctx: ProviderContext, manga_url: str) -> list[ChapterItem]:
    return await generic.list_chapters(
        ctx.base_url,
        manga_url,
        cookies=ctx.cookies,
        user_agent=ctx.user_agent,
        http_mode=ctx.http_mode,
        force_engine=ctx.force_engine,
        rate_limit_rps=ctx.rate_limit_rps,
        concurrency=ctx.concurrency,
    )


async def _generic_reader_images(ctx: ProviderContext, chapter_url: str) -> list[str]:
    return await generic.fetch_reader_images(
        ctx.base_url,
        chapter_url,
        cookies=ctx.cookies,
        user_agent=ctx.user_agent,
        http_mode=ctx.http_mode,
        force_engine=ctx.force_engine,
        rate_limit_rps=ctx.rate_limit_rps,
        concurrency=ctx.concurrency,
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
        features=("search", "catalog", "chapters", "download", "image_proxy"),
        form_schema=(
            {
                "key": "storage_state_path",
                "label": "状态文件路径",
                "type": "string",
                "required": False,
                "default": "data/mangaforfree_state.json",
                "placeholder": "data/mangaforfree_state.json",
                "help": "可选，包含 cf_clearance 等 Cookie",
            },
            {
                "key": "rate_limit_rps",
                "label": "每秒请求数",
                "type": "number",
                "required": False,
                "default": 2,
                "help": "建议 0.5~3，站点风控严格时降低",
            },
        ),
        image_cache_public=False,
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
        features=("search", "catalog", "chapters", "download", "image_proxy"),
        form_schema=(
            {
                "key": "storage_state_path",
                "label": "状态文件路径",
                "type": "string",
                "required": False,
                "default": "data/toongod_state.json",
                "placeholder": "data/toongod_state.json",
                "help": "推荐上传包含 cf_clearance 的状态文件",
            },
            {
                "key": "user_data_dir",
                "label": "浏览器配置目录",
                "type": "string",
                "required": False,
                "default": "data/toongod_profile",
                "help": "有头/无头模式复用浏览器会话",
            },
            {
                "key": "rate_limit_rps",
                "label": "每秒请求数",
                "type": "number",
                "required": False,
                "default": 2,
                "help": "建议 0.5~2，过快容易触发风控",
            },
        ),
        image_cache_public=False,
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
        features=("search", "catalog", "chapters", "download", "image_proxy", "custom_host"),
        form_schema=(
            {
                "key": "base_url",
                "label": "站点地址",
                "type": "string",
                "required": True,
                "default": "",
                "placeholder": "https://example.com",
            },
            {
                "key": "http_mode",
                "label": "HTTP 模式",
                "type": "boolean",
                "required": False,
                "default": True,
            },
            {
                "key": "rate_limit_rps",
                "label": "每秒请求数",
                "type": "number",
                "required": False,
                "default": 1,
            },
        ),
        image_cache_public=False,
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
                "features": list(provider.features),
                "form_schema": [dict(field) for field in provider.form_schema],
                "image_cache_public": bool(provider.image_cache_public),
            }
        )
    return {"items": items}
