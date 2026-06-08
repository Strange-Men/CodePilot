from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Protocol


@dataclass(frozen=True)
class ParsedFunction:
    name: str
    params: list[str] = field(default_factory=list)
    return_type: str | None = None
    decorators: list[str] = field(default_factory=list)
    docstring: str | None = None
    start_line: int = 0
    end_line: int = 0
    calls: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class ParsedClass:
    name: str
    bases: list[str] = field(default_factory=list)
    decorators: list[str] = field(default_factory=list)
    docstring: str | None = None
    start_line: int = 0
    end_line: int = 0
    methods: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class ParsedRoute:
    method: str
    path: str
    handler: str
    line: int = 0


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
    function_details: list[ParsedFunction] = field(default_factory=list)
    class_details: list[ParsedClass] = field(default_factory=list)
    call_refs: list[str] = field(default_factory=list)
    route_patterns: list[ParsedRoute] = field(default_factory=list)


class SourceParser(Protocol):
    language: str

    def discover_files(self, repo_dir: Path, max_files: int, max_file_size_bytes: int) -> tuple[list[Path], int, int]:
        """Return selected source files, total supported files, and skipped files."""

    def parse_file(self, repo_dir: Path, path: Path) -> ParsedSourceFile:
        """Parse a source file into CodePilot's indexable shape."""
