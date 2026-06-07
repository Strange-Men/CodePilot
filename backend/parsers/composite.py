from __future__ import annotations

from pathlib import Path

from backend.parsers.base import ParsedSourceFile, SourceParser
from backend.services.source_selection import source_file_priority

COMPOSITE_ENTRY_NAMES = {
    "__main__.py",
    "app.js",
    "app.py",
    "app.ts",
    "index.js",
    "index.ts",
    "main.js",
    "main.py",
    "main.ts",
    "server.js",
    "server.py",
    "server.ts",
}
COMPOSITE_CORE_PATH_PARTS = {"api", "app", "core", "pages", "routes", "services", "src"}


class CompositeSourceParser(SourceParser):
    language = "mixed"

    def __init__(self, parsers: list[SourceParser]) -> None:
        self.parsers = tuple(parsers)
        self.languages = tuple(parser.language for parser in parsers)
        self._parsers_by_extension = {
            extension: parser
            for parser in parsers
            for extension in self._extensions_for(parser.language)
        }

    def discover_files(
        self,
        repo_dir: Path,
        max_files: int,
        max_file_size_bytes: int,
    ) -> tuple[list[Path], int, int]:
        candidates: dict[str, Path] = {}
        parser_candidates: list[list[Path]] = []
        total = 0
        for parser in self.parsers:
            files, parser_total, _parser_skipped = parser.discover_files(
                repo_dir,
                max_files,
                max_file_size_bytes,
            )
            total += parser_total
            parser_candidates.append(files)
            for path in files:
                candidates[path.relative_to(repo_dir).as_posix()] = path

        prioritized: list[Path] = []
        if max_files >= len(parser_candidates):
            prioritized.extend(files[0] for files in parser_candidates if files)
        prioritized.extend(sorted(candidates.values(), key=self._importance_key))
        selected = list(dict.fromkeys(prioritized))[:max_files]
        return selected, total, max(0, total - len(selected))

    def parse_file(self, repo_dir: Path, path: Path) -> ParsedSourceFile:
        try:
            parser = self._parsers_by_extension[path.suffix.lower()]
        except KeyError as exc:
            raise ValueError(f"No matching parser for source file: {path}") from exc
        return parser.parse_file(repo_dir, path)

    @staticmethod
    def _extensions_for(language: str) -> tuple[str, ...]:
        return {
            "python": (".py",),
            "javascript": (".js", ".jsx"),
            "typescript": (".ts", ".tsx"),
        }.get(language, ())

    @staticmethod
    def _importance_key(path: Path) -> tuple[int, int, str]:
        return source_file_priority(
            path,
            entry_names=COMPOSITE_ENTRY_NAMES,
            core_path_parts=COMPOSITE_CORE_PATH_PARTS,
        )
