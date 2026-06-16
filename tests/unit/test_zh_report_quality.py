"""Tests for Chinese report quality improvements (V3.5.9 Step 5)."""

from __future__ import annotations

from backend.models.structured_review import (
    BilingualTextField,
    DisplayFields,
    ReviewFinding,
)
from backend.reviewers.localization import (
    CHINESE_TO_ENGLISH_HEADINGS,
    LABEL_TRANSLATIONS,
    REPORT_HEADING_TRANSLATIONS,
)
from backend.reviewers.localized_report_renderer import (
    render_localized_report,
    render_localized_report_with_prose,
)


class TestPrioritySectionInZhReport:
    """Test that zh reports include the 优先处理建议 section."""

    def _make_finding(self, **kwargs) -> ReviewFinding:
        defaults = {
            "section": "Code Smells",
            "title": "Test finding",
            "description": "A test finding.",
            "severity": "high",
            "confidence": 0.85,
            "files": ["src/app.py"],
            "evidence_ids": ["ev_001"],
            "impact": "May cause issues.",
            "first_step": "Add tests.",
        }
        defaults.update(kwargs)
        return ReviewFinding(**defaults)

    def test_zh_report_includes_priority_heading(self) -> None:
        report = "# Executive Summary\nContent.\n"
        findings = [self._make_finding()]
        result = render_localized_report(report, "zh", findings=findings)
        assert "# 优先处理建议" in result

    def test_zh_report_groups_into_p1(self) -> None:
        report = "# Executive Summary\nContent.\n"
        findings = [self._make_finding(severity="high", confidence=0.9)]
        result = render_localized_report(report, "zh", findings=findings)
        assert "## P1：建议优先处理" in result

    def test_zh_report_groups_into_p2(self) -> None:
        report = "# Executive Summary\nContent.\n"
        findings = [self._make_finding(severity="medium", confidence=0.6)]
        result = render_localized_report(report, "zh", findings=findings)
        assert "## P2：建议排期优化" in result

    def test_zh_report_groups_into_p3(self) -> None:
        report = "# Executive Summary\nContent.\n"
        findings = [self._make_finding(severity="low", confidence=0.3)]
        result = render_localized_report(report, "zh", findings=findings)
        assert "## P3：低风险改进" in result

    def test_no_p1_shows_message(self) -> None:
        report = "# Executive Summary\nContent.\n"
        findings = [self._make_finding(severity="low", confidence=0.3)]
        result = render_localized_report(report, "zh", findings=findings)
        assert "本次未发现需要立即处理的 P1 问题" in result

    def test_en_report_no_priority_section(self) -> None:
        report = "# Executive Summary\nContent.\n"
        findings = [self._make_finding()]
        result = render_localized_report(report, "en", findings=findings)
        assert "优先处理建议" not in result

    def test_priority_section_after_executive_summary(self) -> None:
        report = "# Executive Summary\nContent.\n# What This Repository Is\nInfo.\n"
        findings = [self._make_finding()]
        result = render_localized_report(report, "zh", findings=findings)
        exec_pos = result.index("执行摘要")
        priority_pos = result.index("优先处理建议")
        identity_pos = result.index("仓库概览")
        assert exec_pos < priority_pos < identity_pos


