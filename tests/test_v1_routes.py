from __future__ import annotations

import asyncio
import json
from datetime import datetime, timezone
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from manga_translator.server.core.account_service import AccountService
from manga_translator.server.core.middleware import init_middleware_services, require_auth
from manga_translator.server.core.models import Session
from manga_translator.server.core.permission_service import PermissionService
from manga_translator.server.core.session_service import SessionService
import manga_translator.server.routes.v1_manga as v1_manga
import manga_translator.server.routes.v1_parser as v1_parser
import manga_translator.server.routes.v1_scraper as v1_scraper
import manga_translator.server.routes.v1_translate as v1_translate
import manga_translator.server.routes.web as web


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.fixture
def sample_data(tmp_path: Path):
    data_root = tmp_path / "data"
    raw_dir = data_root / "raw"
    results_dir = data_root / "results"
    raw_dir.mkdir(parents=True, exist_ok=True)
    results_dir.mkdir(parents=True, exist_ok=True)

    chapter_dir = raw_dir / "demo_manga" / "chapter_1"
    chapter_dir.mkdir(parents=True, exist_ok=True)
    (chapter_dir / "001.jpg").write_bytes(b"demo-image")

    dist_dir = tmp_path / "dist"
    dist_dir.mkdir(parents=True, exist_ok=True)
    (dist_dir / "index.html").write_text("<html><body>spa-index</body></html>", encoding="utf-8")

    return {
        "tmp_path": tmp_path,
        "data_root": data_root,
        "raw_dir": raw_dir,
        "results_dir": results_dir,
        "dist_dir": dist_dir,
    }


@pytest.fixture
def patch_services(monkeypatch: pytest.MonkeyPatch, sample_data):
    raw_dir = sample_data["raw_dir"]
    results_dir = sample_data["results_dir"]

    # Patch manga/translate services to use temp dirs.
    v1_manga.library_service.raw_dir = raw_dir
    v1_manga.library_service.results_dir = results_dir
    v1_translate.library_service.raw_dir = raw_dir
    v1_translate.library_service.results_dir = results_dir

    # Patch scraper storage dirs.
    v1_scraper.DATA_DIR = sample_data["data_root"]
    v1_scraper.RAW_DIR = raw_dir
    v1_scraper.STATE_DIR = sample_data["data_root"] / "state"
    v1_scraper.TASK_DB_PATH = sample_data["data_root"] / "scraper_tasks.db"
    v1_scraper.init_task_store(v1_scraper.TASK_DB_PATH)
    v1_scraper._scraper_tasks.clear()

    # Patch SPA dist path.
    web.dist_dir = str(sample_data["dist_dir"])


