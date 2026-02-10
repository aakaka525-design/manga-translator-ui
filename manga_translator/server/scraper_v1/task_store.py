"""SQLite store for scraper tasks."""

from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from threading import RLock
from typing import Any, Iterable


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _parse_iso(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed


_UNSET = object()


@dataclass
class TaskStoreRecord:
    task_id: str
    status: str
    message: str
    report: dict[str, Any] | None
    request_payload: dict[str, Any] | None
    provider: str | None
    created_at: str
    updated_at: str
    finished_at: str | None
    error_code: str | None
    retry_count: int = 0
    max_retries: int = 2
    next_retry_at: str | None = None
    last_error: str | None = None
    request_fingerprint: str | None = None
    started_at: str | None = None

    def to_payload(self) -> dict[str, Any]:
        return {
            "task_id": self.task_id,
            "status": self.status,
            "message": self.message,
            "report": self.report,
            "provider": self.provider,
            "persisted": True,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "finished_at": self.finished_at,
            "error_code": self.error_code,
            "retry_count": self.retry_count,
            "max_retries": self.max_retries,
            "next_retry_at": self.next_retry_at,
            "last_error": self.last_error,
            "request_fingerprint": self.request_fingerprint,
            "started_at": self.started_at,
        }


@dataclass
class AlertStoreRecord:
    id: int
    rule: str
    severity: str
    message: str
    payload: dict[str, Any] | None
    webhook_status: str
    webhook_attempts: int
    webhook_last_error: str | None
    created_at: str
    updated_at: str

    def to_payload(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "rule": self.rule,
            "severity": self.severity,
            "message": self.message,
            "payload": self.payload,
            "webhook_status": self.webhook_status,
            "webhook_attempts": self.webhook_attempts,
            "webhook_last_error": self.webhook_last_error,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }


class ScraperTaskStore:
    _EXTRA_COLUMNS: dict[str, str] = {
        "retry_count": "INTEGER NOT NULL DEFAULT 0",
        "max_retries": "INTEGER NOT NULL DEFAULT 2",
        "next_retry_at": "TEXT",
        "last_error": "TEXT",
        "request_fingerprint": "TEXT",
        "started_at": "TEXT",
    }

    def __init__(self, db_path: Path):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = RLock()
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.db_path), timeout=10, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        return conn

    def _existing_columns(self, conn: sqlite3.Connection) -> set[str]:
        rows = conn.execute("PRAGMA table_info(scraper_tasks)").fetchall()
        return {str(row[1]) for row in rows}

    def _ensure_migrations(self, conn: sqlite3.Connection) -> None:
        existing = self._existing_columns(conn)
        for column, ddl in self._EXTRA_COLUMNS.items():
            if column not in existing:
                conn.execute(f"ALTER TABLE scraper_tasks ADD COLUMN {column} {ddl}")

    def _init_db(self) -> None:
        with self._lock, self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS scraper_tasks (
                    task_id TEXT PRIMARY KEY,
                    status TEXT NOT NULL,
                    message TEXT,
                    report_json TEXT,
                    request_json TEXT,
                    provider TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    finished_at TEXT,
                    error_code TEXT,
                    retry_count INTEGER NOT NULL DEFAULT 0,
                    max_retries INTEGER NOT NULL DEFAULT 2,
                    next_retry_at TEXT,
                    last_error TEXT,
                    request_fingerprint TEXT,
                    started_at TEXT
                )
                """
            )
            self._ensure_migrations(conn)
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS scraper_alerts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    rule TEXT NOT NULL,
                    severity TEXT NOT NULL,
                    message TEXT NOT NULL,
                    payload_json TEXT,
                    webhook_status TEXT NOT NULL DEFAULT 'pending',
                    webhook_attempts INTEGER NOT NULL DEFAULT 0,
                    webhook_last_error TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
                """
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_scraper_tasks_updated_at ON scraper_tasks(updated_at)"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_scraper_tasks_status ON scraper_tasks(status)"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_scraper_tasks_fingerprint_status ON scraper_tasks(request_fingerprint, status)"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_scraper_tasks_provider_updated_at ON scraper_tasks(provider, updated_at)"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_scraper_alerts_rule_created_at ON scraper_alerts(rule, created_at)"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_scraper_alerts_webhook_status_created_at ON scraper_alerts(webhook_status, created_at)"
            )
            conn.commit()

    def _from_row(self, row: sqlite3.Row) -> TaskStoreRecord:
        report_json = row["report_json"] if "report_json" in row.keys() else None
        request_json = row["request_json"] if "request_json" in row.keys() else None
        return TaskStoreRecord(
            task_id=row["task_id"],
            status=row["status"],
            message=row["message"] or "",
            report=json.loads(report_json) if report_json else None,
            request_payload=json.loads(request_json) if request_json else None,
            provider=row["provider"] if "provider" in row.keys() else None,
            created_at=row["created_at"],
            updated_at=row["updated_at"],
            finished_at=row["finished_at"] if "finished_at" in row.keys() else None,
            error_code=row["error_code"] if "error_code" in row.keys() else None,
            retry_count=int(row["retry_count"] or 0) if "retry_count" in row.keys() else 0,
            max_retries=int(row["max_retries"] or 2) if "max_retries" in row.keys() else 2,
            next_retry_at=row["next_retry_at"] if "next_retry_at" in row.keys() else None,
            last_error=row["last_error"] if "last_error" in row.keys() else None,
            request_fingerprint=row["request_fingerprint"] if "request_fingerprint" in row.keys() else None,
            started_at=row["started_at"] if "started_at" in row.keys() else None,
        )

    def _from_alert_row(self, row: sqlite3.Row) -> AlertStoreRecord:
        payload_json = row["payload_json"] if "payload_json" in row.keys() else None
        return AlertStoreRecord(
            id=int(row["id"]),
            rule=str(row["rule"] or ""),
            severity=str(row["severity"] or "info"),
            message=str(row["message"] or ""),
            payload=json.loads(payload_json) if payload_json else None,
            webhook_status=str(row["webhook_status"] or "pending"),
            webhook_attempts=int(row["webhook_attempts"] or 0),
            webhook_last_error=row["webhook_last_error"] if "webhook_last_error" in row.keys() else None,
            created_at=str(row["created_at"] or ""),
            updated_at=str(row["updated_at"] or ""),
        )

    def _fetch_task(self, conn: sqlite3.Connection, task_id: str) -> TaskStoreRecord | None:
        row = conn.execute(
            """
            SELECT
                task_id,status,message,report_json,request_json,provider,
                created_at,updated_at,finished_at,error_code,
                retry_count,max_retries,next_retry_at,last_error,request_fingerprint,started_at
              FROM scraper_tasks
             WHERE task_id = ?
            """,
            (task_id,),
        ).fetchone()
        if row is None:
            return None
        return self._from_row(row)

    def create_task(
        self,
        task_id: str,
        *,
        status: str,
        message: str,
        request_payload: dict[str, Any] | None,
        provider: str | None,
        retry_count: int = 0,
        max_retries: int = 2,
        next_retry_at: str | None = None,
        last_error: str | None = None,
        request_fingerprint: str | None = None,
        started_at: str | None = None,
        error_code: str | None = None,
    ) -> None:
        now = _utc_now()
        request_json = json.dumps(request_payload, ensure_ascii=False) if request_payload is not None else None
        with self._lock, self._connect() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO scraper_tasks(
                    task_id,status,message,report_json,request_json,provider,
                    created_at,updated_at,finished_at,error_code,
                    retry_count,max_retries,next_retry_at,last_error,request_fingerprint,started_at
                ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                """,
                (
                    task_id,
                    status,
                    message,
                    None,
                    request_json,
                    provider,
                    now,
                    now,
                    None,
                    error_code,
                    int(retry_count),
                    int(max_retries),
                    next_retry_at,
                    last_error,
                    request_fingerprint,
                    started_at,
                ),
            )
            conn.commit()

    def update_task(
        self,
        task_id: str,
        *,
        status: str,
        message: str,
        report: dict[str, Any] | None = None,
        error_code: str | None = None,
        finished: bool = False,
        retry_count: int | None = None,
        max_retries: int | None = None,
        next_retry_at: str | None | object = _UNSET,
        last_error: str | None | object = _UNSET,
        started_at: str | None | object = _UNSET,
    ) -> None:
        now = _utc_now()
        with self._lock, self._connect() as conn:
            existing = self._fetch_task(conn, task_id)
            if existing is None:
                return

            report_value = report if report is not None else existing.report
            report_json = json.dumps(report_value, ensure_ascii=False) if report_value is not None else None

            resolved_retry_count = int(retry_count) if retry_count is not None else int(existing.retry_count)
            resolved_max_retries = int(max_retries) if max_retries is not None else int(existing.max_retries)

            if next_retry_at is _UNSET:
                resolved_next_retry = existing.next_retry_at
            else:
                resolved_next_retry = next_retry_at

            if last_error is _UNSET:
                resolved_last_error = existing.last_error
            else:
                resolved_last_error = last_error

            if started_at is _UNSET:
                resolved_started_at = existing.started_at
            else:
                resolved_started_at = started_at

            finished_at = now if finished else existing.finished_at
            resolved_error_code = error_code if error_code is not None else existing.error_code

            conn.execute(
                """
                UPDATE scraper_tasks
                   SET status = ?,
                       message = ?,
                       report_json = ?,
                       updated_at = ?,
                       finished_at = ?,
                       error_code = ?,
                       retry_count = ?,
                       max_retries = ?,
                       next_retry_at = ?,
                       last_error = ?,
                       started_at = ?
                 WHERE task_id = ?
                """,
                (
                    status,
                    message,
                    report_json,
                    now,
                    finished_at,
                    resolved_error_code,
                    resolved_retry_count,
                    resolved_max_retries,
                    resolved_next_retry,
                    resolved_last_error,
                    resolved_started_at,
                    task_id,
                ),
            )
            conn.commit()

    def get_task(self, task_id: str) -> TaskStoreRecord | None:
        with self._lock, self._connect() as conn:
            return self._fetch_task(conn, task_id)

    def find_active_by_fingerprint(
        self,
        fingerprint: str,
        *,
        within_minutes: int = 30,
        statuses: Iterable[str] = ("pending", "running", "retrying"),
    ) -> TaskStoreRecord | None:
        normalized = (fingerprint or "").strip()
        if not normalized:
            return None

        status_list = [str(item).strip() for item in statuses if str(item).strip()]
        if not status_list:
            return None

        threshold = (datetime.now(timezone.utc) - timedelta(minutes=max(1, within_minutes))).isoformat()
        placeholders = ",".join("?" for _ in status_list)
        query = f"""
            SELECT
                task_id,status,message,report_json,request_json,provider,
                created_at,updated_at,finished_at,error_code,
                retry_count,max_retries,next_retry_at,last_error,request_fingerprint,started_at
              FROM scraper_tasks
             WHERE request_fingerprint = ?
               AND status IN ({placeholders})
               AND updated_at >= ?
             ORDER BY updated_at DESC
             LIMIT 1
        """

        with self._lock, self._connect() as conn:
            row = conn.execute(query, (normalized, *status_list, threshold)).fetchone()
            if row is None:
                return None
            return self._from_row(row)

    def append_alert(
        self,
        *,
        rule: str,
        severity: str,
        message: str,
        payload: dict[str, Any] | None = None,
        webhook_status: str = "pending",
        webhook_attempts: int = 0,
        webhook_last_error: str | None = None,
    ) -> AlertStoreRecord:
        now = _utc_now()
        payload_json = json.dumps(payload, ensure_ascii=False) if payload is not None else None
        with self._lock, self._connect() as conn:
            cursor = conn.execute(
                """
                INSERT INTO scraper_alerts(
                    rule,severity,message,payload_json,webhook_status,webhook_attempts,webhook_last_error,created_at,updated_at
                ) VALUES(?,?,?,?,?,?,?,?,?)
                """,
                (
                    str(rule or "").strip() or "unknown",
                    str(severity or "").strip() or "info",
                    str(message or "").strip(),
                    payload_json,
                    str(webhook_status or "").strip() or "pending",
                    max(0, int(webhook_attempts)),
                    webhook_last_error,
                    now,
                    now,
                ),
            )
            alert_id = int(cursor.lastrowid or 0)
            conn.commit()

        record = self.get_alert(alert_id)
        if record is None:
            raise RuntimeError("failed to load inserted alert")
        return record

    def get_alert(self, alert_id: int) -> AlertStoreRecord | None:
        with self._lock, self._connect() as conn:
            row = conn.execute(
                """
                SELECT
                    id,rule,severity,message,payload_json,webhook_status,webhook_attempts,webhook_last_error,created_at,updated_at
                  FROM scraper_alerts
                 WHERE id = ?
                """,
                (int(alert_id),),
            ).fetchone()
            if row is None:
                return None
            return self._from_alert_row(row)

    def update_alert_webhook(
        self,
        alert_id: int,
        *,
        status: str,
        attempts: int,
        last_error: str | None = None,
    ) -> AlertStoreRecord | None:
        now = _utc_now()
        with self._lock, self._connect() as conn:
            conn.execute(
                """
                UPDATE scraper_alerts
                   SET webhook_status = ?,
                       webhook_attempts = ?,
                       webhook_last_error = ?,
                       updated_at = ?
                 WHERE id = ?
                """,
                (
                    str(status or "").strip() or "pending",
                    max(0, int(attempts)),
                    last_error,
                    now,
                    int(alert_id),
                ),
            )
            conn.commit()
        return self.get_alert(alert_id)

    def list_alerts(
        self,
        *,
        severity: str | None = None,
        rule: str | None = None,
        limit: int = 20,
        offset: int = 0,
    ) -> tuple[list[AlertStoreRecord], int]:
        safe_limit = max(1, min(int(limit), 200))
        safe_offset = max(0, int(offset))
        conditions: list[str] = []
        values: list[Any] = []

        if severity:
            conditions.append("severity = ?")
            values.append(severity.strip())

        if rule:
            conditions.append("rule = ?")
            values.append(rule.strip())

        where = ""
        if conditions:
            where = " WHERE " + " AND ".join(conditions)

        count_query = f"SELECT COUNT(*) AS total FROM scraper_alerts{where}"
        list_query = f"""
            SELECT
                id,rule,severity,message,payload_json,webhook_status,webhook_attempts,webhook_last_error,created_at,updated_at
              FROM scraper_alerts
              {where}
             ORDER BY created_at DESC, id DESC
             LIMIT ? OFFSET ?
        """

        with self._lock, self._connect() as conn:
            total_row = conn.execute(count_query, tuple(values)).fetchone()
            total = int(total_row["total"] if total_row else 0)
            rows = conn.execute(list_query, (*values, safe_limit, safe_offset)).fetchall()

        return [self._from_alert_row(row) for row in rows], total

    def latest_alert_in_cooldown(
        self,
        *,
        rule: str,
        cooldown_sec: int = 300,
        severity: str | None = None,
    ) -> AlertStoreRecord | None:
        safe_rule = str(rule or "").strip()
        if not safe_rule:
            return None
        safe_cooldown = max(0, int(cooldown_sec))

        conditions = ["rule = ?"]
        values: list[Any] = [safe_rule]
        if severity:
            conditions.append("severity = ?")
            values.append(severity.strip())

        where = " AND ".join(conditions)
        query = f"""
            SELECT
                id,rule,severity,message,payload_json,webhook_status,webhook_attempts,webhook_last_error,created_at,updated_at
              FROM scraper_alerts
             WHERE {where}
             ORDER BY created_at DESC, id DESC
             LIMIT 1
        """

        with self._lock, self._connect() as conn:
            row = conn.execute(query, tuple(values)).fetchone()
        if row is None:
            return None

        record = self._from_alert_row(row)
        created_at = _parse_iso(record.created_at)
        if created_at is None:
            return None
        delta = (datetime.now(timezone.utc) - created_at).total_seconds()
        if delta <= float(safe_cooldown):
            return record
        return None

    def queue_stats(self) -> dict[str, Any]:
        with self._lock, self._connect() as conn:
            rows = conn.execute(
                """
                SELECT status, COUNT(*) AS cnt
                  FROM scraper_tasks
                 GROUP BY status
                """
            ).fetchall()
            oldest_pending_row = conn.execute(
                """
                SELECT created_at
                  FROM scraper_tasks
                 WHERE status IN ('pending','running','retrying')
                 ORDER BY created_at ASC
                 LIMIT 1
                """
            ).fetchone()

        status_counts = {str(row["status"]): int(row["cnt"] or 0) for row in rows}
        pending = int(status_counts.get("pending", 0))
        running = int(status_counts.get("running", 0))
        retrying = int(status_counts.get("retrying", 0))
        done = int(status_counts.get("success", 0) + status_counts.get("partial", 0))
        failed = int(status_counts.get("error", 0))
        backlog = pending + running + retrying

        oldest_pending_age_sec: int | None = None
        if oldest_pending_row is not None:
            created_at = _parse_iso(str(oldest_pending_row["created_at"] or ""))
            if created_at is not None:
                age = (datetime.now(timezone.utc) - created_at).total_seconds()
                oldest_pending_age_sec = max(0, int(age))

        return {
            "pending": pending,
            "running": running,
            "retrying": retrying,
            "done": done,
            "failed": failed,
            "backlog": backlog,
            "oldest_pending_age_sec": oldest_pending_age_sec,
        }

    def list_tasks(
        self,
        *,
        status: str | None,
        provider: str | None,
        limit: int = 20,
        offset: int = 0,
    ) -> tuple[list[TaskStoreRecord], int]:
        safe_limit = max(1, min(int(limit), 200))
        safe_offset = max(0, int(offset))

        conditions: list[str] = []
        values: list[Any] = []

        if status:
            conditions.append("status = ?")
            values.append(status.strip())

        if provider:
            conditions.append("provider = ?")
            values.append(provider.strip())

        where = ""
        if conditions:
            where = " WHERE " + " AND ".join(conditions)

        base_query = f"""
            SELECT
                task_id,status,message,report_json,request_json,provider,
                created_at,updated_at,finished_at,error_code,
                retry_count,max_retries,next_retry_at,last_error,request_fingerprint,started_at
              FROM scraper_tasks
              {where}
             ORDER BY updated_at DESC
             LIMIT ? OFFSET ?
        """

        count_query = f"SELECT COUNT(*) AS total FROM scraper_tasks{where}"

        with self._lock, self._connect() as conn:
            total_row = conn.execute(count_query, tuple(values)).fetchone()
            total = int(total_row["total"] if total_row else 0)

            rows = conn.execute(base_query, (*values, safe_limit, safe_offset)).fetchall()
            items = [self._from_row(row) for row in rows]

        return items, total

    def metrics(self, *, hours: int = 24) -> dict[str, Any]:
        safe_hours = max(1, min(int(hours), 24 * 30))
        threshold = (datetime.now(timezone.utc) - timedelta(hours=safe_hours)).isoformat()

        with self._lock, self._connect() as conn:
            summary_rows = conn.execute(
                """
                SELECT status, COUNT(*) AS cnt
                  FROM scraper_tasks
                 WHERE updated_at >= ?
                 GROUP BY status
                """,
                (threshold,),
            ).fetchall()

            provider_rows = conn.execute(
                """
                SELECT COALESCE(provider, 'unknown') AS provider, COUNT(*) AS cnt
                  FROM scraper_tasks
                 WHERE updated_at >= ?
                 GROUP BY COALESCE(provider, 'unknown')
                """,
                (threshold,),
            ).fetchall()

            error_rows = conn.execute(
                """
                SELECT error_code, COUNT(*) AS cnt
                  FROM scraper_tasks
                 WHERE updated_at >= ?
                   AND error_code IS NOT NULL
                   AND error_code != ''
                 GROUP BY error_code
                """,
                (threshold,),
            ).fetchall()

        status_counts = {str(row["status"]): int(row["cnt"] or 0) for row in summary_rows}
        total = int(sum(status_counts.values()))
        success = int(status_counts.get("success", 0))
        partial = int(status_counts.get("partial", 0))
        error = int(status_counts.get("error", 0))

        provider_breakdown = {str(row["provider"]): int(row["cnt"] or 0) for row in provider_rows}
        error_code_breakdown = {str(row["error_code"]): int(row["cnt"] or 0) for row in error_rows}

        return {
            "hours": safe_hours,
            "total": total,
            "success": success,
            "partial": partial,
            "error": error,
            "success_rate": (float(success) / float(total)) if total else 0.0,
            "provider_breakdown": provider_breakdown,
            "error_code_breakdown": error_code_breakdown,
        }

    def mark_stale_tasks(
        self,
        *,
        stale_before: str,
        message: str,
        error_code: str,
        statuses: Iterable[str] = ("pending", "running", "retrying"),
    ) -> int:
        status_list = [str(item).strip() for item in statuses if str(item).strip()]
        if not status_list:
            return 0

        placeholders = ",".join("?" for _ in status_list)
        now = _utc_now()
        query = f"""
            UPDATE scraper_tasks
               SET status = 'error',
                   message = ?,
                   updated_at = ?,
                   finished_at = ?,
                   error_code = ?,
                   next_retry_at = NULL,
                   last_error = COALESCE(last_error, ?)
             WHERE status IN ({placeholders})
               AND updated_at < ?
        """

        with self._lock, self._connect() as conn:
            cursor = conn.execute(
                query,
                (
                    message,
                    now,
                    now,
                    error_code,
                    message,
                    *status_list,
                    stale_before,
                ),
            )
            conn.commit()
            return int(cursor.rowcount or 0)

    def prune_completed(self, *, days: int = 7) -> int:
        threshold = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
        with self._lock, self._connect() as conn:
            cursor = conn.execute(
                """
                DELETE FROM scraper_tasks
                 WHERE status IN ('success','partial','error')
                   AND updated_at < ?
                """,
                (threshold,),
            )
            conn.commit()
            return int(cursor.rowcount or 0)
