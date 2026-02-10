from __future__ import annotations

from datetime import timedelta

import pytest

from manga_translator.server.core.account_service import AccountService
from manga_translator.server.core.models import UserPermissions
from manga_translator.server.core.permission_service import PermissionService
from manga_translator.server.core.session_service import SessionService


def test_account_service_creates_hashed_user_and_verifies_password(tmp_path):
    accounts_file = tmp_path / "accounts.json"
    service = AccountService(accounts_file=str(accounts_file))

    account = service.create_user(
        username="alice",
        password="secure123",
        role="user",
        group="unit-test-group",
    )

    assert account.password_hash != "secure123"
    assert service.verify_password("alice", "secure123") is True
    assert service.verify_password("alice", "wrong-pass") is False
    assert accounts_file.exists() is True


def test_account_service_rejects_short_password(tmp_path):
    service = AccountService(accounts_file=str(tmp_path / "accounts.json"))

    with pytest.raises(ValueError, match="至少为6个字符"):
        service.create_user(username="alice", password="12345", role="user")


def test_session_service_expires_and_deactivates_session():
    service = SessionService(session_timeout_minutes=60, enable_persistence=False)
    session = service.create_session(
        username="alice",
        role="user",
        ip_address="127.0.0.1",
        user_agent="pytest",
    )
    assert service.get_session(session.token) is not None

    session.last_activity = session.last_activity - timedelta(minutes=120)
    assert service.get_session(session.token) is None
    assert session.token not in service.sessions_by_token
    assert session.is_active is False


def test_session_service_persistence_roundtrip(tmp_path):
    sessions_file = tmp_path / "sessions.json"
    service = SessionService(
        sessions_file=str(sessions_file),
        session_timeout_minutes=60,
        enable_persistence=True,
    )
    created = service.create_session(
        username="bob",
        role="admin",
        ip_address="127.0.0.1",
        user_agent="pytest",
    )
    assert sessions_file.exists() is True

    reloaded = SessionService(
        sessions_file=str(sessions_file),
        session_timeout_minutes=60,
        enable_persistence=True,
    )
    loaded = reloaded.get_session(created.token)
    assert loaded is not None
    assert loaded.username == "bob"
    assert loaded.role == "admin"


def test_permission_service_concurrent_and_daily_quota_limits(tmp_path):
    account_service = AccountService(accounts_file=str(tmp_path / "accounts.json"))
    account_service.create_user(
        username="charlie",
        password="secure123",
        role="user",
        group="unit-nonexistent-group",
        permissions=UserPermissions(
            allowed_translators=["google"],
            denied_translators=[],
            allowed_parameters=["translator"],
            denied_parameters=[],
            max_concurrent_tasks=2,
            daily_quota=2,
            can_upload_files=True,
            can_delete_files=False,
        ),
    )
    permission_service = PermissionService(account_service)

    permission_service.increment_task_count("charlie")
    assert permission_service.check_concurrent_limit("charlie") is True
    permission_service.increment_task_count("charlie")
    assert permission_service.check_concurrent_limit("charlie") is True
    permission_service.increment_task_count("charlie")
    assert permission_service.check_concurrent_limit("charlie") is False

    assert permission_service.check_daily_quota("charlie") is True
    permission_service.increment_daily_usage("charlie")
    permission_service.increment_daily_usage("charlie")
    assert permission_service.check_daily_quota("charlie") is False


def test_permission_service_filters_parameters_by_allowlist(tmp_path):
    account_service = AccountService(accounts_file=str(tmp_path / "accounts.json"))
    account_service.create_user(
        username="dora",
        password="secure123",
        role="user",
        group="unit-nonexistent-group",
        permissions=UserPermissions(
            allowed_translators=["google"],
            denied_translators=[],
            allowed_parameters=["translator", "target_lang"],
            denied_parameters=[],
            max_concurrent_tasks=2,
            daily_quota=100,
            can_upload_files=True,
            can_delete_files=False,
        ),
    )
    permission_service = PermissionService(account_service)

    filtered = permission_service.filter_parameters(
        "dora",
        {"translator": "google", "target_lang": "zh", "temperature": 0.5},
    )
    assert filtered == {"translator": "google", "target_lang": "zh"}
