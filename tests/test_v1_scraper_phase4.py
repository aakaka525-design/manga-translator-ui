from __future__ import annotations

import asyncio
import sqlite3
import sys
import time
import types
from datetime import datetime, timezone
from pathlib import Path

import aiohttp
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from manga_translator.server.core.middleware import require_admin, require_auth
from manga_translator.server.core.models import Session
from manga_translator.server.core.auth import valid_admin_tokens
from manga_translator.server.core.account_service import AccountService
from manga_translator.server.core.permission_service import PermissionService
from manga_translator.server.core.session_service import SessionService
from manga_translator.server.core.middleware import init_middleware_services
from manga_translator.server.core.logging_manager import global_log_queue

# Keep tests isolated from optional runtime-only dependencies.
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
import manga_translator.server.routes.v1_parser as v1_parser
import manga_translator.server.routes.v1_scraper as v1_scraper
from manga_translator.server.core.config_manager import DEFAULT_ADMIN_SETTINGS, admin_settings
from manga_translator.server.scraper_v1.alerts import ScraperAlertEngine


def _admin_session() -> Session:
    return Session(
        session_id="phase4-admin",
        username="admin",
        role="admin",
        token="phase4-token",
        created_at=datetime.now(timezone.utc),
        last_activity=datetime.now(timezone.utc),
        ip_address="127.0.0.1",
        user_agent="pytest",
        is_active=True,
    )


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

    async def _reader_images(base_url, chapter_url, cookies, user_agent, http_mode, force_engine):
        _ = (base_url, chapter_url, cookies, user_agent, http_mode, force_engine)
        return ["https://example.org/image-1.jpg"]

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
        reader_images=_reader_images,
        auth_url="https://example.org",
    )


@pytest.fixture
def phase4_data(tmp_path: Path):
    root = tmp_path / "phase4_data"
    raw_dir = root / "raw"
    state_dir = root / "state"
    raw_dir.mkdir(parents=True, exist_ok=True)
    state_dir.mkdir(parents=True, exist_ok=True)
    return {"root": root, "raw_dir": raw_dir, "state_dir": state_dir, "db_path": root / "scraper_tasks.db"}


@pytest.fixture
def phase4_config():
    old_value = admin_settings.get("scraper_alerts")
    admin_settings["scraper_alerts"] = {
        "enabled": True,
        "poll_interval_sec": 30,
        "cooldown_sec": 300,
        "threshold_backlog": 30,
        "threshold_error_rate": 0.25,
        "threshold_min_sample": 20,
        "webhook": {"enabled": False, "url": "", "timeout_sec": 5, "max_retries": 3},
    }
    yield admin_settings["scraper_alerts"]
    if old_value is None:
        admin_settings.pop("scraper_alerts", None)
    else:
        admin_settings["scraper_alerts"] = old_value


@pytest.fixture
def phase4_app(phase4_data, phase4_config):
    _ = phase4_config
    v1_scraper.DATA_DIR = phase4_data["root"]
    v1_scraper.RAW_DIR = phase4_data["raw_dir"]
    v1_scraper.STATE_DIR = phase4_data["state_dir"]
    v1_scraper.TASK_DB_PATH = phase4_data["db_path"]
    v1_scraper.init_task_store(phase4_data["db_path"])
    v1_scraper._scraper_tasks.clear()
    v1_scraper._alert_runtime.update(
        {
            "running": False,
            "enabled": True,
            "poll_interval_sec": 30,
            "last_run_at": None,
            "last_error": None,
            "last_emitted": 0,
            "started_at": None,
            "stopped_at": None,
        }
    )

    app = FastAPI()
    app.include_router(v1_scraper.router)

    session = _admin_session()

    async def _fake_auth():
        return session

    app.dependency_overrides[require_auth] = _fake_auth
    return app


