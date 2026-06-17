from __future__ import annotations

import argparse
import json
from dataclasses import asdict, dataclass
from pathlib import Path

from backend.models.context import CodeFileSummary, EvidenceRecord, RepositoryContext, ReviewContext
from backend.models.review_state import AgentExecutionState
from backend.models.structured_review import ReviewFinding, StructuredReviewDraft
from backend.reviewers.report_composer import HumanReadableReportComposer
from backend.services.evidence import stable_evidence_id
from backend.services.insights import RepositoryInsightEngine


@dataclass(frozen=True)
class ReportQualityCheck:
    name: str
    passed: bool
    details: str


@dataclass(frozen=True)
class ReportQualityEvaluation:
    version: str
    checks: list[ReportQualityCheck]
    report_characters: int
    report_lines: int

    @property
    def passed(self) -> bool:
        return all(check.passed for check in self.checks)

    def to_dict(self) -> dict:
        return {
            "version": self.version,
            "passed": self.passed,
            "summary": {
                "passed": sum(check.passed for check in self.checks),
                "failed": sum(not check.passed for check in self.checks),
                "total": len(self.checks),
            },
            "report_characters": self.report_characters,
            "report_lines": self.report_lines,
            "checks": [asdict(check) for check in self.checks],
        }

    def to_markdown(self) -> str:
        lines = [
            "# CodePilot V3.4 Report Quality Evaluation",
            "",
            f"Overall: **{'PASS' if self.passed else 'FAIL'}**",
            "",
            "| Check | Result | Details |",
            "| --- | --- | --- |",
        ]
        lines.extend(
            f"| {check.name} | {'PASS' if check.passed else 'FAIL'} | {check.details} |"
            for check in self.checks
        )
        lines.extend(
            [
                "",
                f"- Report characters: {self.report_characters}",
                f"- Report lines: {self.report_lines}",
            ]
        )
        return "\n".join(lines) + "\n"


def run_report_quality_evaluation() -> ReportQualityEvaluation:
    context, draft, agent_states, secret_marker = _quality_sample()
    report = HumanReadableReportComposer().compose(context, draft, agent_states)
    valid_evidence_ids = {record.evidence_id for record in context.evidence}
    action_plan = report.split("# Action Plan", 1)[1].split("# Evidence Appendix", 1)[0]
    architecture_map = report.split("# Key Architecture Map", 1)[1].split("# Agent Summary", 1)[0]
    actionable_count = sum(bool(finding.recommendation) for finding in draft.findings)

    checks = [
        ReportQualityCheck(
            name="flask_not_cli_only",
            passed="web framework" in context.insights.repository_type.lower()
            and "cli tool" not in context.insights.repository_type.lower(),
            details=f"classified as {context.insights.repository_type}",
        ),
        ReportQualityCheck(
            name="production_recommendations_first",
            passed=action_plan.index("Application dispatch boundary") < action_plan.index("Test fixture concentration"),
            details="production action appears before the higher-severity test-only action",
        ),
        ReportQualityCheck(
            name="readable_cycle_groups",
            passed=(
                "Cycle group (9 modules):" in architecture_map
                and "+3 more" in architecture_map
                and " -> " not in architecture_map
            ),
            details="long dependency cycle is bounded and does not render as a repeated chain",
        ),
        ReportQualityCheck(
            name="agent_summary_visible",
            passed=(
                "# Agent Summary" in report
                and "ArchitectureAgent" in report
                and "MaintainabilityAgent" in report
            ),
            details="agent status, findings, confidence, severity mix, and evidence counts are present",
        ),
        ReportQualityCheck(
            name="actionable_recommendations",
            passed=(
                action_plan.count("**First step:**") >= actionable_count
                and action_plan.count("**Evidence:**") >= actionable_count
                and action_plan.count("**Validation tests:**") >= actionable_count
            ),
            details="every actionable finding includes a first step, evidence, and validation tests",
        ),
        ReportQualityCheck(
            name="evidence_grounding",
            passed=all(
                finding.evidence_ids
                and all(evidence_id in valid_evidence_ids for evidence_id in finding.evidence_ids)
                for finding in draft.findings
            ),
            details="all sample findings cite evidence IDs present in the safe evidence index",
        ),
        ReportQualityCheck(
            name="readable_and_bounded",
            passed=(
                len(report) <= 30_000
                and len(report.splitlines()) <= 400
                and report.count("# Executive Summary") == 1
                and report.count("# Evidence Appendix") == 1
            ),
            details=f"report size is {len(report)} characters across {len(report.splitlines())} lines",
        ),
        ReportQualityCheck(
            name="self_contained_evidence_appendix",
            passed=(
                "# Evidence Appendix" in report
                and "## E1" in report
                and secret_marker in report  # snippets now included for self-containment
            ),
            details="evidence appendix contains display refs and code snippets for offline readability",
        ),
    ]
    return ReportQualityEvaluation(
        version="3.4",
        checks=checks,
        report_characters=len(report),
        report_lines=len(report.splitlines()),
    )


