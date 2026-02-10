from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace

from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient

import manga_translator.server.core.middleware as middleware
from manga_translator.server.core.auth import valid_admin_tokens
from manga_translator.server.core.models import Session
from manga_translator.server.core.group_service import GroupService
from manga_translator.server.core.quota_service import QuotaManagementService
from manga_translator.server.repositories.permission_repository import PermissionRepository
from manga_translator.server.repositories.quota_repository import QuotaRepository


class _DummyAccountService:
    def __init__(self, active_by_user: dict[str, bool]) -> None:
        self._active_by_user = active_by_user

    def get_user(self, username: str):
        is_active = self._active_by_user.get(username, False)
        return SimpleNamespace(is_active=is_active) if username in self._active_by_user else None


class _DummySessionService:
    def __init__(self, sessions_by_token: dict[str, Session]) -> None:
        self._sessions_by_token = sessions_by_token

    def verify_token(self, token: str):
        return self._sessions_by_token.get(token)


class _DummyPermissionService:
    def __init__(
        self,
        *,
        can_create_task: bool = True,
        can_use_daily_quota: bool = True,
        active_tasks: int = 0,
        max_tasks: int = 2,
        usage: int = 0,
        quota: int = 10,
    ) -> None:
        self._can_create_task = can_create_task
        self._can_use_daily_quota = can_use_daily_quota
        self._active_tasks = active_tasks
        self._max_tasks = max_tasks
        self._usage = usage
        self._quota = quota
        self._task_counter = 0
        self._daily_usage = 0

    def check_concurrent_limit(self, username: str) -> bool:
        _ = username
        return self._can_create_task

    def get_active_task_count(self, username: str) -> int:
        _ = username
        return self._active_tasks

    def get_effective_max_concurrent(self, username: str) -> int:
        _ = username
        return self._max_tasks

    def check_daily_quota(self, username: str) -> bool:
        _ = username
        return self._can_use_daily_quota

    def get_daily_usage(self, username: str) -> int:
        _ = username
        return self._usage

    def get_effective_daily_quota(self, username: str) -> int:
        _ = username
        return self._quota

    def increment_task_count(self, username: str) -> None:
        _ = username
        self._task_counter += 1

    def decrement_task_count(self, username: str) -> None:
        _ = username
        self._task_counter = max(0, self._task_counter - 1)

    def increment_daily_usage(self, username: str) -> None:
        _ = username
        self._daily_usage += 1

    def check_translator_permission(self, username: str, translator: str) -> bool:
        _ = (username, translator)
        return True

    def get_user_permissions(self, username: str):
        _ = username
        return SimpleNamespace(allowed_translators=["*"])

    def filter_parameters(self, username: str, parameters: dict):
        _ = username
        return parameters


def _make_session(username: str, role: str, token: str) -> Session:
    now = datetime.now(timezone.utc)
    return Session(
        session_id=f"session-{username}",
        username=username,
        role=role,
        token=token,
        created_at=now,
        last_activity=now,
        ip_address="127.0.0.1",
        user_agent="pytest",
        is_active=True,
    )


def _build_auth_app() -> FastAPI:
    app = FastAPI()

    @app.get("/auth-only")
    async def auth_only(session: Session = Depends(middleware.require_auth)):
        return {"username": session.username, "role": session.role}

    @app.get("/admin-only")
    async def admin_only(session: Session = Depends(middleware.require_admin)):
        return {"username": session.username, "role": session.role}

    return app


def test_require_auth_missing_token_returns_no_token_error(monkeypatch):
    account_service = _DummyAccountService(active_by_user={"alice": True})
    session_service = _DummySessionService(sessions_by_token={})
    perm_service = _DummyPermissionService()
    monkeypatch.setattr(
        middleware,
        "get_services",
        lambda: (account_service, session_service, perm_service),
        raising=True,
    )

    app = _build_auth_app()
    with TestClient(app) as client:
        response = client.get("/auth-only")
        assert response.status_code == 401
        detail = response.json()["detail"]
        assert detail["error"]["code"] == "NO_TOKEN"


def test_require_auth_inactive_user_returns_user_inactive(monkeypatch):
    session = _make_session("alice", "user", "token-alice")
    account_service = _DummyAccountService(active_by_user={"alice": False})
    session_service = _DummySessionService(sessions_by_token={"token-alice": session})
    perm_service = _DummyPermissionService()
    monkeypatch.setattr(
        middleware,
        "get_services",
        lambda: (account_service, session_service, perm_service),
        raising=True,
    )

    app = _build_auth_app()
    with TestClient(app) as client:
        response = client.get("/auth-only", headers={"X-Session-Token": "token-alice"})
        assert response.status_code == 401
        detail = response.json()["detail"]
        assert detail["error"]["code"] == "USER_INACTIVE"


def test_require_admin_accepts_legacy_admin_token(monkeypatch):
    account_service = _DummyAccountService(active_by_user={})
    session_service = _DummySessionService(sessions_by_token={})
    perm_service = _DummyPermissionService()
    monkeypatch.setattr(
        middleware,
        "get_services",
        lambda: (account_service, session_service, perm_service),
        raising=True,
    )

    valid_admin_tokens.clear()
    valid_admin_tokens.add("legacy-admin-token")
    try:
        app = _build_auth_app()
        with TestClient(app) as client:
            response = client.get("/admin-only", headers={"X-Admin-Token": "legacy-admin-token"})
            assert response.status_code == 200
            data = response.json()
            assert data["role"] == "admin"
            assert data["username"] == "legacy-admin"
    finally:
        valid_admin_tokens.clear()


