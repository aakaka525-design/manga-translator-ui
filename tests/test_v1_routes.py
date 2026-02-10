from __future__ import annotations

import asyncio
import io
import json
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace

import aiohttp
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from PIL import Image

from manga_translator.server.core.account_service import AccountService
from manga_translator.server.core.middleware import init_middleware_services, require_auth
from manga_translator.server.core.models import Session
from manga_translator.server.core.permission_service import PermissionService
from manga_translator.server.core.session_service import SessionService
import manga_translator.server.routes.v1_manga as v1_manga
import manga_translator.server.routes.v1_parser as v1_parser
import manga_translator.server.routes.v1_scraper as v1_scraper
import manga_translator.server.routes.v1_settings as v1_settings
import manga_translator.server.routes.v1_system as v1_system
import manga_translator.server.routes.v1_translate as v1_translate
import manga_translator.server.routes.web as web
from manga_translator.server.core.logging_manager import global_log_queue


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

    # Patch v1 settings storage path.
    v1_settings.SETTINGS_FILE = sample_data["data_root"] / "user_settings.json"

    # Patch SPA dist path.
    web.dist_dir = str(sample_data["dist_dir"])


@pytest.fixture
def authed_app(patch_services):
    app = FastAPI()
    app.include_router(v1_manga.router)
    app.include_router(v1_translate.router)
    app.include_router(v1_scraper.router)
    app.include_router(v1_parser.router)
    app.include_router(v1_settings.router)
    app.include_router(v1_system.router)
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
    app.include_router(v1_settings.router)
    app.include_router(v1_system.router)

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


def test_v1_manga_routes_ignore_identical_result_copy(authed_app, sample_data):
    translated = sample_data["results_dir"] / "demo_manga" / "chapter_1" / "001.jpg"
    translated.parent.mkdir(parents=True, exist_ok=True)
    translated.write_bytes((sample_data["raw_dir"] / "demo_manga" / "chapter_1" / "001.jpg").read_bytes())

    with TestClient(authed_app) as client:
        chapter = client.get("/api/v1/manga/demo_manga/chapter/chapter_1")
        assert chapter.status_code == 200
        payload = chapter.json()
        assert payload["pages"][0]["translated_url"] is None
        assert payload["pages"][0]["status"] == "pending"


def test_v1_manga_routes_output_url_contains_cache_buster(authed_app, sample_data):
    translated = sample_data["results_dir"] / "demo_manga" / "chapter_1" / "001.jpg"
    translated.parent.mkdir(parents=True, exist_ok=True)
    translated.write_bytes(b"translated-image")

    with TestClient(authed_app) as client:
        chapter = client.get("/api/v1/manga/demo_manga/chapter/chapter_1")
        assert chapter.status_code == 200
        payload = chapter.json()
        translated_url = payload["pages"][0]["translated_url"]
        assert translated_url is not None
        assert translated_url.startswith("/output/demo_manga/chapter_1/001.jpg?v=")
        assert payload["pages"][0]["status"] == "translated"


def test_translate_target_language_normalization():
    assert v1_translate._resolve_target_language(None) == "CHS"
    assert v1_translate._resolve_target_language("  ") == "CHS"
    assert v1_translate._resolve_target_language("zh") == "CHS"
    assert v1_translate._resolve_target_language("zh-CN") == "CHS"
    assert v1_translate._resolve_target_language("zh_TW") == "CHT"
    assert v1_translate._resolve_target_language("en") == "ENG"
    assert v1_translate._resolve_target_language("JPN") == "JPN"


@pytest.mark.anyio
async def test_translate_single_image_caps_retry_attempts_and_normalizes_target(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
):
    source_path = tmp_path / "source.jpg"
    output_path = tmp_path / "output.jpg"

    img = Image.new("RGB", (8, 8), color=(240, 240, 240))
    img.save(source_path)

    class _TranslatorConfig:
        attempts = -1
        target_lang = "ENG"
        skip_lang = None

    class _Config:
        translator = _TranslatorConfig()

    captured: dict[str, object] = {}

    def _fake_load_default_config():
        return _Config()

    async def _fake_build_translate_context(_request, config, payload):
        captured["attempts"] = config.translator.attempts
        captured["target_lang"] = config.translator.target_lang
        with Image.open(io.BytesIO(payload)) as payload_img:
            result_img = payload_img.convert("RGB")
        return SimpleNamespace(result=result_img, text_regions=[object()])

    monkeypatch.setattr(
        "manga_translator.server.core.config_manager.load_default_config",
        _fake_load_default_config,
    )
    monkeypatch.setattr(v1_translate, "_build_translate_context", _fake_build_translate_context)

    result = await v1_translate._translate_single_image(source_path, output_path, None, "zh")

    assert output_path.exists()
    assert captured["attempts"] == v1_translate.TRANSLATE_MAX_ATTEMPTS
    assert captured["target_lang"] == "CHS"
    assert result["fallback_used"] is False
    assert result["regions_count"] == 1


