from __future__ import annotations

import asyncio
import sqlite3
import sys
import types
from datetime import datetime, timezone
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from manga_translator.server.core.middleware import require_admin, require_auth
from manga_translator.server.core.models import Session

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