class TestBannedEnglishLabelsInZh:
    """Test that zh reports do not contain banned English labels."""

    BANNED_LABELS = [
        "Recommendation:",
        "Impact:",
        "First step:",
        "Validation tests:",
        "Category:",
        "Grounding:",
    ]

    def test_structured_review_zh_markdown_no_banned_labels(self) -> None:
        """to_localized_markdown with lang='zh' should use Chinese labels."""
        finding = ReviewFinding(
            section="Code Smells",
            title="Test issue",
            description="A test issue.",
            severity="high",
            confidence=0.85,
            files=["src/app.py"],
            evidence_ids=["ev_001"],
            recommendation="Fix this.",
            impact="Affects stability.",
            first_step="Add tests.",
            validation_tests=["pytest tests/"],
            caveat="Public API.",
            evidence=["ev_001 -> src/app.py:10-20"],
            display=DisplayFields(
                en=BilingualTextField(
                    title="Test issue",
                    description="A test issue.",
                    recommendation="Fix this.",
                    impact="Affects stability.",
                    first_step="Add tests.",
                    caveat="Public API.",
                ),
                zh=BilingualTextField(
                    title="测试问题",
                    description="一个测试问题。",
                    recommendation="修复此问题。",
                    impact="影响稳定性。",
                    first_step="先添加测试。",
                    caveat="公共 API。",
                ),
            ),
        )
        result = finding.to_localized_markdown("zh")
        for banned in self.BANNED_LABELS:
            assert banned not in result, f"Banned label '{banned}' found in zh markdown"

    def test_structured_review_zh_uses_chinese_labels(self) -> None:
        """to_localized_markdown with lang='zh' should use proper Chinese labels."""
        finding = ReviewFinding(
            section="Code Smells",
            title="测试问题",
            description="一个测试问题。",
            severity="high",
            confidence=0.85,
            files=["src/app.py"],
            evidence_ids=["ev_001"],
            recommendation="修复此问题。",
            impact="影响稳定性。",
            first_step="先添加测试。",
            validation_tests=["pytest tests/"],
            caveat="公共 API。",
            evidence=["ev_001 -> src/app.py:10-20"],
        )
        result = finding.to_localized_markdown("zh")
        assert "问题类型：" in result
        assert "置信度：" in result
        assert "涉及文件：" in result
        assert "证据引用：" in result
        assert "建议：" in result
        assert "影响：" in result
        assert "建议先做：" in result
        assert "验证方式：" in result
        assert "注意事项：" in result
        assert "证据说明：" in result

    def test_structured_review_en_unchanged(self) -> None:
        """to_localized_markdown with lang='en' should keep English labels."""
        finding = ReviewFinding(
            section="Code Smells",
            title="Test issue",
            description="A test issue.",
            severity="high",
            confidence=0.85,
            files=["src/app.py"],
            evidence_ids=["ev_001"],
            recommendation="Fix this.",
        )
        result = finding.to_localized_markdown("en")
        assert "Category:" in result
        assert "Files:" in result
        assert "Evidence:" in result
        assert "Recommendation:" in result


class TestDefaultSectionContentTranslated:
    """Test that DEFAULT_SECTION_CONTENT is translated in zh mode."""

    def test_default_content_translated_in_zh(self) -> None:
        report = "# Code Smells\nNo critical findings detected from the available repository summaries.\n"
        result = render_localized_report(report, "zh")
        assert "暂未从可用的仓库摘要中检测到明确的问题" in result
        assert "No critical findings detected" not in result

    def test_default_content_unchanged_in_en(self) -> None:
        report = "# Code Smells\nNo critical findings detected from the available repository summaries.\n"
        result = render_localized_report(report, "en")
        assert "No critical findings detected" in result


class TestChineseLabelTranslations:
    """Test that all required Chinese label translations exist."""

    def test_why_it_matters_translated(self) -> None:
        assert "**为什么重要：**" in LABEL_TRANSLATIONS.values()

    def test_suggest_first_action_translated(self) -> None:
        assert "**建议先做：**" in LABEL_TRANSLATIONS.values()

    def test_validation_method_translated(self) -> None:
        assert "**验证方式：**" in LABEL_TRANSLATIONS.values()

    def test_evidence_citation_translated(self) -> None:
        assert "**证据引用：**" in LABEL_TRANSLATIONS.values()

    def test_issue_type_translated(self) -> None:
        assert "**问题类型：**" in LABEL_TRANSLATIONS.values()

    def test_evidence_explanation_translated(self) -> None:
        assert "**证据说明：**" in LABEL_TRANSLATIONS.values()

    def test_involved_files_translated(self) -> None:
        assert "**涉及文件：**" in LABEL_TRANSLATIONS.values()

    def test_responsibility_scope_translated(self) -> None:
        assert "**责任范围：**" in LABEL_TRANSLATIONS.values()


