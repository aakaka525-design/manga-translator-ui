from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from manga_translator.server.core.middleware import require_auth
from manga_translator.server.core.models import Session
import manga_translator.server.routes.v1_parser as v1_parser
import manga_translator.server.routes.v1_scraper as v1_scraper
from manga_translator.server.scraper_v1 import ProviderUnavailableError, resolve_provider
from manga_translator.server.scraper_v1 import generic as generic_provider
from manga_translator.server.scraper_v1 import mangaforfree as mangaforfree_provider
from manga_translator.server.scraper_v1 import toongod as toongod_provider


@pytest.fixture
def phase2_data(tmp_path: Path):
    root = tmp_path / "phase2_data"
    raw_dir = root / "raw"
    raw_dir.mkdir(parents=True, exist_ok=True)
    state_dir = root / "state"
    state_dir.mkdir(parents=True, exist_ok=True)
    return {"root": root, "raw_dir": raw_dir, "state_dir": state_dir, "db_path": root / "scraper_tasks.db"}


@pytest.fixture
def phase2_app(phase2_data):
    v1_scraper.DATA_DIR = phase2_data["root"]
    v1_scraper.RAW_DIR = phase2_data["raw_dir"]
    v1_scraper.STATE_DIR = phase2_data["state_dir"]
    v1_scraper.TASK_DB_PATH = phase2_data["db_path"]
    v1_scraper.init_task_store(phase2_data["db_path"])
    v1_scraper._scraper_tasks.clear()

    app = FastAPI()
    app.include_router(v1_scraper.router)
    app.include_router(v1_parser.router)

    fake_session = Session(
        session_id="phase2-s1",
        username="tester",
        role="admin",
        token="token-phase2",
        created_at=datetime.now(timezone.utc),
        last_activity=datetime.now(timezone.utc),
        ip_address="127.0.0.1",
        user_agent="pytest",
        is_active=True,
    )

    async def _fake_auth():
        return fake_session

    app.dependency_overrides[require_auth] = _fake_auth
    return app


def test_provider_resolution_matrix():
    assert resolve_provider("https://mangaforfree.com").key == "mangaforfree"
    assert resolve_provider("https://toongod.org").key == "toongod"
    assert resolve_provider("https://example.org").key == "generic"

    with pytest.raises(ProviderUnavailableError):
        resolve_provider("https://example.org", "mangaforfree")


def test_parse_search_filters_series_urls_for_mangaforfree():
    html = """
    <a href="/manga/">root</a>
    <a href="/manga/demo-series/">Demo Series</a>
    <a href="/manga/demo-series/chapter-1/">Chapter 1</a>
    <a href="/manga/demo-series/chapter-1/p/2/">Chapter 1 Page 2</a>
    """
    items = mangaforfree_provider.parse_search(html, "https://example.org")
    urls = [item.url for item in items]
    assert urls == ["https://example.org/manga/demo-series/"]


def test_parse_search_filters_series_urls_for_toongod():
    html = """
    <a href="/webtoon/hero-webtoon/">Hero Webtoon</a>
    <a href="/webtoon/hero-webtoon/chapter-3/">Hero Chapter</a>
    <a href="/manga/demo-series/">Demo Series</a>
    <a href="/manga/">root</a>
    """
    items = toongod_provider.parse_search(html, "https://example.org")
    urls = [item.url for item in items]
    assert urls == [
        "https://example.org/webtoon/hero-webtoon/",
        "https://example.org/manga/demo-series/",
    ]


def test_parse_search_filters_series_urls_for_generic():
    html = """
    <a href="/manga/demo-series/">Demo Series</a>
    <a href="/webtoon/hero-webtoon/">Hero Webtoon</a>
    <a href="/comic/super-comic/">Super Comic</a>
    <a href="/series/future-series/">Future Series</a>
    <a href="/manga/demo-series/chapter-1/">Demo Series Chapter</a>
    <a href="/manga/">root</a>
    """
    items = generic_provider.parse_search(html, "https://example.org")
    urls = [item.url for item in items]
    assert urls == [
        "https://example.org/manga/demo-series/",
        "https://example.org/webtoon/hero-webtoon/",
        "https://example.org/comic/super-comic/",
        "https://example.org/series/future-series/",
    ]


@pytest.mark.asyncio
async def test_mangaforfree_search_does_not_prepend_slug_when_results_exist(monkeypatch: pytest.MonkeyPatch):
    html = '<a href="/manga/my-life-is-a-piece-of-cake/">My Life Is A Piece Of Cake</a>'

    async def _fake_fetch_html(url: str, *, cookies: dict[str, str], headers: dict[str, str], timeout_sec: float = 25):
        _ = (url, cookies, headers, timeout_sec)
        return html

    monkeypatch.setattr(mangaforfree_provider, "_fetch_html", _fake_fetch_html)

    items = await mangaforfree_provider.search_manga(
        "https://example.org",
        "one piece",
        cookies={},
        user_agent="pytest-agent",
    )
    assert items
    assert items[0].id == "my-life-is-a-piece-of-cake"
    assert all(item.id != "one-piece" for item in items)


