"""Localization support for CodePilot review reports.

Provides deterministic Chinese translations for report headings and labels.
Agent analysis remains English/canonical — this module only translates
structural elements (headings, bold labels) for display and export.
"""

from __future__ import annotations

import re
from typing import Literal

Language = Literal["en", "zh"]

VALID_LANGUAGES: set[str] = {"en", "zh"}

REPORT_HEADING_TRANSLATIONS: dict[str, str] = {
    "Executive Summary": "执行摘要",
    "Top Risks": "主要风险",
    "What This Repository Is": "仓库概览",
    "How It Works": "工作方式",
    "Key Architecture Map": "架构地图",
    "Cycle Groups": "循环依赖组",
    "Agent Summary": "Agent 总结",
    "Agent Findings": "Agent 问题发现",
    "Architecture Summary": "架构总结",
    "Code Smells": "代码坏味道",
    "Maintainability Issues": "可维护性问题",
    "Refactoring Suggestions": "重构建议",
    "Action Plan": "行动计划",
    "Evidence Appendix": "证据附录",
    "Repository Metrics": "仓库指标",
    "Diff Review Scope": "差异审查范围",
}

LABEL_TRANSLATIONS: dict[str, str] = {
    "**Type:**": "**类型：**",
    "**Primary components:**": "**主要组件：**",
    "**Scope analyzed:**": "**分析范围：**",
    "**Repository summary:**": "**仓库摘要：**",
    "**Why it matters:**": "**为什么重要：**",
    "**Where:**": "**位置：**",
    "**Likely responsibility area:**": "**可能的责任区域：**",
    "**First step:**": "**第一步：**",
    "**Change risk:**": "**变更风险：**",
    "**Evidence:**": "**证据：**",
    "**Validation tests:**": "**验证测试：**",
    "**Caveat:**": "**注意事项：**",
}

# Reverse mapping for headings that appear in Chinese reports
# (used by frontend parseReport to recognize Chinese headings)
CHINESE_TO_ENGLISH_HEADINGS: dict[str, str] = {
    zh: en for en, zh in REPORT_HEADING_TRANSLATIONS.items()
}


def normalize_language(lang: str | None) -> Language:
    """Normalize a language string to 'en' or 'zh'.

    Returns 'en' for None, empty string, or any unrecognized value.
    """
    if lang and lang.strip().lower() in VALID_LANGUAGES:
        return lang.strip().lower()  # type: ignore[return-value]
    return "en"


def translate_report_heading(heading: str) -> str:
    """Translate a single report heading to Chinese if a mapping exists.

    Returns the original heading if no translation is available.
    """
    return REPORT_HEADING_TRANSLATIONS.get(heading, heading)


def translate_report_headings(report_markdown: str, lang: Language) -> str:
    """Replace Markdown headings with Chinese equivalents.

    Only modifies top-level (# ) and second-level (## ) headings that
    match known English report section titles. Content below headings
    is preserved unchanged.
    """
    if lang != "zh":
        return report_markdown

    lines = report_markdown.split("\n")
    translated: list[str] = []
    for line in lines:
        match = re.match(r"^(#{1,2})\s+(.+)$", line)
        if match:
            prefix = match.group(1)
            heading_text = match.group(2).strip()
            zh_heading = REPORT_HEADING_TRANSLATIONS.get(heading_text, heading_text)
            translated.append(f"{prefix} {zh_heading}")
        else:
            translated.append(line)
    return "\n".join(translated)


def translate_finding_labels(text: str | None, lang: Language) -> str | None:
    """Translate bold labels within finding text to Chinese.

    Only translates label prefixes like '**Why it matters:**' — the
    content after the label remains in English (canonical agent output).
    Returns None if input is None.
    """
    if lang != "zh" or text is None:
        return text
    result = text
    for en_label, zh_label in LABEL_TRANSLATIONS.items():
        result = result.replace(en_label, zh_label)
    return result


def translate_report_labels(report_markdown: str, lang: Language) -> str:
    """Translate bold labels within report body text to Chinese."""
    if lang != "zh":
        return report_markdown
    result = report_markdown
    for en_label, zh_label in LABEL_TRANSLATIONS.items():
        result = result.replace(en_label, zh_label)
    return result
