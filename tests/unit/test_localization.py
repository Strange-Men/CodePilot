"""Tests for the backend localization module."""

from __future__ import annotations

from backend.reviewers.localization import (
    CATEGORY_TRANSLATIONS,
    CHINESE_TO_ENGLISH_HEADINGS,
    LABEL_TRANSLATIONS,
    PROSE_REPLACEMENTS,
    REPORT_HEADING_TRANSLATIONS,
    SEVERITY_TRANSLATIONS,
    STATUS_VALUE_TRANSLATIONS,
    normalize_language,
    translate_enum_values,
    translate_finding_labels,
    translate_report_headings,
    translate_report_labels,
    translate_report_prose,
)
from backend.reviewers.localized_report_renderer import _fix_chinese_validation_backticks


class TestNormalizeLanguage:
    def test_none_returns_en(self) -> None:
        assert normalize_language(None) == "en"

    def test_empty_returns_en(self) -> None:
        assert normalize_language("") == "en"

    def test_whitespace_returns_en(self) -> None:
        assert normalize_language("  ") == "en"

    def test_invalid_returns_en(self) -> None:
        assert normalize_language("fr") == "en"
        assert normalize_language("de") == "en"
        assert normalize_language("EN") == "en"  # case-insensitive, valid

    def test_en_returns_en(self) -> None:
        assert normalize_language("en") == "en"

    def test_zh_returns_zh(self) -> None:
        assert normalize_language("zh") == "zh"

    def test_case_insensitive(self) -> None:
        assert normalize_language("EN") == "en"
        assert normalize_language("ZH") == "zh"
        assert normalize_language("Zh") == "zh"

    def test_strips_whitespace(self) -> None:
        assert normalize_language(" zh ") == "zh"
        assert normalize_language(" en ") == "en"


class TestTranslateReportHeadings:
    def test_en_returns_unchanged(self) -> None:
        report = "# Executive Summary\nSome content.\n"
        assert translate_report_headings(report, "en") == report

    def test_zh_translates_top_level_headings(self) -> None:
        report = "# Executive Summary\nContent.\n"
        result = translate_report_headings(report, "zh")
        assert "# 执行摘要" in result
        assert "Content." in result

    def test_zh_translates_second_level_headings(self) -> None:
        report = "## Top Risks\n- Risk one\n"
        result = translate_report_headings(report, "zh")
        assert "## 主要风险" in result

    def test_zh_preserves_unknown_headings(self) -> None:
        report = "# Custom Section\nContent.\n"
        result = translate_report_headings(report, "zh")
        assert "# Custom Section" in result

    def test_zh_translates_all_known_headings(self) -> None:
        report_lines = [f"# {heading}" for heading in REPORT_HEADING_TRANSLATIONS]
        report = "\n".join(report_lines) + "\n"
        result = translate_report_headings(report, "zh")
        for en, zh in REPORT_HEADING_TRANSLATIONS.items():
            assert f"# {zh}" in result, f"Missing translation for: {en}"

    def test_zh_preserves_body_content(self) -> None:
        report = (
            "# Executive Summary\n"
            "CodePilot analyzed 10 files.\n"
            "- Finding one\n"
            "- Finding two\n"
        )
        result = translate_report_headings(report, "zh")
        assert "CodePilot analyzed 10 files." in result
        assert "- Finding one" in result
        assert "- Finding two" in result


class TestTranslateFindingLabels:
    def test_en_returns_unchanged(self) -> None:
        text = "**Why it matters:** This is important."
        assert translate_finding_labels(text, "en") == text

    def test_none_returns_none(self) -> None:
        assert translate_finding_labels(None, "zh") is None

    def test_zh_translates_why_it_matters(self) -> None:
        text = "**Why it matters:** Changes may break consumers."
        result = translate_finding_labels(text, "zh")
        assert result == "**为什么重要：** Changes may break consumers."

    def test_zh_translates_first_step(self) -> None:
        text = "**First step:** Add tests before refactoring."
        result = translate_finding_labels(text, "zh")
        assert result == "**建议先做：** Add tests before refactoring."

    def test_zh_translates_caveat(self) -> None:
        text = "**Caveat:** This is a public API."
        result = translate_finding_labels(text, "zh")
        assert result == "**注意事项：** This is a public API."

    def test_zh_preserves_content_after_label(self) -> None:
        text = "**Evidence:** `ev_abc123`, `ev_def456`"
        result = translate_finding_labels(text, "zh")
        assert "`ev_abc123`, `ev_def456`" in result

    def test_zh_translates_multiple_labels(self) -> None:
        text = "**Why it matters:** Important.\n**First step:** Do something."
        result = translate_finding_labels(text, "zh")
        assert "**为什么重要：**" in result
        assert "**建议先做：**" in result


