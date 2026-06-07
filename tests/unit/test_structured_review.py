from backend.models.structured_review import ReviewFinding, StructuredReviewDraft
from backend.reviewers.markdown_adapter import MarkdownReviewAdapter


def test_markdown_adapter_parses_contract_sections_into_findings() -> None:
    draft = MarkdownReviewAdapter().parse(
        "# Architecture Summary\nArchitecture.\n\n"
        "# Code Smells\nSmell one.\n\n"
        "# Refactoring Suggestions\nRefactor."
    )

    assert [finding.section for finding in draft.findings] == [
        "Architecture Summary",
        "Code Smells",
        "Refactoring Suggestions",
    ]
    assert draft.section_markdown("Code Smells") == "Smell one."


def test_structured_finding_renders_future_facing_metadata() -> None:
    finding = ReviewFinding(
        section="Code Smells",
        title="Large service boundary",
        description="The module coordinates unrelated workflows.",
        severity="medium",
        files=["services/review.py"],
        recommendation="Extract a focused orchestration service.",
    )

    markdown = finding.to_markdown()

    assert "**Large service boundary:**" in markdown
    assert "`services/review.py`" in markdown
    assert "Recommendation: Extract a focused orchestration service." in markdown


def test_adapter_renders_structured_draft_with_unchanged_contract_order() -> None:
    draft = StructuredReviewDraft(
        findings=[
            ReviewFinding(section="Refactoring Suggestions", description="Refactor."),
            ReviewFinding(section="Architecture Summary", description="Architecture."),
        ]
    )

    report = MarkdownReviewAdapter().render(draft)

    assert report.index("# Architecture Summary") < report.index("# Code Smells")
    assert report.index("# Code Smells") < report.index("# Maintainability Issues")
    assert report.index("# Maintainability Issues") < report.index("# Refactoring Suggestions")
    assert report.count("No critical findings detected") == 2
    assert report.endswith("\n")


def test_markdown_round_trip_preserves_normalized_report(sample_context) -> None:
    adapter = MarkdownReviewAdapter()
    raw = (
        "# Architecture Summary\nArchitecture.\n\n"
        "# Code Smells\nSmells.\n\n"
        "# Maintainability Issues\nMaintainability.\n\n"
        "# Refactoring Suggestions\nRefactor."
    )

    report = adapter.normalize(raw, sample_context)
    round_tripped = adapter.render(adapter.parse(report), sample_context)

    assert round_tripped == report


def test_adapter_accepts_nested_review_context(sample_context) -> None:
    adapter = MarkdownReviewAdapter()

    legacy = adapter.normalize("Unstructured reviewer note.", sample_context)
    nested = adapter.normalize("Unstructured reviewer note.", sample_context.to_review_context())

    assert nested == legacy
