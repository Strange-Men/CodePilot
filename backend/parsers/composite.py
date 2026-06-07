from __future__ import annotations

from pathlib import Path

from backend.parsers.base import ParsedSourceFile, SourceParser


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
        parts = [part.lower() for part in path.parts]
        name = path.name.lower()
        score = 50
        if name in {
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
        }:
            score -= 20
        if any(part in {"api", "app", "core", "pages", "routes", "services", "src"} for part in parts):
            score -= 10
        if any(part in {"test", "tests", "__tests__"} or part.startswith("test") for part in parts):
            score += 8
        return score, len(parts), path.as_posix()