@pytest.fixture
def phase4_admin_app(phase4_data, phase4_config):
    _ = phase4_config
    v1_scraper.DATA_DIR = phase4_data["root"]
    v1_scraper.RAW_DIR = phase4_data["raw_dir"]
    v1_scraper.STATE_DIR = phase4_data["state_dir"]
    v1_scraper.TASK_DB_PATH = phase4_data["db_path"]
    v1_scraper.init_task_store(phase4_data["db_path"])
    v1_scraper._scraper_tasks.clear()

    app = FastAPI()
    app.include_router(admin_routes.router)

    session = _admin_session()

    async def _fake_auth():
        return session

    async def _fake_admin():
        return session

    app.dependency_overrides[require_auth] = _fake_auth
    app.dependency_overrides[require_admin] = _fake_admin
    return app


def test_scraper_alerts_default_config():
    alerts_cfg = DEFAULT_ADMIN_SETTINGS.get("scraper_alerts")
    assert isinstance(alerts_cfg, dict)
    assert alerts_cfg.get("enabled") is True
    assert alerts_cfg.get("poll_interval_sec") == 30
    assert alerts_cfg.get("cooldown_sec") == 300
    assert alerts_cfg.get("threshold_backlog") == 30
    assert alerts_cfg.get("threshold_error_rate") == 0.25
    assert alerts_cfg.get("threshold_min_sample") == 20
    assert alerts_cfg.get("webhook", {}).get("enabled") is False
    assert alerts_cfg.get("webhook", {}).get("timeout_sec") == 5
    assert alerts_cfg.get("webhook", {}).get("max_retries") == 3


def test_alert_store_and_queue_stats(phase4_app):
    _ = phase4_app
    store = v1_scraper._get_task_store()

    store.create_task(
        "phase4-pending",
        status="pending",
        message="queued",
        request_payload={"base_url": "https://example.org"},
        provider="generic",
        request_fingerprint="fp-phase4-pending",
    )
    store.create_task(
        "phase4-running",
        status="running",
        message="running",
        request_payload={"base_url": "https://example.org"},
        provider="generic",
        request_fingerprint="fp-phase4-running",
        started_at=datetime.now(timezone.utc).isoformat(),
    )
    store.create_task(
        "phase4-success",
        status="success",
        message="done",
        request_payload={"base_url": "https://example.org"},
        provider="generic",
        request_fingerprint="fp-phase4-success",
    )
    store.update_task(
        "phase4-success",
        status="success",
        message="done",
        report={"success_count": 1, "failed_count": 0, "total_count": 1},
        finished=True,
    )
    store.create_task(
        "phase4-error",
        status="error",
        message="failed",
        request_payload={"base_url": "https://example.org"},
        provider="generic",
        request_fingerprint="fp-phase4-error",
    )
    store.update_task(
        "phase4-error",
        status="error",
        message="failed",
        error_code="SCRAPER_RETRY_EXHAUSTED",
        last_error="timeout",
        finished=True,
    )

    stats = store.queue_stats()
    assert stats["pending"] >= 1
    assert stats["running"] >= 1
    assert stats["done"] >= 1
    assert stats["failed"] >= 1
    assert stats["backlog"] >= 2

    alert = store.append_alert(
        rule="backlog_high",
        severity="warning",
        message="backlog > threshold",
        payload={"backlog": stats["backlog"]},
    )
    assert alert.id > 0

    items, total = store.list_alerts(limit=20, offset=0)
    assert total >= 1
    assert any(item.rule == "backlog_high" for item in items)

    in_cooldown = store.latest_alert_in_cooldown(rule="backlog_high", severity="warning", cooldown_sec=300)
    assert in_cooldown is not None

    conn = sqlite3.connect(store.db_path)
    try:
        columns = conn.execute("PRAGMA table_info(scraper_alerts)").fetchall()
    finally:
        conn.close()
    column_names = {row[1] for row in columns}
    assert "rule" in column_names
    assert "webhook_status" in column_names
    assert "webhook_last_error" in column_names


