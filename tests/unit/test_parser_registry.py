from __future__ import annotations

from pathlib import Path

import pytest

from backend.parsers.base import ParsedSourceFile
from backend.parsers.python_parser import PythonParser
from backend.parsers.registry import ParserRegistry, build_default_parser_registry


class FakeParser:
    language = "fake"

    def discover_files(self, repo_dir: Path, max_files: int, max_file_size_bytes: int) -> tuple[list[Path], int, int]:
        return [], 0, 0

    def parse_file(self, repo_dir: Path, path: Path) -> ParsedSourceFile:
        return ParsedSourceFile(path="fake", classes=[], functions=[], imports=[], first_docstring=None)


def test_default_registry_registers_python_parser() -> None:
    registry = build_default_parser_registry()

    parser = registry.create("python")

    assert isinstance(parser, PythonParser)
    assert registry.languages() == ("python",)


def test_registry_normalizes_language_names() -> None:
    registry = ParserRegistry()
    registry.register(" Fake ", FakeParser)

    parser = registry.create("FAKE")

    assert isinstance(parser, FakeParser)
    assert registry.languages() == ("fake",)


def test_registry_raises_for_unregistered_language() -> None:
    registry = ParserRegistry()

    with pytest.raises(KeyError, match="No parser registered for language: ruby"):
        registry.create("ruby")