@pytest.mark.anyio
async def test_translate_single_image_converts_rgba_result_for_jpeg_output(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
):
    source_path = tmp_path / "source.jpg"
    output_path = tmp_path / "output.jpg"

    src = Image.new("RGB", (8, 8), color=(240, 240, 240))
    src.save(source_path)

    class _TranslatorConfig:
        attempts = 1
        target_lang = "ENG"
        skip_lang = None

    class _Config:
        translator = _TranslatorConfig()

    def _fake_load_default_config():
        return _Config()

    async def _fake_build_translate_context(_request, _config, _payload):
        result_img = Image.new("RGBA", (8, 8), color=(255, 0, 0, 180))
        return SimpleNamespace(result=result_img, text_regions=[object()])

    monkeypatch.setattr(
        "manga_translator.server.core.config_manager.load_default_config",
        _fake_load_default_config,
    )
    monkeypatch.setattr(v1_translate, "_build_translate_context", _fake_build_translate_context)

    result = await v1_translate._translate_single_image(source_path, output_path, "en", "zh")

    assert output_path.exists()
    assert result["fallback_used"] is False
    assert result["regions_count"] == 1
    assert result["output_changed"] is True
    with Image.open(output_path) as out:
        assert out.mode == "RGB"


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


@pytest.mark.anyio
async def test_translate_chapter_fallback_result_is_not_counted_as_success(
    monkeypatch: pytest.MonkeyPatch, patch_services
):
    async def _fake_translate(image_path, output_path, source_language, target_language):
        _ = (image_path, source_language, target_language)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_bytes(b"raw-copy")
        return {
            "output_path": str(output_path),
            "regions_count": 0,
            "fallback_used": True,
            "fallback_reason": "missing runtime deps",
        }

    monkeypatch.setattr(v1_translate, "_translate_single_image", _fake_translate)

    stale_file = v1_translate.library_service.results_dir / "demo_manga" / "chapter_1" / "001.png"
    stale_file.parent.mkdir(parents=True, exist_ok=True)
    stale_file.write_bytes(b"stale-translated-image")

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

    final = [item for item in events if item["type"] == "chapter_complete"][-1]
    assert final["status"] == "error"
    assert final["success_count"] == 0
    assert final["failed_count"] == 1
    assert not (v1_translate.library_service.results_dir / "demo_manga" / "chapter_1" / "001.jpg").exists()
    assert not stale_file.exists()


@pytest.mark.anyio
async def test_translate_chapter_no_change_result_is_not_counted_as_success(
    monkeypatch: pytest.MonkeyPatch, patch_services
):
    async def _fake_translate(image_path, output_path, source_language, target_language):
        _ = (image_path, source_language, target_language)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_bytes(b"raw-copy")
        return {
            "output_path": str(output_path),
            "regions_count": 1,
            "output_changed": False,
            "no_change_reason": "no_text_regions_detected",
        }

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

    final = [item for item in events if item["type"] == "chapter_complete"][-1]
    assert final["status"] == "error"
    assert final["success_count"] == 0
    assert final["failed_count"] == 1
    assert not (v1_translate.library_service.results_dir / "demo_manga" / "chapter_1" / "001.jpg").exists()


@pytest.mark.anyio
async def test_translate_chapter_no_regions_result_is_not_counted_as_success(
    monkeypatch: pytest.MonkeyPatch, patch_services
):
    async def _fake_translate(image_path, output_path, source_language, target_language):
        _ = (image_path, source_language, target_language)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_bytes(b"visually-unchanged-but-reencoded")
        return {
            "output_path": str(output_path),
            "regions_count": 0,
            "output_changed": True,
        }

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

    final = [item for item in events if item["type"] == "chapter_complete"][-1]
    assert final["status"] == "error"
    assert final["success_count"] == 0
    assert final["failed_count"] == 1
    assert not (v1_translate.library_service.results_dir / "demo_manga" / "chapter_1" / "001.jpg").exists()


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