@pytest.fixture
def authed_app(patch_services):
    app = FastAPI()
    app.include_router(v1_manga.router)
    app.include_router(v1_translate.router)
    app.include_router(v1_scraper.router)
    app.include_router(v1_parser.router)
    app.include_router(web.router)

    fake_session = Session(
        session_id="s1",
        username="tester",
        role="admin",
        token="token-1",
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


@pytest.fixture
def real_auth_app(patch_services, tmp_path: Path):
    # Initialize real middleware services for auth regression checks.
    accounts = AccountService(accounts_file=str(tmp_path / "accounts.json"))
    accounts.create_user("admin", "123456", "admin")
    sessions = SessionService(
        sessions_file=str(tmp_path / "sessions.json"),
        enable_persistence=False,
        session_timeout_minutes=60,
    )
    permissions = PermissionService(accounts)
    init_middleware_services(accounts, sessions, permissions)

    app = FastAPI()
    app.include_router(v1_manga.router)
    app.include_router(v1_scraper.router)

    return {
        "app": app,
        "sessions": sessions,
    }


def test_spa_routes_return_index(authed_app):
    with TestClient(authed_app) as client:
        for path in ["/", "/signin", "/admin", "/scraper", "/manga/demo", "/read/demo/ch1"]:
            response = client.get(path)
            assert response.status_code == 200
            assert "spa-index" in response.text

        redirect = client.get("/static/login.html", follow_redirects=False)
        assert redirect.status_code == 307
        assert redirect.headers["location"] == "/signin"


def test_v1_manga_routes(authed_app):
    with TestClient(authed_app) as client:
        resp = client.get("/api/v1/manga")
        assert resp.status_code == 200
        mangas = resp.json()
        assert len(mangas) == 1
        assert mangas[0]["id"] == "demo_manga"

        chapters = client.get("/api/v1/manga/demo_manga/chapters")
        assert chapters.status_code == 200
        assert chapters.json()[0]["id"] == "chapter_1"

        chapter = client.get("/api/v1/manga/demo_manga/chapter/chapter_1")
        assert chapter.status_code == 200
        data = chapter.json()
        assert data["manga_id"] == "demo_manga"
        assert data["chapter_id"] == "chapter_1"
        assert len(data["pages"]) == 1


@pytest.mark.anyio
async def test_translate_chapter_emits_events(monkeypatch: pytest.MonkeyPatch, patch_services):
    async def _fake_translate(image_path, output_path, source_language, target_language):
        _ = (image_path, source_language, target_language)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_bytes(b"translated")
        return {"output_path": str(output_path), "regions_count": 1}

    monkeypatch.setattr(v1_translate, "_translate_single_image", _fake_translate)

    queue: asyncio.Queue[str] = asyncio.Queue()
    v1_translate.v1_event_bus.add_listener(queue)

    req = v1_translate.ChapterTranslateRequest(manga_id="demo_manga", chapter_id="chapter_1")
    await v1_translate._process_chapter_job(req)

    events = []
    while not queue.empty():
        raw = await queue.get()
        payload = json.loads(raw.removeprefix("data: ").strip())
        events.append(payload)

    v1_translate.v1_event_bus.remove_listener(queue)

    event_types = [item["type"] for item in events]
    assert "chapter_start" in event_types
    assert "progress" in event_types
    assert "chapter_complete" in event_types

    final = [item for item in events if item["type"] == "chapter_complete"][-1]
    assert final["status"] == "success"
    assert final["success_count"] == 1


def test_translate_routes_with_auth_override(monkeypatch: pytest.MonkeyPatch, authed_app):
    async def _fake_translate(image_path, output_path, source_language, target_language):
        _ = (image_path, source_language, target_language)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_bytes(b"translated")
        return {"output_path": str(output_path), "regions_count": 1}

    monkeypatch.setattr(v1_translate, "_translate_single_image", _fake_translate)

    with TestClient(authed_app) as client:
        chapter_resp = client.post(
            "/api/v1/translate/chapter",
            json={"manga_id": "demo_manga", "chapter_id": "chapter_1"},
        )
        assert chapter_resp.status_code == 200
        assert chapter_resp.json()["page_count"] == 1

        page_resp = client.post(
            "/api/v1/translate/page",
            json={
                "manga_id": "demo_manga",
                "chapter_id": "chapter_1",
                "image_name": "001.jpg",
            },
        )
        assert page_resp.status_code == 200
        assert page_resp.json()["status"] == "completed"


def test_scraper_routes(monkeypatch: pytest.MonkeyPatch, authed_app):
    async def _fake_search(base_url, keyword, cookies, user_agent, http_mode, force_engine):
        _ = (base_url, keyword, cookies, user_agent, http_mode, force_engine)
        return [v1_scraper.MangaPayload(id="demo", title="Demo", url="https://example.com/manga/demo/")]

    async def _fake_catalog(base_url, page, orderby, path, cookies, user_agent, http_mode, force_engine):
        _ = (base_url, page, orderby, path, cookies, user_agent, http_mode, force_engine)
        return ([v1_scraper.MangaPayload(id="demo", title="Demo", url="https://example.com/manga/demo/")], False)

    async def _fake_chapters(base_url, manga_url, cookies, user_agent, http_mode, force_engine):
        _ = (base_url, manga_url, cookies, user_agent, http_mode, force_engine)
        return [v1_scraper.ChapterPayload(id="chapter-1", title="Chapter 1", url=f"{manga_url}chapter-1", index=1)]

    async def _fake_reader_images(base_url, chapter_url, cookies, user_agent, http_mode, force_engine):
        _ = (base_url, chapter_url, cookies, user_agent, http_mode, force_engine)
        return ["https://example.com/img-1.jpg"]

    provider = v1_scraper.ProviderAdapter(
        key="generic",
        label="Generic",
        hosts=(),
        supports_http=True,
        supports_playwright=True,
        supports_custom_host=True,
        default_catalog_path="/manga/",
        search=_fake_search,
        catalog=_fake_catalog,
        chapters=_fake_chapters,
        reader_images=_fake_reader_images,
        auth_url="https://example.com",
    )

    def _fake_resolve_provider(base_url, site_hint):
        _ = site_hint
        if not base_url:
            raise v1_scraper.ProviderUnavailableError("invalid base_url")
        return provider

    async def _fake_run_download(task_id, req, provider_obj, base_url, cookies, user_agent, force_engine):
        _ = (req, provider_obj, base_url, cookies, user_agent, force_engine)
        v1_scraper._scraper_tasks[task_id].update(
            {
                "status": "success",
                "message": "下载完成",
                "report": {"success_count": 1, "failed_count": 0, "total_count": 1},
            }
        )
        v1_scraper._get_task_store().update_task(
            task_id,
            status="success",
            message="下载完成",
            report={"success_count": 1, "failed_count": 0, "total_count": 1},
            finished=True,
        )

    monkeypatch.setattr(v1_scraper, "resolve_provider", _fake_resolve_provider)
    monkeypatch.setattr(v1_scraper, "_run_download_task", _fake_run_download)

    with TestClient(authed_app) as client:
        search_resp = client.post(
            "/api/v1/scraper/search",
            json={"base_url": "https://example.com", "keyword": "demo"},
        )
        assert search_resp.status_code == 200
        assert search_resp.json()[0]["id"] == "demo"

        catalog_resp = client.post(
            "/api/v1/scraper/catalog",
            json={"base_url": "https://example.com", "page": 1},
        )
        assert catalog_resp.status_code == 200
        assert catalog_resp.json()["items"][0]["id"] == "demo"

        chapters_resp = client.post(
            "/api/v1/scraper/chapters",
            json={
                "base_url": "https://example.com",
                "manga": {"id": "demo", "title": "Demo", "url": "https://example.com/manga/demo/"},
            },
        )
        assert chapters_resp.status_code == 200
        assert chapters_resp.json()[0]["id"] == "chapter-1"

        download_resp = client.post(
            "/api/v1/scraper/download",
            json={
                "base_url": "https://example.com",
                "manga": {"id": "demo", "title": "Demo", "url": "https://example.com/manga/demo/"},
                "chapter": {"id": "chapter-1", "title": "Chapter 1", "url": "https://example.com/manga/demo/chapter-1"},
            },
        )
        assert download_resp.status_code == 200
        task_id = download_resp.json()["task_id"]

        task_resp = client.get(f"/api/v1/scraper/task/{task_id}")
        assert task_resp.status_code == 200
        assert task_resp.json()["task_id"] == task_id
        assert task_resp.json()["persisted"] is True

        unsupported_resp = client.post(
            "/api/v1/scraper/search",
            json={"base_url": "", "keyword": "demo"},
        )
        assert unsupported_resp.status_code == 400
        assert unsupported_resp.json()["detail"]["code"] == "SCRAPER_PROVIDER_UNAVAILABLE"


def test_parser_routes(monkeypatch: pytest.MonkeyPatch, authed_app):
    html = """
    <html>
      <head>
        <title>Demo Manga</title>
        <meta property='og:title' content='Demo Manga Title' />
        <meta property='og:image' content='https://mangaforfree.com/cover.jpg' />
      </head>
      <body>
        <a href='/manga/demo-1/'>Demo One</a>
        <p>First paragraph with enough length for parser output.</p>
        <p>Second paragraph with enough length for parser output.</p>
      </body>
    </html>
    """

    monkeypatch.setattr(v1_parser, "_fetch_html", lambda url, mode='http': html)

    with TestClient(authed_app) as client:
        parse_resp = client.post("/api/v1/parser/parse", json={"url": "https://mangaforfree.com/manga/demo-1/", "mode": "http"})
        assert parse_resp.status_code == 200
        assert parse_resp.json()["title"] == "Demo Manga Title"
        assert len(parse_resp.json()["paragraphs"]) >= 2

        list_resp = client.post("/api/v1/parser/list", json={"url": "https://mangaforfree.com/manga/", "mode": "http"})
        assert list_resp.status_code == 200
        payload = list_resp.json()
        assert payload["page_type"] == "list"
        assert payload["recognized"] is True
        assert len(payload["items"]) >= 1


def test_auth_regression_protected_v1(real_auth_app):
    app = real_auth_app["app"]
    sessions: SessionService = real_auth_app["sessions"]

    with TestClient(app) as client:
        unauth = client.get("/api/v1/manga")
        assert unauth.status_code == 401
        unauth_scraper = client.get("/api/v1/scraper/providers")
        assert unauth_scraper.status_code == 401

        session = sessions.create_session("admin", "admin", "127.0.0.1", "pytest")
        authed = client.get("/api/v1/manga", headers={"X-Session-Token": session.token})
        assert authed.status_code == 200
        authed_scraper = client.get("/api/v1/scraper/providers", headers={"X-Session-Token": session.token})
        assert authed_scraper.status_code == 200