@pytest.mark.asyncio
async def test_toongod_search_does_not_prepend_slug_when_results_exist(monkeypatch: pytest.MonkeyPatch):
    html = '<a href="/webtoon/hero-webtoon/">Hero Webtoon</a>'

    async def _fake_fetch_html(url: str, *, cookies: dict[str, str], headers: dict[str, str], timeout_sec: float = 25):
        _ = (url, cookies, headers, timeout_sec)
        return html

    monkeypatch.setattr(toongod_provider, "_fetch_html", _fake_fetch_html)

    items = await toongod_provider.search_manga(
        "https://example.org",
        "solo leveling",
        cookies={},
        user_agent="pytest-agent",
    )
    assert items
    assert items[0].id == "hero-webtoon"
    assert all(item.id != "solo-leveling" for item in items)


@pytest.mark.asyncio
async def test_generic_search_does_not_prepend_slug_when_results_exist(monkeypatch: pytest.MonkeyPatch):
    html = '<a href="/comic/super-comic/">Super Comic</a>'

    async def _fake_fetch_html(
        url: str,
        *,
        cookies: dict[str, str],
        user_agent: str,
        http_mode: bool,
        force_engine: str | None,
    ):
        _ = (url, cookies, user_agent, http_mode, force_engine)
        return html

    monkeypatch.setattr(generic_provider, "_fetch_html", _fake_fetch_html)

    items = await generic_provider.search_manga(
        "https://example.org",
        "one piece",
        cookies={},
        user_agent="pytest-agent",
        http_mode=True,
        force_engine=None,
    )
    assert items
    assert items[0].id == "super-comic"
    assert all(item.id != "one-piece" for item in items)


@pytest.mark.asyncio
async def test_mangaforfree_list_chapters_falls_back_to_ajax(monkeypatch: pytest.MonkeyPatch):
    page_html = """
    <html>
      <body>
        <div id="manga-chapters-holder" data-id="358958"></div>
        <script>
          var manga = {"ajax_url":"https://example.org/wp-admin/admin-ajax.php","manga_id":"358958"};
        </script>
      </body>
    </html>
    """
    ajax_html = """
    <ul class="main version-chap">
      <li class="wp-manga-chapter"><a href="https://example.org/manga/demo-series/chapter-2/">Chapter 2</a></li>
      <li class="wp-manga-chapter"><a href="https://example.org/manga/demo-series/chapter-1/">Chapter 1</a></li>
    </ul>
    """

    async def _fake_fetch_html(url: str, *, cookies: dict[str, str], headers: dict[str, str], timeout_sec: float = 25):
        _ = (url, cookies, headers, timeout_sec)
        return page_html

    async def _fake_fetch_ajax(ajax_url: str, manga_id: str, *, cookies: dict[str, str], headers: dict[str, str], referer: str):
        _ = (ajax_url, manga_id, cookies, headers, referer)
        return ajax_html

    monkeypatch.setattr(mangaforfree_provider, "_fetch_html", _fake_fetch_html)
    monkeypatch.setattr(mangaforfree_provider, "_fetch_chapters_via_ajax", _fake_fetch_ajax, raising=False)

    chapters = await mangaforfree_provider.list_chapters(
        "https://example.org",
        "https://example.org/manga/demo-series/",
        cookies={},
        user_agent="pytest-agent",
    )
    assert len(chapters) == 2
    assert [chapter.id for chapter in chapters] == ["chapter-1", "chapter-2"]


def test_providers_endpoint(phase2_app):
    with TestClient(phase2_app) as client:
        resp = client.get("/api/v1/scraper/providers")
        assert resp.status_code == 200
        payload = resp.json()
        keys = {item["key"] for item in payload["items"]}
        assert {"mangaforfree", "toongod", "generic"}.issubset(keys)


def test_task_status_reads_from_sqlite_store(phase2_app):
    store = v1_scraper._get_task_store()
    store.create_task(
        "task-from-store",
        status="success",
        message="done",
        request_payload={"base_url": "https://example.org"},
        provider="generic",
    )
    store.update_task(
        "task-from-store",
        status="success",
        message="done",
        report={"success_count": 1, "failed_count": 0, "total_count": 1},
        finished=True,
    )

    with TestClient(phase2_app) as client:
        resp = client.get("/api/v1/scraper/task/task-from-store")
        assert resp.status_code == 200
        data = resp.json()
        assert data["task_id"] == "task-from-store"
        assert data["persisted"] is True
        assert data["status"] == "success"
        assert data["report"]["success_count"] == 1
        assert data["created_at"]
        assert data["updated_at"]


