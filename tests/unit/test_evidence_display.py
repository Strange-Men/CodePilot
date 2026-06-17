"""Tests for evidence display mapping (E1/E2/E3 refs).

Validates that:
- Raw ev_* IDs map to E1/E2/E3 in first-appearance order
- Same raw ID always maps to the same E-number in a report
- Raw ev_* IDs do not appear in normal exported Markdown
- Evidence appendix uses E1/E2 headings
- Appendix contains file path, line range, symbol, snippet
- Snippet is truncated to safe limits
- Missing evidence detail does not crash export
- zh/en labels are correct
"""

from __future__ import annotations

from backend.models.context import EvidenceRecord
from backend.models.structured_review import ReviewFinding, StructuredReviewDraft
from backend.reviewers.evidence_display import (
    EvidenceDisplayMap,
    build_evidence_appendix,
    format_evidence_ref,
)
from backend.reviewers.report_composer import HumanReadableReportComposer


def _make_finding(
    evidence_ids: list[str],
    **overrides,
) -> ReviewFinding:
    defaults = {
        "section": "Maintainability Issues",
        "title": "Test finding",
        "description": "A test finding.",
        "severity": "medium",
        "confidence": 0.7,
        "files": ["src/app.py"],
        "recommendation": "Fix it.",
    }
    defaults.update(overrides)
    return ReviewFinding(evidence_ids=evidence_ids, **defaults)


def _make_record(
    evidence_id: str,
    file_path: str = "src/app.py",
    start_line: int = 10,
    end_line: int = 20,
    snippet: str = "def foo(): pass",
    kind: str = "symbol",
    symbols: list[str] | None = None,
) -> EvidenceRecord:
    return EvidenceRecord(
        evidence_id=evidence_id,
        file_path=file_path,
        start_line=start_line,
        end_line=end_line,
        snippet=snippet,
        kind=kind,
        symbols=symbols or [],
    )


class TestEvidenceDisplayMap:
    def test_first_appearance_order(self) -> None:
        findings = [
            _make_finding(["ev_bbb", "ev_aaa"]),
            _make_finding(["ev_ccc", "ev_bbb"]),
        ]
        dm = EvidenceDisplayMap.from_findings(findings)
        assert dm.ref("ev_bbb") == "E1"
        assert dm.ref("ev_aaa") == "E2"
        assert dm.ref("ev_ccc") == "E3"

    def test_same_raw_id_maps_to_same_enumber(self) -> None:
        findings = [
            _make_finding(["ev_aaa"]),
            _make_finding(["ev_aaa", "ev_bbb"]),
        ]
        dm = EvidenceDisplayMap.from_findings(findings)
        assert dm.ref("ev_aaa") == "E1"
        # Same ID in second finding still maps to E1
        assert dm.ref("ev_aaa") == "E1"
        assert dm.ref("ev_bbb") == "E2"

    def test_unknown_id_passthrough(self) -> None:
        dm = EvidenceDisplayMap.from_evidence_ids(["ev_aaa"])
        assert dm.ref("ev_unknown") == "ev_unknown"

    def test_ref_bracket_format(self) -> None:
        dm = EvidenceDisplayMap.from_evidence_ids(["ev_aaa", "ev_bbb"])
        assert dm.ref_bracket("ev_aaa") == "[E1]"
        assert dm.ref_bracket("ev_bbb") == "[E2]"

    def test_replace_in_text(self) -> None:
        dm = EvidenceDisplayMap.from_evidence_ids(
            ["ev_0123456789abcdef0123", "ev_fedcba9876543210fedc"]
        )
        text = "See ev_0123456789abcdef0123 and ev_fedcba9876543210fedc for details."
        result = dm.replace_in_text(text)
        assert "[E1]" in result
        assert "[E2]" in result
        assert "ev_0123456789abcdef0123" not in result
        assert "ev_fedcba9876543210fedc" not in result

    def test_replace_preserves_non_evidence_text(self) -> None:
        dm = EvidenceDisplayMap.from_evidence_ids(["ev_0123456789abcdef0123"])
        text = "The function `evolve` is not an evidence ID."
        result = dm.replace_in_text(text)
        assert "evolve" in result

    def test_from_evidence_ids_preserves_order(self) -> None:
        dm = EvidenceDisplayMap.from_evidence_ids(
            ["ev_ccc", "ev_aaa", "ev_bbb", "ev_aaa"]
        )
        assert dm.ref("ev_ccc") == "E1"
        assert dm.ref("ev_aaa") == "E2"
        assert dm.ref("ev_bbb") == "E3"

    def test_len(self) -> None:
        dm = EvidenceDisplayMap.from_evidence_ids(["ev_aaa", "ev_bbb"])
        assert len(dm) == 2


