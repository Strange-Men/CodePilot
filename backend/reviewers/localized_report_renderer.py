"""Localized report rendering for CodePilot.

Takes a canonical English report and re-renders it for the target language
by translating headings, labels, prose sentences, and finding prose.
Agent analysis content is preserved unchanged — only display prose is localized.
"""

from __future__ import annotations

import re

from backend.models.structured_review import ReviewFinding
from backend.reviewers.constants import DEFAULT_SECTION_CONTENT, DEFAULT_SECTION_CONTENT_ZH
from backend.reviewers.evidence_display import EvidenceDisplayMap
from backend.reviewers.localization import (
    Language,
    translate_enum_values,
    translate_finding_labels,
    translate_report_headings,
    translate_report_labels,
    translate_report_prose,
)
from backend.reviewers.priority_layer import generate_priority_section
from backend.reviewers.zh_presentation import finalize_zh_report


def render_localized_report(
    report_markdown: str,
    lang: Language,
    findings: list[ReviewFinding] | None = None,
) -> str:
    """Render a localized version of the report markdown.

    For English, returns the original report unchanged.
    For Chinese, translates headings, bold labels, and known prose sentences
    while preserving all finding content, evidence IDs, file paths, and data fields.

    Args:
        report_markdown: The canonical English report markdown.
        lang: Target language ('en' or 'zh').
        findings: Optional ReviewFinding objects for priority section injection.

    Returns:
        The localized report markdown.
    """
    if lang != "zh":
        return report_markdown

    # Build evidence display map for E1/E2 refs
    display_map = EvidenceDisplayMap.from_findings(findings or [])

    # Step 1: Translate section headings
    translated = translate_report_headings(report_markdown, lang)

    # Step 2: Translate bold labels within body text
    translated = translate_report_labels(translated, lang)

    # Step 3: Replace known English prose sentences with Chinese equivalents
    translated = translate_report_prose(translated, lang)

    # Step 4: Translate agent display names in headings and table cells
    translated = _translate_agent_names(translated, lang)

    # Step 5: Translate enum values (severity, status, category)
    translated = translate_enum_values(translated, lang)

    # Step 6: Replace default section content with Chinese
    translated = translated.replace(DEFAULT_SECTION_CONTENT, DEFAULT_SECTION_CONTENT_ZH)

    # Step 7: Inject priority section after Executive Summary
    if findings:
        priority_section = generate_priority_section(findings, display_map)
        if priority_section:
            translated = _inject_after_heading(
                translated, "执行摘要", priority_section,
            )

    # Step 8: Strip backticks from Chinese natural language text
    translated = _fix_chinese_validation_backticks(translated)

    # Step 9: Replace raw ev_* IDs with [E1]/[E2] display refs
    translated = display_map.replace_in_text(translated)

    # Step 10: Final Chinese quality guard — metadata repair + normalize remaining English leakage
    translated = finalize_zh_report(translated)

    return translated


def render_localized_report_with_prose(
    report_markdown: str,
    localized_findings: list[dict],
    lang: Language,
    findings: list[ReviewFinding] | None = None,
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
        findings: Optional ReviewFinding objects for priority section injection.

    Returns:
        The localized report markdown with natural Chinese prose.
    """
    if lang != "zh":
        return report_markdown

    # Build evidence display map for E1/E2 refs
    display_map = EvidenceDisplayMap.from_findings(findings or [])

    # Step 1: Translate section headings and labels
    translated = translate_report_headings(report_markdown, lang)
    translated = translate_report_labels(translated, lang)

    # Step 2: Replace known English prose sentences
    translated = translate_report_prose(translated, lang)

    # Step 3: Translate agent display names
    translated = _translate_agent_names(translated, lang)

    # Step 3.5: Translate enum values (severity, status, category)
    translated = translate_enum_values(translated, lang)

    # Step 3.6: Replace default section content with Chinese
    translated = translated.replace(DEFAULT_SECTION_CONTENT, DEFAULT_SECTION_CONTENT_ZH)

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

    # Step 6: Inject priority section after Executive Summary
    if findings:
        priority_section = generate_priority_section(findings, display_map)
        if priority_section:
            translated = _inject_after_heading(
                translated, "执行摘要", priority_section,
            )

    # Step 7: Strip backticks from Chinese natural language validation text
    translated = _fix_chinese_validation_backticks(translated)

    # Step 8: Replace raw ev_* IDs with [E1]/[E2] display refs
    translated = display_map.replace_in_text(translated)

    # Step 9: Final Chinese quality guard — metadata repair + normalize remaining English leakage
    translated = finalize_zh_report(translated)

    return translated


def render_localized_finding_text(text: str | None, lang: Language) -> str | None:
    """Render localized text for a single finding field.

    Translates bold label prefixes while preserving the English content.
    Returns None if input is None.
    """
    return translate_finding_labels(text, lang)


def _inject_after_heading(report: str, heading_text: str, section: str) -> str:
    """Insert a new section after the block containing the given heading.

    Finds the heading by exact text match and inserts the section after
    the entire heading block (heading line + its content until the next heading).
    If the heading is not found, prepends the section at the top.
    """
    lines = report.split("\n")
    insert_idx = len(lines)  # default: append at end
    in_target_block = False

    for i, line in enumerate(lines):
        match = re.match(r"^#{1,2}\s+(.+)$", line)
        if match:
            current_heading = match.group(1).strip()
            if current_heading == heading_text:
                in_target_block = True
                continue
            elif in_target_block:
                # We've reached the next heading after the target block
                insert_idx = i
                break

    # Insert the priority section
    before = "\n".join(lines[:insert_idx])
    after = "\n".join(lines[insert_idx:])
    return f"{before}\n\n{section}\n\n{after}"


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

# Chinese characters that indicate natural language (not code/commands)
_ZH_CHAR_PATTERN = re.compile(r'[一-鿿]')


def _fix_chinese_validation_backticks(text: str) -> str:
    """Strip backticks from Chinese natural language validation text.

    Commands and file paths keep their backticks.
    Chinese text wrapped in backticks gets backticks removed.
    """
    def _replace_if_chinese(match: re.Match[str]) -> str:
        content = match.group(1)
        # If the backticked content contains Chinese characters, it's natural language
        if _ZH_CHAR_PATTERN.search(content):
            return content
        return match.group(0)

    # Match backticked text (non-greedy)
    return re.sub(r'`([^`]+)`', _replace_if_chinese, text)
