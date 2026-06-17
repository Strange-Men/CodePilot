from __future__ import annotations

import re
from dataclasses import asdict, dataclass
from statistics import mean

from backend.core.report_contract import REPORT_SECTIONS

MAX_REPORT_CHARACTERS = 30_000
MAX_REPORT_LINES = 400
MAX_MAIN_BODY_CYCLE_ARROWS = 5


@dataclass(frozen=True)
class QualityCheck:
    name: str
    dimension: str
    passed: bool
    details: str


@dataclass(frozen=True)
class QualityDimensionScore:
    name: str
    score: float
    passed_checks: int
    total_checks: int


@dataclass(frozen=True)
class ReportQualityScore:
    aggregate_score: float
    dimensions: list[QualityDimensionScore]
    checks: list[QualityCheck]

    @property
    def passed(self) -> bool:
        return all(check.passed for check in self.checks)

    @property
    def failed_checks(self) -> list[str]:
        return [check.name for check in self.checks if not check.passed]

    def to_dict(self) -> dict:
        return {
            "aggregate_score": self.aggregate_score,
            "passed": self.passed,
            "failed_checks": self.failed_checks,
            "dimensions": [asdict(dimension) for dimension in self.dimensions],
            "checks": [asdict(check) for check in self.checks],
        }


def evaluate_report_quality(
    report: str,
    findings: list[dict],
    evidence_refs: list[dict],
    agent_states: list[dict],
    *,
    tags: list[str] | None = None,
) -> ReportQualityScore:
    tags = tags or []
    evidence_ids = {str(record.get("evidence_id")) for record in evidence_refs}
    action_plan = _section(report, "# Action Plan", "# Evidence Appendix")
    evidence_appendix = _section(report, "# Evidence Appendix", None)
    main_body = report.split("# Evidence Appendix", 1)[0]
    actionable = [finding for finding in findings if finding.get("recommendation")]
    checks = [
        *_readability_checks(report, main_body),
        *_actionability_checks(action_plan, actionable),
        *_grounding_checks(report, evidence_appendix, findings, evidence_ids),
        *_agent_visibility_checks(report, agent_states),
        *_classification_checks(report, action_plan, findings, tags),
    ]
    dimensions: list[QualityDimensionScore] = []
    for dimension in (
        "readability",
        "actionability",
        "grounding",
        "agent_visibility",
        "classification_quality",
    ):
        dimension_checks = [check for check in checks if check.dimension == dimension]
        passed = sum(check.passed for check in dimension_checks)
        total = len(dimension_checks)
        dimensions.append(
            QualityDimensionScore(
                name=dimension,
                score=round((passed / total) * 100, 2) if total else 100.0,
                passed_checks=passed,
                total_checks=total,
            )
        )
    return ReportQualityScore(
        aggregate_score=round(mean(item.score for item in dimensions), 2),
        dimensions=dimensions,
        checks=checks,
    )


