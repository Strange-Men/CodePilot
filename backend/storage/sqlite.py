from __future__ import annotations

import json
import sqlite3
from datetime import UTC, datetime
from pathlib import Path
from threading import Lock

from backend.models.context import EvidenceRecord
from backend.models.review import ReviewStatus
from backend.models.review_state import AgentExecutionState, PersistedReviewState
from backend.models.structured_review import ReviewFinding


class ReviewStore:
    def __init__(self, database_path: Path) -> None:
        self.database_path = database_path
        self._lock = Lock()
        self._initialize()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.database_path, timeout=10)
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA busy_timeout = 10000")
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
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS review_findings (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    task_id TEXT NOT NULL,
                    finding_index INTEGER NOT NULL,
                    section TEXT NOT NULL,
                    title TEXT,
                    description TEXT NOT NULL,
                    severity TEXT NOT NULL,
                    category TEXT,
                    confidence REAL,
                    recommendation TEXT,
                    files_json TEXT NOT NULL,
                    evidence_ids_json TEXT NOT NULL,
                    evidence_json TEXT NOT NULL,
                    validation_status TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY (task_id) REFERENCES reviews(task_id) ON DELETE CASCADE,
                    UNIQUE (task_id, finding_index)
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS review_evidence_refs (
                    task_id TEXT NOT NULL,
                    evidence_id TEXT NOT NULL,
                    file_path TEXT NOT NULL,
                    start_line INTEGER NOT NULL,
                    end_line INTEGER NOT NULL,
                    kind TEXT NOT NULL,
                    symbols_json TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY (task_id) REFERENCES reviews(task_id) ON DELETE CASCADE,
                    PRIMARY KEY (task_id, evidence_id)
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS review_agent_states (
                    task_id TEXT NOT NULL,
                    agent_id TEXT NOT NULL,
                    status TEXT NOT NULL,
                    error TEXT,
                    findings_json TEXT NOT NULL,
                    evidence_ids_json TEXT NOT NULL,
                    prompt_tokens INTEGER,
                    completion_tokens INTEGER,
                    llm_calls INTEGER,
                    validation_status TEXT NOT NULL,
                    metadata_json TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    FOREIGN KEY (task_id) REFERENCES reviews(task_id) ON DELETE CASCADE,
                    PRIMARY KEY (task_id, agent_id)
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS review_graph_states (
                    task_id TEXT PRIMARY KEY,
                    state_json TEXT NOT NULL,
                    schema_version TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    FOREIGN KEY (task_id) REFERENCES reviews(task_id) ON DELETE CASCADE
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS schema_metadata (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL
                )
                """
            )
            conn.commit()
            self._add_column_if_missing(conn, "review_findings", "impact", "TEXT")
            self._add_column_if_missing(conn, "review_findings", "first_step", "TEXT")
            self._add_column_if_missing(conn, "review_findings", "validation_tests_json", "TEXT NOT NULL DEFAULT '[]'")
            self._add_column_if_missing(conn, "review_findings", "confidence_rationale", "TEXT")
            self._add_column_if_missing(conn, "review_findings", "caveat", "TEXT")
            existing = conn.execute(
                "SELECT value FROM schema_metadata WHERE key = 'schema_version'"
            ).fetchone()
            if existing is None:
                conn.execute(
                    "INSERT INTO schema_metadata (key, value) VALUES ('schema_version', '1')"
                )
                conn.commit()

    @property
    def schema_version(self) -> str | None:
        with self._lock, self._connect() as conn:
            row = conn.execute(
                "SELECT value FROM schema_metadata WHERE key = 'schema_version'"
            ).fetchone()
        return row["value"] if row else None

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

    def list_reviews(self, limit: int = 50) -> list[dict]:
        with self._lock, self._connect() as conn:
            rows = conn.execute(
                """
                SELECT * FROM reviews
                ORDER BY created_at DESC, task_id DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
        return [dict(row) for row in rows]

    def fail_stale_reviews(
        self,
        older_than: datetime,
        error_message: str,
    ) -> int:
        if older_than.tzinfo is None:
            raise ValueError("older_than must be timezone-aware.")
        intermediate_statuses = (
            ReviewStatus.pending.value,
            ReviewStatus.cloning.value,
            ReviewStatus.parsing.value,
            ReviewStatus.summarizing.value,
            ReviewStatus.reviewing.value,
        )
        placeholders = ", ".join("?" for _ in intermediate_statuses)
        updated_count = 0
        with self._lock, self._connect() as conn:
            conn.execute("BEGIN IMMEDIATE")
            rows = conn.execute(
                f"""
                SELECT task_id, status, updated_at
                FROM reviews
                WHERE status IN ({placeholders})
                """,
                intermediate_statuses,
            ).fetchall()
            now = self._now()
            for row in rows:
                try:
                    updated_at = datetime.fromisoformat(row["updated_at"])
                except (TypeError, ValueError):
                    continue
                if updated_at.tzinfo is None or updated_at >= older_than:
                    continue
                result = conn.execute(
                    """
                    UPDATE reviews
                    SET status = ?, error = ?, updated_at = ?
                    WHERE task_id = ? AND status = ? AND updated_at = ?
                    """,
                    (
                        ReviewStatus.failed.value,
                        error_message,
                        now,
                        row["task_id"],
                        row["status"],
                        row["updated_at"],
                    ),
                )
                updated_count += result.rowcount
            conn.commit()
        return updated_count

    def delete_review(self, task_id: str) -> bool:
        terminal_statuses = {
            ReviewStatus.completed.value,
            ReviewStatus.failed.value,
        }
        with self._lock, self._connect() as conn:
            conn.execute("BEGIN IMMEDIATE")
            row = conn.execute(
                "SELECT status FROM reviews WHERE task_id = ?",
                (task_id,),
            ).fetchone()
            if row is None:
                conn.rollback()
                return False
            if row["status"] not in terminal_statuses:
                conn.rollback()
                raise ValueError("Only completed or failed reviews can be deleted.")

            conn.execute("DELETE FROM review_graph_states WHERE task_id = ?", (task_id,))
            conn.execute("DELETE FROM review_agent_states WHERE task_id = ?", (task_id,))
            conn.execute("DELETE FROM review_evidence_refs WHERE task_id = ?", (task_id,))
            conn.execute("DELETE FROM review_findings WHERE task_id = ?", (task_id,))
            conn.execute("DELETE FROM reviews WHERE task_id = ?", (task_id,))
            conn.commit()
        return True

    def replace_structured_findings(
        self,
        task_id: str,
        findings: list[ReviewFinding],
        evidence: list[EvidenceRecord],
    ) -> None:
        now = self._now()
        with self._lock, self._connect() as conn:
            conn.execute("DELETE FROM review_findings WHERE task_id = ?", (task_id,))
            conn.execute("DELETE FROM review_evidence_refs WHERE task_id = ?", (task_id,))
            for index, finding in enumerate(findings):
                conn.execute(
                    """
                    INSERT INTO review_findings (
                        task_id, finding_index, section, title, description, severity, category,
                        confidence, recommendation, files_json, evidence_ids_json, evidence_json,
                        validation_status, created_at,
                        impact, first_step, validation_tests_json, confidence_rationale, caveat
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        task_id,
                        index,
                        finding.section,
                        finding.title,
                        finding.description,
                        finding.severity,
                        finding.category,
                        finding.confidence,
                        finding.recommendation,
                        self._json(finding.files),
                        self._json(finding.evidence_ids),
                        self._json(finding.evidence),
                        "validated",
                        now,
                        finding.impact,
                        finding.first_step,
                        self._json(finding.validation_tests),
                        finding.confidence_rationale,
                        finding.caveat,
                    ),
                )

            referenced_evidence_ids = {
                evidence_id
                for finding in findings
                for evidence_id in finding.evidence_ids
            }
            for record in evidence:
                if record.evidence_id not in referenced_evidence_ids:
                    continue
                conn.execute(
                    """
                    INSERT INTO review_evidence_refs (
                        task_id, evidence_id, file_path, start_line, end_line, kind, symbols_json, created_at
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        task_id,
                        record.evidence_id,
                        record.file_path,
                        record.start_line,
                        record.end_line,
                        record.kind,
                        self._json(record.symbols),
                        now,
                    ),
                )
            conn.commit()

    def get_structured_findings(self, task_id: str) -> list[dict]:
        with self._lock, self._connect() as conn:
            rows = conn.execute(
                """
                SELECT * FROM review_findings
                WHERE task_id = ?
                ORDER BY finding_index ASC
                """,
                (task_id,),
            ).fetchall()
        return [self._decode_json_columns(dict(row)) for row in rows]

    def get_evidence_refs(self, task_id: str) -> list[dict]:
        with self._lock, self._connect() as conn:
            rows = conn.execute(
                """
                SELECT * FROM review_evidence_refs
                WHERE task_id = ?
                ORDER BY evidence_id ASC
                """,
                (task_id,),
            ).fetchall()
        return [self._decode_json_columns(dict(row)) for row in rows]

    def replace_agent_states(self, task_id: str, agent_states: list[AgentExecutionState]) -> None:
        now = self._now()
        with self._lock, self._connect() as conn:
            conn.execute("DELETE FROM review_agent_states WHERE task_id = ?", (task_id,))
            for state in agent_states:
                conn.execute(
                    """
                    INSERT INTO review_agent_states (
                        task_id, agent_id, status, error, findings_json, evidence_ids_json,
                        prompt_tokens, completion_tokens, llm_calls, validation_status,
                        metadata_json, created_at, updated_at
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        task_id,
                        state.agent_id,
                        state.status,
                        state.error,
                        self._json([finding.model_dump(mode="json") for finding in state.findings]),
                        self._json(state.evidence_ids),
                        state.prompt_tokens,
                        state.completion_tokens,
                        state.llm_calls,
                        state.validation_status,
                        self._json(state.metadata),
                        now,
                        now,
                    ),
                )
            conn.commit()

    def get_agent_states(self, task_id: str) -> list[dict]:
        with self._lock, self._connect() as conn:
            rows = conn.execute(
                """
                SELECT * FROM review_agent_states
                WHERE task_id = ?
                ORDER BY agent_id ASC
                """,
                (task_id,),
            ).fetchall()
        return [self._decode_json_columns(dict(row)) for row in rows]

    def replace_review_state(self, task_id: str, state: PersistedReviewState) -> None:
        now = self._now()
        state = state.model_copy(update={"task_id": task_id})
        payload = state.model_dump(mode="json")
        with self._lock, self._connect() as conn:
            conn.execute(
                """
                INSERT INTO review_graph_states (task_id, state_json, schema_version, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(task_id) DO UPDATE SET
                    state_json = excluded.state_json,
                    schema_version = excluded.schema_version,
                    updated_at = excluded.updated_at
                """,
                (task_id, self._json(payload), "v3.1", now, now),
            )
            conn.commit()

    def get_review_state(self, task_id: str) -> PersistedReviewState | None:
        with self._lock, self._connect() as conn:
            row = conn.execute(
                "SELECT state_json FROM review_graph_states WHERE task_id = ?",
                (task_id,),
            ).fetchone()
        if row is None:
            return None
        return PersistedReviewState.model_validate(json.loads(row["state_json"]))

    def inspect_review(self, task_id: str) -> dict | None:
        review = self.get_review(task_id)
        if review is None:
            return None
        state = self.get_review_state(task_id)
        return {
            "review": review,
            "structured_findings": self.get_structured_findings(task_id),
            "evidence_refs": self.get_evidence_refs(task_id),
            "agent_states": self.get_agent_states(task_id),
            "review_state": state.model_dump(mode="json") if state is not None else None,
        }

    @staticmethod
    def _add_column_if_missing(conn: sqlite3.Connection, table: str, column: str, col_def: str) -> None:
        existing = {row["name"] for row in conn.execute(f"PRAGMA table_info({table})")}
        if column not in existing:
            conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {col_def}")
            conn.commit()

    @staticmethod
    def _now() -> str:
        return datetime.now(UTC).isoformat()

    @staticmethod
    def _json(value: object) -> str:
        return json.dumps(value, sort_keys=True)

    @staticmethod
    def _decode_json_columns(row: dict) -> dict:
        decoded = dict(row)
        for key in list(decoded):
            if key.endswith("_json"):
                decoded[key.removesuffix("_json")] = json.loads(decoded.pop(key))
        return decoded
