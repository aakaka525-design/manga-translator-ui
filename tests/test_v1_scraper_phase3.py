from __future__ import annotations

import asyncio
import sqlite3
import sys
import types
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from manga_translator.server.core.middleware import require_admin, require_auth
from manga_translator.server.core.models import Session

# admin routes depend on Config import from manga_translator package.
# Stub it in tests to avoid pulling optional runtime-only dependencies.
import manga_translator as mt_pkg


class _DummyConfig:
    @classmethod
    def model_validate(cls, _obj):
        return cls()

    @classmethod
    def parse_raw(cls, _raw):
        return cls()


sys.modules.setdefault("py3langid", types.SimpleNamespace(classify=lambda text: ("en", 1.0)))
mt_pkg.Config = _DummyConfig
sys.modules.setdefault(
    "manga_translator.utils",
    types.SimpleNamespace(BASE_PATH=str(Path(__file__).resolve().parents[1])),
)

import manga_translator.server.routes.admin as admin_routes
import manga_translator.server.routes.v1_scraper as v1_scraper


@pytest.fixture
def phase3_data(tmp_path: Path):
    root = tmp_path / "phase3_data"
    raw_dir = root / "raw"
    raw_dir.mkdir(parents=True, exist_ok=True)
    state_dir = root / "state"
    state_dir.mkdir(parents=True, exist_ok=True)
    db_path = root / "scraper_tasks.db"
    return {"root": root, "raw_dir": raw_dir, "state_dir": state_dir, "db_path": db_path}


@pytest.fixture
def phase3_app(phase3_data):
    v1_scraper.DATA_DIR = phase3_data["root"]
    v1_scraper.RAW_DIR = phase3_data["raw_dir"]
    v1_scraper.STATE_DIR = phase3_data["state_dir"]
    v1_scraper.TASK_DB_PATH = phase3_data["db_path"]
    v1_scraper.init_task_store(phase3_data["db_path"])
    v1_scraper._scraper_tasks.clear()

    app = FastAPI()
    app.include_router(v1_scraper.router)

    admin_session = Session(
        session_id="phase3-admin",
        username="admin",
        role="admin",
        token="phase3-token",
        created_at=datetime.now(timezone.utc),
        last_activity=datetime.now(timezone.utc),
        ip_address="127.0.0.1",
        user_agent="pytest",
        is_active=True,
    )

    async def _fake_auth():
        return admin_session

    app.dependency_overrides[require_auth] = _fake_auth
    return app


@pytest.fixture
def phase3_admin_app(phase3_data):
    v1_scraper.DATA_DIR = phase3_data["root"]
    v1_scraper.RAW_DIR = phase3_data["raw_dir"]
    v1_scraper.STATE_DIR = phase3_data["state_dir"]
    v1_scraper.TASK_DB_PATH = phase3_data["db_path"]
    v1_scraper.init_task_store(phase3_data["db_path"])
    v1_scraper._scraper_tasks.clear()

    app = FastAPI()
    app.include_router(admin_routes.router)

    admin_session = Session(
        session_id="phase3-admin-2",
        username="admin",
        role="admin",
        token="phase3-token-2",
        created_at=datetime.now(timezone.utc),
        last_activity=datetime.now(timezone.utc),
        ip_address="127.0.0.1",
        user_agent="pytest",
        is_active=True,
    )

    async def _fake_auth():
        return admin_session

    async def _fake_admin():
        return admin_session

    app.dependency_overrides[require_auth] = _fake_auth
    app.dependency_overrides[require_admin] = _fake_admin
    return app


def _provider_stub():
    async def _noop_search(base_url, keyword, cookies, user_agent, http_mode, force_engine):
        _ = (base_url, keyword, cookies, user_agent, http_mode, force_engine)
        return []

    async def _noop_catalog(base_url, page, orderby, path, cookies, user_agent, http_mode, force_engine):
        _ = (base_url, page, orderby, path, cookies, user_agent, http_mode, force_engine)
        return [], False

    async def _noop_chapters(base_url, manga_url, cookies, user_agent, http_mode, force_engine):
        _ = (base_url, manga_url, cookies, user_agent, http_mode, force_engine)
        return []

    async def _noop_reader(base_url, chapter_url, cookies, user_agent, http_mode, force_engine):
        _ = (base_url, chapter_url, cookies, user_agent, http_mode, force_engine)
        return []

    return v1_scraper.ProviderAdapter(
        key="generic",
        label="Generic",
        hosts=(),
        supports_http=True,
        supports_playwright=True,
        supports_custom_host=True,
        default_catalog_path="/manga/",
        search=_noop_search,
        catalog=_noop_catalog,
        chapters=_noop_chapters,
        reader_images=_noop_reader,
        auth_url="https://example.org",
    )


