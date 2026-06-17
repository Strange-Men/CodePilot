"""Tests for centralized Chinese presentation pipeline (V3.7).

Regression tests using current bad V3.6 examples to verify that
English leakage in display.zh fields is detected and repaired before
rendering, and that metadata patterns are cleaned up post-render.
"""

from __future__ import annotations

from backend.models.structured_review import (
    BilingualTextField,
    DisplayFields,
    ReviewFinding,
)
from backend.reviewers.localized_report_renderer import render_localized_report
from backend.reviewers.zh_presentation import (
    _CAVEAT_TEMPLATES,
    _CONFIDENCE_RATIONALE_TEMPLATE,
    _DESCRIPTION_TEMPLATE,
    _FIRST_STEP_TEMPLATES,
    _GENERIC_CAVEAT,
    _GENERIC_FIRST_STEP,
    _GENERIC_IMPACT,
    _GENERIC_RECOMMENDATION,
    _IMPACT_TEMPLATES,
    _RECOMMENDATION_TEMPLATES,
    _TITLE_TEMPLATES,
    _VALIDATION_TEST_REPLACEMENT,
    finalize_zh_report,
    is_english_leakage,
    prepare_zh_report,
    repair_zh_display_fields,
    repair_zh_field,
    repair_zh_findings,
    repair_zh_metadata,
    repair_zh_validation_tests,
    validate_zh_fields,
)

# ---------------------------------------------------------------------------
# Fixtures — V3.6 bad examples that must be fixed in V3.7
# ---------------------------------------------------------------------------

# display.zh fields with English leakage (from V3.6 reports)
V36_ENGLISH_IMPACT = "Increases maintenance burden and raises the risk of regressions during future changes."
V36_ENGLISH_RECOMMENDATION = "Review if the duplication is intentional for backward compatibility."
V36_ENGLISH_FIRST_STEP = "Extract common logic to reduce duplication and improve maintainability."
V36_ENGLISH_CAVEAT = "This boundary is part of a public API; changing it may break downstream consumers."
V36_ENGLISH_TITLE = "Evidence-grounded code smell"
V36_ENGLISH_DESCRIPTION = "The selected evidence highlights a repository concern that should be reviewed."
V36_ENGLISH_CONFIDENCE = "Based on evidence records provided in the prompt context."
V36_ENGLISH_VALIDATION = "Run the full test suite before and after any boundary change."

# Metadata patterns from V3.6 reports
V36_METADATA_ENGLISH = """## E1 · src/flask/app.py:392-412

* Type：source
* Symbol：send_static_file
* Related findings：重复的错误处理模式
* Description：This evidence was derived from parsed code symbols or structured repository context.

# 仓库指标

- 源文件总数：83
- 已分析文件：83
"""

V36_REPO_SUMMARY = "Python 仓库 with 83 Python files。Supporting modules。Dependency structure。"
V36_EVIDENCE_HIGHLIGHTS = "The selected evidence highlights a repository concern."


# ---------------------------------------------------------------------------
# Fixtures — clean Chinese fields (should NOT be repaired)
# ---------------------------------------------------------------------------

CLEAN_ZH_IMPACT = "该问题会增加维护成本，并提高后续修改遗漏或引入回归的风险。"
CLEAN_ZH_RECOMMENDATION = "先确认该逻辑是否确实重复；如果重复，应在保持公共 API 兼容的前提下提取公共实现。"
CLEAN_ZH_FIRST_STEP = "先为当前行为补充针对性测试，再进行小步重构。"
CLEAN_ZH_CAVEAT = "如果该逻辑属于公共 API，变更前需要确认兼容性影响。"
CLEAN_ZH_TITLE = "send_static_file 的代码质量需要关注"
CLEAN_ZH_DESCRIPTION = "该函数存在重复的错误处理模式，建议提取公共实现。"


# ---------------------------------------------------------------------------
# Fixtures — allowed English (should NOT be flagged)
# ---------------------------------------------------------------------------

ALLOWED_TECH = "API URL JSON HTTP CLI UI DB SQL MiMo OpenAI Flask FastAPI"
ALLOWED_PATH = "src/flask/app.py"
ALLOWED_SYMBOL = "send_static_file"
ALLOWED_COMMAND = "pytest tests/test_cli.py"
ALLOWED_EVIDENCE_REF = "[E1] [E2]"