def test_translate_page_returns_503_when_fallback_used(monkeypatch: pytest.MonkeyPatch, authed_app):
    async def _fake_translate(image_path, output_path, source_language, target_language):
        _ = (image_path, source_language, target_language)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_bytes(b"raw-copy")
        return {
            "output_path": str(output_path),
            "regions_count": 0,
            "fallback_used": True,
            "fallback_reason": "missing runtime deps",
        }

    monkeypatch.setattr(v1_translate, "_translate_single_image", _fake_translate)

    with TestClient(authed_app) as client:
        stale_file = v1_translate.library_service.results_dir / "demo_manga" / "chapter_1" / "001.png"
        stale_file.parent.mkdir(parents=True, exist_ok=True)
        stale_file.write_bytes(b"stale-translated-image")
        page_resp = client.post(
            "/api/v1/translate/page",
            json={
                "manga_id": "demo_manga",
                "chapter_id": "chapter_1",
                "image_name": "001.jpg",
            },
        )
        assert page_resp.status_code == 503
        assert "fallback" in page_resp.json()["detail"]
        assert not stale_file.exists()


def test_translate_page_returns_409_when_output_has_no_visible_change(
    monkeypatch: pytest.MonkeyPatch, authed_app
):
    async def _fake_translate(image_path, output_path, source_language, target_language):
        _ = (image_path, source_language, target_language)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_bytes(b"raw-copy")
        return {
            "output_path": str(output_path),
            "regions_count": 1,
            "output_changed": False,
            "no_change_reason": "no_text_regions_detected",
        }

    monkeypatch.setattr(v1_translate, "_translate_single_image", _fake_translate)

    with TestClient(authed_app) as client:
        page_resp = client.post(
            "/api/v1/translate/page",
            json={
                "manga_id": "demo_manga",
                "chapter_id": "chapter_1",
                "image_name": "001.jpg",
            },
        )
        assert page_resp.status_code == 409
        assert "no visible changes" in page_resp.json()["detail"]


def test_translate_page_returns_409_when_no_text_regions_detected(
    monkeypatch: pytest.MonkeyPatch, authed_app
):
    async def _fake_translate(image_path, output_path, source_language, target_language):
        _ = (image_path, source_language, target_language)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_bytes(b"visually-unchanged-but-reencoded")
        return {
            "output_path": str(output_path),
            "regions_count": 0,
            "output_changed": True,
        }

    monkeypatch.setattr(v1_translate, "_translate_single_image", _fake_translate)

    with TestClient(authed_app) as client:
        page_resp = client.post(
            "/api/v1/translate/page",
            json={
                "manga_id": "demo_manga",
                "chapter_id": "chapter_1",
                "image_name": "001.jpg",
            },
        )
        assert page_resp.status_code == 409
        assert "no detected text regions" in page_resp.json()["detail"]


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

    async def _fake_run_download(task_id, req, provider_obj, base_url, cookies, user_agent, force_engine, **kwargs):
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


