"""Cloudflare challenge solving helpers."""

from __future__ import annotations

import asyncio
import logging
import os
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlparse

import aiohttp

from .base import looks_like_challenge
from .http_client import ScraperHttpClient
from .mangaforfree import CloudflareChallengeError
from .state import CookieStore

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class SolveResult:
    cookies: dict[str, str]
    html: str
    level_used: str
    user_agent: str | None = None


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
                logger.info("CF solve: cached cookies worked for %s", domain)
                return SolveResult(cookies=merged, html=html, level_used="cached", user_agent=user_agent)

        html = await self.http_client.fetch_html(
            url,
            cookies=current_cookies,
            user_agent=user_agent,
            referer=referer,
            allow_error_body=True,
        )
        if not looks_like_challenge(html):
            logger.info("CF solve: direct fetch OK for %s (no challenge)", domain)
            return SolveResult(cookies=current_cookies, html=html, level_used="http_client", user_agent=user_agent)

        logger.info("CF solve: challenge detected for %s, trying FlareSolverr", domain)

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
                            logger.warning("FlareSolverr returned %d, retrying...", response.status)
                            await asyncio.sleep(2)
                            continue
                        if response.status >= 400:
                            logger.warning("FlareSolverr returned %d, giving up", response.status)
                            return None
                        body = await response.json()
            except (asyncio.TimeoutError, aiohttp.ClientError) as exc:
                if attempt == 0:
                    logger.warning("FlareSolverr error (%s), retrying...", exc)
                    await asyncio.sleep(2)
                    continue
                logger.error("FlareSolverr failed after retry: %s", exc)
                return None

            solution = body.get("solution") if isinstance(body, dict) else None
            if not isinstance(solution, dict):
                logger.warning("FlareSolverr returned no solution")
                return None

            html = str(solution.get("response") or "")

            # Parse cookies BEFORE challenge check — cf_clearance presence
            # is the strongest signal that the challenge was actually solved,
            # even if the HTML still triggers looks_like_challenge() due to
            # embedded CF CDN references or residual challenge markup.
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

            has_cf_clearance = "cf_clearance" in parsed_cookies

            if not html:
                logger.warning("FlareSolverr returned empty HTML")
                return None

            if looks_like_challenge(html) and not has_cf_clearance:
                # HTML looks like a challenge AND no cf_clearance cookie —
                # FlareSolverr genuinely failed to solve the challenge.
                logger.warning(
                    "FlareSolverr HTML still looks like challenge (len=%d) "
                    "and no cf_clearance cookie — solve failed",
                    len(html),
                )
                return None

            if looks_like_challenge(html) and has_cf_clearance:
                # HTML triggers false positive but cf_clearance is present —
                # trust the cookie, the page content is real.
                logger.info(
                    "FlareSolverr: HTML triggered looks_like_challenge (len=%d) "
                    "but cf_clearance present — trusting solve result",
                    len(html),
                )

            # Extract user agent from FlareSolverr for TLS+UA fingerprint consistency
            solved_user_agent = str(solution.get("userAgent") or "") or None

            logger.info(
                "FlareSolverr solved: html=%d bytes, cookies=%s, ua=%s",
                len(html), list(parsed_cookies.keys()),
                (solved_user_agent or "")[:40],
            )
            return SolveResult(
                cookies=parsed_cookies, html=html,
                level_used="flaresolverr", user_agent=solved_user_agent,
            )

        return None
