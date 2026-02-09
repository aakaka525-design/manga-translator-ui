"""Scraper v1 package."""

from .mangaforfree import (
    CloudflareChallengeError,
    MangaItem,
    ChapterItem,
    fetch_reader_images,
    list_catalog,
    list_chapters,
    search_manga,
)
from .state import (
    CookieInfo,
    collect_cookies,
    cookies_to_header,
    default_state_path,
    get_state_info,
    load_state_payload,
    normalize_base_url,
    save_state_payload,
)
from .providers import (
    BrowserUnavailableError,
    ProviderAdapter,
    ProviderUnavailableError,
    provider_allows_image_host,
    provider_auth_url,
    providers_payload,
    resolve_provider,
)
from .task_store import ScraperTaskStore

__all__ = [
    "CloudflareChallengeError",
    "MangaItem",
    "ChapterItem",
    "fetch_reader_images",
    "list_catalog",
    "list_chapters",
    "search_manga",
    "CookieInfo",
    "collect_cookies",
    "cookies_to_header",
    "default_state_path",
    "get_state_info",
    "load_state_payload",
    "normalize_base_url",
    "save_state_payload",
    "BrowserUnavailableError",
    "ProviderAdapter",
    "ProviderUnavailableError",
    "provider_allows_image_host",
    "provider_auth_url",
    "providers_payload",
    "resolve_provider",
    "ScraperTaskStore",
]
