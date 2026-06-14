from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from backend.models.context import EvidenceRecord
from backend.models.review import ReviewStatus
from backend.models.review_state import AgentExecutionState, ReviewState
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


def test_store_persists_agent_states_with_validation_status(tmp_path: Path) -> None:
    store = ReviewStore(tmp_path / "reviews.db")
    store.create_review("task-1", "https://github.com/example/one")
    finding = ReviewFinding(
        section="Code Smells",
        description="Validated finding.",
        evidence_ids=["ev_safe"],
    )

    store.replace_agent_states(
        "task-1",
        [
            AgentExecutionState(
                agent_id="CodeSmellAgent",
                status="completed",
                findings=[finding],
                evidence_ids=["ev_safe"],
                prompt_tokens=12,
                completion_tokens=8,
                llm_calls=1,
            ),
            AgentExecutionState(
                agent_id="FailingAgent",
                status="failed",
                error="agent failed",
                validation_status="failed",
            ),
        ],
    )

    rows = store.get_agent_states("task-1")
    by_agent = {row["agent_id"]: row for row in rows}
    assert by_agent["CodeSmellAgent"]["validation_status"] == "validated"
    assert by_agent["CodeSmellAgent"]["findings"][0]["evidence_ids"] == ["ev_safe"]
    assert by_agent["CodeSmellAgent"]["llm_calls"] == 1
    assert by_agent["FailingAgent"]["status"] == "failed"
    assert by_agent["FailingAgent"]["validation_status"] == "failed"


def test_store_initializes_schema_version(tmp_path: Path) -> None:
    store = ReviewStore(tmp_path / "reviews.db")

    assert store.schema_version == "1"


def test_store_preserves_existing_schema_version(tmp_path: Path) -> None:
    database_path = tmp_path / "reviews.db"
    store = ReviewStore(database_path)
    assert store.schema_version == "1"

    with store._connect() as conn:
        conn.execute(
            "UPDATE schema_metadata SET value = '2' WHERE key = 'schema_version'"
        )
        conn.commit()

    store2 = ReviewStore(database_path)
    assert store2.schema_version == "2"


def test_store_persists_review_state_for_internal_inspection(tmp_path: Path, sample_context) -> None:
    store = ReviewStore(tmp_path / "reviews.db")
    store.create_review("task-1", "https://github.com/example/one")
    context = sample_context.to_review_context()
    context.evidence = [
        EvidenceRecord(
            evidence_id="ev_safe",
            file_path="app.py",
            start_line=1,
            end_line=2,
            snippet="password=super-secret",
            symbols=["create_app"],
        )
    ]
    finding = ReviewFinding(
        section="Architecture Summary",
        description="Validated finding.",
        evidence_ids=["ev_safe"],
    )
    state = ReviewState(
        task_id="task-1",
        context=context,
        evidence_bundles={"ArchitectureAgent": context.evidence},
        agent_results=[
            AgentExecutionState(
                agent_id="ArchitectureAgent",
                status="completed",
                findings=[finding],
                evidence_ids=["ev_safe"],
            )
        ],
        validated_findings=[finding],
    )

    store.replace_structured_findings("task-1", [finding], context.evidence)
    store.replace_agent_states("task-1", state.agent_results)
    store.replace_review_state("task-1", state.safe_snapshot())

    persisted_state = store.get_review_state("task-1")
    inspection = store.inspect_review("task-1")
    assert persisted_state is not None
    assert persisted_state.evidence_index[0].evidence_id == "ev_safe"
    assert inspection is not None
    assert inspection["structured_findings"][0]["evidence_ids"] == ["ev_safe"]
    assert inspection["review_state"]["evidence_bundles"] == {"ArchitectureAgent": ["ev_safe"]}
    assert "super-secret" not in str(inspection)
    assert "snippet" not in str(inspection["review_state"])


def test_delete_review_explicitly_removes_all_related_rows(tmp_path: Path, sample_context) -> None:
    store = ReviewStore(tmp_path / "reviews.db")
    store.create_review("task-1", "https://github.com/example/one")
    store.create_review("task-2", "https://github.com/example/two")
    store.update_status("task-1", ReviewStatus.completed, report_markdown="# Complete")
    store.update_status("task-2", ReviewStatus.completed, report_markdown="# Keep")
    context = sample_context.to_review_context()
    evidence = EvidenceRecord(
        evidence_id="ev_safe",
        file_path="app.py",
        start_line=1,
        end_line=2,
        snippet="password=super-secret",
        symbols=["create_app"],
    )
    context.evidence = [evidence]
    finding = ReviewFinding(
        section="Architecture Summary",
        description="Validated finding.",
        evidence_ids=["ev_safe"],
    )
    agent_state = AgentExecutionState(
        agent_id="ArchitectureAgent",
        status="completed",
        findings=[finding],
        evidence_ids=["ev_safe"],
    )
    review_state = ReviewState(
        task_id="task-1",
        context=context,
        evidence_bundles={"ArchitectureAgent": [evidence]},
        agent_results=[agent_state],
        validated_findings=[finding],
    )
    store.replace_structured_findings("task-1", [finding], [evidence])
    store.replace_agent_states("task-1", [agent_state])
    store.replace_review_state("task-1", review_state.safe_snapshot())

    assert store.delete_review("task-1") is True

    assert store.get_review("task-1") is None
    assert store.get_review("task-2") is not None
    with store._connect() as conn:
        for table in (
            "review_graph_states",
            "review_agent_states",
            "review_evidence_refs",
            "review_findings",
        ):
            count = conn.execute(
                f"SELECT COUNT(*) FROM {table} WHERE task_id = ?",
                ("task-1",),
            ).fetchone()[0]
            assert count == 0


