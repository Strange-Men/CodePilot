from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import PurePosixPath

ENTRY_POINT_NAMES = {
    "main.py",
    "app.py",
    "server.py",
    "manage.py",
    "cli.py",
    "__main__.py",
    "main.js",
    "main.jsx",
    "main.ts",
    "main.tsx",
    "app.js",
    "app.jsx",
    "app.ts",
    "app.tsx",
    "server.js",
    "server.jsx",
    "server.ts",
    "server.tsx",
    "cli.js",
    "cli.jsx",
    "cli.ts",
    "cli.tsx",
}
CORE_PATH_PARTS = {
    "api",
    "core",
    "domain",
    "llm",
    "models",
    "parsers",
    "reviewers",
    "services",
}
DOCUMENTATION_PATH_PARTS = {"doc", "docs", "documentation", "examples"}
TEST_PATH_PARTS = {"test", "tests", "__tests__"}
FRAMEWORK_BOOTSTRAP_MARKERS = {
    "@nestjs/core",
    "createapp(",
    "createroot(",
    "django.core.management",
    "express(",
    "fastapi(",
    "flask(",
    "react-dom/client",
    "uvicorn.run(",
}


@dataclass(frozen=True)
class ScoreInput:
    path: str
    line_count: int
    complexity_estimate: int
    is_entry_point: bool = False


@dataclass(frozen=True)
class ScoredFile:
    path: str
    score: float
    label: str
    role: str


def detect_entry_point(path: str, source: str) -> bool:
    normalized_path = path.replace("\\", "/").lower()
    name = PurePosixPath(normalized_path).name
    compact_source = "".join(source.lower().split())
    return (
        name in ENTRY_POINT_NAMES
        or "__main__" in name
        or "main" in PurePosixPath(name).stem
        or "__main__" in source
        or any(marker in compact_source for marker in FRAMEWORK_BOOTSTRAP_MARKERS)
    )


def score_files(files: Iterable[ScoreInput]) -> dict[str, ScoredFile]:
    score_inputs = list(files)
    adjusted_scores = {
        file.path: max(0.0, _base_score(file) + _score_modifier(file.path))
        for file in score_inputs
    }
    maximum = max(adjusted_scores.values(), default=0.0)

    scored: dict[str, ScoredFile] = {}
    for file in score_inputs:
        adjusted = adjusted_scores[file.path]
        normalized = (adjusted / maximum * 100.0) if maximum > 0 else 0.0
        score = round(min(100.0, max(0.0, normalized)), 2)
        scored[file.path] = ScoredFile(
            path=file.path,
            score=score,
            label=importance_label(score),
            role=file_role(file.path, file.is_entry_point),
        )
    return scored


def importance_label(score: float) -> str:
    if score >= 90:
        return "Critical"
    if score >= 70:
        return "High"
    if score >= 40:
        return "Medium"
    if score >= 20:
        return "Low"
    return "Peripheral"


def file_role(path: str, is_entry_point: bool) -> str:
    if is_entry_point:
        return "Entry Point"
    if is_core_module(path):
        return "Core Module"
    return "Supporting File"


def is_core_module(path: str) -> bool:
    return bool(_path_parts(path) & CORE_PATH_PARTS)


def is_test_file(path: str) -> bool:
    parts = _path_parts(path)
    name = PurePosixPath(path.replace("\\", "/").lower()).name
    return (
        bool(parts & TEST_PATH_PARTS)
        or name.startswith("test_")
        or ".test." in name
        or ".spec." in name
    )


def is_documentation_file(path: str) -> bool:
    return bool(_path_parts(path) & DOCUMENTATION_PATH_PARTS)


def _base_score(file: ScoreInput) -> float:
    return (file.line_count * 0.3) + (file.complexity_estimate * 0.7)


def _score_modifier(path: str) -> float:
    modifier = 0.0
    if is_test_file(path):
        modifier -= 20.0
    if is_documentation_file(path):
        modifier -= 25.0
    if is_core_module(path):
        modifier += 10.0
    return modifier


def _path_parts(path: str) -> set[str]:
    return set(PurePosixPath(path.replace("\\", "/").lower()).parts)
