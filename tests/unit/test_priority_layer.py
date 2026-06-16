"""Tests for the deterministic priority layer."""

from __future__ import annotations

from backend.models.structured_review import ReviewFinding
from backend.reviewers.priority_layer import (
    assign_priority,
    generate_priority_section,
)


class TestAssignPriority:
    def test_high_confidence_high_severity_is_p1(self) -> None:
        finding = ReviewFinding(
            section="Code Smells",
            title="Test",
            description="Test",
            severity="high",
            confidence=0.85,
            files=["src/app.py"],
            evidence_ids=["ev_001"],
        )
        assert assign_priority(finding) == "P1"

    def test_critical_severity_high_confidence_is_p1(self) -> None:
        finding = ReviewFinding(
            section="Architecture Summary",
            title="Test",
            description="Test",
            severity="critical",
            confidence=0.9,
        )
        assert assign_priority(finding) == "P1"

    def test_high_severity_low_confidence_is_p2(self) -> None:
        finding = ReviewFinding(
            section="Code Smells",
            title="Test",
            description="Test",
            severity="high",
            confidence=0.5,
        )
        assert assign_priority(finding) == "P2"

    def test_medium_severity_is_p2(self) -> None:
        finding = ReviewFinding(
            section="Code Smells",
            title="Test",
            description="Test",
            severity="medium",
            confidence=0.7,
        )
        assert assign_priority(finding) == "P2"

    def test_low_severity_is_p3(self) -> None:
        finding = ReviewFinding(
            section="Refactoring Suggestions",
            title="Test",
            description="Test",
            severity="low",
            confidence=0.5,
        )
        assert assign_priority(finding) == "P3"

    def test_informational_is_p3(self) -> None:
        finding = ReviewFinding(
            section="Maintainability Issues",
            title="Test",
            description="Test",
            severity="informational",
            confidence=0.3,
        )
        assert assign_priority(finding) == "P3"


class TestGeneratePrioritySection:
    def test_empty_findings_returns_empty(self) -> None:
        assert generate_priority_section([]) == ""

    def test_section_includes_heading(self) -> None:
        findings = [
            ReviewFinding(
                section="Code Smells",
                title="Test finding",
                description="A test.",
                severity="medium",
                confidence=0.6,
            ),
        ]
        result = generate_priority_section(findings)
        assert "# 优先处理建议" in result

    def test_p1_findings_grouped_correctly(self) -> None:
        findings = [
            ReviewFinding(
                section="Code Smells",
                title="Critical issue",
                description="A critical issue.",
                severity="high",
                confidence=0.9,
                files=["src/main.py"],
                evidence_ids=["ev_001"],
                impact="May cause data loss.",
                recommendation="Fix immediately.",
            ),
        ]
        result = generate_priority_section(findings)
        assert "## P1：建议优先处理" in result
        assert "**Critical issue**" in result
        assert "为什么重要：" in result
        assert "建议先做：" in result
        assert "涉及文件：" in result
        assert "证据引用：" in result

    def test_no_p1_shows_message(self) -> None:
        findings = [
            ReviewFinding(
                section="Refactoring Suggestions",
                title="Low priority",
                description="A low priority item.",
                severity="low",
                confidence=0.3,
            ),
        ]
        result = generate_priority_section(findings)
        assert "本次未发现需要立即处理的 P1 问题" in result

    def test_p2_grouped_correctly(self) -> None:
        findings = [
            ReviewFinding(
                section="Code Smells",
                title="Medium issue",
                description="A medium issue.",
                severity="medium",
                confidence=0.6,
            ),
        ]
        result = generate_priority_section(findings)
        assert "## P2：建议排期优化" in result

    def test_p3_grouped_correctly(self) -> None:
        findings = [
            ReviewFinding(
                section="Refactoring Suggestions",
                title="Low issue",
                description="A low issue.",
                severity="low",
                confidence=0.3,
            ),
        ]
        result = generate_priority_section(findings)
        assert "## P3：低风险改进" in result

    def test_uses_impact_as_why_important(self) -> None:
        findings = [
            ReviewFinding(
                section="Code Smells",
                title="Test",
                description="Desc.",
                severity="high",
                confidence=0.8,
                impact="This affects performance significantly.",
            ),
        ]
        result = generate_priority_section(findings)
        assert "This affects performance significantly." in result

    def test_falls_back_to_description_when_no_impact(self) -> None:
        findings = [
            ReviewFinding(
                section="Code Smells",
                title="Test",
                description="This is the description.",
                severity="high",
                confidence=0.8,
            ),
        ]
        result = generate_priority_section(findings)
        assert "This is the description." in result

    def test_uses_first_step_as_suggested_action(self) -> None:
        findings = [
            ReviewFinding(
                section="Code Smells",
                title="Test",
                description="Desc.",
                severity="high",
                confidence=0.8,
                first_step="Add unit tests first.",
            ),
        ]
        result = generate_priority_section(findings)
        assert "Add unit tests first." in result

    def test_no_banned_english_labels(self) -> None:
        """Priority section should not contain banned English labels."""
        findings = [
            ReviewFinding(
                section="Code Smells",
                title="Test finding",
                description="A test.",
                severity="high",
                confidence=0.8,
                impact="Impact text.",
                first_step="Do this first.",
            ),
        ]
        result = generate_priority_section(findings)
        banned = ["Recommendation:", "Impact:", "First step:", "Validation tests:",
                   "Category:", "Grounding:"]
        for term in banned:
            assert term not in result, f"Banned term '{term}' found in priority section"

    def test_evidence_ids_preserved(self) -> None:
        findings = [
            ReviewFinding(
                section="Code Smells",
                title="Test",
                description="Desc.",
                severity="high",
                confidence=0.8,
                evidence_ids=["ev_abc123", "ev_def456"],
            ),
        ]
        result = generate_priority_section(findings)
        assert "ev_abc123" in result
        assert "ev_def456" in result

    def test_file_paths_preserved(self) -> None:
        findings = [
            ReviewFinding(
                section="Code Smells",
                title="Test",
                description="Desc.",
                severity="high",
                confidence=0.8,
                files=["backend/api/reviews.py"],
            ),
        ]
        result = generate_priority_section(findings)
        assert "backend/api/reviews.py" in result

    def test_limits_p1_to_5_items(self) -> None:
        findings = [
            ReviewFinding(
                section="Code Smells",
                title=f"Finding {i}",
                description=f"Desc {i}.",
                severity="high",
                confidence=0.9,
            )
            for i in range(8)
        ]
        result = generate_priority_section(findings)
        # Count P1 items (lines starting with "* **")
        p1_section = result.split("## P2")[0] if "## P2" in result else result
        p1_items = [line for line in p1_section.split("\n") if line.strip().startswith("* **")]
        assert len(p1_items) <= 5
