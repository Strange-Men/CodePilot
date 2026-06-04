from __future__ import annotations

import sqlite3
from datetime import UTC, datetime
from pathlib import Path
from threading import Lock

from backend.models.review import ReviewStatus


class ReviewStore:
    def __init__(self, database_path: Path) -> None:
        self.database_path = database_path
        self._lock = Lock()
        self._initialize()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.database_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _initialize(self) -> None:
        with self._lock, self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS reviews (
                    task_id TEXT PRIMARY KEY,
                    repo_url TEXT NOT NULL,
                    status TEXT NOT NULL,
                    error TEXT,
                    report_markdown TEXT,
                    export_path TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
                """
            )
            conn.commit()

    def create_review(self, task_id: str, repo_url: str) -> None:
        now = self._now()
        with self._lock, self._connect() as conn:
            conn.execute(
                """
                INSERT INTO reviews (task_id, repo_url, status, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (task_id, repo_url, ReviewStatus.pending.value, now, now),
            )
            conn.commit()

    def update_status(
        self,
        task_id: str,
        status: ReviewStatus,
        *,
        error: str | None = None,
        report_markdown: str | None = None,
        export_path: str | None = None,
    ) -> None:
        with self._lock, self._connect() as conn:
            conn.execute(
                """
                UPDATE reviews
                SET status = ?, error = ?, report_markdown = COALESCE(?, report_markdown),
                    export_path = COALESCE(?, export_path), updated_at = ?
                WHERE task_id = ?
                """,
                (status.value, error, report_markdown, export_path, self._now(), task_id),
            )
            conn.commit()

    def get_review(self, task_id: str) -> dict | None:
        with self._lock, self._connect() as conn:
            row = conn.execute("SELECT * FROM reviews WHERE task_id = ?", (task_id,)).fetchone()
        return dict(row) if row else None

    @staticmethod
    def _now() -> str:
        return datetime.now(UTC).isoformat()