class TestTranslateReportLabels:
    def test_en_returns_unchanged(self) -> None:
        report = "**Type:** Python repository"
        assert translate_report_labels(report, "en") == report

    def test_zh_translates_type_label(self) -> None:
        report = "- **Type:** Python repository"
        result = translate_report_labels(report, "zh")
        assert "**类型：**" in result
        assert "Python repository" in result

    def test_zh_translates_scope_label(self) -> None:
        report = "- **Scope analyzed:** 10 of 15 files"
        result = translate_report_labels(report, "zh")
        assert "**分析范围：**" in result


class TestChineseToEnglishHeadingsReverse:
    def test_all_chinese_headings_have_english_reverse(self) -> None:
        for en, zh in REPORT_HEADING_TRANSLATIONS.items():
            assert zh in CHINESE_TO_ENGLISH_HEADINGS, f"Missing reverse for: {zh}"
            assert CHINESE_TO_ENGLISH_HEADINGS[zh] == en


class TestCanonicalDataPreservation:
    """Verify that localization never modifies canonical review data."""

    def test_severity_not_translated(self) -> None:
        text = "**Severity:** high"
        result = translate_finding_labels(text, "zh")
        assert "high" in result

    def test_confidence_not_translated(self) -> None:
        text = "confidence 0.91"
        result = translate_finding_labels(text, "zh")
        assert "0.91" in result

    def test_evidence_ids_not_translated(self) -> None:
        text = "**Evidence:** `ev_abc123`"
        result = translate_finding_labels(text, "zh")
        assert "`ev_abc123`" in result

    def test_file_paths_not_translated(self) -> None:
        text = "in `backend/api/reviews.py`"
        result = translate_finding_labels(text, "zh")
        assert "`backend/api/reviews.py`" in result


class TestTerminologyV355:
    """Verify V3.5.5 terminology changes."""

    def test_code_smells_heading_uses_new_term(self) -> None:
        assert REPORT_HEADING_TRANSLATIONS["Code Smells"] == "代码质量问题"

    def test_old_code_smell_term_not_in_headings(self) -> None:
        for zh in REPORT_HEADING_TRANSLATIONS.values():
            assert "代码坏味道" not in zh, f"Old term found in: {zh}"

    def test_architecture_summary_uses_new_term(self) -> None:
        assert REPORT_HEADING_TRANSLATIONS["Architecture Summary"] == "架构分析"

    def test_validation_tests_label_uses_new_term(self) -> None:
        assert LABEL_TRANSLATIONS["**Validation tests:**"] == "**验证方式：**"

    def test_no_bad_terms_in_label_translations(self) -> None:
        for zh in LABEL_TRANSLATIONS.values():
            assert "代码坏味道" not in zh

    def test_no_bad_terms_in_prose_replacements(self) -> None:
        for zh in PROSE_REPLACEMENTS.values():
            assert "代码坏味道" not in zh

    def test_prose_replacements_cover_key_sentences(self) -> None:
        # Check that key English prose sentences have Chinese replacements
        keys = list(PROSE_REPLACEMENTS.keys())
        assert any("This description is based on paths" in k for k in keys)
        assert any("Source snippets are intentionally omitted" in k for k in keys)
        assert any("Trace startup and top-level composition here" in k for k in keys)
        assert any("Changes can affect several internal consumers" in k for k in keys)
        assert any("Findings are grouped by the agent" in k for k in keys)
        assert any("Supported source files:" in k for k in keys)
        assert any("Average complexity estimate:" in k for k in keys)


class TestTranslateReportProse:
    def test_en_returns_unchanged(self) -> None:
        report = "Execution begins around `src/app.py`."
        assert translate_report_prose(report, "en") == report

    def test_zh_replaces_known_prose(self) -> None:
        report = (
            "- This description is based on paths, symbols, routes, "
            "and resolved internal dependencies."
        )
        result = translate_report_prose(report, "zh")
        assert "以上描述基于" in result
        assert "This description is based on" not in result

    def test_zh_replaces_source_snippets(self) -> None:
        report = "Source snippets are intentionally omitted."
        result = translate_report_prose(report, "zh")
        assert "不展开源码片段" in result

    def test_zh_replaces_metrics_labels(self) -> None:
        report = "- Supported source files: 42\n- Average complexity estimate: 3.14"
        result = translate_report_prose(report, "zh")
        assert "支持的源文件数：" in result
        assert "平均复杂度估计：" in result

    def test_zh_preserves_code_symbols(self) -> None:
        report = "Execution begins around `src/flask/app.py`."
        result = translate_report_prose(report, "zh")
        assert "`src/flask/app.py`" in result

    def test_zh_replaces_table_headers(self) -> None:
        report = "| Area | Files | Why It Matters |"
        result = translate_report_prose(report, "zh")
        assert "| 区域 |" in result
        assert "| 重要性 |" in result