def test_require_admin_rejects_non_admin_session(monkeypatch):
    session = _make_session("alice", "user", "token-user")
    account_service = _DummyAccountService(active_by_user={"alice": True})
    session_service = _DummySessionService(sessions_by_token={"token-user": session})
    perm_service = _DummyPermissionService()
    monkeypatch.setattr(
        middleware,
        "get_services",
        lambda: (account_service, session_service, perm_service),
        raising=True,
    )

    app = _build_auth_app()
    with TestClient(app) as client:
        response = client.get("/admin-only", headers={"X-Session-Token": "token-user"})
        assert response.status_code == 403
        detail = response.json()["detail"]
        assert detail["error"]["code"] == "ADMIN_REQUIRED"


def test_check_concurrent_limit_and_daily_quota_raise_http_429(monkeypatch):
    account_service = _DummyAccountService(active_by_user={})
    session_service = _DummySessionService(sessions_by_token={})
    perm_service = _DummyPermissionService(
        can_create_task=False,
        can_use_daily_quota=False,
        active_tasks=3,
        max_tasks=2,
        usage=15,
        quota=10,
    )
    monkeypatch.setattr(
        middleware,
        "get_services",
        lambda: (account_service, session_service, perm_service),
        raising=True,
    )

    from fastapi import HTTPException

    try:
        middleware.check_concurrent_limit("alice")
        raise AssertionError("Expected HTTPException for concurrent limit")
    except HTTPException as exc:
        assert exc.status_code == 429
        assert exc.detail["error"]["code"] == "CONCURRENT_LIMIT_EXCEEDED"

    try:
        middleware.check_daily_quota("alice")
        raise AssertionError("Expected HTTPException for daily quota")
    except HTTPException as exc:
        assert exc.status_code == 429
        assert exc.detail["error"]["code"] == "DAILY_QUOTA_EXCEEDED"


def test_quota_service_enforces_default_upload_and_session_limits(tmp_path):
    quota_repo = QuotaRepository(str(tmp_path / "quotas.json"))
    permission_repo = PermissionRepository(str(tmp_path / "permissions.json"))
    group_service = GroupService(config_file=str(tmp_path / "groups.json"))
    service = QuotaManagementService(quota_repo, permission_repo, group_service, data_path=str(tmp_path))
    user_id = "quota-user"

    ok, message = service.check_upload_limit(
        user_id=user_id,
        file_size=QuotaManagementService.DEFAULT_MAX_FILE_SIZE + 1,
        file_count=1,
    )
    assert ok is False
    assert "超过限制" in (message or "")

    for i in range(QuotaManagementService.DEFAULT_MAX_SESSIONS):
        assert service.register_session(user_id, f"session-{i}") is True

    ok, message = service.check_session_limit(user_id)
    assert ok is False
    assert "已达到限制" in (message or "")

    assert service.unregister_session(user_id, "session-0") is True
    ok, _ = service.check_session_limit(user_id)
    assert ok is True


def test_quota_service_respects_user_specific_daily_quota_and_reset(tmp_path):
    quota_repo = QuotaRepository(str(tmp_path / "quotas.json"))
    permission_repo = PermissionRepository(str(tmp_path / "permissions.json"))
    group_service = GroupService(config_file=str(tmp_path / "groups.json"))
    service = QuotaManagementService(quota_repo, permission_repo, group_service, data_path=str(tmp_path))
    user_id = "daily-user"

    assert service.set_user_quota_limits(user_id, daily_quota=2) is True
    ok, _ = service.check_daily_quota(user_id, image_count=1)
    assert ok is True

    assert service.increment_quota_usage(user_id, 2) is True
    ok, message = service.check_daily_quota(user_id, image_count=1)
    assert ok is False
    assert "每日配额不足" in (message or "")

    assert service.reset_daily_quota(user_id) is True
    ok, _ = service.check_daily_quota(user_id, image_count=2)
    assert ok is True


def test_quota_service_applies_group_quota_limits_when_user_has_group(tmp_path):
    quota_repo = QuotaRepository(str(tmp_path / "quotas.json"))
    permission_repo = PermissionRepository(str(tmp_path / "permissions.json"))
    group_service = GroupService(config_file=str(tmp_path / "groups.json"))
    service = QuotaManagementService(quota_repo, permission_repo, group_service, data_path=str(tmp_path))

    group_service.update_group(
        "vip",
        {
            "name": "VIP",
            "description": "VIP group for tests",
            "quota_limits": {
                "max_file_size": 2048,
                "max_files_per_upload": 3,
                "max_sessions": 2,
                "daily_quota": 7,
            },
        },
    )

    data = permission_repo._read_data()
    data.setdefault("user_permissions", {})["vip-user"] = {"group": "vip"}
    permission_repo._write_data(data)

    ok, message = service.check_upload_limit("vip-user", file_size=4096, file_count=1)
    assert ok is False
    assert "超过限制" in (message or "")

    stored = quota_repo.get_user_quota("vip-user")
    assert stored is not None
    assert stored["max_file_size"] == 2048
    assert stored["max_sessions"] == 2
    assert stored["daily_quota"] == 7