# ---------------------------------------------------------------------------
# Tests: is_english_leakage
# ---------------------------------------------------------------------------


class TestIsEnglishLeakage:
    """Test English leakage detection in zh fields."""

    def test_english_sentence_detected(self):
        assert is_english_leakage(V36_ENGLISH_IMPACT) is True

    def test_english_recommendation_detected(self):
        assert is_english_leakage(V36_ENGLISH_RECOMMENDATION) is True

    def test_english_first_step_detected(self):
        assert is_english_leakage(V36_ENGLISH_FIRST_STEP) is True

    def test_english_caveat_detected(self):
        assert is_english_leakage(V36_ENGLISH_CAVEAT) is True

    def test_english_title_detected(self):
        assert is_english_leakage(V36_ENGLISH_TITLE) is True

    def test_english_description_detected(self):
        assert is_english_leakage(V36_ENGLISH_DESCRIPTION) is True

    def test_english_confidence_detected(self):
        assert is_english_leakage(V36_ENGLISH_CONFIDENCE) is True

    def test_english_validation_detected(self):
        assert is_english_leakage(V36_ENGLISH_VALIDATION) is True

    def test_chinese_text_not_detected(self):
        assert is_english_leakage(CLEAN_ZH_IMPACT) is False
        assert is_english_leakage(CLEAN_ZH_RECOMMENDATION) is False
        assert is_english_leakage(CLEAN_ZH_FIRST_STEP) is False
        assert is_english_leakage(CLEAN_ZH_CAVEAT) is False

    def test_tech_names_not_detected(self):
        assert is_english_leakage("Flask") is False
        assert is_english_leakage("FastAPI") is False
        assert is_english_leakage("API") is False
        assert is_english_leakage("MiMo") is False
        assert is_english_leakage("OpenAI") is False

    def test_code_symbols_not_detected(self):
        assert is_english_leakage("send_static_file") is False
        assert is_english_leakage("OpenAICompatibleClient") is False
        assert is_english_leakage("MAX_ENTRIES") is False

    def test_file_paths_not_detected(self):
        assert is_english_leakage("src/flask/app.py") is False
        assert is_english_leakage("backend/api/reviews.py") is False

    def test_commands_not_detected(self):
        assert is_english_leakage("pytest tests/test_cli.py") is False
        assert is_english_leakage("npm run build") is False

    def test_evidence_refs_not_detected(self):
        assert is_english_leakage("[E1]") is False
        assert is_english_leakage("[E2]") is False

    def test_none_not_detected(self):
        assert is_english_leakage(None) is False

    def test_empty_not_detected(self):
        assert is_english_leakage("") is False
        assert is_english_leakage("  ") is False

    def test_single_severity_word_not_detected(self):
        """Single severity words are handled by normalize_zh_markdown fallback,
        not by is_english_leakage (they're not in _COMMON_ENGLISH_WORDS)."""
        assert is_english_leakage("high") is False
        assert is_english_leakage("medium") is False
        assert is_english_leakage("low") is False

    def test_single_tech_word_not_detected(self):
        """Single tech name should not be detected."""
        assert is_english_leakage("Flask") is False
        assert is_english_leakage("SQLite") is False


# ---------------------------------------------------------------------------
# Tests: repair_zh_field
# ---------------------------------------------------------------------------