def _quality_sample() -> tuple[
    ReviewContext,
    StructuredReviewDraft,
    list[AgentExecutionState],
    str,
]:
    summaries = [
        _summary(
            "src/flask/app.py",
            classes=["Flask"],
            functions=["full_dispatch_request"],
            line_count=620,
            function_count=20,
            complexity_estimate=32,
            importance_score=95,
            file_role="Core Module",
            fan_in=5,
            is_hub=True,
        ),
        _summary(
            "src/flask/cli.py",
            functions=["main"],
            importance_score=90,
            file_role="Entry Point",
        ),
        _summary(
            "src/flask/blueprints.py",
            classes=["Blueprint", "Response"],
            functions=["register"],
            importance_score=75,
            file_role="Core Module",
        ),
        _summary(
            "tests/test_app.py",
            functions=["test_dispatch"],
            line_count=1800,
            function_count=70,
            complexity_estimate=90,
            importance_score=100,
        ),
        *[
            _summary(f"src/flask/cycle_{index}.py", importance_score=30 - index)
            for index in range(9)
        ],
    ]
    legacy = RepositoryContext(
        repo_url="https://github.com/pallets/flask",
        total_python_files=len(summaries),
        analyzed_files=len(summaries),
        skipped_files=0,
        file_summaries=summaries,
        repository_summary="Python web framework with request dispatch, blueprints, CLI integration, and tests.",
        language="Python",
        total_lines=sum(summary.line_count for summary in summaries),
        avg_complexity=sum(summary.complexity_estimate for summary in summaries) / len(summaries),
        entry_points=["src/flask/cli.py"],
        core_modules=["src/flask/app.py", "src/flask/blueprints.py"],
        supporting_modules=[f"src/flask/cycle_{index}.py" for index in range(9)],
        dependency_edges={
            "src/flask/cli.py": ["src/flask/app.py"],
            "src/flask/blueprints.py": ["src/flask/app.py"],
        },
        circular_dependencies=[[f"src/flask/cycle_{index}.py" for index in range(9)]],
        hub_files=["src/flask/app.py"],
    )
    context = legacy.to_review_context()
    context.insights = RepositoryInsightEngine().generate(context)

    secret_marker = "V34_SECRET_SNIPPET"
    production_evidence_id = stable_evidence_id(
        "src/flask/app.py",
        440,
        470,
        f"def full_dispatch_request():\n    marker = '{secret_marker}'",
    )
    test_evidence_id = stable_evidence_id(
        "tests/test_app.py",
        100,
        140,
        "def test_dispatch():\n    pass",
    )
    context.evidence = [
        EvidenceRecord(
            evidence_id=production_evidence_id,
            file_path="src/flask/app.py",
            start_line=440,
            end_line=470,
            snippet=f"def full_dispatch_request():\n    marker = '{secret_marker}'",
            kind="symbol",
            symbols=["Flask", "full_dispatch_request"],
        ),
        EvidenceRecord(
            evidence_id=test_evidence_id,
            file_path="tests/test_app.py",
            start_line=100,
            end_line=140,
            snippet="def test_dispatch():\n    pass",
            kind="symbol",
            symbols=["test_dispatch"],
        ),
    ]
    production_finding = ReviewFinding(
        section="Architecture Summary",
        title="Application dispatch boundary",
        description="The central request dispatch path has broad internal dependency pressure.",
        severity="high",
        category="architecture",
        confidence=0.91,
        files=["src/flask/app.py"],
        recommendation="Stabilize the dispatch contract before extracting smaller request-processing steps.",
        evidence_ids=[production_evidence_id],
        evidence=[f"{production_evidence_id} -> src/flask/app.py:440-470"],
    )
    test_finding = ReviewFinding(
        section="Maintainability Issues",
        title="Test fixture concentration",
        description="A large test module concentrates many dispatch scenarios.",
        severity="critical",
        category="maintainability",
        confidence=0.95,
        files=["tests/test_app.py"],
        recommendation="Group related scenarios behind focused fixtures without changing production behavior.",
        evidence_ids=[test_evidence_id],
        evidence=[f"{test_evidence_id} -> tests/test_app.py:100-140"],
    )
    draft = StructuredReviewDraft(findings=[test_finding, production_finding])
    agent_states = [
        AgentExecutionState(
            agent_id="ArchitectureAgent",
            status="completed",
            findings=[production_finding],
            evidence_ids=[production_evidence_id],
        ),
        AgentExecutionState(
            agent_id="MaintainabilityAgent",
            status="completed",
            findings=[test_finding],
            evidence_ids=[test_evidence_id],
        ),
    ]
    return context, draft, agent_states, secret_marker


def _summary(path: str, **overrides) -> CodeFileSummary:
    values = {
        "path": path,
        "purpose": "Implements framework behavior.",
        "summary": "Implements framework behavior.",
        "line_count": 80,
        "function_count": 3,
        "complexity_estimate": 5,
        "importance_score": 40.0,
        "file_role": "Supporting Module",
    }
    values.update(overrides)
    return CodeFileSummary(**values)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run deterministic V3.4 report quality checks.")
    parser.add_argument("--json-output", type=Path)
    parser.add_argument("--markdown-output", type=Path)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    evaluation = run_report_quality_evaluation()
    payload = json.dumps(evaluation.to_dict(), indent=2)
    print(payload)
    if args.json_output:
        args.json_output.parent.mkdir(parents=True, exist_ok=True)
        args.json_output.write_text(payload + "\n", encoding="utf-8")
    if args.markdown_output:
        args.markdown_output.parent.mkdir(parents=True, exist_ok=True)
        args.markdown_output.write_text(evaluation.to_markdown(), encoding="utf-8")
    return 0 if evaluation.passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
