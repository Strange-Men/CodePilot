from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class RepoResult:
    """Enriched result for a single repository evaluation."""

    repo_id: str
    repo_url: str
    repo_name: str
    categories: dict[str, str]
    tags: list[str]
    status: str
    passed: bool
    details: str
    runtime_seconds: float
    total_python_files: int
    analyzed_files: int
    skipped_files: int
    has_report: bool
    has_all_sections: bool


@dataclass
class CategoryMetrics:
    """Aggregated metrics for a category dimension."""

    category_type: str
    category_value: str
    total_repos: int
    passed_repos: int
    failed_repos: int
    review_success_rate: float
    clone_failure_count: int
    parse_failure_count: int
    report_completeness_rate: float
    average_runtime_seconds: float
    total_python_files_found: int
    total_analyzed_files: int
    total_skipped_files: int


@dataclass
class EvalReport:
    """Top-level evaluation report."""

    timestamp: str
    config_version: str
    total_repos: int
    passed_repos: int
    failed_repos: int
    overall_success_rate: float
    overall_average_runtime_seconds: float
    category_metrics: list[CategoryMetrics]
    repo_results: list[RepoResult]


def detect_clone_failure(details: str, status: str) -> bool:
    """Heuristic: detect if failure was at clone stage."""
    if status != "failed":
        return False
    lower = details.lower()
    return any(
        marker in lower
        for marker in ["clone", "git", "timeout", "connection", "network"]
    )


def detect_parse_issue(result: RepoResult, expected_language: str) -> bool:
    """Detect unexpected parse outcomes."""
    if result.status != "completed":
        return False
    if expected_language == "javascript":
        return False
    if expected_language == "python" and result.total_python_files == 0:
        return True
    return False


def compute_category_metrics(
    results: list[RepoResult],
    category_type: str,
) -> list[CategoryMetrics]:
    """Group results by a category dimension and compute aggregates."""
    groups: dict[str, list[RepoResult]] = {}
    for result in results:
        value = result.categories.get(category_type, "unknown")
        groups.setdefault(value, []).append(result)

    metrics: list[CategoryMetrics] = []
    for value, group in sorted(groups.items()):
        total = len(group)
        passed = sum(1 for r in group if r.passed)
        failed = total - passed
        completed = [r for r in group if r.status == "completed"]
        clone_failures = sum(
            1 for r in group if detect_clone_failure(r.details, r.status)
        )
        parse_issues = sum(
            1 for r in group if detect_parse_issue(r, r.categories.get("language", "unknown"))
        )
        report_complete = sum(1 for r in completed if r.has_all_sections)

        metrics.append(
            CategoryMetrics(
                category_type=category_type,
                category_value=value,
                total_repos=total,
                passed_repos=passed,
                failed_repos=failed,
                review_success_rate=passed / total if total else 0.0,
                clone_failure_count=clone_failures,
                parse_failure_count=parse_issues,
                report_completeness_rate=(
                    report_complete / len(completed) if completed else 0.0
                ),
                average_runtime_seconds=(
                    sum(r.runtime_seconds for r in group) / total if total else 0.0
                ),
                total_python_files_found=sum(r.total_python_files for r in group),
                total_analyzed_files=sum(r.analyzed_files for r in group),
                total_skipped_files=sum(r.skipped_files for r in group),
            )
        )
    return metrics


def compute_eval_report(
    results: list[RepoResult],
    config_version: str,
    timestamp: str,
) -> EvalReport:
    """Build the full evaluation report from all repo results."""
    total = len(results)
    passed = sum(1 for r in results if r.passed)
    failed = total - passed

    all_metrics: list[CategoryMetrics] = []
    for cat_type in ("size", "language", "health"):
        all_metrics.extend(compute_category_metrics(results, cat_type))

    return EvalReport(
        timestamp=timestamp,
        config_version=config_version,
        total_repos=total,
        passed_repos=passed,
        failed_repos=failed,
        overall_success_rate=passed / total if total else 0.0,
        overall_average_runtime_seconds=(
            sum(r.runtime_seconds for r in results) / total if total else 0.0
        ),
        category_metrics=all_metrics,
        repo_results=results,
    )


