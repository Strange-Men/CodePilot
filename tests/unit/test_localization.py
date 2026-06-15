"""Tests for the backend localization module."""

from __future__ import annotations

from backend.reviewers.localization import (
    CHINESE_TO_ENGLISH_HEADINGS,
    REPORT_HEADING_TRANSLATIONS,
    normalize_language,
    translate_finding_labels,
    translate_report_headings,
    translate_report_labels,
)


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
        assert result == "**第一步：** Add tests before refactoring."

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
        assert "**第一步：**" in result


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