def test_task_store_migration_columns(phase3_app):
    _ = phase3_app
    store = v1_scraper._get_task_store()
    conn = sqlite3.connect(store.db_path)
    try:
        rows = conn.execute("PRAGMA table_info(scraper_tasks)").fetchall()
    finally:
        conn.close()

    columns = {row[1] for row in rows}
    assert "retry_count" in columns
    assert "max_retries" in columns
    assert "next_retry_at" in columns
    assert "last_error" in columns
    assert "request_fingerprint" in columns
    assert "started_at" in columns


def test_download_idempotent_existing_task(monkeypatch: pytest.MonkeyPatch, phase3_app):
    provider = _provider_stub()

    async def _fake_run_download(*args, **kwargs):
        _ = (args, kwargs)
        return None

    monkeypatch.setattr(v1_scraper, "resolve_provider", lambda base_url, site_hint: provider)
    monkeypatch.setattr(v1_scraper, "_run_download_task", _fake_run_download)

    payload = {
        "base_url": "https://example.org",
        "manga": {"id": "demo", "title": "Demo", "url": "https://example.org/manga/demo/"},
        "chapter": {"id": "ch-1", "title": "CH1", "url": "https://example.org/manga/demo/ch-1/"},
    }

    with TestClient(phase3_app) as client:
        first = client.post("/api/v1/scraper/download", json=payload)
        assert first.status_code == 200
        task_id = first.json()["task_id"]

        second = client.post("/api/v1/scraper/download", json=payload)
        assert second.status_code == 200
        data = second.json()
        assert data["task_id"] == task_id
        assert data["status"] == "existing"
        assert data["error_code"] == "SCRAPER_TASK_DUPLICATE"


def test_task_status_contains_retry_fields(phase3_app):
    store = v1_scraper._get_task_store()
    store.create_task(
        "phase3-task-1",
        status="retrying",
        message="下载重试中",
        request_payload={"base_url": "https://example.org"},
        provider="generic",
        max_retries=2,
        request_fingerprint="fp-1",
    )
    store.update_task(
        "phase3-task-1",
        status="error",
        message="达到重试上限",
        report={"success_count": 0, "failed_count": 1, "total_count": 1},
        retry_count=2,
        max_retries=2,
        error_code="SCRAPER_RETRY_EXHAUSTED",
        last_error="network timeout",
        finished=True,
    )

    with TestClient(phase3_app) as client:
        resp = client.get("/api/v1/scraper/task/phase3-task-1")
        assert resp.status_code == 200
        data = resp.json()
        assert data["retry_count"] == 2
        assert data["max_retries"] == 2
        assert data["error_code"] == "SCRAPER_RETRY_EXHAUSTED"
        assert data["last_error"] == "network timeout"
        assert data["queue_status"] == "failed"
        assert data["worker_id"] == "local-worker"


def test_recover_stale_tasks_marks_error(phase3_app):
    store = v1_scraper._get_task_store()
    store.create_task(
        "phase3-stale",
        status="running",
        message="下载中",
        request_payload={"base_url": "https://example.org"},
        provider="generic",
        max_retries=2,
        request_fingerprint="fp-stale",
    )

    stale_at = (datetime.now(timezone.utc) - timedelta(minutes=30)).isoformat()
    conn = sqlite3.connect(store.db_path)
    try:
        conn.execute("UPDATE scraper_tasks SET updated_at = ? WHERE task_id = ?", (stale_at, "phase3-stale"))
        conn.commit()
    finally:
        conn.close()

    changed = v1_scraper.recover_stale_tasks(stale_minutes=10)
    assert changed == 1

    record = store.get_task("phase3-stale")
    assert record is not None
    assert record.status == "error"
    assert record.error_code == "SCRAPER_TASK_STALE"


def test_admin_scraper_tasks_and_metrics(phase3_admin_app):
    store = v1_scraper._get_task_store()
    store.create_task(
        "phase3-admin-ok",
        status="success",
        message="下载完成",
        request_payload={"base_url": "https://toongod.org"},
        provider="toongod",
        max_retries=2,
        request_fingerprint="fp-admin-1",
    )
    store.update_task(
        "phase3-admin-ok",
        status="success",
        message="下载完成",
        report={"success_count": 1, "failed_count": 0, "total_count": 1},
        retry_count=0,
        max_retries=2,
        finished=True,
    )

    store.create_task(
        "phase3-admin-err",
        status="error",
        message="失败",
        request_payload={"base_url": "https://example.org"},
        provider="generic",
        max_retries=2,
        request_fingerprint="fp-admin-2",
    )
    store.update_task(
        "phase3-admin-err",
        status="error",
        message="失败",
        retry_count=2,
        max_retries=2,
        error_code="SCRAPER_RETRY_EXHAUSTED",
        last_error="timeout",
        finished=True,
    )

    with TestClient(phase3_admin_app) as client:
        tasks_resp = client.get("/admin/scraper/tasks", params={"provider": "generic", "limit": 10, "offset": 0})
        assert tasks_resp.status_code == 200
        tasks_data = tasks_resp.json()
        assert tasks_data["total"] >= 1
        assert all(item["provider"] == "generic" for item in tasks_data["items"])

        metrics_resp = client.get("/admin/scraper/metrics", params={"hours": 24})
        assert metrics_resp.status_code == 200
        metrics = metrics_resp.json()
        assert metrics["total"] >= 2
        assert "provider_breakdown" in metrics
        assert "error_code_breakdown" in metrics


