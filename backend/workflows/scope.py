from __future__ import annotations

from pathlib import Path


def parse_changed_files(values: list[str] | tuple[str, ...]) -> set[str]:
    paths: set[str] = set()
    for value in values:
        for raw_line in str(value).splitlines():
            path = _normalize_candidate(raw_line)
            if path:
                paths.add(path)
    return paths


def parse_unified_diff_paths(diff_text: str) -> set[str]:
    paths: set[str] = set()
    for raw_line in diff_text.splitlines():
        line = raw_line.strip()
        if line.startswith("diff --git "):
            parts = line.split()
            if len(parts) >= 4:
                paths.update(filter(None, (_normalize_candidate(parts[2]), _normalize_candidate(parts[3]))))
        elif line.startswith("+++ ") or line.startswith("--- "):
            parts = line.split(maxsplit=1)
            if len(parts) == 2:
                path = _normalize_candidate(parts[1])
                if path:
                    paths.add(path)
    return paths


def parse_diff_file(path: Path) -> set[str]:
    return parse_unified_diff_paths(path.read_text(encoding="utf-8"))


def _normalize_candidate(candidate: str) -> str:
    path = candidate.strip().strip('"').replace("\\", "/")
    if not path or path == "/dev/null":
        return ""
    for prefix in ("a/", "b/"):
        if path.startswith(prefix):
            path = path.removeprefix(prefix)
    if path.startswith("/dev/null"):
        return ""
    return path.lstrip("/")