class TestFormatEvidenceRef:
    def test_empty_ids(self) -> None:
        dm = EvidenceDisplayMap.from_evidence_ids([])
        assert format_evidence_ref(dm, []) == ""

    def test_single_id(self) -> None:
        dm = EvidenceDisplayMap.from_evidence_ids(["ev_aaa"])
        assert format_evidence_ref(dm, ["ev_aaa"]) == "[E1]"

    def test_multiple_ids(self) -> None:
        dm = EvidenceDisplayMap.from_evidence_ids(["ev_aaa", "ev_bbb", "ev_ccc"])
        assert format_evidence_ref(dm, ["ev_aaa", "ev_ccc"]) == "[E1] [E3]"


class TestEvidenceAppendix:
    def test_appendix_en_labels(self) -> None:
        findings = [_make_finding(["ev_aaa"])]
        records = [_make_record("ev_aaa")]
        dm = EvidenceDisplayMap.from_findings(findings)
        result = build_evidence_appendix(findings, records, dm, lang="en")
        assert "# Evidence Appendix" in result
        assert "## E1 · src/app.py:10-20" in result
        assert "Type" in result

    def test_appendix_zh_labels(self) -> None:
        findings = [_make_finding(["ev_aaa"])]
        records = [_make_record("ev_aaa")]
        dm = EvidenceDisplayMap.from_findings(findings)
        result = build_evidence_appendix(findings, records, dm, lang="zh")
        assert "# 证据附录" in result
        assert "## E1 · src/app.py:10-20" in result
        assert "类型" in result

    def test_appendix_contains_symbol(self) -> None:
        findings = [_make_finding(["ev_aaa"])]
        records = [_make_record("ev_aaa", symbols=["send_static_file"])]
        dm = EvidenceDisplayMap.from_findings(findings)
        result = build_evidence_appendix(findings, records, dm, lang="en")
        assert "send_static_file" in result

    def test_appendix_contains_snippet(self) -> None:
        findings = [_make_finding(["ev_aaa"])]
        records = [_make_record("ev_aaa", snippet="def foo():\n    return 42")]
        dm = EvidenceDisplayMap.from_findings(findings)
        result = build_evidence_appendix(findings, records, dm, lang="en")
        assert "def foo():" in result
        assert "return 42" in result

    def test_appendix_truncates_long_snippet(self) -> None:
        long_snippet = "\n".join(f"line {i}" for i in range(50))
        findings = [_make_finding(["ev_aaa"])]
        records = [_make_record("ev_aaa", snippet=long_snippet)]
        dm = EvidenceDisplayMap.from_findings(findings)
        result = build_evidence_appendix(findings, records, dm, lang="en")
        # Should be truncated to MAX_SNIPPET_LINES (20) + "..."
        assert "line 19" in result
        assert "line 20" not in result or "..." in result

    def test_appendix_missing_evidence_detail(self) -> None:
        """Missing evidence record should not crash export."""
        findings = [_make_finding(["ev_aaa"])]
        records: list[EvidenceRecord] = []  # No records
        dm = EvidenceDisplayMap.from_findings(findings)
        result = build_evidence_appendix(findings, records, dm, lang="en")
        assert "## E1 ·" in result
        assert "unknown" in result

    def test_appendix_max_entries(self) -> None:
        """More than 30 evidence items should be truncated."""
        evidence_ids = [f"ev_{i:020x}" for i in range(35)]
        findings = [_make_finding(evidence_ids)]
        records = [_make_record(eid) for eid in evidence_ids]
        dm = EvidenceDisplayMap.from_findings(findings)
        result = build_evidence_appendix(findings, records, dm, lang="en", max_entries=30)
        assert "## E30 ·" in result
        assert "## E31 ·" not in result
        assert "omitted" in result.lower() or "省略" in result

    def test_appendix_related_findings(self) -> None:
        findings = [
            _make_finding(["ev_aaa"], title="Duplicate method"),
        ]
        records = [_make_record("ev_aaa")]
        dm = EvidenceDisplayMap.from_findings(findings)
        result = build_evidence_appendix(findings, records, dm, lang="en")
        assert "Duplicate method" in result