@pytest.mark.asyncio
async def test_alert_engine_rules_and_cooldown(phase4_app):
    _ = phase4_app
    store = v1_scraper._get_task_store()

    # Trigger backlog_high.
    for idx in range(31):
        store.create_task(
            f"phase4-backlog-{idx}",
            status="pending",
            message="queued",
            request_payload={"base_url": "https://example.org"},
            provider="generic",
            request_fingerprint=f"fp-backlog-{idx}",
        )

    # Trigger error_rate_high and stale_detected.
    for idx in range(20):
        task_id = f"phase4-error-rate-{idx}"
        store.create_task(
            task_id,
            status="error",
            message="done",
            request_payload={"base_url": "https://example.org"},
            provider="generic",
            request_fingerprint=f"fp-error-rate-{idx}",
        )
        if idx < 3:
            error_code = "SCRAPER_TASK_STALE"
        else:
            error_code = "SCRAPER_RETRY_EXHAUSTED"
        store.update_task(
            task_id,
            status="error",
            message="done",
            error_code=error_code,
            finished=True,
        )

    engine = ScraperAlertEngine(store, admin_settings.get("scraper_alerts"))
    first = await engine.run_once()
    emitted_rules = {item.rule for item in first}
    assert "backlog_high" in emitted_rules
    assert "error_rate_high" in emitted_rules
    assert "stale_detected" in emitted_rules

    second = await engine.run_once()
    assert second == []


def test_admin_health_alerts_queue_auth_routes(monkeypatch: pytest.MonkeyPatch, phase4_admin_app):
    store = v1_scraper._get_task_store()
    store.create_task(
        "phase4-admin-pending",
        status="pending",
        message="queued",
        request_payload={"base_url": "https://example.org"},
        provider="generic",
        request_fingerprint="fp-admin-pending",
    )
    store.append_alert(
        rule="backlog_high",
        severity="warning",
        message="backlog high",
        payload={"backlog": 31},
        webhook_status="skipped",
    )

    with TestClient(phase4_admin_app) as client:
        health_resp = client.get("/admin/scraper/health")
        assert health_resp.status_code == 200
        health = health_resp.json()
        assert set(health.keys()) == {"status", "db", "scheduler", "alerts", "time"}

        alerts_resp = client.get("/admin/scraper/alerts", params={"severity": "warning", "limit": 10, "offset": 0})
        assert alerts_resp.status_code == 200
        alerts_payload = alerts_resp.json()
        assert alerts_payload["total"] >= 1
        assert alerts_payload["items"][0]["rule"] == "backlog_high"

        queue_resp = client.get("/admin/scraper/queue/stats")
        assert queue_resp.status_code == 200
        queue_payload = queue_resp.json()
        assert queue_payload["pending"] >= 1
        assert "oldest_pending_age_sec" in queue_payload

        missing_cfg = client.post("/admin/scraper/alerts/test-webhook", json={})
        assert missing_cfg.status_code == 400
        assert missing_cfg.json()["detail"]["code"] == "SCRAPER_ALERT_CONFIG_INVALID"

        async def _fake_send_test(*, webhook_url, timeout_sec=5, max_retries=3):
            _ = (webhook_url, timeout_sec, max_retries)
            return {"sent": True, "attempts": 1, "status": "sent", "message": "ok"}

        monkeypatch.setattr(v1_scraper, "send_test_webhook", _fake_send_test)
        webhook_resp = client.post(
            "/admin/scraper/alerts/test-webhook",
            json={"webhook_url": "https://example.org/hook"},
        )
        assert webhook_resp.status_code == 200
        webhook_payload = webhook_resp.json()
        assert webhook_payload["sent"] is True
        assert webhook_payload["attempts"] == 1