class TestRepairZhField:
    """Test individual field repair."""

    def test_english_impact_repaired(self):
        result = repair_zh_field(V36_ENGLISH_IMPACT, "impact", "code_smell")
        assert result == _IMPACT_TEMPLATES["code_smell"]
        assert "Increases maintenance" not in result

    def test_english_recommendation_repaired(self):
        result = repair_zh_field(V36_ENGLISH_RECOMMENDATION, "recommendation", "code_smell")
        assert result == _RECOMMENDATION_TEMPLATES["code_smell"]
        assert "Review if" not in result

    def test_english_first_step_repaired(self):
        result = repair_zh_field(V36_ENGLISH_FIRST_STEP, "first_step", "refactor")
        assert result == _FIRST_STEP_TEMPLATES["refactor"]
        assert "Extract common" not in result

    def test_english_caveat_repaired_public_api(self):
        result = repair_zh_field(V36_ENGLISH_CAVEAT, "caveat", "")
        assert result == _CAVEAT_TEMPLATES["public_api"]
        assert "public API" not in result

    def test_english_caveat_repaired_generic(self):
        result = repair_zh_field("This finding is based on structural signals.", "caveat", "")
        assert result == _GENERIC_CAVEAT

    def test_english_confidence_repaired(self):
        result = repair_zh_field(V36_ENGLISH_CONFIDENCE, "confidence_rationale", "")
        assert result == _CONFIDENCE_RATIONALE_TEMPLATE

    def test_english_title_repaired(self):
        result = repair_zh_field(V36_ENGLISH_TITLE, "title", "code_smell")
        assert result == _TITLE_TEMPLATES["code_smell"]

    def test_english_description_repaired(self):
        result = repair_zh_field(V36_ENGLISH_DESCRIPTION, "description", "")
        assert result == _DESCRIPTION_TEMPLATE

    def test_chinese_text_preserved(self):
        """Chinese fields should NOT be repaired."""
        assert repair_zh_field(CLEAN_ZH_IMPACT, "impact", "code_smell") == CLEAN_ZH_IMPACT
        assert repair_zh_field(CLEAN_ZH_RECOMMENDATION, "recommendation", "code_smell") == CLEAN_ZH_RECOMMENDATION
        assert repair_zh_field(CLEAN_ZH_FIRST_STEP, "first_step", "refactor") == CLEAN_ZH_FIRST_STEP
        assert repair_zh_field(CLEAN_ZH_CAVEAT, "caveat", "") == CLEAN_ZH_CAVEAT

    def test_none_returns_none(self):
        assert repair_zh_field(None, "impact", "code_smell") is None

    def test_tech_names_preserved(self):
        """Tech names should NOT be repaired."""
        assert repair_zh_field("Flask", "title", "code_smell") == "Flask"
        assert repair_zh_field("API", "impact", "") == "API"

    def test_code_symbols_preserved(self):
        """Code symbols should NOT be repaired."""
        assert repair_zh_field("send_static_file", "title", "code_smell") == "send_static_file"

    def test_different_categories_get_different_templates(self):
        """Different categories should get different templates."""
        impact_smell = repair_zh_field(V36_ENGLISH_IMPACT, "impact", "code_smell")
        impact_arch = repair_zh_field(V36_ENGLISH_IMPACT, "impact", "architecture")
        impact_refactor = repair_zh_field(V36_ENGLISH_IMPACT, "impact", "refactor")
        impact_maintain = repair_zh_field(V36_ENGLISH_IMPACT, "impact", "maintainability")

        assert impact_smell == _IMPACT_TEMPLATES["code_smell"]
        assert impact_arch == _IMPACT_TEMPLATES["architecture"]
        assert impact_refactor == _IMPACT_TEMPLATES["refactor"]
        assert impact_maintain == _IMPACT_TEMPLATES["maintainability"]

    def test_unknown_category_gets_generic(self):
        """Unknown category should get generic template."""
        result = repair_zh_field(V36_ENGLISH_IMPACT, "impact", "unknown_category")
        assert result == _GENERIC_IMPACT


# ---------------------------------------------------------------------------
# Tests: repair_zh_validation_tests
# ---------------------------------------------------------------------------


class TestRepairZhValidationTests:
    """Test validation_tests list repair."""

    def test_english_prose_repaired(self):
        tests = [V36_ENGLISH_VALIDATION]
        result = repair_zh_validation_tests(tests, "")
        assert result == [_VALIDATION_TEST_REPLACEMENT]

    def test_command_preserved(self):
        tests = ["pytest tests/test_cli.py"]
        result = repair_zh_validation_tests(tests, "")
        assert result == ["pytest tests/test_cli.py"]

    def test_chinese_preserved(self):
        tests = ["运行测试套件，确认没有新增警告或失败。"]
        result = repair_zh_validation_tests(tests, "")
        assert result == ["运行测试套件，确认没有新增警告或失败。"]

    def test_mixed_list(self):
        tests = [
            "pytest tests/",
            V36_ENGLISH_VALIDATION,
            "运行测试套件",
        ]
        result = repair_zh_validation_tests(tests, "")
        assert result[0] == "pytest tests/"  # command preserved
        assert result[1] == _VALIDATION_TEST_REPLACEMENT  # English repaired
        assert result[2] == "运行测试套件"  # Chinese preserved

    def test_none_returns_none(self):
        assert repair_zh_validation_tests(None) is None

    def test_empty_list_returns_empty(self):
        assert repair_zh_validation_tests([]) == []


