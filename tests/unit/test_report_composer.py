from __future__ import annotations

from backend.core.report_contract import REPORT_SECTIONS
from backend.models.context import EvidenceRecord
from backend.models.review_state import AgentExecutionState
from backend.models.structured_review import ReviewFinding, StructuredReviewDraft
from backend.reviewers.markdown_adapter import MarkdownReviewAdapter
from backend.reviewers.report_composer import HumanReadableReportComposer
from backend.services.evidence import stable_evidence_id


def test_composer_builds_readable_report_without_exposing_snippets(sample_context) -> None:
    context = sample_context.to_review_context()
    context.insights.repository_type = "Python backend API"
    evidence_id = stable_evidence_id("services/review.py", 10, 14, "SECRET_VALUE = 'redacted'")
    context.evidence = [
        EvidenceRecord(
            evidence_id=evidence_id,
            file_path="services/review.py",
            start_line=10,
            end_line=14,
            snippet="SECRET_VALUE = 'redacted'",
            kind="symbol",
            symbols=["review"],
        )
    ]
    draft = StructuredReviewDraft(
        findings=[
            ReviewFinding(
                section="Maintainability Issues",
                title="Shared review boundary",
                description="Several callers depend on the review service contract.",
                severity="high",
                confidence=0.88,
                files=["services/review.py"],
                recommendation="Add contract tests before narrowing the service interface.",
                evidence_ids=[evidence_id],
            )
        ]
    )

    agent_states = [
        AgentExecutionState(
            agent_id="MaintainabilityAgent",
            status="completed",
            findings=draft.findings,
            evidence_ids=[evidence_id],
        )
    ]
    report = HumanReadableReportComposer().compose(context, draft, agent_states)

    for heading in [
        "# Executive Summary",
        "# What This Repository Is",
        "# How It Works",
        "# Key Architecture Map",
        "# Agent Summary",
        "# Agent Findings",
        "# Action Plan",
        "# Evidence Appendix",
    ]:
        assert heading in report
    assert list(MarkdownReviewAdapter.extract_sections(report)) == REPORT_SECTIONS
    assert evidence_id in report
    assert "services/review.py:10-14" in report
    assert "SECRET_VALUE" not in report
    assert "**Why it matters:**" in report
    assert "**First step:**" in report
    assert "**Validation hint:**" in report
    assert "| MaintainabilityAgent | completed | 1 | high=1 | 0.88 | 1 |" in report
    assert "## MaintainabilityAgent" in report


def test_composer_bounds_top_risks_and_action_plan(sample_context) -> None:
    findings = [
        ReviewFinding(
            section=REPORT_SECTIONS[index % len(REPORT_SECTIONS)],
            title=f"Finding {index}",
            description=f"Risk {index}.",
            severity="medium",
            confidence=0.5,
            files=[f"src/module_{index}.py"],
            recommendation=f"Address risk {index}.",
            evidence_ids=[f"ev_{index:020x}"],
        )
        for index in range(10)
    ]

    report = HumanReadableReportComposer().compose(
        sample_context.to_review_context(),
        StructuredReviewDraft(findings=findings),
    )

    executive = report.split("# What This Repository Is", 1)[0]
    action_plan = report.split("# Action Plan", 1)[1].split("# Evidence Appendix", 1)[0]
    assert executive.count("- **Finding") == 5
    assert action_plan.count("## ") == 5