def test_task_status_queue_status_compatibility(phase4_app):
    store = v1_scraper._get_task_store()
    store.create_task(
        "phase4-task-status",
        status="success",
        message="done",
        request_payload={"base_url": "https://example.org"},
        provider="generic",
        request_fingerprint="fp-task-status",
        started_at="2026-02-10T08:00:00+00:00",
    )
    store.update_task(
        "phase4-task-status",
        status="success",
        message="done",
        report={"success_count": 1, "failed_count": 0, "total_count": 1},
        finished=True,
    )

    with TestClient(phase4_app) as client:
        resp = client.get("/api/v1/scraper/task/phase4-task-status")
        assert resp.status_code == 200
        payload = resp.json()
        assert payload["queue_status"] == "done"
        assert payload["enqueued_at"]
        assert payload["dequeued_at"] == "2026-02-10T08:00:00+00:00"
        assert payload["worker_id"] == "local-worker"


def test_task_endpoint_none_fields_are_null_not_string_none(phase4_app):
    task_id = "phase4-task-none-normalization"
    now = datetime.now(timezone.utc).isoformat()
    v1_scraper._scraper_tasks[task_id] = {
        "task_id": task_id,
        "status": "success",
        "message": "done",
        "report": {"ok": True},
        "created_at": now,
        "updated_at": now,
        "created_tick": time.monotonic(),
        "retry_count": 0,
        "max_retries": 2,
        "next_retry_at": None,
        "error_code": None,
        "last_error": None,
    }

    with TestClient(phase4_app) as client:
        resp = client.get(f"/api/v1/scraper/task/{task_id}")
        assert resp.status_code == 200
        payload = resp.json()
        assert payload["next_retry_at"] is None
        assert payload["error_code"] is None
        assert payload["last_error"] is None


def test_access_check_toongod_403_returns_forbidden_structured(monkeypatch: pytest.MonkeyPatch, phase4_app):
    text_called = {"value": False}

    class _FakeResponse:
        status = 403

        async def text(self):
            text_called["value"] = True
            raise aiohttp.ClientPayloadError("Can not decode content-encoding: br")

    class _FakeResponseCtx:
        def __init__(self, response):
            self._response = response

        async def __aenter__(self):
            return self._response

        async def __aexit__(self, exc_type, exc, tb):
            _ = (exc_type, exc, tb)
            return False

    class _FakeClientSession:
        def __init__(self, *args, **kwargs):
            _ = (args, kwargs)

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            _ = (exc_type, exc, tb)
            return False

        def get(self, url, headers=None):
            _ = (url, headers)
            return _FakeResponseCtx(_FakeResponse())

    monkeypatch.setattr(v1_scraper.aiohttp, "ClientSession", _FakeClientSession)

    with TestClient(phase4_app) as client:
        resp = client.post(
            "/api/v1/scraper/access-check",
            json={"base_url": "https://toongod.org", "site_hint": "toongod"},
        )
        assert resp.status_code == 200
        payload = resp.json()
        assert payload["status"] == "forbidden"
        assert payload["http_status"] == 403
        assert text_called["value"] is False


@pytest.mark.asyncio
async def test_alert_scheduler_start_stop(monkeypatch: pytest.MonkeyPatch, phase4_app):
    _ = phase4_app
    cycles = {"count": 0}

    async def _fake_cycle():
        cycles["count"] += 1
        return []

    monkeypatch.setattr(v1_scraper, "run_alert_cycle_once", _fake_cycle)

    await v1_scraper.start_alert_scheduler()
    await asyncio.sleep(0.05)
    runtime = v1_scraper.get_alert_runtime_snapshot()
    assert runtime["running"] is True
    assert cycles["count"] >= 1

    await v1_scraper.stop_alert_scheduler()
    runtime_after = v1_scraper.get_alert_runtime_snapshot()
    assert runtime_after["running"] is False


