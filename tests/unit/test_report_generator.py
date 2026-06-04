from __future__ import annotations

from pathlib import Path

from backend.llm.client import REPORT_SECTIONS, MockLLMClient
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

    report, export_path = ReportGenerator(llm, tmp_path, 5000).generate("task-1", sample_context)

    assert_report_shape(report)
    assert export_path == tmp_path / "task-1.md"
    assert export_path.read_text(encoding="utf-8") == report


def test_mock_mode_generates_required_sections(sample_context) -> None:
    prompt = ReportGenerator(MockLLMClient(), Path("."), 5000)._build_prompt(sample_context)
    report = MockLLMClient().generate_review(prompt)

    assert_report_shape(report)


def test_malformed_llm_response_is_normalized(tmp_path: Path, sample_context) -> None:
    report, _ = ReportGenerator(StaticLLM("Unstructured reviewer note."), tmp_path, 5000).generate(
        "task-1",
        sample_context,
    )

    assert_report_shape(report)
    assert "Unstructured reviewer note." in report


def test_missing_sections_receive_default_content(tmp_path: Path, sample_context) -> None:
    report, _ = ReportGenerator(
        StaticLLM("# Architecture Summary\nOnly one section."),
        tmp_path,
        5000,
    ).generate("task-1", sample_context)

    assert_report_shape(report)
    assert "Only one section." in report
    assert report.count("No critical findings detected") == 3


def test_extra_sections_are_not_preserved(tmp_path: Path, sample_context) -> None:
    report, _ = ReportGenerator(
        StaticLLM(
            "# Architecture Summary\nArchitecture.\n\n"
            "# Security Review\nNot part of V1 report.\n\n"
            "# Code Smells\nSmells.\n",
        ),
        tmp_path,
        5000,
    ).generate("task-1", sample_context)

    assert_report_shape(report)
    assert "Security Review" not in report


def test_prompt_budget_trims_large_context(tmp_path: Path, sample_context) -> None:
    sample_context.file_summaries[0].summary = "word " * 100

    prompt = ReportGenerator(StaticLLM(""), tmp_path, prompt_token_budget=20)._build_prompt(sample_context)

    assert len(prompt.split()) <= 15


def test_section_order_is_stable(tmp_path: Path, sample_context) -> None:
    report, _ = ReportGenerator(
        StaticLLM(
            "# Refactoring Suggestions\nRefactor.\n\n"
            "# Architecture Summary\nArchitecture.\n\n"
            "# Maintainability Issues\nMaintain.\n\n"
            "# Code Smells\nSmells.\n",
        ),
        tmp_path,
        5000,
    ).generate("task-1", sample_context)

    positions = [report.index(f"# {section}") for section in REPORT_SECTIONS]
    assert positions == sorted(positions)


def test_report_ends_with_newline(tmp_path: Path, sample_context) -> None:
    report, _ = ReportGenerator(StaticLLM("Unstructured reviewer note."), tmp_path, 5000).generate(
        "task-1",
        sample_context,
    )

    assert report.endswith("\n")
