from __future__ import annotations

from backend.core.report_contract import numbered_report_section_lines
from backend.models.context import (
    CodeFileSummary,
    RepositoryContext,
    ReviewContext,
    as_review_context,
)
from backend.prompts.models import PromptSection, PromptTemplate, PromptVersion
from backend.prompts.token_budget import TokenBudgeter


class PromptRenderer:
    def __init__(
        self,
        token_budget: int,
        token_model: str = "gpt-4o-mini",
        version: PromptVersion = PromptVersion.V2_6,
    ) -> None:
        self.version = version
        self.token_budgeter = TokenBudgeter(token_budget, token_model)

    def render(self, context: ReviewContext | RepositoryContext) -> str:
        return self.token_budgeter.fit(self.build_template(context).render())

    def build_template(self, context: ReviewContext | RepositoryContext) -> PromptTemplate:
        context = as_review_context(context)
        sections = [
            PromptSection(
                name="instructions",
                lines=(
                    "Review this repository using only summarized repository context.",
                    "Do not assume access to raw source code.",
                    "Return markdown with exactly four top-level sections:",
                    *numbered_report_section_lines(),
                    "Architecture Summary requirements:",
                    "- Describe Entry Points, Core Modules, Supporting Modules, and Dependency Structure.",
                    "- Explain how important dependency relationships shape control flow and change risk.",
                    "- Use hub and cycle evidence in findings instead of listing file paths without interpretation.",
                    "- Explain why each risk or recommendation matters to maintainers and newcomers.",
                ),
            ),
            PromptSection(
                name="repository_summary",
                lines=(
                    "Repository Summary:",
                    f"Repository URL: {context.repo_url}",
                    f"Repository language: {context.language}",
                    f"Total source files: {context.total_python_files}",
                    f"Analyzed files: {context.analyzed_files}",
                    f"Skipped files: {context.skipped_files}",
                    f"Total lines: {context.total_lines}",
                    f"Average complexity: {context.avg_complexity:.2f}",
                    context.repository_summary,
                ),
            ),
            PromptSection(
                name="repository_insights",
                lines=tuple(self._repository_insights_lines(context)),
            ),
            PromptSection(
                name="architecture_summary",
                lines=tuple(self._architecture_summary_lines(context)),
            ),
            PromptSection(
                name="architecture_graph",
                lines=tuple(self._architecture_graph_lines(context)),
            ),
        ]
        detailed_paths = {
            summary.path for summary in self.top_important_files(context, limit=10)
        }
        for roles, heading in (
            ({"Entry Point"}, "Entry Points"),
            ({"Core Module"}, "Core Modules"),
            ({"Supporting File", "Supporting Module"}, "Supporting Modules"),
            ({"Test File"}, "Test Files"),
            ({"Documentation"}, "Documentation"),
            ({"Configuration"}, "Configuration"),
        ):
            sections.append(
                PromptSection(
                    name=heading.lower().replace(" ", "_"),
                    lines=tuple(
                        self._file_group_lines(
                            heading,
                            [
                                summary
                                for summary in context.file_summaries
                                if summary.file_role in roles
                            ],
                            detailed_paths,
                        )
                    ),
                )
            )
        return PromptTemplate(version=self.version, sections=tuple(sections))

    @staticmethod
    def _repository_insights_lines(context: ReviewContext) -> list[str]:
        insights = context.insights
        lines = [
            "Repository Insights:",
            f"- Repository Type: {insights.repository_type}",
            f"- Major Components: {', '.join(insights.major_components) or 'None detected'}",
            "Risk Hotspots:",
        ]
        lines.extend(
            f"- {finding.title}: {finding.explanation}"
            for finding in insights.risk_hotspots
        )
        lines.append("Recommended Reading Order:")
        lines.extend(
            f"- {finding.title}: {finding.explanation}"
            for finding in insights.onboarding_guide
        )
        lines.append("Refactoring Candidates:")
        lines.extend(
            f"- {finding.title}: {finding.explanation}"
            for finding in insights.refactoring_candidates
        )
        return lines

    @staticmethod
    def _architecture_summary_lines(context: ReviewContext) -> list[str]:
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
    def _architecture_graph_lines(cls, context: ReviewContext) -> list[str]:
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
        relationships = cls.important_dependency_relationships(context, limit=30)
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
    def important_dependency_relationships(
        context: ReviewContext | RepositoryContext,
        *,
        limit: int,
    ) -> list[tuple[str, str]]:
        context = as_review_context(context)
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
    def top_important_files(
        context: ReviewContext | RepositoryContext,
        *,
        limit: int,
    ) -> list[CodeFileSummary]:
        context = as_review_context(context)
        return sorted(
            context.file_summaries,
            key=lambda summary: (-summary.importance_score, summary.path),
        )[:limit]

    @staticmethod
    def _file_group_lines(
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
