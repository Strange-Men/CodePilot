from __future__ import annotations

from pathlib import Path

import pytest

from backend.parsers.python_parser import PythonParser


def test_parse_valid_python_file(temp_repo: Path) -> None:
    source = temp_repo / "app.py"
    source.write_text(
        '"""Application module."""\n'
        "import os\n"
        "from pathlib import Path\n\n"
        "class App:\n"
        "    pass\n\n"
        "async def create_app():\n"
        "    return App()\n",
        encoding="utf-8",
    )

    parsed = PythonParser().parse_file(temp_repo, source)

    assert parsed.path == "app.py"
    assert "App" in parsed.classes
    assert "create_app" in parsed.functions
    assert parsed.imports
    assert parsed.first_docstring == "Application module."


def test_parse_syntax_error_file_returns_safe_result(temp_repo: Path) -> None:
    source = temp_repo / "broken.py"
    source.write_text("def broken(:\n    pass\n", encoding="utf-8")

    parser = PythonParser()
    parser._tree_sitter_parser = None
    parsed = parser.parse_file(temp_repo, source)

    assert parsed.path == "broken.py"
    assert parsed.classes == []
    assert parsed.functions == []
    assert parsed.imports == []
    assert parsed.first_docstring is None


def test_parse_empty_file(temp_repo: Path) -> None:
    source = temp_repo / "empty.py"
    source.write_text("", encoding="utf-8")

    parsed = PythonParser().parse_file(temp_repo, source)

    assert parsed.path == "empty.py"
    assert parsed.classes == []
    assert parsed.functions == []
    assert parsed.first_docstring is None
    assert parsed.line_count == 0
    assert parsed.function_count == 0
    assert parsed.complexity_estimate == 0


def test_python_metrics_count_lines_functions_and_control_flow(temp_repo: Path) -> None:
    source = temp_repo / "metrics.py"
    source.write_text(
        "def evaluate(items, enabled):\n"
        "    assert items\n"
        "    if enabled and items:\n"
        "        for item in items:\n"
        "            while item:\n"
        "                break\n"
        "    try:\n"
        "        with open('value.txt') as handle:\n"
        "            return handle.read()\n"
        "    except OSError:\n"
        "        return None\n",
        encoding="utf-8",
    )

    parsed = PythonParser().parse_file(temp_repo, source)

    assert parsed.line_count == 11
    assert parsed.function_count == 1
    assert parsed.complexity_estimate == 7


def test_discover_skips_large_file(temp_repo: Path) -> None:
    small = temp_repo / "small.py"
    large = temp_repo / "large.py"
    small.write_text("x = 1\n", encoding="utf-8")
    large.write_text("x = '" + ("a" * 300) + "'\n", encoding="utf-8")

    files, total, skipped = PythonParser().discover_files(temp_repo, max_files=10, max_file_size_bytes=100)

    assert files == [small]
    assert total == 2
    assert skipped == 1


def test_discover_ignores_unsupported_files(temp_repo: Path) -> None:
    (temp_repo / "README.md").write_text("# docs\n", encoding="utf-8")
    (temp_repo / "script.js").write_text("console.log('no')\n", encoding="utf-8")

    files, total, skipped = PythonParser().discover_files(temp_repo, max_files=10, max_file_size_bytes=1000)

    assert files == []
    assert total == 0
    assert skipped == 0


def test_discover_ignores_configured_directories(temp_repo: Path) -> None:
    ignored = temp_repo / ".venv" / "ignored.py"
    kept = temp_repo / "src" / "kept.py"
    ignored.parent.mkdir()
    kept.parent.mkdir()
    ignored.write_text("x = 1\n", encoding="utf-8")
    kept.write_text("x = 2\n", encoding="utf-8")

    files, total, skipped = PythonParser().discover_files(temp_repo, max_files=10, max_file_size_bytes=1000)

    assert files == [kept]
    assert total == 1
    assert skipped == 0


def test_discover_respects_max_files_and_prioritizes_entrypoints(temp_repo: Path) -> None:
    for name in ["z.py", "main.py", "api/routes.py"]:
        path = temp_repo / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("x = 1\n", encoding="utf-8")

    files, total, skipped = PythonParser().discover_files(temp_repo, max_files=2, max_file_size_bytes=1000)

    assert [path.relative_to(temp_repo).as_posix() for path in files] == ["main.py", "api/routes.py"]
    assert total == 3
    assert skipped == 1


def test_parser_relative_paths_use_posix_separators(temp_repo: Path) -> None:
    source = temp_repo / "pkg" / "module.py"
    source.parent.mkdir()
    source.write_text("def run():\n    return 1\n", encoding="utf-8")

    parsed = PythonParser().parse_file(temp_repo, source)

    assert parsed.path == "pkg/module.py"


def test_parse_file_handles_non_ascii_before_imports_regression(temp_repo: Path) -> None:
    source = temp_repo / "enterprise_edge.py"
    non_ascii_comment = f"# {chr(0x4E2D)}\n" * 200
    source.write_text(non_ascii_comment + "import os\n", encoding="utf-8")

    parser = PythonParser()
    if parser._tree_sitter_parser is None:
        pytest.skip("tree-sitter parser unavailable")

    parsed = parser.parse_file(temp_repo, source)

    assert parsed.path == "enterprise_edge.py"
    assert parsed.imports == ["import os"]
