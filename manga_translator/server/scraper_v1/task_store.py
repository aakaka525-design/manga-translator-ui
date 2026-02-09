"""SQLite store for scraper tasks."""

from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from threading import RLock
from typing import Any


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


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
        }


class ScraperTaskStore:
    def __init__(self, db_path: Path):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = RLock()
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.db_path), timeout=10, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        return conn

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
                    error_code TEXT
                )
                """
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_scraper_tasks_updated_at ON scraper_tasks(updated_at)"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_scraper_tasks_status ON scraper_tasks(status)"
            )
            conn.commit()

    def create_task(
        self,
        task_id: str,
        *,
        status: str,
        message: str,
        request_payload: dict[str, Any] | None,
        provider: str | None,
    ) -> None:
        now = _utc_now()
        request_json = json.dumps(request_payload, ensure_ascii=False) if request_payload is not None else None
        with self._lock, self._connect() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO scraper_tasks(
                    task_id,status,message,report_json,request_json,provider,created_at,updated_at,finished_at,error_code
                ) VALUES(?,?,?,?,?,?,?,?,?,?)
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
                    None,
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
    ) -> None:
        now = _utc_now()
        report_json = json.dumps(report, ensure_ascii=False) if report is not None else None
        finished_at = now if finished else None
        with self._lock, self._connect() as conn:
            conn.execute(
                """
                UPDATE scraper_tasks
                   SET status = ?,
                       message = ?,
                       report_json = COALESCE(?, report_json),
                       updated_at = ?,
                       finished_at = COALESCE(?, finished_at),
                       error_code = COALESCE(?, error_code)
                 WHERE task_id = ?
                """,
                (
                    status,
                    message,
                    report_json,
                    now,
                    finished_at,
                    error_code,
                    task_id,
                ),
            )
            conn.commit()

    def get_task(self, task_id: str) -> TaskStoreRecord | None:
        with self._lock, self._connect() as conn:
            row = conn.execute(
                """
                SELECT task_id,status,message,report_json,request_json,provider,created_at,updated_at,finished_at,error_code
                  FROM scraper_tasks
                 WHERE task_id = ?
                """,
                (task_id,),
            ).fetchone()
        if row is None:
            return None
        report_json = row["report_json"]
        request_json = row["request_json"]
        return TaskStoreRecord(
            task_id=row["task_id"],
            status=row["status"],
            message=row["message"] or "",
            report=json.loads(report_json) if report_json else None,
            request_payload=json.loads(request_json) if request_json else None,
            provider=row["provider"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
            finished_at=row["finished_at"],
            error_code=row["error_code"],
        )

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
