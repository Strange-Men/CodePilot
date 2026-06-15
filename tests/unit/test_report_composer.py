from __future__ import annotations

from backend.core.report_contract import REPORT_SECTIONS
from backend.models.context import CodeFileSummary, EvidenceRecord
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
    context.file_summaries.append(
        CodeFileSummary(
            path="tests/test_review.py",
            purpose="Tests review behavior.",
            summary="Tests review behavior.",
        )
    )
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
    assert "**Likely responsibility area:** validated symbols `review`." in report
    assert "**First step:** In `services/review.py`" in report
    assert "**Change risk:** Changes can affect up to 1 resolved internal consumers" in report
    assert "**Validation tests:** Run `tests/test_review.py` before and after the change." in report
    assert "| MaintainabilityAgent | completed | 1 | high=1 | 0.88 | 1 |" in report
    assert "## MaintainabilityAgent" in report


def test_composer_uses_useful_fields_in_action_plan(sample_context) -> None:
    context = sample_context.to_review_context()
    evidence_id = stable_evidence_id("app.py", 1, 10, "def main(): pass")
    context.evidence = [
        EvidenceRecord(
            evidence_id=evidence_id,
            file_path="app.py",
            start_line=1,
            end_line=10,
            snippet="def main(): pass",
            kind="symbol",
            symbols=["main"],
        )
    ]
    draft = StructuredReviewDraft(
        findings=[
            ReviewFinding(
                section="Architecture Summary",
                title="Duplicate dispatch logic",
                description="Two paths implement similar dispatch.",
                severity="medium",
                confidence=0.8,
                files=["app.py"],
                recommendation="Extract shared logic.",
                evidence_ids=[evidence_id],
                impact="Changes may need to be duplicated across both paths, risking inconsistency.",
                first_step="Add characterization tests covering both dispatch paths before refactoring.",
                validation_tests=["tests/test_blueprints.py", "tests/test_basic.py"],
                confidence_rationale="Multiple evidence records confirm the pattern.",
                caveat="Mature public API; avoid breaking compatibility without migration path.",
            )
        ]
    )

    report = HumanReadableReportComposer().compose(context, draft)

    assert "**Why it matters:** Changes may need to be duplicated across both paths, risking inconsistency." in report
    assert "**First step:** Add characterization tests covering both dispatch paths before refactoring." in report
    assert "**Validation tests:** `tests/test_blueprints.py`, `tests/test_basic.py`" in report
    assert "**Caveat:** Mature public API; avoid breaking compatibility without migration path." in report


def test_composer_falls_back_to_description_when_impact_missing(sample_context) -> None:
    context = sample_context.to_review_context()
    evidence_id = stable_evidence_id("app.py", 1, 10, "def main(): pass")
    context.evidence = [
        EvidenceRecord(
            evidence_id=evidence_id,
            file_path="app.py",
            start_line=1,
            end_line=10,
            snippet="def main(): pass",
            kind="symbol",
            symbols=["main"],
        )
    ]
    draft = StructuredReviewDraft(
        findings=[
            ReviewFinding(
                section="Architecture Summary",
                title="Simple finding",
                description="A finding without useful fields.",
                severity="low",
                confidence=0.5,
                files=["app.py"],
                recommendation="Review the code.",
                evidence_ids=[evidence_id],
            )
        ]
    )

    report = HumanReadableReportComposer().compose(context, draft)

    assert "**Why it matters:** A finding without useful fields." in report
    assert "**Caveat:**" not in report


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


def test_composer_downranks_test_only_actions(sample_context) -> None:
    production = ReviewFinding(
        section="Refactoring Suggestions",
        title="Production boundary",
        description="Production risk.",
        severity="medium",
        files=["src/service.py"],
        recommendation="Narrow the service boundary.",
        evidence_ids=["ev_production"],
    )
    test_only = ReviewFinding(
        section="Refactoring Suggestions",
        title="Test helper",
        description="Test risk.",
        severity="critical",
        files=["tests/test_service.py"],
        recommendation="Split the test helper.",
        evidence_ids=["ev_test"],
    )

    report = HumanReadableReportComposer().compose(
        sample_context.to_review_context(),
        StructuredReviewDraft(findings=[test_only, production]),
    )

    action_plan = report.split("# Action Plan", 1)[1].split("# Evidence Appendix", 1)[0]
    assert action_plan.index("Production boundary") < action_plan.index("Test helper")


def test_table_cell_escapes_pipes_and_normalizes_multiline_whitespace() -> None:
    value = "  foo | bar\nline one\t  line two  "

    assert HumanReadableReportComposer._table_cell(value) == r"foo \| bar line one line two"


def test_table_cell_preserves_windows_paths_and_readable_markdown() -> None:
    values = [
        r"C:\folder\file.py",
        "**bold**",
        "[link](https://example.com)",
        "`code`",
    ]

    assert [HumanReadableReportComposer._table_cell(value) for value in values] == values


def test_table_cell_pipe_escaping_is_idempotent() -> None:
    escaped = HumanReadableReportComposer._table_cell("foo | bar")

    assert HumanReadableReportComposer._table_cell(escaped) == escaped