def quality_summary_to_markdown(repo_scores: list[tuple[str, ReportQualityScore]]) -> str:
    lines = [
        "# CodePilot V3.5 Report Quality Summary",
        "",
        "| Repository | Aggregate | Readability | Actionability | Grounding | Agent Visibility | Classification |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for repo_name, score in repo_scores:
        by_name = {dimension.name: dimension.score for dimension in score.dimensions}
        lines.append(
            f"| {repo_name} | {score.aggregate_score:.2f} | "
            f"{by_name['readability']:.2f} | {by_name['actionability']:.2f} | "
            f"{by_name['grounding']:.2f} | {by_name['agent_visibility']:.2f} | "
            f"{by_name['classification_quality']:.2f} |"
        )
    aggregate = mean(score.aggregate_score for _, score in repo_scores) if repo_scores else 0.0
    lines.extend(["", f"Aggregate quality score: **{aggregate:.2f}/100**", "", "## Failed Checks", ""])
    failures = [
        f"- `{repo_name}`: {', '.join(score.failed_checks)}"
        for repo_name, score in repo_scores
        if score.failed_checks
    ]
    lines.extend(failures or ["- None."])
    return "\n".join(lines) + "\n"


def _readability_checks(report: str, main_body: str) -> list[QualityCheck]:
    paragraph_counts: dict[str, int] = {}
    for paragraph in re.split(r"\n\s*\n", main_body):
        normalized = " ".join(paragraph.lower().split())
        if len(normalized) >= 80:
            paragraph_counts[normalized] = paragraph_counts.get(normalized, 0) + 1
    repeated = [paragraph for paragraph, count in paragraph_counts.items() if count > 1]
    max_arrows_in_line = max((line.count(" -> ") for line in main_body.splitlines()), default=0)
    required_once = ["# Executive Summary", "# Action Plan", *[f"# {section}" for section in REPORT_SECTIONS]]
    bounded_sections = all(report.count(heading) == 1 for heading in required_once)
    return [
        QualityCheck(
            "executive_summary_present",
            "readability",
            "# Executive Summary" in report,
            "The report must contain one executive summary.",
        ),
        QualityCheck(
            "action_plan_present",
            "readability",
            "# Action Plan" in report,
            "The report must contain an action plan.",
        ),
        QualityCheck(
            "report_is_bounded",
            "readability",
            (
                len(report) <= MAX_REPORT_CHARACTERS
                and len(report.splitlines()) <= MAX_REPORT_LINES
                and bounded_sections
            ),
            f"{len(report)} characters, {len(report.splitlines())} lines; required sections appear once.",
        ),
        QualityCheck(
            "cycle_chain_is_bounded",
            "readability",
            max_arrows_in_line <= MAX_MAIN_BODY_CYCLE_ARROWS,
            f"The longest main-body line contains {max_arrows_in_line} dependency arrows.",
        ),
        QualityCheck(
            "no_repeated_generic_boilerplate",
            "readability",
            not repeated,
            f"Repeated long paragraph count: {len(repeated)}.",
        ),
    ]


def _actionability_checks(action_plan: str, actionable: list[dict]) -> list[QualityCheck]:
    expected = len(actionable)
    file_count = sum(bool(finding.get("files")) for finding in actionable)
    why_count = action_plan.count("**Why it matters:**")
    first_step_count = action_plan.count("**First step:**")
    validation_count = action_plan.count("**Validation tests:**")
    return [
        QualityCheck(
            "recommendations_name_files",
            "actionability",
            expected == 0 or file_count == expected,
            f"{file_count}/{expected} actionable findings name files.",
        ),
        QualityCheck(
            "recommendations_explain_impact",
            "actionability",
            expected == 0 or why_count >= expected,
            f"{why_count}/{expected} action items explain why they matter.",
        ),
        QualityCheck(
            "recommendations_include_first_step",
            "actionability",
            expected == 0 or first_step_count >= expected,
            f"{first_step_count}/{expected} action items include a first step.",
        ),
        QualityCheck(
            "recommendations_include_validation_hint",
            "actionability",
            expected == 0 or validation_count >= expected,
            f"{validation_count}/{expected} action items include validation guidance.",
        ),
    ]


def _grounding_checks(
    report: str,
    evidence_appendix: str,
    findings: list[dict],
    evidence_ids: set[str],
) -> list[QualityCheck]:
    findings_with_evidence = sum(bool(finding.get("evidence_ids")) for finding in findings)
    valid_findings = sum(
        bool(finding.get("evidence_ids"))
        and all(str(evidence_id) in evidence_ids for evidence_id in finding.get("evidence_ids") or [])
        for finding in findings
    )
    secret_like = bool(
        re.search(
            r"(?:password|secret|api[_-]?key)\s*=\s*['\"][^'\"]{8,}",
            evidence_appendix,
            flags=re.IGNORECASE,
        )
    )
    has_display_refs = bool(re.search(r"## E\d+ ·", evidence_appendix))
    return [
        QualityCheck(
            "findings_include_evidence_ids",
            "grounding",
            not findings or findings_with_evidence == len(findings),
            f"{findings_with_evidence}/{len(findings)} findings cite evidence IDs.",
        ),
        QualityCheck(
            "findings_reference_known_evidence",
            "grounding",
            not findings or valid_findings == len(findings),
            f"{valid_findings}/{len(findings)} findings reference persisted evidence.",
        ),
        QualityCheck(
            "evidence_appendix_present",
            "grounding",
            "# Evidence Appendix" in report,
            "The report must contain a safe evidence appendix.",
        ),
        QualityCheck(
            "self_contained_evidence_appendix",
            "grounding",
            has_display_refs and not secret_like,
            "Evidence appendix uses E1/E2 display refs and contains no leaked secrets.",
        ),
    ]


def _agent_visibility_checks(report: str, agent_states: list[dict]) -> list[QualityCheck]:
    agent_ids = [str(state.get("agent_id") or "") for state in agent_states]
    visible = sum(agent_id in report for agent_id in agent_ids)
    return [
        QualityCheck(
            "agent_summary_present",
            "agent_visibility",
            "# Agent Summary" in report,
            "Agent summary heading is present.",
        ),
        QualityCheck(
            "agent_findings_grouped",
            "agent_visibility",
            "# Agent Findings" in report,
            "Agent findings heading is present.",
        ),
        QualityCheck(
            "agent_state_details_visible",
            "agent_visibility",
            not agent_ids or visible == len(agent_ids),
            f"{visible}/{len(agent_ids)} persisted agents are named in the report.",
        ),
    ]


def _classification_checks(
    report: str,
    action_plan: str,
    findings: list[dict],
    tags: list[str],
) -> list[QualityCheck]:
    lowered = report.lower()
    flask_like = "flask-like" in tags or "web" in tags
    request_response_only = "request-response-only" in tags
    production_findings = [
        finding
        for finding in findings
        if any(not _is_test_path(str(path)) for path in finding.get("files") or [])
    ]
    test_findings = [
        finding
        for finding in findings
        if finding.get("files") and all(_is_test_path(str(path)) for path in finding.get("files") or [])
    ]
    production_first = True
    if production_findings and test_findings:
        first_files_match = re.search(r"\*\*(?:Files|Where):\*\*\s*([^\n]+)", action_plan)
        production_first = bool(
            first_files_match
            and any(
                f"`{path}`" in first_files_match.group(1)
                for finding in production_findings
                for path in finding.get("files") or []
            )
        )
    return [
        QualityCheck(
            "flask_like_not_cli_only",
            "classification_quality",
            not flask_like or ("web framework" in lowered and "cli tool" not in lowered),
            "Flask-like datasets must be classified as a web framework, not CLI-only.",
        ),
        QualityCheck(
            "generic_request_response_not_framework",
            "classification_quality",
            not request_response_only or "web framework" not in lowered,
            "Generic Request/Response names alone must not imply a web framework.",
        ),
        QualityCheck(
            "production_recommendations_precede_tests",
            "classification_quality",
            production_first,
            "The first action item is production-focused when both production and test findings exist.",
        ),
    ]


def _section(report: str, heading: str, next_heading: str | None) -> str:
    if heading not in report:
        return ""
    content = report.split(heading, 1)[1]
    if next_heading and next_heading in content:
        content = content.split(next_heading, 1)[0]
    return content


def _is_test_path(path: str) -> bool:
    normalized = path.replace("\\", "/").lower()
    return normalized.startswith("tests/") or "/tests/" in normalized or normalized.split("/")[-1].startswith("test_")