def test_admin_scraper_auth_requires_admin(phase3_data):
    v1_scraper.TASK_DB_PATH = phase3_data["db_path"]
    v1_scraper.init_task_store(phase3_data["db_path"])

    app = FastAPI()
    app.include_router(admin_routes.router)

    user_session = Session(
        session_id="phase3-user",
        username="user",
        role="user",
        token="phase3-user-token",
        created_at=datetime.now(timezone.utc),
        last_activity=datetime.now(timezone.utc),
        ip_address="127.0.0.1",
        user_agent="pytest",
        is_active=True,
    )

    async def _fake_auth():
        return user_session

    app.dependency_overrides[require_auth] = _fake_auth

    with TestClient(app) as client:
        resp = client.get("/admin/scraper/tasks")
        assert resp.status_code == 403


def test_task_store_list_and_metrics_methods(phase3_app):
    _ = phase3_app
    store = v1_scraper._get_task_store()
    store.create_task(
        "phase3-metrics-1",
        status="success",
        message="ok",
        request_payload={"base_url": "https://toongod.org"},
        provider="toongod",
        max_retries=2,
        request_fingerprint="fp-m-1",
    )
    store.update_task(
        "phase3-metrics-1",
        status="success",
        message="ok",
        retry_count=0,
        max_retries=2,
        finished=True,
    )

    items, total = store.list_tasks(status=None, provider=None, limit=20, offset=0)
    assert total >= 1
    assert any(item.task_id == "phase3-metrics-1" for item in items)

    metrics = store.metrics(hours=24)
    assert metrics["total"] >= 1
    assert "toongod" in metrics["provider_breakdown"]


@pytest.mark.asyncio
async def test_download_retry_exhausted(monkeypatch: pytest.MonkeyPatch, phase3_app):
    provider = _provider_stub()

    async def _reader_images(base_url, chapter_url, cookies, user_agent, http_mode, force_engine):
        _ = (base_url, chapter_url, cookies, user_agent, http_mode, force_engine)
        return ["https://example.org/a.jpg"]

    provider = provider.__class__(
        key=provider.key,
        label=provider.label,
        hosts=provider.hosts,
        supports_http=provider.supports_http,
        supports_playwright=provider.supports_playwright,
        supports_custom_host=provider.supports_custom_host,
        default_catalog_path=provider.default_catalog_path,
        search=provider.search,
        catalog=provider.catalog,
        chapters=provider.chapters,
        reader_images=_reader_images,
        auth_url=provider.auth_url,
    )

    async def _always_fail_download(*args, **kwargs):
        _ = (args, kwargs)
        return False, "network timeout"

    monkeypatch.setattr(v1_scraper, "resolve_provider", lambda base_url, site_hint: provider)
    monkeypatch.setattr(v1_scraper, "_download_image", _always_fail_download)
    monkeypatch.setattr(v1_scraper, "TASK_RETRY_DELAY_SEC", 0.01)

    with TestClient(phase3_app) as client:
        resp = client.post(
            "/api/v1/scraper/download",
            json={
                "base_url": "https://example.org",
                "manga": {"id": "retry-demo", "title": "Demo", "url": "https://example.org/manga/retry-demo/"},
                "chapter": {"id": "ch-1", "title": "CH1", "url": "https://example.org/manga/retry-demo/ch-1/"},
            },
        )
        assert resp.status_code == 200
        task_id = resp.json()["task_id"]

        # Wait for async retries to finish.
        for _ in range(100):
            payload = client.get(f"/api/v1/scraper/task/{task_id}").json()
            if payload["status"] in {"error", "success", "partial"}:
                break
            await asyncio.sleep(0.05)

        payload = client.get(f"/api/v1/scraper/task/{task_id}").json()
        assert payload["status"] == "error"
        assert payload["error_code"] == "SCRAPER_RETRY_EXHAUSTED"
        assert payload["retry_count"] == payload["max_retries"]
