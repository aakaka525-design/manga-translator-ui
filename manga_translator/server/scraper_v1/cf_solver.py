"""Cloudflare challenge solving helpers."""

from __future__ import annotations

import asyncio
import os
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlparse

import aiohttp

from .base import looks_like_challenge
from .http_client import ScraperHttpClient
from .mangaforfree import CloudflareChallengeError
from .state import CookieStore


@dataclass(frozen=True)
class SolveResult:
    cookies: dict[str, str]
    html: str
    level_used: str


class CloudflareSolver:
    def __init__(self, http_client: ScraperHttpClient, cookie_store: CookieStore | None = None):
        self.http_client = http_client
        self.flaresolverr_url = (os.environ.get("FLARESOLVERR_URL") or "").strip()
        self._cookie_store = cookie_store

    async def solve(
        self,
        url: str,
        *,
        current_cookies: dict[str, str],
        user_agent: str,
        referer: str | None = None,
    ) -> SolveResult:
        domain = (urlparse(url).hostname or "").strip().lower()
        cached_cookies = self._cookie_store.get_cookies(domain) if (self._cookie_store and domain) else {}
        if cached_cookies:
            merged = {**current_cookies, **cached_cookies}
            html = await self.http_client.fetch_html(
                url,
                cookies=merged,
                user_agent=user_agent,
                referer=referer,
                allow_error_body=True,
            )
            if not looks_like_challenge(html):
                return SolveResult(cookies=merged, html=html, level_used="cached")

        html = await self.http_client.fetch_html(
            url,
            cookies=current_cookies,
            user_agent=user_agent,
            referer=referer,
            allow_error_body=True,
        )
        if not looks_like_challenge(html):
            return SolveResult(cookies=current_cookies, html=html, level_used="http_client")

        if self.flaresolverr_url:
            solved = await self._solve_with_flaresolverr(url=url, user_agent=user_agent)
            if solved is not None:
                if self._cookie_store and domain and solved.cookies:
                    merged = {**current_cookies, **solved.cookies}
                    self._cookie_store.update_cookies(domain, merged, None)
                return solved

        raise CloudflareChallengeError(f"CF 挑战无法自动解决，请手动注入 Cookie (domain={domain or 'unknown'})")

    async def _solve_with_flaresolverr(self, *, url: str, user_agent: str) -> SolveResult | None:
        for attempt in range(2):
            try:
                timeout = aiohttp.ClientTimeout(total=60)
                payload: dict[str, Any] = {
                    "cmd": "request.get",
                    "url": url,
                    "maxTimeout": 45000,
                    "userAgent": user_agent,
                }
                async with aiohttp.ClientSession(timeout=timeout) as session:
                    async with session.post(self.flaresolverr_url, json=payload) as response:
                        if response.status >= 500 and attempt == 0:
                            await asyncio.sleep(2)
                            continue
                        if response.status >= 400:
                            return None
                        body = await response.json()
            except (asyncio.TimeoutError, aiohttp.ClientError):
                if attempt == 0:
                    await asyncio.sleep(2)
                    continue
                return None

            solution = body.get("solution") if isinstance(body, dict) else None
            if not isinstance(solution, dict):
                return None

            html = str(solution.get("response") or "")
            if not html or looks_like_challenge(html):
                return None

            cookies_payload = solution.get("cookies")
            parsed_cookies: dict[str, str] = {}
            if isinstance(cookies_payload, list):
                for item in cookies_payload:
                    if not isinstance(item, dict):
                        continue
                    name = str(item.get("name") or "").strip()
                    value = str(item.get("value") or "")
                    if name:
                        parsed_cookies[name] = value

            return SolveResult(cookies=parsed_cookies, html=html, level_used="flaresolverr")

        return None
