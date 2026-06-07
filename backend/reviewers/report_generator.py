from __future__ import annotations

from pathlib import Path

from backend.core.report_contract import REPORT_SECTIONS, numbered_report_section_lines
from backend.llm.client import LLMClient
from backend.models.review import RepositoryContext


class ReportGenerator:
    def __init__(self, llm_client: LLMClient, reports_path: Path, prompt_token_budget: int) -> None:
        self.llm_client = llm_client
        self.reports_path = reports_path
        self.prompt_token_budget = prompt_token_budget

    def generate(self, task_id: str, context: RepositoryContext) -> tuple[str, Path]:
        prompt = self._build_prompt(context)
        raw_report = self.llm_client.generate_review(prompt)
        report = self._normalize_report(raw_report)
        export_path = self.reports_path / f"{task_id}.md"
        export_path.write_text(report, encoding="utf-8")
        return report, export_path

    def _build_prompt(self, context: RepositoryContext) -> str:
        lines = [
            "Review this repository using only summarized repository context.",
            "Do not assume access to raw source code.",
            "Return markdown with exactly four top-level sections:",
            *numbered_report_section_lines(),
            f"Repository URL: {context.repo_url}",
            f"Repository language: {context.language}",
            f"Total source files: {context.total_python_files}",
            f"Analyzed files: {context.analyzed_files}",
            f"Skipped files: {context.skipped_files}",
            f"Repository summary: {context.repository_summary}",
            "File summaries:",
        ]
        for summary in context.file_summaries:
            lines.append(f"- {summary.summary}")

        prompt = "\n".join(lines)
        words = prompt.split()
        max_words = int(self.prompt_token_budget * 0.75)
        if len(words) > max_words:
            prompt = " ".join(words[:max_words])
        return prompt

    def _normalize_report(self, report: str) -> str:
        sections = self._extract_sections(report)
        output: list[str] = []
        for section in REPORT_SECTIONS:
            body = sections.get(section) or "No critical findings detected from the available repository summaries."
            output.append(f"# {section}\n{body.strip()}")
        return "\n\n".join(output) + "\n"

    @staticmethod
    def _extract_sections(report: str) -> dict[str, str]:
        current: str | None = None
        sections: dict[str, list[str]] = {}
        aliases = {section.lower(): section for section in REPORT_SECTIONS}

        for raw_line in report.splitlines():
            stripped = raw_line.strip()
            heading = stripped.lstrip("#").strip()
            heading_key = heading.lower()
            if heading_key in aliases:
                current = aliases[heading_key]
                sections.setdefault(current, [])
                continue
            if stripped.startswith("#"):
                continue
            if current:
                sections[current].append(raw_line)

        if not sections and report.strip():
            sections["Architecture Summary"] = [report.strip()]
        return {key: "\n".join(value).strip() for key, value in sections.items()}