def test_phase4_admin_auth_requires_admin(phase4_data, phase4_config):
    _ = phase4_config
    v1_scraper.TASK_DB_PATH = phase4_data["db_path"]
    v1_scraper.init_task_store(phase4_data["db_path"])

    app = FastAPI()
    app.include_router(admin_routes.router)

    user_session = Session(
        session_id="phase4-user",
        username="user",
        role="user",
        token="phase4-user-token",
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
        resp = client.get("/admin/scraper/health")
        assert resp.status_code == 403


def test_admin_scraper_legacy_token_auth_works(phase4_data, phase4_config):
    _ = phase4_config
    v1_scraper.TASK_DB_PATH = phase4_data["db_path"]
    v1_scraper.init_task_store(phase4_data["db_path"])

    app = FastAPI()
    app.include_router(admin_routes.router)

    token = "phase4-legacy-admin-token"
    valid_admin_tokens.add(token)
    try:
        with TestClient(app) as client:
            resp = client.get("/admin/scraper/health", headers={"X-Admin-Token": token})
        assert resp.status_code == 200
    finally:
        valid_admin_tokens.discard(token)


def test_admin_scraper_legacy_token_invalid_rejected(phase4_data, phase4_config):
    _ = phase4_config
    v1_scraper.TASK_DB_PATH = phase4_data["db_path"]
    v1_scraper.init_task_store(phase4_data["db_path"])

    app = FastAPI()
    app.include_router(admin_routes.router)

    with TestClient(app) as client:
        resp = client.get("/admin/scraper/health", headers={"X-Admin-Token": "phase4-invalid-token"})
    assert resp.status_code == 401


def test_download_store_failure_does_not_leave_in_memory_pending_task(
    monkeypatch: pytest.MonkeyPatch,
    phase4_app,
):
    _ = phase4_app
    v1_scraper._scraper_tasks.clear()

    provider = _provider_stub()
    monkeypatch.setattr(v1_scraper, "resolve_provider", lambda base_url, site_hint: provider)

    store = v1_scraper._get_task_store()

    def _raise_store_error(*args, **kwargs):
        _ = (args, kwargs)
        raise RuntimeError("sqlite create_task failed")

    monkeypatch.setattr(store, "create_task", _raise_store_error)

    payload = {
        "base_url": "https://example.org",
        "manga": {"id": "demo", "title": "Demo", "url": "https://example.org/manga/demo/"},
        "chapter": {"id": "ch-1", "title": "CH1", "url": "https://example.org/manga/demo/ch-1/"},
    }

    with TestClient(phase4_app) as client:
        resp = client.post("/api/v1/scraper/download", json=payload)

    assert resp.status_code == 500
    assert resp.json()["detail"]["code"] == "SCRAPER_TASK_STORE_ERROR"
    assert v1_scraper._scraper_tasks == {}


@pytest.mark.asyncio
async def test_download_non_retryable_failure_keeps_retry_count_and_error_code_semantics(
    monkeypatch: pytest.MonkeyPatch,
    phase4_app,
):
    _ = phase4_app
    provider = _provider_stub()
    monkeypatch.setattr(v1_scraper, "resolve_provider", lambda base_url, site_hint: provider)

    async def _non_retryable_download(*args, **kwargs):
        _ = (args, kwargs)
        return False, "HTTP 403", False

    monkeypatch.setattr(v1_scraper, "_download_image", _non_retryable_download)

    task_id = "phase4-non-retryable"
    created_at = datetime.now(timezone.utc).isoformat()
    v1_scraper._scraper_tasks[task_id] = {
        "task_id": task_id,
        "status": "pending",
        "message": "queued",
        "created_at": created_at,
        "updated_at": created_at,
        "created_tick": asyncio.get_event_loop().time(),
        "retry_count": 0,
        "max_retries": 2,
        "next_retry_at": None,
        "error_code": None,
        "last_error": None,
        "report": None,
        "provider": "generic",
    }
    store = v1_scraper._get_task_store()
    store.create_task(
        task_id,
        status="pending",
        message="queued",
        request_payload={"base_url": "https://example.org"},
        provider="generic",
        request_fingerprint="fp-phase4-non-retryable",
    )

    req = v1_scraper.ScraperDownloadRequest(
        base_url="https://example.org",
        manga=v1_scraper.MangaPayload(id="demo", title="Demo", url="https://example.org/manga/demo/"),
        chapter=v1_scraper.ChapterPayload(id="ch-1", title="CH1", url="https://example.org/manga/demo/ch-1/"),
        http_mode=True,
    )

    await v1_scraper._run_download_task(
        task_id,
        req,
        provider,
        "https://example.org",
        {},
        "pytest-user-agent",
        None,
        retry_count=0,
        max_retries=2,
        request_fingerprint="fp-phase4-non-retryable",
    )

    payload = v1_scraper._scraper_tasks[task_id]
    assert payload["status"] == "error"
    assert payload["retry_count"] == 0
    assert payload["max_retries"] == 2
    assert payload["error_code"] == "SCRAPER_DOWNLOAD_FAILED"

    record = store.get_task(task_id)
    assert record is not None
    assert record.status == "error"
    assert record.retry_count == 0
    assert record.error_code == "SCRAPER_DOWNLOAD_FAILED"


def test_parser_routes_use_thread_offload_for_fetch(monkeypatch: pytest.MonkeyPatch):
    app = FastAPI()
    app.include_router(v1_parser.router)

    async def _fake_auth():
        return _admin_session()

    app.dependency_overrides[require_auth] = _fake_auth

    html = """
    <html>
      <head><title>Parser Demo</title></head>
      <body>
        <a href="/manga/demo-series/">Demo Series</a>
        <p>First paragraph with enough length for parser output.</p>
      </body>
    </html>
    """

    def _fake_fetch_html(url: str, mode: str = "http") -> str:
        _ = (url, mode)
        return html

    to_thread_calls: list[tuple[object, tuple[object, ...], dict[str, object]]] = []

    async def _fake_to_thread(func, *args, **kwargs):
        to_thread_calls.append((func, args, kwargs))
        return func(*args, **kwargs)

    monkeypatch.setattr(v1_parser, "_fetch_html", _fake_fetch_html)
    monkeypatch.setattr(v1_parser.asyncio, "to_thread", _fake_to_thread)

    with TestClient(app) as client:
        parse_resp = client.post(
            "/api/v1/parser/parse",
            json={"url": "https://mangaforfree.com/manga/demo-series/", "mode": "http"},
        )
        assert parse_resp.status_code == 200
        list_resp = client.post(
            "/api/v1/parser/list",
            json={"url": "https://mangaforfree.com/manga/", "mode": "http"},
        )
        assert list_resp.status_code == 200

    assert len(to_thread_calls) == 2
    assert all(call[0] is _fake_fetch_html for call in to_thread_calls)


def test_admin_legacy_token_auth_works_for_admin_settings(tmp_path: Path):
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
    app.include_router(admin_routes.router)
    token = "legacy-admin-settings-token"
    valid_admin_tokens.add(token)
    try:
        with TestClient(app) as client:
            resp = client.get("/admin/settings", headers={"X-Admin-Token": token})
        assert resp.status_code == 200
    finally:
        valid_admin_tokens.discard(token)


def test_admin_legacy_token_auth_works_for_admin_logs(tmp_path: Path):
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
    app.include_router(admin_routes.router)
    token = "legacy-admin-logs-token"
    valid_admin_tokens.add(token)
    global_log_queue.append(
        {
            "timestamp": "2026-02-10T00:00:00+00:00",
            "level": "INFO",
            "message": "legacy-token-log-line",
        }
    )
    try:
        with TestClient(app) as client:
            resp = client.get("/admin/logs", headers={"X-Admin-Token": token})
        assert resp.status_code == 200
        payload = resp.json()
        assert isinstance(payload.get("logs"), list)
    finally:
        valid_admin_tokens.discard(token)
