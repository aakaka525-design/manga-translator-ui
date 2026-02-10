from __future__ import annotations

import json
from pathlib import Path
from uuid import uuid4

from manga_translator.server.core.audit_service import AuditService
from manga_translator.server.core.session_security_service import SessionSecurityService


def test_session_security_service_validates_uuid_v4_tokens(tmp_path):
    service = SessionSecurityService(data_dir=str(tmp_path))
    session = service.create_session(user_id="alice", metadata={"source": "pytest"})

    assert service.validate_session_token_format(session.session_token) is True
    assert service.validate_session_token_format("not-a-uuid") is False


def test_session_security_service_enforces_ownership_and_rate_limit(tmp_path):
    service = SessionSecurityService(data_dir=str(tmp_path))
    owner = "alice"
    other = "bob"
    session = service.create_session(user_id=owner)

    allowed, reason = service.check_session_ownership(session.session_token, owner, "view")
    assert allowed is True
    assert reason is None

    denied, deny_reason = service.check_session_ownership(session.session_token, other, "view")
    assert denied is False
    assert "own this session" in (deny_reason or "")

    for _ in range(10):
        ok, _ = service.check_session_ownership("invalid-token", other, "view")
        assert ok is False

    blocked, block_reason = service.check_session_ownership("invalid-token", other, "view")
    assert blocked is False
    assert "Rate limit exceeded" in (block_reason or "")


def test_audit_service_logs_and_filters_events(tmp_path):
    audit_log = tmp_path / "audit.log"
    service = AuditService(audit_log_file=str(audit_log))

    service.log_event(
        event_type="login",
        username="alice",
        ip_address="127.0.0.1",
        details={"client": "web"},
        result="success",
    )
    service.log_event(
        event_type="login",
        username="bob",
        ip_address="127.0.0.1",
        details={"client": "web"},
        result="failure",
    )

    filtered = service.query_events(filters={"username": "alice"})
    assert len(filtered) == 1
    assert filtered[0].username == "alice"
    assert filtered[0].result == "success"


def test_audit_service_export_csv_and_rotate(tmp_path):
    audit_log = tmp_path / "audit.log"
    service = AuditService(audit_log_file=str(audit_log), max_log_size_mb=1, max_backup_files=2)

    service.log_event(
        event_type="permission_change",
        username="admin",
        ip_address="127.0.0.1",
        details={"target": "alice"},
        result="success",
    )
    csv_output = service.export_events(format="csv")
    assert "event_id,timestamp,event_type,username,ip_address,result,details" in csv_output
    assert "permission_change" in csv_output

    assert service.rotate_log_file() is True
    backups = list(tmp_path.glob("audit.log.*"))
    assert backups

    # Rotated file should still be valid JSON lines.
    for backup in backups:
        with open(backup, "r", encoding="utf-8") as handle:
            for line in handle:
                line = line.strip()
                if line:
                    json.loads(line)
