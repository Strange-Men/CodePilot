from __future__ import annotations

from pathlib import Path

import pytest

from backend.parsers.base import ParsedSourceFile
from backend.parsers.composite import CompositeSourceParser


class ExtensionParser:
    def __init__(self, language: str, extension: str) -> None:
        self.language = language
        self.extension = extension
        self.parsed: list[str] = []

    def discover_files(
        self,
        repo_dir: Path,
        max_files: int,
        max_file_size_bytes: int,
    ) -> tuple[list[Path], int, int]:
        files = sorted(repo_dir.rglob(f"*{self.extension}"))
        return files[:max_files], len(files), max(0, len(files) - max_files)

    def parse_file(self, repo_dir: Path, path: Path) -> ParsedSourceFile:
        relative_path = path.relative_to(repo_dir).as_posix()
        self.parsed.append(relative_path)
        return ParsedSourceFile(
            path=relative_path,
            classes=[],
            functions=[],
            imports=[],
            first_docstring=None,
        )


def test_composite_parser_discovers_all_supported_languages(temp_repo: Path) -> None:
    (temp_repo / "app.py").write_text("", encoding="utf-8")
    (temp_repo / "index.js").write_text("", encoding="utf-8")
    (temp_repo / "types.ts").write_text("", encoding="utf-8")
    parser = CompositeSourceParser(
        [
            ExtensionParser("python", ".py"),
            ExtensionParser("javascript", ".js"),
            ExtensionParser("typescript", ".ts"),
        ]
    )

    files, total, skipped = parser.discover_files(temp_repo, 10, 1000)

    assert {path.name for path in files} == {"app.py", "index.js", "types.ts"}
    assert total == 3
    assert skipped == 0
    assert parser.languages == ("python", "javascript", "typescript")


def test_composite_parser_preserves_one_file_per_language_with_tight_limit(temp_repo: Path) -> None:
    for name in ("a.py", "b.py", "c.py"):
        (temp_repo / name).write_text("", encoding="utf-8")
    (temp_repo / "index.js").write_text("", encoding="utf-8")
    parser = CompositeSourceParser(
        [
            ExtensionParser("python", ".py"),
            ExtensionParser("javascript", ".js"),
        ]
    )

    files, total, skipped = parser.discover_files(temp_repo, 2, 1000)

    assert {path.suffix for path in files} == {".py", ".js"}
    assert total == 4
    assert skipped == 2


@pytest.mark.parametrize(
    ("filename", "expected_language"),
    [
        ("module.py", "python"),
        ("index.js", "javascript"),
        ("component.tsx", "typescript"),
    ],
)
def test_composite_parser_delegates_parse_by_extension(
    temp_repo: Path,
    filename: str,
    expected_language: str,
) -> None:
    path = temp_repo / filename
    path.write_text("", encoding="utf-8")
    parsers = [
        ExtensionParser("python", ".py"),
        ExtensionParser("javascript", ".js"),
        ExtensionParser("typescript", ".tsx"),
    ]
    parser = CompositeSourceParser(parsers)

    parsed = parser.parse_file(temp_repo, path)

    assert parsed.path == filename
    assert next(item for item in parsers if item.language == expected_language).parsed == [filename]


def test_composite_parser_rejects_unknown_extension(temp_repo: Path) -> None:
    path = temp_repo / "README.md"
    path.write_text("", encoding="utf-8")
    parser = CompositeSourceParser([ExtensionParser("python", ".py")])

    with pytest.raises(ValueError, match="No matching parser"):
        parser.parse_file(temp_repo, path)
