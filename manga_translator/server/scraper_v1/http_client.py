"""Unified HTTP client for scraper providers."""

from __future__ import annotations

import asyncio
import logging
import os
import time
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from threading import Lock
from typing import Any, Optional
from urllib.parse import urlparse

logger = logging.getLogger(__name__)

import aiohttp
from yarl import URL


try:
    from curl_cffi import requests as curl_requests
except Exception:  # pragma: no cover
    curl_requests = None


DEFAULT_ENGINE = os.environ.get("SCRAPER_HTTP_ENGINE", "aiohttp").strip().lower() or "aiohttp"
DEFAULT_DOMAIN_CONCURRENCY = max(1, int(os.environ.get("SCRAPER_DOMAIN_CONCURRENCY", "6") or 6))
DEFAULT_TIMEOUT_SEC = float(os.environ.get("SCRAPER_HTTP_TIMEOUT_SEC", "25") or 25)


@dataclass(frozen=True)
class BinaryResponse:
    payload: bytes
    media_type: str


@dataclass(frozen=True)
class DownloadResult:
    ok: bool
    error: str | None = None
    retryable: bool = False


class ScraperHttpClient:
    def __init__(self, default_user_agent: str):
        self._default_ua = default_user_agent
        self._domain_semaphores: dict[str, asyncio.Semaphore] = {}
        self._domain_rate_next: dict[str, float] = defaultdict(float)
        self._rate_lock = asyncio.Lock()
        self._semaphore_lock = Lock()
        self.engine = DEFAULT_ENGINE
        # FlareSolverr transparent fallback — any GET 403 will automatically
        # be retried through FlareSolverr using the exact same URL.
        self._flaresolverr_url: str = (
            os.environ.get("FLARESOLVERR_URL") or ""
        ).strip()
        # Domain → {cookies, user_agent, ts} extracted from FlareSolverr.
        # Used by fetch_binary to retry 403 image/binary requests.
        # Entries expire after _CF_COOKIE_TTL seconds.
        self._cf_cookies: dict[str, tuple[dict[str, str], float]] = {}   # domain -> (cookies, timestamp)
        self._cf_user_agent: dict[str, tuple[str, float]] = {}           # domain -> (ua, timestamp)
        self._CF_COOKIE_TTL: float = 1800.0  # 30 minutes

    def inject_cf_cookies(
        self,
        url: str,
        cookies: dict[str, str],
        user_agent: str | None = None,
    ) -> None:
        """Inject externally-obtained CF cookies into the internal cache.

        This bridges the gap between cf_solver (which stores cookies in
        CookieStore) and fetch_binary (which reads _cf_cookies).  After
        a successful FlareSolverr solve for an HTML page, the caller
        should inject the resulting cookies here so that subsequent
        binary requests (images) on the same domain can reuse them
        without triggering another FlareSolverr call.
        """
        if not cookies:
            return
        domain = self._domain_key(url)
        now = time.monotonic()
        existing = self._cf_cookies.get(domain)
        if existing:
            merged = {**existing[0], **cookies}
        else:
            merged = dict(cookies)
        self._cf_cookies[domain] = (merged, now)
        if user_agent:
            self._cf_user_agent[domain] = (user_agent, now)
        logger.info(
            "[http_client] injected %d CF cookies for %s (ua=%s)",
            len(cookies), domain, bool(user_agent),
        )

    def set_engine(self, engine: str | None) -> None:
        candidate = (engine or "").strip().lower()
        if candidate in {"aiohttp", "curl_cffi"}:
            self.engine = candidate

    def _domain_key(self, url: str) -> str:
        return (urlparse(url).hostname or "").lower() or "_default"

    def _domain_semaphore(self, domain: str, limit: int | None = None) -> asyncio.Semaphore:
        max_conn = max(1, int(limit or DEFAULT_DOMAIN_CONCURRENCY))
        with self._semaphore_lock:
            sem = self._domain_semaphores.get(domain)
            if sem is None:
                sem = asyncio.Semaphore(max_conn)
                self._domain_semaphores[domain] = sem
            return sem

    async def _wait_rate_limit(self, domain: str, rate_limit_rps: float | None) -> None:
        rps = float(rate_limit_rps or 0)
        if rps <= 0:
            return
        interval = 1.0 / max(0.001, rps)
        async with self._rate_lock:
            now = time.monotonic()
            next_at = self._domain_rate_next.get(domain, 0.0)
            wait_sec = max(0.0, next_at - now)
            self._domain_rate_next[domain] = max(now, next_at) + interval
        if wait_sec > 0:
            await asyncio.sleep(wait_sec)

    def _build_headers(
        self,
        *,
        user_agent: str | None = None,
        referer: str | None = None,
        headers: dict[str, str] | None = None,
    ) -> dict[str, str]:
        req_headers = {
            "User-Agent": user_agent or self._default_ua,
            "Accept-Encoding": "gzip, deflate",
        }
        if referer:
            req_headers["Referer"] = referer
        if headers:
            req_headers.update(headers)
        return req_headers

    async def fetch_html(
        self,
        url: str,
        *,
        cookies: dict[str, str] | None = None,
        user_agent: str | None = None,
        referer: str | None = None,
        headers: dict[str, str] | None = None,
        allow_error_body: bool = False,
        timeout_sec: float = DEFAULT_TIMEOUT_SEC,
        rate_limit_rps: float | None = None,
        concurrency: int | None = None,
    ) -> str:
        return await self.request_text(
            "GET",
            url,
            cookies=cookies,
            user_agent=user_agent,
            referer=referer,
            headers=headers,
            allow_error_body=allow_error_body,
            timeout_sec=timeout_sec,
            rate_limit_rps=rate_limit_rps,
            concurrency=concurrency,
        )

    async def post_form_html(
        self,
        url: str,
        *,
        data: dict[str, str],
        cookies: dict[str, str] | None = None,
        user_agent: str | None = None,
        referer: str | None = None,
        headers: dict[str, str] | None = None,
        timeout_sec: float = DEFAULT_TIMEOUT_SEC,
        rate_limit_rps: float | None = None,
        concurrency: int | None = None,
    ) -> str:
        return await self.request_text(
            "POST",
            url,
            data=data,
            cookies=cookies,
            user_agent=user_agent,
            referer=referer,
            headers=headers,
            timeout_sec=timeout_sec,
            rate_limit_rps=rate_limit_rps,
            concurrency=concurrency,
        )

    async def request_text(
        self,
        method: str,
        url: str,
        *,
        data: dict[str, str] | None = None,
        cookies: dict[str, str] | None = None,
        user_agent: str | None = None,
        referer: str | None = None,
        headers: dict[str, str] | None = None,
        allow_error_body: bool = False,
        timeout_sec: float = DEFAULT_TIMEOUT_SEC,
        rate_limit_rps: float | None = None,
        concurrency: int | None = None,
    ) -> str:
        domain = self._domain_key(url)
        await self._wait_rate_limit(domain, rate_limit_rps)
        sem = self._domain_semaphore(domain, concurrency)
        req_headers = self._build_headers(user_agent=user_agent, referer=referer, headers=headers)

        async with sem:
            try:
                if self.engine == "curl_cffi" and curl_requests is not None:
                    return await self._request_text_curl_cffi(
                        method,
                        url,
                        data=data,
                        cookies=cookies,
                        headers=req_headers,
                        allow_error_body=allow_error_body,
                        timeout_sec=timeout_sec,
                    )
                return await self._request_text_aiohttp(
                    method,
                    url,
                    data=data,
                    cookies=cookies,
                    headers=req_headers,
                    allow_error_body=allow_error_body,
                    timeout_sec=timeout_sec,
                )
            except aiohttp.ClientResponseError as exc:
                status_code = int(exc.status or 0)
                is_cf_blocked = status_code in {401, 403}

                # curl_cffi TLS fingerprint is incompatible with cf_clearance
                # cookies obtained from FlareSolverr (Chrome). Automatically
                # fall back to aiohttp when cf_clearance is present but
                # curl_cffi gets blocked.
                if (
                    is_cf_blocked
                    and self.engine == "curl_cffi"
                    and cookies
                    and "cf_clearance" in cookies
                ):
                    logger.info(
                        "[http_client] curl_cffi %d with cf_clearance, "
                        "falling back to aiohttp for %s",
                        status_code, url,
                    )
                    try:
                        return await self._request_text_aiohttp(
                            method, url, data=data, cookies=cookies,
                            headers=req_headers,
                            allow_error_body=allow_error_body,
                            timeout_sec=timeout_sec,
                        )
                    except aiohttp.ClientResponseError:
                        pass  # fall through to FlareSolverr below

                # Transparent FlareSolverr fallback: on 403 for GET requests,
                # automatically retry via FlareSolverr with the exact URL.
                if (
                    is_cf_blocked
                    and method.upper() == "GET"
                    and self._flaresolverr_url
                    and not allow_error_body
                ):
                    html = await self._try_flaresolverr(url, user_agent or self._default_ua)
                    if html is not None:
                        return html
                raise

    async def _request_text_aiohttp(
        self,
        method: str,
        url: str,
        *,
        data: dict[str, str] | None,
        cookies: dict[str, str] | None,
        headers: dict[str, str],
        allow_error_body: bool,
        timeout_sec: float,
    ) -> str:
        timeout = aiohttp.ClientTimeout(total=timeout_sec)
        async with aiohttp.ClientSession(timeout=timeout, cookies=cookies or {}) as session:
            async with session.request(method.upper(), url, headers=headers, data=data) as response:
                text = await response.text()
                if response.status >= 400:
                    if allow_error_body:
                        return text
                    raise self._client_error(url, response.status, response.headers)
                return text

    async def _request_text_curl_cffi(
        self,
        method: str,
        url: str,
        *,
        data: dict[str, str] | None,
        cookies: dict[str, str] | None,
        headers: dict[str, str],
        allow_error_body: bool,
        timeout_sec: float,
    ) -> str:
        assert curl_requests is not None
        async with curl_requests.AsyncSession(impersonate="chrome120", timeout=timeout_sec) as session:
            response = await session.request(method.upper(), url, data=data, headers=headers, cookies=cookies or {})
            status = int(response.status_code)
            text = response.text
            if status >= 400:
                if allow_error_body:
                    return text
                raise self._client_error(url, status, response.headers)
            return text

    async def _try_flaresolverr(self, url: str, user_agent: str) -> str | None:
        """Transparent FlareSolverr fallback for CF-protected pages.

        Called automatically by request_text() when a GET returns 403.
        Sends the exact URL to FlareSolverr and returns the full HTML on
        success, or None if FlareSolverr can't help (caller re-raises).
        """
        from .base import looks_like_challenge  # avoid circular import

        logger.info("[FlareSolverr] 403 fallback for %s", url)
        payload: dict[str, Any] = {
            "cmd": "request.get",
            "url": url,
            "maxTimeout": 45000,
            "userAgent": user_agent,
        }
        for attempt in range(2):
            try:
                timeout = aiohttp.ClientTimeout(total=60)
                async with aiohttp.ClientSession(timeout=timeout) as session:
                    async with session.post(self._flaresolverr_url, json=payload) as resp:
                        if resp.status >= 500 and attempt == 0:
                            await asyncio.sleep(2)
                            continue
                        if resp.status >= 400:
                            logger.warning("[FlareSolverr] HTTP %d from FlareSolverr", resp.status)
                            return None
                        body = await resp.json()
            except (asyncio.TimeoutError, aiohttp.ClientError) as exc:
                if attempt == 0:
                    await asyncio.sleep(2)
                    continue
                logger.warning("[FlareSolverr] connection error: %s", exc)
                return None

            solution = body.get("solution") if isinstance(body, dict) else None
            if not isinstance(solution, dict):
                logger.warning("[FlareSolverr] no 'solution' in response")
                return None

            html = str(solution.get("response") or "")

            # Parse cookies first — cf_clearance presence is the strongest
            # signal that the challenge was solved, even if the HTML still
            # triggers looks_like_challenge() due to embedded CF CDN refs.
            cookies_payload = solution.get("cookies")
            has_cf_clearance = False
            if isinstance(cookies_payload, list):
                for item in cookies_payload:
                    if isinstance(item, dict) and str(item.get("name") or "").strip() == "cf_clearance":
                        has_cf_clearance = True
                        break

            if not html:
                logger.warning("[FlareSolverr] returned empty HTML")
                return None

            if looks_like_challenge(html) and not has_cf_clearance:
                logger.warning("[FlareSolverr] returned challenge page (no cf_clearance)")
                return None

            if looks_like_challenge(html) and has_cf_clearance:
                logger.info(
                    "[FlareSolverr] HTML triggered challenge detection but "
                    "cf_clearance present — trusting solve result"
                )

            # Extract and cache cookies + UA per domain so that fetch_binary
            # can reuse them for image/binary requests on the same domain.
            domain = self._domain_key(url)
            cookies_payload = solution.get("cookies")
            now = time.monotonic()
            if isinstance(cookies_payload, list):
                parsed: dict[str, str] = {}
                for item in cookies_payload:
                    if isinstance(item, dict):
                        name = str(item.get("name") or "").strip()
                        value = str(item.get("value") or "")
                        if name:
                            parsed[name] = value
                if parsed:
                    self._cf_cookies[domain] = (parsed, now)
            solved_ua = str(solution.get("userAgent") or "")
            if solved_ua:
                self._cf_user_agent[domain] = (solved_ua, now)

            logger.info("[FlareSolverr] OK %d bytes for %s", len(html), url)
            return html

        return None

    async def fetch_binary(
        self,
        url: str,
        *,
        cookies: dict[str, str] | None = None,
        user_agent: str | None = None,
        referer: str | None = None,
        headers: dict[str, str] | None = None,
        timeout_sec: float = DEFAULT_TIMEOUT_SEC,
        rate_limit_rps: float | None = None,
        concurrency: int | None = None,
    ) -> BinaryResponse:
        domain = self._domain_key(url)
        await self._wait_rate_limit(domain, rate_limit_rps)
        sem = self._domain_semaphore(domain, concurrency)

        # Merge in any non-expired cf_clearance cookies from FlareSolverr
        effective_cookies = dict(cookies or {})
        now = time.monotonic()
        cf_entry = self._cf_cookies.get(domain)
        if cf_entry and (now - cf_entry[1]) < self._CF_COOKIE_TTL:
            for k, v in cf_entry[0].items():
                effective_cookies.setdefault(k, v)
        # Use FlareSolverr's UA if available and not expired
        ua_entry = self._cf_user_agent.get(domain)
        effective_ua = (ua_entry[0] if ua_entry and (now - ua_entry[1]) < self._CF_COOKIE_TTL else None) or user_agent
        req_headers = self._build_headers(user_agent=effective_ua, referer=referer, headers=headers)

        async with sem:
            # First attempt with effective cookies + UA
            try:
                return await self._fetch_binary_raw(
                    url, cookies=effective_cookies, headers=req_headers, timeout_sec=timeout_sec,
                )
            except aiohttp.ClientResponseError as exc:
                if int(exc.status or 0) != 403 or not self._flaresolverr_url:
                    raise
                # 403 on binary — trigger FlareSolverr to refresh cookies,
                # then retry with the new cookies.
                logger.info("[FlareSolverr] binary 403 for %s, refreshing cookies", url)
                solve_url = referer or url
                _ = await self._try_flaresolverr(solve_url, effective_ua or self._default_ua)
                # Merge cookies from both solve_domain and binary_domain
                # (handles CDN/subdomain scenarios where they differ)
                refreshed_cookies = dict(cookies or {})
                solve_domain = self._domain_key(solve_url)
                for d in {domain, solve_domain}:
                    cf_new = self._cf_cookies.get(d)
                    if cf_new:
                        refreshed_cookies.update(cf_new[0])
                # Pick UA from whichever domain has it
                new_ua_entry = self._cf_user_agent.get(domain) or self._cf_user_agent.get(solve_domain)
                new_ua = (new_ua_entry[0] if new_ua_entry else None) or effective_ua
                new_headers = self._build_headers(user_agent=new_ua, referer=referer, headers=headers)
                return await self._fetch_binary_raw(
                    url, cookies=refreshed_cookies, headers=new_headers, timeout_sec=timeout_sec,
                )

    async def _fetch_binary_raw(
        self,
        url: str,
        *,
        cookies: dict[str, str],
        headers: dict[str, str],
        timeout_sec: float,
    ) -> BinaryResponse:
        if self.engine == "curl_cffi" and curl_requests is not None:
            async with curl_requests.AsyncSession(impersonate="chrome120", timeout=timeout_sec) as session:
                response = await session.get(url, headers=headers, cookies=cookies)
                status = int(response.status_code)
                if status >= 400:
                    raise self._client_error(url, status, response.headers)
                media_type = (response.headers or {}).get("content-type") or "application/octet-stream"
                return BinaryResponse(payload=response.content or b"", media_type=media_type)

        timeout = aiohttp.ClientTimeout(total=timeout_sec)
        async with aiohttp.ClientSession(timeout=timeout, cookies=cookies) as session:
            async with session.get(url, headers=headers) as response:
                if response.status >= 400:
                    raise self._client_error(url, response.status, response.headers)
                payload = await response.read()
                media_type = response.headers.get("content-type") or "application/octet-stream"
                return BinaryResponse(payload=payload, media_type=media_type)

    async def download_binary(
        self,
        url: str,
        output_path: Path,
        *,
        cookies: dict[str, str] | None = None,
        user_agent: str | None = None,
        referer: str | None = None,
        headers: dict[str, str] | None = None,
        timeout_sec: float = 30,
        retry_delays: tuple[float, ...] = (0.0, 0.5, 1.0, 2.0),
        rate_limit_rps: float | None = None,
        concurrency: int | None = None,
    ) -> DownloadResult:
        last_error: str | None = None
        delays = retry_delays if retry_delays else (0.0,)
        for idx, delay in enumerate(delays):
            if delay > 0:
                await asyncio.sleep(delay)
            try:
                data = await self.fetch_binary(
                    url,
                    cookies=cookies,
                    user_agent=user_agent,
                    referer=referer,
                    headers=headers,
                    timeout_sec=timeout_sec,
                    rate_limit_rps=rate_limit_rps,
                    concurrency=concurrency,
                )
                if not data.payload:
                    last_error = "empty payload"
                    if idx < len(delays) - 1:
                        continue
                    return DownloadResult(ok=False, error=last_error, retryable=True)
                output_path.write_bytes(data.payload)
                return DownloadResult(ok=True)
            except aiohttp.ClientResponseError as exc:
                last_error = f"HTTP {exc.status}"
                retryable = int(exc.status or 0) in {408, 425, 429, 500, 502, 503, 504}
                if retryable and idx < len(delays) - 1:
                    continue
                return DownloadResult(ok=False, error=last_error, retryable=retryable)
            except (
                aiohttp.ClientConnectionError,
                aiohttp.ClientPayloadError,
                aiohttp.ServerTimeoutError,
                asyncio.TimeoutError,
            ) as exc:
                last_error = str(exc) or exc.__class__.__name__
                if idx < len(delays) - 1:
                    continue
                return DownloadResult(ok=False, error=last_error, retryable=True)
            except Exception as exc:  # noqa: BLE001
                last_error = str(exc)
                return DownloadResult(ok=False, error=last_error, retryable=False)
        return DownloadResult(ok=False, error=last_error or "下载失败", retryable=True)

    def _client_error(self, url: str, status: int, headers: dict | aiohttp.typedefs.LooseHeaders | None = None) -> aiohttp.ClientResponseError:
        request_info = aiohttp.RequestInfo(url=URL(url), method="GET", headers={})
        return aiohttp.ClientResponseError(
            request_info=request_info,
            history=(),
            status=int(status),
            message=f"HTTP {status}",
            headers=headers,
        )


_global_http_client: ScraperHttpClient | None = None


def get_http_client(default_user_agent: str = "Mozilla/5.0") -> ScraperHttpClient:
    global _global_http_client
    if _global_http_client is None:
        _global_http_client = ScraperHttpClient(default_user_agent=default_user_agent)
    return _global_http_client


def reset_http_client() -> None:
    global _global_http_client
    _global_http_client = None
