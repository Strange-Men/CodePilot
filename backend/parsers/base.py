from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Protocol


@dataclass(frozen=True)
class ParsedSourceFile:
    path: str
    classes: list[str]
    functions: list[str]
    imports: list[str]
    first_docstring: str | None


class SourceParser(Protocol):
    language: str

    def discover_files(self, repo_dir: Path, max_files: int, max_file_size_bytes: int) -> tuple[list[Path], int, int]:
        """Return selected source files, total supported files, and skipped files."""

    def parse_file(self, repo_dir: Path, path: Path) -> ParsedSourceFile:
        """Parse a source file into CodePilot's indexable shape."""
