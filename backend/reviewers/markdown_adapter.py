from __future__ import annotations

from collections.abc import Iterable

from backend.core.report_contract import REPORT_SECTIONS
from backend.models.context import (
    CodeFileSummary,
    RepositoryContext,
    RepositoryInsight,
    ReviewContext,
    as_review_context,
)
from backend.models.structured_review import ReviewFinding, StructuredReviewDraft
from backend.prompts import PromptRenderer

DEFAULT_SECTION_CONTENT = "No critical findings detected from the available repository summaries."
APPENDIX_SECTIONS = {
    "Repository Insights",
    "Repository Metrics",
    "Architecture Graph",
}


class MarkdownReviewAdapter:
    def parse(self, report: str) -> StructuredReviewDraft:
        sections = self.extract_sections(report)
        return StructuredReviewDraft(
            findings=[
                ReviewFinding(section=section, description=body)
                for section, body in sections.items()
                if body
            ]
        )

    def normalize(
        self,
        report: str,
        context: ReviewContext | RepositoryContext | None = None,
    ) -> str:
        return self.render(self.parse(report), context)

    def render(
        self,
        draft: StructuredReviewDraft,
        context: ReviewContext | RepositoryContext | None = None,
    ) -> str:
        output = [
            f"# {section}\n{draft.section_markdown(section) or DEFAULT_SECTION_CONTENT}"
            for section in REPORT_SECTIONS
        ]
        if context is not None:
            review_context = as_review_context(context)
            output.append(self.repository_insights_section(review_context))
            output.append(self.repository_metrics_section(review_context))
            output.append(self.architecture_graph_section(review_context))
        return "\n\n".join(output) + "\n"

    @staticmethod
    def extract_sections(report: str) -> dict[str, str]:
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
            if heading in APPENDIX_SECTIONS:
                current = None
                continue
            if stripped.startswith("#"):
                continue
            if current:
                sections[current].append(raw_line)

        if not sections and report.strip():
            sections["Architecture Summary"] = [report.strip()]
        return {key: "\n".join(value).strip() for key, value in sections.items()}

    @classmethod
    def repository_metrics_section(cls, context: ReviewContext) -> str:
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
        top_files = cls.top_important_files(context, limit=10)
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

    @classmethod
    def repository_insights_section(cls, context: ReviewContext) -> str:
        insights = context.insights
        lines = [
            "# Repository Insights",
            "",
            "## Architecture Overview",
            f"- **Repository type:** {insights.repository_type}",
        ]
        if insights.major_components:
            lines.append(f"- **Major components:** {', '.join(insights.major_components)}")
        lines.extend(cls.render_insight_findings(insights.architecture_overview))
        lines.extend(["", "## Risk Hotspots"])
        lines.extend(cls.render_insight_findings(insights.risk_hotspots))
        lines.extend(["", "## Onboarding Guide"])
        lines.extend(cls.render_insight_findings(insights.onboarding_guide))
        lines.extend(["", "## Refactoring Candidates"])
        lines.extend(cls.render_insight_findings(insights.refactoring_candidates))
        return "\n".join(lines)

    @staticmethod
    def render_insight_findings(findings: Iterable[RepositoryInsight]) -> list[str]:
        lines: list[str] = []
        for finding in findings:
            files = f" Files: {', '.join(f'`{path}`' for path in finding.files)}." if finding.files else ""
            lines.append(f"- **{finding.title}:** {finding.explanation}{files}")
        return lines or ["- No insight available from the analyzed source files."]

    @staticmethod
    def architecture_graph_section(context: ReviewContext) -> str:
        summaries = {summary.path: summary for summary in context.file_summaries}
        edge_count = sum(len(targets) for targets in context.dependency_edges.values())
        lines = [
            "# Architecture Graph",
            f"- Analyzed nodes: {len(context.file_summaries)}",
            f"- Resolved internal dependencies: {edge_count}",
            "",
            "## Entry Points",
        ]
        lines.extend(f"- `{path}`" for path in context.entry_points)
        if not context.entry_points:
            lines.append("- None detected.")

        lines.extend(["", "## Important Relationships"])
        relationships = PromptRenderer.important_dependency_relationships(context, limit=30)
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
    def top_important_files(
        context: ReviewContext,
        *,
        limit: int,
    ) -> list[CodeFileSummary]:
        return sorted(
            context.file_summaries,
            key=lambda summary: (-summary.importance_score, summary.path),
        )[:limit]