# ---------------------------------------------------------------------------
# Tests: repair_zh_display_fields
# ---------------------------------------------------------------------------


class TestRepairZhDisplayFields:
    """Test finding-level display.zh repair."""

    def _make_finding(self, **kwargs) -> ReviewFinding:
        defaults = {
            "section": "Code Smells",
            "title": "Test finding",
            "description": "A test finding.",
            "severity": "high",
            "confidence": 0.85,
            "files": ["src/app.py"],
            "evidence_ids": ["ev_001"],
            "category": "code_smell",
        }
        defaults.update(kwargs)
        return ReviewFinding(**defaults)

    def test_english_display_fields_repaired(self):
        """All English display.zh fields should be repaired."""
        finding = self._make_finding(
            display=DisplayFields(
                en=BilingualTextField(
                    title="Test finding",
                    description="A test finding.",
                    impact=V36_ENGLISH_IMPACT,
                    recommendation=V36_ENGLISH_RECOMMENDATION,
                ),
                zh=BilingualTextField(
                    title=V36_ENGLISH_TITLE,
                    description=V36_ENGLISH_DESCRIPTION,
                    impact=V36_ENGLISH_IMPACT,
                    recommendation=V36_ENGLISH_RECOMMENDATION,
                ),
            ),
        )
        repaired = repair_zh_display_fields(finding)

        assert repaired.display.zh.title == _TITLE_TEMPLATES["code_smell"]
        assert repaired.display.zh.description == _DESCRIPTION_TEMPLATE
        assert repaired.display.zh.impact == _IMPACT_TEMPLATES["code_smell"]
        assert repaired.display.zh.recommendation == _RECOMMENDATION_TEMPLATES["code_smell"]

    def test_chinese_display_fields_preserved(self):
        """Chinese display.zh fields should NOT be modified."""
        finding = self._make_finding(
            display=DisplayFields(
                en=BilingualTextField(title="Test"),
                zh=BilingualTextField(
                    title=CLEAN_ZH_TITLE,
                    description=CLEAN_ZH_DESCRIPTION,
                    impact=CLEAN_ZH_IMPACT,
                ),
            ),
        )
        repaired = repair_zh_display_fields(finding)

        assert repaired.display.zh.title == CLEAN_ZH_TITLE
        assert repaired.display.zh.description == CLEAN_ZH_DESCRIPTION
        assert repaired.display.zh.impact == CLEAN_ZH_IMPACT

    def test_no_display_returns_same(self):
        """Finding without display should be returned unchanged."""
        finding = self._make_finding(display=None)
        repaired = repair_zh_display_fields(finding)
        assert repaired is finding

    def test_en_display_preserved(self):
        """English display fields should NOT be modified."""
        en_title = "English title"
        finding = self._make_finding(
            display=DisplayFields(
                en=BilingualTextField(title=en_title),
                zh=BilingualTextField(title=CLEAN_ZH_TITLE),
            ),
        )
        repaired = repair_zh_display_fields(finding)
        assert repaired.display.en.title == en_title

    def test_mixed_fields_partially_repaired(self):
        """Only English fields should be repaired; Chinese fields kept."""
        finding = self._make_finding(
            display=DisplayFields(
                en=BilingualTextField(),
                zh=BilingualTextField(
                    title=CLEAN_ZH_TITLE,  # Chinese — keep
                    impact=V36_ENGLISH_IMPACT,  # English — repair
                ),
            ),
        )
        repaired = repair_zh_display_fields(finding)

        assert repaired.display.zh.title == CLEAN_ZH_TITLE  # kept
        assert repaired.display.zh.impact == _IMPACT_TEMPLATES["code_smell"]  # repaired


# ---------------------------------------------------------------------------
# Tests: repair_zh_findings
# ---------------------------------------------------------------------------


