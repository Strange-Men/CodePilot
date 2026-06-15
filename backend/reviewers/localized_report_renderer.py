"""Localized report rendering for CodePilot.

Takes a canonical English report and re-renders it for the target language
by translating headings and labels. Agent analysis content is preserved
unchanged — only structural elements are localized.
"""

from __future__ import annotations

from backend.reviewers.localization import (
    Language,
    translate_finding_labels,
    translate_report_headings,
    translate_report_labels,
)


def render_localized_report(report_markdown: str, lang: Language) -> str:
    """Render a localized version of the report markdown.

    For English, returns the original report unchanged.
    For Chinese, translates headings and bold labels while preserving
    all finding content, evidence IDs, file paths, and data fields.

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

    return translated


def render_localized_finding_text(text: str | None, lang: Language) -> str | None:
    """Render localized text for a single finding field.

    Translates bold label prefixes while preserving the English content.
    Returns None if input is None.
    """
    return translate_finding_labels(text, lang)
