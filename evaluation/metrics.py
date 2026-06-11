from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from backend.models.review_state import AgentExecutionState
from backend.models.structured_review import ReviewFinding

REPORT_MARKDOWN_MAX_CHARS = 5000


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
    report_markdown: str = ""
    quality_score: float | None = None
    quality_scores: dict[str, float] | None = None
    failed_checks: list[str] | None = None


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
    overall_quality_score: float | None
    category_metrics: list[CategoryMetrics]
    repo_results: list[RepoResult]


@dataclass(frozen=True)
class HallucinationMetrics:
    evidence_validity: float
    unsupported_claim_rate: float
    grounding_score: float
    evidence_density: float


@dataclass(frozen=True)
class FindingQualityMetrics:
    actionability: float
    specificity: float
    severity_distribution: dict[str, int]
    average_confidence: float
    evidence_density: float


@dataclass(frozen=True)
class AgentEvaluationMetrics:
    agent_name: str
    finding_count: int
    hallucination: HallucinationMetrics
    quality: FindingQualityMetrics


@dataclass(frozen=True)
class RetrievalEvaluationMetrics:
    agent_count: int
    average_precision_like: float
    average_recall_like: float
    average_token_utilization: float
    total_latency_ms: float
    total_selected_evidence: int
    large_repo_mode: bool


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
    if expected_language in {"javascript", "mixed", "python"} and result.total_python_files == 0:
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
        overall_quality_score=(
            sum(r.quality_score for r in results if r.quality_score is not None)
            / len([r for r in results if r.quality_score is not None])
            if any(r.quality_score is not None for r in results)
            else None
        ),
        category_metrics=all_metrics,
        repo_results=results,
    )


def compute_hallucination_metrics(
    findings: list[ReviewFinding],
    valid_evidence_ids: set[str],
) -> HallucinationMetrics:
    if not findings:
        return HallucinationMetrics(
            evidence_validity=1.0,
            unsupported_claim_rate=0.0,
            grounding_score=1.0,
            evidence_density=0.0,
        )
    total_evidence_refs = sum(len(finding.evidence_ids) for finding in findings)
    valid_refs = sum(
        1
        for finding in findings
        for evidence_id in finding.evidence_ids
        if evidence_id in valid_evidence_ids
    )
    supported_findings = sum(
        1
        for finding in findings
        if finding.evidence_ids and all(evidence_id in valid_evidence_ids for evidence_id in finding.evidence_ids)
    )
    evidence_validity = valid_refs / total_evidence_refs if total_evidence_refs else 0.0
    unsupported_claim_rate = 1 - (supported_findings / len(findings))
    grounding_score = (evidence_validity + (1 - unsupported_claim_rate)) / 2
    return HallucinationMetrics(
        evidence_validity=evidence_validity,
        unsupported_claim_rate=unsupported_claim_rate,
        grounding_score=grounding_score,
        evidence_density=total_evidence_refs / len(findings),
    )


def compute_finding_quality_metrics(findings: list[ReviewFinding]) -> FindingQualityMetrics:
    if not findings:
        return FindingQualityMetrics(
            actionability=0.0,
            specificity=0.0,
            severity_distribution={},
            average_confidence=0.0,
            evidence_density=0.0,
        )
    actionable = sum(1 for finding in findings if finding.recommendation)
    specific = sum(1 for finding in findings if finding.files and finding.evidence_ids)
    severity_distribution: dict[str, int] = {}
    confidence_values: list[float] = []
    evidence_refs = 0
    for finding in findings:
        severity_distribution[finding.severity] = severity_distribution.get(finding.severity, 0) + 1
        if finding.confidence is not None:
            confidence_values.append(finding.confidence)
        evidence_refs += len(finding.evidence_ids)
    return FindingQualityMetrics(
        actionability=actionable / len(findings),
        specificity=specific / len(findings),
        severity_distribution=severity_distribution,
        average_confidence=sum(confidence_values) / len(confidence_values) if confidence_values else 0.0,
        evidence_density=evidence_refs / len(findings),
    )


