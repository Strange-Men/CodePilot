from __future__ import annotations

from pathlib import Path

from backend.models.review import CodeFileSummary, RepositoryContext
from backend.parsers.base import ParsedSourceFile, SourceParser
from backend.services.dependency_graph import DependencyGraph
from backend.services.scoring import ScoreInput, score_files


class RepositoryIndexer:
    def __init__(self, parser: SourceParser, max_files: int, max_file_size_bytes: int) -> None:
        self.parser = parser
        self.max_files = max_files
        self.max_file_size_bytes = max_file_size_bytes

    def build_context(self, repo_dir: Path, repo_url: str) -> RepositoryContext:
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

        return RepositoryContext(
            repo_url=repo_url,
            total_python_files=total,
            analyzed_files=len(summaries),
            skipped_files=skipped,
            file_summaries=summaries,
            repository_summary=repo_summary,
            language=self._language_label(),
            total_lines=total_lines,
            avg_complexity=avg_complexity,
            entry_points=[
                summary.path for summary in summaries if summary.file_role == "Entry Point"
            ],
            core_modules=[
                summary.path for summary in summaries if summary.file_role == "Core Module"
            ],
            dependency_edges={
                path: list(targets)
                for path, targets in dependency_graph.dependencies.items()
            },
            circular_dependencies=[list(cycle) for cycle in dependency_graph.cycles],
            hub_files=list(dependency_graph.hub_files),
            orphan_files=list(dependency_graph.orphan_files),
        )

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
        top_files = ", ".join(
            summary.path
            for summary in sorted(
                summaries,
                key=lambda summary: (-summary.importance_score, summary.path),
            )[:20]
        ) or "none"
        language = self._language_label()
        return (
            f"{language} repository with {total} {language} files; analyzed {len(summaries)} and skipped {skipped}. "
            f"Important files include: {top_files}."
        )

    def _infer_purpose(self, parsed: ParsedSourceFile) -> str:
        lower_path = parsed.path.lower()
        if parsed.first_docstring:
            return " ".join(parsed.first_docstring.split())[:220]
        if "api" in lower_path or "router" in lower_path:
            return "Defines web API endpoints or request routing."
        if "model" in lower_path or parsed.classes:
            return "Defines data models or object-oriented domain behavior."
        if "test" in lower_path:
            return "Contains tests or validation helpers."
        if "service" in lower_path:
            return "Implements application service logic."
        if "parser" in lower_path:
            return "Parses source code or input data."
        if parsed.functions:
            return "Provides reusable functions for application behavior."
        return f"{self._language_label()} module with limited top-level structure detected."

    def _language_label(self) -> str:
        labels = {
            "python": "Python",
            "javascript": "JavaScript",
            "typescript": "TypeScript",
        }
        return labels.get(self.parser.language, self.parser.language.title())

    @staticmethod
    def _trim_words(text: str, limit: int) -> str:
        words = text.split()
        if len(words) <= limit:
            return text
        return " ".join(words[:limit]) + "..."
