"""Unified HTTP client for scraper providers."""

from __future__ import annotations

import asyncio
import os
import time
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from threading import Lock
from typing import Optional
from urllib.parse import urlparse

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
        timeout_sec: float = DEFAULT_TIMEOUT_SEC,
        rate_limit_rps: float | None = None,
        concurrency: int | None = None,
    ) -> str:
        domain = self._domain_key(url)
        await self._wait_rate_limit(domain, rate_limit_rps)
        sem = self._domain_semaphore(domain, concurrency)
        req_headers = self._build_headers(user_agent=user_agent, referer=referer, headers=headers)

        async with sem:
            if self.engine == "curl_cffi" and curl_requests is not None:
                return await self._request_text_curl_cffi(method, url, data=data, cookies=cookies, headers=req_headers, timeout_sec=timeout_sec)
            return await self._request_text_aiohttp(method, url, data=data, cookies=cookies, headers=req_headers, timeout_sec=timeout_sec)

    async def _request_text_aiohttp(
        self,
        method: str,
        url: str,
        *,
        data: dict[str, str] | None,
        cookies: dict[str, str] | None,
        headers: dict[str, str],
        timeout_sec: float,
    ) -> str:
        timeout = aiohttp.ClientTimeout(total=timeout_sec)
        async with aiohttp.ClientSession(timeout=timeout, cookies=cookies or {}) as session:
            async with session.request(method.upper(), url, headers=headers, data=data) as response:
                text = await response.text()
                response.raise_for_status()
                return text

    async def _request_text_curl_cffi(
        self,
        method: str,
        url: str,
        *,
        data: dict[str, str] | None,
        cookies: dict[str, str] | None,
        headers: dict[str, str],
        timeout_sec: float,
    ) -> str:
        assert curl_requests is not None
        async with curl_requests.AsyncSession(impersonate="chrome120", timeout=timeout_sec) as session:
            response = await session.request(method.upper(), url, data=data, headers=headers, cookies=cookies or {})
            status = int(response.status_code)
            text = response.text
            if status >= 400:
                raise self._client_error(url, status, response.headers)
            return text

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
        req_headers = self._build_headers(user_agent=user_agent, referer=referer, headers=headers)

        async with sem:
            if self.engine == "curl_cffi" and curl_requests is not None:
                assert curl_requests is not None
                async with curl_requests.AsyncSession(impersonate="chrome120", timeout=timeout_sec) as session:
                    response = await session.get(url, headers=req_headers, cookies=cookies or {})
                    status = int(response.status_code)
                    if status >= 400:
                        raise self._client_error(url, status, response.headers)
                    media_type = (response.headers or {}).get("content-type") or "application/octet-stream"
                    return BinaryResponse(payload=response.content or b"", media_type=media_type)

            timeout = aiohttp.ClientTimeout(total=timeout_sec)
            async with aiohttp.ClientSession(timeout=timeout, cookies=cookies or {}) as session:
                async with session.get(url, headers=req_headers) as response:
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
