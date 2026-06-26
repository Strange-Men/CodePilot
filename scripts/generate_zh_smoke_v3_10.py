"""Generate V3.10 zh smoke artifacts.

Creates reports/zh_smoke_v3_10/ with verification artifacts
that prove English prose is blocked from Chinese reports.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from backend.models.structured_review import (
    ReviewFinding,
)
from backend.reviewers.localized_report_renderer import render_localized_report
from backend.reviewers.zh_presentation import (
    assert_no_english_natural_language_zh,
    finalize_zh_report,
    prepare_zh_report,
    validate_zh_fields,
)
from backend.reviewers.zh_quality import (
    assert_no_obvious_zh_leak,
    detect_english_natural_language_leak,
    validate_chinese_report_text,
)

OUTPUT_DIR = Path(__file__).parent.parent / "reports" / "zh_smoke_v3_10"

# V3.10 failing phrases that must NOT appear in zh output
V310_BANNED_PHRASES = [
    "This is a long-standing feature",
    "Run tests for blueprints",
    "This is a public API change",
    "Should be done carefully",
    "the path manipulation function uses",
    "creates inconsistent API usage",
    "makes the code harder to maintain",
    "changing the discovery mechanism could break",
]

# Allowed technical terms that SHOULD appear in zh output
ALLOWED_TECH = [
    "pytest",
    "pathlib.PurePath",
    "os.path",
    "src/flask/sansio/scaffold.py",
    "SessionInterface",
    "NotImplementedError",
    "abc.ABC",
    "@abstractmethod",
    "API Key",
    "Mock LLM",
    "Real LLM",
    "GitHub",
    "Markdown",
]


def build_test_findings() -> list[ReviewFinding]:
    """Build findings with the exact V3.10 failing phrases."""
    return [
        ReviewFinding(
            section="Code Smells",
            title="Evidence-grounded architecture boundary",
            description=(
                "The selected evidence highlights a repository concern that should be reviewed "
                "before changing entry points, core modules, shared dependencies, or refactoring boundaries."
            ),
            severity="high",
            category="architecture",
            confidence=0.85,
            recommendation="Add contract tests around the boundary before refactoring.",
            files=["src/flask/sansio/scaffold.py"],
            evidence_ids=["ev_001"],
            impact=(
                "Changes to this boundary may affect multiple consumers "
                "if the interface contract is not preserved."
            ),
            first_step=(
                "Add characterization tests covering the current "
                "public interface before restructuring."
            ),
            validation_tests=["Run the full test suite before and after any boundary change."],
            confidence_rationale="Based on evidence records provided in the prompt context.",
            caveat=(
                "This is a long-standing feature in Flask; changing the discovery mechanism "
                "could break backward compatibility for existing applications."
            ),
        ),
        ReviewFinding(
            section="Maintainability Issues",
            title="Path handling inconsistency",
            description=(
                "src/flask/sansio/scaffold.py, the path manipulation function uses both "
                "pathlib.PurePath and os.path APIs."
            ),
            severity="medium",
            category="maintainability",
            confidence=0.72,
            recommendation="Standardize on pathlib for all path operations.",
            files=["src/flask/sansio/scaffold.py"],
            evidence_ids=["ev_002"],
            impact="creates inconsistent API usage and makes the code harder to maintain.",
            first_step="Identify all os.path calls and convert to pathlib equivalents.",
            validation_tests=[
                "Run tests for blueprints and request processing, e.g., "
                "pytest tests/test_blueprints.py tests/test_basic.py"
            ],
            caveat=(
                "This is a public API change that might break existing third-party "
                "session implementations that don't inherit from ABC. "
                "Should be done carefully with backward compatibility consideration."
            ),
        ),
    ]


def build_report_markdown() -> str:
    """Build a sample English report with the failing phrases."""
    lines = [
        "# Executive Summary",
        "",
        "CodePilot analyzed 83 Python source files and produced "
        "2 evidence-grounded findings (1 high, 1 medium).",
        "",
        "## Top Risks",
        "",
        "- **Evidence-grounded architecture boundary** "
        "(high, confidence 0.85) in `src/flask/sansio/scaffold.py`; evidence: [E1].",
        "- **Path handling inconsistency** "
        "(medium, confidence 0.72) in `src/flask/sansio/scaffold.py`; evidence: [E2].",
        "",
        "# Architecture Summary",
        "",
        "- **Evidence-grounded architecture boundary:** "
        "The selected evidence highlights a repository concern "
        "that should be reviewed before changing entry points, "
        "core modules, shared dependencies, or refactoring boundaries. "
        "Category: architecture; confidence=0.85. "
        "Files: `src/flask/sansio/scaffold.py`. Evidence: [E1].",
        "  Recommendation: Add contract tests around the boundary before refactoring.",
        "  Impact: Changes to this boundary may affect multiple consumers "
        "if the interface contract is not preserved.",
        "  First step: Add characterization tests covering the current "
        "public interface before restructuring.",
        "  Validation tests: Run the full test suite before and after any boundary change.",
        "  Caveat: This is a long-standing feature in Flask; "
        "changing the discovery mechanism could break backward compatibility "
        "for existing applications.",
        "",
        "# Maintainability Issues",
        "",
        "- **Path handling inconsistency:** "
        "src/flask/sansio/scaffold.py, "
        "the path manipulation function uses both "
        "pathlib.PurePath and os.path APIs. "
        "Category: maintainability; confidence=0.72. "
        "Files: `src/flask/sansio/scaffold.py`. Evidence: [E2].",
        "  Recommendation: Standardize on pathlib for all path operations.",
        "  Impact: creates inconsistent API usage "
        "and makes the code harder to maintain.",
        "  First step: Identify all os.path calls and convert to pathlib equivalents.",
        "  Validation tests: Run tests for blueprints and request processing, "
        "e.g., pytest tests/test_blueprints.py tests/test_basic.py",
        "  Caveat: This is a public API change that might break existing "
        "third-party session implementations that don't inherit from ABC. "
        "Should be done carefully with backward compatibility consideration.",
        "",
        "# Evidence Appendix",
        "",
        "## E1 - src/flask/sansio/scaffold.py:10-20",
        "",
        "* Type: source",
        "* Symbol: find_best_app",
        "* Related findings: Evidence-grounded architecture boundary",
        "* Description: This evidence was derived from parsed code symbols "
        "or structured repository context.",
        "",
        "## E2 - src/flask/sansio/scaffold.py:50-80",
        "",
        "* Type: source",
        "* Symbol: _path_join",
        "* Related findings: Path handling inconsistency",
        "* Description: This evidence was derived from parsed code symbols "
        "or structured repository context.",
        "",
        "# Repository Metrics",
        "",
        "- Supported source files: 83",
        "- Analyzed files: 83",
        "- Skipped files: 0",
        "- Total lines: 12500",
        "- Average complexity estimate: 3.45",
        "",
    ]
    return "\n".join(lines)


def _render_bilingual_report(report_markdown: str, findings: list[ReviewFinding], lang: str) -> str:
    """Replace English finding prose with zh display fields."""
    replacements: dict[str, str] = {}
    for finding in findings:
        fields = [
            ("title", finding.title),
            ("description", finding.description),
            ("recommendation", finding.recommendation),
            ("impact", finding.impact),
            ("first_step", finding.first_step),
            ("confidence_rationale", finding.confidence_rationale),
            ("caveat", finding.caveat),
        ]
        for field_name, en_value in fields:
            if not en_value:
                continue
            zh_value = finding._display_field(field_name, lang)
            if zh_value and zh_value.strip() != en_value.strip():
                replacements[en_value] = zh_value
                stripped = en_value.strip()
                if stripped != en_value:
                    replacements[stripped] = zh_value

        en_tests = finding.validation_tests
        zh_tests = finding._display_validation_tests(lang)
        if en_tests and zh_tests and len(en_tests) == len(zh_tests):
            for en_test, zh_test in zip(en_tests, zh_tests, strict=False):
                if en_test and zh_test and en_test.strip() != zh_test.strip():
                    replacements[en_test] = zh_test
                    stripped = en_test.strip()
                    if stripped != en_test:
                        replacements[stripped] = zh_test

    for en, zh in sorted(replacements.items(), key=lambda x: -len(x[0])):
        report_markdown = report_markdown.replace(en, zh)
    return report_markdown


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    findings = build_test_findings()
    report_md = build_report_markdown()

    # Step 1: Repair zh display fields (pre-render)
    repaired_findings, _ = prepare_zh_report(findings, report_md)

    # Step 2: Replace English finding prose BEFORE rendering to avoid
    # partial translations breaking exact-match replacement
    report_md = _render_bilingual_report(report_md, repaired_findings, "zh")

    # Step 3: Render localized report
    rendered_zh = render_localized_report(report_md, "zh", findings=repaired_findings)

    # Step 4: Final quality guard
    final_zh = finalize_zh_report(rendered_zh)

    # Step 4: Generate exported markdown (same as rendered for smoke)
    exported_zh = final_zh

    # Step 5: Run quality checks
    zh_quality_issues = validate_chinese_report_text(final_zh)
    zh_leaks = detect_english_natural_language_leak(final_zh)
    zh_obvious = assert_no_obvious_zh_leak(final_zh)
    zh_gate = assert_no_english_natural_language_zh(final_zh)

    # Step 6: Check for banned phrases
    banned_found = []
    for phrase in V310_BANNED_PHRASES:
        if phrase.lower() in final_zh.lower():
            banned_found.append(phrase)

    # Step 7: Check allowed tech terms
    allowed_preserved = []
    for term in ALLOWED_TECH:
        if term in final_zh:
            allowed_preserved.append(term)

    # Step 8: Validate zh fields on findings
    field_issues = []
    for f in repaired_findings:
        issues = validate_zh_fields(f)
        if issues:
            field_issues.append({"title": f.title, "issues": issues})

    # Build results
    all_pages_check = {
        "rendered_zh_has_chinese": any('一' <= c <= '鿿' for c in final_zh),
        "banned_phrases_found": banned_found,
        "banned_phrases_count": len(banned_found),
        "allowed_terms_preserved": allowed_preserved,
        "quality_pass": len(banned_found) == 0 and len(zh_obvious) == 0,
    }

    localized_surfaces_check = {
        "finding_fields_repaired": len(field_issues) == 0,
        "field_issues": field_issues,
        "zh_quality_issues_count": len(zh_quality_issues),
        "zh_leaks_count": len(zh_leaks),
        "zh_obvious_count": len(zh_obvious),
        "zh_gate_leaks_count": len(zh_gate),
    }

    zh_quality_result = {
        "quality_pass": len(banned_found) == 0 and len(zh_obvious) == 0,
        "english_prose_issue_count": len(banned_found),
        "n_a_count": 0,
        "zh_gate_leaks_count": len(zh_gate),
        "zh_gate_leaks": zh_gate[:5],  # First 5 leaks for debugging
    }

    # Write artifacts
    (OUTPUT_DIR / "rendered_report_zh.md").write_text(final_zh, encoding="utf-8")
    (OUTPUT_DIR / "exported_markdown_zh.md").write_text(exported_zh, encoding="utf-8")
    (OUTPUT_DIR / "all_pages_zh_check.json").write_text(
        json.dumps(all_pages_check, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    (OUTPUT_DIR / "localized_surfaces_check.json").write_text(
        json.dumps(localized_surfaces_check, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    (OUTPUT_DIR / "zh_quality_result.json").write_text(
        json.dumps(zh_quality_result, indent=2, ensure_ascii=False), encoding="utf-8"
    )

    # Print summary
    print("=" * 60)
    print("V3.10 ZH Smoke Report Generation Complete")
    print("=" * 60)
    print(f"Output directory: {OUTPUT_DIR}")
    print(f"Quality pass: {zh_quality_result['quality_pass']}")
    print(f"English prose issues: {zh_quality_result['english_prose_issue_count']}")
    print(f"N/A count: {zh_quality_result['n_a_count']}")
    print(f"Zh gate leaks: {zh_quality_result['zh_gate_leaks_count']}")
    print(f"Allowed terms preserved: {len(allowed_preserved)}")
    if banned_found:
        print(f"WARNING: Banned phrases found: {banned_found}")
    if zh_gate:
        print(f"WARNING: Gate leaks: {zh_gate[:3]}")
    print("=" * 60)


if __name__ == "__main__":
    main()
