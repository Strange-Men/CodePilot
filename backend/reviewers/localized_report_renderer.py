"""Localized report rendering for CodePilot.

Takes a canonical English report and re-renders it for the target language
by translating headings, labels, prose sentences, and finding prose.
Agent analysis content is preserved unchanged — only display prose is localized.
"""

from __future__ import annotations

from backend.reviewers.localization import (
    Language,
    translate_finding_labels,
    translate_report_headings,
    translate_report_labels,
    translate_report_prose,
)


def render_localized_report(report_markdown: str, lang: Language) -> str:
    """Render a localized version of the report markdown.

    For English, returns the original report unchanged.
    For Chinese, translates headings, bold labels, and known prose sentences
    while preserving all finding content, evidence IDs, file paths, and data fields.

    Args:
        report_markdown: The canonical English report markdown.
        lang: Target language ('en' or 'zh').

    Returns:
        The localized report markdown.
    """
    if lang != "zh":
        return report_markdown

    # Step 1: Translate section headings
    translated = translate_report_headings(report_markdown, lang)

    # Step 2: Translate bold labels within body text
    translated = translate_report_labels(translated, lang)

    # Step 3: Replace known English prose sentences with Chinese equivalents
    translated = translate_report_prose(translated, lang)

    # Step 4: Translate agent display names in headings and table cells
    translated = _translate_agent_names(translated, lang)

    return translated


def render_localized_report_with_prose(
    report_markdown: str,
    localized_findings: list[dict],
    lang: Language,
) -> str:
    """Render a localized report with natural Chinese finding prose.

    Translates headings, labels, and known prose sentences, then replaces
    English finding prose (title, description, recommendation, impact, etc.)
    with localized versions from the localized findings data.

    Code identifiers, file paths, evidence IDs, severity, and confidence
    are preserved unchanged.

    Args:
        report_markdown: The canonical English report markdown.
        localized_findings: Findings with *_zh keys merged in.
        lang: Target language ('en' or 'zh').

    Returns:
        The localized report markdown with natural Chinese prose.
    """
    if lang != "zh":
        return report_markdown

    # Step 1: Translate section headings and labels
    translated = translate_report_headings(report_markdown, lang)
    translated = translate_report_labels(translated, lang)

    # Step 2: Replace known English prose sentences
    translated = translate_report_prose(translated, lang)

    # Step 3: Translate agent display names
    translated = _translate_agent_names(translated, lang)

    # Step 4: Build replacement map from localized findings
    replacements: dict[str, str] = {}
    for finding in localized_findings:
        for key, value in finding.items():
            if not key.endswith("_zh"):
                continue
            en_key = key.removesuffix("_zh")
            en_value = finding.get(en_key)
            if (
                en_value
                and value
                and isinstance(en_value, str)
                and isinstance(value, str)
                and en_value != value
            ):
                replacements[en_value] = value

        # Handle validation_tests (list of strings)
        en_tests = finding.get("validation_tests") or []
        zh_tests = finding.get("validation_tests_zh") or []
        if isinstance(en_tests, list) and isinstance(zh_tests, list):
            for en_test, zh_test in zip(en_tests, zh_tests, strict=False):
                if (
                    en_test
                    and zh_test
                    and isinstance(en_test, str)
                    and isinstance(zh_test, str)
                    and en_test != zh_test
                ):
                    replacements[en_test] = zh_test

    # Step 5: Apply replacements (longest first to avoid partial matches)
    for en, zh in sorted(replacements.items(), key=lambda x: -len(x[0])):
        translated = translated.replace(en, zh)

    return translated


def render_localized_finding_text(text: str | None, lang: Language) -> str | None:
    """Render localized text for a single finding field.

    Translates bold label prefixes while preserving the English content.
    Returns None if input is None.
    """
    return translate_finding_labels(text, lang)


def _translate_agent_names(report_markdown: str, lang: Language) -> str:
    """Replace agent IDs with localized display names in report text.

    Only replaces standalone occurrences (as headings or table cells),
    not partial matches inside other words.
    """
    if lang != "zh":
        return report_markdown
    result = report_markdown
    for agent_id, display_name in _AGENT_DISPLAY_NAMES.items():
        # Replace in headings: "## ArchitectureAgent" -> "## 架构分析 Agent"
        result = result.replace(f"## {agent_id}", f"## {display_name}")
        # Replace in table cells: "| ArchitectureAgent |" -> "| 架构分析 Agent |"
        result = result.replace(f"| {agent_id} ", f"| {display_name} ")
        result = result.replace(f"| {agent_id}|", f"| {display_name}|")
    return result


_AGENT_DISPLAY_NAMES: dict[str, str] = {
    "ArchitectureAgent": "架构分析 Agent",
    "CodeSmellAgent": "代码质量 Agent",
    "MaintainabilityAgent": "可维护性 Agent",
    "RefactorAgent": "重构建议 Agent",
}