class TestTranslateEnumValues:
    def test_en_returns_unchanged(self) -> None:
        report = "| completed | validated |"
        assert translate_enum_values(report, "en") == report

    def test_zh_translates_status_in_table_cells(self) -> None:
        report = "| ArchitectureAgent | completed | 1 | H1 M0 L0 | 0.92 | 2 |"
        result = translate_enum_values(report, "zh")
        assert "已完成" in result
        assert "completed" not in result

    def test_zh_translates_severity_in_table_cells(self) -> None:
        report = "| high | Finding title | 0.85 | a.py | ev_1 |"
        result = translate_enum_values(report, "zh")
        assert "| 高 |" in result

    def test_zh_translates_severity_mix_abbreviations(self) -> None:
        report = "H1 M2 L0"
        result = translate_enum_values(report, "zh")
        assert "高1" in result
        assert "中2" in result
        assert "低0" in result

    def test_zh_translates_severity_count_patterns(self) -> None:
        report = "medium=1, low=2"
        result = translate_enum_values(report, "zh")
        assert "中=1" in result
        assert "低=2" in result

    def test_zh_translates_category_in_labels(self) -> None:
        report = "**类型：** architecture"
        result = translate_enum_values(report, "zh")
        assert "**类型：** 架构" in result

    def test_zh_translates_status_in_labels(self) -> None:
        report = "**状态：** completed"
        result = translate_enum_values(report, "zh")
        assert "**状态：** 已完成" in result

    def test_zh_preserves_code_symbols(self) -> None:
        report = "The `completed` function in high.py"
        result = translate_enum_values(report, "zh")
        # Should not translate inline code references
        assert "`completed`" in result

    def test_severity_translations_complete(self) -> None:
        assert SEVERITY_TRANSLATIONS["critical"] == "严重"
        assert SEVERITY_TRANSLATIONS["high"] == "高"
        assert SEVERITY_TRANSLATIONS["medium"] == "中"
        assert SEVERITY_TRANSLATIONS["low"] == "低"

    def test_status_translations_complete(self) -> None:
        assert STATUS_VALUE_TRANSLATIONS["completed"] == "已完成"
        assert STATUS_VALUE_TRANSLATIONS["validated"] == "已验证"
        assert STATUS_VALUE_TRANSLATIONS["failed"] == "失败"
        assert STATUS_VALUE_TRANSLATIONS["skipped"] == "已跳过"
        assert STATUS_VALUE_TRANSLATIONS["pending"] == "等待中"
        assert STATUS_VALUE_TRANSLATIONS["running"] == "运行中"

    def test_category_translations_complete(self) -> None:
        assert CATEGORY_TRANSLATIONS["architecture"] == "架构"
        assert CATEGORY_TRANSLATIONS["code_smell"] == "代码质量"
        assert CATEGORY_TRANSLATIONS["maintainability"] == "可维护性"
        assert CATEGORY_TRANSLATIONS["refactor"] == "重构"


class TestReportBannedStrings:
    """Verify that zh reports never contain banned English strings."""

    BANNED_STRINGS = [
        "[zh]",
        "Recommendation:",
        "Impact:",
        "First step:",
        "Validation tests:",
        "Caveat:",
        "Grounding:",
        "Category:",
        "confidence=",
    ]

    def test_label_translations_cover_banned_labels(self) -> None:
        """All banned bold labels should have Chinese translations."""
        for banned in ["**Recommendation:**", "**Impact:**", "**First step:**",
                        "**Validation tests:**", "**Caveat:**", "**Grounding:**",
                        "**Category:**"]:
            assert banned in LABEL_TRANSLATIONS, f"Missing translation for: {banned}"

    def test_first_step_uses_polished_term(self) -> None:
        """First step label should use 建议先做, not 安全第一步."""
        assert LABEL_TRANSLATIONS["**First step:**"] == "**建议先做：**"
        assert LABEL_TRANSLATIONS["**First safe step:**"] == "**建议先做：**"

    def test_confidence_pattern_translated(self) -> None:
        assert "confidence=" in PROSE_REPLACEMENTS
        assert PROSE_REPLACEMENTS["confidence="] == "置信度="

    def test_no_bad_terms_in_severity_translations(self) -> None:
        for zh in SEVERITY_TRANSLATIONS.values():
            assert "代码坏味道" not in zh

    def test_no_bad_terms_in_status_translations(self) -> None:
        for zh in STATUS_VALUE_TRANSLATIONS.values():
            assert "代码坏味道" not in zh


