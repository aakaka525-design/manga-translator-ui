from __future__ import annotations

from typing import Any

import aiohttp
import pytest

from manga_translator.server.scraper_v1.cf_solver import CloudflareSolver, SolveResult
from manga_translator.server.scraper_v1.http_client import ScraperHttpClient
from manga_translator.server.scraper_v1.mangaforfree import CloudflareChallengeError
from manga_translator.server.scraper_v1.state import CookieStore


class _FakeAiohttpResponse:
    def __init__(self, status: int, text: str, headers: dict[str, str] | None = None):
        self.status = status
        self._text = text
        self.headers = headers or {}

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False

    async def text(self) -> str:
        return self._text


class _FakeAiohttpSession:
    def __init__(self, response: _FakeAiohttpResponse, *args: Any, **kwargs: Any):
        _ = (args, kwargs)
        self._response = response

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False

    def request(self, *args: Any, **kwargs: Any):
        _ = (args, kwargs)
        return self._response


@pytest.mark.asyncio
async def test_fetch_html_allow_error_body_returns_html_on_403(monkeypatch: pytest.MonkeyPatch):
    response = _FakeAiohttpResponse(403, "<html>Just a moment...</html>", {"content-type": "text/html"})
    monkeypatch.setattr(
        "manga_translator.server.scraper_v1.http_client.aiohttp.ClientSession",
        lambda *args, **kwargs: _FakeAiohttpSession(response, *args, **kwargs),
    )

    client = ScraperHttpClient(default_user_agent="pytest-agent")
    html = await client.fetch_html("https://example.org", allow_error_body=True)
    assert "just a moment" in html.lower()


@pytest.mark.asyncio
async def test_fetch_html_default_raises_on_403(monkeypatch: pytest.MonkeyPatch):
    response = _FakeAiohttpResponse(403, "<html>Just a moment...</html>", {"content-type": "text/html"})
    monkeypatch.setattr(
        "manga_translator.server.scraper_v1.http_client.aiohttp.ClientSession",
        lambda *args, **kwargs: _FakeAiohttpSession(response, *args, **kwargs),
    )

    client = ScraperHttpClient(default_user_agent="pytest-agent")
    with pytest.raises(aiohttp.ClientResponseError):
        await client.fetch_html("https://example.org")


class _DummyHttpClient:
    def __init__(self, html: str):
        self.html = html
        self.calls: list[dict[str, Any]] = []

    async def fetch_html(self, url: str, **kwargs: Any) -> str:
        self.calls.append({"url": url, **kwargs})
        return self.html


@pytest.mark.asyncio
async def test_cf_solver_detects_challenge_and_falls_back(monkeypatch: pytest.MonkeyPatch):
    http_client = _DummyHttpClient("<html>Just a moment...</html>")
    solver = CloudflareSolver(http_client)
    solver.flaresolverr_url = "http://localhost:8191/v1"

    async def _fake_solve(**kwargs: Any):
        _ = kwargs
        return SolveResult(cookies={"cf_clearance": "token"}, html="<html>ok</html>", level_used="flaresolverr")

    monkeypatch.setattr(solver, "_solve_with_flaresolverr", _fake_solve)

    result = await solver.solve("https://www.toongod.org/webtoon/demo/", current_cookies={}, user_agent="pytest-agent")
    assert result.level_used == "flaresolverr"
    assert result.cookies["cf_clearance"] == "token"
    assert http_client.calls
    assert http_client.calls[0].get("allow_error_body") is True


@pytest.mark.asyncio
async def test_cf_solver_caches_cookies_after_solve(monkeypatch: pytest.MonkeyPatch):
    http_client = _DummyHttpClient("<html>Just a moment...</html>")
    cookie_store = CookieStore()
    solver = CloudflareSolver(http_client, cookie_store=cookie_store)
    solver.flaresolverr_url = "http://localhost:8191/v1"

    async def _fake_solve(**kwargs: Any):
        _ = kwargs
        return SolveResult(cookies={"cf_clearance": "cached-token"}, html="<html>ok</html>", level_used="flaresolverr")

    monkeypatch.setattr(solver, "_solve_with_flaresolverr", _fake_solve)

    result = await solver.solve("https://www.toongod.org/webtoon/demo/", current_cookies={"foo": "bar"}, user_agent="pytest-agent")
    assert result.level_used == "flaresolverr"

    cached = cookie_store.get_cookies("www.toongod.org")
    assert cached.get("cf_clearance") == "cached-token"
    assert cached.get("foo") == "bar"


@pytest.mark.asyncio
async def test_cf_solver_no_flaresolverr_raises_challenge():
    http_client = _DummyHttpClient("<html>Just a moment...</html>")
    solver = CloudflareSolver(http_client)
    solver.flaresolverr_url = ""

    with pytest.raises(CloudflareChallengeError):
        await solver.solve("https://www.toongod.org/webtoon/demo/", current_cookies={}, user_agent="pytest-agent")
