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
    CookieStore,
    collect_cookies,
    cookies_to_header,
    default_state_path,
    get_cookie_store,
    get_state_info,
    load_state_payload,
    merge_cookies,
    normalize_base_url,
    save_state_payload,
)
from .base import ProviderContext
from .http_client import ScraperHttpClient, DownloadResult, BinaryResponse, get_http_client
from .cf_solver import CloudflareSolver, SolveResult
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
from .alerts import (
    DEFAULT_ALERT_SETTINGS,
    ScraperAlertEngine,
    normalize_alert_settings,
    send_test_webhook,
    send_webhook,
)

__all__ = [
    "CloudflareChallengeError",
    "MangaItem",
    "ChapterItem",
    "fetch_reader_images",
    "list_catalog",
    "list_chapters",
    "search_manga",
    "CookieInfo",
    "CookieStore",
    "collect_cookies",
    "cookies_to_header",
    "default_state_path",
    "get_cookie_store",
    "get_state_info",
    "load_state_payload",
    "merge_cookies",
    "normalize_base_url",
    "save_state_payload",
    "ProviderContext",
    "ScraperHttpClient",
    "DownloadResult",
    "BinaryResponse",
    "get_http_client",
    "CloudflareSolver",
    "SolveResult",
    "BrowserUnavailableError",
    "ProviderAdapter",
    "ProviderUnavailableError",
    "provider_allows_image_host",
    "provider_auth_url",
    "providers_payload",
    "resolve_provider",
    "ScraperTaskStore",
    "DEFAULT_ALERT_SETTINGS",
    "ScraperAlertEngine",
    "normalize_alert_settings",
    "send_test_webhook",
    "send_webhook",
]
