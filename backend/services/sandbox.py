from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from backend.services.source_selection import source_file_priority

ALLOWED_SOURCE_EXTENSIONS = {".py", ".js", ".jsx", ".ts", ".tsx"}
IGNORE_DIRS = {
    ".cache",
    ".git",
    ".next",
    ".turbo",
    ".venv",
    "__pycache__",
    "build",
    "coverage",
    "dist",
    "node_modules",
    "vendor",
    "venv",
}
ENTRY_NAMES = {
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
CORE_PATH_PARTS = {"api", "app", "core", "pages", "routes", "services", "src"}
REDACTED = "[REDACTED]"

SECRET_PATTERNS = (
    re.compile(
        r"(?im)(?P<prefix>\b(?:api[_-]?key|access[_-]?token|auth[_-]?token|client[_-]?secret|"
        r"password|secret)\b\s*[:=]\s*[\"']?)(?P<secret>[^\s\"']{6,})"
    ),
    re.compile(r"(?i)\bBearer\s+(?P<secret>[A-Za-z0-9._~+/=-]{8,})"),
    re.compile(r"\b(?P<secret>gh[pousr]_[A-Za-z0-9]{20,})\b"),
    re.compile(r"\b(?P<secret>sk-[A-Za-z0-9_-]{16,})\b"),
    re.compile(
        r"-----BEGIN [A-Z ]*PRIVATE KEY-----.*?-----END [A-Z ]*PRIVATE KEY-----",
        re.DOTALL,
    ),
)


def redact_secrets(text: str) -> str:
    redacted = text
    for pattern in SECRET_PATTERNS:
        if "prefix" in pattern.groupindex:
            redacted = pattern.sub(lambda match: f"{match.group('prefix')}{REDACTED}", redacted)
        elif "secret" in pattern.groupindex:
            redacted = pattern.sub(
                lambda match: match.group(0).replace(match.group("secret"), REDACTED),
                redacted,
            )
        else:
            redacted = pattern.sub(REDACTED, redacted)
    return redacted


@dataclass(frozen=True)
class SandboxFile:
    path: str
    absolute_path: Path
    extension: str
    size_bytes: int
    line_count: int
    content: str


@dataclass(frozen=True)
class SandboxManifest:
    repo_dir: Path
    files: tuple[SandboxFile, ...]
    total_supported_files: int
    skipped_files: int

    def for_extensions(self, extensions: set[str]) -> list[SandboxFile]:
        return [file for file in self.files if file.extension in extensions]

    def get(self, relative_path: str) -> SandboxFile:
        normalized = relative_path.replace("\\", "/")
        for file in self.files:
            if file.path == normalized:
                return file
        raise KeyError(normalized)


class SandboxFilter:
    def __init__(self, *, max_lines_per_file: int = 5000) -> None:
        self.max_lines_per_file = max_lines_per_file

    def build_manifest(
        self,
        repo_dir: Path,
        max_files: int,
        max_file_size_bytes: int,
    ) -> SandboxManifest:
        root = repo_dir.resolve(strict=True)
        candidates: list[SandboxFile] = []
        total = 0
        skipped = 0

        for path in repo_dir.rglob("*"):
            if path.is_dir() or path.suffix.lower() not in ALLOWED_SOURCE_EXTENSIONS:
                continue
            if any(part in IGNORE_DIRS for part in path.relative_to(repo_dir).parts):
                continue
            total += 1
            if self._is_unsafe_path(root, path):
                skipped += 1
                continue
            try:
                size = path.stat().st_size
                if size > max_file_size_bytes:
                    skipped += 1
                    continue
                content = redact_secrets(path.read_text(encoding="utf-8", errors="replace"))
            except OSError:
                skipped += 1
                continue
            line_count = len(content.splitlines())
            if line_count > self.max_lines_per_file:
                skipped += 1
                continue
            candidates.append(
                SandboxFile(
                    path=path.relative_to(repo_dir).as_posix(),
                    absolute_path=path,
                    extension=path.suffix.lower(),
                    size_bytes=size,
                    line_count=line_count,
                    content=content,
                )
            )

        selected = sorted(candidates, key=lambda file: self._importance_key(file.absolute_path))[:max_files]
        skipped += max(0, len(candidates) - len(selected))
        return SandboxManifest(
            repo_dir=root,
            files=tuple(selected),
            total_supported_files=total,
            skipped_files=skipped,
        )

    @staticmethod
    def _is_unsafe_path(root: Path, path: Path) -> bool:
        if path.is_symlink():
            return True
        current = path.parent
        while current != root and current != current.parent:
            if current.is_symlink():
                return True
            current = current.parent
        try:
            return not path.resolve(strict=True).is_relative_to(root)
        except OSError:
            return True

    @staticmethod
    def _importance_key(path: Path) -> tuple[int, int, str]:
        return source_file_priority(
            path,
            entry_names=ENTRY_NAMES,
            core_path_parts=CORE_PATH_PARTS,
        )