def compute_agent_metrics(
    findings_by_agent: dict[str, list[ReviewFinding]],
    valid_evidence_ids: set[str],
) -> list[AgentEvaluationMetrics]:
    return [
        AgentEvaluationMetrics(
            agent_name=agent_name,
            finding_count=len(findings),
            hallucination=compute_hallucination_metrics(findings, valid_evidence_ids),
            quality=compute_finding_quality_metrics(findings),
        )
        for agent_name, findings in sorted(findings_by_agent.items())
    ]


def compute_retrieval_metrics(agent_states: list[AgentExecutionState]) -> RetrievalEvaluationMetrics:
    retrieval_states = [
        state
        for state in agent_states
        if "retrieval_precision_like" in state.metadata
    ]
    if not retrieval_states:
        return RetrievalEvaluationMetrics(
            agent_count=0,
            average_precision_like=0.0,
            average_recall_like=0.0,
            average_token_utilization=0.0,
            total_latency_ms=0.0,
            total_selected_evidence=0,
            large_repo_mode=False,
        )
    return RetrievalEvaluationMetrics(
        agent_count=len(retrieval_states),
        average_precision_like=_average_metadata(retrieval_states, "retrieval_precision_like"),
        average_recall_like=_average_metadata(retrieval_states, "retrieval_recall_like"),
        average_token_utilization=_average_metadata(retrieval_states, "retrieval_token_utilization"),
        total_latency_ms=sum(float(state.metadata.get("retrieval_latency_ms") or 0.0) for state in retrieval_states),
        total_selected_evidence=sum(
            int(state.metadata.get("retrieval_selected_evidence") or 0)
            for state in retrieval_states
        ),
        large_repo_mode=any(bool(state.metadata.get("retrieval_large_repo_mode")) for state in retrieval_states),
    )


def _average_metadata(agent_states: list[AgentExecutionState], key: str) -> float:
    return sum(float(state.metadata.get(key) or 0.0) for state in agent_states) / len(agent_states)


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
        "overall_quality_score": (
            round(report.overall_quality_score, 2)
            if report.overall_quality_score is not None
            else None
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
                "report_markdown": r.report_markdown,
                "quality_score": r.quality_score,
                "quality_scores": r.quality_scores,
                "failed_checks": r.failed_checks or [],
            }
            for r in report.repo_results
        ],
    }


def v3_metrics_to_dict(metrics: list[AgentEvaluationMetrics]) -> list[dict[str, Any]]:
    return [
        {
            "agent_name": metric.agent_name,
            "finding_count": metric.finding_count,
            "hallucination": {
                "evidence_validity": round(metric.hallucination.evidence_validity, 4),
                "unsupported_claim_rate": round(metric.hallucination.unsupported_claim_rate, 4),
                "grounding_score": round(metric.hallucination.grounding_score, 4),
                "evidence_density": round(metric.hallucination.evidence_density, 2),
            },
            "quality": {
                "actionability": round(metric.quality.actionability, 4),
                "specificity": round(metric.quality.specificity, 4),
                "severity_distribution": metric.quality.severity_distribution,
                "average_confidence": round(metric.quality.average_confidence, 4),
                "evidence_density": round(metric.quality.evidence_density, 2),
            },
        }
        for metric in metrics
    ]


def retrieval_metrics_to_dict(metrics: RetrievalEvaluationMetrics) -> dict[str, Any]:
    return {
        "agent_count": metrics.agent_count,
        "average_precision_like": round(metrics.average_precision_like, 4),
        "average_recall_like": round(metrics.average_recall_like, 4),
        "average_token_utilization": round(metrics.average_token_utilization, 4),
        "total_latency_ms": round(metrics.total_latency_ms, 3),
        "total_selected_evidence": metrics.total_selected_evidence,
        "large_repo_mode": metrics.large_repo_mode,
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
    if report.overall_quality_score is not None:
        lines.append(f"| Report Quality | {report.overall_quality_score:.2f}/100 |")
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
        "| Runtime | Source Files | Details |"
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

    scored = [r for r in report.repo_results if r.quality_score is not None]
    if scored:
        lines.append("\n## Report Quality Scores\n")
        lines.append("| Repository | Aggregate | Failed Checks |")
        lines.append("| --- | ---: | --- |")
        for result in scored:
            failed_checks = ", ".join(result.failed_checks or []) or "None"
            lines.append(f"| {result.repo_name} | {result.quality_score:.2f} | {failed_checks} |")

    return "\n".join(lines) + "\n"
