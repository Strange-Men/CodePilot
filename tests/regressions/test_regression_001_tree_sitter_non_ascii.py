from __future__ import annotations

from pathlib import Path

import pytest

from backend.parsers.python_parser import PythonParser


def test_regression_001_parser_handles_non_ascii_before_imports(temp_repo: Path) -> None:
    source = temp_repo / "enterprise_edge.py"
    non_ascii_prefix = f"# {chr(0x4E2D)}\n" * 200
    source.write_text(non_ascii_prefix + "import os\n", encoding="utf-8")

    parser = PythonParser()
    if parser._tree_sitter_parser is None:
        pytest.skip("tree-sitter parser unavailable")

    parsed = parser.parse_file(temp_repo, source)

    assert parsed.path == "enterprise_edge.py"
    assert parsed.imports == ["import os"]