def test_download_task_persists_and_can_be_reloaded(monkeypatch: pytest.MonkeyPatch, phase2_app):
    async def _fake_reader_images(base_url, chapter_url, cookies, user_agent, http_mode, force_engine):
        _ = (base_url, chapter_url, cookies, user_agent, http_mode, force_engine)
        return ["https://example.org/a.jpg"]

    async def _fake_run_download(task_id, req, provider_obj, base_url, cookies, user_agent, force_engine, **kwargs):
        _ = (req, provider_obj, base_url, cookies, user_agent, force_engine)
        await v1_scraper._set_task_state(
            task_id,
            status="success",
            message="下载完成",
            report={"success_count": 1, "failed_count": 0, "total_count": 1},
            finished=True,
        )

    provider = v1_scraper.ProviderAdapter(
        key="generic",
        label="Generic",
        hosts=(),
        supports_http=True,
        supports_playwright=True,
        supports_custom_host=True,
        default_catalog_path="/manga/",
        search=lambda *args, **kwargs: asyncio.sleep(0),  # not used
        catalog=lambda *args, **kwargs: asyncio.sleep(0),  # not used
        chapters=lambda *args, **kwargs: asyncio.sleep(0),  # not used
        reader_images=_fake_reader_images,
        auth_url="https://example.org",
    )

    monkeypatch.setattr(v1_scraper, "resolve_provider", lambda base_url, site_hint: provider)
    monkeypatch.setattr(v1_scraper, "_run_download_task", _fake_run_download)

    with TestClient(phase2_app) as client:
        resp = client.post(
            "/api/v1/scraper/download",
            json={
                "base_url": "https://example.org",
                "manga": {"id": "demo", "title": "Demo", "url": "https://example.org/manga/demo/"},
                "chapter": {"id": "ch-1", "title": "CH1", "url": "https://example.org/manga/demo/ch-1/"},
            },
        )
        assert resp.status_code == 200
        task_id = resp.json()["task_id"]

        task_resp = client.get(f"/api/v1/scraper/task/{task_id}")
        assert task_resp.status_code == 200
        assert task_resp.json()["persisted"] is True

        v1_scraper._scraper_tasks.clear()
        reloaded_resp = client.get(f"/api/v1/scraper/task/{task_id}")
        assert reloaded_resp.status_code == 200
        assert reloaded_resp.json()["status"] == "success"
        assert reloaded_resp.json()["persisted"] is True


def test_generic_playwright_missing_returns_structured_error(monkeypatch: pytest.MonkeyPatch, phase2_app):
    def _raise_browser_missing(url: str, user_agent: str, timeout_ms: int = 25000):
        _ = (url, user_agent, timeout_ms)
        raise generic_provider.BrowserUnavailableError("playwright not installed")

    monkeypatch.setattr(generic_provider, "_fetch_html_playwright_sync", _raise_browser_missing)

    with TestClient(phase2_app) as client:
        resp = client.post(
            "/api/v1/scraper/search",
            json={
                "base_url": "https://example.org",
                "keyword": "demo",
                "force_engine": "playwright",
            },
        )
        assert resp.status_code == 400
        payload = resp.json()
        assert payload["detail"]["code"] == "SCRAPER_BROWSER_UNAVAILABLE"


def test_parser_list_generic_downloadable(monkeypatch: pytest.MonkeyPatch, phase2_app):
    html = """
    <html>
      <body>
        <a href="/comic/demo-1/">Demo One</a>
        <p>Paragraph one for parser output test.</p>
      </body>
    </html>
    """
    monkeypatch.setattr(v1_parser, "_fetch_html", lambda url, mode="http": html)

    with TestClient(phase2_app) as client:
        resp = client.post(
            "/api/v1/parser/list",
            json={"url": "https://example.org/comic/", "mode": "http"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["site"] == "generic"
        assert data["recognized"] is False
        assert data["downloadable"] is True
        assert len(data["items"]) >= 1


def test_task_status_backward_compatible_fields(phase2_app):
    store = v1_scraper._get_task_store()
    store.create_task(
        "phase2-compat",
        status="success",
        message="done",
        request_payload={"base_url": "https://example.org"},
        provider="generic",
    )
    store.update_task(
        "phase2-compat",
        status="success",
        message="done",
        report={"success_count": 1, "failed_count": 0, "total_count": 1},
        finished=True,
    )

    with TestClient(phase2_app) as client:
        resp = client.get("/api/v1/scraper/task/phase2-compat")
        assert resp.status_code == 200
        payload = resp.json()

        # Phase2 core fields remain unchanged.
        assert payload["task_id"] == "phase2-compat"
        assert payload["status"] == "success"
        assert payload["persisted"] is True
        assert payload["report"]["success_count"] == 1

        # Phase3 optional fields may appear, but should keep safe defaults.
        assert payload.get("retry_count", 0) == 0
        assert payload.get("max_retries", 2) >= 2