class TestPriorityHeadingInTranslations:
    """Test that the priority heading is in the translation maps."""

    def test_priority_recommendations_heading(self) -> None:
        assert "Priority Recommendations" in REPORT_HEADING_TRANSLATIONS
        assert REPORT_HEADING_TRANSLATIONS["Priority Recommendations"] == "优先处理建议"

    def test_priority_heading_has_reverse(self) -> None:
        assert "优先处理建议" in CHINESE_TO_ENGLISH_HEADINGS
        assert CHINESE_TO_ENGLISH_HEADINGS["优先处理建议"] == "Priority Recommendations"


class TestEmptyAgentWording:
    """Test that empty agent states produce natural Chinese wording."""

    def test_no_findings_wording_in_zh_prose(self) -> None:
        """The prose replacements should include natural Chinese empty-agent wording."""
        from backend.reviewers.localization import PROSE_REPLACEMENTS

        assert "No validated findings." in PROSE_REPLACEMENTS
        assert PROSE_REPLACEMENTS["No validated findings."] == "暂未发现明确的问题。"

    def test_no_validated_finding_produced(self) -> None:
        from backend.reviewers.localization import PROSE_REPLACEMENTS

        assert "No validated finding was produced." in PROSE_REPLACEMENTS
        assert "暂未产出需要单独列出的问题发现" in PROSE_REPLACEMENTS["No validated finding was produced."]


class TestEvidenceExplanationInZh:
    """Test that evidence explanation sections exist in zh findings."""

    def test_evidence_explanation_label_in_translations(self) -> None:
        """Evidence explanation should use 证据说明 label."""
        assert "**Grounding:**" in LABEL_TRANSLATIONS
        assert LABEL_TRANSLATIONS["**Grounding:**"] == "**证据说明：**"

    def test_zh_markdown_includes_evidence_explanation(self) -> None:
        finding = ReviewFinding(
            section="Code Smells",
            title="Test",
            description="Desc.",
            severity="medium",
            confidence=0.7,
            evidence=["ev_001 -> src/app.py:10-20"],
        )
        result = finding.to_localized_markdown("zh")
        assert "证据说明：" in result
        assert "ev_001 -> src/app.py:10-20" in result


class TestActionPlanLabelsInZh:
    """Test that action plan uses Chinese-native labels."""

    def test_action_plan_labels_in_prose_replacements(self) -> None:
        from backend.reviewers.localization import PROSE_REPLACEMENTS

        # These are the new Chinese-native action plan labels
        assert "No evidence-grounded action is recommended yet." in PROSE_REPLACEMENTS

    def test_change_risk_translated(self) -> None:
        from backend.reviewers.localization import PROSE_REPLACEMENTS

        key = "Higher structural risk because at least one cited file participates in a dependency cycle."
        zh_value = PROSE_REPLACEMENTS[key]
        assert "结构性风险较高" in zh_value


class TestBilingualReportWithProse:
    """Test render_localized_report_with_prose with priority section."""

    def test_prose_render_includes_priority(self) -> None:
        report = "# Executive Summary\nContent.\n# Action Plan\n- Finding.\n"
        localized_findings = [
            {
                "title": "Test",
                "title_zh": "测试",
                "description": "Desc.",
                "description_zh": "描述。",
                "severity": "high",
                "confidence": 0.8,
            },
        ]
        findings = [
            ReviewFinding(
                section="Code Smells",
                title="Test",
                description="Desc.",
                severity="high",
                confidence=0.8,
                files=["src/app.py"],
                evidence_ids=["ev_001"],
            ),
        ]
        result = render_localized_report_with_prose(
            report, localized_findings, "zh", findings=findings,
        )
        assert "优先处理建议" in result

    def test_prose_render_no_findings_no_priority(self) -> None:
        report = "# Executive Summary\nContent.\n"
        result = render_localized_report_with_prose(report, [], "zh")
        assert "优先处理建议" not in result
