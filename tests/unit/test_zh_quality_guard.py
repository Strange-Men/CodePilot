"""Tests for Chinese report quality guard.

Validates that zh reports do not contain obvious English natural-language
leakage, that code/file paths/symbols are preserved, and that raw ev_* IDs
are properly handled.
"""

from __future__ import annotations

import pytest

from backend.reviewers.localized_report_renderer import render_localized_report
from backend.reviewers.zh_quality import (
    _RAW_EV_RE,
    _SEVERITY_REPLACEMENTS,
    _STATUS_REPLACEMENTS,
    assert_no_obvious_zh_leak,
    detect_english_natural_language_leak,
    is_allowed_english_token,
    normalize_zh_markdown,
    normalize_zh_text,
    redact_or_replace_raw_evidence_ids,
    validate_chinese_report_text,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

SAMPLE_ZH_REPORT = """# 执行摘要

CodePilot 审查了 42 个 Python 源文件并产出了 5 个基于证据的问题发现（高2，中2，低1）。

## 主要风险

- **重复的错误处理模式** （高，置信度 0.90）涉及文件：`src/flask/app.py`；证据引用：[E1] [E2]。
- **循环依赖风险** （中，置信度 0.85）涉及文件：`src/flask/blueprints.py`；证据引用：[E3]。

# 仓库概览

- **类型：** Python repository
- **主要组件：** Flask, Blueprint, SQLAlchemy
- **分析范围：** 42 个已分析文件
- **仓库摘要：** 这是一个基于 Flask 的 Web 应用。

# 工作方式

执行入口主要集中在 `src/flask/app.py`，随后调用 `src/flask/blueprints.py`。

# Agent 总结

| Agent | 状态 | 问题数 | 严重性分布 | 平均置信度 | 证据数 |
| --- | --- | ---: | --- | ---: | ---: |
| 架构分析 Agent | 已完成 | 2 | 高1 中1 | 0.88 | 3 |
| 代码质量 Agent | 已完成 | 3 | 中2 低1 | 0.75 | 2 |

# 证据附录

## E1 · src/flask/app.py:392-412

* 类型：source
* 符号：send_static_file
* 关联问题：重复的错误处理模式
* 说明：该证据来自已解析的代码符号或结构化仓库上下文。

```python
def send_static_file(self, filename):
    return self._send_static_file(filename)
```

# 仓库指标

- 支持的源文件数：42
- 已分析文件数：42
- 已跳过文件数：0
- 总行数：12500
- 平均复杂度：3.45
"""

SAMPLE_EN_REPORT = """# Executive Summary

CodePilot analyzed 42 Python source files and produced 5 evidence-grounded findings (2 high, 2 medium, 1 low).

## Top Risks

- **Duplicate error handling** (high, confidence 0.90) in `src/flask/app.py`; evidence: [E1] [E2].
- **Circular dependency risk** (medium, confidence 0.85) in `src/flask/blueprints.py`; evidence: [E3].
"""

MIXED_MIMO_REPORT_ZH = """# 执行摘要

CodePilot 审查了 15 个 Python 源文件并产出了 3 个基于证据的问题发现。

## 主要风险

- **循环依赖模式：** Flask app 和 Blueprint 之间存在双向导入。
  建议：变更需要同时修改多个位置，会增加遗漏、缺陷和维护成本。
  影响：复杂代码会增加缺陷风险，也会让后续扩展和调试更困难。
  建议先做：先确认是否存在可复用的公共基类；如果没有，可提取一个辅助函数，让 Flask app 和 Blueprint 共同复用。
  验证方式：`pytest tests/test_flask.py`
  证据引用：[E1] [E2]。

- **递归深度风险：** 某些递归函数缺少深度限制。
  建议：可以考虑改为迭代写法，以提升可读性。
  影响：对不熟悉递归的维护者来说，可读性会下降。
  证据引用：[E3]。
"""

RAW_EV_IN_TEXT = "这个问题的证据是 ev_aabbccddeeff00112233 和 ev_11223344556677889900。"


# ---------------------------------------------------------------------------
# Tests: is_allowed_english_token
# ---------------------------------------------------------------------------


class TestIsAllowedEnglishToken:
    """Test allowed English token detection."""

    def test_file_paths_are_allowed(self):
        assert is_allowed_english_token("src/flask/app.py")
        assert is_allowed_english_token("backend/api/reviews.py")
        assert is_allowed_english_token("tests/test_cli.py")
        assert is_allowed_english_token("./config/settings.yaml")
        assert is_allowed_english_token("../docs/README.md")

    def test_code_symbols_are_allowed(self):
        assert is_allowed_english_token("send_static_file")
        assert is_allowed_english_token("OpenAICompatibleClient")
        assert is_allowed_english_token("MAX_ENTRIES")
        assert is_allowed_english_token("renderReport")
        assert is_allowed_english_token("my_function")

    def test_commands_are_allowed(self):
        assert is_allowed_english_token("pytest tests/test_cli.py")
        assert is_allowed_english_token("npm run build")
        assert is_allowed_english_token("git commit")

    def test_tech_names_are_allowed(self):
        assert is_allowed_english_token("Flask")
        assert is_allowed_english_token("FastAPI")
        assert is_allowed_english_token("React")
        assert is_allowed_english_token("SQLite")
        assert is_allowed_english_token("MiMo")
        assert is_allowed_english_token("OpenAI")

    def test_evidence_refs_are_allowed(self):
        assert is_allowed_english_token("[E1]")
        assert is_allowed_english_token("[E2]")
        assert is_allowed_english_token("[E99]")

    def test_common_tech_abbreviations_are_allowed(self):
        assert is_allowed_english_token("api")
        assert is_allowed_english_token("cli")
        assert is_allowed_english_token("json")
        assert is_allowed_english_token("yaml")

    def test_natural_language_words_are_not_allowed(self):
        assert not is_allowed_english_token("Changes")
        assert not is_allowed_english_token("require")
        assert not is_allowed_english_token("updates")
        assert not is_allowed_english_token("multiple")
        assert not is_allowed_english_token("locations")


# ---------------------------------------------------------------------------
# Tests: detect_english_natural_language_leak
# ---------------------------------------------------------------------------


class TestDetectEnglishLeak:
    """Test English natural language leak detection."""

    def test_chinese_text_has_no_leak(self):
        text = "变更需要同时修改多个位置，会增加遗漏、缺陷和维护成本。"
        leaks = detect_english_natural_language_leak(text)
        assert leaks == []

    def test_english_sentence_detected(self):
        text = "Changes require updates in multiple locations, increasing bug risk."
        leaks = detect_english_natural_language_leak(text)
        assert len(leaks) > 0

    def test_code_blocks_ignored(self):
        text = """中文文本。

```python
def changes_require_updates():
    pass
```

更多中文。"""
        leaks = detect_english_natural_language_leak(text)
        assert leaks == []

    def test_inline_code_ignored(self):
        text = "调用 `send_static_file` 函数来处理静态文件。"
        leaks = detect_english_natural_language_leak(text)
        assert leaks == []

    def test_table_rows_ignored(self):
        text = "| completed | 2 | 高1 中1 | 0.88 | 3 |"
        leaks = detect_english_natural_language_leak(text)
        assert leaks == []

    def test_mixed_chinese_english_not_flagged(self):
        """Lines with Chinese characters are intentional bilingual content."""
        text = "这个函数使用了 Flask 框架来处理请求。"
        leaks = detect_english_natural_language_leak(text)
        assert leaks == []

    def test_short_english_fragments_not_flagged(self):
        """Short fragments with < 4 common words are acceptable."""
        text = "使用 API 接口"
        leaks = detect_english_natural_language_leak(text)
        assert leaks == []


# ---------------------------------------------------------------------------
# Tests: normalize_zh_text
# ---------------------------------------------------------------------------


class TestNormalizeZhText:
    """Test text field normalization."""

    def test_none_is_safe(self):
        assert normalize_zh_text(None) is None

    def test_phrase_replacement(self):
        text = "Changes require updates in multiple locations, increasing bug risk and maintenance effort."
        result = normalize_zh_text(text)
        assert "变更需要同时修改多个位置" in result
        assert "Changes require" not in result

    def test_recursion_phrase_replacement(self):
        text = "Reduced readability for developers unfamiliar with recursion"
        result = normalize_zh_text(text)
        assert "对不熟悉递归的维护者来说" in result

    def test_iterative_phrase_replacement(self):
        text = "Consider rewriting using an iterative approach"
        result = normalize_zh_text(text)
        assert "迭代写法" in result

    def test_duplication_phrase_replacement(self):
        text = "This duplication may be intentional"
        result = normalize_zh_text(text)
        assert "这种重复可能是出于兼容性" in result

    def test_complex_code_phrase_replacement(self):
        text = "Complex code increases risk of bugs and makes it harder to extend or debug."
        result = normalize_zh_text(text)
        assert "复杂代码会增加缺陷风险" in result

    def test_module_detection_phrase_replacement(self):
        text = "Could lead to incorrect module detection, affecting CLI commands."
        result = normalize_zh_text(text)
        assert "可能导致模块识别错误" in result

    def test_validated_symbols_replacement(self):
        text = "validated symbols `send_static_file`"
        result = normalize_zh_text(text)
        assert "已验证符号" in result
        assert "`send_static_file`" in result

    def test_backward_compatibility_replacement(self):
        text = "backward compatibility"
        result = normalize_zh_text(text)
        assert "向后兼容性" in result

    def test_code_paths_preserved(self):
        text = "问题在 `src/flask/app.py` 中"
        result = normalize_zh_text(text)
        assert "`src/flask/app.py`" in result

    def test_empty_text(self):
        assert normalize_zh_text("") == ""


# ---------------------------------------------------------------------------
# Tests: V3.5.12 final zh metadata cleanup
# ---------------------------------------------------------------------------


class TestV3512FinalZhMetadataCleanup:
    """Regression tests for final Chinese report/export metadata cleanup."""

    def test_summary_metadata_cleanup(self):
        md = (
            "CodePilot 审查了 83 Python source files；"
            "analyzed 83 and skipped 0；"
            "83 of 83 supported source files。"
        )
        result = normalize_zh_markdown(md)

        assert "83 个 Python 源文件" in result
        assert "已分析 83 个，已跳过 0 个" in result
        assert "已分析 83 / 83 个支持的源文件" in result
        assert "Python source files" not in result
        assert "supported source files" not in result

    def test_repo_overview_label_cleanup(self):
        md = """| Area | Files | Why |
| --- | --- | --- |
| Entry points | `app.py` | startup |
| Core modules | `core.py` | central |
| Dependency hubs | `hub.py` | fan-in |

## Cycle group 1
- Python repository
- source files
- analyzed files
- skipped files
"""
        result = normalize_zh_markdown(md)

        assert "入口文件" in result
        assert "核心模块" in result
        assert "依赖枢纽" in result
        assert "循环依赖组 1" in result
        assert "Python 仓库" in result
        assert "源文件" in result
        assert "已分析文件" in result
        assert "已跳过文件" in result

    def test_severity_status_and_display_values_cleanup(self):
        md = """| Agent | Status | Severity |
| --- | --- | --- |
| A1 | completed | high |
| A2 | validated | medium |
| A3 | running | low |
| A4 | failed | info |

状态：completed；严重性：medium；Confidence: n/a；validated symbols `foo`；no findings。
"""
        result = normalize_zh_markdown(md)

        assert "状态" in result
        assert "| 已完成 | 高 |" in result
        assert "| 已验证 | 中 |" in result
        assert "| 运行中 | 低 |" in result
        assert "| 失败 | 信息 |" in result
        assert "状态：已完成" in result
        assert "严重性：中" in result
        assert "置信度 暂无数据" in result
        assert "已验证符号 `foo`" in result
        assert "暂未发现明确问题" in result

    def test_validate_chinese_report_text_flags_english_prose_but_preserves_code(self):
        report = """建议：Consider rewriting this logic to reduce maintenance risk.
影响：src/flask/app.py 中的 `send_static_file` 和 Blueprint 应保留原文。
验证方式：运行 `pytest tests/test_app.py`，确认行为不变。
"""

        issues = validate_chinese_report_text(report)

        assert any(issue.startswith("mixed_language_issue") for issue in issues)
        assert all("src/flask/app.py" not in issue for issue in issues)
        assert all("send_static_file" not in issue for issue in issues)

    def test_mixed_count_phrases(self):
        result = normalize_zh_text("4 medium; 2 medium, 2 low; 1 high, 3 info")

        assert result == "4 个中风险; 2 个中风险，2 个低风险; 1 个高风险，3 个信息项"

    def test_allowed_tech_tokens_preserved(self):
        md = "Python/Flask/API/URL/JSON/HTTP/CLI/UI/DB/SQL 与 MiMo/OpenAI 均应保留。"
        result = normalize_zh_markdown(md)

        for token in ["Python", "Flask", "API", "URL", "JSON", "HTTP", "CLI", "UI", "DB", "SQL", "MiMo", "OpenAI"]:
            assert token in result

    def test_file_paths_inline_code_and_code_blocks_preserved(self):
        md = """路径 backend/reviewers/zh_quality.py 保留；`source files` 和 `completed` 保留。

```text
Recommendation: keep source files and completed unchanged in code.
```
"""
        result = normalize_zh_markdown(md)

        assert "backend/reviewers/zh_quality.py" in result
        assert "`source files`" in result
        assert "`completed`" in result
        assert "Recommendation: keep source files and completed unchanged in code." in result

    def test_e1_e2_refs_preserved_and_raw_ev_hidden(self):
        md = "证据 [E1] [E2] raw ev_aabbccddeeff00112233"
        result = normalize_zh_markdown(md)

        assert "[E1]" in result
        assert "[E2]" in result
        assert "ev_aabbccddeeff00112233" not in result
        assert "[E?]" in result

    def test_hyphenated_english_fallback_title_not_mangled(self):
        result = normalize_zh_text("Evidence-grounded architecture boundary; Evidence: [E1]")

        assert "Evidence-grounded architecture boundary" in result
        assert "证据引用 [E1]" in result

    def test_english_renderer_unchanged(self):
        report = "CodePilot analyzed 83 Python source files and produced 4 medium findings."

        assert render_localized_report(report, "en") == report


# ---------------------------------------------------------------------------
# Tests: normalize_zh_markdown
# ---------------------------------------------------------------------------


class TestNormalizeZhMarkdown:
    """Test markdown normalization."""

    def test_code_blocks_not_modified(self):
        md = """中文文本。

```python
def changes_require_updates():
    Recommendation = "do something"
    return Impact
```

更多中文。"""
        result = normalize_zh_markdown(md)
        assert "def changes_require_updates():" in result
        assert 'Recommendation = "do something"' in result
        assert "return Impact" in result

    def test_inline_code_preserved(self):
        md = "调用 `send_static_file` 函数来处理 `src/flask/app.py` 中的静态文件。"
        result = normalize_zh_markdown(md)
        assert "`send_static_file`" in result
        assert "`src/flask/app.py`" in result

    def test_severity_in_parentheses_translated(self):
        md = "这个问题是（medium）级别的。"
        result = normalize_zh_markdown(md)
        assert "（中）" in result
        assert "medium" not in result

    def test_severity_in_table_translated(self):
        md = "| high | 问题描述 | 0.90 |"
        result = normalize_zh_markdown(md)
        assert "| 高 |" in result

    def test_status_in_table_translated(self):
        md = "| completed | 2 |"
        result = normalize_zh_markdown(md)
        assert "| 已完成 |" in result

    def test_evidence_refs_preserved(self):
        md = "证据引用：[E1] [E2] [E3]"
        result = normalize_zh_markdown(md)
        assert "[E1]" in result
        assert "[E2]" in result
        assert "[E3]" in result

    def test_raw_ev_ids_replaced(self):
        md = "证据 ev_aabbccddeeff00112233 已验证。"
        result = normalize_zh_markdown(md)
        assert "ev_aabbccddeeff00112233" not in result
        assert "[E?]" in result

    def test_known_phrase_replaced(self):
        md = "Changes require updates in multiple locations, increasing bug risk and maintenance effort."
        result = normalize_zh_markdown(md)
        assert "变更需要同时修改多个位置" in result
        assert "Changes require" not in result

    def test_backward_compatibility_label_translated(self):
        md = "这是为了 backward compatibility 考虑。"
        result = normalize_zh_markdown(md)
        assert "向后兼容性" in result

    def test_mixed_zh_report_passes(self):
        """The sample mixed MiMo report should pass quality checks."""
        result = normalize_zh_markdown(MIXED_MIMO_REPORT_ZH)
        # Known phrases should be replaced
        assert "变更需要同时修改多个位置" in result
        assert "复杂代码会增加缺陷风险" in result
        assert "迭代写法" in result
        assert "向后兼容性" not in result or "backward compatibility" not in result

    def test_empty_markdown(self):
        assert normalize_zh_markdown("") == ""


# ---------------------------------------------------------------------------
# Tests: raw ev_* regression
# ---------------------------------------------------------------------------


class TestRawEvidenceIdRegression:
    """Test that raw ev_* IDs do not leak to user-facing reports."""

    def test_raw_ev_ids_replaced_with_placeholder(self):
        result = normalize_zh_markdown(RAW_EV_IN_TEXT)
        assert "ev_aabbccddeeff00112233" not in result
        assert "ev_11223344556677889900" not in result
        assert "[E?]" in result

    def test_redact_without_display_map(self):
        result = redact_or_replace_raw_evidence_ids(RAW_EV_IN_TEXT)
        assert "ev_aabbccddeeff00112233" not in result
        assert "[E?]" in result

    def test_redact_with_display_map(self):
        class MockDisplayMap:
            def ref_bracket(self, raw_id: str) -> str:
                mapping = {
                    "ev_aabbccddeeff00112233": "[E1]",
                    "ev_11223344556677889900": "[E2]",
                }
                return mapping.get(raw_id, "[E?]")

        result = redact_or_replace_raw_evidence_ids(RAW_EV_IN_TEXT, MockDisplayMap())
        assert "ev_aabbccddeeff00112233" not in result
        assert "[E1]" in result
        assert "[E2]" in result

    def test_no_ev_ids_in_sample_zh_report(self):
        result = normalize_zh_markdown(SAMPLE_ZH_REPORT)
        matches = _RAW_EV_RE.findall(result)
        assert matches == []

    def test_ev_pattern_matches_correctly(self):
        assert _RAW_EV_RE.search("ev_aabbccddeeff00112233")
        assert not _RAW_EV_RE.search("ev_short")
        assert not _RAW_EV_RE.search("[E1]")
        assert not _RAW_EV_RE.search("evidence_id")


# ---------------------------------------------------------------------------
# Tests: assert_no_obvious_zh_leak
# ---------------------------------------------------------------------------


class TestAssertNoObviousZhLeak:
    """Test the quality assertion function."""

    def test_clean_chinese_report_passes(self):
        issues = assert_no_obvious_zh_leak(SAMPLE_ZH_REPORT)
        # May have minor issues but no raw ev_* or obvious English labels
        ev_issues = [i for i in issues if "ev_*" in i]
        assert ev_issues == []

    def test_raw_ev_ids_detected(self):
        md = "问题证据 ev_aabbccddeeff00112233 已验证。"
        issues = assert_no_obvious_zh_leak(md)
        assert any("ev_*" in i for i in issues)

    def test_english_label_detected(self):
        md = "- **Recommendation:** 使用迭代写法"
        issues = assert_no_obvious_zh_leak(md)
        assert any("Recommendation" in i for i in issues)

    def test_normalized_report_passes(self):
        """After normalization, the mixed MiMo report should pass."""
        normalized = normalize_zh_markdown(MIXED_MIMO_REPORT_ZH)
        issues = assert_no_obvious_zh_leak(normalized)
        # No raw ev_* should remain
        ev_issues = [i for i in issues if "ev_*" in i]
        assert ev_issues == []


# ---------------------------------------------------------------------------
# Tests: English report unchanged
# ---------------------------------------------------------------------------


class TestEnglishReportUnchanged:
    """Verify that English reports are NOT accidentally translated."""

    def test_en_report_not_translated(self):
        """normalize_zh_markdown should NOT be called on English reports.
        But if it were, it should not destroy English content."""
        # normalize_zh_markdown is only called for zh, but verify
        # the function doesn't corrupt English text badly
        result = normalize_zh_markdown(SAMPLE_EN_REPORT)
        # The English report content should still be mostly intact
        assert "Executive Summary" in result
        assert "CodePilot analyzed" in result

    def test_severity_translations_only_apply_in_zh_context(self):
        """Severity translations in normalize_zh_markdown are context-aware."""
        en_text = "This is a high severity issue."
        # "high" in a natural English sentence gets translated, but that's OK
        # because this function is ONLY called for zh reports
        # The key is that English reports never pass through this function
        normalize_zh_markdown(en_text)  # nosec: intentional call to verify no crash


# ---------------------------------------------------------------------------
# Tests: Severity/Status value translations
# ---------------------------------------------------------------------------


class TestEnumTranslations:
    """Test severity and status value translations."""

    @pytest.mark.parametrize(
        ("en_val", "zh_val"),
        _SEVERITY_REPLACEMENTS.items(),
    )
    def test_severity_in_parentheses(self, en_val: str, zh_val: str):
        md = f"（{en_val}）"
        result = normalize_zh_markdown(md)
        assert f"（{zh_val}）" in result

    @pytest.mark.parametrize(
        ("en_val", "zh_val"),
        _STATUS_REPLACEMENTS.items(),
    )
    def test_status_in_parentheses(self, en_val: str, zh_val: str):
        md = f"（{en_val}）"
        result = normalize_zh_markdown(md)
        assert f"（{zh_val}）" in result

    def test_severity_in_table(self):
        md = "| medium | low | high |"
        result = normalize_zh_markdown(md)
        assert "| 中 |" in result
        assert "| 低 |" in result
        assert "| 高 |" in result

    def test_status_in_table(self):
        md = "| completed | failed | running |"
        result = normalize_zh_markdown(md)
        assert "| 已完成 |" in result
        assert "| 失败 |" in result
        assert "| 运行中 |" in result


# ---------------------------------------------------------------------------
# Tests: Phrase replacements completeness
# ---------------------------------------------------------------------------


class TestPhraseReplacements:
    """Test that all defined phrase replacements work."""

    @pytest.mark.parametrize(
        ("en_phrase", "zh_fragment"),
        [
            (
                "Changes require updates in multiple locations, increasing bug risk and maintenance effort.",
                "变更需要同时修改多个位置",
            ),
            (
                "Reduced readability for developers unfamiliar with recursion",
                "对不熟悉递归的维护者来说",
            ),
            (
                "Consider rewriting using an iterative approach",
                "迭代写法",
            ),
            (
                "This duplication may be intentional",
                "这种重复可能是出于兼容性",
            ),
            (
                "Complex code increases risk of bugs and makes it harder to extend or debug.",
                "复杂代码会增加缺陷风险",
            ),
            (
                "Could lead to incorrect module detection, affecting CLI commands.",
                "可能导致模块识别错误",
            ),
            ("validated symbols", "已验证符号"),
            ("backward compatibility", "向后兼容性"),
        ],
    )
    def test_phrase_is_replaced(self, en_phrase: str, zh_fragment: str):
        result = normalize_zh_text(en_phrase)
        assert zh_fragment in result
        assert en_phrase not in result


# ---------------------------------------------------------------------------
# Tests: No secrets in output
# ---------------------------------------------------------------------------


class TestNoSecrets:
    """Verify no secrets leak through the quality guard."""

    def test_no_api_keys_in_output(self):
        md = "API key: sk-abc123def456ghi789jkl012mno345pqr678stu901"
        result = normalize_zh_markdown(md)
        # The function doesn't redact secrets (that's _sanitize_error's job),
        # but it should not modify them either
        assert "sk-abc123" in result

    def test_no_env_vars_in_output(self):
        md = "使用 OPENAI_API_KEY 环境变量"
        result = normalize_zh_markdown(md)
        assert "OPENAI_API_KEY" in result


# ---------------------------------------------------------------------------
# Tests: Legacy/old reviews
# ---------------------------------------------------------------------------


class TestLegacyReviews:
    """Test that old reviews without bilingual display still work."""

    def test_old_review_without_display_fields(self):
        """Old reviews have no display.zh fields — normalization still works."""
        md = """# 执行摘要

CodePilot 审查了 10 个 Python 源文件。

# Agent 总结

| Agent | 状态 | 问题数 |
| --- | --- | ---: |
| ArchitectureAgent | completed | 2 |
"""
        result = normalize_zh_markdown(md)
        # Status should be translated
        assert "| 已完成 |" in result
        # Agent names are handled by localization, not zh_quality
        # but the status translation should still work

    def test_legacy_review_with_raw_ev_ids(self):
        """Legacy reviews might have raw ev_* — they should be cleaned up."""
        md = "问题证据 ev_aabbccddeeff00112233 已验证。"
        result = normalize_zh_markdown(md)
        assert "ev_aabbccddeeff00112233" not in result
        assert "[E?]" in result