def test_scraper_routes_map_upstream_http_status(monkeypatch: pytest.MonkeyPatch, authed_app):
    async def _search_403(base_url, keyword, cookies, user_agent, http_mode, force_engine):
        _ = (base_url, keyword, cookies, user_agent, http_mode, force_engine)
        raise aiohttp.ClientResponseError(
            request_info=SimpleNamespace(real_url="https://toongod.org/search"),
            history=(),
            status=403,
            message="Forbidden",
            headers=None,
        )

    async def _catalog_403(base_url, page, orderby, path, cookies, user_agent, http_mode, force_engine):
        _ = (base_url, page, orderby, path, cookies, user_agent, http_mode, force_engine)
        raise aiohttp.ClientResponseError(
            request_info=SimpleNamespace(real_url="https://toongod.org/webtoon/"),
            history=(),
            status=403,
            message="Forbidden",
            headers=None,
        )

    async def _chapters_404(base_url, manga_url, cookies, user_agent, http_mode, force_engine):
        _ = (base_url, manga_url, cookies, user_agent, http_mode, force_engine)
        raise aiohttp.ClientResponseError(
            request_info=SimpleNamespace(real_url="https://mangaforfree.com/manga/not-found/"),
            history=(),
            status=404,
            message="Not Found",
            headers=None,
        )

    async def _unused_reader_images(base_url, chapter_url, cookies, user_agent, http_mode, force_engine):
        _ = (base_url, chapter_url, cookies, user_agent, http_mode, force_engine)
        return []

    provider = v1_scraper.ProviderAdapter(
        key="generic",
        label="Generic",
        hosts=(),
        supports_http=True,
        supports_playwright=True,
        supports_custom_host=True,
        default_catalog_path="/manga/",
        search=_search_403,
        catalog=_catalog_403,
        chapters=_chapters_404,
        reader_images=_unused_reader_images,
        auth_url="https://example.com",
    )

    monkeypatch.setattr(v1_scraper, "resolve_provider", lambda base_url, site_hint: provider)

    with TestClient(authed_app) as client:
        search_resp = client.post(
            "/api/v1/scraper/search",
            json={"base_url": "https://example.com", "keyword": "demo"},
        )
        assert search_resp.status_code == 403
        assert search_resp.json()["detail"]["code"] == "SCRAPER_AUTH_CHALLENGE"

        catalog_resp = client.post(
            "/api/v1/scraper/catalog",
            json={"base_url": "https://example.com", "page": 1},
        )
        assert catalog_resp.status_code == 403
        assert catalog_resp.json()["detail"]["code"] == "SCRAPER_AUTH_CHALLENGE"

        chapters_resp = client.post(
            "/api/v1/scraper/chapters",
            json={
                "base_url": "https://example.com",
                "manga": {"id": "demo", "title": "Demo", "url": "https://example.com/manga/demo/"},
            },
        )
        assert chapters_resp.status_code == 404
        assert chapters_resp.json()["detail"]["code"] == "SCRAPER_CHAPTERS_FAILED"


def test_v1_settings_routes(authed_app):
    with TestClient(authed_app) as client:
        initial = client.get("/api/v1/settings")
        assert initial.status_code == 200
        payload = initial.json()
        assert payload["ai_model"] == "zai-org/glm-4.7-flash"
        assert payload["source_language"] == "en"
        assert payload["target_language"] == "zh"

        model_resp = client.post("/api/v1/settings/model", json={"model": "gpt-4o"})
        assert model_resp.status_code == 200
        assert model_resp.json()["success"] is True

        upscale_resp = client.post(
            "/api/v1/settings/upscale",
            json={"model": "realesr-animevideov3-x4", "scale": 4, "enabled": False},
        )
        assert upscale_resp.status_code == 200
        assert upscale_resp.json()["success"] is True

        final = client.get("/api/v1/settings")
        assert final.status_code == 200
        final_payload = final.json()
        assert final_payload["ai_model"] == "gpt-4o"
        assert final_payload["upscale_model"] == "realesr-animevideov3-x4"
        assert final_payload["upscale_scale"] == 4
        assert final_payload["upscale_enable"] is False


def test_v1_system_logs_route(authed_app):
    global_log_queue.append(
        {
            "timestamp": "2026-02-10T00:00:00+00:00",
            "level": "INFO",
            "message": "routes smoke log",
        }
    )
    with TestClient(authed_app) as client:
        resp = client.get("/api/v1/system/logs?lines=1")
        assert resp.status_code == 200
        payload = resp.json()
        assert isinstance(payload, list)
        assert len(payload) == 1
        assert "routes smoke log" in payload[0]


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
        unauth_settings = client.get("/api/v1/settings")
        assert unauth_settings.status_code == 401
        unauth_system_logs = client.get("/api/v1/system/logs")
        assert unauth_system_logs.status_code == 401

        session = sessions.create_session("admin", "admin", "127.0.0.1", "pytest")
        authed = client.get("/api/v1/manga", headers={"X-Session-Token": session.token})
        assert authed.status_code == 200
        authed_scraper = client.get("/api/v1/scraper/providers", headers={"X-Session-Token": session.token})
        assert authed_scraper.status_code == 200
        authed_settings = client.get("/api/v1/settings", headers={"X-Session-Token": session.token})
        assert authed_settings.status_code == 200
        authed_system_logs = client.get("/api/v1/system/logs", headers={"X-Session-Token": session.token})
        assert authed_system_logs.status_code == 200