class TestReportComposerEvidenceDisplay:
    def test_no_raw_ev_ids_in_report(self, sample_context) -> None:
        """Raw ev_* IDs should not appear in the composed report."""
        context = sample_context.to_review_context()
        evidence_id = "ev_0123456789abcdef0123"
        context.evidence = [
            _make_record(evidence_id, snippet="def foo(): pass", symbols=["foo"])
        ]
        draft = StructuredReviewDraft(
            findings=[_make_finding([evidence_id])]
        )
        report = HumanReadableReportComposer().compose(context, draft)
        assert evidence_id not in report
        assert "[E1]" in report

    def test_evidence_appendix_in_report(self, sample_context) -> None:
        context = sample_context.to_review_context()
        evidence_id = "ev_0123456789abcdef0123"
        context.evidence = [
            _make_record(evidence_id, snippet="def foo(): pass", symbols=["foo"])
        ]
        draft = StructuredReviewDraft(
            findings=[_make_finding([evidence_id])]
        )
        report = HumanReadableReportComposer().compose(context, draft)
        assert "# Evidence Appendix" in report
        assert "## E1 ·" in report

    def test_action_plan_uses_display_refs(self, sample_context) -> None:
        context = sample_context.to_review_context()
        evidence_id = "ev_0123456789abcdef0123"
        context.evidence = [
            _make_record(evidence_id, snippet="def foo(): pass", symbols=["foo"])
        ]
        draft = StructuredReviewDraft(
            findings=[_make_finding([evidence_id])]
        )
        report = HumanReadableReportComposer().compose(context, draft)
        action_section = report.split("# Action Plan")[1].split("# Evidence Appendix")[0]
        assert "[E1]" in action_section
        assert evidence_id not in action_section

    def test_agent_findings_use_display_refs(self, sample_context) -> None:
        from backend.models.review_state import AgentExecutionState

        context = sample_context.to_review_context()
        evidence_id = "ev_0123456789abcdef0123"
        context.evidence = [
            _make_record(evidence_id, snippet="def foo(): pass", symbols=["foo"])
        ]
        finding = _make_finding([evidence_id])
        draft = StructuredReviewDraft(findings=[finding])
        agent_states = [
            AgentExecutionState(
                agent_id="TestAgent",
                status="completed",
                findings=[finding],
                evidence_ids=[evidence_id],
            )
        ]
        report = HumanReadableReportComposer().compose(context, draft, agent_states)
        agent_section = report.split("# Agent Findings")[1].split("# Action Plan")[0]
        assert "[E1]" in agent_section
        assert evidence_id not in agent_section

    def test_zh_export_uses_zh_labels(self, sample_context) -> None:
        context = sample_context.to_review_context()
        evidence_id = "ev_0123456789abcdef0123"
        context.evidence = [
            _make_record(evidence_id, snippet="def foo(): pass", symbols=["foo"])
        ]
        draft = StructuredReviewDraft(
            findings=[_make_finding([evidence_id])]
        )
        report = HumanReadableReportComposer().compose(context, draft, lang="zh")
        assert "# 证据附录" in report
        assert evidence_id not in report


class TestFindingMarkdownDisplay:
    def test_to_markdown_uses_display_refs(self) -> None:
        dm = EvidenceDisplayMap.from_evidence_ids(
            ["ev_0123456789abcdef0123", "ev_fedcba9876543210fedc"]
        )
        finding = _make_finding(["ev_0123456789abcdef0123", "ev_fedcba9876543210fedc"])
        md = finding.to_markdown(dm)
        assert "[E1]" in md
        assert "[E2]" in md
        assert "ev_0123456789abcdef0123" not in md
        assert "ev_fedcba9876543210fedc" not in md

    def test_to_zh_markdown_uses_display_refs(self) -> None:
        dm = EvidenceDisplayMap.from_evidence_ids(["ev_0123456789abcdef0123"])
        finding = _make_finding(["ev_0123456789abcdef0123"])
        md = finding.to_localized_markdown("zh", dm)
        assert "[E1]" in md
        assert "ev_0123456789abcdef0123" not in md
        assert "证据引用" in md

    def test_to_markdown_without_display_map_preserves_raw_ids(self) -> None:
        """Backward compatibility: no display_map = raw IDs preserved."""
        finding = _make_finding(["ev_abc123"])
        md = finding.to_markdown()
        assert "ev_abc123" in md

    def test_backward_compat_no_evidence(self) -> None:
        """Finding with no evidence_ids should work fine."""
        dm = EvidenceDisplayMap.from_findings([])
        finding = _make_finding([])
        md = finding.to_markdown(dm)
        assert "Evidence:" not in md