class TestRepairZhFindings:
    """Test batch finding repair."""

    def test_all_findings_repaired(self):
        """All findings with English leakage should be repaired."""
        findings = [
            ReviewFinding(
                section="Code Smells",
                title="Test 1",
                description="Desc 1",
                severity="high",
                category="code_smell",
                display=DisplayFields(
                    en=BilingualTextField(),
                    zh=BilingualTextField(impact=V36_ENGLISH_IMPACT),
                ),
            ),
            ReviewFinding(
                section="Refactoring Suggestions",
                title="Test 2",
                description="Desc 2",
                severity="medium",
                category="refactor",
                display=DisplayFields(
                    en=BilingualTextField(),
                    zh=BilingualTextField(first_step=V36_ENGLISH_FIRST_STEP),
                ),
            ),
        ]
        repaired = repair_zh_findings(findings)

        assert repaired[0].display.zh.impact == _IMPACT_TEMPLATES["code_smell"]
        assert repaired[1].display.zh.first_step == _FIRST_STEP_TEMPLATES["refactor"]

    def test_empty_list(self):
        assert repair_zh_findings([]) == []


# ---------------------------------------------------------------------------
# Tests: repair_zh_metadata
# ---------------------------------------------------------------------------


class TestRepairZhMetadata:
    """Test metadata repair in rendered markdown."""

    def test_evidence_labels_repaired(self):
        """Evidence appendix labels should be translated."""
        md = "* Type：source\n* Symbol：send_static_file\n* Related findings：Test\n* Description：text"
        result = repair_zh_metadata(md)
        assert "* 类型：" in result
        assert "* 符号：" in result
        assert "* 关联问题：" in result
        assert "* 说明：" in result
        assert "* Type：" not in result
        assert "* Symbol：" not in result

    def test_evidence_description_repaired(self):
        md = "This evidence was derived from parsed code symbols or structured repository context."
        result = repair_zh_metadata(md)
        assert "该证据来自已解析的代码符号或结构化仓库上下文。" in result
        assert "This evidence was derived" not in result

    def test_repo_summary_repaired(self):
        md = "Python 仓库 with 83 Python files"
        result = repair_zh_metadata(md)
        assert "Python 仓库，包含" in result
        assert "Python 源文件" in result
        assert "Python 仓库 with" not in result

    def test_supporting_modules_repaired(self):
        md = "Supporting modules"
        result = repair_zh_metadata(md)
        assert "支撑模块" in result
        assert "Supporting modules" not in result

    def test_dependency_structure_repaired(self):
        md = "Dependency structure"
        result = repair_zh_metadata(md)
        assert "依赖结构" in result
        assert "Dependency structure" not in result

    def test_evidence_highlights_repaired(self):
        md = "The selected evidence highlights a repository concern."
        result = repair_zh_metadata(md)
        assert "以下证据指出" in result
        assert "The selected evidence highlights" not in result

    def test_snippet_missing_repaired(self):
        md = "Source snippet was not persisted; only file location and symbol info are available."
        result = repair_zh_metadata(md)
        assert "源码片段未持久化" in result

    def test_omitted_note_repaired(self):
        md = "Remaining evidence entries were omitted. Re-run the review to see full context."
        result = repair_zh_metadata(md)
        assert "其余证据已省略" in result

    def test_chinese_text_preserved(self):
        md = "该问题会增加维护成本。"
        result = repair_zh_metadata(md)
        assert result == md


# ---------------------------------------------------------------------------
# Tests: validate_zh_fields
# ---------------------------------------------------------------------------


class TestValidateZhFields:
    """Test zh field validation."""

    def test_clean_finding_no_issues(self):
        finding = ReviewFinding(
            section="Code Smells",
            title="Test",
            description="Desc",
            display=DisplayFields(
                en=BilingualTextField(),
                zh=BilingualTextField(
                    title=CLEAN_ZH_TITLE,
                    impact=CLEAN_ZH_IMPACT,
                ),
            ),
        )
        issues = validate_zh_fields(finding)
        assert issues == []

    def test_english_fields_reported(self):
        finding = ReviewFinding(
            section="Code Smells",
            title="Test",
            description="Desc",
            category="code_smell",
            display=DisplayFields(
                en=BilingualTextField(),
                zh=BilingualTextField(
                    title=V36_ENGLISH_TITLE,
                    impact=V36_ENGLISH_IMPACT,
                    recommendation=V36_ENGLISH_RECOMMENDATION,
                ),
            ),
        )
        issues = validate_zh_fields(finding)
        assert "title" in issues
        assert "impact" in issues
        assert "recommendation" in issues

    def test_no_display_no_issues(self):
        finding = ReviewFinding(
            section="Code Smells",
            title="Test",
            description="Desc",
            display=None,
        )
        issues = validate_zh_fields(finding)
        assert issues == []


