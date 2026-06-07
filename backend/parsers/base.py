from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Protocol


@dataclass(frozen=True)
class ParsedSourceFile:
    path: str
    classes: list[str]
    functions: list[str]
    imports: list[str]
    first_docstring: str | None
    line_count: int = 0
    function_count: int = 0
    complexity_estimate: int = 0
    is_entry_point: bool = False
    dependency_imports: list[str] = field(default_factory=list)


class SourceParser(Protocol):
    language: str

    def discover_files(self, repo_dir: Path, max_files: int, max_file_size_bytes: int) -> tuple[list[Path], int, int]:
        """Return selected source files, total supported files, and skipped files."""

    def parse_file(self, repo_dir: Path, path: Path) -> ParsedSourceFile:
        """Parse a source file into CodePilot's indexable shape."""
