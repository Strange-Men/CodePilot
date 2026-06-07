from __future__ import annotations

from pathlib import Path

from backend.models.context import (
    CodeFileSummary,
    DependencyStructure,
    FileAnalysisBundle,
    RepoMetadata,
    RepositoryContext,
    ReviewContext,
)
from backend.parsers.base import ParsedSourceFile, SourceParser
from backend.services.dependency_graph import DependencyGraph
from backend.services.insights import RepositoryInsightEngine
from backend.services.scoring import ScoreInput, file_role, score_files


class RepositoryIndexer:
    def __init__(self, parser: SourceParser, max_files: int, max_file_size_bytes: int) -> None:
        self.parser = parser
        self.max_files = max_files
        self.max_file_size_bytes = max_file_size_bytes

    def build_context(self, repo_dir: Path, repo_url: str) -> RepositoryContext:
        return RepositoryContext.from_review_context(self.build_review_context(repo_dir, repo_url))

    def build_review_context(self, repo_dir: Path, repo_url: str) -> ReviewContext:
        files, total, skipped = self.parser.discover_files(repo_dir, self.max_files, self.max_file_size_bytes)
        parsed_files = [self.parser.parse_file(repo_dir, path) for path in files]
        summaries = [self._summarize_file(parsed) for parsed in parsed_files]
        dependency_graph = DependencyGraph(self.parser.language).build(parsed_files)
        cycle_files = {
            path
            for cycle in dependency_graph.cycles
            for path in cycle
        }
        hub_files = set(dependency_graph.hub_files)
        orphan_files = set(dependency_graph.orphan_files)
        for summary in summaries:
            summary.dependencies = list(dependency_graph.dependencies[summary.path])
            summary.fan_in = dependency_graph.fan_in[summary.path]
            summary.fan_out = dependency_graph.fan_out[summary.path]
            summary.in_dependency_cycle = summary.path in cycle_files
            summary.is_hub = summary.path in hub_files
            summary.is_orphan = summary.path in orphan_files
        scored_files = score_files(
            ScoreInput(
                path=summary.path,
                line_count=summary.line_count,
                complexity_estimate=summary.complexity_estimate,
                is_entry_point=summary.is_entry_point,
                fan_in=summary.fan_in,
                fan_out=summary.fan_out,
                in_dependency_cycle=summary.in_dependency_cycle,
            )
            for summary in summaries
        )
        for summary in summaries:
            scored = scored_files[summary.path]
            summary.importance_score = scored.score
            summary.importance_label = scored.label
            summary.file_role = scored.role
        repo_summary = self._summarize_repository(summaries, total, skipped)
        total_lines = sum(summary.line_count for summary in summaries)
        avg_complexity = (
            sum(summary.complexity_estimate for summary in summaries) / len(summaries)
            if summaries
            else 0.0
        )

        context = ReviewContext(
            metadata=RepoMetadata(
                repo_url=repo_url,
                total_source_files=total,
                analyzed_files=len(summaries),
                skipped_files=skipped,
                repository_summary=repo_summary,
                language=self._language_label(),
                total_lines=total_lines,
                avg_complexity=avg_complexity,
            ),
            files=FileAnalysisBundle(
                summaries=summaries,
                entry_points=[
                    summary.path for summary in summaries if summary.file_role == "Entry Point"
                ],
                core_modules=[
                    summary.path for summary in summaries if summary.file_role == "Core Module"
                ],
                supporting_modules=[
                    summary.path
                    for summary in summaries
                    if summary.file_role in {"Supporting File", "Supporting Module"}
                ],
            ),
            dependencies=DependencyStructure(
                edges={
                    path: list(targets)
                    for path, targets in dependency_graph.dependencies.items()
                },
                circular_dependencies=[list(cycle) for cycle in dependency_graph.cycles],
                hub_files=list(dependency_graph.hub_files),
                orphan_files=list(dependency_graph.orphan_files),
            ),
        )
        context.insights = RepositoryInsightEngine().generate(context)
        return context

    def _summarize_file(self, parsed: ParsedSourceFile) -> CodeFileSummary:
        purpose = self._infer_purpose(parsed)
        class_list = ", ".join(parsed.classes[:8]) or "none"
        function_list = ", ".join(parsed.functions[:12]) or "none"
        summary = f"{parsed.path}: purpose={purpose}; classes={class_list}; functions={function_list}"
        exported_symbols = getattr(parsed, "exported_symbols", [])
        if exported_symbols:
            summary = f"{summary}; exports={', '.join(exported_symbols[:12])}"
        summary = f"{summary}."
        return CodeFileSummary(
            path=parsed.path,
            classes=parsed.classes[:20],
            functions=parsed.functions[:30],
            purpose=purpose,
            summary=self._trim_words(summary, 170),
            line_count=parsed.line_count,
            function_count=parsed.function_count,
            complexity_estimate=parsed.complexity_estimate,
            is_entry_point=parsed.is_entry_point,
        )

    def _summarize_repository(self, summaries: list[CodeFileSummary], total: int, skipped: int) -> str:
        entry_points = self._paths_for_roles(summaries, {"Entry Point"})
        core_modules = self._paths_for_roles(summaries, {"Core Module"})
        supporting_modules = self._paths_for_roles(
            summaries,
            {"Supporting File", "Supporting Module"},
        )
        hubs = [
            summary.path
            for summary in sorted(
                summaries,
                key=lambda summary: (-summary.fan_in, -summary.importance_score, summary.path),
            )
            if summary.is_hub
        ]
        dependency_count = sum(summary.fan_out for summary in summaries)
        cycle_count = sum(summary.in_dependency_cycle for summary in summaries)
        language = self._language_label()
        return (
            f"{language} repository with {total} {language} files; analyzed {len(summaries)} and skipped {skipped}. "
            f"Entry points: {self._format_paths(entry_points)}. "
            f"Core modules: {self._format_paths(core_modules)}. "
            f"Supporting modules: {self._format_paths(supporting_modules)}. "
            f"Dependency structure: {dependency_count} resolved internal relationships; "
            f"hubs: {self._format_paths(hubs)}; {cycle_count} modules participate in cycles."
        )

    def _infer_purpose(self, parsed: ParsedSourceFile) -> str:
        lower_path = parsed.path.lower()
        if parsed.first_docstring:
            return " ".join(parsed.first_docstring.split())[:220]
        role = file_role(parsed.path, parsed.is_entry_point)
        if role == "Entry Point":
            return "Bootstraps the application and connects top-level runtime components."
        if role == "Test File":
            return "Contains tests, fixtures, or validation helpers."
        if role == "Documentation":
            return "Provides executable examples or documentation-adjacent source."
        if role == "Configuration":
            return "Defines application, tooling, or test configuration."
        if "api" in lower_path or "router" in lower_path:
            return "Defines web API endpoints or request routing."
        if "service" in lower_path:
            return "Implements application service logic."
        if "parser" in lower_path:
            return "Parses source code or input data."
        dependency_count = len(parsed.dependency_imports or parsed.imports)
        if dependency_count >= 3 and parsed.functions:
            return "Coordinates several imported components through application workflows."
        if parsed.classes and parsed.functions:
            return "Implements object-oriented domain behavior with supporting operations."
        if "model" in lower_path or parsed.classes:
            return "Defines data models or object-oriented domain behavior."
        exported_symbols = getattr(parsed, "exported_symbols", [])
        if exported_symbols:
            return "Defines a public module interface for reusable application behavior."
        if len(parsed.functions) >= 5:
            return "Groups a substantial set of related application operations."
        if parsed.functions:
            return "Provides reusable functions for application behavior."
        if dependency_count:
            return "Composes imported modules without exposing substantial local behavior."
        return f"{self._language_label()} module with limited top-level structure detected."

    def _language_label(self) -> str:
        labels = {
            "python": "Python",
            "javascript": "JavaScript",
            "typescript": "TypeScript",
        }
        parser_languages = getattr(self.parser, "languages", ())
        if parser_languages:
            return " + ".join(labels.get(language, language.title()) for language in parser_languages)
        return labels.get(self.parser.language, self.parser.language.title())

    @staticmethod
    def _paths_for_roles(
        summaries: list[CodeFileSummary],
        roles: set[str],
    ) -> list[str]:
        return [
            summary.path
            for summary in sorted(
                summaries,
                key=lambda summary: (-summary.importance_score, summary.path),
            )
            if summary.file_role in roles
        ]

    @staticmethod
    def _format_paths(paths: list[str], limit: int = 8) -> str:
        if not paths:
            return "none detected"
        displayed = ", ".join(paths[:limit])
        remaining = len(paths) - limit
        return f"{displayed} (+{remaining} more)" if remaining > 0 else displayed

    @staticmethod
    def _trim_words(text: str, limit: int) -> str:
        words = text.split()
        if len(words) <= limit:
            return text
        return " ".join(words[:limit]) + "..."
