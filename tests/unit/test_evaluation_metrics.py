from __future__ import annotations

from evaluation.metrics import RepoResult, compute_category_metrics


def test_python_parse_issue_count_uses_collected_parser_stats() -> None:
    results = [
        RepoResult(
            repo_id="healthy-python",
            repo_url="https://github.com/example/healthy-python.git",
            repo_name="example/healthy-python",
            categories={"language": "python"},
            tags=[],
            status="completed",
            passed=True,
            details="completed",
            runtime_seconds=1.0,
            total_python_files=12,
            analyzed_files=10,
            skipped_files=2,
            has_report=True,
            has_all_sections=True,
        ),
        RepoResult(
            repo_id="empty-python",
            repo_url="https://github.com/example/empty-python.git",
            repo_name="example/empty-python",
            categories={"language": "python"},
            tags=[],
            status="completed",
            passed=True,
            details="completed",
            runtime_seconds=1.0,
            total_python_files=0,
            analyzed_files=0,
            skipped_files=0,
            has_report=True,
            has_all_sections=True,
        ),
    ]

    metrics = compute_category_metrics(results, "language")

    assert metrics[0].category_value == "python"
    assert metrics[0].parse_failure_count == 1
    assert metrics[0].total_python_files_found == 12
    assert metrics[0].total_analyzed_files == 10
    assert metrics[0].total_skipped_files == 2