class TestV357InlinePatterns:
    """Verify V3.5.7 inline severity+confidence pattern translations."""

    def test_severity_confidence_parenthetical_translated(self) -> None:
        report = "- **title** (medium, confidence 0.90) in `file.py`; evidence: ev_1."
        result = translate_enum_values(report, "zh")
        assert "严重程度：中" in result
        assert "置信度：0.90" in result
        assert "(medium, confidence 0.90)" not in result

    def test_all_severity_confidence_patterns_translated(self) -> None:
        for en_sev, zh_sev in SEVERITY_TRANSLATIONS.items():
            report = f"({en_sev}, confidence 0.50)"
            result = translate_enum_values(report, "zh")
            assert f"严重程度：{zh_sev}" in result, f"Failed for {en_sev}"

    def test_standalone_severity_parenthetical_translated(self) -> None:
        report = "Finding (medium) needs attention."
        result = translate_enum_values(report, "zh")
        assert "（中）" in result
        assert "(medium)" not in result

    def test_evidence_semicolon_translated(self) -> None:
        report = "in `file.py`; evidence: ev_1."
        result = translate_report_prose(report, "zh")
        # The "; evidence:" pattern should be translated
        assert "; evidence:" not in result or "；证据引用：" in result

    def test_in_file_path_translated_to_chinese(self) -> None:
        """The 'in `path`' pattern after confidence parenthetical should be translated."""
        report = "- **title** (medium, confidence 0.72) in `src/flask/app.py`; evidence: [E4]."
        result = translate_enum_values(report, "zh")
        assert "涉及文件：" in result
        assert "in `src/" not in result

    def test_in_multiple_file_paths_translated(self) -> None:
        """Multiple comma-separated paths after 'in' should all be preserved."""
        report = "- **title** (medium, confidence 0.72) in `src/a.py`, `src/b.py`, `src/c.py`; evidence: [E4]."
        result = translate_enum_values(report, "zh")
        assert "涉及文件：" in result
        assert "`src/a.py`" in result
        assert "`src/b.py`" in result
        assert "`src/c.py`" in result
        assert "in `src/" not in result

    def test_in_file_path_with_already_translated_confidence(self) -> None:
        """When confidence is already translated to 置信度, the pattern should still match."""
        report = "- **title** (medium, 置信度 0.72) in `src/flask/app.py`; evidence: [E4]."
        result = translate_enum_values(report, "zh")
        assert "涉及文件：" in result
        assert "in `src/" not in result


class TestV357ProseReplacements:
    """Verify V3.5.7 new prose replacements."""

    def test_codepilot_analyzed_translated(self) -> None:
        report = "CodePilot analyzed 10 files."
        result = translate_report_prose(report, "zh")
        assert "CodePilot 审查了" in result
        assert "CodePilot analyzed" not in result

    def test_and_produced_translated(self) -> None:
        report = "analyzed 10 files and produced 5 findings."
        result = translate_report_prose(report, "zh")
        assert "并产出了" in result

    def test_no_validated_risks_translated(self) -> None:
        report = "no validated risks"
        result = translate_report_prose(report, "zh")
        assert "暂无已验证的风险" in result

    def test_evidence_grounded_findings_translated(self) -> None:
        report = "5 evidence-grounded findings"
        result = translate_report_prose(report, "zh")
        assert "基于证据的问题发现" in result

    def test_fallback_report_translated(self) -> None:
        report = "The full report could not be composed due to an LLM error during report generation."
        result = translate_report_prose(report, "zh")
        assert "由于 LLM" in result
        assert "无法组装完整报告" in result


class TestV357ValidationBackticks:
    """Verify V3.5.7 strips backticks from Chinese natural language validation text."""

    def test_chinese_text_backticks_stripped(self) -> None:
        text = "在边界变更前后运行完整测试套件，确认无回归。"
        result = _fix_chinese_validation_backticks(f"`{text}`")
        assert result == text
        assert "`" not in result

    def test_command_backticks_preserved(self) -> None:
        text = "Run `pytest tests/` before and after."
        result = _fix_chinese_validation_backticks(text)
        assert "`pytest tests/`" in result

    def test_file_path_backticks_preserved(self) -> None:
        text = "Check `backend/api/reviews.py` for issues."
        result = _fix_chinese_validation_backticks(text)
        assert "`backend/api/reviews.py`" in result

    def test_mixed_content(self) -> None:
        text = "运行 `pytest` 确认无回归。"
        result = _fix_chinese_validation_backticks(text)
        # "pytest" should keep backticks (no Chinese chars)
        assert "`pytest`" in result
        # Chinese text around it should be fine
        assert "运行" in result
        assert "确认无回归" in result

    def test_no_chinese_text_unchanged(self) -> None:
        text = "Run `pytest` and `npm test`."
        result = _fix_chinese_validation_backticks(text)
        assert result == text
