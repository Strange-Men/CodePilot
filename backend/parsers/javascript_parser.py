from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

from backend.parsers.base import ParsedFunction, ParsedRoute, ParsedSourceFile, SourceParser
from backend.services.sandbox import IGNORE_DIRS
from backend.services.scoring import detect_entry_point
from backend.services.source_selection import source_file_priority

JAVASCRIPT_EXTENSIONS = {".js", ".jsx"}
TYPESCRIPT_EXTENSIONS = {".ts", ".tsx"}
SCRIPT_EXTENSIONS = JAVASCRIPT_EXTENSIONS | TYPESCRIPT_EXTENSIONS
SCRIPT_ENTRY_NAMES = {
    "index.js",
    "index.jsx",
    "index.ts",
    "index.tsx",
    "main.ts",
    "main.js",
    "app.ts",
    "app.js",
}
SCRIPT_CORE_PATH_PARTS = {"src", "app", "pages", "routes", "api", "components", "services", "lib"}


@dataclass(frozen=True)
class ParsedJavaScriptFile(ParsedSourceFile):
    exported_symbols: list[str] = field(default_factory=list)


class JavaScriptParser(SourceParser):
    language = "javascript"
    extensions = JAVASCRIPT_EXTENSIONS

    def discover_files(self, repo_dir: Path, max_files: int, max_file_size_bytes: int) -> tuple[list[Path], int, int]:
        candidates: list[Path] = []
        total_source_files = 0
        skipped = 0

        for path in repo_dir.rglob("*"):
            if path.is_dir() or path.suffix.lower() not in self.extensions:
                continue
            if any(part in IGNORE_DIRS for part in path.parts):
                continue
            total_source_files += 1
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
        return selected, total_source_files, skipped

    def parse_file(self, repo_dir: Path, path: Path) -> ParsedJavaScriptFile:
        source = path.read_text(encoding="utf-8", errors="replace")
        relative_path = path.relative_to(repo_dir).as_posix()
        return self.parse_source(source, relative_path)

    def parse_source(self, source: str, relative_path: str) -> ParsedJavaScriptFile:
        imports = self._extract_imports(source)
        classes = self._extract_classes(source)
        functions = self._extract_functions(source)
        exported_symbols = self._extract_exported_symbols(source)
        function_details = self._extract_function_details(source)
        return ParsedJavaScriptFile(
            path=relative_path,
            classes=classes,
            functions=functions,
            imports=imports,
            first_docstring=self._extract_leading_comment(source),
            line_count=len(source.splitlines()),
            function_count=self._count_functions(source),
            complexity_estimate=self._estimate_complexity(source),
            is_entry_point=detect_entry_point(relative_path, source),
            dependency_imports=self._extract_dependency_imports(source),
            exported_symbols=exported_symbols,
            function_details=function_details,
            call_refs=self._extract_call_refs(source),
            route_patterns=self._extract_route_patterns(source),
        )

    @staticmethod
    def _count_functions(source: str) -> int:
        return len(re.findall(r"\bfunction\b", source)) + source.count("=>")

    @staticmethod
    def _estimate_complexity(source: str) -> int:
        control_flow = sum(
            len(re.findall(rf"\b{keyword}\b", source))
            for keyword in ("if", "for", "while", "catch")
        )
        return control_flow + source.count("&&") + source.count("||") + source.count("?")

    @staticmethod
    def _extract_imports(source: str) -> list[str]:
        imports: list[str] = []
        patterns = [
            r"^\s*import\s+.+?from\s+['\"][^'\"]+['\"];?",
            r"^\s*import\s+['\"][^'\"]+['\"];?",
            r"^\s*export\s+.+?from\s+['\"][^'\"]+['\"];?",
            r"\brequire\(\s*['\"][^'\"]+['\"]\s*\)",
        ]
        for pattern in patterns:
            for match in re.finditer(pattern, source, re.MULTILINE):
                imports.append(" ".join(match.group(0).strip().split())[:120])
        return _dedupe(imports)[:12]

    @staticmethod
    def _extract_dependency_imports(source: str) -> list[str]:
        imports: list[str] = []
        patterns = [
            r"\b(?:import|export)\s+(?:type\s+)?(?:[^;\n]*?\s+from\s+)?['\"](?P<specifier>[^'\"]+)['\"]",
            r"\brequire\(\s*['\"](?P<specifier>[^'\"]+)['\"]\s*\)",
            r"\bimport\(\s*['\"](?P<specifier>[^'\"]+)['\"]\s*\)",
        ]
        for pattern in patterns:
            imports.extend(
                match.group("specifier")
                for match in re.finditer(pattern, source, re.MULTILINE)
            )
        return _dedupe(imports)

    @staticmethod
    def _extract_classes(source: str) -> list[str]:
        classes = [
            match.group("name")
            for match in re.finditer(
                r"^\s*(?:export\s+default\s+|export\s+)?class\s+(?P<name>[A-Za-z_$][\w$]*)",
                source,
                re.MULTILINE,
            )
        ]
        return _dedupe(classes)

    @staticmethod
    def _extract_functions(source: str) -> list[str]:
        functions: list[str] = []
        declaration_patterns = [
            r"^\s*(?:export\s+(?:default\s+)?)?(?:async\s+)?function\s+(?P<name>[A-Za-z_$][\w$]*)\s*\(",
            r"^\s*(?:export\s+)?(?:const|let|var)\s+(?P<name>[A-Za-z_$][\w$]*)\s*=\s*(?:async\s*)?\([^)]*\)\s*=>",
            r"^\s*(?:export\s+)?(?:const|let|var)\s+(?P<name>[A-Za-z_$][\w$]*)\s*=\s*(?:async\s+)?function\b",
        ]
        for pattern in declaration_patterns:
            functions.extend(
                match.group("name") for match in re.finditer(pattern, source, re.MULTILINE)
            )
        return _dedupe(functions)

    @staticmethod
    def _extract_exported_symbols(source: str) -> list[str]:
        exported: list[str] = []
        declaration_pattern = (
            r"^\s*export\s+(?:default\s+)?"
            r"(?:async\s+)?(?:class|function|const|let|var|interface|type|enum)\s+"
            r"(?P<name>[A-Za-z_$][\w$]*)"
        )
        exported.extend(
            match.group("name") for match in re.finditer(declaration_pattern, source, re.MULTILINE)
        )
        for match in re.finditer(r"^\s*export\s*\{(?P<body>[^}]+)\}", source, re.MULTILINE):
            for symbol in match.group("body").split(","):
                cleaned = symbol.strip()
                if not cleaned:
                    continue
                exported.append(cleaned.split(" as ")[-1].strip())
        if re.search(r"^\s*export\s+default\s+(?!class|function\b)", source, re.MULTILINE):
            exported.append("default")
        return _dedupe(exported)

    @staticmethod
    def _extract_function_details(source: str) -> list[ParsedFunction]:
        details: list[ParsedFunction] = []
        patterns = [
            r"^\s*(?:export\s+(?:default\s+)?)?(?:async\s+)?function\s+(?P<name>[A-Za-z_$][\w$]*)\s*\((?P<params>[^)]*)\)",
            r"^\s*(?:export\s+)?(?:const|let|var)\s+(?P<name>[A-Za-z_$][\w$]*)\s*=\s*(?:async\s*)?\((?P<params>[^)]*)\)\s*=>",
        ]
        line_offsets = _line_offsets(source)
        for pattern in patterns:
            for match in re.finditer(pattern, source, re.MULTILINE):
                details.append(
                    ParsedFunction(
                        name=match.group("name"),
                        params=[
                            param.strip().split("=", 1)[0].strip()
                            for param in match.group("params").split(",")
                            if param.strip()
                        ],
                        start_line=_line_for_offset(line_offsets, match.start()),
                        end_line=_line_for_offset(line_offsets, match.end()),
                    )
                )
        return details

    @staticmethod
    def _extract_call_refs(source: str) -> list[str]:
        calls = [
            match.group("name")
            for match in re.finditer(r"\b(?P<name>[A-Za-z_$][\w$]*(?:\.[A-Za-z_$][\w$]*)?)\s*\(", source)
            if match.group("name") not in {"function", "if", "for", "while", "switch", "catch"}
        ]
        return _dedupe(calls)[:80]

    @staticmethod
    def _extract_route_patterns(source: str) -> list[ParsedRoute]:
        routes: list[ParsedRoute] = []
        line_offsets = _line_offsets(source)
        pattern = (
            r"\b(?:app|router|server)\.(?P<method>get|post|put|patch|delete|use)\s*"
            r"\(\s*['\"](?P<path>[^'\"]+)['\"]\s*,\s*(?P<handler>[A-Za-z_$][\w$]*)?"
        )
        for match in re.finditer(pattern, source, re.IGNORECASE):
            routes.append(
                ParsedRoute(
                    method=match.group("method").upper(),
                    path=match.group("path"),
                    handler=match.group("handler") or "inline",
                    line=_line_for_offset(line_offsets, match.start()),
                )
            )
        return routes

    @staticmethod
    def _extract_leading_comment(source: str) -> str | None:
        stripped = source.lstrip()
        block = re.match(r"/\*\*(?P<body>.*?)\*/", stripped, re.DOTALL)
        if block:
            lines = [line.strip(" *") for line in block.group("body").splitlines()]
            return " ".join(line for line in lines if line).strip() or None
        line_comments = re.match(r"(?P<body>(?://[^\n]*\n)+)", stripped)
        if line_comments:
            lines = [line.removeprefix("//").strip() for line in line_comments.group("body").splitlines()]
            return " ".join(line for line in lines if line).strip() or None
        return None

    @staticmethod
    def _importance_key(path: Path) -> tuple[int, int, str]:
        return source_file_priority(
            path,
            entry_names=SCRIPT_ENTRY_NAMES,
            core_path_parts=SCRIPT_CORE_PATH_PARTS,
        )


class TypeScriptParser(JavaScriptParser):
    language = "typescript"
    extensions = TYPESCRIPT_EXTENSIONS


def _dedupe(items: list[str]) -> list[str]:
    seen: set[str] = set()
    deduped: list[str] = []
    for item in items:
        if item and item not in seen:
            seen.add(item)
            deduped.append(item)
    return deduped


def _line_offsets(source: str) -> list[int]:
    offsets = [0]
    for match in re.finditer("\n", source):
        offsets.append(match.end())
    return offsets


def _line_for_offset(offsets: list[int], offset: int) -> int:
    line = 1
    for index, line_offset in enumerate(offsets, start=1):
        if line_offset > offset:
            break
        line = index
    return line
