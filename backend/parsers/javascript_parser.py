from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from backend.parsers.base import ParsedSourceFile, SourceParser

IGNORE_DIRS = {
    "node_modules",
    "dist",
    "build",
    "coverage",
    ".git",
    ".next",
    ".turbo",
    ".cache",
    "vendor",
}

JAVASCRIPT_EXTENSIONS = {".js", ".jsx"}
TYPESCRIPT_EXTENSIONS = {".ts", ".tsx"}
SCRIPT_EXTENSIONS = JAVASCRIPT_EXTENSIONS | TYPESCRIPT_EXTENSIONS


@dataclass(frozen=True)
class ParsedJavaScriptFile(ParsedSourceFile):
    exported_symbols: list[str]


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
        imports = self._extract_imports(source)
        classes = self._extract_classes(source)
        functions = self._extract_functions(source)
        exported_symbols = self._extract_exported_symbols(source)
        return ParsedJavaScriptFile(
            path=relative_path,
            classes=classes,
            functions=functions,
            imports=imports,
            first_docstring=self._extract_leading_comment(source),
            exported_symbols=exported_symbols,
        )

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
        parts = [part.lower() for part in path.parts]
        name = path.name.lower()
        score = 50
        if name in {"index.js", "index.jsx", "index.ts", "index.tsx", "main.ts", "main.js", "app.ts", "app.js"}:
            score -= 20
        if any(part in {"src", "app", "pages", "routes", "api", "components", "services", "lib"} for part in parts):
            score -= 10
        if any(part in {"tests", "test", "__tests__"} or part.startswith("test") for part in parts):
            score += 8
        return (score, len(parts), path.as_posix())


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
