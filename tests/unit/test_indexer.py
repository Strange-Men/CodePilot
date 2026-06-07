from __future__ import annotations

from pathlib import Path

import pytest

from backend.parsers.base import ParsedSourceFile
from backend.services.indexer import RepositoryIndexer


class StaticParser:
    language = "python"

    def __init__(self, parsed_files: list[ParsedSourceFile]) -> None:
        self.parsed_files = parsed_files

    def discover_files(
        self,
        repo_dir: Path,
        max_files: int,
        max_file_size_bytes: int,
    ) -> tuple[list[Path], int, int]:
        return [repo_dir / parsed.path for parsed in self.parsed_files], len(self.parsed_files), 0

    def parse_file(self, repo_dir: Path, path: Path) -> ParsedSourceFile:
        relative_path = path.relative_to(repo_dir).as_posix()
        return next(parsed for parsed in self.parsed_files if parsed.path == relative_path)


def test_indexer_propagates_repository_metrics_and_importance(temp_repo: Path) -> None:
    parser = StaticParser(
        [
            ParsedSourceFile(
                path="small.py",
                classes=[],
                functions=["small"],
                imports=[],
                first_docstring=None,
                line_count=10,
                function_count=1,
                complexity_estimate=2,
            ),
            ParsedSourceFile(
                path="large.py",
                classes=[],
                functions=["large"],
                imports=[],
                first_docstring=None,
                line_count=100,
                function_count=1,
                complexity_estimate=10,
            ),
        ]
    )

    context = RepositoryIndexer(parser, max_files=10, max_file_size_bytes=1000).build_context(
        temp_repo,
        "https://github.com/example/project",
    )

    assert context.total_lines == 110
    assert context.avg_complexity == pytest.approx(6.0)
    summaries = {summary.path: summary for summary in context.file_summaries}
    assert summaries["small.py"].importance_score == pytest.approx(11.89)
    assert summaries["large.py"].importance_score == pytest.approx(100.0)
    assert summaries["small.py"].importance_label == "Peripheral"
    assert summaries["large.py"].importance_label == "Critical"
    assert context.repository_summary.index("large.py") < context.repository_summary.index("small.py")


def test_indexer_propagates_entry_points_and_core_modules(temp_repo: Path) -> None:
    parser = StaticParser(
        [
            ParsedSourceFile(
                path="app.py",
                classes=[],
                functions=["create_app"],
                imports=[],
                first_docstring=None,
                line_count=20,
                function_count=1,
                complexity_estimate=1,
                is_entry_point=True,
            ),
            ParsedSourceFile(
                path="services/review.py",
                classes=[],
                functions=["review"],
                imports=[],
                first_docstring=None,
                line_count=20,
                function_count=1,
                complexity_estimate=1,
            ),
        ]
    )

    context = RepositoryIndexer(parser, max_files=10, max_file_size_bytes=1000).build_context(
        temp_repo,
        "https://github.com/example/project",
    )

    assert context.entry_points == ["app.py"]
    assert context.core_modules == ["services/review.py"]
    summaries = {summary.path: summary for summary in context.file_summaries}
    assert summaries["app.py"].file_role == "Entry Point"
    assert summaries["services/review.py"].file_role == "Core Module"
