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


def test_structured_finding_accepts_useful_fields() -> None:
    finding = ReviewFinding(
        section="Code Smells",
        title="Duplicate dispatch logic",
        description="Two paths implement similar dispatch.",
        severity="medium",
        confidence=0.75,
        files=["app.py", "blueprint.py"],
        recommendation="Extract shared logic.",
        evidence_ids=["ev_abc123"],
        impact="Changes may need to be duplicated across both paths.",
        first_step="Add characterization tests before refactoring.",
        validation_tests=["tests/test_blueprints.py", "tests/test_basic.py"],
        confidence_rationale="Multiple evidence records confirm the pattern.",
        caveat="Mature public API; avoid breaking compatibility.",
    )

    assert finding.impact == "Changes may need to be duplicated across both paths."
    assert finding.first_step == "Add characterization tests before refactoring."
    assert finding.validation_tests == ["tests/test_blueprints.py", "tests/test_basic.py"]
    assert finding.confidence_rationale == "Multiple evidence records confirm the pattern."
    assert finding.caveat == "Mature public API; avoid breaking compatibility."


def test_structured_finding_useful_fields_render_in_markdown() -> None:
    finding = ReviewFinding(
        section="Code Smells",
        title="Duplicate dispatch logic",
        description="Two paths implement similar dispatch.",
        severity="medium",
        recommendation="Extract shared logic.",
        impact="Changes may need duplication.",
        first_step="Add tests first.",
        validation_tests=["tests/test_blueprints.py"],
        caveat="Public API compatibility required.",
    )

    markdown = finding.to_markdown()

    assert "Impact: Changes may need duplication." in markdown
    assert "First step: Add tests first." in markdown
    assert "Validation tests: tests/test_blueprints.py" in markdown
    assert "Caveat: Public API compatibility required." in markdown


def test_structured_finding_missing_useful_fields_render_cleanly() -> None:
    finding = ReviewFinding(
        section="Code Smells",
        title="Simple finding",
        description="A simple finding without useful fields.",
        severity="low",
    )

    markdown = finding.to_markdown()

    assert "Impact:" not in markdown
    assert "First step:" not in markdown
    assert "Validation tests:" not in markdown
    assert "Caveat:" not in markdown


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


def test_architecture_graph_compresses_long_cycle_groups(sample_context) -> None:
    sample_context.circular_dependencies = [[f"module_{index}.py" for index in range(9)]]

    section = MarkdownReviewAdapter.architecture_graph_section(sample_context.to_review_context())

    assert "Cycle group (9 modules):" in section
    assert "+3 more" in section
    assert "module_0.py -> module_1.py" not in section