# ---------------------------------------------------------------------------
# Tests: V3.6 regression — full pipeline
# ---------------------------------------------------------------------------


class TestV36Regression:
    """Regression tests using actual V3.6 bad examples."""

    def test_prepare_zh_report_repairs_english_fields(self):
        """prepare_zh_report should repair all English display.zh fields."""
        findings = [
            ReviewFinding(
                section="Code Smells",
                title="Test",
                description="Desc",
                severity="high",
                confidence=0.85,
                category="code_smell",
                files=["src/app.py"],
                evidence_ids=["ev_001"],
                display=DisplayFields(
                    en=BilingualTextField(
                        title="Test",
                        description="Desc",
                        impact=V36_ENGLISH_IMPACT,
                        recommendation=V36_ENGLISH_RECOMMENDATION,
                    ),
                    zh=BilingualTextField(
                        title=V36_ENGLISH_TITLE,
                        description=V36_ENGLISH_DESCRIPTION,
                        impact=V36_ENGLISH_IMPACT,
                        recommendation=V36_ENGLISH_RECOMMENDATION,
                    ),
                ),
            ),
        ]
        repaired, _ = prepare_zh_report(findings, "")

        assert repaired[0].display.zh.title == _TITLE_TEMPLATES["code_smell"]
        assert repaired[0].display.zh.impact == _IMPACT_TEMPLATES["code_smell"]
        assert repaired[0].display.zh.recommendation == _RECOMMENDATION_TEMPLATES["code_smell"]

    def test_finalize_zh_report_repairs_metadata(self):
        """finalize_zh_report should repair metadata patterns."""
        md = """# 证据附录

## E1 · src/flask/app.py:392-412

* Type：source
* Symbol：send_static_file
* Related findings：重复的错误处理模式
* Description：This evidence was derived from parsed code symbols or structured repository context.

Python 仓库 with 83 Python files。Supporting modules。Dependency structure。
"""
        result = finalize_zh_report(md)

        assert "* 类型：" in result
        assert "* 符号：" in result
        assert "* 关联问题：" in result
        assert "该证据来自" in result
        assert "Python 仓库，包含" in result
        assert "支撑模块" in result
        assert "依赖结构" in result
        # English should be gone
        assert "* Type：" not in result
        assert "* Symbol：" not in result
        assert "This evidence was derived" not in result
        assert "Supporting modules" not in result
        assert "Dependency structure" not in result

    def test_full_pipeline_english_findings_repaired_and_metadata_cleaned(self):
        """Full pipeline: repair fields pre-render, metadata post-render."""
        findings = [
            ReviewFinding(
                section="Code Smells",
                title="Test",
                description="Desc",
                severity="high",
                confidence=0.85,
                category="code_smell",
                files=["src/app.py"],
                evidence_ids=["ev_001"],
                display=DisplayFields(
                    en=BilingualTextField(),
                    zh=BilingualTextField(
                        impact=V36_ENGLISH_IMPACT,
                        recommendation=V36_ENGLISH_RECOMMENDATION,
                    ),
                ),
            ),
        ]

        # Pre-render: repair display.zh fields
        repaired, _ = prepare_zh_report(findings, "")

        # Verify fields were repaired
        assert repaired[0].display.zh.impact == _IMPACT_TEMPLATES["code_smell"]
        assert repaired[0].display.zh.recommendation == _RECOMMENDATION_TEMPLATES["code_smell"]

        # Post-render: repair metadata
        md = "* Type：source\n* Symbol：send_static_file"
        result = finalize_zh_report(md)
        assert "* 类型：" in result
        assert "* 符号：" in result


# ---------------------------------------------------------------------------
# Tests: allowed English preserved
# ---------------------------------------------------------------------------


