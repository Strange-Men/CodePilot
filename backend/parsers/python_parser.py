from __future__ import annotations

import ast
from dataclasses import dataclass
from pathlib import Path

from backend.parsers.base import ParsedSourceFile, SourceParser

IGNORE_DIRS = {
    "node_modules",
    "dist",
    "build",
    ".venv",
    "venv",
    "vendor",
    ".git",
    "__pycache__",
    ".next",
}


@dataclass(frozen=True)
class ParsedPythonFile(ParsedSourceFile):
    pass


class PythonParser(SourceParser):
    language = "python"

    def __init__(self) -> None:
        self._tree_sitter_parser = self._build_tree_sitter_parser()

    def discover_files(self, repo_dir: Path, max_files: int, max_file_size_bytes: int) -> tuple[list[Path], int, int]:
        candidates: list[Path] = []
        total_python_files = 0
        skipped = 0

        for path in repo_dir.rglob("*.py"):
            if any(part in IGNORE_DIRS for part in path.parts):
                continue
            total_python_files += 1
            try:
                if path.stat().st_size > max_file_size_bytes:
                    skipped += 1
                    continue
            except OSError:
                skipped += 1
                continue
            candidates.append(path)

        selected = sorted(candidates, key=self._importance_key)[:max_files]
        skipped += max(0, len(candidates) - len(selected))
        return selected, total_python_files, skipped

    def parse_file(self, repo_dir: Path, path: Path) -> ParsedPythonFile:
        source = path.read_text(encoding="utf-8", errors="replace")
        relative_path = path.relative_to(repo_dir).as_posix()

        if self._tree_sitter_parser:
            parsed = self._parse_with_tree_sitter(source, relative_path)
            if parsed:
                return parsed

        return self._parse_with_ast(source, relative_path)

    def _parse_with_tree_sitter(self, source: str, relative_path: str) -> ParsedPythonFile | None:
        source_bytes = source.encode("utf-8")
        try:
            tree = self._tree_sitter_parser.parse(source_bytes)
            root = tree.root_node
        except Exception:
            return None

        classes: list[str] = []
        functions: list[str] = []
        imports: list[str] = []

        def text(node) -> str:
            return source_bytes[node.start_byte : node.end_byte].decode("utf-8", errors="replace")

        def walk(node) -> None:
            if node.type == "class_definition":
                name = node.child_by_field_name("name")
                if name:
                    classes.append(text(name))
            elif node.type == "function_definition":
                name = node.child_by_field_name("name")
                if name:
                    functions.append(text(name))
            elif node.type in {"import_statement", "import_from_statement"}:
                lines = text(node).splitlines()
                if lines:
                    imports.append(lines[0][:120])
            for child in node.children:
                walk(child)

        walk(root)
        docstring = self._extract_ast_docstring(source)
        return ParsedPythonFile(relative_path, classes, functions, imports[:12], docstring)

    def _parse_with_ast(self, source: str, relative_path: str) -> ParsedPythonFile:
        try:
            module = ast.parse(source)
        except SyntaxError:
            return ParsedPythonFile(relative_path, [], [], [], None)

        classes = [node.name for node in ast.walk(module) if isinstance(node, ast.ClassDef)]
        functions = [
            node.name
            for node in ast.walk(module)
            if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef)
        ]
        imports: list[str] = []
        for node in ast.walk(module):
            if isinstance(node, ast.Import):
                imports.extend(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imports.append(node.module)
        return ParsedPythonFile(relative_path, classes, functions, imports[:12], ast.get_docstring(module))

    @staticmethod
    def _extract_ast_docstring(source: str) -> str | None:
        try:
            module = ast.parse(source)
        except SyntaxError:
            return None
        return ast.get_docstring(module)

    @staticmethod
    def _importance_key(path: Path) -> tuple[int, int, str]:
        parts = [part.lower() for part in path.parts]
        name = path.name.lower()
        score = 50
        if name in {"main.py", "app.py", "__init__.py"}:
            score -= 20
        if any(part in {"api", "services", "core", "models", "parsers", "reviewers", "llm"} for part in parts):
            score -= 10
        if any(part in {"tests", "test"} or part.startswith("test_") for part in parts):
            score += 8
        return (score, len(parts), path.as_posix())

    @staticmethod
    def _build_tree_sitter_parser():
        try:
            from tree_sitter_language_pack import get_parser

            return get_parser("python")
        except Exception:
            return None
