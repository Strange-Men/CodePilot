from __future__ import annotations

from pathlib import Path

from backend.models.review import CodeFileSummary, RepositoryContext
from backend.parsers.python_parser import ParsedPythonFile, PythonParser


class RepositoryIndexer:
    def __init__(self, parser: PythonParser, max_files: int, max_file_size_bytes: int) -> None:
        self.parser = parser
        self.max_files = max_files
        self.max_file_size_bytes = max_file_size_bytes

    def build_context(self, repo_dir: Path, repo_url: str) -> RepositoryContext:
        files, total, skipped = self.parser.discover_files(repo_dir, self.max_files, self.max_file_size_bytes)
        parsed_files = [self.parser.parse_file(repo_dir, path) for path in files]
        summaries = [self._summarize_file(parsed) for parsed in parsed_files]
        repo_summary = self._summarize_repository(summaries, total, skipped)

        return RepositoryContext(
            repo_url=repo_url,
            total_python_files=total,
            analyzed_files=len(summaries),
            skipped_files=skipped,
            file_summaries=summaries,
            repository_summary=repo_summary,
        )

    def _summarize_file(self, parsed: ParsedPythonFile) -> CodeFileSummary:
        purpose = self._infer_purpose(parsed)
        class_list = ", ".join(parsed.classes[:8]) or "none"
        function_list = ", ".join(parsed.functions[:12]) or "none"
        summary = (
            f"{parsed.path}: purpose={purpose}; classes={class_list}; "
            f"functions={function_list}."
        )
        return CodeFileSummary(
            path=parsed.path,
            classes=parsed.classes[:20],
            functions=parsed.functions[:30],
            purpose=purpose,
            summary=self._trim_words(summary, 170),
        )

    def _summarize_repository(self, summaries: list[CodeFileSummary], total: int, skipped: int) -> str:
        top_files = ", ".join(summary.path for summary in summaries[:20]) or "none"
        return (
            f"Python repository with {total} Python files; analyzed {len(summaries)} and skipped {skipped}. "
            f"Important files include: {top_files}."
        )

    @staticmethod
    def _infer_purpose(parsed: ParsedPythonFile) -> str:
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
        return "Python module with limited top-level structure detected."

    @staticmethod
    def _trim_words(text: str, limit: int) -> str:
        words = text.split()
        if len(words) <= limit:
            return text
        return " ".join(words[:limit]) + "..."

