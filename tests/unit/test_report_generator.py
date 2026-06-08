from __future__ import annotations

from pathlib import Path

from backend.core.report_contract import load_report_sections
from backend.llm.client import REPORT_SECTIONS, MockLLMClient
from backend.models.review import CodeFileSummary
from backend.prompts import PromptRenderer
from backend.reviewers.report_generator import ReportGenerator


class StaticLLM:
    def __init__(self, response: str) -> None:
        self.response = response
        self.prompts: list[str] = []

    def generate_review(self, prompt: str) -> str:
        self.prompts.append(prompt)
        return self.response


def assert_report_shape(report: str) -> None:
    for section in REPORT_SECTIONS:
        assert f"# {section}" in report


def test_valid_report_generation_writes_markdown(tmp_path: Path, sample_context) -> None:
    llm = StaticLLM(
        "# Architecture Summary\nGood structure.\n\n"
        "# Code Smells\nFew smells.\n\n"
        "# Maintainability Issues\nLow risk.\n\n"
        "# Refactoring Suggestions\nKeep tests small.\n"
    )

    result = ReportGenerator(llm, tmp_path, 5000).generate("task-1", sample_context)

    assert_report_shape(result.report)
    assert result.export_path == tmp_path / "task-1.md"
    assert result.export_path.read_text(encoding="utf-8") == result.report
    assert "# Repository Metrics" in result.report
    assert "# Repository Insights" in result.report


def test_mock_mode_generates_required_sections(sample_context) -> None:
    prompt = ReportGenerator(MockLLMClient(), Path("."), 5000)._build_prompt(sample_context)
    report = MockLLMClient().generate_review(prompt)

    assert_report_shape(report)
    assert "Python application" in report
    assert "Entry points are app.py" in report
    assert "Core modules are services/review.py" in report
    assert "1 resolved internal relationships" in report
    assert "High fan-in hubs are services/review.py (fan_in=1)" in report


def test_malformed_llm_response_is_normalized(tmp_path: Path, sample_context) -> None:
    result = ReportGenerator(StaticLLM("Unstructured reviewer note."), tmp_path, 5000).generate(
        "task-1",
        sample_context,
    )

    assert_report_shape(result.report)
    assert "Unstructured reviewer note." in result.report


def test_missing_sections_receive_default_content(tmp_path: Path, sample_context) -> None:
    result = ReportGenerator(
        StaticLLM("# Architecture Summary\nOnly one section."),
        tmp_path,
        5000,
    ).generate("task-1", sample_context)

    assert_report_shape(result.report)
    assert "Only one section." in result.report
    assert result.report.count("No critical findings detected") == 3


def test_extra_sections_are_not_preserved(tmp_path: Path, sample_context) -> None:
    result = ReportGenerator(
        StaticLLM(
            "# Architecture Summary\nArchitecture.\n\n"
            "# Security Review\nNot part of V1 report.\n\n"
            "# Code Smells\nSmells.\n",
        ),
        tmp_path,
        5000,
    ).generate("task-1", sample_context)

    assert_report_shape(result.report)
    assert "Security Review" not in result.report


def test_prompt_budget_trims_large_context(tmp_path: Path, sample_context) -> None:
    sample_context.file_summaries[0].summary = "word " * 100
    full_prompt = ReportGenerator(StaticLLM(""), tmp_path, prompt_token_budget=5000)._build_prompt(sample_context)

    prompt = ReportGenerator(StaticLLM(""), tmp_path, prompt_token_budget=20)._build_prompt(sample_context)

    generator = ReportGenerator(StaticLLM(""), tmp_path, prompt_token_budget=20)
    assert generator._count_prompt_tokens(prompt) <= 20
    assert "\n" in prompt
    assert all(line in full_prompt.splitlines() for line in prompt.splitlines())


def test_prompt_budget_preserves_complete_prompt_when_it_fits(tmp_path: Path, sample_context) -> None:
    generator = ReportGenerator(StaticLLM(""), tmp_path, prompt_token_budget=5000)

    prompt = generator._build_prompt(sample_context)

    assert "services/review.py: purpose=Implements review behavior; classes=none; functions=review." in prompt
    assert prompt.endswith("Configuration:\n- None detected.")
    assert "\nRepository Summary:\n" in prompt


