from __future__ import annotations

import re
from pathlib import Path

from backend.core.report_contract import REPORT_SECTIONS, numbered_report_section_lines
from backend.llm.client import LLMClient
from backend.models.review import CodeFileSummary, RepositoryContext


class ReportGenerator:
    def __init__(self, llm_client: LLMClient, reports_path: Path, prompt_token_budget: int) -> None:
        self.llm_client = llm_client
        self.reports_path = reports_path
        self.prompt_token_budget = prompt_token_budget

    def generate(self, task_id: str, context: RepositoryContext) -> tuple[str, Path]:
        prompt = self._build_prompt(context)
        raw_report = self.llm_client.generate_review(prompt)
        report = self._normalize_report(raw_report, context)
        export_path = self.reports_path / f"{task_id}.md"
        export_path.write_text(report, encoding="utf-8")
        return report, export_path

    def _build_prompt(self, context: RepositoryContext) -> str:
        lines = [
            "Review this repository using only summarized repository context.",
            "Do not assume access to raw source code.",
            "Return markdown with exactly four top-level sections:",
            *numbered_report_section_lines(),
            "Architecture Summary requirements:",
            "- Describe Entry Points, Core Modules, Supporting Modules, and Dependency Structure.",
            "- Explain how important dependency relationships shape control flow and change risk.",
            "- Use hub and cycle evidence in findings instead of listing file paths without interpretation.",
            "Repository Summary:",
            f"Repository URL: {context.repo_url}",
            f"Repository language: {context.language}",
            f"Total source files: {context.total_python_files}",
            f"Analyzed files: {context.analyzed_files}",
            f"Skipped files: {context.skipped_files}",
            f"Total lines: {context.total_lines}",
            f"Average complexity: {context.avg_complexity:.2f}",
            context.repository_summary,
            *self._architecture_summary_prompt(context),
            *self._architecture_graph_prompt(context),
        ]
        detailed_paths = {
            summary.path for summary in self._top_important_files(context, limit=10)
        }
        for roles, heading in (
            ({"Entry Point"}, "Entry Points"),
            ({"Core Module"}, "Core Modules"),
            ({"Supporting File", "Supporting Module"}, "Supporting Modules"),
            ({"Test File"}, "Test Files"),
            ({"Documentation"}, "Documentation"),
            ({"Configuration"}, "Configuration"),
        ):
            lines.extend(
                self._prompt_file_group(
                    heading,
                    [
                        summary
                        for summary in context.file_summaries
                        if summary.file_role in roles
                    ],
                    detailed_paths,
                )
            )

        return self._fit_to_token_budget("\n".join(lines))

    def _fit_to_token_budget(self, prompt: str) -> str:
        if self.prompt_token_budget <= 0:
            return ""
        selected_lines: list[str] = []
        used_tokens = 0
        for line in prompt.splitlines():
            line_tokens = len(re.findall(r"\w+|[^\w\s]", line))
            if used_tokens + line_tokens > self.prompt_token_budget:
                break
            selected_lines.append(line)
            used_tokens += line_tokens
        if selected_lines:
            return "\n".join(selected_lines)

        tokens = list(re.finditer(r"\w+|[^\w\s]", prompt))
        return prompt[: tokens[self.prompt_token_budget - 1].end()].rstrip()

    def _normalize_report(self, report: str, context: RepositoryContext | None = None) -> str:
        sections = self._extract_sections(report)
        output: list[str] = []
        for section in REPORT_SECTIONS:
            body = sections.get(section) or "No critical findings detected from the available repository summaries."
            output.append(f"# {section}\n{body.strip()}")
        if context is not None:
            output.append(self._repository_metrics_section(context))
            output.append(self._architecture_graph_section(context))
        return "\n\n".join(output) + "\n"

    def _repository_metrics_section(self, context: RepositoryContext) -> str:
        lines = [
            "# Repository Metrics",
            f"- Total source files: {context.total_python_files}",
            f"- Analyzed files: {context.analyzed_files}",
            f"- Skipped files: {context.skipped_files}",
            f"- Total lines: {context.total_lines}",
            f"- Average complexity: {context.avg_complexity:.2f}",
            "",
            "## Top Files",
            "",
            "| File | Lines | Complexity | Score | Label |",
            "| --- | ---: | ---: | ---: | --- |",
        ]
        top_files = self._top_important_files(context, limit=10)
        if top_files:
            for summary in top_files:
                path = summary.path.replace("|", r"\|")
                lines.append(
                    f"| {path} | {summary.line_count} | {summary.complexity_estimate} | "
                    f"{summary.importance_score:.2f} | {summary.importance_label} |"
                )
        else:
            lines.append("| No analyzed files | 0 | 0 | 0.00 | Peripheral |")
        return "\n".join(lines)

    @staticmethod
    def _architecture_summary_prompt(context: RepositoryContext) -> list[str]:
        supporting_modules = context.supporting_modules or [
            summary.path
            for summary in context.file_summaries
            if summary.file_role in {"Supporting File", "Supporting Module"}
        ]
        edge_count = sum(len(targets) for targets in context.dependency_edges.values())
        return [
            "Architecture Summary Context:",
            f"- Entry Points: {', '.join(context.entry_points) or 'None detected'}",
            f"- Core Modules: {', '.join(context.core_modules) or 'None detected'}",
            f"- Supporting Modules: {', '.join(supporting_modules) or 'None detected'}",
            (
                f"- Dependency Structure: {edge_count} resolved internal relationships, "
                f"{len(context.hub_files)} hubs, and {len(context.circular_dependencies)} cycles"
            ),
        ]

    @classmethod
    def _architecture_graph_prompt(cls, context: RepositoryContext) -> list[str]:
        summaries = {summary.path: summary for summary in context.file_summaries}
        hubs = ", ".join(
            f"{path} (fan_in={summaries[path].fan_in})"
            for path in context.hub_files
            if path in summaries
        ) or "None detected"
        cycles = "; ".join(
            " -> ".join([*cycle, cycle[0]])
            for cycle in context.circular_dependencies
            if cycle
        ) or "None detected"
        orphans = ", ".join(context.orphan_files) or "None detected"
        lines = [
            "Architecture Graph:",
            f"- Hub Files: {hubs}",
            f"- Circular Dependencies: {cycles}",
            f"- Orphans: {orphans}",
            "Important Dependency Relationships:",
        ]
        relationships = cls._important_dependency_relationships(context, limit=30)
        lines.extend(f"- {source} -> {target}" for source, target in relationships)
        if not relationships:
            lines.append("- None resolved.")
        lines.extend(
            [
                (
                    "Hub Analysis Guidance: inspect high fan-in modules for broad change impact, "
                    "unstable interfaces, and mixed responsibilities."
                ),
                (
                    "Cycle Analysis Guidance: explain ownership and initialization risks in each cycle, "
                    "then suggest the smallest dependency-breaking boundary."
                ),
            ]
        )
        return lines

    @staticmethod
    def _architecture_graph_section(context: RepositoryContext) -> str:
        summaries = {summary.path: summary for summary in context.file_summaries}
        edge_count = sum(len(targets) for targets in context.dependency_edges.values())
        lines = [
            "# Architecture Graph",
            f"- Analyzed nodes: {len(context.file_summaries)}",
            f"- Resolved internal dependencies: {edge_count}",
            "",
            "## Entry Points",
        ]
        lines.extend(
            f"- `{path}`" for path in context.entry_points
        )
        if not context.entry_points:
            lines.append("- None detected.")

        lines.extend(["", "## Important Relationships"])
        relationships = ReportGenerator._important_dependency_relationships(context, limit=30)
        if relationships:
            lines.extend(f"- `{source}` -> `{target}`" for source, target in relationships)
        else:
            lines.append("- None resolved.")

        lines.extend(
            [
                "",
                "## Hub Files",
                "",
                "| File | Fan In | Fan Out | Score |",
                "| --- | ---: | ---: | ---: |",
            ]
        )
        hubs = [summaries[path] for path in context.hub_files if path in summaries]
        if hubs:
            lines.extend(
                f"| {summary.path} | {summary.fan_in} | {summary.fan_out} | "
                f"{summary.importance_score:.2f} |"
                for summary in hubs
            )
        else:
            lines.append("| None detected | 0 | 0 | 0.00 |")

        lines.extend(["", "## Circular Dependencies"])
        if context.circular_dependencies:
            lines.extend(
                f"- {' -> '.join([*cycle, cycle[0]])}"
                for cycle in context.circular_dependencies
                if cycle
            )
        else:
            lines.append("- None detected.")

        lines.extend(["", "## Orphans"])
        if context.orphan_files:
            lines.extend(f"- `{path}`" for path in context.orphan_files)
        else:
            lines.append("- None detected.")
        return "\n".join(lines)

    @staticmethod
    def _important_dependency_relationships(
        context: RepositoryContext,
        *,
        limit: int,
    ) -> list[tuple[str, str]]:
        importance_scores = {
            summary.path: summary.importance_score
            for summary in context.file_summaries
        }
        relationships = [
            (source, target)
            for source, targets in context.dependency_edges.items()
            for target in targets
        ]
        return sorted(
            relationships,
            key=lambda edge: (
                -importance_scores.get(edge[0], 0.0),
                -importance_scores.get(edge[1], 0.0),
                edge,
            ),
        )[:limit]

    @staticmethod
    def _top_important_files(
        context: RepositoryContext,
        *,
        limit: int,
    ) -> list[CodeFileSummary]:
        return sorted(
            context.file_summaries,
            key=lambda summary: (-summary.importance_score, summary.path),
        )[:limit]

    @staticmethod
    def _prompt_file_group(
        heading: str,
        summaries: list[CodeFileSummary],
        detailed_paths: set[str],
    ) -> list[str]:
        lines = [f"{heading}:"]
        if not summaries:
            return [*lines, "- None detected."]

        ordered = sorted(summaries, key=lambda summary: (-summary.importance_score, summary.path))
        detailed = [summary for summary in ordered if summary.path in detailed_paths]
        remaining = [summary for summary in ordered if summary.path not in detailed_paths]
        for summary in detailed:
            lines.append(
                f"- {summary.path} | score={summary.importance_score:.2f} "
                f"({summary.importance_label}) | lines={summary.line_count} | "
                f"functions={summary.function_count} | complexity={summary.complexity_estimate} | "
                f"{summary.summary}"
            )
        if remaining:
            compact = ", ".join(
                f"{summary.path} [{summary.importance_score:.2f} {summary.importance_label}]"
                for summary in remaining
            )
            lines.append(f"- Remaining summarized files: {compact}")
        return lines

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
