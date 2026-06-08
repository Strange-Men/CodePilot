from __future__ import annotations

import ast
from dataclasses import dataclass, field
from pathlib import Path

from backend.parsers.base import ParsedClass, ParsedFunction, ParsedRoute, ParsedSourceFile, SourceParser
from backend.services.scoring import detect_entry_point
from backend.services.source_selection import source_file_priority

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
PYTHON_ENTRY_NAMES = {"main.py", "app.py", "__init__.py"}
PYTHON_CORE_PATH_PARTS = {"api", "services", "core", "models", "parsers", "reviewers", "llm"}


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
        return self.parse_source(source, relative_path)

    def parse_source(self, source: str, relative_path: str) -> ParsedPythonFile:
        module = self._parse_ast(source)

        if self._tree_sitter_parser:
            parsed = self._parse_with_tree_sitter(source, relative_path, module)
            if parsed:
                return parsed

        return self._parse_with_ast(source, relative_path, module)

    def _parse_with_tree_sitter(
        self,
        source: str,
        relative_path: str,
        module: ast.Module | None,
    ) -> ParsedPythonFile | None:
        source_bytes = source.encode("utf-8")
        try:
            tree = self._tree_sitter_parser.parse(source_bytes)
            root = tree.root_node
        except Exception:
            return None

        classes: list[str] = []
        functions: list[str] = []
        imports: list[str] = []
        details = self._deep_context_from_module(module) if module is not None else _PythonDeepContext()

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
        line_count = len(source.splitlines())
        function_count = (
            sum(
                isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef)
                for node in ast.walk(module)
            )
            if module is not None
            else 0
        )
        return ParsedPythonFile(
            path=relative_path,
            classes=classes,
            functions=functions,
            imports=imports[:12],
            first_docstring=ast.get_docstring(module) if module is not None else None,
            line_count=line_count,
            function_count=function_count,
            complexity_estimate=self._estimate_complexity(module) if module is not None else 0,
            is_entry_point=detect_entry_point(relative_path, source),
            dependency_imports=self._dependency_imports_from_module(module) if module is not None else [],
            function_details=details.functions,
            class_details=details.classes,
            call_refs=details.call_refs,
            route_patterns=details.routes,
        )

    def _parse_with_ast(
        self,
        source: str,
        relative_path: str,
        module: ast.Module | None,
    ) -> ParsedPythonFile:
        if module is None:
            return ParsedPythonFile(
                path=relative_path,
                classes=[],
                functions=[],
                imports=[],
                first_docstring=None,
                line_count=len(source.splitlines()),
                is_entry_point=detect_entry_point(relative_path, source),
            )

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
        details = self._deep_context_from_module(module)
        return ParsedPythonFile(
            path=relative_path,
            classes=classes,
            functions=functions,
            imports=imports[:12],
            first_docstring=ast.get_docstring(module),
            line_count=len(source.splitlines()),
            function_count=len(functions),
            complexity_estimate=self._estimate_complexity(module),
            is_entry_point=detect_entry_point(relative_path, source),
            dependency_imports=self._dependency_imports_from_module(module),
            function_details=details.functions,
            class_details=details.classes,
            call_refs=details.call_refs,
            route_patterns=details.routes,
        )

    @staticmethod
    def _parse_ast(source: str) -> ast.Module | None:
        try:
            return ast.parse(source)
        except SyntaxError:
            return None

    @staticmethod
    def _dependency_imports_from_module(module: ast.AST) -> list[str]:
        imports: list[str] = []
        for node in ast.walk(module):
            if isinstance(node, ast.Import):
                imports.extend(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom):
                prefix = "." * node.level
                base = prefix + (node.module or "")
                for alias in node.names:
                    if alias.name != "*":
                        imports.append(f"{base}.{alias.name}" if node.module else f"{prefix}{alias.name}")
                if node.module:
                    imports.append(base)
        return list(dict.fromkeys(imports))

    @staticmethod
    def _estimate_complexity(module: ast.AST) -> int:
        complexity = 0
        control_flow_nodes = (
            ast.If,
            ast.For,
            ast.AsyncFor,
            ast.While,
            ast.ExceptHandler,
            ast.With,
            ast.AsyncWith,
            ast.Assert,
        )
        for node in ast.walk(module):
            if isinstance(node, control_flow_nodes):
                complexity += 1
            elif isinstance(node, ast.BoolOp):
                complexity += max(0, len(node.values) - 1)
        return complexity

    @classmethod
    def _deep_context_from_module(cls, module: ast.Module) -> _PythonDeepContext:
        functions: list[ParsedFunction] = []
        classes: list[ParsedClass] = []
        routes: list[ParsedRoute] = []
        call_refs: list[str] = []

        for node in ast.walk(module):
            if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
                function_calls = cls._calls_in_node(node)
                decorators = [cls._expression_text(decorator) for decorator in node.decorator_list]
                functions.append(
                    ParsedFunction(
                        name=node.name,
                        params=[arg.arg for arg in [*node.args.posonlyargs, *node.args.args, *node.args.kwonlyargs]],
                        return_type=cls._expression_text(node.returns) if node.returns is not None else None,
                        decorators=decorators,
                        docstring=ast.get_docstring(node),
                        start_line=getattr(node, "lineno", 0),
                        end_line=getattr(node, "end_lineno", getattr(node, "lineno", 0)),
                        calls=function_calls,
                    )
                )
                call_refs.extend(function_calls)
                routes.extend(cls._routes_from_function(node, decorators))
            elif isinstance(node, ast.ClassDef):
                classes.append(
                    ParsedClass(
                        name=node.name,
                        bases=[cls._expression_text(base) for base in node.bases],
                        decorators=[cls._expression_text(decorator) for decorator in node.decorator_list],
                        docstring=ast.get_docstring(node),
                        start_line=getattr(node, "lineno", 0),
                        end_line=getattr(node, "end_lineno", getattr(node, "lineno", 0)),
                        methods=[
                            child.name
                            for child in node.body
                            if isinstance(child, ast.FunctionDef | ast.AsyncFunctionDef)
                        ],
                    )
                )

        return _PythonDeepContext(
            functions=functions,
            classes=classes,
            routes=routes,
            call_refs=list(dict.fromkeys(call_refs)),
        )

    @classmethod
    def _routes_from_function(
        cls,
        node: ast.FunctionDef | ast.AsyncFunctionDef,
        decorators: list[str],
    ) -> list[ParsedRoute]:
        routes: list[ParsedRoute] = []
        for decorator, original in zip(decorators, node.decorator_list, strict=True):
            if not isinstance(original, ast.Call) or not original.args:
                continue
            if not isinstance(original.args[0], ast.Constant) or not isinstance(original.args[0].value, str):
                continue
            method = decorator.split("(", 1)[0].rsplit(".", 1)[-1].upper()
            if method in {"GET", "POST", "PUT", "PATCH", "DELETE", "ROUTE", "WEBSOCKET"}:
                routes.append(
                    ParsedRoute(
                        method=method,
                        path=original.args[0].value,
                        handler=node.name,
                        line=getattr(node, "lineno", 0),
                    )
                )
        return routes

    @classmethod
    def _calls_in_node(cls, node: ast.AST) -> list[str]:
        calls: list[str] = []
        for child in ast.walk(node):
            if isinstance(child, ast.Call):
                calls.append(cls._call_name(child.func))
        return [call for call in dict.fromkeys(calls) if call]

    @classmethod
    def _call_name(cls, node: ast.AST) -> str:
        if isinstance(node, ast.Name):
            return node.id
        if isinstance(node, ast.Attribute):
            base = cls._call_name(node.value)
            return f"{base}.{node.attr}" if base else node.attr
        return ""

    @staticmethod
    def _expression_text(node: ast.AST | None) -> str:
        if node is None:
            return ""
        try:
            return ast.unparse(node)
        except Exception:
            return ""

    @staticmethod
    def _importance_key(path: Path) -> tuple[int, int, str]:
        return source_file_priority(
            path,
            entry_names=PYTHON_ENTRY_NAMES,
            core_path_parts=PYTHON_CORE_PATH_PARTS,
            test_name_prefixes=("test_",),
        )

    @staticmethod
    def _build_tree_sitter_parser():
        try:
            from tree_sitter_language_pack import get_parser

            return get_parser("python")
        except Exception:
            return None


@dataclass(frozen=True)
class _PythonDeepContext:
    functions: list[ParsedFunction] = field(default_factory=list)
    classes: list[ParsedClass] = field(default_factory=list)
    routes: list[ParsedRoute] = field(default_factory=list)
    call_refs: list[str] = field(default_factory=list)