def test_delete_review_rejects_active_status(tmp_path: Path) -> None:
    store = ReviewStore(tmp_path / "reviews.db")
    store.create_review("task-1", "https://github.com/example/one")
    store.update_status("task-1", ReviewStatus.reviewing)

    with pytest.raises(ValueError, match="completed or failed"):
        store.delete_review("task-1")

    assert store.get_review("task-1")["status"] == ReviewStatus.reviewing.value


def test_fail_stale_reviews_only_updates_old_intermediate_statuses(tmp_path: Path) -> None:
    store = ReviewStore(tmp_path / "reviews.db")
    cutoff = datetime(2026, 6, 14, 12, 0, tzinfo=UTC)
    statuses = [
        ReviewStatus.pending,
        ReviewStatus.cloning,
        ReviewStatus.parsing,
        ReviewStatus.summarizing,
        ReviewStatus.reviewing,
    ]
    for index, status in enumerate(statuses):
        task_id = f"task-{index}"
        store.create_review(task_id, "https://github.com/example/one")
        _set_review_status_and_updated_at(store, task_id, status, cutoff - timedelta(hours=1))

    updated_count = store.fail_stale_reviews(
        older_than=cutoff,
        error_message="Review was interrupted before completion.",
    )

    assert updated_count == len(statuses)
    for index in range(len(statuses)):
        row = store.get_review(f"task-{index}")
        assert row["status"] == ReviewStatus.failed.value
        assert row["error"] == "Review was interrupted before completion."


def test_fail_stale_reviews_leaves_recent_intermediate_statuses_untouched(tmp_path: Path) -> None:
    store = ReviewStore(tmp_path / "reviews.db")
    cutoff = datetime(2026, 6, 14, 12, 0, tzinfo=UTC)
    store.create_review("task-1", "https://github.com/example/one")
    _set_review_status_and_updated_at(
        store,
        "task-1",
        ReviewStatus.reviewing,
        cutoff + timedelta(seconds=1),
    )

    updated_count = store.fail_stale_reviews(
        older_than=cutoff,
        error_message="Review was interrupted before completion.",
    )

    assert updated_count == 0
    assert store.get_review("task-1")["status"] == ReviewStatus.reviewing.value


def test_fail_stale_reviews_leaves_completed_and_failed_untouched(tmp_path: Path) -> None:
    store = ReviewStore(tmp_path / "reviews.db")
    cutoff = datetime(2026, 6, 14, 12, 0, tzinfo=UTC)
    for task_id, status in (
        ("completed-task", ReviewStatus.completed),
        ("failed-task", ReviewStatus.failed),
    ):
        store.create_review(task_id, "https://github.com/example/one")
        _set_review_status_and_updated_at(store, task_id, status, cutoff - timedelta(days=1))

    updated_count = store.fail_stale_reviews(
        older_than=cutoff,
        error_message="Review was interrupted before completion.",
    )

    assert updated_count == 0
    assert store.get_review("completed-task")["status"] == ReviewStatus.completed.value
    assert store.get_review("failed-task")["status"] == ReviewStatus.failed.value


def test_fail_stale_reviews_leaves_malformed_timestamps_untouched(tmp_path: Path) -> None:
    store = ReviewStore(tmp_path / "reviews.db")
    store.create_review("task-1", "https://github.com/example/one")
    with store._connect() as conn:
        conn.execute(
            "UPDATE reviews SET status = ?, updated_at = ? WHERE task_id = ?",
            (ReviewStatus.parsing.value, "not-a-timestamp", "task-1"),
        )
        conn.commit()

    updated_count = store.fail_stale_reviews(
        older_than=datetime(2026, 6, 14, 12, 0, tzinfo=UTC),
        error_message="Review was interrupted before completion.",
    )

    assert updated_count == 0
    assert store.get_review("task-1")["status"] == ReviewStatus.parsing.value


def test_fail_stale_reviews_returns_updated_count(tmp_path: Path) -> None:
    store = ReviewStore(tmp_path / "reviews.db")
    cutoff = datetime(2026, 6, 14, 12, 0, tzinfo=UTC)
    for task_id in ("task-1", "task-2"):
        store.create_review(task_id, "https://github.com/example/one")
        _set_review_status_and_updated_at(
            store,
            task_id,
            ReviewStatus.pending,
            cutoff - timedelta(minutes=31),
        )
    store.create_review("recent-task", "https://github.com/example/one")
    _set_review_status_and_updated_at(
        store,
        "recent-task",
        ReviewStatus.pending,
        cutoff + timedelta(seconds=1),
    )

    updated_count = store.fail_stale_reviews(
        older_than=cutoff,
        error_message="Review was interrupted before completion.",
    )

    assert updated_count == 2


def _set_review_status_and_updated_at(
    store: ReviewStore,
    task_id: str,
    status: ReviewStatus,
    updated_at: datetime,
) -> None:
    with store._connect() as conn:
        conn.execute(
            "UPDATE reviews SET status = ?, updated_at = ? WHERE task_id = ?",
            (status.value, updated_at.isoformat(), task_id),
        )
        conn.commit()