def test_prompt_groups_files_and_only_details_top_ten(tmp_path: Path, sample_context) -> None:
    sample_context.file_summaries = [
        CodeFileSummary(
            path=f"file-{index:02}.py",
            purpose="Test file.",
            summary=f"detail-{index}",
            line_count=index,
            complexity_estimate=index,
            importance_score=float(index),
            importance_label="Low",
            file_role=(
                "Entry Point"
                if index == 20
                else "Core Module"
                if index >= 18
                else "Supporting File"
            ),
        )
        for index in range(21)
    ]

    prompt = ReportGenerator(StaticLLM(""), tmp_path, 5000)._build_prompt(sample_context)

    assert "Repository Summary:" in prompt
    assert "Total lines: 150" in prompt
    assert "Average complexity: 6.50" in prompt
    assert "Entry Points:" in prompt
    assert "Core Modules:" in prompt
    assert "Supporting Modules:" in prompt
    assert "Architecture Graph:" in prompt
    assert "Important Dependency Relationships:" in prompt
    assert "- Hub Files:" in prompt
    assert "- Circular Dependencies:" in prompt
    assert "- Orphans:" in prompt
    assert prompt.count("| score=") == 10
    assert "detail-20" in prompt
    assert "detail-11" in prompt
    assert "detail-10" not in prompt
    assert "file-00.py [0.00 Low]" in prompt
    assert prompt.index("file-20.py") < prompt.index("file-19.py")


def test_prompt_includes_dependency_edges_and_analysis_guidance(tmp_path: Path, sample_context) -> None:
    prompt = ReportGenerator(StaticLLM(""), tmp_path, 5000)._build_prompt(sample_context)

    assert "Architecture Summary requirements:" in prompt
    assert "- Entry Points: app.py" in prompt
    assert "- Core Modules: services/review.py" in prompt
    assert "- Dependency Structure: 1 resolved internal relationships, 1 hubs, and 0 cycles" in prompt
    assert "- app.py -> services/review.py" in prompt
    assert "Hub Analysis Guidance: inspect high fan-in modules" in prompt
    assert "Cycle Analysis Guidance: explain ownership and initialization risks" in prompt


def test_dependency_relationships_prioritize_important_files(sample_context) -> None:
    sample_context.file_summaries.append(
        CodeFileSummary(
            path="helpers/format.py",
            purpose="Formats output.",
            summary="Formatting helper.",
            importance_score=10.0,
        )
    )
    sample_context.dependency_edges = {
        "app.py": ["helpers/format.py", "services/review.py"],
        "services/review.py": ["helpers/format.py"],
        "helpers/format.py": [],
    }

    relationships = PromptRenderer.important_dependency_relationships(sample_context, limit=2)

    assert relationships == [
        ("app.py", "services/review.py"),
        ("app.py", "helpers/format.py"),
    ]


def test_repository_metrics_are_appended_after_contract_sections(tmp_path: Path, sample_context) -> None:
    result = ReportGenerator(
        StaticLLM("# Architecture Summary\nArchitecture."),
        tmp_path,
        5000,
    ).generate("task-1", sample_context)

    report = result.report
    assert report.index("# Repository Metrics") > report.index("# Refactoring Suggestions")
    assert report.index("# Repository Insights") > report.index("# Refactoring Suggestions")
    assert report.index("# Repository Insights") < report.index("# Repository Metrics")
    assert "- Total lines: 150" in report
    assert "- Average complexity: 6.50" in report
    assert "## Top Files" in report
    assert "| File | Lines | Complexity | Score | Label |" in report
    assert "| app.py | 100 | 8 | 100.00 | Critical |" in report
    assert report.index("| app.py |") < report.index("| services/review.py |")
    assert report.index("# Architecture Graph") > report.index("# Repository Metrics")
    assert "- Resolved internal dependencies: 1" in report
    assert "## Important Relationships" in report
    assert "- `app.py` -> `services/review.py`" in report
    assert "| services/review.py | 1 | 0 | 80.06 |" in report


def test_section_order_is_stable(tmp_path: Path, sample_context) -> None:
    result = ReportGenerator(
        StaticLLM(
            "# Refactoring Suggestions\nRefactor.\n\n"
            "# Architecture Summary\nArchitecture.\n\n"
            "# Maintainability Issues\nMaintain.\n\n"
            "# Code Smells\nSmells.\n",
        ),
        tmp_path,
        5000,
    ).generate("task-1", sample_context)

    positions = [result.report.index(f"# {section}") for section in REPORT_SECTIONS]
    assert positions == sorted(positions)


def test_report_ends_with_newline(tmp_path: Path, sample_context) -> None:
    result = ReportGenerator(StaticLLM("Unstructured reviewer note."), tmp_path, 5000).generate(
        "task-1",
        sample_context,
    )

    assert result.report.endswith("\n")


def test_report_sections_are_loaded_from_shared_contract() -> None:
    assert REPORT_SECTIONS == [section.title for section in load_report_sections()]
