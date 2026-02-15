"""Cloudflare challenge solving helpers."""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any

import aiohttp

from .base import looks_like_challenge
from .http_client import ScraperHttpClient


@dataclass(frozen=True)
class SolveResult:
    cookies: dict[str, str]
    html: str
    level_used: str


class CloudflareSolver:
    def __init__(self, http_client: ScraperHttpClient):
        self.http_client = http_client
        self.flaresolverr_url = (os.environ.get("FLARESOLVERR_URL") or "").strip()

    async def solve(
        self,
        url: str,
        *,
        current_cookies: dict[str, str],
        user_agent: str,
        referer: str | None = None,
    ) -> SolveResult:
        html = await self.http_client.fetch_html(
            url,
            cookies=current_cookies,
            user_agent=user_agent,
            referer=referer,
        )
        if not looks_like_challenge(html):
            return SolveResult(cookies=current_cookies, html=html, level_used="http_client")

        if self.flaresolverr_url:
            solved = await self._solve_with_flaresolverr(url=url, user_agent=user_agent)
            if solved is not None:
                return solved

        raise RuntimeError("SCRAPER_AUTH_CHALLENGE")

    async def _solve_with_flaresolverr(self, *, url: str, user_agent: str) -> SolveResult | None:
        timeout = aiohttp.ClientTimeout(total=45)
        payload: dict[str, Any] = {
            "cmd": "request.get",
            "url": url,
            "maxTimeout": 30000,
            "userAgent": user_agent,
        }
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.post(self.flaresolverr_url, json=payload) as response:
                if response.status >= 400:
                    return None
                body = await response.json()

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
