from __future__ import annotations

from pathlib import Path

from backend.models.context import EvidenceRecord
from backend.models.review import ReviewStatus
from backend.models.structured_review import ReviewFinding
from backend.storage.sqlite import ReviewStore


def test_store_initializes_database_file(tmp_path: Path) -> None:
    database_path = tmp_path / "reviews.db"

    ReviewStore(database_path)

    assert database_path.exists()


def test_store_configures_wal_and_busy_timeout(tmp_path: Path) -> None:
    store = ReviewStore(tmp_path / "reviews.db")

    with store._connect() as conn:
        journal_mode = conn.execute("PRAGMA journal_mode").fetchone()[0]
        busy_timeout = conn.execute("PRAGMA busy_timeout").fetchone()[0]

    assert journal_mode == "wal"
    assert busy_timeout == 10000


def test_create_review_stores_pending_status(tmp_path: Path) -> None:
    store = ReviewStore(tmp_path / "reviews.db")

    store.create_review("task-1", "https://github.com/pallets/flask")
    row = store.get_review("task-1")

    assert row is not None
    assert row["task_id"] == "task-1"
    assert row["repo_url"] == "https://github.com/pallets/flask"
    assert row["status"] == "pending"
    assert row["created_at"]
    assert row["updated_at"]


def test_update_status_sets_error(tmp_path: Path) -> None:
    store = ReviewStore(tmp_path / "reviews.db")
    store.create_review("task-1", "https://github.com/pallets/flask")

    store.update_status("task-1", ReviewStatus.failed, error="clone failed")

    row = store.get_review("task-1")
    assert row["status"] == "failed"
    assert row["error"] == "clone failed"


def test_update_status_preserves_report_when_not_replaced(tmp_path: Path) -> None:
    store = ReviewStore(tmp_path / "reviews.db")
    store.create_review("task-1", "https://github.com/pallets/flask")
    store.update_status(
        "task-1",
        ReviewStatus.completed,
        report_markdown="# Architecture Summary\nDone.\n",
        export_path="reports/task-1.md",
    )

    store.update_status("task-1", ReviewStatus.failed, error="later error")

    row = store.get_review("task-1")
    assert row["report_markdown"] == "# Architecture Summary\nDone.\n"
    assert row["export_path"] == "reports/task-1.md"


def test_get_review_returns_none_for_missing_task(tmp_path: Path) -> None:
    store = ReviewStore(tmp_path / "reviews.db")

    assert store.get_review("missing") is None


def test_list_reviews_returns_empty_list_for_new_store(tmp_path: Path) -> None:
    store = ReviewStore(tmp_path / "reviews.db")

    assert store.list_reviews() == []


def test_list_reviews_returns_newest_rows_first(tmp_path: Path) -> None:
    store = ReviewStore(tmp_path / "reviews.db")
    store.create_review("task-1", "https://github.com/example/one")
    store.create_review("task-2", "https://github.com/example/two")

    rows = store.list_reviews()

    assert [row["task_id"] for row in rows] == ["task-2", "task-1"]


def test_list_reviews_applies_limit_without_schema_changes(tmp_path: Path) -> None:
    store = ReviewStore(tmp_path / "reviews.db")
    store.create_review("task-1", "https://github.com/example/one")
    store.create_review("task-2", "https://github.com/example/two")

    rows = store.list_reviews(limit=1)

    assert len(rows) == 1
    with store._connect() as conn:
        columns = [row["name"] for row in conn.execute("PRAGMA table_info(reviews)").fetchall()]
    assert columns == [
        "task_id",
        "repo_url",
        "status",
        "error",
        "report_markdown",
        "export_path",
        "created_at",
        "updated_at",
    ]


def test_store_persists_validated_findings_and_safe_evidence_refs(tmp_path: Path) -> None:
    store = ReviewStore(tmp_path / "reviews.db")
    store.create_review("task-1", "https://github.com/example/one")
    finding = ReviewFinding(
        section="Architecture Summary",
        title="Boundary",
        description="A validated boundary finding.",
        category="architecture",
        severity="medium",
        confidence=0.8,
        files=["app.py"],
        recommendation="Add a contract test.",
        evidence_ids=["ev_safe"],
        evidence=["ev_safe -> app.py:1-2"],
    )
    evidence = EvidenceRecord(
        evidence_id="ev_safe",
        file_path="app.py",
        start_line=1,
        end_line=2,
        snippet="password=super-secret",
        kind="symbol",
        symbols=["create_app"],
    )

    store.replace_structured_findings("task-1", [finding], [evidence])

    findings = store.get_structured_findings("task-1")
    evidence_refs = store.get_evidence_refs("task-1")
    assert findings[0]["validation_status"] == "validated"
    assert findings[0]["evidence_ids"] == ["ev_safe"]
    assert evidence_refs[0]["evidence_id"] == "ev_safe"
    assert evidence_refs[0]["symbols"] == ["create_app"]
    assert "snippet" not in evidence_refs[0]
    with store._connect() as conn:
        persisted = "\n".join(
            str(value)
            for row in conn.execute("SELECT * FROM review_evidence_refs").fetchall()
            for value in row
        )
    assert "super-secret" not in persisted


def test_replacing_structured_findings_is_idempotent(tmp_path: Path) -> None:
    store = ReviewStore(tmp_path / "reviews.db")
    store.create_review("task-1", "https://github.com/example/one")
    first = ReviewFinding(section="Architecture Summary", description="First", evidence_ids=["ev_first"])
    second = ReviewFinding(section="Code Smells", description="Second", evidence_ids=["ev_second"])
    evidence = [
        EvidenceRecord(
            evidence_id="ev_first",
            file_path="first.py",
            start_line=1,
            end_line=1,
            snippet="first",
        ),
        EvidenceRecord(
            evidence_id="ev_second",
            file_path="second.py",
            start_line=2,
            end_line=2,
            snippet="second",
        ),
    ]

    store.replace_structured_findings("task-1", [first], evidence)
    store.replace_structured_findings("task-1", [second], evidence)

    assert [row["description"] for row in store.get_structured_findings("task-1")] == ["Second"]
    assert [row["evidence_id"] for row in store.get_evidence_refs("task-1")] == ["ev_second"]
