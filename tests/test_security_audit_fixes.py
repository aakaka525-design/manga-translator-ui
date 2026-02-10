from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient

import manga_translator.server.routes.admin as admin_routes
import manga_translator.server.routes.web as web_routes
from manga_translator.server.core.auth import (
    hash_password,
    reset_legacy_auth_rate_limit_state,
    valid_admin_tokens,
    verify_password_hash,
)


def _build_app_with_router(router):
    app = FastAPI()
    app.include_router(router)
    return app


def test_admin_setup_stores_hashed_password(monkeypatch):
    settings = {"admin_password": "", "admin_password_hash": ""}
    monkeypatch.setattr(admin_routes, "admin_settings", settings, raising=True)
    monkeypatch.setattr(admin_routes, "save_admin_settings", lambda payload: True, raising=True)
    valid_admin_tokens.clear()

    app = _build_app_with_router(admin_routes.router)
    with TestClient(app) as client:
        resp = client.post("/admin/setup", data={"password": "secure123"})
        assert resp.status_code == 200
        payload = resp.json()
        assert payload["success"] is True
        token = payload["token"]
        assert token in valid_admin_tokens

    assert settings["admin_password"] == ""
    assert verify_password_hash("secure123", settings["admin_password_hash"])


def test_admin_login_migrates_legacy_plain_password(monkeypatch):
    settings = {"admin_password": "legacy123", "admin_password_hash": ""}
    saved = {"count": 0}

    def _fake_save(payload):
        _ = payload
        saved["count"] += 1
        return True

    monkeypatch.setattr(admin_routes, "admin_settings", settings, raising=True)
    monkeypatch.setattr(admin_routes, "save_admin_settings", _fake_save, raising=True)
    valid_admin_tokens.clear()

    app = _build_app_with_router(admin_routes.router)
    with TestClient(app) as client:
        resp = client.post("/admin/login", data={"password": "legacy123"})
        assert resp.status_code == 200
        payload = resp.json()
        assert payload["success"] is True
        assert payload["token"] in valid_admin_tokens

    assert saved["count"] == 1
    assert settings["admin_password"] == ""
    assert verify_password_hash("legacy123", settings["admin_password_hash"])


def test_admin_change_password_uses_hash(monkeypatch):
    settings = {"admin_password": "", "admin_password_hash": hash_password("oldpass123")}
    monkeypatch.setattr(admin_routes, "admin_settings", settings, raising=True)
    monkeypatch.setattr(admin_routes, "save_admin_settings", lambda payload: True, raising=True)
    valid_admin_tokens.clear()
    valid_admin_tokens.add("legacy-token")

    app = _build_app_with_router(admin_routes.router)
    with TestClient(app) as client:
        resp = client.post(
            "/admin/change-password",
            data={"old_password": "oldpass123", "new_password": "newpass123"},
            headers={"X-Admin-Token": "legacy-token"},
        )
        assert resp.status_code == 200
        assert resp.json()["success"] is True

    assert settings["admin_password"] == ""
    assert verify_password_hash("newpass123", settings["admin_password_hash"])
    assert len(valid_admin_tokens) == 0


def test_user_login_with_hash_and_legacy_migration(monkeypatch):
    settings = {
        "user_access": {
            "require_password": True,
            "user_password_hash": "",
            "user_password": "user12345",
        }
    }
    saved = {"count": 0}

    def _fake_save(payload):
        _ = payload
        saved["count"] += 1
        return True

    monkeypatch.setattr(web_routes, "admin_settings", settings, raising=True)
    monkeypatch.setattr(web_routes, "save_admin_settings", _fake_save, raising=True)

    app = _build_app_with_router(web_routes.router)
    with TestClient(app) as client:
        legacy_resp = client.post("/user/login", data={"password": "user12345"})
        assert legacy_resp.status_code == 200
        assert legacy_resp.json()["success"] is True

        wrong_resp = client.post("/user/login", data={"password": "wrong-pass"})
        assert wrong_resp.status_code == 200
        assert wrong_resp.json()["success"] is False

        hashed_resp = client.post("/user/login", data={"password": "user12345"})
        assert hashed_resp.status_code == 200
        assert hashed_resp.json()["success"] is True

    assert saved["count"] == 1
    user_access = settings["user_access"]
    assert user_access["user_password"] == ""
    assert verify_password_hash("user12345", user_access["user_password_hash"])