class TestAllowedEnglishPreserved:
    """Test that allowed English tokens are NOT repaired."""

    def test_tech_names_in_chinese_field_preserved(self):
        """Chinese fields with tech names should be preserved."""
        text = "该问题使用了 Flask 和 FastAPI 框架。"
        assert is_english_leakage(text) is False
        assert repair_zh_field(text, "impact", "") == text

    def test_file_paths_in_chinese_field_preserved(self):
        text = "问题在 `src/flask/app.py` 中。"
        assert is_english_leakage(text) is False

    def test_code_symbols_preserved(self):
        assert is_english_leakage("send_static_file") is False
        assert is_english_leakage("OpenAICompatibleClient") is False

    def test_evidence_refs_preserved(self):
        assert is_english_leakage("[E1]") is False
        assert is_english_leakage("[E2]") is False

    def test_commands_preserved(self):
        assert is_english_leakage("pytest tests/test_cli.py") is False


# ---------------------------------------------------------------------------
# Tests: en report unchanged
# ---------------------------------------------------------------------------


class TestEnReportUnchanged:
    """Verify that English reports are NOT affected."""

    def test_en_report_not_translated(self):
        report = "CodePilot analyzed 42 Python source files and produced 5 findings."
        result = render_localized_report(report, "en")
        assert result == report

    def test_en_report_no_chinese_labels(self):
        report = "# Executive Summary\nContent.\n"
        result = render_localized_report(report, "en")
        assert "执行摘要" not in result
        assert "Executive Summary" in result


# ---------------------------------------------------------------------------
# Tests: old reviews still render
# ---------------------------------------------------------------------------


class TestOldReviewsStillRender:
    """Test that old reviews without bilingual display still work."""

    def test_old_review_without_display_fields(self):
        """Old reviews have no display.zh — normalization still works."""
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
            # No display field
        )
        # repair_zh_display_fields should return unchanged
        repaired = repair_zh_display_fields(finding)
        assert repaired is finding

    def test_legacy_review_metadata_cleaned(self):
        """Legacy reviews with English metadata should be cleaned."""
        md = "This evidence was derived from parsed code symbols."
        result = finalize_zh_report(md)
        assert "该证据来自" in result


# ---------------------------------------------------------------------------
# Tests: no secrets
# ---------------------------------------------------------------------------


class TestNoSecrets:
    """Verify no secrets leak through the presentation pipeline."""

    def test_api_keys_not_modified(self):
        md = "API key: sk-abc123def456ghi789jkl012mno345pqr678stu901"
        result = finalize_zh_report(md)
        assert "sk-abc123" in result

    def test_env_vars_preserved(self):
        md = "使用 OPENAI_API_KEY 环境变量"
        result = finalize_zh_report(md)
        assert "OPENAI_API_KEY" in result


# ---------------------------------------------------------------------------
# Tests: template completeness
# ---------------------------------------------------------------------------


class TestTemplateCompleteness:
    """Test that all category templates are defined."""

    ALL_CATEGORIES = ("code_smell", "architecture", "maintainability", "refactor")

    def test_impact_templates_complete(self):
        for cat in self.ALL_CATEGORIES:
            assert cat in _IMPACT_TEMPLATES, f"Missing impact template for {cat}"

    def test_recommendation_templates_complete(self):
        for cat in self.ALL_CATEGORIES:
            assert cat in _RECOMMENDATION_TEMPLATES, f"Missing recommendation template for {cat}"

    def test_first_step_templates_complete(self):
        for cat in self.ALL_CATEGORIES:
            assert cat in _FIRST_STEP_TEMPLATES, f"Missing first_step template for {cat}"

    def test_title_templates_complete(self):
        for cat in self.ALL_CATEGORIES:
            assert cat in _TITLE_TEMPLATES, f"Missing title template for {cat}"

    def test_caveat_templates_have_public_api(self):
        assert "public_api" in _CAVEAT_TEMPLATES

    def test_templates_are_chinese(self):
        """All templates should contain Chinese characters."""
        for template in (
            *_IMPACT_TEMPLATES.values(),
            *_RECOMMENDATION_TEMPLATES.values(),
            *_FIRST_STEP_TEMPLATES.values(),
            *_CAVEAT_TEMPLATES.values(),
            *_TITLE_TEMPLATES.values(),
            _DESCRIPTION_TEMPLATE,
            _CONFIDENCE_RATIONALE_TEMPLATE,
            _GENERIC_IMPACT,
            _GENERIC_RECOMMENDATION,
            _GENERIC_FIRST_STEP,
            _GENERIC_CAVEAT,
            _VALIDATION_TEST_REPLACEMENT,
        ):
            assert any('一' <= c <= '鿿' for c in template), (
                f"Template is not Chinese: {template!r}"
            )