def report_to_dict(report: EvalReport) -> dict[str, Any]:
    """Convert EvalReport to a JSON-serializable dict."""
    return {
        "timestamp": report.timestamp,
        "config_version": report.config_version,
        "total_repos": report.total_repos,
        "passed_repos": report.passed_repos,
        "failed_repos": report.failed_repos,
        "overall_success_rate": round(report.overall_success_rate, 4),
        "overall_average_runtime_seconds": round(
            report.overall_average_runtime_seconds, 2
        ),
        "category_metrics": [
            {
                "category_type": m.category_type,
                "category_value": m.category_value,
                "total_repos": m.total_repos,
                "passed_repos": m.passed_repos,
                "failed_repos": m.failed_repos,
                "review_success_rate": round(m.review_success_rate, 4),
                "clone_failure_count": m.clone_failure_count,
                "parse_failure_count": m.parse_failure_count,
                "report_completeness_rate": round(m.report_completeness_rate, 4),
                "average_runtime_seconds": round(m.average_runtime_seconds, 2),
                "total_python_files_found": m.total_python_files_found,
                "total_analyzed_files": m.total_analyzed_files,
                "total_skipped_files": m.total_skipped_files,
            }
            for m in report.category_metrics
        ],
        "repo_results": [
            {
                "repo_id": r.repo_id,
                "repo_url": r.repo_url,
                "repo_name": r.repo_name,
                "categories": r.categories,
                "tags": r.tags,
                "status": r.status,
                "passed": r.passed,
                "details": r.details,
                "runtime_seconds": round(r.runtime_seconds, 2),
                "total_python_files": r.total_python_files,
                "analyzed_files": r.analyzed_files,
                "skipped_files": r.skipped_files,
                "has_report": r.has_report,
                "has_all_sections": r.has_all_sections,
            }
            for r in report.repo_results
        ],
    }


def report_to_markdown(report: EvalReport) -> str:
    """Convert EvalReport to a human-readable Markdown string."""
    lines: list[str] = []
    lines.append("# CodePilot Evaluation Report\n")
    lines.append(f"**Generated:** {report.timestamp}")
    lines.append(f"**Configuration:** default.json v{report.config_version}\n")

    lines.append("## Summary\n")
    lines.append("| Metric | Value |")
    lines.append("|--------|-------|")
    lines.append(f"| Total Repositories | {report.total_repos} |")
    lines.append(f"| Passed | {report.passed_repos} |")
    lines.append(f"| Failed | {report.failed_repos} |")
    lines.append(f"| Success Rate | {report.overall_success_rate * 100:.1f}% |")
    lines.append(
        f"| Average Runtime | {report.overall_average_runtime_seconds:.1f}s |"
    )
    completed = [r for r in report.repo_results if r.status == "completed"]
    report_complete = sum(1 for r in completed if r.has_all_sections)
    completeness = report_complete / len(completed) * 100 if completed else 0.0
    lines.append(f"| Report Completeness | {completeness:.1f}% |")

    for cat_type, title in [
        ("size", "By Size Category"),
        ("language", "By Language Category"),
        ("health", "By Health Category"),
    ]:
        cat_metrics = [
            m for m in report.category_metrics if m.category_type == cat_type
        ]
        if not cat_metrics:
            continue
        lines.append(f"\n## {title}\n")
        label = cat_type.capitalize()
        lines.append(f"| {label} | Passed/Total | Rate | Avg Runtime |")
        lines.append("|--------|-------------|------|-------------|")
        for m in sorted(cat_metrics, key=lambda x: x.category_value):
            lines.append(
                f"| {m.category_value} "
                f"| {m.passed_repos}/{m.total_repos} "
                f"| {m.review_success_rate * 100:.1f}% "
                f"| {m.average_runtime_seconds:.1f}s |"
            )

    lines.append("\n## Per-Repository Results\n")
    lines.append(
        "| # | ID | Repository | Size/Lang/Health | Status | Passed "
        "| Runtime | Python Files | Details |"
    )
    lines.append(
        "|---|-----|-----------|-----------------|--------|--------"
        "|---------|-------------|---------|"
    )
    for i, r in enumerate(report.repo_results, 1):
        cat_str = (
            f"{r.categories.get('size', '?')}/"
            f"{r.categories.get('language', '?')}/"
            f"{r.categories.get('health', '?')}"
        )
        marker = "PASS" if r.passed else "FAIL"
        lines.append(
            f"| {i} | {r.repo_id} | {r.repo_name} | {cat_str} "
            f"| {r.status} | {marker} | {r.runtime_seconds:.1f}s "
            f"| {r.total_python_files} | {r.details} |"
        )

    failures = [r for r in report.repo_results if not r.passed]
    if failures:
        lines.append("\n## Failures\n")
        lines.append("| # | ID | Repository | Status | Error |")
        lines.append("|---|-----|-----------|--------|-------|")
        for i, r in enumerate(failures, 1):
            lines.append(
                f"| {i} | {r.repo_id} | {r.repo_name} "
                f"| {r.status} | {r.details} |"
            )

    return "\n".join(lines) + "\n"