def test_result_folder_path_traversal_is_blocked(monkeypatch, tmp_path: Path):
    result_root = tmp_path / "result"
    demo_folder = result_root / "demo"
    demo_folder.mkdir(parents=True, exist_ok=True)
    (demo_folder / "final.png").write_bytes(b"demo")

    monkeypatch.setattr(web_routes, "result_dir", str(result_root), raising=True)

    app = _build_app_with_router(web_routes.router)
    with TestClient(app) as client:
        ok_resp = client.get("/result/demo/final.png")
        assert ok_resp.status_code == 200

        traversal_resp = client.get("/result/%2E%2E/final.png")
        assert traversal_resp.status_code == 400

        delete_traversal_resp = client.delete("/results/%2E%2E")
        assert delete_traversal_resp.status_code == 400


def test_admin_login_rate_limit_blocks_after_repeated_failures(monkeypatch):
    settings = {"admin_password": "", "admin_password_hash": hash_password("correct-pass")}
    monkeypatch.setattr(admin_routes, "admin_settings", settings, raising=True)
    monkeypatch.setattr(admin_routes, "save_admin_settings", lambda payload: True, raising=True)
    valid_admin_tokens.clear()
    reset_legacy_auth_rate_limit_state()

    app = _build_app_with_router(admin_routes.router)
    with TestClient(app) as client:
        for _ in range(10):
            resp = client.post("/admin/login", data={"password": "wrong-pass"})
            assert resp.status_code == 200
            assert resp.json()["success"] is False

        limited = client.post("/admin/login", data={"password": "wrong-pass"})
        assert limited.status_code == 429
        detail = limited.json()["detail"]
        assert detail["error"]["code"] == "RATE_LIMIT_EXCEEDED"
        assert detail["error"]["details"]["retry_after"] >= 1

    reset_legacy_auth_rate_limit_state()


def test_admin_change_password_rate_limit_blocks_after_repeated_failures(monkeypatch):
    settings = {"admin_password": "", "admin_password_hash": hash_password("current-pass")}
    monkeypatch.setattr(admin_routes, "admin_settings", settings, raising=True)
    monkeypatch.setattr(admin_routes, "save_admin_settings", lambda payload: True, raising=True)
    valid_admin_tokens.clear()
    valid_admin_tokens.add("legacy-token")
    reset_legacy_auth_rate_limit_state()

    app = _build_app_with_router(admin_routes.router)
    with TestClient(app) as client:
        headers = {"X-Admin-Token": "legacy-token"}
        for _ in range(10):
            resp = client.post(
                "/admin/change-password",
                data={"old_password": "wrong-old", "new_password": "new-pass-123"},
                headers=headers,
            )
            assert resp.status_code == 200
            assert resp.json()["success"] is False

        limited = client.post(
            "/admin/change-password",
            data={"old_password": "wrong-old", "new_password": "new-pass-123"},
            headers=headers,
        )
        assert limited.status_code == 429
        detail = limited.json()["detail"]
        assert detail["error"]["code"] == "RATE_LIMIT_EXCEEDED"
        assert detail["error"]["details"]["retry_after"] >= 1

    reset_legacy_auth_rate_limit_state()


def test_user_login_rate_limit_blocks_after_repeated_failures(monkeypatch):
    settings = {
        "user_access": {
            "require_password": True,
            "user_password_hash": hash_password("correct-pass"),
            "user_password": "",
        }
    }
    monkeypatch.setattr(web_routes, "admin_settings", settings, raising=True)
    monkeypatch.setattr(web_routes, "save_admin_settings", lambda payload: True, raising=True)
    reset_legacy_auth_rate_limit_state()

    app = _build_app_with_router(web_routes.router)
    with TestClient(app) as client:
        for _ in range(10):
            resp = client.post("/user/login", data={"password": "wrong-pass"})
            assert resp.status_code == 200
            assert resp.json()["success"] is False

        limited = client.post("/user/login", data={"password": "wrong-pass"})
        assert limited.status_code == 429
        detail = limited.json()["detail"]
        assert detail["error"]["code"] == "RATE_LIMIT_EXCEEDED"
        assert detail["error"]["details"]["retry_after"] >= 1

    reset_legacy_auth_rate_limit_state()
